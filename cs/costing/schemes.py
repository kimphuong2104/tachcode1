#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

"""
The Product Costing Schema classes.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import datetime
from cdb import ue
from cdb import sqlapi
from cdb import cdbuuid
from cdb import sig
from cdb.objects import Object
from cdb.objects import Reference_N
from cdb.objects import ReferenceMapping_N
from cdb.objects import Forward
from cdb.objects import operations
from cdb.objects import State
from cdb.platform import olc
from cs.currency import Currency
from cs.currency import CurrConversion
from cs.audittrail import WithAuditTrail
from cs.costing.parameters import get_default_parameter_values
from cs.costing.parameters import ResultValue
from cs.costing.parameters import ParameterValue

rac__all__ = ["WithCalculationSchema", "CalculationSchema", "UnitConversion"]

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
fCurrency = Forward("cs.currency.Currency")

CONTEXT_ONLY_KEY = "__context_only__"
# Signal used to inject calculation parameters from business objects
PARAMETER_SIGNAL = sig.signal()
PRE_CALC_SIGNAL = sig.signal()
POST_CALC_SIGNAL = sig.signal()


class WithCalculationSchema:
    """
    Base implementation of result calculation for objects with a calc. schema.
    :note: The schema is only assigned to the Calculation object and
           also applied to all sub objects.
    """

    def get_calculation_schema(self, ctx=None):
        """
        Get the calculation schema from the Calculation object.
        """
        if hasattr(self, "is_calculation"):
            return self.CalculationSchema
        else:
            return self.Calculation.CalculationSchema

    @classmethod
    def get_parameter_values(cls,
                            record=None,
                            classname=None,
                            calculation=None,
                            parent_paras=None,
                            ctx=None,
                            exch_factor=None,
                            is_calculation=False):
        """
        Get the parameter values. It updates the parameter list from the parent
        object or the Calculation object with own parameters, and marks the
        context only parameters.
        :Parameters:
            - `parent_paras` : The parameters from parent object
            - `ctx` : The context adapter
            - `exch_factor` : The currency exchange factors
        :returns: A dictionary contains a dictionary of parameter
                  values with (parameter name : value) items under `values` key.
                  It contains also a list of names of context only paramaters which
                  can be looked up under constant key name `CONTEXT_ONLY_KEY`.
        """
        if exch_factor is None:
            exch_factor = {}
        if parent_paras is None:
            parent_paras = get_default_parameter_values()
        if classname is None:
            classname = cls.__classname__
        if is_calculation:
            return cls._get_own_parameter_values(record=record,
                                                 classname=classname,
                                                 calculation=calculation,
                                                 ctx=ctx,
                                                 exch_factor=exch_factor)
        else:
            self_paras = cls._get_own_parameter_values(record=record,
                                                       classname=classname,
                                                       calculation=calculation,
                                                       ctx=ctx,
                                                       exch_factor=exch_factor)
            result = get_default_parameter_values(
                parent_paras["values"], self_paras[CONTEXT_ONLY_KEY])
            # override parent parameters with own ones
            result["values"].update(self_paras["values"])
            return result

    @classmethod
    def _get_own_parameter_values(cls, record=None, classname=None, calculation=None,
                                  ctx=None, exch_factor=None):
        """
        Default implementation to collect own parameters.
            :note: currency exchange factor would not be used here,
                   but only in special object context.
        """
        paras = get_default_parameter_values()
        if exch_factor is None:
            exch_factor = {}
        if record is None:
            record = calculation
        for pval in sqlapi.RecordSet2("cdbpco_para_val_v", "context_object_id = '%s'" % record.cdb_object_id):
            if pval.curr_object_id and\
                    "curr_object_id" in record and\
                    pval.curr_object_id != record.curr_object_id:
                exch = exch_factor.setdefault((pval.curr_object_id, record.curr_object_id),
                                              CurrConversion.getCurrExchangeFactor(
                                                  pval.curr_object_id,
                                                  record.curr_object_id,
                                                  calculation.cdb_project_id))
                paras["values"][pval.para_code] = pval.value * exch if exch else pval.value
            else:
                paras["values"][pval.para_code] = pval.value
            if pval.context_only and int(pval.context_only) != 0:
                paras[CONTEXT_ONLY_KEY].append(pval.para_code)
        results = [cls.get_own_parameter_values(record=record,
                                                classname=classname,
                                                calculation=calculation,
                                                ctx=ctx,
                                                exch_factor=exch_factor)]
        results += sig.emit(cls, PARAMETER_SIGNAL)(record, classname, calculation, ctx, exch_factor)
        for result in results:
            paras["values"].update(result["values"])
            if CONTEXT_ONLY_KEY in result:
                paras[CONTEXT_ONLY_KEY] += result[CONTEXT_ONLY_KEY]
        return paras

    @classmethod
    def get_own_parameter_values(cls, record=None, classname=None, calculation=None,
                                 ctx=None, exch_factor=None):
        no_values = dict(values={})
        no_values[CONTEXT_ONLY_KEY] = []
        return no_values

    @classmethod
    def get_aggregate_result(cls, rdef, record):
        """
        Get the result for definition rdef from the current object, return it
        for aggregation.
        """
        if record and rdef:
            rs = ResultValue.KeywordQuery(rdef_object_id=rdef.cdb_object_id,
                                          context_object_id=record.cdb_object_id)
            if rs:
                return rs[0].value
        return 0.0

    @classmethod
    def create_result(cls, record, rdef_id, val, calc_object_id, entered_value, ctx=None):
        """
        Save the result in database.
        """
        ResultValue.Create(cdb_object_id=cdbuuid.create_uuid(),
                           context_object_id=record.cdb_object_id,
                           calc_object_id=calc_object_id,
                           rdef_object_id=rdef_id,
                           entered_value=entered_value,
                           value=val)

    @classmethod
    def should_use_formula_for_result(cls, classname, rdef, ctx=None):
        """
        Default implementation to tell whether the result should be calculated
        using formula or not.
        :Parameters:
            - `rdef` : The result definition
            - `ctx` : The context adapter
        :return: True if the formula should be used.
        """
        # not_aggr_for == "*": calculate using formula for all classes
        # not_aggr_for contains current object class: calculate using formula
        # help_value == 1: Current result is a help value, should always be
        #                  calculated
        # otherwise: The value should be aggregated from results of child objects.
        if rdef.not_aggr_for == "*":
            return True
        if rdef.not_aggr_for:
            clsnames = rdef.not_aggr_for.replace(" ", "").split(",")
            if classname in clsnames:
                return True
        return rdef.help_value == 1

    @classmethod
    def calculate_result(cls, rdef, paras, record=None, ctx=None):
        """
        Calculate a single result.
        :Parameters:
            - `rdef` : The result definition
            - `paras` : The given parameters
            - `ctx` : The context adapter
        :returns:
            - calculated result
            - jumpout: whether to break calculation for current object
        """
        # Get the parameter of right type
        fml = rdef.formula
        val = 0.0
        if fml:
            try:
                # !!!!!! Caution !!!!!!
                # Remove all methods from builtins to keep the eval() safe.
                # But the call of eval() is not 100% safe yet.
                # The user must not input sth. like "2**2000000000" as formula,
                # it may not lead to error but the cpu will be overloaded.
                biarg = {"__builtins__": []}
                if record:
                    fml = fml.format(**record)
                    if 'None' in fml:
                        fml.replace('None', '0.0')
                if "CHILD_" + rdef.code not in paras:
                    paras["CHILD_" + rdef.code] = 0.0
                val = eval(fml, biarg, paras)
            except Exception as e:
                # Exception handler while calculating results
                # Ignore the current result, continue with next result
                # definition
                if rdef.exception_handler == "Continue":
                    return None, False
                # Break calculation for current object, continue with next
                # object
                elif rdef.exception_handler == "Break":
                    return None, True
                # Cancel the current calculation, throw exception
                else:
                    from cdb import CADDOK
                    raise ue.Exception("cdbpco_result_exception",
                                       "%s: %s" % (rdef.code, e),
                                       record.name if CADDOK.ISOLANG == "de" else record.ml_name_en)
        else:
            # Ignore the current result, continue with next result definition
            return None, False
        paras[rdef.code] = val
        return val, False

    @classmethod
    def calculate_results(cls, record=None, classname=None, calculation=None, rdefs=None,
                          aggr_children=None, paras=None, ctx=None, exch_factor=None,
                          entered_values=None, processed_objects=[]):
        """
        Calculate all results of current object.
        :Parameters:
            - `rdefs`: A list from to calculated result definitions
            - `aggr_children`: A list from (child objects, assigend amount)
                               pairs to aggregate the results
            - `paras`: The parameters
            - `ctx`: The context adapter
            - `exch_factor`: The currency exchange factors
        :returns: A dictionary from (definition id : result value) items.
        """
        if exch_factor is None:
            exch_factor = {}
        if classname is None:
            classname = cls.__classname__
        if rdefs is None:
            rdefs = []
        if aggr_children is None:
            aggr_children = {}

        if not paras:
            paras = cls.get_parameter_values(record={}, classname=classname, calculation=calculation,
                                             ctx=ctx, exch_factor=exch_factor)
        results = {}
        for rdef in rdefs:
            if cls.should_use_formula_for_result(classname, rdef, ctx):
                child_val = 0.0
                org_calc_val = 0.0
                if classname not in ["cdbpco_delivery", "cdbpco_calculation", "cdbpco_product"]\
                        and record and record.cdb_object_id in aggr_children:
                    children = aggr_children[record.cdb_object_id].get(rdef.code, [])
                    for child in children:
                        if child["curr_object_id"] == record.curr_object_id:
                            child_val += child["val_o"] * child["quantity"]
                            org_calc_val += (child["val_o"] * child["quantity"])
                        else:
                            exch = 1.0
                            if rdef.is_currency:
                                exch = exch_factor.setdefault(
                                    (child["curr_object_id"], record.curr_object_id),
                                    CurrConversion.getCurrExchangeFactor(
                                        child["curr_object_id"],
                                        record.curr_object_id,
                                        record.cdb_project_id))
                            exch_val = (child["val_o"] * child["quantity"] * exch)
                            child_val += exch_val
                            org_calc_val += exch_val
                    paras["values"]["CHILD_" + rdef.code] = child_val
        for rdef in rdefs:
            if cls.should_use_formula_for_result(classname, rdef, ctx):
                sig.emit(cls, PRE_CALC_SIGNAL)(record, rdef, paras["values"])
                rval, jump_out = cls.calculate_result(rdef, paras["values"], record, ctx)
                # Break the calculation for current object(move to next object
                # if exists)
                if not rval:
                    rval = 0.0
                if jump_out:
                    return results
                if record:
                    if rdef.is_currency:
                        calc_curr = record.calc_curr_object_id
                        exch = 1.0
                        if record.curr_object_id:
                            if record.curr_object_id != calc_curr:
                                exch = exch_factor.setdefault((record.curr_object_id, calc_curr),
                                                              CurrConversion.getCurrExchangeFactor(
                                                                  record.curr_object_id,
                                                                  calc_curr,
                                                                  record.cdb_project_id))
                            convs = UnitConversion.convert_price_from_to_unit(
                                record.cost_unit, record.mengeneinheit, 1.0)
                            org_calc_val = rval * convs
                            rval = rval * exch * convs
                    else:
                        org_calc_val = rval
                    if rdef.add_to_parent and getattr(record, "parent_object_id", False):
                        if paras["values"]["INTERNAL_PARENT_ID"] not in aggr_children:
                            aggr_children[paras["values"]["INTERNAL_PARENT_ID"]] = {}
                        if rdef.code not in aggr_children[paras["values"]["INTERNAL_PARENT_ID"]]:
                            aggr_children[paras["values"]["INTERNAL_PARENT_ID"]][rdef.code] = [{
                                "val_e": rval,
                                "val_o": org_calc_val,
                                "curr_object_id": record.curr_object_id,
                                "quantity": paras["values"]["QUANT"],
                                "cdb_object_id": record.cdb_object_id
                            }]
                        else:
                            clone = False
                            for agc in aggr_children[paras["values"]["INTERNAL_PARENT_ID"]][
                                rdef.code]:
                                if agc["cdb_object_id"] == record.cdb_object_id:
                                    clone = True
                            if not clone:
                                aggr_children[paras["values"]["INTERNAL_PARENT_ID"]][
                                    rdef.code].append({
                                    "val_e": rval,
                                    "val_o": org_calc_val,
                                    "curr_object_id": record.curr_object_id,
                                    "quantity": paras["values"]["QUANT"],
                                    "cdb_object_id": record.cdb_object_id
                                })

            else:
                rval = paras["values"].get(rdef.code, 0.0)
                for (cld, amount) in aggr_children:
                    if type(cld) is dict:
                        aggval = cld.get(rdef.cdb_object_id, 0.0)
                    else:
                        aggval = cls.get_aggregate_result(rdef, cld)
                    # Assigned amount must be considered in aggregation
                    rval += aggval * amount
            if rval is not None:
                # The result itself can be used as "parameter" for further
                # calculation
                paras["values"][rdef.code] = rval
                # Only save the result to database if asked so, and never save
                # help values

                if rdef.help_value != 1:
                    calc_object_id = getattr(record, "calc_object_id", record.cdb_object_id)
                    entered_value = 0
                    if entered_values:
                        if record.cdb_object_id in entered_values:
                            if rdef.code in entered_values[record.cdb_object_id]:
                                entered_value = entered_values[record.cdb_object_id][rdef.code]
                    create_record = True
                    if processed_objects and record.cdb_object_id in processed_objects:
                        create_record = False
                    if create_record:
                        cls.create_result(record=record,
                                          rdef_id=rdef.cdb_object_id,
                                          val=rval,
                                          calc_object_id=calc_object_id,
                                          entered_value=entered_value,
                                          ctx=ctx)
                results[rdef.code] = rval
            sig.emit(cls, POST_CALC_SIGNAL)(record, rdef, paras["values"], results)
        return results, aggr_children


class CalculationSchema(Object, WithAuditTrail):
    """
    Schema of a Calculation, defines ParameterDefinitions and
    ResultDefinitions.
    """
    __maps_to__ = "cdbpco_schema"
    __classname__ = "cdbpco_schema"

    ParameterDefinitions = Reference_N(
        fParameterDefinition,
        fParameterDefinition.schema_object_id == fCalculationSchema.cdb_object_id)

    ResultDefinitions = Reference_N(
        fParameterDefinition,
        fParameterDefinition.schema_object_id == fCalculationSchema.cdb_object_id,
        fParameterDefinition.formula != '',
        order_by=fParameterDefinition.order_no)

    ResultDefinitionsByType = ReferenceMapping_N(
        fParameterDefinition,
        fParameterDefinition.schema_object_id == fCalculationSchema.cdb_object_id,
        fParameterDefinition.formula != '',
        order_by=fParameterDefinition.order_no,
        indexed_by=fParameterDefinition.type)

    OtherVersions = Reference_N(fCalculationSchema,
                                fCalculationSchema.ml_name_de == fCalculationSchema.ml_name_de,
                                fCalculationSchema.ml_name_en == fCalculationSchema.ml_name_en)

    ActiveVersions = Reference_N(fCalculationSchema,
                                 fCalculationSchema.ml_name_de == fCalculationSchema.ml_name_de,
                                 fCalculationSchema.ml_name_en == fCalculationSchema.ml_name_en,
                                 fCalculationSchema.active == 1,
                                 order_by=fCalculationSchema.schema_index)

    PreviousVersions = Reference_N(fCalculationSchema,
                                   fCalculationSchema.ml_name_de == fCalculationSchema.ml_name_de,
                                   fCalculationSchema.ml_name_en == fCalculationSchema.ml_name_en,
                                   fCalculationSchema.schema_index < fCalculationSchema.schema_index,
                                   order_by=fCalculationSchema.schema_index)

    Machines = Reference_N(fMachine,
                           fMachine.schema_object_id == fCalculationSchema.cdb_object_id)

    Currencies = Reference_N(fCurrency,
                             fCurrency.schema_object_id == fCalculationSchema.cdb_object_id)

    event_map = {
        ('copy', 'post'): ('copy_definitions', 'copy_currencies'),
        ('cdbpco_new_revision', 'now'): ('create_index'),
        ('delete', 'post'): ('delete_schema'),
        ('create', 'post'): ('create_calculation_currencies')
    }

    class DRAFT(State):
        status = 0

    class REVIEW(State):
        status = 100

    class BLOCKED(State):
        status = 170

        def post(state, self, ctx):  # @NoSelf
            self.active = 0

    class OBSOLETE(State):
        status = 180

        def post(state, self, ctx):  # @NoSelf
            self.active = 0

    class REVISION(State):
        status = 190

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(CalculationSchema.RELEASED.status)
                ctx.excl_state(CalculationSchema.OBSOLETE.status)
            super(CalculationSchema.REVISION, state).pre_mask(self, ctx)

    class RELEASED(State):
        status = 200

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(CalculationSchema.REVISION.status)
            super(CalculationSchema.RELEASED, state).pre_mask(self, ctx)

        def post(state, self, ctx):  # @NoSelf
            self.active = 1
            if len(self.PreviousVersions):
                if self.PreviousVersions[-1].status == CalculationSchema.REVISION.status:
                    self.PreviousVersions[-1].ChangeState(CalculationSchema.OBSOLETE.status)

    def create_index(self, ctx):
        new_index = max(self.OtherVersions.schema_index) + 1

        def init_status_schema(schema_index):
            # initial status attributes
            return {"status": 0,
                    "schema_index": schema_index,
                    "active": 0,
                    "cdb_status_txt": olc.StateDefinition.ByKeys(0, "cdbpco_schema").StateText['']}

        new_scheme = operations.operation("CDB_Copy", self, **init_status_schema(new_index))
        if new_scheme:
            self.ChangeState(CalculationSchema.REVISION.status)

            def init_new_machine():
                return {"schema_object_id": new_scheme.cdb_object_id}
            for machine in self.Machines.KeywordQuery(status=200):
                operations.operation("cdbpco_new_revision", machine, **init_new_machine())

    def create_calculation_currencies(self, ctx):
        currencies = Currency.Query("schema_object_id='' or schema_object_id is null")
        self.copy_from_currencies(currencies)
        default_ones = {curr.name: curr.cdb_object_id for curr in currencies}
        for currency in self.Currencies:
            CurrConversion.Create(from_curr_object_id=currency.cdb_object_id,
                                  to_curr_object_id=default_ones[currency.name],
                                  convert_factor=1.0)

    def copy_from_currencies(self, currencies):
        mapping = {}
        for currency in currencies:
            nc = currency.Copy(schema_object_id=self.cdb_object_id,
                               is_ref_curr=0)
            mapping[currency.cdb_object_id] = nc.cdb_object_id
        for conversion in CurrConversion.KeywordQuery(from_curr_object_id=mapping.keys()):
            try:
                conversion.Copy(from_curr_object_id=mapping[conversion.from_curr_object_id],
                                to_curr_object_id=mapping[conversion.to_curr_object_id]
                                if conversion.to_curr_object_id in mapping
                                else conversion.to_curr_object_id)
            except KeyError as e:
                pass
        return mapping

    def copy_currencies(self, ctx):
        old_object = CalculationSchema.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        mapping = self.copy_from_currencies(old_object.Currencies)
        for curr in mapping.keys():
            ParameterValue.KeywordQuery(curr_object_id=curr,
                                        pdef_object_id=self.ParameterDefinitions.cdb_object_id).Update(
                    curr_object_id=mapping[curr])

    def delete_schema(self, ctx):
        if self.PreviousVersions:
            last_one = self.PreviousVersions[-1]
            if last_one.status == CalculationSchema.REVISION.status:
                last_one.ChangeState(CalculationSchema.RELEASED.status)

    def copy_definitions(self, ctx):
        """
        Copy also the ParameterDefinitions while being
        copied.
        """
        template_obj = CalculationSchema.ByKeys(
                            ctx.cdbtemplate["cdb_object_id"])
        for pdef in template_obj.ParameterDefinitions:
            pdef.copy_to(self)

    def on_cdbpco_parameter_copy_pre_mask(self, ctx):
        curryear = datetime.date.today().year
        ctx.set("from_year", curryear)
        ctx.set("to_year", curryear)

    def on_cdbpco_parameter_copy_pre(self, ctx):
        """
        Check whether the values which should be copied exist.
        """
        sqlstr = "select count(*) cnt from cdbpco_para_val where "
        sqlstr += " pdef_object_id in ("
        sqlstr += "  select cdb_object_id from cdbpco_para_def where "
        sqlstr += "   schema_object_id='%s') " % self.cdb_object_id
        sqlstr += " and context_object_id is null or context_object_id='' "
        sqlstr += " and costplant_object_id='%s' " % ctx.dialog['from_site']
        sqlstr += " and valid_year='%s' " % ctx.dialog['from_year']
        rset = sqlapi.RecordSet2(sql=sqlstr)
        if rset[0].cnt < 1:
            raise ue.Exception("cdbpco_err_msg_16")

    def on_cdbpco_parameter_copy_now(self, ctx):
        """
        Copy the default parameter value of the given site and year for
        another site and year.
        """
        for pdef in self.ParameterDefinitions:
            if pdef.has_defaults == 0:
                continue
            for pval in pdef.DefaultValues.KeywordQuery(
                            costplant_object_id=ctx.dialog['from_site'],
                            valid_year=ctx.dialog['from_year']):
                cond = dict(costplant_object_id=ctx.dialog['to_site'],
                            valid_year=ctx.dialog['to_year'],
                            material_object_id=pval.material_object_id,
                            technology_id=pval.technology_id)
                if len(pdef.DefaultValues.KeywordQuery(**cond)) > 0:
                    # check whether the existing value should be overwritten
                    if int(ctx.dialog['overwrite_value']) == 0:
                        continue
                    else:
                        pdef.DefaultValues.KeywordQuery(**cond).Delete()
                from cs.costing.parameters import ParameterValue
                cond.update(ParameterValue.MakeChangeControlAttributes())
                pval.Copy(**cond)


class UnitConversion(Object):
    """
    Conversion between units.
    """
    __maps_to__ = "cdbpco_unit_convert"
    __classname__ = "cdbpco_unit_convert"

    @classmethod
    def convert_quantity_from_to_unit(cls, from_unit, to_unit, from_value):
        """
        Convert quantity between units.
        :Parameters:
            - `from_unit` : the source unit
            - `to_unit` : the target unit
            - `from_value` : the quantity in source unit
        :returns: the quantity value in target unit
        """
        if from_unit != to_unit:
            convobj = UnitConversion.Query("from_unit='%s' and to_unit='%s'" %
                                                (from_unit, to_unit))
            if convobj and from_value and convobj[0].convert_factor:
                try:
                    return from_value * float(convobj[0].convert_factor)
                except Exception:
                    pass
        return from_value

    @classmethod
    def convert_price_from_to_unit(cls, from_unit, to_unit, from_value):
        """
        Convert price between units. It works same like
        `convert_quantity_from_to_unit`.
        """
        if from_unit != to_unit:
            convobj = UnitConversion.Query("from_unit='%s' and to_unit='%s'" %
                                                (from_unit, to_unit))
            if convobj and from_value and convobj[0].convert_factor:
                try:
                    return from_value / float(convobj[0].convert_factor)
                except Exception:
                    pass
        return from_value


@sig.connect(Currency, "delete", "pre")
def check_delete_currency(self, ctx):
    """
    Check the conditions before delete current object.
    """
    checkclasses = [fComponent,
                    fCalculation,
                    fPartCost,
                    ]
    # If current object is referenced from other objects,
    # it should not be delete.
    for chkcls in checkclasses:
        if len(chkcls.KeywordQuery(curr_object_id=self.cdb_object_id)):
            raise ue.Exception("cdbpco_err_msg_04")
    if len(CurrConversion.Query(
                "from_curr_object_id='%s' or to_curr_object_id='%s'" %
                (self.cdb_object_id, self.cdb_object_id))):
        raise ue.Exception("cdbpco_err_msg_04")
