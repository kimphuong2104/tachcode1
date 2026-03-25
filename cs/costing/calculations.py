#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
import six
from cs.workflow.briefcases import WithBriefcase

"""
The Product Costing Calculation classes.
"""
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime
import json
from cdb import auth
from cdb import ue
from cdb import sqlapi
from cdb import transaction
from cdb import cdbuuid
from cdb import constants
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Forward
from cdb.objects import operations
from cdb.objects import State
from cdb.platform import olc
from cdb.platform.mom.constraints import DDConstraintField
from cs.workflow import briefcases
from cs.tools.powerreports import WithPowerReports
from cs.currency import Currency
from cs.sharing.share_objects import WithSharing
from cs.vp.items import Item
from cs.audittrail import WithAuditTrail
from cs.costing.schemes import WithCalculationSchema
from cs.costing.parameters import get_default_parameter_values
from cs.costing.parameters import init_parameter_cache
from cs.costing.parameters import ResultValue
from cs.costing.components import Component
from cs.costing.components import Product2Delivery
from cs.costing.components import Delivery
from cs.costing.components import Product
from cs.costing.components import Component2Component
from cs.costing.components import Component2Delivery
from cs.costing.components import PartComponent
from cs.costing.parameters import ParameterValue
from cs.costing.volume_curve import VolumeCurveEntry


rac__all__ = ["Calculation", "CalculationStatiProt"]

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
fVolumeCurveEntry = Forward("cs.costing.volume_curve.VolumeCurveEntry")
fClonedComponent = Forward("cs.costing.components.Component2Component")

CONTEXT_ONLY_KEY = "__context_only__"


class Calculation(Object, WithPowerReports, WithCalculationSchema, briefcases.BriefcaseContent, WithSharing, WithAuditTrail, WithBriefcase):
    """
    The Calculation object. It contains the common bussiness
    logic for all calculations.
    """

    __maps_to__ = "cdbpco_calculation"
    __classname__ = "cdbpco_calculation"

    # Here defines which attribute from the default object should be taken as
    # the default schema id for the calculation.
    default_schema_attribute = "schema_object_id"

    Currency = Reference_1(Currency,
                           fCalculation.curr_object_id)

    Deliveries = Reference_N(fDelivery,
                             fDelivery.calc_object_id == fCalculation.cdb_object_id,
                             order_by=fDelivery.sales_year)

    ComponentFolders = Reference_N(fComponentFolder,
                                   fComponentFolder.calc_object_id == fCalculation.cdb_object_id,
                                   order_by=fComponentFolder.order_no)

    Products = Reference_N(fProduct,
                           fProduct.calc_object_id == fCalculation.cdb_object_id)

    Product = Reference_1(fProduct,
                          fCalculation.cdbvp_product_object_id)

    Item = Reference_1(fItem,
                       fCalculation.teilenummer,
                       fCalculation.t_index)

    Components = Reference_N(fComponent,
                             fComponent.calc_object_id == fCalculation.cdb_object_id)

    TopComponents = Reference_N(fComponent,
                                fComponent.calc_object_id == fCalculation.cdb_object_id,
                                fComponent.parent_object_id == "")

    ClonedComponents = Reference_N(fClonedComponent,
                             fClonedComponent.calc_object_id == fCalculation.cdb_object_id)

    CalculationSchema = Reference_1(fCalculationSchema,
                                    fCalculation.schema_object_id)

    ParameterValues = Reference_N(fParameterValue,
                                  fParameterValue.context_object_id == fCalculation.cdb_object_id)

    ResultValues = Reference_N(fResultValue,
                               fResultValue.context_object_id == fCalculation.cdb_object_id)

    OtherVersions = Reference_N(fCalculation,
                                fCalculation.name == fCalculation.name,
                                fCalculation.cdb_project_id == fCalculation.cdb_project_id,
                                fCalculation.c_index != fCalculation.c_index)

    PreviousVersions = Reference_N(fCalculation,
                                   fCalculation.name == fCalculation.name,
                                   fCalculation.cdb_project_id == fCalculation.cdb_project_id,
                                   fCalculation.c_index < fCalculation.c_index,
                                   order_by=fCalculation.c_index)

    VolumeCurveEntries = Reference_N(fVolumeCurveEntry,
                                     fVolumeCurveEntry.calc_object_id == fCalculation.cdb_object_id,
                                     order_by=fVolumeCurveEntry.sales_year)

    event_map = {
        (('create', 'copy'), 'pre_mask'): 'set_defaults',
        ('modify', 'pre_mask'): 'reset_modify_mask',
        ('modify', 'post'): ('check_sop_eop', 'check_comp_excel_filenames'),
        ('delete', 'pre'): 'check_delete',
        ('delete', 'post'): ('delete_calculation_object', 'reset_obsolete_version'),
        (('create', 'copy', 'modify'), 'pre_mask'): '_set_readonly',
        (('create', 'copy', 'modify'), 'pre'): 'check_calc_name',
        ('create', 'pre'): 'calc_copy_run_create_pre',
        ('create', 'post'): 'calc_copy_run_create_post',
        (('create', 'copy', 'modify'), 'post'): 'set_currency',
        ('cdbpco_add_from_bom', 'now'): 'add_components_from_bom',
        ('cdbpco_import_component_part', 'now'): 'import_component_part',
        ('cdbpco_open_in_browser', 'now'): 'open_in_browser',
        ('cdbpco_delegate', 'now'): 'delegate_calculation',
        ('cdbpco_import_selective_struct', 'now'): 'add_selective_components_from_bom',
        ('copy', 'post'): "update_currencies"
    }

    @classmethod
    def get_default_schema_attribute(cls):
        return cls.default_schema_attribute

    def _set_readonly(self, ctx):
        ctx.set_fields_readonly(["cdb_status_txt", "status"])
        ctx.set_mandatory("costplant_object_id")

    @classmethod
    def is_calculation(cls):
        return True

    @classmethod
    def on_cdbpco_create_calc_from_template_now(cls, ctx):
        """
        Create a calculation from a chosen template. At first it opens a
        catalog which shows only filtered templates according to current
        relationship.
        """
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdbpco_calc_tmpl_br")
        else:
            cdb_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            template = Calculation.ByKeys(cdb_object_id)
            ctx.set_followUpOperation(
                "CDB_Copy",
                predefined=[("para_year", datetime.date.today().year)],
                keep_rship_context=True,
                op_object=template)

    # def copy_to(self, newproj):
    #     """
    #     Copy the current Calculation object to the new project.
    #     """
    #     newdata = {"cdb_project_id": newproj.cdb_project_id,
    #                "cdb_object_id": cdbuuid.create_uuid()}
    #     newdata.update(self.MakeChangeControlAttributes())
    #     new_calc = self.Copy(**newdata)
    #     # copy sub objects from the old to new Calculation object
    #     self.copy_sub_objects(new_calc)

    def set_defaults(self, ctx):
        # status
        self.status = Calculation.NEW.status
        self.cdb_status_txt = olc.StateDefinition.ByKeys(0, "cdbpco_calculation").StateText['']
        self.template = 0
        self.cdb_objektart = "cdbpco_calculation"

        if ctx.action == "create":
            # initiate revision no. by creating
            self.c_index = self.gen_c_index(True)
            # default base year: current year
            self.para_year = datetime.date.today().year
            self.subject_type = "Common Role"
            self.subject_id = "CDBPCO-Editor"
        if ctx.action == "copy" and "followup_cdbpco_new_revision" in \
           ctx.ue_args.get_attribute_names():
            ctx.skip_dialog()

    def on_copy_pre_mask(self, ctx):
        if "followup_cdbpco_new_revision" not in \
           ctx.ue_args.get_attribute_names():
            # reset revision to 0 in all cases by copying
            ctx.set("c_index", self.gen_c_index(True))
        else:
            # creating revision: set some fields readonly
            ctx.set_fields_readonly(["name",
                                     "template",
                                     "cdb_project_id",
                                     "project_name",
                                     "schema_object_id",
                                     "category_name",
                                     "costplant_object_id",
                                     "curr_object_id"])
        self.reset_status(ctx)

    def on_copy_post(self, ctx):
        self.setObsoleteVersion(ctx)
        template_obj = Calculation.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        self.calc_copy_from_template(ctx, template_obj)

    def setObsoleteVersion(self, ctx):
        if "followup_cdbpco_new_revision" not in \
                ctx.ue_args.get_attribute_names():
            return
        if len(self.PreviousVersions):
            if self.PreviousVersions[-1].status in [Calculation.NEW.status,
                                                    Calculation.COMPLETED.status]:
                self.PreviousVersions[-1].ChangeState(Calculation.OBSOLETE.status)

    def reset_obsolete_version(self, ctx):
        # only if current version is the newest one
        prev = len(self.PreviousVersions)
        if prev and prev == len(self.OtherVersions):
            last_one = self.PreviousVersions[-1]
            if last_one.status == Calculation.OBSOLETE.status:
                last_one.ChangeState(Calculation.NEW.status)
                last_one.cdb_obsolete = 0

    def calc_copy_from_template(self, ctx, template_obj):
        if template_obj:
            self.getPersistentObject().Update(
                template_object_id=template_obj.cdb_object_id)
            template_obj.copy_sub_objects(self)
            if not self.template:
                # If:
                # - copying object is a template or
                # - copied object has different schema as the copying object
                # - copied object belongs to different plant as the copying
                #   object
                # - copied object uses parameter values for different year as
                #   the copying object
                # then initiate the parameters for the copied object using
                # default values.
                if template_obj.template or \
                    self.schema_object_id != template_obj.schema_object_id or \
                    self.costplant_object_id != template_obj.costplant_object_id or \
                    self.para_year != template_obj.para_year:
                    self.create_default_parameters(ctx)
                    Component.create_default_parameters_for_components(self.Components)
                # otherwise copy the parameters from the copying object
                else:
                    ParameterValue.copy_parameters_to(template_obj, self)
                    # maybe it needs to generate new parameter value because of
                    # year deference
                    self.create_default_parameters(ctx, template_obj)

    def copy_sub_objects(self, new_calc):
        """
        Copy sub objects to new Calculation object.
        :Parameters:
            - `new_calc` : The new Calculation object
        """
        newobj_dict = {}
        # copy Component Folders
        compfolders = self.ComponentFolders.Query("parent_object_id=''")
        for oldobj in compfolders:
            oldobj.copy_to(new_calc, newobj_dict)
        # copy Products
        for oldobj in self.Products:
            oldobj.copy_to(new_calc, newobj_dict)
        # copy Components
        for oldobj in self.TopComponents:
            newobj = oldobj.copy_to(new_calc, newobj_dict)
            Component.copy_structure_for_component(oldobj,
                                                   newobj,
                                                   newobj_dict=newobj_dict,
                                                   copy_clones=True)
        for oldobj in self.Deliveries:
            oldobj.copy_to(new_calc, newobj_dict)

    def calc_copy_run_create_pre(self, ctx):
        # Calling the "copy as" operation.
        if "calc_copying_from" in ctx.dialog.get_attribute_names():
            ctx.keep("calc_copying_from", ctx.dialog['calc_copying_from'])

    def set_currency(self, ctx):
        available_currencies = Currency.KeywordQuery(name=self.curr_name,
                                                     schema_object_id=self.schema_object_id)
        if available_currencies and\
            self.curr_object_id and\
            self.curr_object_id not in available_currencies.cdb_object_id:
            Calculation.ByKeys(self.cdb_object_id).Update(curr_object_id=available_currencies[0].cdb_object_id)

    def calc_copy_run_create_post(self, ctx):
        # Calling the "copy as" operation.
        template_obj = None
        if "calc_copying_from" in ctx.ue_args.get_attribute_names():
            template_obj = Calculation.ByKeys(ctx.ue_args["calc_copying_from"])
            self.calc_copy_from_template(ctx,
                                         template_obj)
            if template_obj:
                # also copy the document assignments
                if hasattr(template_obj, "DocumentAssignments"):
                    for docassign in template_obj.DocumentAssignments:
                        docassign.copy_to(self)

    def on_create_post(self, ctx):
        if "calc_copying_from" not in ctx.ue_args.get_attribute_names():
            # It is not calling the "copy as" operation.
            # If current Calculation object is not a template, then create
            # default parameter values for it.
            if not self.template:
                self.create_default_parameters(ctx)

    def create_default_parameters(self, ctx, template_obj=None):
        """
        Create default parameter values for a Calculation object.
        """
        # generate the query conditions: valid year and plant
        year = self.para_year
        if not year:
            year = "%d" % datetime.date.today().year
        qstr = "valid_year='%s'" % year
        if self.costplant_object_id:
            qstr += " and costplant_object_id='%s'" % self.costplant_object_id
        pdefs = self.CalculationSchema.ParameterDefinitions
        tmplvals = []
        # If a Calculation object is given as a template,
        # then some values should be copied from it, just skip them.
        # Otherwise create all new default values.
        if template_obj:
            tmplvals = template_obj.ParameterValues.pdef_object_id
        real_pdefs = {}

        for pdef in pdefs:
            if pdef.has_defaults == 0:
                continue
            if pdef.code not in real_pdefs:
                real_pdefs[pdef.code] = pdef
            elif self.GetClassname() == '':
                real_pdefs[pdef.code] = pdef
            else:
                continue

        for pdef in pdefs:
            # current parameter value should be copied from template object if
            # given
            if pdef.cdb_object_id in tmplvals:
                continue

            dvals = pdef.DefaultValues.Query(qstr)

            if dvals:
                for dval in dvals:
                    dval.copy_to_context_object(context_object_id=self.cdb_object_id)
            else:
                ParameterValue.createForContextObject(
                    pdef,
                    context_object_id=self.cdb_object_id,
                    value=0.0)

    def on_cdbpco_init_parameter_now(self, ctx):
        """
        Recreate all parameters from default values.
        """
        if not self.template:
            init_parameter_cache(True)
            self.ParameterValues.KeywordQuery(overwrite=1).Delete()
            self.create_default_parameters(ctx)
            Component.create_default_parameters_for_components(self.Components)
            Delivery.create_default_parameters_for_deliveries(self.Deliveries)
        else:
            raise ue.Exception("cdbpco_err_msg_13")

    def reset_modify_mask(self, ctx):
        ctx.set_fields_readonly(["schema_object_id",
                                 "costplant_object_id",
                                 "template",
                                 "mapped_classname"])
        # lock name attribute if calculation already has other versions
        if self.has_other_versions():
            ctx.set_readonly("name")
        # Keep consistent project references with revisions etc.
        if self.Project:
            ctx.set_fields_readonly(["cdb_project_id", "project_name"])

    def check_sop_eop(self, ctx):
        changed = False
        if self.sop != ctx.previous_values.sop:
            if self.sop > ctx.previous_values.sop:
                old_entries = self.VolumeCurveEntries.Query("sales_year < '%s'" % self.sop)
                for old_entry in old_entries:
                    operations.operation("CDB_Delete", old_entry)
            else:
                if self.VolumeCurveEntries:
                    start_entry = self.VolumeCurveEntries[0]
                    for i in six.moves.range(int(ctx.previous_values.sop), int(self.sop), -1):
                        start_entry.Copy(amount=0,
                                         sales_year=str(i - 1))
            changed = True
        if self.eop != ctx.previous_values.eop:
            if self.eop < ctx.previous_values.eop:
                old_entries = self.VolumeCurveEntries.Query("sales_year > '%s'" % self.eop)
                for old_entry in old_entries:
                    operations.operation("CDB_Delete", old_entry)
            else:
                if self.VolumeCurveEntries:
                    start_entry = self.VolumeCurveEntries[-1]
                    for i in six.moves.range(int(ctx.previous_values.eop), int(self.eop)):
                        start_entry.Copy(amount=0,
                                         sales_year=str(i + 1))
            changed = True
        if changed:
            for delivery in self.Deliveries:
                operations.operation("CDB_Delete", delivery)
            Calculation.ByKeys(self.cdb_object_id).Update(para_year=self.sop)

    def check_comp_excel_filenames(self, ctx):
        for c in self.Components:
            c.check_excel_filename(ctx)

    def on_cdbpco_calculate_results_now(self, ctx):
        """
        Calculate results for current Calculation
        object.
        """
        if not self.template:
            self.ResultValues.Delete()
            self._calculate_result(ctx)
        else:
            raise ue.Exception("cdbpco_err_msg_13")

    def calculate_components(self, comp, cloned_components, parameter_cache,
                             calc_paras, curr_exchange_factor, comp_mapping,
                             entered_values, ctx):
        components_to_calc = [comp]
        components_to_calc += self.get_components_from_structure(comp)
        components_to_calc.reverse()
        aggr_children = {}
        processed_objects = []
        for component in components_to_calc:
            if type(component) == tuple:
                c = component[0]
                parent_id = component[1].parent_object_id if \
                    component[1] else c.parent_object_id
                quantity = component[1].quantity if component[1] else c.quantity
            else:
                c = component
                parent_id = c.combined_parent if "combined_parent" in c else c.parent_object_id
                quantity = c.combined_quantity if "combined_quantity" in c else c.quantity
            if not c:
                continue
            if c.cloned:
                cloned_components.append(c.cdb_object_id)
            if parent_id in cloned_components:
                continue
            cls_name = c.cdb_classname
            defs = parameter_cache[self.schema_object_id][cls_name]["formulas"] if cls_name in \
                                                                                   parameter_cache[
                                                                                       self.schema_object_id] else \
            parameter_cache[self.schema_object_id][""]["formulas"]

            # get combined parameter list
            comp_paras = Component.get_parameter_values(
                record=c,
                classname=c.cdb_classname,
                calculation=self,
                parent_paras=calc_paras,
                ctx=ctx,
                exch_factor=curr_exchange_factor)
            comp_paras["values"]["QUANT"] = quantity
            comp_paras["values"]["MAX_VC_QUANT"] = comp.VolumeCurve.peak_amount
            comp_paras["values"]["MIN_VC_QUANT"] = comp.VolumeCurve.minimal_amount
            comp_paras["values"]["AVG_VC_QUANT"] = comp.VolumeCurve.mean_amount
            comp_paras["values"]["INTERNAL_PARENT_ID"] = parent_id
            # calculate the result, force eval the formula, save the
            # results in database if required

            compresult, aggr_children = Component.calculate_results(record=c,
                                                                    classname=c.cdb_classname,
                                                                    rdefs=defs,
                                                                    aggr_children=aggr_children,
                                                                    paras=comp_paras,
                                                                    entered_values=entered_values,
                                                                    processed_objects=processed_objects)
            # save the results temporarily to speed up the calculation
            # process
            comp_mapping[c.cdb_object_id] = compresult
            processed_objects.append(c.cdb_object_id)

    def cleanup_volume_curves(self, comp, top_comp=None):
        recalc_vc = False
        years = six.moves.range(int(self.sop), int(self.eop) + 1)
        missing_years = set()
        c_vc = comp.VolumeCurve
        if c_vc:
            if top_comp:
                p_vc = top_comp.VolumeCurve
                if c_vc.volume_curve_object_id != p_vc.volume_curve_object_id:
                    if c_vc.Entries:
                        c_vc.Entries.Delete()
                    c_vc.Update(volume_curve_object_id=p_vc.volume_curve_object_id)
                    recalc_vc = True
            if c_vc.Entries:
                for entry in c_vc.Entries:
                    if int(entry.sales_year) not in years:
                        entry.Delete()
                        recalc_vc = True
                        continue
                    missing_years.add(int(entry.sales_year))
                missing_years = list(set(years) - missing_years)
                for missing in missing_years:
                    VolumeCurveEntry.CreateNoResult(
                        sales_year=str(missing),
                        amount=0,
                        volume_curve_object_id=comp.VolumeCurve.cdb_object_id,
                        calc_object_id=self.cdb_object_id,
                        primary_component_object_id=comp.VolumeCurve.cdb_object_id
                    )
                    recalc_vc = True
        elif not top_comp:
            raise ue.Exception("cdbpco_volume_curve_missing", comp.GetDescription())
        if not top_comp:
            for delivery in self.Deliveries:
                if int(delivery.sales_year) not in years:
                    delivery.cdbpco_delete()
                    delivery.Delete()
        if recalc_vc:
            c_vc.set_volume_curve_values()

    def perform_cleanup(self, ctx=None):
        # Perform cleanup
        comps_in_struct = set()

        for top_comp in self.TopComponents:
            self.cleanup_volume_curves(top_comp)
            comps_in_struct.add(top_comp.cdb_object_id)
            comp_struct = self._get_component_structure_other(top_comp)
            for calc_comp in comp_struct:
                if type(calc_comp) == tuple:
                    c = calc_comp[0]
                else:
                    c = calc_comp
                comps_in_struct.add(c.cdb_object_id)
                self.cleanup_volume_curves(c, top_comp)

        for calc_comp_to_delete in self.Components:
            if calc_comp_to_delete.cdb_object_id not in comps_in_struct:
                cc = Component2Component.KeywordQuery(comp_object_id=calc_comp_to_delete.cdb_object_id,
                                                      calc_object_id=self.cdb_object_id)
                if cc:
                    cc.Delete()
                calc_comp_to_delete.cdbpco_delete()
                calc_comp_to_delete.Delete()


    def calculate_component(self, comp, ctx=None):
        """
        Calculate results for a single component.
        """
        # if not parameter_cache:
        init_parameter_cache()
        from cs.costing.parameters import parameter_cache
        curr_exchange_factor = {}
        # get all parameters from Calculation object
        calc_paras_all = Calculation.get_parameter_values(record=None,
                                                          classname=None,
                                                          calculation=self,
                                                          parent_paras={},
                                                          ctx=ctx,
                                                          exch_factor=curr_exchange_factor,
                                                          is_calculation=True)
        # the parameters for current calculating step
        calc_paras = {}

        calc_children = []
        with transaction.Transaction():
            # get the context-only parameter list from parameters of
            # Calculation object (to ignore)
            context_only = calc_paras_all.get(CONTEXT_ONLY_KEY)
            # remove context-only parameters from parent parameters
            # the other parameters including so far calculated results
            # will be taken by further calculation
            calc_paras = get_default_parameter_values({
                k: v for k, v in six.iteritems(calc_paras_all["values"])
                if k not in context_only
            })

            comp_mapping = {}
            entered_values = {}
            keep_values = ResultValue.Query("context_object_id IN (SELECT cdb_object_id "
                                            "FROM cdbpco_component WHERE calc_object_id = '%s') AND entered_value > 0" % self.cdb_object_id)
            for kv in keep_values:
                if kv.context_object_id in entered_values:
                    entered_values[kv.context_object_id][kv.para_code] = kv.entered_value
                else:
                    new_entry = {}
                    new_entry[kv.para_code] = kv.entered_value
                    entered_values[kv.context_object_id] = new_entry
            # Delete result values for components
            ResultValue.Query("context_object_id IN (SELECT cdb_object_id "
                              "FROM cdbpco_component WHERE calc_object_id = '%s')" % self.cdb_object_id).Delete()
            cloned_components = []
            self.perform_cleanup()
            self.calculate_components(comp, cloned_components, parameter_cache,
                                      calc_paras, curr_exchange_factor, comp_mapping,
                                      entered_values, ctx)

    def _calculate_result(self, ctx):
        """
        Calculate results.
        """
        # if not parameter_cache:
        init_parameter_cache()
        from cs.costing.parameters import parameter_cache
        curr_exchange_factor = {}
        # get all parameters from Calculation object
        calc_paras_all = Calculation.get_parameter_values(record=None,
                                                          classname=None,
                                                          calculation=self,
                                                          parent_paras={},
                                                          ctx=ctx,
                                                          exch_factor=curr_exchange_factor,
                                                          is_calculation=True)
        # the parameters for current calculating step
        calc_paras = {}

        # calc_children: save "direct" child objects using to generate the
        # aggregated values for the Calculation object.
        # The "direct" children are objects that can be find in the highest
        # level in the hierarchy:
        # "Delivery>Product>Component". Every "direct" child can
        # only be 1x assigned to the Calculation object. It would NOT be used
        # for calculating other sub objects in intermediate levels.
        calc_children = []
        with transaction.Transaction():
            # get the context-only parameter list from parameters of
            # Calculation object (to ignore)
            context_only = calc_paras_all.get(CONTEXT_ONLY_KEY)
            # remove context-only parameters from parent parameters
            # the other parameters including so far calculated results
            # will be taken by further calculation
            calc_paras = get_default_parameter_values({
                k: v for k, v in six.iteritems(calc_paras_all["values"])
                if k not in context_only
            })

            # calculate QUANT for Products
            prod_amount = sqlapi.RecordSet2(sql=(
                "select product_object_id, sum(amount) as total "
                "from %s where calc_object_id='%s' and amount<>0 "
                "group by product_object_id" % (
                    Product2Delivery.GetTableName(), self.cdb_object_id)
            ))
            prod_total = dict(
                [(r.product_object_id, r.total) for r in prod_amount])

            # =============================================================
            # Typically only the results of components would be calculated
            # via formula, the results for objects of higher levels are
            # summed up. (Exception: relative values & help values are
            # always be calculated via formula.)
            # =============================================================
            # results of components
            comp_mapping = {}
            entered_values = {}
            keep_values = ResultValue.Query("context_object_id IN (SELECT cdb_object_id "
                                            "FROM cdbpco_component WHERE calc_object_id = '%s') AND entered_value > 0" % self.cdb_object_id)
            for kv in keep_values:
                if kv.context_object_id in entered_values:
                    entered_values[kv.context_object_id][kv.para_code] = kv.entered_value
                else:
                    new_entry = {}
                    new_entry[kv.para_code] = kv.entered_value
                    entered_values[kv.context_object_id] = new_entry
            # Delete result values for components
            ResultValue.Query("context_object_id IN (SELECT cdb_object_id "
                              "FROM cdbpco_component WHERE calc_object_id = '%s')" % self.cdb_object_id).Delete()
            ResultValue.Query("context_object_id IN (SELECT cdb_object_id "
                              "FROM cdbpco_product WHERE calc_object_id = '%s')" % self.cdb_object_id).Delete()
            ResultValue.Query("context_object_id IN (SELECT cdb_object_id "
                              "FROM cdbpco_delivery WHERE calc_object_id = '%s')" % self.cdb_object_id).Delete()
            cloned_components = []
            self.perform_cleanup()
            for comp in self.TopComponents:
                self.calculate_components(comp, cloned_components, parameter_cache,
                                          calc_paras, curr_exchange_factor, comp_mapping,
                                          entered_values, ctx)

            # results of products
            defs = parameter_cache[self.schema_object_id][""]["formulas"]
            if self.Products:
                for prod in self.Products:
                    # components are children to be aggregated
                    aggr_children = []
                    for asgn in prod.ComponentAssignments:
                        amount = asgn.amount
                        # consider only assigned components
                        if amount == 0:
                            continue
                        # if component data is saved, use it, otherwise
                        # read it from database
                        if comp_mapping:
                            aggr_children.append(
                                (comp_mapping[asgn.comp_object_id],
                                 amount))
                        else:
                            aggr_children.append((asgn.Component, amount))
                    prod_paras = Product.get_parameter_values(
                        record=prod,
                        classname="",
                        calculation=self,
                        parent_paras=calc_paras,
                        ctx=ctx,
                        exch_factor=curr_exchange_factor)
                    prod_paras["values"]["QUANT"] = prod_total.get(prod.cdb_object_id, 0)
                    Product.calculate_results(record=prod,
                                              calculation=self,
                                              rdefs=defs,
                                              aggr_children=aggr_children,
                                              paras=prod_paras)
            # Deliveries
            if self.Deliveries:
                vc_in_py = {}
                for delivery in self.Deliveries:
                    year = int(delivery.sales_year) - int(self.sop)
                    vc = 0
                    if delivery.ComponentAssignments:
                        for asgn in delivery.ComponentAssignments:
                            vc += asgn.amount
                    else:
                        for asgn in delivery.ProductAssignments:
                            vc += asgn.amount
                    vc_in_py[year] = vc
                delivery_results = None
                for delivery in self.Deliveries:
                    aggr_children = []
                    if delivery.ComponentAssignments:
                        for asgn in delivery.ComponentAssignments:
                            aggr_children.append((asgn.Component, asgn.amount))
                    else:
                        for asgn in delivery.ProductAssignments:
                            aggr_children.append((asgn.Product, asgn.amount))
                    delivery_paras = Delivery.get_parameter_values(
                        record=delivery,
                        classname="",
                        calculation=self,
                        parent_paras=calc_paras,
                        ctx=ctx,
                        exch_factor=curr_exchange_factor)
                    delivery_paras["values"]["VOLUMECURVE_IN_PY"] = vc_in_py
                    if delivery_results:
                        for k, v in delivery_results.items():
                            delivery_paras["values"]["PRIOR_" + k] = v
                    delivery_results, children = Delivery.calculate_results(record=delivery,
                                               calculation=self,
                                               rdefs=defs,
                                               aggr_children=aggr_children,
                                               paras=delivery_paras)
                    calc_children.append((delivery, 1))

            # results for the Calculation object itself
            Calculation.calculate_results(record=self,
                                             calculation=self,
                                             rdefs=defs,
                                             aggr_children=calc_children,
                                             paras=calc_paras_all)

    def check_delete(self, ctx, deleting=None):
        """
        Check the conditions before delete current object.
        See implementations of sub classes.
        """
        pass

    def calcBatchDelete(self, ctx=None):
        fCalculationStatiProt.KeywordQuery(
                cdbparentobjectid=self.cdb_object_id).Delete()
        if hasattr(self, "DocumentAssignments"):
            self.DocumentAssignments.Delete()
        self.delete_calculation_object(ctx)
        self.Delete()

    def delete_calculation_object(self, ctx):
        """
        Delete or clean up the related objects of current Calculation object.
        Will be called by deleting the (parent) Calculation object.
        """
        self._delete_calculation_object(ctx)
        self.ParameterValues.Delete()
        self.ResultValues.Delete()

    def _delete_calculation_object(self, ctx):
        """
        Delete or clean up the related objects in rc structure of current
        Calculation object.
        """
        # tell the Deliveries to delete sub objects
        for calcobj in self.Deliveries:
            calcobj.delete_calculation_object(ctx)
        # tell the Products to delete sub objects
        for calcobj in self.Products:
            calcobj.delete_calculation_object(ctx)
        # tell the Components to delete sub objects
        for calcobj in self.Components:
            calcobj.delete_calculation_object(ctx)
        # then the folders
        for calcobj in self.ComponentFolders:
            calcobj.delete_calculation_object(ctx)

    def gen_c_index(self, usedefault=False):
        """
        Generate the revision number of the Calculation object.
        """
        if usedefault:
            return 0
        # find out the max value in database
        sql = ("select max(c_index) maxno from cdbpco_calculation where "
               "name='%s' and cdb_project_id='%s'" %
               (self.name, self.cdb_project_id))
        r = sqlapi.RecordSet2(sql=sql)
        # default value: 0
        rno = 0
        try:
            # try to increase the number
            rno = int(r[0].maxno) + 1
        except Exception:
            pass
        return rno

    def init_status(self):
        # initial status attributes
        return {"status": 0,
                "cdb_status_txt": olc.StateDefinition.ByKeys(0, "cdbpco_calculation").StateText['']}

    def reset_status(self, ctx):
        # reset status attributes to initial values
        for (k, v) in list(six.iteritems(self.init_status())):
            ctx.set(k, v)

    def on_cdbpco_new_revision_now(self, ctx):
        """
        Generate a new revision of the Calculation object.
        """
        if self.CalculationSchema.active:
            schema_object_id = self.schema_object_id
        else:
            actives = self.CalculationSchema.ActiveVersions
            if actives:
                schema_object_id = actives[-1].cdb_object_id
            else:
                raise ue.Exception("cdbpco_no_active_schema")

        # Also open the mask to provide an opportunity to change base year
        opargs = [("followup_cdbpco_new_revision", 1)]
        predefined = [("c_index", self.gen_c_index()),
                      ("schema_object_id", schema_object_id)]
        # call system operation of copy
        ctx.set_followUpOperation("CDB_Copy",
                                  opargs=opargs,
                                  predefined=predefined)

    def has_other_versions(self):
        """
        Indicate whether the current Calculation object has other versions.
        """
        return len(self.OtherVersions)

    def check_calc_name(self, ctx):
        """
        Check whether the name of the Calculation object is already in use
        while:
            - creating a Calculation object,
            - changing the name by modifying or copying.
        The same name can be used only if revision number, project id or
        calculation type changed. It will be checked through the constraints
        in configuration.
        """
        if ctx and ctx.dialog and "name" in ctx.dialog.get_attribute_names()\
            and (ctx.action == "create" or ctx.dialog.name != self.name or
            (ctx.action in ["copy", "modify"] and ctx.dialog.name != ctx.object.name)):
            if len(Calculation.Query("name='%s' and cdb_project_id='%s'" %
                                     (ctx.dialog.name, self.cdb_project_id))):
                raise ue.Exception("cdbpco_name_used")

    def confirm_create_deliveries(self, ctx):
        msg = ctx.MessageBox("cdbpco_create_deliveries_confirm",
                             [],
                             "confirm_replace_deliveries",
                             ctx.MessageBox.kMsgBoxIconQuestion)
        msg.addYesButton(1)
        msg.addCancelButton()
        ctx.show_message(msg)

    def on_cdbpco_create_deliveries_now(self, ctx):
        sop = self.sop
        eop = self.eop
        if ctx and ctx.dialog and "sop" in ctx.dialog.get_attribute_names():
            sop = ctx.dialog.sop
            eop = ctx.dialog.eop
        prev = self.Deliveries.Query(
            "sales_year>='%s' and sales_year<='%s'" % (
                sop, eop))
        if len(prev):
            if not "confirm_replace_deliveries" in ctx.dialog.get_attribute_names():
                self.confirm_create_deliveries(ctx)
            elif ctx.dialog["confirm_replace_deliveries"] != \
                ctx.MessageBox.kMsgBoxResultYes:
                return
        sop = int(sop)
        eop = int(eop)
        if sop and eop:
            if len(prev):
                for delivery in prev:
                    operations.operation(constants.kOperationDelete, delivery)
            vcs = {}
            for year in six.moves.range(sop, eop + 1):
                vcs[str(year)] = operations.operation(constants.kOperationNew,
                                                      Delivery,
                                                      calc_object_id=self.cdb_object_id,
                                                      sales_year=str(year),
                                                      **Delivery.MakeChangeControlAttributes())
            for vce in self.VolumeCurveEntries:
                Component2Delivery.Create(calc_object_id=self.cdb_object_id,
                                          comp_object_id=vce.primary_component_object_id,
                                          amount=vce.amount,
                                          delivery_object_id=vcs[vce.sales_year].cdb_object_id)

    def on_cdbpco_gen_product_from_part_now(self, ctx):
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdbpco_part_brows",
                                cdb_project_id=self.cdb_project_id if self.cdb_project_id else "")
        else:
            teilenummer = ctx.catalog_selection[0]["teilenummer"]
            t_index = ctx.catalog_selection[0]["t_index"]
            args = {"cdb::argument.gen_product_from_part": "1"}
            ctx.url(Product.MakeCdbcmsg(constants.kOperationNew,
                                        calc_object_id=self.cdb_object_id,
                                        teilenummer=teilenummer,
                                        t_index=t_index,
                                        **args).eLink_url())

    def _get_structure_oracle(self, bom_from_item):
        QUERYSTR = (
            "SELECT "
            "  e.rownr, e.stufe, e.baugruppe, e.b_index, e.teilenummer, e.t_index, e.menge, a.mengeneinheit,"
            "  a.t_kategorie, a.material_object_id, a.cdb_object_id"
            " FROM "
            " (SELECT rownum rownr, level stufe, baugruppe, b_index, teilenummer, t_index, menge "
            "   FROM einzelteile "
            "   START WITH baugruppe = '%s' AND b_index = '%s'"
            "   CONNECT BY NOCYCLE baugruppe = PRIOR teilenummer AND b_index = PRIOR t_index) e,"
            " teile_stamm a "
            "WHERE "
            "  a.teilenummer = e.teilenummer AND a.t_index = e.t_index "
            "ORDER BY"
            "  rownr"
        )
        query = QUERYSTR % (bom_from_item.teilenummer, bom_from_item.t_index)
        return sqlapi.RecordSet2(sql=query)

    def _get_component_structure_oracle(self, component):
        query = """
        SELECT c.*, e.combined_quantity, e.combined_parent,
         e.combined_id
        FROM
            (SELECT rownum rownr, level stufe, comp_object_id, parent_object_id,
             quantity AS combined_quantity, parent_object_id AS combined_parent,
             cdb_object_id as combined_id
             FROM cdbpco_comp2component
             START WITH parent_object_id = '{cdb_object_id}'
             CONNECT BY NOCYCLE parent_object_id = PRIOR comp_object_id) e,
             cdbpco_component_v c
        WHERE
            c.cdb_object_id = e.comp_object_id
        ORDER BY
            rownr""".format(cdb_object_id=component.cdb_object_id)
        return sqlapi.RecordSet2(table="cdbpco_component", sql=query)

    def _get_structure_mssql(self, bom_from_item):
        # Recursive CTE. The sortorder attribute is built along the way in
        # order to deliver the results in the right hierarchical order
        QUERYSTR = """
        WITH Hierarchical (baugruppe, b_index, teilenummer, t_index,
                           menge, t_kategorie, mengeneinheit,
                           material_object_id, cdb_object_id, stufe)
        AS (
            SELECT et.baugruppe, et.b_index, et.teilenummer, et.t_index,
                    et.menge, ts.t_kategorie, ts.mengeneinheit,
                    ts.material_object_id, ts.cdb_object_id, 1 as stufe
            FROM   einzelteile AS et
            INNER JOIN teile_stamm AS ts ON et.teilenummer = ts.teilenummer
                                        AND et.t_index = ts.t_index
            WHERE  et.baugruppe = '{teilenummer}' AND et.b_index = '{t_index}'
            UNION ALL
            SELECT et.baugruppe, et.b_index, et.teilenummer, et.t_index,
                    et.menge, ts.t_kategorie, ts.mengeneinheit,
                    ts.material_object_id, ts.cdb_object_id, stufe + 1
            FROM   einzelteile AS et
            INNER JOIN teile_stamm AS ts ON et.teilenummer = ts.teilenummer
                                         AND et.t_index = ts.t_index
            INNER JOIN Hierarchical AS h ON h.teilenummer = et.baugruppe
                                         AND h.t_index = et.b_index
            WHERE 1>0
        )
        SELECT * FROM Hierarchical
        """.format(teilenummer=bom_from_item.teilenummer,
                   t_index=bom_from_item.t_index)
        return sqlapi.RecordSet2(sql=QUERYSTR)

    def _get_component_structure_mssql(self, component):
        query = """
        WITH Hierarchical (comp_object_id, parent_object_id, stufe,
         combined_quantity, combined_parent, combined_id)
        AS (
            SELECT c.comp_object_id, c.parent_object_id, 1 AS stufe,
             c.quantity AS combined_quantity, c.parent_object_id AS combined_parent,
             c.cdb_object_id AS combined_id
            FROM cdbpco_comp2component AS c
            WHERE c.parent_object_id = '{cdb_object_id}'
            UNION ALL
            SELECT c.comp_object_id, c.parent_object_id, stufe + 1,
             c.quantity AS combined_quantity, c.parent_object_id AS combined_parent,
             c.cdb_object_id as combined_id
            FROM cdbpco_comp2component AS c
            INNER JOIN Hierarchical AS h ON h.comp_object_id = c.parent_object_id
        )
        SELECT c.*, h.combined_quantity, h.combined_parent, h.combined_id FROM Hierarchical AS h
        INNER JOIN cdbpco_component_v AS c ON c.cdb_object_id = h.comp_object_id
        """.format(cdb_object_id=component.cdb_object_id)
        return sqlapi.RecordSet2(table="cdbpco_component", sql=query)

    def _get_bom_components(self, item, curr_lev=1):
        """ Ermittlung Produktstruktur Hierarchieinformationen """
        result = []
        if item and item.isAssembly():
            for comp in item.Components:
                result.append((curr_lev, comp))
                if comp.Item.isAssembly():
                    result += self._get_bom_components(comp.Item,
                                                       curr_lev + 1)
        return result

    def _get_structure_components(self, comp, curr_lev=1):
        result = []
        for c in comp.Children:
            result.append((c.Component, c))
            if c.Children:
                result += self._get_structure_components(c,
                                                         curr_lev + 1)
        return result

    def _get_structure_other(self, bom_from_item):
        """ Return the hierarchical structure by iterating through the elements
        as instantiated objects in the Object Framework"""
        result = []
        for lev, obj in self._get_bom_components(bom_from_item):
            d = {}
            d["stufe"] = lev
            d["baugruppe"] = obj.baugruppe
            d["b_index"] = obj.b_index
            d["teilenummer"] = obj.teilenummer
            d["t_index"] = obj.t_index
            d["t_kategorie"] = obj.Item.t_kategorie
            d["menge"] = obj.menge
            d["mengeneinheit"] = obj.Item.mengeneinheit
            d["material_object_id"] = obj.Item.material_object_id
            d["cdb_object_id"] = obj.Item.cdb_object_id
            result.append(d)
        return result

    def _get_component_structure_other(self, component):
        result = []
        cc = Component2Component.KeywordQuery(comp_object_id=component.cdb_object_id,
                                              parent_object_id=component.parent_object_id)
        if cc:
            for obj in self._get_structure_components(cc[0]):
                result.append(obj)
            return result
        return []

    def select_creation_class(self, teilenummer, t_index):
        return PartComponent

    def add_components_from_bom(self, ctx=None, item=None):
        dbscript = {sqlapi.DBMS_ORACLE: self._get_structure_oracle,
                    sqlapi.DBMS_MSSQL: self._get_structure_mssql,
                    sqlapi.DBMS_SQLITE: self._get_structure_other}
        dbtype = sqlapi.SQLdbms()
        func = dbscript.get(dbtype, self._get_structure_other)
        if not ctx:
            bom_from_item = item
        else:
            bom_from_item = Item.ByKeys(ctx.dialog.teilenummer, ctx.dialog.t_index)
        result = func(bom_from_item=bom_from_item)
        params = {
            "material_object_id": bom_from_item.material_object_id,
            "mengeneinheit": bom_from_item.mengeneinheit,
            "cost_unit": bom_from_item.mengeneinheit,
            "teilenummer": bom_from_item.teilenummer,
            "t_index": bom_from_item.t_index,
            "quantity": 1.0,
            "part_object_id": bom_from_item.cdb_object_id,
            "curr_object_id": self.curr_object_id,
            "calc_object_id": self.cdb_object_id,
            "costplant_object_id": self.costplant_object_id,
            "parent_object_id": "",
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "mek": 0.0,
            "fek": 0.0
        }
        head = operations.operation("CDB_Create",
                                    self.select_creation_class(bom_from_item.teilenummer, bom_from_item.t_index),
                                    **params)
        components = []
        previous_level = 1

        masters = {}
        clones = []
        for r in result:
            stufe = int(r["stufe"])
            params = {
                "material_object_id": r["material_object_id"],
                "mengeneinheit": r["mengeneinheit"],
                "cost_unit": r["mengeneinheit"],
                "teilenummer": r["teilenummer"],
                "t_index": r["t_index"],
                "part_object_id": r["cdb_object_id"],
                "quantity": r["menge"],
                "curr_object_id": self.curr_object_id,
                "calc_object_id": self.cdb_object_id,
                "costplant_object_id": self.costplant_object_id,
                "parent_object_id": components[stufe - 2] if stufe != 1 else head.cdb_object_id,
                "subject_id": self.subject_id,
                "subject_type": self.subject_type,
                "mek": 0.0,
                "fek": 0.0
            }
            # Workaround for oracle

            if not r['teilenummer'] + '_' + r['t_index'] in masters:
                new_component = operations.operation("CDB_Create",
                                                     self.select_creation_class(r["teilenummer"], r["t_index"]),
                                                     **params)
                masters[r['teilenummer'] + '_' + r['t_index']] = new_component.cdb_object_id
                if stufe - 1 >= len(components) and previous_level != stufe - 1:
                    components.append(new_component.cdb_object_id)
                else:
                    components[stufe - 1] = new_component.cdb_object_id
                previous_level = stufe - 1
            elif params["parent_object_id"] not in clones:
                clones.append(masters[r['teilenummer'] + '_' + r['t_index']])
                Component2Component.Create(parent_object_id=params["parent_object_id"],
                                        comp_object_id=masters[r['teilenummer'] + '_' + r['t_index']],
                                        calc_object_id=self.cdb_object_id,
                                        cloned=1,
                                        quantity=r["menge"])
                if stufe - 1 >= len(components) and previous_level != stufe - 1:
                    components.append(masters[r['teilenummer'] + '_' + r['t_index']])
                else:
                    components[stufe - 1] = masters[r['teilenummer'] + '_' + r['t_index']]
                previous_level = stufe - 1
            else:
                clones.append(masters[r['teilenummer'] + '_' + r['t_index']])
            if clones:
                Component.KeywordQuery(cdb_object_id=clones).Update(cloned=1)

                Component2Component.KeywordQuery(cdb_object_id=clones, calc_object_id=self.cdb_object_id).Update(cloned=1)

    def import_component_part(self, ctx=None, item=None):

        dbscript = {sqlapi.DBMS_ORACLE: self._get_structure_oracle,
                    sqlapi.DBMS_MSSQL: self._get_structure_mssql,
                    sqlapi.DBMS_SQLITE: self._get_structure_other}
        dbtype = sqlapi.SQLdbms()
        func = dbscript.get(dbtype, self._get_structure_other)
        if not ctx:
            bom_from_item = item
        else:
            bom_from_item = Item.ByKeys(ctx.dialog.teilenummer, ctx.dialog.t_index)
        result = func(bom_from_item=bom_from_item)

        params = {
            "material_object_id": bom_from_item.material_object_id,
            "mengeneinheit": bom_from_item.mengeneinheit,
            "cost_unit": bom_from_item.mengeneinheit,
            "teilenummer": bom_from_item.teilenummer,
            "t_index": bom_from_item.t_index,
            "quantity": 1.0,
            "part_object_id": bom_from_item.cdb_object_id,
            "curr_object_id": self.curr_object_id,
            "calc_object_id": self.cdb_object_id,
            "costplant_object_id": self.costplant_object_id,
            "parent_object_id": "",
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "mek": 0.0,
            "fek": 0.0
        }
        head = operations.operation("CDB_Create",
                                    self.select_creation_class(bom_from_item.teilenummer, bom_from_item.t_index),
                                    **params)

    def open_in_browser(self, ctx):
        ctx.url("/info/calculation/%s" % self.cdb_object_id, view_extern=1, icon="")

    def delegate_calculation(self, ctx):
        self.subject_id = ctx.dialog.subject_id
        self.subject_type = ctx.dialog.subject_type

    def add_selective_components_from_bom(self, ctx):
        if "react" in ctx.dialog.get_attribute_names() and ctx.dialog.react:
            boms = json.loads(ctx.dialog.react)
            masters = {}
            clones = []
            oid_map = {}
            for bom in boms:
                del bom["description"]
                del bom["icon"]
                del bom["level"]
                bom["cdb_object_id"] = cdbuuid.create_uuid()
                oid_map[bom["part_object_id"]] = bom["cdb_object_id"]

                if bom["parent_object_id"]:
                    bom["parent_object_id"] = oid_map[bom["parent_object_id"]]

                if bom['teilenummer'] + '_' + bom['t_index'] not in masters:
                    bom["mek"] = 0.0
                    bom["fek"] = 0.0
                    new_component = operations.operation("CDB_Create", self.select_creation_class(bom['teilenummer'], bom['t_index']), **bom)
                    masters[bom['teilenummer'] + '_' + bom['t_index']] = new_component.cdb_object_id

                elif bom["parent_object_id"] not in clones:
                    clones.append(masters[bom['teilenummer'] + '_' + bom['t_index']])
                    Component2Component.Create(parent_object_id=bom["parent_object_id"],
                                            comp_object_id=masters[bom['teilenummer'] + '_' + bom['t_index']],
                                            calc_object_id=bom["calc_object_id"],
                                            cloned=1,
                                            quantity=bom["quantity"])
                else:
                    clones.append(masters[bom['teilenummer'] + '_' + bom['t_index']])
                if clones:
                    Component.KeywordQuery(cdb_object_id=clones).Update(cloned=1)
                    Component2Component.KeywordQuery(cdb_object_id=clones, calc_object_id=bom["calc_object_id"]).Update(
                        cloned=1)

    def get_components_from_structure(self, component):
        dbscript = {sqlapi.DBMS_ORACLE: self._get_component_structure_oracle,
                    sqlapi.DBMS_MSSQL: self._get_component_structure_mssql,
                    sqlapi.DBMS_SQLITE: self._get_component_structure_other}
        dbtype = sqlapi.SQLdbms()
        func = dbscript.get(dbtype, self._get_component_structure_other)
        return func(component=component)

    def update_currencies(self, ctx):
        old_object = Calculation.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        if old_object.schema_object_id != self.schema_object_id:
            old_curr = {c.name: c.cdb_object_id for c in Currency.KeywordQuery(schema_object_id=old_object.schema_object_id)}
            new_curr = {old_curr[nc.name]: nc.cdb_object_id for nc in Currency.KeywordQuery(schema_object_id=self.schema_object_id)}
            for curr in new_curr.keys():
                self.Components.KeywordQuery(curr_object_id=curr).Update(curr_object_id=new_curr[curr])
                ParameterValue.KeywordQuery(curr_object_id=curr,
                                            context_object_id=self.Components.cdb_object_id).Update(curr_object_id=new_curr[curr])

    # ======= OLC =======
    class NEW(State):
        status = 0

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(Calculation.OBSOLETE.status)
            super(Calculation.NEW, state).pre_mask(self, ctx)

    class COMPLETED(State):
        status = 250

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(Calculation.OBSOLETE.status)
            super(Calculation.COMPLETED, state).pre_mask(self, ctx)

    class DISCARDED(State):
        status = 180

        def post(state, self, ctx):  # @NoSelf
            self.cdb_obsolete = 1

    class OBSOLETE(State):
        status = 190

        def pre_mask(state, self, ctx):  # @NoSelf
            if not ctx.batch:
                ctx.excl_state(Calculation.NEW.status)
            super(Calculation.OBSOLETE, state).pre_mask(self, ctx)

        def post(state, self, ctx):  # @NoSelf
            self.cdb_obsolete = 1

    @classmethod
    def set_revision_search_pattern(cls):
        search_with = []
        constraints = DDConstraintField.KeywordQuery(classname=cls.__classname__)
        for c in constraints:
            if c.field_name in ["cdb_object_id", "c_index"]:
                continue
            search_with.append(c.field_name)
        return {"orderby": "c_index",
                "search_with": search_with}


class CalculationStatiProt(Object):
    """
    Status change protocols of calculations.
    """
    __maps_to__ = "cdbpco_calculation_statiprot"
    __classname__ = "cdbpco_calculation_statiprot"
