#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Imported libraries and packages
from cdb.lru_cache import lru_cache
from cdb.objects import Reference_Methods
from cdb.objects import Forward
from cdb.objects import ByID

from cdb.platform.mom import entities

import datetime
import warnings

from .qualitycharacteristics import QCDefinition, ObjectQualityCharacteristic


def _getDate(date_str):
    return datetime.datetime.strptime(date_str, "%d.%m.%Y")


# References to cdb-classes
fQualityCharacteristic = Forward("cs.metrics.qualitycharacteristics.QualityCharacteristic")
fClassQualityCharacteristic = Forward("cs.metrics.qualitycharacteristics.ClassQualityCharacteristic")
fObjectQualityCharacteristic = Forward("cs.metrics.qualitycharacteristics.ObjectQualityCharacteristic")
fOKZClassAssociation = Forward("cs.metrics.qualitycharacteristics.OKZClassAssociation")
fKKZClassAssociation = Forward("cs.metrics.qualitycharacteristics.KKZClassAssociation")
fGroupingValue = Forward("cs.metrics.qualitycharacteristics.GroupingValue")


@lru_cache(maxsize=100, typed=True, clear_after_ue=False)
def _get_OKZAssociations(*bases):
    cls_condition = str(fOKZClassAssociation.classname.one_of(*bases))

    stmt = (
        "SELECT * FROM %s WHERE status={status} AND {cls_condition}"
        .format(
            status=QCDefinition.VALID.status,
            cls_condition=cls_condition
        )
    )

    # We need to use SQL here, because we need to query over
    # a joined attribute (status)
    relation = entities.CDBClassDef("cdbqc_obj_def2class").getRelation()
    OKZAssociations = fOKZClassAssociation.SQL(stmt % relation)
    return OKZAssociations


@lru_cache(maxsize=100, typed=True, clear_after_ue=False)
def _get_KKZAssociations(*bases):
    cls_condition = str(fOKZClassAssociation.classname.one_of(*bases))

    stmt = (
        "SELECT * FROM %s WHERE status={status} AND {cls_condition}"
        .format(
            status=QCDefinition.VALID.status,
            cls_condition=cls_condition
        )
    )

    # We need to use SQL here, because we need to query over
    # a joined attribute (status)
    relation = entities.CDBClassDef("cdbqc_class_def2class").getRelation()
    KKZAssociations = fKKZClassAssociation.SQL(stmt % relation)
    return KKZAssociations


class WithQualityCharacteristic(object):
    """ Decorator base-class for classes which possess a quality characteristic """

    def _ObjectQualityCharacteristics(self):
        return ObjectQualityCharacteristic.KeywordQuery(cdbf_object_id=self.cdb_object_id)
    ObjectQualityCharacteristics = Reference_Methods(fObjectQualityCharacteristic, _ObjectQualityCharacteristics)

    def _ClassQualityCharacteristics(self, asso=None):
        bases = list(self.GetClassDef().getBaseClassNames())
        bases.append(self.GetClassname())

        condition = fClassQualityCharacteristic.classname.one_of(*bases)

        if asso is None:
            cqcs = fClassQualityCharacteristic.Query(condition)
            try:
                result = [cqc for cqc in cqcs if
                          all([gr.attribute_value == getattr(self, gr.attribute_name) for gr in cqc.Groupings])]
            except KeyError:
                # read access to virtual attributes leads to KeyError, but they can be accessed on persistent objects
                pobj = self.getPersistentObject()
                result = [cqc for cqc in cqcs if
                          all([gr.attribute_value == getattr(pobj, gr.attribute_name) for gr in cqc.Groupings])]
        elif hasattr(asso, 'GroupingAttributes'):
            try:
                own_grouping_values = {
                    group_attr.attribute_name: getattr(
                        self, group_attr.attribute_name
                    ) for group_attr in asso.GroupingAttributes
                }
            except KeyError:
                # read access to virtual attributes leads to KeyError, but they can be accessed on persistent objects
                pobj = self.getPersistentObject()
                own_grouping_values = {
                    group_attr.attribute_name: getattr(
                        pobj, group_attr.attribute_name
                    ) for group_attr in asso.GroupingAttributes
                }
            cqcs_candidate_ids = None
            for group_attr_name, group_attr_val in own_grouping_values.items():
                args = {
                    "attribute_name": group_attr_name,
                    "attribute_value": group_attr_val
                }
                if cqcs_candidate_ids is None:
                    cqcs_candidate_ids = set(fGroupingValue.KeywordQuery(**args).qc_object_id)
                else:
                    cqcs_candidate_ids = cqcs_candidate_ids.intersection(
                        set(fGroupingValue.KeywordQuery(**args).qc_object_id)
                    )
                if not cqcs_candidate_ids:
                    # a intersection with an empty set will always be empty - so skip any further
                    # grouping attributes
                    break
            if not own_grouping_values:
                candidate_ids = set(fClassQualityCharacteristic.KeywordQuery(
                    classname=bases
                ).cdb_object_id)
                # when they have a grouping value but we do not have they are not the right ones
                blacklisted_candidates = set(fGroupingValue.KeywordQuery(
                    qc_object_id=candidate_ids
                ).qc_object_id)
                candidate_ids = candidate_ids.difference(blacklisted_candidates)
                return fClassQualityCharacteristic.KeywordQuery(
                    classname=bases,
                    cdb_object_id=candidate_ids
                )
            elif cqcs_candidate_ids:
                return fClassQualityCharacteristic.KeywordQuery(
                    classname=bases,
                    cdb_object_id=cqcs_candidate_ids
                )
            else:
                result = []
        else:
            raise ValueError('Invalid association value. Only KKZClassAssociation can be used')
        return result

    ClassQualityCharacteristics = Reference_Methods(fClassQualityCharacteristic, _ClassQualityCharacteristics)

    def createQualityCharacteristic(self, ctx):
        """ Creates a quality characteristic, as soon as an object of the class is created """
        from cdbwrapc import CDBClassDef
        bases = list(CDBClassDef(self.GetClassname()).getBaseClassNames())
        bases.append(self.GetClassname())
        OKZAssociations = _get_OKZAssociations(*bases)
        for asso in OKZAssociations:
            if not asso.ORule or asso.ORule.match(self):
                args = {
                    "cdbqc_def_object_id": asso.cdbqc_def_object_id,
                    "cdbf_object_id": self.cdb_object_id,
                    "classname": asso.classname
                }
                kz = ObjectQualityCharacteristic.ByKeys(**args)
                if not kz:
                    try:
                        self.addQCArguments(args, ctx)
                    except TypeError:
                        warnings.warn(
                            "WithQualityCharacteristic: def addQCArguments(self, args) is deprecated "
                            "and will be removed in upcoming releases. "
                            "Use def addQCArguments(self, args, ctx=None) instead.",
                            DeprecationWarning, stacklevel=2
                        )
                        self.addQCArguments(args)
                    kz = ObjectQualityCharacteristic.CreateQC(**args)

        KKZAssociations = _get_KKZAssociations(*bases)
        # Create Class Quality Characteristics, if necessary
        for asso in KKZAssociations:
            if not asso.ORule or asso.ORule.match(self):
                cqcs = len(self._ClassQualityCharacteristics(asso=asso))
                if not cqcs:
                    cqc = fClassQualityCharacteristic.CreateQC(
                        cdbqc_def_object_id=asso.cdbqc_def_object_id,
                        classname=asso.classname
                    )

                    for grouping in asso.GroupingAttributes:
                        fGroupingValue.Create(qc_object_id=cqc.cdb_object_id,
                                              attribute_name=grouping.attribute_name,
                                              attribute_value=getattr(self, grouping.attribute_name))

    def addQCArguments(self, args, ctx=None):
        """
        Projekte und Aufgaben werden speziell behandelt, um das Eintragen
        von Projektrollen als Verantwortlicher zu ermöglichen.
        """
        pass

    def deleteQCs(self, ctx):
        """Delete the object quality characteristics"""
        for qc in self.ObjectQualityCharacteristics:
            qc.DeleteQC()

    def copy_values(self, ctx):
        if ctx.action == "cdbvp_index" and "new_index_id" in ctx.ue_args.get_attribute_names():
            qcs = self.ObjectQualityCharacteristics
            new_id = ctx.ue_args.new_index_id
        elif ctx.action == "index":
            new_id = self.cdb_object_id
            template = ByID(ctx.cdbtemplate.cdb_object_id)
            qcs = template.ObjectQualityCharacteristics
        else:
            qcs = []

        from cs.metrics import qualitycharacteristics
        for qc in qcs:
            new_qc = qualitycharacteristics.ObjectQualityCharacteristic.\
                ByKeys(cdbqc_def_object_id=qc.cdbqc_def_object_id,
                       cdbf_object_id=new_id)
            if new_qc:
                qc.CopyValues(new_qc)

    event_map = {
                    (('create', 'copy', 'modify', 'state_change', 'index'), 'post'): 'createQualityCharacteristic',
                    (('cdbvp_index'), 'post'): 'copy_values',
                    ('index', 'final'): 'copy_values',
                    ('delete', 'pre'): 'deleteQCs'
               }


# Custom computation rule, used for automatic tests
def test_computation_rule(qc):
    return 42
