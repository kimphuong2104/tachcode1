#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
import six

"""
The Product Costing Parameter classes.
"""
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import datetime
from cdb import ue
from cdb import sqlapi
from cdb import misc
from cdb import cdbuuid
from cdb.platform import gui
from cdb.platform.mom import entities
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Forward
from cdb.objects import ByID
from cdb.objects import operations
from cs.audittrail import WithAuditTrail
from cs.costing.costingreport import ReportConfiguration

rac__all__ = ["ParameterDefinition", "ParameterValue", "ResultValue"]

fItem = Forward("cs.vp.items.Item")
fFile = Forward("cdb.objects.cdb_file.CDB_File")
fCalculation = Forward("cs.costing.calculations.Calculation")
fCalculationStatiProt = Forward("cs.costing.calculations.CalculationStatiProt")
fDelivery = Forward("cs.costing.components.Delivery")
fComponentFolder = Forward("cs.costing.components.ComponentFolder")
fComponentFolder2Component = Forward("cs.costing.components.ComponentFolder2Component")
fProduct = Forward("cs.costing.components.Product")
fComponent = Forward("cs.costing.components.Component")
fComponent2Product = Forward("cs.costing.components.Component2Product")
fCalculationSchema = Forward("cs.costing.schemes.CalculationSchema")
fParameterDefinition = Forward("cs.costing.parameters.ParameterDefinition")
fParameterValue = Forward("cs.costing.parameters.ParameterValue")
fResultValue = Forward("cs.costing.parameters.ResultValue")
fUnitConversion = Forward("cs.costing.schemes.UnitConversion")
fPartCost = Forward("cs.costing.components.PartCost")
fProduct2Delivery = Forward("cs.costing.components.Product2Delivery")
fMachine = Forward("cs.costing.machinedb.Machine")
fVolumeCurve = Forward("cs.costing.volume_curve.VolumeCurve")
fClonedComponent = Forward("cs.costing.components.Component2Component")

CONTEXT_ONLY_KEY = "__context_only__"
parameter_cache = {}


def get_default_parameter_values(values={}, context_only=[]):
    mapping = dict(values={
        "PY": 0,
        "QUANT": 1
    })
    if values:
        mapping["values"].update(values)
    mapping[CONTEXT_ONLY_KEY] = list(set(context_only).union(["PY", "QUANT"]))
    return mapping


def log(msg):
    misc.cdblogv(misc.kLogMsg, 7, msg)


def init_parameter_cache(force=False):
    global parameter_cache
    if parameter_cache and not force:
        return
    if force:
        parameter_cache = {}
    rs = sqlapi.RecordSet2("cdbpco_para_def")
    para_obj_ids = {}
    for r in rs:
        if r.schema_object_id not in parameter_cache:
            parameter_cache[r.schema_object_id] = {}
        cls_name = r.classname
        if not cls_name:
            cls_name = ""
        if cls_name not in parameter_cache[r.schema_object_id]:
            parameter_cache[r.schema_object_id][cls_name] = {"parameters": {},
                                                             "formulas": {}}
        if r.formula != "":
            parameter_cache[r.schema_object_id][cls_name]["formulas"][r.code] = r
        parameter_cache[r.schema_object_id][cls_name]["parameters"][r.code] = r
        para_obj_ids[r.cdb_object_id] = (r.schema_object_id, cls_name)
    for s in list(parameter_cache):
        for cls_name in list(parameter_cache[s]):
            if not cls_name:
                continue
            for code, p_def in six.iteritems(parameter_cache[s][""]["parameters"]):
                if code not in parameter_cache[s][cls_name]["parameters"]:
                    parameter_cache[s][cls_name]["parameters"][code] = p_def
            for code, r_def in six.iteritems(parameter_cache[s][""]["formulas"]):
                if code not in parameter_cache[s][cls_name]["formulas"]:
                    parameter_cache[s][cls_name]["formulas"][code] = r_def

    for s in list(parameter_cache):
        for cls_name in list(parameter_cache[s]):
            formulas = list(six.itervalues(parameter_cache[s][cls_name]["formulas"]))
            formulas = sorted(formulas, key=lambda formula: formula.order_no)
            parameter_cache[s][cls_name]["formulas"] = formulas


class ParameterDefinition(Object, WithAuditTrail):
    """
    Defines a Parameter.
    """
    __maps_to__ = "cdbpco_para_def"
    __classname__ = "cdbpco_para_def"

    event_map = {
        ('delete', 'pre'): 'check_delete',
        (('create', 'copy'), 'pre_mask'): 'set_position',
        ('cdbpco_transfer_to_report', 'now'): 'transfer_to_report'
        }

    DefaultValues = Reference_N(
        fParameterValue,
        fParameterValue.pdef_object_id == fParameterDefinition.cdb_object_id,
        fParameterValue.context_object_id == "")

    ResultValues = Reference_N(
        fResultValue,
        fResultValue.rdef_object_id == fParameterDefinition.cdb_object_id)

    CalculationSchema = Reference_1(fCalculationSchema,
                                    fCalculation.schema_object_id)

    def set_position(self, ctx):
        # set the folder position to next possible value
        pos = 0
        maxposrec = sqlapi.RecordSet2(sql="select max(order_no) maxpos " +
                                         "from %s " % self.GetTableName() +
                                         "where schema_object_id='%s'" %
                                            self.schema_object_id)
        try:
            pos = int(maxposrec[0].maxpos) + 1
        except Exception:
            pass
        self.order_no = pos

    def transfer_to_report(self, ctx):
        if not ReportConfiguration.KeywordQuery(schema_object_id=self.schema_object_id,
                                                param_object_id=self.cdb_object_id):
            params = {
                "schema_object_id": self.schema_object_id,
                "param_object_id": self.cdb_object_id,
                "row_name_de": self.ml_name_de,
                "row_name_en": self.ml_name_en,
                "row_type": "Parameter",
                "position_costing_report": 10
            }
            config_rows = ReportConfiguration.KeywordQuery(schema_object_id=self.schema_object_id)
            if config_rows:
                params["position_costing_report"] = max(config_rows.position_costing_report) + 10
            operations.operation("CDB_Create", ReportConfiguration, **params)

    def copy_to(self, newschema):
        """
        Copy the current object to a new Schema object.
        """
        newdata = {"schema_object_id": newschema.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        newobj = self.Copy(**newdata)
        # also copy the default parameter values
        for pval in self.DefaultValues:
            pval.copy_to(newobj)

    def check_delete(self, ctx):
        """
        Check the conditions before delete the current object.
        """
        if len(fParameterValue.Query(
            "pdef_object_id='%s' and context_object_id<>''" % self.cdb_object_id)):
            # If current object is referenced from other objects,
            # it should not be delete.
            raise ue.Exception("cdbpco_err_msg_04")

    def on_cdbpco_set_pos_now(self, ctx):
        """
        Operation event handler to reset the position of a object - move it up
        or down. See `ComponentFolder.on_cdbpco_set_pos_now`
        """
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdbpco_para_br",
                                schema_object_id=self.schema_object_id)
        else:
            cdb_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            targetobj = ParameterDefinition.ByKeys(cdb_object_id)
            if targetobj:
                mypos = self.order_no
                targetpos = targetobj.order_no
                if mypos != targetpos + 1:
                    posstep = 1
                    newpos = targetpos + 1
                    cond = "order_no>%i and order_no<%i" % (targetpos, mypos)
                    if mypos < targetpos:
                        cond = "order_no<=%i and order_no>%i" % (targetpos,
                                                                 mypos)
                        posstep = -1
                        newpos = targetpos
                    moveobjs = ParameterDefinition.Query(
                                    "schema_object_id='%s' and " %
                                    self.schema_object_id + cond)
                    for moveobj in moveobjs:
                        moveobj.order_no = moveobj.order_no + posstep
                    self.order_no = newpos

    def referencedAuditTrailObjects(self):
        return [self, self.CalculationSchema]


class ParameterValue(Object):
    """
    A Parameter value. It is dependent on context object, plant and valid year.
    """
    __maps_to__ = "cdbpco_para_val"
    __classname__ = "cdbpco_para_val"

    ParameterDefinition = Reference_1(fParameterDefinition,
                                      fParameterValue.pdef_object_id)

    event_map = {
            ('create', 'pre_mask'): 'init_para'
            }

    def copy_to(self, newpdef):
        """
        Copy the current object to a new ParameterDefinition.
        """
        newdata = {"pdef_object_id": newpdef.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        self.Copy(**newdata)

    def init_para(self, ctx):
        """
        Initiate Parameter values.
        """
        if self.context_object_id and not self.costplant_object_id:
            ctxobj = ByID(self.context_object_id)
            calcobj = ctxobj
            if not hasattr(calcobj, "is_calculation"):
                calcobj = ctxobj.Calculation
            self.costplant_object_id = calcobj.costplant_object_id
            ctx.set_fields_readonly(["costplant_object_id"])
        if not self.valid_year:
            self.valid_year = "%d" % datetime.date.today().year

    @classmethod
    def copy_parameters_to(cls, template_obj, target_obj):
        for pvalue in template_obj.ParameterValues:
            pvalue.Copy(cdb_object_id=cdbuuid.create_uuid(),
                        context_object_id=target_obj.cdb_object_id)

    @classmethod
    def removeParameterConstraint(cls):
        # Such information saved on context object
        # is essential. Keep parameter value neutralized
        # when assigning to a context object.
        return dict(costplant_object_id="",
                    valid_year="",
                    material_object_id="",
                    technology_id="")

    def copy_to_context_object(self, context_object_id):
        try:
            return self.Copy(cdb_object_id=cdbuuid.create_uuid(),
                             context_object_id=context_object_id,
                             **self.removeParameterConstraint())
        except:
            pass

    @classmethod
    def createForContextObject(cls, pdef, context_object_id, value):
        try:
            return cls.Create(
                        cdb_object_id=cdbuuid.create_uuid(),
                        context_object_id=context_object_id,
                        value=value,
                        pdef_object_id=pdef.cdb_object_id,
                        **cls.removeParameterConstraint())
        except:
            pass


class ResultValue(Object, WithAuditTrail):
    """
    Result value object.
    """
    __maps_to__ = "cdbpco_result_val"
    __classname__ = "cdbpco_result_val"

    ResultDefinition = Reference_1(fParameterDefinition,
                                   fResultValue.rdef_object_id)

    event_map = {
        (('modify', 'create'), 'post'): ('modify_default')
    }

    def referencedAuditTrailObjects(self):
        return [ByID(self.context_object_id)]

    def modify_default(self, ctx):
        rdef = self.ResultDefinition
        if rdef.formula != "" and rdef.has_defaults > 0:
            ParameterValue.KeywordQuery(
                context_object_id=self.context_object_id,
                pdef_object_id=self.rdef_object_id,
            ).Update(value=self.value,
                     overwrite=0)

    @classmethod
    def copyResultTo(cls, template_obj, target_obj):
        for rvalue in template_obj.ResultValues:
            rvalue.Copy(cdb_object_id=cdbuuid.create_uuid(),
                        context_object_id=target_obj.cdb_object_id)


class AggregationCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        self.browser_data = AggregationCatalogData(self)
        self.setResultData(self.browser_data)

    def handleResultDataSelection(self, selected_rows):
        selected_classnames = []
        if self.getInvokingDlgValue("not_aggr_for"):
            selected_classnames = self.getInvokingDlgValue("not_aggr_for").split(",")
        for s in selected_rows:
            selected_classnames.append(self.browser_data.data[s]["classname"])
        self.setValue("not_aggr_for", ",".join(selected_classnames))


class AggregationCatalogData(gui.CDBCatalogContent):
    def __init__(self, catalog):
        tabdef = catalog.getTabularDataDefName()
        gui.CDBCatalogContent.__init__(self, tabdef)
        self.data = []
        self._initData()

    def _initData(self, refresh=False):
        if not self.data or refresh:
            result = [{"classname": "*"},
                      {"classname": "cdbpco_delivery"},
                      {"classname": "cdbpco_calculation"}]
            cdef = entities.CDBClassDef("cdbpco_component")
            subclasses = cdef.getSubClassNames(True)
            for sc in entities.Entity.KeywordQuery(classname=subclasses):
                if sc.is_abstract:
                    continue
                else:
                    result.append({"classname": sc.classname})
            self.data = result

    def onSearchChanged(self):
        self._initData(True)

    def refresh(self):
        self._initData(True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()
        for col in tdef.getColumns():
            attr = col.getAttribute()
            try:
                value = self.data[row][attr]
                if not value:
                    value = u""
            except Exception:
                value = u""
            result.append(value)
        return result
