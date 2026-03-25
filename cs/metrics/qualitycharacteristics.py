#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Module QualityCharacteristics
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

''' Imported libraries '''
import cdbwrapc

from cdb import sqlapi
from cdb import ue
from cdb import auth
from cdb import util
from cdb import misc
from cdb import tools
from cdb import cdbtime
from cdb import rte
from cdb.platform import gui
from cdb.objects import Object
from cdb.objects import Reference_N
from cdb.objects import Reference_1
from cdb.objects import Reference_Methods
from cdb.objects import ReferenceMethods_1
from cdb.objects import ReferenceMethods_N
from cdb.objects import Forward
from cdb.objects import ByID
from cdb.objects import Rule
from cdb.objects import NULL
from cdb.objects import LocalizedField
from cdb.objects import State
from cdb.objects import Transition
from cdb.objects.org import WithSubject
from cdb.platform.mom import SimpleArguments
from cdb.platform.mom.relships import Relship
from cdb.platform.mom.entities import Entity
from cdb.platform.gui import I18nCatalogEntry
from cdb.sqlapi import SQLdbms_date
from cdb.sig import connect

from cs.metrics import targetprocessor
from cs.metrics import computationrules as ComputationRules
from cs.metrics import exceptions

from functools import partial

from datetime import date, timedelta
import calendar
import functools
import logging

''' References to corresponding cdb-classes '''
fEntity = Forward("cdb.platform.mom.entities.Entity")
fChildConfiguration = Forward("cs.metrics.qualitycharacteristics.ChildConfiguration")
fParentConfiguration = Forward("cs.metrics.qualitycharacteristics.ParentConfiguration")
fHistory = Forward("cs.metrics.qualitycharacteristics.History")
fQualityCharacteristic = Forward("cs.metrics.qualitycharacteristics.QualityCharacteristic")
fObjectQualityCharacteristic = Forward("cs.metrics.qualitycharacteristics.ObjectQualityCharacteristic")
fClassQualityCharacteristic = Forward("cs.metrics.qualitycharacteristics.ClassQualityCharacteristic")
fQCDefinition = Forward("cs.metrics.qualitycharacteristics.QCDefinition")
fObjectQCDefinition = Forward("cs.metrics.qualitycharacteristics.ObjectQCDefinition")
fClassQCDefinition = Forward("cs.metrics.qualitycharacteristics.ClassQCDefinition")
fRule = Forward("cdb.objects.Rule")
fAssociation = Forward("cs.metrics.qualitycharacteristics.ClassAssociation")
fKKZAssociation = Forward("cs.metrics.qualitycharacteristics.KKZClassAssociation")
fOKZAssociation = Forward("cs.metrics.qualitycharacteristics.OKZClassAssociation")
fQCUnit = Forward("cs.metrics.qualitycharacteristics.QCUnit")
fQCUnitType = Forward("cs.metrics.qualitycharacteristics.QCUnitType")
fGroupingValue = Forward("cs.metrics.qualitycharacteristics.GroupingValue")
fGroupingAttribute = Forward("cs.metrics.qualitycharacteristics.GroupingAttribute")
fComputationRule = Forward("cs.metrics.computationrules.ComputationRule")
fQCAction = Forward("cs.metrics.actions.QCAction")
fUpdateClock = Forward("cs.metrics.computationrules.UpdateClock")

period_catalog = None

LOG = logging.getLogger(__name__)


def resolve(name):
    global period_catalog

    if period_catalog is None:
        period_catalog = dict([(uc.period_de, uc.position) for uc in ComputationRules.UpdateClock.Query()])

    return period_catalog[name]


class memoize(object):
    """ Memoize decorator specific for object quality characteristics. """

    def __init__(self, function):
        self.function = function
        self.cache = {}

    def __call__(self, *args):
        try:
            obj = args[0]
            obj_id = obj.cdbf_object_id
            return self.cache[obj_id]
        except KeyError:
            value = self.function(*args)
            self.cache[id] = value
            return value
        except TypeError:
            # uncachable -- for instance, passing a list as an argument.
            # Better to not cache than to blow up entirely.
            return self.func(*args)
        except AttributeError:
            raise ue.Exception("just_a_replacement", "memoize only works with ObjectQualityCharacteristic objects")

    def __repr__(self):
        """Return the function's docstring."""
        return repr(self.function)

    def __get__(self, obj, objtype):
        """Support instance methods."""
        fn = functools.partial(self.__call__, obj)
        fn.reset = self.reset
        fn.__repr__ = self.__repr__
        return fn

    def reset(self):
        self.cache.clear()


# QC

class ClassAssociation(Object):
    """Association of a Class to a Quality characteristic"""

    __maps_to__ = "cdbqc_def2class"
    __classname__ = "cdbqc_def2class"

    # Reference to Object Rule which decides, for which object of the class there should be a quality characteristic
    ORule = Reference_1(fRule, fAssociation.obj_rule_name)

    # Reference to the computation rule, used to compute the value of the quality characteristics '''
    ComputationRule = Reference_1(fComputationRule, fComputationRule.cdb_object_id == fAssociation.computation_rule_id)

    # Reference to the definition of the quality characteristic '''
    Definition = Reference_1(fQCDefinition, fQCDefinition.cdb_object_id == fAssociation.cdbqc_def_object_id)

    UpdateClock = Reference_1(fUpdateClock, fUpdateClock.position == fAssociation.update_clock)

    def set_mandatory(self, ctx):
        '''
        Sets the choice of a computation rule as mandatory, if the checkbox "computed" is selected,
        and as readonly if the checkbox is not selected
        '''
        if "computed" in ctx.dialog.get_attribute_names():
            if self.computed == 1:
                ctx.set_fields_mandatory(['computation_rule_id', 'update_clock'])
            else:
                ctx.set_fields_readonly(['computation_rule_id', 'update_clock'])

    def update_next_computation(self, ctx):
        ''' Updates the date of the next computation '''
        from cs.metrics import services as Services

        if ctx.object.update_clock != self.update_clock:
            self.next_computation = Services.get_next_computation(self.update_clock)

    def GetExcludedFieldsOnExport(self):
        return ["next_computation"]

    event_map = {(('create', 'modify', 'copy'), 'pre_mask'): 'set_mandatory',
                 ('modify', ('post_mask')): 'update_next_computation'}


class OKZClassAssociation(ClassAssociation):
    ''' Association of a Class to a object-quality characteristic '''
    __classname__ = "cdbqc_obj_def2class"
    __match__ = fOKZAssociation.cdb_classname == "cdbqc_obj_def2class"

    ChildConfigurations = Reference_N(fChildConfiguration, fChildConfiguration.classname == fOKZAssociation.classname,
                                      fChildConfiguration.cdbqc_def_object_id == fOKZAssociation.cdbqc_def_object_id)
    ParentConfigurations = Reference_N(fParentConfiguration, fParentConfiguration.classname == fOKZAssociation.classname,
                                       fParentConfiguration.cdbqc_def_object_id == fOKZAssociation.cdbqc_def_object_id)

    # Reference to QualityCharacteristics
    def _getQualityCharacteristics(self):
        result = []

        if self.Definition:
            for qc in self.Definition.QualityCharacteristics:
                obj = ByID(qc.cdbf_object_id)
                if obj:
                    bases = list(obj.GetClassDef().getBaseClassNames())
                    bases.append(obj.GetClassname())

                    if self.classname in bases and \
                           (not self.ORule or self.ORule.match(obj)):
                        result.append(qc)
        return result

    QualityCharacteristics = Reference_Methods(fQualityCharacteristic,
                                               _getQualityCharacteristics)

    def createQCs(self):
        ''' After a status change from 'created' to 'valid'
            the quality characteristics will be created for
            all objects which satisfy the object rules.
        '''
        from cs.metrics import services as Services

        objrule = self.obj_rule_name
        rule = Rule.ByKeys(objrule)

        clsname = self.classname
        entity = Entity.ByKeys(classname=clsname)
        if not entity or not entity.getFqpyname():
            raise ue.Exception("just_a_replacement", "Entity {0} has no python name".format(clsname))

        VClass = tools.getObjectByName(entity.getFqpyname())
        if not VClass.HasField('cdb_object_id'):
            raise ue.Exception("just_a_replacement", "Entity {0} has no cdb_object_id".format(clsname))

        check_rule = False
        if not rule:
            # Case 1: there is no rule
            collection = VClass.Query()
            oids = collection.cdb_object_id
        else:
            try:
                # Case 2: there is a rule and no python references are involved
                stmt = rule.stmt(VClass)

                # we cannot use VClass.Query(sql=stmt) here, because if VClass
                # has a __match__ attribute, we get a ParameterError
                rs = sqlapi.RecordSet2(sql="SELECT cdb_object_id FROM (%s)" % stmt)
                oids = [r.cdb_object_id for r in rs]

            # Workaround E031098, E031106:
            # actually we should except only cdb.objects.InvalidTerm
            # but since there are so many problems with Rule.stmt
            # we except every exception
            except Exception:
                # Case 3: there is a rule which uses some python references
                check_rule = True
                collection = VClass.Query()
                oids = collection.cdb_object_id

        oids_with_qcs = self.Definition.QualityCharacteristics.cdbf_object_id
        for object_id in set(oids).difference(oids_with_qcs):
            obj = VClass.ByKeys(cdb_object_id=object_id)
            if not check_rule or rule.match(obj):
                args = {"cdbqc_def_object_id": self.cdbqc_def_object_id,
                         "cdbf_object_id": obj.cdb_object_id,
                         "classname": clsname
                        }
                obj.addQCArguments(args)
                ObjectQualityCharacteristic.CreateQC(**args)

        if self.Definition.computed:
            self.next_computation = Services.get_next_computation(self.update_clock)


class KKZClassAssociation(ClassAssociation):
    ''' Association of a Class to a object-quality characteristic '''
    __classname__ = "cdbqc_class_def2class"
    __match__ = fKKZAssociation.cdb_classname == "cdbqc_class_def2class"

    # Reference to QualityCharacteristics
    def _getQualityCharacteristics(self):
        def bases(qc):
            bs = list(cdbwrapc.CDBClassDef(qc.classname).getBaseClassNames())
            bs.append(qc.classname)
            return bs

        if self.Definition:
            return [qc for qc in self.Definition.QualityCharacteristics
                    if self.classname in bases(qc)]
        else:
            return []

    QualityCharacteristics = Reference_Methods(fQualityCharacteristic,
                                               _getQualityCharacteristics)

    """ Reference to the associated class """
    Class = Reference_1(fEntity, fEntity.classname == fKKZAssociation.classname)

    """ List of attributes, which define the grouping of the class """
    GroupingAttributes = Reference_N(fGroupingAttribute, (fGroupingAttribute.classname == fKKZAssociation.classname) &
                                        (fGroupingAttribute.cdbqc_def_object_id == fKKZAssociation.cdbqc_def_object_id))

    def createQCs(self, ctx=None):
        ''' After a status change from 'created' to 'valid'
            the quality characteristics will be created for
            all objects which satisfy the object rules.
        '''
        from cs.metrics import services as Services

        if self.GroupingAttributes:
            make_signature = lambda qc: ";;".join(["%s::%s" % (gv.attribute_name, gv.attribute_value) for gv in qc.Groupings])
            signatures = [make_signature(qc) for qc in self.QualityCharacteristics]

            # attrs = [attr.attribute_name for attr in self.GroupingAttributes]
            attrs = self.GroupingAttributes.attribute_name

            rs = sqlapi.RecordSet2(sql="SELECT DISTINCT %s FROM %s" % (', '.join(attrs), self.Class.getRelation()))
            for record in rs:
                if not (";;".join(["%s::%s" % item for item in record.items()]) in signatures):
                    qc = ClassQualityCharacteristic.CreateQC(cdbqc_def_object_id=self.cdbqc_def_object_id,
                                                             classname=self.classname)

                    for attribute_name in record.keys():
                        GroupingValue.Create(qc_object_id=qc.cdb_object_id,
                                             attribute_name=attribute_name,
                                             attribute_value=record[attribute_name])
        else:
            if not self.QualityCharacteristics:
                qc = ClassQualityCharacteristic.CreateQC(cdbqc_def_object_id=self.cdbqc_def_object_id,
                                                         classname=self.classname)

        if self.Definition.computed:
            self.next_computation = Services.get_next_computation(self.update_clock)


class ChildConfiguration(Object):
    """ Configuration of the successor of an objects relative to a quality characteristic for the purpose of aggregation """
    __maps_to__ = "cdbqc_children"
    __classname__ = "cdbqc_children"

    ORule = Reference_1(fRule, fChildConfiguration.obj_rule_name)
    Definition = Reference_1(fObjectQCDefinition, fObjectQCDefinition.cdb_object_id == fChildConfiguration.cdbqc_def_object_id)


class ParentConfiguration(Object):
    """ Configuration of the predecessor of an objects relative to a quality characteristic for the purpose of aggregation """
    __maps_to__ = "cdbqc_parents"
    __classname__ = "cdbqc_parents"

    ORule = Reference_1(fRule, fParentConfiguration.obj_rule_name)
    Definition = Reference_1(fObjectQCDefinition, fObjectQCDefinition.cdb_object_id == fParentConfiguration.cdbqc_def_object_id)


class QualityCharacteristic(WithSubject):
    """ Base Class for quality characteristics"""
    __maps_to__ = "cdbqc_quality_character"
    __classname__ = "cdbqc_quality_character"

    Historie = Reference_N(fHistory, fHistory.cdbqc_object_id == fQualityCharacteristic.cdb_object_id)
    QCActions = Reference_N(fQCAction, fQCAction.qc_object_id == fQualityCharacteristic.cdb_object_id)
    Definition = Reference_1(fQCDefinition, fQCDefinition.cdb_object_id == fQualityCharacteristic.cdbqc_def_object_id)

    def __setattr__(self, name, value):
        # FIXME: use properties for this
        if name == "target_value":
            self.set_target_value(value)
        elif name == "act_value":
            self.set_actual_value(value)
        else:
            super(QualityCharacteristic, self).__setattr__(name, value)

    def _createKeymap(self, objekt, child, k_referer, k_reference):
        ''' Support function to parse the keymap of a relationship '''
        result = {}
        for pair in k_referer.split(';'):
            lpair = pair.strip().split('=')
            result[lpair[1].strip()] = getattr(objekt, lpair[0].strip())

        for pair in k_reference.split(';'):
            lpair = pair.strip().split('=')
            result[lpair[1].strip()] = getattr(child, lpair[0].strip())

        return result

    def getWhereCondition(self, relation, root_alias):
        ''' Returns an SQL-Condition used to compute the value of computed quality characteristics.
            This method is implemented in the subclasses
        '''
        raise NotImplementedError("To be implemented in the subclasses")

    def compute(self, ctx=None):
        """ Computes the quality characteristic and store the new value
            in self.act_value
        """
        if self.Definition.computed and self.Association:
            self.Association.ComputationRule.compute(self)

    @staticmethod
    def get_target_fulfillment(act_value, target_value):
        if not target_value:
            return targetprocessor.TargetStatus.not_given.value  # @UndefinedVariable

        try:
            tp = targetprocessor.TargetProcessor(target_value)

            if act_value in (None, NULL, ""):
                status = targetprocessor.TargetStatus.not_given.value  # @UndefinedVariable
            else:
                result = tp(act_value)
                if result:
                    status = targetprocessor.TargetStatus.green.value  # @UndefinedVariable
                else:
                    status = targetprocessor.TargetStatus.red.value  # @UndefinedVariable
        except targetprocessor.InvalidTargetValue:
            return targetprocessor.TargetStatus.invalid.value  # @UndefinedVariable

        return status

    def getGrade(self):
        qgrade = self.grade_name
        if qgrade:
            return qgrade
        return ""

    def getValue(self, date):
        '''
        Returns the value of the quality characteristic at the date 'date'.

        :param date: A date
        :type date: A string in the format 'dd.mm.yyyy'
        '''
        if not date:
            return self.act_value
        else:
            cls = Entity.ByKeys("cdbqc_history")

            stmt = ("SELECT MAX(cdb_cdate) AS result FROM %s WHERE cdbqc_object_id = '%s' AND cdb_cdate <= %s" %
                                   (cls.getRelation(), self.cdb_object_id, SQLdbms_date(date + " 23:59:59")))
            rs = sqlapi.RecordSet2(sql=stmt)
            real_date = rs[0]["result"]

            if real_date != NULL:
                histories = self.Historie.Query(fHistory.cdb_cdate == real_date)
                return histories[-1].value
            else:
                return None

    def keepAttributes(self, ctx, **args):
        '''
        Keeps the required attributes for creation of a history object,
        in order to use them in later user exits.
        '''
        attributes = ctx.dialog.get_attribute_names()

        if 'guetegrad' in attributes:
            fguetegrad = ctx.dialog.guetegrad
            ctx.keep("guetegrad", fguetegrad)

        if 'comment' in attributes:
            fcomment = ctx.dialog.comment
            ctx.keep("comment", fcomment)

    def createHistoryObject(self, ctx=None, **kwargs):
        '''
        A history object will only be created, if an actual value is registered.
        That value could be registered manually or it could be taken from aggregate result,
        if available.
        The actual value, the quality grade and the optional comment will be saved as history,
        if there is not already an object with same date and value.
        '''

        if self.act_value != NULL:
            # Check by a database query if value and date already exists
            histories = History.KeywordQuery(cdbqc_object_id=self.cdb_object_id, value=self.act_value, cdb_cdate=self.cdb_mdate)
            if not histories:
                # Arguments needed to create a history entry, if the value not already exists and the value is not null
                args = {
                        "cdbqc_object_id": self.cdb_object_id,
                        "value": self.act_value,
                        "cdb_cdate": self.cdb_mdate,
                        "cdb_cpersno": self.cdb_mpersno,
                      }

                if ctx:
                    # If a quality grade is given, append it to the arguments
                    if ("guetegrad" in ctx.ue_args.get_attribute_names()):
                        if ctx.ue_args.guetegrad:
                            gg_obj = QCGrade.ByKeys(name_de=ctx.ue_args.guetegrad)
                            if gg_obj:
                                args.update({"cdbqc_qgrade_object_id": gg_obj.cdb_object_id})
                elif kwargs and "guetegrad" in kwargs.keys():
                    fguetegrad = kwargs.get("guetegrad")
                    gg_obj = QCGrade.ByKeys(name_de=fguetegrad)
                    if gg_obj:
                        args.update({"cdbqc_qgrade_object_id": gg_obj.cdb_object_id})

                # Create the history object using the collected arguments
                hobj = fHistory.Create(**args)

                # if a comment is given, save it together with the history object
                if ctx:
                    if "comment" in ctx.ue_args.get_attribute_names():
                        hobj.SetText("description", ctx.ue_args.comment)

    def presetDefinition(self, ctx):
        '''The definition of a quality characteristic should not be changed after creation'''
        ctx.set_fields_readonly(["cdbqc_def_object_id", "def_unit_object_id"])

    def checkStatus(self):
        ''' Determine status of actual value and target value for report '''
        if self.act_value and self.target_value:
            target_fulfillment = self.get_target_fulfillment(self.act_value,
                                                             self.target_value)
            if target_fulfillment == targetprocessor.TargetStatus.green.value:  # @UndefinedVariable
                status = 1
            elif target_fulfillment == targetprocessor.TargetStatus.red.value:  # @UndefinedVariable
                status = 0
            else:
                status = 0.5

        return status

    def set_value_readonly(self, ctx):
        ''' Sets the value of the quality characteristic as read-only, in case of a computed quality characteristic '''
        if self.Definition and self.Definition.computed == 1:
            ctx.set_readonly("act_value")

    def DeleteReferredObjects(self):
        # Delete history
        self.Historie.Delete()

        # Delete links to action
        self.QCActions.Delete()

    def CopyValues(self, rhs):
        rhs.Update(target_value=self.target_value,
                   act_value=self.act_value)
        for hist in self.Historie:
            hist.Copy(cdbqc_object_id=rhs.cdb_object_id)
        for qcac in self.QCActions:
            qcac.Copy(qc_object_id=rhs.cdb_object_id)

    def set_target_fulfillment(self, ctx=None):
        self.target_fulfillment = self.get_target_fulfillment(self.act_value,
                                                              self.target_value)

    def set_target_value(self, target_value):
        target_fulfillment = self.get_target_fulfillment(self.act_value,
                                                         target_value)

        if target_fulfillment == targetprocessor.TargetStatus.invalid.value:  # @UndefinedVariable
            raise targetprocessor.InvalidTargetValue

        self.Update(target_value=target_value, target_fulfillment=target_fulfillment)

    event_map = {(('create', 'modify', 'copy'), 'post'): ('createHistoryObject', 'set_target_fulfillment'),
                 (('create', 'modify', 'copy'), 'post_mask'): 'keepAttributes',
                 (('modify'), 'pre'): 'keepAttributes',
                 (('modify', 'copy'), 'pre_mask'): ('presetDefinition'),
                 (('create', 'modify', 'copy'), 'pre_mask'): ('set_value_readonly'),
                 ('cdbqc_compute', 'now'): 'compute'
               }


class ObjectQualityCharacteristic(QualityCharacteristic):
    """ Class for object-quality characteristics """
    __classname__ = "cdbqc_obj_quality_character"
    __match__ = fObjectQualityCharacteristic.cdb_classname == "cdbqc_obj_quality_character"

    ChildConfigurations = Reference_N(fChildConfiguration, fChildConfiguration.classname == fQualityCharacteristic.classname, fChildConfiguration.cdbqc_def_object_id == fQualityCharacteristic.cdbqc_def_object_id)
    ParentConfigurations = Reference_N(fParentConfiguration, fParentConfiguration.classname == fParentConfiguration.classname, fParentConfiguration.cdbqc_def_object_id == fQualityCharacteristic.cdbqc_def_object_id)

    def _getParents(self):
        """ Support method to compute the quality characteristic that precede the current one in the aggregation structure """
        objekt = ByID(self.cdbf_object_id)
        if objekt is None:
            exc = exceptions.OrphanedKPIException(self.cdb_object_id, self.cdbf_object_id)
            LOG.error(exc)
            raise exc
        parent_assignment = None

        for _parent_assignment in self.ParentConfigurations:
            if _parent_assignment.ORule:
                if _parent_assignment.ORule.match(objekt):
                    parent_assignment = _parent_assignment
                    break
            else:
                parent_assignment = _parent_assignment
                break

        if parent_assignment:
            relship = Relship.ByKeys(parent_assignment.relship_name)
            if relship.rs_profile == 'cdb_association_1_1':
                ParentList = [getattr(objekt, relship.rolename)]
            else:
                ParentList = getattr(objekt, relship.rolename)

            parents = [ObjectQualityCharacteristic.ByKeys(cdbqc_def_object_id=self.cdbqc_def_object_id,
                                                          cdbf_object_id=par.cdb_object_id)
                              for par in ParentList if par is not None]
            parents = [p for p in parents if p is not None]
            return parents
        else:
            return None

    # Reference to the quality characteristic that precede the current one in the aggregation structure
    Parents = ReferenceMethods_N(fObjectQualityCharacteristic, _getParents)

    def _getChildrenAndSuccessors(self):
        """ Support method to compute the objects that succeed the current one in the aggregation structure """
        objekt = ByID(self.cdbf_object_id)
        child_assignment = None

        for _child_assignment in self.ChildConfigurations:
            if _child_assignment.ORule:
                if _child_assignment.ORule.match(objekt):
                    child_assignment = _child_assignment
                    break
            else:
                child_assignment = _child_assignment
                break

        if child_assignment:
            relship = Relship.ByKeys(child_assignment.relship_name)

            # Collect all children objects in a list
            if relship.rs_profile == 'cdb_association_1_1':
                ChildrenList = [getattr(objekt, relship.rolename)]
            else:
                ChildrenList = getattr(objekt, relship.rolename)

            result = []
            for child in ChildrenList:
                qc = ObjectQualityCharacteristic.ByKeys(cdbqc_def_object_id=self.cdbqc_def_object_id, cdbf_object_id=child.cdb_object_id)
                if qc and qc.Association:
                    result.append((qc, child))
            return result
    ChildrenAndSuccessors = ReferenceMethods_N(fObjectQualityCharacteristic, _getChildrenAndSuccessors)

    def _getSuccessors(self):
        cas = self.ChildrenAndSuccessors
        return [successor for _child, successor in cas]
    Successors = ReferenceMethods_N(fObjectQualityCharacteristic, _getSuccessors)

    def _getChildren(self):
        """ Support method to compute the quality characteristic that succeed the current one in the aggregation structure """
        cas = self.ChildrenAndSuccessors
        return [child for child, _successor in cas]
    # Reference to the quality characteristic that succeed the current one in the aggregation structure
    Children = ReferenceMethods_N(fObjectQualityCharacteristic, _getChildren)

    Definition = Reference_1(fObjectQCDefinition, fObjectQCDefinition.cdb_object_id == fQualityCharacteristic.cdbqc_def_object_id)

    def _getAssociation(self, classname=None, object_id=None):
        if not classname:
            classname = self.classname
        if not object_id:
            object_id = self.cdbf_object_id

        """ Support method to compute the class association relative to the current quality characteristic """
        assos = fAssociation.Query((fAssociation.cdbqc_def_object_id == self.cdbqc_def_object_id) &
                                  (fAssociation.classname == classname))
        matches = [asso for asso in assos if not asso.ORule or asso.ORule.match(ByID(object_id))]
        if matches:
            return matches[0]
    Association = ReferenceMethods_1(fAssociation, _getAssociation)

    def getWhereCondition(self, relation, root_alias):
        """ Returns an SQL-Condition used to compute the value of computed quality characteristics. """
        return "{root_alias}.cdb_object_id='{cdbf_object_id}'".format(cdbf_object_id=self.cdbf_object_id, root_alias=root_alias)

    def evaluate_attribute(self, attr):
        """ Returns the value of the attribute attr of the object referred by the current quality characteristic """
        obj = ByID(self.cdbf_object_id)
        return getattr(obj, attr)

    def is_aggregate_value_uptodate(self):
        for child in self.Children:
            if child.needs_aggregation:
                return False

        for child in self.Children:
            if not ((child.Association and not child.Association.take_aggr_val) or
                        (child.is_aggregate_value_uptodate())):
                return False
        return True

    def aggregate_up_structure(self, ctx=None, force=False):
        """
        Computes the aggregate values of all the quality characteristics that precede the
        current one in the aggregation structure.

        Uses memoization, resets the cache before and after the computation

        :param ctx: CDB operation context (optional)
        :param force: If True aggregates also the quality characteristics with asynchronous aggregation (default False)
        :type force: boolean
        """
        if not self.Definition.asyncron or force:
            self.compute_aggregate_value.reset()
            self.aggregate_up(ctx, force=force)
            self.compute_aggregate_value.reset()

            if force and self.needs_aggregation:
                self.needs_aggregation = 0
        else:
            # Send Job to aggregation queue
            from cs.metrics import aggregation_queue
            aggregation_queue.queue.put(qc_object_id=self.cdb_object_id)
            self.needs_aggregation = 1

    def aggregate_up(self, ctx=None, old_value=None, force=False):
        """
        Computes the aggregate values of all the quality characteristics that precede the
        current one in the aggregation structure without resetting the memoization-cache.
        """
        if ctx and "old_value" in ctx.ue_args.get_attribute_names():
            old_value = float(ctx.ue_args.old_value) if ctx.ue_args.old_value != NULL and ctx.ue_args.old_value != '' else NULL

        if self.Parents:
            # If the user selected in the configuration to take aggregated value automatically as
            # actual value, the aggregated value will be saved as actual value for the superior object
            # and a history object will be created.
            asso_val = self.Association.take_aggr_val if self.Association else 0

            args = {"force": force}
            if asso_val:
                time = cdbtime.localtime()
                args.update({"asso_val": asso_val,
                             "cdb_cdate": time,
                             "cdb_cpersno": auth.persno})

            old_values = {}
            for kz in self.Parents:
                old_values[kz.cdb_object_id] = kz.act_value
                kz.aggregate(**args)

            propagate = asso_val and (old_value is None or old_value != self.act_value)
            for kz in self.Parents:
                if kz.act_value == NULL or propagate:
                    kz.aggregate_up(old_value=old_values[kz.cdb_object_id])

    @memoize
    def compute_aggregate_value(self):
        """
        Compute and returns the aggregate value of the current quality characteristic.
        Uses memoization, if unsure reset the cache before and after use as follows:

        self.compute_aggregate_value.reset()
        """

        self.objekt = ByID(self.cdbf_object_id)

        child_assignment = None
        for _child_assignment in self.ChildConfigurations:
            if _child_assignment.ORule:
                if _child_assignment.ORule.match(self.objekt):
                    child_assignment = _child_assignment
                    break
            else:
                child_assignment = _child_assignment
                break

        if child_assignment:
            relship = Relship.ByKeys(child_assignment.relship_name)
            v_class = Entity.ByKeys(relship.relship_cldef)
            aggr_rule = AggregationRule.ByKeys(child_assignment.aggr_rule_id)

            # Collect all children objects in a list
            if relship.rs_profile == 'cdb_association_1_1':
                ChildrenList = [getattr(self.objekt, relship.rolename)]
            else:
                ChildrenList = getattr(self.objekt, relship.rolename)

            values = []

            # Run through the list of children objects and get the values needed for
            # aggregation value calculation
            for child in ChildrenList:
                value = None
                kz = ObjectQualityCharacteristic.ByKeys(cdbf_object_id=child.cdb_object_id, cdbqc_def_object_id=self.cdbqc_def_object_id)

                if kz and kz.Association:
                    if kz.act_value != NULL:
                        value = kz.act_value
                    elif kz.aggr_value != NULL:
                        value = kz.aggr_value

                    if aggr_rule.name_de == 'Summe mit Koeffizient' and value:
                        if v_class.fqpyname:
                            VClass = tools.getObjectByName(v_class.fqpyname)
                            VObj = VClass.ByKeys(**(self._createKeymap(self.objekt, child, relship.referer_kmap, relship.reference_kmap)))
                            value *= getattr(VObj, child_assignment.coeff_name)

                    if value:
                        values.append(value)

            if aggr_rule.name_de == 'Custom':
                callable_obj = tools.getObjectByName(child_assignment.custom_rule_pyname)
                self.Reload()
                aggr_ctx = AggregationContext(self)
                result = callable_obj(aggr_ctx)

                return result
            else:
                return aggr_rule.aggregate(values)

    def aggregate(self, ctx=None, force=False, **args):
        """ Computes and saves the aggregate value of the current quality characteristics.
            Supports memoization and doesn't reset the cache.
        """
        aggr_value = self.compute_aggregate_value()
        self.aggr_value = aggr_value if aggr_value is not None else NULL

        old_value = self.act_value

        if self.Association and self.Association.take_aggr_val:
            if self.aggr_value != NULL:
                time = cdbtime.localtime()
                self.Update(**{"act_value": self.aggr_value,
                               "target_fulfillment": self.get_target_fulfillment(aggr_value,
                                                                                 self.target_value),
                               "cdb_mdate": time,
                               "cdb_mpersno": auth.persno})
                self.aggregate_up()

            if self.act_value is not None and self.act_value != NULL:
                args["cdbqc_object_id"] = self.cdb_object_id
                args["value"] = self.act_value
                args["guetegrad"] = 'aggregiert'

                self.createHistoryObject(ctx, **args)

        if ctx:
            ctx.keep("old_value", old_value)

    def getChanges(self, ctx):
        '''
        It is checked, if the aggregated value should be taken as actual value.

        - If so the aggregated value will be set as actual value, quality grade will be set to
        'aggregiert', relevant fields will be set to read only.
        - Otherwise the fields for actual value and quality grade stay editable.
        Combobox for quality grade will not contain the option 'aggregiert'
        '''
        if ctx.changed_item == "assume_check":
            check = ctx.dialog.assume_check
            if check == "1":
                if ctx.dialog.aggr_value:
                    actval = ctx.dialog.aggr_value
                    ctx.set("act_value", actval)
                    ctx.set("guetegrad", "aggregiert")
                    ctx.set_fields_readonly(["act_value", "guetegrad"])
                else:
                    ctx.set("act_value", "")
                    ctx.set("guetegrad", "")
            else:
                ctx.set("act_value", "")
                ctx.set("guetegrad", "")
                ctx.set_fields_writeable(["act_value", "guetegrad"])

    def keep_values(self, ctx):
        """ Keeps attributes to be used in later user-exits """
        ctx.keep("old_value", ctx.object.act_value)

    def set_flags(self, ctx=None, old_value=None):
        """ Sets a flag to activate asynchronous aggregation """
        if self.Definition.asyncron:
            needs_aggregation = 0
            if ctx and "old_value" in ctx.ue_args.get_attribute_names():
                if "%s" % ctx.ue_args["old_value"] != "%s" % self.act_value:
                    needs_aggregation = 1
            elif old_value is not None and old_value != self.act_value:
                needs_aggregation = 1

    # Interface to edit the quality characteristic (to be used instead
    # of the kernel operations)
    def set_actual_value(self, value, guetegrad=None):
        old_value = self.act_value

        args = self.MakeChangeControlAttributes()

        # Actual value
        if value == "":
            value = NULL
        args["act_value"] = value

        # Target value fulfillment
        args["target_fulfillment"] = self.get_target_fulfillment(value,
                                                                 self.target_value)

        if guetegrad is not None:
            gg_obj = QCGrade.ByKeys(name_de=guetegrad)
            if gg_obj:
                args.update({"cdbqc_qgrade_object_id": gg_obj.cdb_object_id})

        self.Update(**args)

        # History
        if guetegrad is not None:
            self.createHistoryObject(guetegrad=guetegrad)
        else:
            self.createHistoryObject()

        # Aggregation
        self.aggregate_up_structure()
        # self.set_flags(old_value=old_value)

    @classmethod
    def CreateQC(cls, **kwargs):
        create_args = None
        kwargs.update(cls.MakeChangeControlAttributes())
        if "cdbqc_def_object_id" in kwargs:
            definition = QCDefinition.ByKeys(kwargs["cdbqc_def_object_id"])
            if definition:
                # ensure defaults are set
                create_args = dict(
                    subject_id=definition.subject_id,
                    subject_type=definition.subject_type,
                    target_value=definition.default_target_value
                )
                create_args.update(kwargs)  # defaults can be overwritten by kwargs
        if create_args is None:
            create_args = kwargs
        qc = cls.Create(**create_args)
        # Uncomment if you want the quality characteristics
        # to be computed on creation.
        # if qc.Definition.computed:
        #    qc.Association.ComputationRule.compute(qc)

        # Aggregation
        qc.aggregate()
        # if qc.Definition.asyncron:
        #     qc.needs_aggregation = 1

        qc.aggregate_up_structure()

        return qc

    def DeleteQC(self):
        self.DeleteReferredObjects()
        self.Delete()

    def CopyValues(self, rhs):
        super(ObjectQualityCharacteristic, self).CopyValues(rhs)
        rhs.Update(aggr_value=self.aggr_value,
                   needs_aggregation=self.needs_aggregation)

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the ObjectQualityCharacter and corresponding object itself.
        """
        fobj = ByID(self.cdbf_object_id)
        if fobj:
            return [self, fobj]
        else:
            return [self]

    def disable_actual_value(self, ctx):
        """
        If the object regel in the class association is not satisfied,
        the actual value should not be edited anymore
        """
        if not self.Association:
            ctx.set_readonly('act_value')

    event_map = {(('modify', 'copy'), 'pre_mask'): 'disable_actual_value',
                 (('create', 'modify', 'copy'), 'pre'): 'keep_values',
                 # (('create', 'modify', 'copy'), 'post'): ('aggregate_up_structure', 'set_flags'),
                 (('create', 'modify', 'copy'), 'post'): ('aggregate_up_structure'),
                 (('create', 'copy'), 'pre'): 'aggregate',
                 (('create', 'modify', 'copy'), 'dialogitem_change'): 'getChanges',
               }


class ClassQualityCharacteristic(QualityCharacteristic):
    """ Class for class-quality characteristics """
    __classname__ = "cdbqc_class_quality_character"
    __match__ = fClassQualityCharacteristic.cdb_classname == "cdbqc_class_quality_character"

    Definition = Reference_1(fClassQCDefinition, fClassQCDefinition.cdb_object_id == fClassQualityCharacteristic.cdbqc_def_object_id)
    Groupings = Reference_N(fGroupingValue, fGroupingValue.qc_object_id == fClassQualityCharacteristic.cdb_object_id)
    Association = Reference_1(fAssociation, (fAssociation.cdbqc_def_object_id == fQualityCharacteristic.cdbqc_def_object_id) & (fAssociation.classname == fQualityCharacteristic.classname))

    @classmethod
    def compute_period_extremes(cls, today, length):
        """Computes the beginning and the end of the previous period of <length> months"""

        n = 12 / length
        previous = lambda per: (per - 2) % n + 1

        # the current period (starting from 1)
        period = ((today.month - 1) / length) + 1

        # end of the previous period
        month = previous(period) * length
        year = today.year if period != 1 else today.year - 1
        day = calendar.monthrange(year, month)[1]
        last_day = date(year, month, day)

        # first day of the previous period
        month = (month - length) % 12 + 1
        year = today.year if period != 1 else today.year - 1
        first_day = date(year, month, 1)

        return first_day, last_day

    def getWhereCondition(self, relation, root_alias):
        """
        Returns an SQL-Condition used to compute the value of computed quality characteristics.

        Evaluates the object rule and the period given in the configuration and generates
        an SQL where statement.
        """
        if not relation:
            raise ue.Exception()
        ti = util.TableInfo(relation)
        wheres = [ti.condition([group.attribute_name],
                               [group.attribute_value]) for group in self.Groupings]

        # Help functions
        fd = lambda dt: SQLdbms_date(dt.strftime("%d.%m.%Y"))
        if self.Association and self.Association.ORule:
            v_class = self.Association.Class
            VClass = tools.getObjectByName(v_class.fqpyname)

            root = self.Association.ORule._GetNode(VClass)
            tmp = str(self.Association.ORule.expr(VClass))
            # ensure root of object rule condition match to root alias
            wheres.append(tmp.replace(root.alias + ".", root_alias + "."))

        if self.Association and not self.Association.ComputationRule.getPeriod() is None:
            attr = self.Association.ComputationRule.action

            if not attr:
                raise ue.Exception("just_a_replacement", "QC: Time period without action defined")
            period = int(self.Association.ComputationRule.getPeriod())

            today = date.today()
            if period == resolve("Tag"):
                wheres.append("%s=%s" % (attr, fd(date.today() - timedelta(days=1))))
            elif period != resolve("Ohne"):
                if period == resolve("Woche"):
                    first_day = date.today() - timedelta(days=7 + date.today().weekday())
                    last_day = first_day + timedelta(days=6)
                else:
                    if period == resolve("Monat"):
                        length = 1
                    elif period == resolve("Jahr"):
                        length = 12
                    elif period == resolve("1/2 Jahr"):
                        length = 6
                    elif period == resolve("1/4 Jahr"):
                        length = 3
                    first_day, last_day = self.compute_period_extremes(today, length)

                wheres.append("({0} >= {1}) AND ({0} <= {2})".format(attr, fd(first_day), fd(last_day)))

        return " AND ".join(wheres)

    def evaluate_attribute(self, attr):
        """ Returns the attribute attr of the referred class """
        if not self.Association:
            return NULL

        v_class = self.Association.Class
        VClass = tools.getObjectByName(v_class.fqpyname)

        return getattr(VClass, attr)

    def deleteStuff(self, ctx):
        """
        Deletes the object associated to a definition, which are not automatically deleted on deletion of the definition

        This is necessary because of a conflict between the rights system and the relationships.
        Normally the objects referred by a relationship of type 'aggregate_deep' are deleted after the
        deletion of the referring object. However, if the access rights on the referred object depends
        on a condition on the referring object (Beziehungsrechte), then the system would not have
        the necessary rights for deletion of the referred objects, because the referring object does
        not exist anymore.

        A workaround consists in deleting the referred objects at the time point 'pre' instead of 'post',
        as we do in this method.
        """
        for grouping in self.Groupings:
            # Deletes Associations
            op = cdbwrapc.Operation("CDB_Delete", grouping.ToObjectHandle(), SimpleArguments())
            op.run()

    # Interface to edit the quality characteristic (to be used instead
    # of the kernel operations)
    def set_actual_value(self, value, guetegrad=None):
        args = self.MakeChangeControlAttributes()

        # Actual value
        args["act_value"] = value

        # Target value fulfillment
        args["target_fulfillment"] = self.get_target_fulfillment(value,
                                                                 self.target_value)

        self.Update(**args)

        # History
        self.createHistoryObject(guetegrad=guetegrad if guetegrad is not None
                                 else "berechnet")

    @classmethod
    def CreateQC(cls, **kwargs):
        if "cdbqc_def_object_id" in kwargs:
            definition = QCDefinition.ByKeys(kwargs["cdbqc_def_object_id"])
            if definition:
                kwargs.update(subject_id=definition.subject_id,
                              subject_type=definition.subject_type,
                              target_value=definition.default_target_value)

        qc = cls.Create(**kwargs)

        # Uncomment if you want the quality characteristics
        # to be computed on creation.
        # if qc.Definition.computed:
        #    qc.Association.ComputationRule.compute(qc)

        return qc

    def DeleteQC(self):
        self.DeleteReferredObjects()
        self.Groupings.Delete()
        self.Delete()

    def CopyValues(self, rhs):
        super(ClassQualityCharacteristic, self).CopyValues(rhs)
        for gv in self.Groupings:
            gv.Copy(qc_object_id=rhs.cdb_object_id)

    event_map = {(('delete'), 'pre'): 'deleteStuff'
               }


class History(Object):
    __maps_to__ = "cdbqc_history"
    __classname__ = "cdbqc_history"


class QCGrade(Object):
    __maps_to__ = "cdbqc_q_grade"
    __classname__ = "cdbqc_q_grade"

    Name = LocalizedField("name")


class AggregationRule(Object):
    ''' Standard aggregation rule. Custom aggregation rules are treated separately '''

    __maps_to__ = "cdbqc_aggr_rule"
    __classname__ = "cdbqc_aggr_rule"

    def aggregate(self, values):
        '''
            Computes the aggregated value, depending on the given rule and quality characteristic
            definition. Possible standard rules are e.g. Summe, Maximum...

            :param values: values that needs to be aggregated
        '''

        rulename = self.name_de

        # Depending on the rule the result will be calculated
        if rulename:
            if rulename == "Summe" or rulename == "Summe mit Koeffizient":
                return sum(values)
            elif rulename == "Maximum":
                return max(values)
            elif rulename == "Minimum":
                return min(values)
        else:
            return 0


class QCDefinition(WithSubject):
    """ Base class for definitions of quality characteristics """
    __maps_to__ = "cdbqc_definition"
    __classname__ = "cdbqc_definition"

    Unit = Reference_1(fQCUnit, fQCUnit.cdb_object_id == fQCDefinition.unit_object_id)
    QualityCharacteristics = Reference_N(fQualityCharacteristic,
                                         fQualityCharacteristic.cdbqc_def_object_id == fQCDefinition.cdb_object_id)
    Associations = Reference_N(fAssociation, fAssociation.cdbqc_def_object_id == fQCDefinition.cdb_object_id)

    Name = LocalizedField("name")

    class CREATED(State):
        status = 0

    class VALID(State):
        status = 100

        def Constraints(state, self):  # @NoSelf
            return [("check_consistency", [])]

        def pre(state, self, ctx):  # @NoSelf
            if self.cdb_classname == "cdbqc_obj_definition" and len(self.QualityCharacteristics):
                # if self.asyncron:
                #     self.QualityCharacteristics.Update(needs_aggregation=1)
                # else:
                    for qc in self.QualityCharacteristics:
                        qc.aggregate_up_structure()

    class INVALID(State):
        status = 200

    class CREATED_TO_VALID(Transition):
        transition = (0, 100)

        def post(transition, self, ctx):  # @NoSelf
            for asso in self.Associations:
                asso.createQCs()

    def deleteStuff(self, ctx):
        """
        Deletes the object associated to a definition, which are not automatically deleted on deletion of the definition

        This is necessary because of a conflict between the rights system and the relationships.
        Normally the objects referred by a relationship of type 'aggregate_deep' are deleted after the
        deletion of the referring object. However, if the access rights on the referred object depends
        on a condition on the referring object (Beziehungsrechte), then the system would not have
        the necessary rights for deletion of the referred objects, because the referring object does
        not exist anymore.

        A workaround consists in deleting the referred objects at the time point 'pre' instead of 'post',
        as we do in this method.
        """
        for asso in self.Associations:
            # Deletes Associations
            op = cdbwrapc.Operation("CDB_Delete", asso.ToObjectHandle(), SimpleArguments())
            op.run()

    def updateSubjects(self, ctx):
        if ctx.object.subject_id != self.subject_id or \
           ctx.object.subject_type != self.subject_type:
            self.QualityCharacteristics.Update(subject_type=self.subject_type,
                                               subject_id=self.subject_id)

    def check_consistency(self):
        """
        This method checks the consistency of the configuration,
        prior to status change

        :return: None if the configuration is consistent,
                 an error message otherwise
        """
        return None

    def GetExcludedFieldsOnExport(self):
        return ["cdb_mdate"]

    event_map = {(('delete'), 'pre'): 'deleteStuff',
                 (('modify'), 'pre'): 'updateSubjects'}


class ObjectQCDefinition(QCDefinition):
    "Models the definition of object-quality characteristics"
    __classname__ = "cdbqc_obj_definition"
    __match__ = fObjectQCDefinition.cdb_classname == "cdbqc_obj_definition"

    QualityCharacteristics = Reference_N(fObjectQualityCharacteristic, fQualityCharacteristic.cdbqc_def_object_id == fQCDefinition.cdb_object_id)

    def check_consistency(self):
        """
        Check if the configuration is consistent. I.e:

        - Computed and Asynchronous aggregation should not be chosen
          together

        :return: True if the configuration is consistent, False otherwise
        """
        if self.computed and self.asyncron:
            return util.get_label("cdbqc_inconsistent_configuration")
        return None

    def disable_checkbox_computed(self, ctx):
        if self.Associations:
            ctx.set_readonly('computed')

    event_map = {(('copy', 'modify'), 'pre_mask'): 'disable_checkbox_computed'}


class ClassQCDefinition(QCDefinition):
    "Models the definition of class-quality characteristics"
    __classname__ = "cdbqc_class_definition"
    __match__ = fClassQCDefinition.cdb_classname == "cdbqc_class_definition"

    QualityCharacteristics = Reference_N(fClassQualityCharacteristic, fQualityCharacteristic.cdbqc_def_object_id == fQCDefinition.cdb_object_id)


class QCUnit(Object):
    __maps_to__ = "cdbqc_unit"
    ''' corresponding database relation '''
    __classname__ = "cdbqc_unit"

    Name = LocalizedField("name")
    UnitType = Reference_1(fQCUnitType, fQCUnit.cdbqc_utype_object_id)


class QCUnitType(Object):
    __maps_to__ = "cdbqc_unit_type"
    ''' corresponding database relation '''
    __classname__ = "cdbqc_unit_type"

    Name = LocalizedField("name")


class GroupingAttribute(Object):
    __classname__ = "cdbqc_grouping_attribute"
    __maps_to__ = "cdbqc_grouping_attribute"

    Definition = Reference_1(fQCDefinition, fQCDefinition.cdb_object_id == fGroupingAttribute.cdbqc_def_object_id)


class GroupingValue(Object):
    __classname__ = "cdbqc_grouping_value"
    __maps_to__ = "cdbqc_grouping_value"

    QualityCharacteristic = Reference_1(fClassQualityCharacteristic, fClassQualityCharacteristic.cdb_object_id == fGroupingValue.qc_object_id)
    Definition = ReferenceMethods_1(fQCDefinition, lambda x: QCDefinition.ByKeys(x.QualityCharacteristic.cdbqc_def_object_id))

    def getValue(self):
        obj = ByID(self.attribute_value)
        if obj:
            return obj.GetDescription()
        else:
            return self.attribute_value


class PeriodCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        return [I18nCatalogEntry("", "")] + \
                [I18nCatalogEntry("%d" % uc.position, uc.Period[''])
                 for uc in ComputationRules.UpdateClock.Query(
                     ComputationRules.UpdateClock.name_de != "manuell",
                     order_by="position")]


class ActionCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        return [I18nCatalogEntry("", ""), I18nCatalogEntry("cdb_cdate", util.get_label("cdbqc_cdate")), I18nCatalogEntry("cdb_mdate", util.get_label("cdbqc_mdate"))]


class AggregationContext:
    """ Provides context for the custom aggregation rules

        The following structure is constructed:

        - self.qc            The quality characteristic, whose aggregate value is to be computed
        - self.object        The object referred by self.qc
        - self.children      List of the quality characteristics that directly succeed self.qc
                             in the aggregation tree
        - self.successors    List of the objects that directly succeed self.object
                             in the aggregation tree
        - self.children_map  Dictionary of the quality characteristics that directly succeed self.qc
                             in the aggregation tree indexed by the objects in self.successors
        - self.links         List of the objects of the connection class of the relationship
                             going out from self.object and going in some object of self.successors
    """
    def _getLinks(self):
        result = {}

        for child in self.qc.ChildConfigurations:
            relship = Relship.ByKeys(child.relship_name)
            if relship.RefererClass.getFqpyname():
                VClass = tools.getObjectByName(relship.LinkClass.getFqpyname())

                args = {}
                for pair in relship.referer_kmap.split(';'):
                    lpair = pair.strip().split('=')
                    args[lpair[1].strip()] = getattr(self.object, lpair[0].strip())
                result[relship.rolename] = VClass.KeywordQuery(**args)
            else:
                raise ue.Exception("just_a_replacement", "Entity {0} has no python name".format(relship.referer))
        return result

    def __init__(self, qc):
        self.object = ByID(qc.cdbf_object_id)
        self.qc = qc

        self.links = self._getLinks()

        self.successors = qc.Successors
        self.children = qc.Children
        self.children_map = {succ: ObjectQualityCharacteristic.ByKeys(cdbqc_def_object_id=qc.cdbqc_def_object_id, cdbf_object_id=succ.cdb_object_id)
                              for succ in self.successors}


# Connects Vorganger/Nachfolger
def aggregate_relation(child, obj, ctx):
    """ aggregate the quality characteristics referred by the link-object obj

        :param child: Configuration of successors for the aggregation of a quality characteristic
        :type child: cs.metrics.qualitycharacteristics.ChildConfiguration
        :param obj: Object of the link class for the relation child.Relship which links to #
                    the quality characteristics which should be aggregated
        :type obj: An object relative to the DD-Class child.classname
        :param ctx: CDB operation context
    """

    # First we obtain the referred object
    relship = Relship.ByKeys(child.relship_name)

    referer_args = {}
    for pair in relship.referer_kmap.split(';'):
        lpair = pair.strip().split('=')
        referer_args[lpair[0].strip()] = getattr(obj, lpair[1].strip())

    if relship.RefererClass.getFqpyname():
        RefererClass = relship.RefererClass.getFqpyname()
        referer = tools.getObjectByName(RefererClass).ByKeys(**referer_args)
    else:
        raise ue.Exception("just_a_replacement", "Entity {0} has no python name".format(relship.referer))

    # Then we aggregate the quality characteristic
    if referer:
        qc = ObjectQualityCharacteristic.ByKeys(cdbqc_def_object_id=child.cdbqc_def_object_id, cdbf_object_id=referer.cdb_object_id)
        if qc and qc.Definition and qc.Definition.status == qc.Definition.VALID.status:
            old_value = qc.act_value
            qc.aggregate()
            if qc.act_value == NULL or old_value != qc.act_value:
                qc.aggregate_up_structure()


@connect(rte.APPLICATIONS_LOADED_HOOK)
def do_whatever():
    children = ChildConfiguration.Query()
    for child in children:
        if child.Definition and not child.Definition.asyncron:
            relship = Relship.ByKeys(child.relship_name)
            VClass = None
            if relship:
                if relship.RefererClass.getFqpyname():
                    try:
                        VClass = tools.getObjectByName(relship.LinkClass.getFqpyname())
                    except:
                        pass
                else:
                    raise ue.Exception("just_a_replacement", "Entity {0} has no python name".format(relship.referer))
            else:
                misc.cdblogv(misc.kLogErr, 0, "cs.metrics: invalid relship '%s' in child configuration" % child.relship_name)

            if VClass:
                connect(VClass, "create", "post")(partial(aggregate_relation, child))
                connect(VClass, "delete", "post")(partial(aggregate_relation, child))
                connect(VClass, "modify", "post")(partial(aggregate_relation, child))
