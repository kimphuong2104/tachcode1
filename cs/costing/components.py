#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
import six

"""
The Product Costing Component classes.
"""
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import datetime
from cdb import auth
from cdb import ue
from cdb import sqlapi
from cdb import cdbtime
from cdb import cdbuuid
from cdb import sig
from cdb import constants
from cdb import transaction
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_N
from cdb.objects import Forward
from cdb.objects import operations
from cdb.objects.cdb_file import FILE_EVENT
from cdb.fls import allocate_license
from cdb.sig import connect
from cs.currency import Currency
from cs.workflow import briefcases
from cs.vp.bom import AssemblyComponent
from cs.documents import Document
from cs.audittrail import WithAuditTrail
from cs.currency import CurrConversion
from cs.costing.parameters import ResultValue
from cs.costing.parameters import ParameterValue
from cs.costing.parameters import parameter_cache
from cs.costing.parameters import init_parameter_cache
from cs.costing.schemes import WithCalculationSchema
from cs.costing.volume_curve import VolumeCurve
from cs.costing.volume_curve import VolumeCurveEntry

rac__all__ = ["ComponentFolder", "ComponentFolder2Component", "Delivery",
              "Product", "Component", "PartComponent", "StepComponent", "Component2Component",
              "Product2Delivery", "Component2Product"]

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
fComponent2Delivery = Forward("cs.costing.components.Component2Delivery")

COMPONENT_COPY_SIGNAL = sig.signal()


def check_drag_drop_allowed(drag_obj, drop_obj):
    """
    Check the calculation id of the drag and the drop object. The Drag&Drop
    operation only works if the objects belong to the same Calculation object.
    """
    if drag_obj.calc_object_id != drop_obj.calc_object_id:
        raise ue.Exception("cdbpco_calc_context")


class Component(Object, WithCalculationSchema, briefcases.BriefcaseContent, WithAuditTrail):
    """
    A Product consists of Component(s).
    If there is no Delivery and no Product, a Calculation can
    contain one Component or different Components.
    A Component must be assigned to a Calculation, but needs not necessarily to
    be assigned to a Products.
    """

    __maps_to__ = "cdbpco_component"
    __classname__ = "cdbpco_component"

    Calculation = Reference_1(fCalculation,
                              fComponent.calc_object_id)

    Item = Reference_1(fItem,
                       fComponent.teilenummer,
                       fComponent.t_index)

    ProductAssignments = Reference_N(
        fComponent2Product,
        fComponent2Product.comp_object_id == fComponent.cdb_object_id)

    ParameterValues = Reference_N(
        fParameterValue,
        fParameterValue.context_object_id == fComponent.cdb_object_id)

    ResultValues = Reference_N(
        fResultValue,
        fResultValue.context_object_id == fComponent.cdb_object_id)

    FolderAssignments = Reference_N(
        fComponentFolder2Component,
        fComponentFolder2Component.component_object_id == fComponent.cdb_object_id)

    Files = Reference_N(fFile, fFile.cdbf_object_id == fComponent.cdb_object_id)

    CalculatedPartCosts = Reference_N(
        fPartCost,
        fPartCost.source_component_object_id == fComponent.cdb_object_id)

    Parent = Reference_1(
        fComponent,
        fComponent.parent_object_id)

    # Children: direct refs only, no clones
    Children = Reference_N(
        fComponent,
        fComponent.parent_object_id == fComponent.cdb_object_id
    )

    def _get_all_children(self):
        clone_refs = Component2Component.KeywordQuery(
            parent_object_id=self.cdb_object_id,
        )
        return [clone_ref.Component for clone_ref in clone_refs]

    # AllChildren: refs via comp2comp, which include both direct refs + clones
    AllChildren = ReferenceMethods_N(fComponent, _get_all_children)

    VolumeCurve = Reference_1(fVolumeCurve,
                              fComponent.cdb_object_id)
    event_map = {
        ('modify', 'pre_mask'): 'reset_modify_mask',
        ('modify', 'post'): ('modify_link_to_parent', 'check_excel_filename'),
        (('create', 'copy', 'modify'), 'dialogitem_change'): 'handle_dialog_item_change',
        (('info', 'copy', 'modify'), 'pre_mask'): 'showPartCostFields',
        (('copy', 'modify'), 'pre_mask'): 'disable_cost_fields',
        ('copy', 'pre_mask'): 'preset_parent',
        (('create', 'copy'), 'pre'): 'set_position',
        ('create', 'post'): ('copyExcelTemplate', 'prepareVariants', 'create_default_parameters',
                             'createCloneEntry', 'create_volume_curve', 'rearrange_child_component'),
        ('copy', 'pre'): 'preset_clone',
        ('copy', 'post'): ('prepareVariants', 'copy_parameters', 'copy_results', 'copy_volume_curve',
                           'copy_structure'),
        (('create', 'copy'), 'pre_mask'): ('dragndrop', 'set_defaults', 'set_read_only'),
        ('create', 'pre'): ('set_quantity', 'fill_in_name'),
        ('create', 'pre_mask'): 'select_insert_type',
        ('cdbpco_clone_component', 'pre_mask'): 'clone_component_mask',
        ('cdbpco_clone_component', 'now'): 'clone_component',
        ('cdbpco_delegate', 'now'): 'delegate_component',
        ('cdbpco_delete', 'now'): 'delete_original_clone',
        ('cdbpco_delete', 'post'): 'deleteAuditTrailEntry',
        ('cdbpco_calculate_comp_result', 'now'): 'calculate_comp_result'
    }

    def set_defaults(self, ctx):
        self.subject_type = "Person"
        self.subject_id = auth.persno
        if ctx.dialog and "insert_type" not in ctx.dialog.get_attribute_names():
            if ctx.action == "create" and self.Parent:
                self.cloned = self.Parent.cloned
            else:
                self.cloned = 0
        if ctx.action == "create":
            self.quantity = 1.0

    def set_read_only(self, ctx):
        read_only_fields = ["combined_quantity"]
        for f in read_only_fields:
            ctx.set_readonly(f)

    def dragndrop(self, ctx):
        if ctx.dragged_obj:
            self.ml_name_en, self.name = self.name_generator(ctx)
            ctx.set("name", self.name)
            ctx.set("ml_name_en", self.ml_name_en)

    def fill_in_name(self, ctx):
        if not (self.name or self.ml_name_en):
            self.ml_name_en, self.name = self.name_generator(ctx)

    def set_quantity(self, ctx):
        if ctx and "combined_quantity" in ctx.dialog.get_attribute_names():
            self.quantity = float(ctx.dialog.combined_quantity) if ctx.dialog.combined_quantity else 1.0

    def on_preview_now(self, ctx):
        if self.Item:
            self.Item.on_preview_now(ctx)
        else:
            self.Super(Component).on_preview_now(ctx)

    def set_position(self, ctx):
        # set the folder position to next possible value
        pos = 0
        maxposrec = sqlapi.RecordSet2(sql="select max(order_no) maxpos " +
                                         "from %s " % self.GetTableName() +
                                         "where calc_object_id='%s'" %
                                         self.calc_object_id)
        try:
            pos = int(maxposrec[0].maxpos) + 1
        except Exception:
            pass
        self.order_no = pos

    def create_volume_curve(self, ctx):
        if self.parent_object_id and self.Parent.VolumeCurve:
            newvc = self.Parent.VolumeCurve.Copy(object_object_id=self.cdb_object_id,
                                                 primary_volume_curve=0)
        else:
            VolumeCurve.Create(object_object_id=self.cdb_object_id,
                               calc_object_id=self.calc_object_id,
                               volume_curve_object_id=cdbuuid.create_uuid(),
                               primary_volume_curve=1)

    def reset_modify_mask(self, ctx):
        # can not be assigned to other Calculation
        ctx.set_readonly("calc_object_id")
        for p in self.ParameterValues:
            if p.para_code in ["DMANC", "DMATC"] and self.Children:
                ctx.set(p.para_code, "%s:'':1" % p.value)
            else:
                ctx.set(p.para_code, "%s" % p.value)
        for r in self.ResultValues:
            value = r.value
            if not self.Children and r.entered_value:
                value = r.entered_value
            if r.para_code in ["DMANC", "DMATC"] and self.Children:
                ctx.set(r.para_code, "%s:%s:1" % (value,
                                                  r.cdb_object_id))
            else:
                ctx.set(r.para_code, "%s:%s" % (value,
                                                r.cdb_object_id))

    def modify_link_to_parent(self, ctx):
        if self.parent_object_id and ctx.previous_values.parent_object_id != self.parent_object_id:
            ccs = Component2Component.KeywordQuery(comp_object_id=self.cdb_object_id,
                                                   calc_object_id=self.calc_object_id,
                                                   parent_object_id=ctx.previous_values.parent_object_id
                                                   )
            if ccs:
                ccs.Update(parent_object_id=self.parent_object_id)
            self.VolumeCurve.Update(volume_curve_object_id=self.Parent.VolumeCurve.volume_curve_object_id)
        if self.parent_object_id and self.Parent and self.Parent.cloned and not self.cloned:
            Component.ByKeys(self.cdb_object_id).Update(cloned=1)
        if self.Children and self.cloned:
            structure = self.Calculation.get_components_from_structure(self)
            for c in structure:
                if type(c) == tuple:
                    component = c[0]
                else:
                    component = c
                if component:
                    sqlapi.SQLupdate("cdbpco_component set cloned=1 where cdb_object_id='%s'" % component.cdb_object_id)

    def check_excel_filename(self, ctx):
        for f in self.Files:
            if f.isPrimary() and f.cdbf_type.startswith("MS-Excel") and f.cdbf_name != f.generate_name():
                f.Update(cdbf_name=f.generate_name())

    def copy_to(self, newcalc, newobj_dict=None):
        """
        Copy the current object to a new Calculation.
        :Parameters:
            - `newcalc` : the new Calculation object which the current object
                          should be copy to
            - `newobj_dict` : to remember which object is copied from current
                              object. It can be used later to generate the
                              relationships etc.
        """
        newdata = {"calc_object_id": newcalc.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid(),
                   "template_object_id": self.cdb_object_id,
                   "parent_object_id": newobj_dict[self.parent_object_id] if self.parent_object_id else ""}
        newdata.update(self.MakeChangeControlAttributes())
        newobj = self.Copy(**newdata)
        newobj_dict[self.cdb_object_id] = newobj.cdb_object_id
        # also copy the Product->Component relationships
        # the product object can be found via newobj_dict
        for prod_asgn in self.ProductAssignments:
            prod_asgn.copy_to(newobj, newobj_dict)
        for folder_asgn in self.FolderAssignments:
            folder_asgn.copy_to(newobj, newobj_dict)
        if self.Files:
            foundExcel = False
            for f in self.Files:
                if f.cdbf_type.startswith("MS-Excel"):
                    newfile = f.Copy(cdbf_object_id=newobj.cdb_object_id,
                                     cdbf_name="calc_template")
                    newfile.cdbf_name = newfile.generate_name()
                    foundExcel = True
                else:
                    newfile = f.Copy(cdbf_object_id=newobj.cdb_object_id)
            if not foundExcel:
                newobj.copyExcelTemplate()
        else:
            newobj.copyExcelTemplate()
        self.copy_parameters_to(newobj)
        self.copy_results_to(newobj)
        self.copy_volume_curve_to(newobj, newobj_dict)
        return newobj

    @classmethod
    def getPartCost(cls, calculation, teilenummer, t_index):
        """
        Get the cost data of the given part.
        """
        if teilenummer:
            costplant_object_id = calculation.costplant_object_id
            today = sqlapi.SQLdbms_date(datetime.date.today())
            # generate the query condition
            qstr = "teilenummer = '%s' and t_index = '%s'" % \
                        (teilenummer, t_index)
            qstr += " and costplant_object_id = '%s'" % costplant_object_id
            qstr += " and valid_from <= %s and valid_until >= %s" % (today,
                                                                     today)
            costs = PartCost.Query(qstr)
            if costs:
                return costs[0]
        return None

    @classmethod
    def getDefaultCosts(cls, ctx, calculation, teilenummer, t_index):
        """
        Get default value of costs for the component.
        """
        # default mek(direct material costs) and
        # fek(direct manufacturing costs): 0.0
        result = {}
        part_cost = None
        result["mek"] = 0.0
        result["fek"] = 0.0
        if teilenummer and calculation:
            # has part and Calculation assignments
            # part changed or new part assigned, take the values of item
            # costs and name for current Component
            part_cost = cls.getPartCost(calculation, teilenummer, t_index)
            if part_cost:
                result["mek"] = part_cost.mek
                result["fek"] = part_cost.fek
                result["cost_unit"] = part_cost.cost_unit
                result["curr_object_id"] = part_cost.curr_object_id
            item = fItem.ByKeys(teilenummer, t_index)
            result["name"] = item.ToObjectHandle().getDesignation(
                msg_label="cs_costing_component_name_from_part")
            result["part_mengeneinheit"] = item.mengeneinheit
            result["mengeneinheit"] = item.mengeneinheit
            result["material_object_id"] = item.material_object_id
            result["technology_id"] = item.technology_id
        if ("cost_unit" not in result or not result["cost_unit"]) and \
            "part_mengeneinheit" in result:
            result["cost_unit"] = result["part_mengeneinheit"]
        if "curr_object_id" not in result or not result["curr_object_id"]:
            result["curr_object_id"] = calculation.curr_object_id
        return result, part_cost

    def _preset_costs(self, ctx, teilenummer, t_index):
        """
        Preset the data on the dialog.
        """
        # set component fields
        preset, part_cost = self.getDefaultCosts(
            ctx, self.Calculation, teilenummer, t_index)
        for (k, v) in list(six.iteritems(preset)):
            ctx.set(k, v)
        # show cost fields for the part on the dialog
        self._showPartCostFields(ctx, part_cost)
        self.disable_cost_fields(ctx,
                                 no_acc_check=True)

    def disable_cost_fields(self, ctx, no_acc_check=False):
        """
        Check whether the costs can be modified interactively
        """
        mod_allowed = True
        if not no_acc_check:
            # check whether the current object can be modified, to
            # skip set_writeable for readonly objects.
            mod_allowed = self.CheckAccess("save")
        # item assigned:
        # quantity unit not editable
        if self.Item:
            ctx.set_fields_readonly(["mengeneinheit", "mengeneinheit_name"])
        elif mod_allowed:
            ctx.set_fields_writeable(["mengeneinheit", "mengeneinheit_name"])

    def preset_parent(self, ctx):
        if ctx and "parent" in ctx.dialog.get_attribute_names():
            ctx.set("parent_object_id", ctx.dialog.parent)
        ctx.set_readonly("volume_curve")

    def showPartCostFields(self, ctx):
        part_cost = self.getPartCost(
            self.Calculation, self.teilenummer, self.t_index)
        self._showPartCostFields(ctx, part_cost)

    def _showPartCostFields(self, ctx, part_cost=None):
        if not part_cost:
            ctx.set("part_mek", "")
            ctx.set("part_fek", "")
            ctx.set("part_cost_unit", "")
            ctx.set("part_mengeneinheit", "")
            ctx.set("part_curr_object_id", "")
        else:
            ctx.set("part_mek", part_cost.mek)
            ctx.set("part_fek", part_cost.fek)
            ctx.set("part_cost_unit", part_cost.cost_unit)
            ctx.set("part_cost_unit_name", part_cost.cost_unit_name)
            ctx.set("part_curr_object_id", part_cost.curr_object_id)

    def handle_dialog_item_change(self, ctx):
        if ctx.changed_item == "teilenummer":
            self._preset_costs(ctx, self.teilenummer, self.t_index)
            self.ml_name_en, self.name = self.name_generator(ctx)
            ctx.set("name", self.name)
            ctx.set("ml_name_en", self.ml_name_en)
        if ctx.action == "modify" and ctx.changed_item == "curr_name" and not self.Children:
            c = Component.ByKeys(ctx.dialog.cdb_object_id)
            mek_split = ctx.dialog.dmatc.split(":")
            fek_split = ctx.dialog.dmanc.split(":")
            mek = float(mek_split[0])
            fek = float(fek_split[0])

            if c.curr_object_id != ctx.dialog.curr_object_id:
                exch = CurrConversion.getCurrExchangeFactor(c.curr_object_id,
                                                  ctx.dialog.curr_object_id,
                                                  c.cdb_project_id)
                mek = mek * exch
                fek = fek * exch
            ctx.set("dmatc", round(mek, 2))
            ctx.set("dmanc", round(fek, 2))

    def on_create_pre_mask(self, ctx):
        # if the creation is done in the context of a folder, preset calc_object_id from folder
        if ctx.relationship_name == "cdbpco_cfolder2comp":
            if ctx.parent:
                cf = ComponentFolder.ByKeys(ctx.parent.cdb_object_id)
                if cf:
                    self.calc_object_id = cf.calc_object_id
        if ctx.relationship_name == "cdbpco_component2children":
            if ctx.parent:
                p = Component.ByKeys(ctx.parent.cdb_object_id)
                if p:
                    self.calc_object_id = p.calc_object_id
        if not self.costplant_object_id and self.Calculation:
            ctx.set("costplant_object_id", self.Calculation.costplant_object_id)
        if not self.curr_object_id and self.Calculation:
            ctx.set("curr_object_id", self.Calculation.curr_object_id)
        if not self.cost_unit:
            ctx.set("cost_unit", "Stk")
        if not self.mengeneinheit:
            ctx.set("mengeneinheit", "Stk")
        if ctx.dragged_obj:
            self._preset_costs(ctx,
                               ctx.dragged_obj.teilenummer,
                               ctx.dragged_obj.t_index)

    @classmethod
    def get_own_parameter_values(cls, record=None, classname=None, calculation=None,
                                    ctx=None, exch_factor=None):
        """
        Get parameter values from current object. (Overwrite the default
        method in `WithCalculationSchema`.)
        """
        if exch_factor is None:
            exch_factor = {}
        result = super(Component, cls).get_own_parameter_values(ctx)
        return result

    @classmethod
    def should_use_formula_for_result(cls, classname, rdef, ctx=None):
        # Components results are always calculated using formula
        return True

    def delete_calculation_object(self, ctx):
        """
        Delete or clean up the related objects of current object.
        Will be called by deleting the (parent) Calculation object.
        """
        self.cdbpco_delete(ctx)
        self.Delete()

    def update_costs(self):
        """
        Update the component cost using values from assigned part.
        """
        part_cost = self.getPartCost(
            self.Calculation, self.teilenummer, self.t_index)
        if not part_cost:
            return
        init_parameter_cache()
        mek = 0
        fek = 0
        if self.cdb_classname in parameter_cache[self.Calculation.schema_object_id]:
            class_cache = parameter_cache[self.Calculation.schema_object_id][self.cdb_classname][
                "parameters"]
        else:
            class_cache = parameter_cache[self.Calculation.schema_object_id][""]["parameters"]
        if not "DMATC" in class_cache:
            return
        if not "DMANC" in class_cache:
            return
        mek_rv = ResultValue.KeywordQuery(context_object_id=self.cdb_object_id,
                                          rdef_object_id=class_cache["DMATC"].cdb_object_id)
        if mek_rv:
            mek = mek_rv[0].value
        fek_rv = ResultValue.KeywordQuery(context_object_id=self.cdb_object_id,
                                          rdef_object_id=class_cache["DMANC"].cdb_object_id)
        if fek_rv:
            fek = fek_rv[0].value
        if part_cost.curr_object_id != self.curr_object_id or \
           part_cost.mek != mek or \
           part_cost.fek != fek or \
           part_cost.cost_unit != self.cost_unit or \
           part_cost.Item.mengeneinheit != self.mengeneinheit:
            # only save the values if changed
            self.curr_object_id = part_cost.curr_object_id
            self.cost_unit = part_cost.cost_unit
            self.mengeneinheit = part_cost.Item.mengeneinheit
            ParameterValue.KeywordQuery(context_object_id=self.cdb_object_id,
                                        pdef_object_id=class_cache["DMATC"].cdb_object_id).Update(
                value=part_cost.mek)
            if mek_rv:
                mek_rv.Update(value=part_cost.mek,
                              entered_value=part_cost.mek)

            else:
                ResultValue.Create(calc_object_id=self.calc_object_id,
                                   context_object_id=self.cdb_object_id,
                                   rdef_object_id=class_cache["DMATC"].cdb_object_id,
                                   value=part_cost.mek,
                                   entered_value=part_cost.mek)
            ParameterValue.KeywordQuery(context_object_id=self.cdb_object_id,
                                        pdef_object_id=class_cache["DMANC"].cdb_object_id).Update(
                value=part_cost.fek)
            if fek_rv:
                fek_rv.Update(value=part_cost.fek,
                              entered_value=part_cost.fek)
            else:
                ResultValue.Create(calc_object_id=self.calc_object_id,
                                   context_object_id=self.cdb_object_id,
                                   rdef_object_id=class_cache["DMANC"].cdb_object_id,
                                   value=part_cost.fek,
                                   entered_value=part_cost.fek)

    @classmethod
    def on_cdbpco_comp_cost_upd_now(cls, ctx):
        # operation event handler
        for comp in cls.PersistentObjectsFromContext(ctx):
            if comp.Children:
                raise ue.Exception("cdbpco_has_children")
            comp.update_costs()

    def cdbpco_delete(self, ctx=None):
        """
        Delete related objects.
        """
        self.ProductAssignments.Delete()
        self.ParameterValues.Delete()
        self.ResultValues.Delete()
        self.FolderAssignments.Delete()
        self.CalculatedPartCosts.Update(source_component_object_id="")
        if self.VolumeCurve:
            self.VolumeCurve.Delete()
        entries = VolumeCurveEntry.KeywordQuery(primary_component_object_id=self.cdb_object_id)
        if entries:
            entries.Delete()
        if not self.Parent or self.cloned == 0:
            cc = Component2Component.KeywordQuery(parent_object_id="" if not self.Parent else self.parent_object_id,
                                                  comp_object_id=self.cdb_object_id,
                                                  calc_object_id=self.calc_object_id)
            if cc:
                cc.Delete()
        self.deleteAuditTrailEntry(ctx)

    def on_cdbpco_set_pos_now(self, ctx):
        """
        Operation event handler to reset the position of a component -
        move it up or down.
        """
        # show a list of objects to be selected:
        # the current object will be moved to the next position of the selected
        # one
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdbpco_component_br2",
                                calc_object_id=self.calc_object_id)
        else:
            cdb_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            # find out the selected object
            targetobj = Component.ByKeys(cdb_object_id)
            if targetobj:
                mypos = self.order_no
                targetpos = targetobj.order_no
                if mypos != targetpos + 1:
                    # current object is not next to the selected one: will be
                    # moved there
                    # CAUTION: not only the current object will be moved -
                    # but also the intermediate objects
                    # posstep: moving direction, 1=afterwards(downwards),
                    # -1=forwards(upwards)
                    posstep = 1
                    # the "should be"-position for current object
                    newpos = targetpos + 1
                    cond = "order_no>%i and order_no<%i" % (targetpos, mypos)
                    if mypos < targetpos:
                        # current object is in front of the target position, so
                        # move the objects behind it forwards
                        cond = "order_no<=%i and order_no>%i" % (targetpos,
                                                                 mypos)
                        posstep = -1
                        newpos = targetpos
                    # find out which objects should be moved
                    moveobjs = Component.Query(
                                    "calc_object_id='%s' and %s" %
                                    (self.calc_object_id, cond))
                    for moveobj in moveobjs:
                        moveobj.order_no = moveobj.order_no + posstep
                    self.order_no = newpos

    def prepareVariants(self, ctx=None):
        products = self.Calculation.Products.Query(
            "cdb_object_id not in "
            "(select product_object_id from %s where comp_object_id='%s')" % (
                Component2Product.GetTableName(), self.cdb_object_id
            ))
        Component2Product.prepareVariants(
            self.Calculation, components=[self], products=products)

    def preset_clone(self, ctx=None):
        if self.Parent:
            self.cloned = self.Parent.cloned

    def copyExcelTemplate(self, ctx=None):
        if self.Calculation and self.Calculation.doc_object_id:
            doc = Document.KeywordQuery(cdb_object_id=self.Calculation.doc_object_id)
            if doc:
                for f in doc[0].PrimaryFiles:
                    newfile = f.Copy(cdbf_object_id=self.cdb_object_id)
                    newfile.cdbf_name = newfile.generate_name()

    @classmethod
    def genComponentFromBOM(cls, teilenummer, t_index, product, amount):
        calc_object_id = product.calc_object_id
        calculation = product.Calculation
        components = cls.KeywordQuery(calc_object_id=calc_object_id,
                                      teilenummer=teilenummer,
                                      t_index=t_index)
        if len(components) > 0:
            component = components[0]
        else:
            preset, part_cost = cls.getDefaultCosts(
                None, calculation, teilenummer, t_index)
            if "costplant_object_id" not in preset or not preset["costplant_object_id"]:
                preset["costplant_object_id"] = calculation.costplant_object_id
            component = operations.operation(
                constants.kOperationNew,
                cls,
                calc_object_id=calc_object_id,
                teilenummer=teilenummer,
                t_index=t_index,
                **preset
            )
        if component:
            asgn = component.ProductAssignments.KeywordQuery(
                product_object_id=product.cdb_object_id)
            if len(asgn) > 0:
                asgn[0].Update(amount=amount)
            else:
                Component2Product.prepareVariants(calculation,
                                                  products=[product],
                                                  components=[component],
                                                  amount=amount)

    def updateParameterValue(self, code, value):
        # API for Office Link
        # Update existing value or create one
        if not code:
            return
        _code = code.upper()
        pdef = self.Calculation.CalculationSchema.ParameterDefinitions.KeywordQuery(
            code=_code)
        if not len(pdef):
            return
        pval = self.ParameterValues.KeywordQuery(pdef_object_id=pdef[0].cdb_object_id)
        if len(pval):
            pval.Update(value=value)
        else:
            ParameterValue.createForContextObject(
                pdef[0], context_object_id=self.cdb_object_id, value=value)

    def getResultValue(self, code):
        # API for Office Link
        # Get result for code
        if code:
            _code = code.upper()
            rdef = self.Calculation.CalculationSchema.ResultDefinitions.KeywordQuery(
                code=_code)
            if len(rdef):
                rval = self.ResultValues.KeywordQuery(rdef_object_id=rdef[0].cdb_object_id)
                if len(rval):
                    return rval[0].value
        return 0

    def fileUpdate(self, the_file, ctx=None):
        if the_file.isPrimary() and the_file.cdbf_type.startswith("MS-Excel"):
            self.Update(cdb_m2date=the_file.cdb_mdate, cdb_m2persno=the_file.cdb_mpersno)

    @classmethod
    def on_cdbpco_comp_cost_to_part_now(cls, ctx):
        # operation event handler
        for comp in cls.PersistentObjectsFromContext(ctx):
            comp.transfer_cost_to_part()

    def transfer_cost_to_part(self):
        """
        Transfer the cost data to the given part.
        """
        if not self.Item:
            return
        init_parameter_cache()
        part_cost = self.getPartCost(
            self.Calculation, self.teilenummer, self.t_index)
        mek = 0
        fek = 0

        if self.cdb_classname in parameter_cache[self.Calculation.schema_object_id]:
            class_cache = parameter_cache[self.Calculation.schema_object_id][self.cdb_classname]["parameters"]
        else:
            class_cache = parameter_cache[self.Calculation.schema_object_id][""]["parameters"]
        if "DMATC" in class_cache:
            mek_rv = ResultValue.KeywordQuery(calc_object_id=self.calc_object_id,
                                              context_object_id=self.cdb_object_id,
                                              rdef_object_id=class_cache["DMATC"].cdb_object_id)
            if mek_rv:
                mek = mek_rv[0].value
        if "DMANC" in class_cache:
            fek_rv = ResultValue.KeywordQuery(calc_object_id=self.calc_object_id,
                                              context_object_id=self.cdb_object_id,
                                              rdef_object_id=class_cache["DMANC"].cdb_object_id)
            if fek_rv:
                fek = fek_rv[0].value
        if part_cost:
            if part_cost.curr_object_id == self.curr_object_id and \
               part_cost.mek == mek and \
               part_cost.fek == fek and \
               part_cost.cost_unit == self.cost_unit and \
               part_cost.Item.mengeneinheit == self.mengeneinheit:
                # no diferences
                return
        params = dict(teilenummer=self.teilenummer,
                      t_index=self.t_index,
                      costplant_object_id=self.costplant_object_id,
                      curr_object_id=self.curr_object_id,
                      cost_unit=self.cost_unit,
                      mek=mek,
                      fek=fek,
                      source_component_object_id=self.cdb_object_id)
        PartCost.createPartCost(**params)

    def copy_parameters_to(self, target):
        if self.Calculation.schema_object_id == target.Calculation.schema_object_id and\
           self.costplant_object_id == target.costplant_object_id and \
           self.Calculation.para_year == target.Calculation.para_year and \
           self.material_object_id == target.material_object_id and \
           self.technology_id == target.technology_id:
            ParameterValue.copy_parameters_to(self, target)

    def copy_results_to(self, target):
        ResultValue.copyResultTo(self, target)

    def copy_volume_curve_to(self, target, newobj_dict={}):
        if self.VolumeCurve:
            if self.calc_object_id != target.calc_object_id:
                if self.VolumeCurve.primary_volume_curve and self.VolumeCurve.Entries:
                    newvc = self.VolumeCurve.Copy(volume_curve_object_id=target.cdb_object_id,
                                                  object_object_id=target.cdb_object_id,
                                                  calc_object_id=target.calc_object_id)
                    for entry in self.VolumeCurve.Entries:
                        entry.Copy(volume_curve_object_id=newvc.volume_curve_object_id,
                                   calc_object_id=newvc.calc_object_id,
                                   primary_component_object_id=target.cdb_object_id)
                        newobj_dict[entry.volume_curve_object_id] = newvc.volume_curve_object_id
                elif self.VolumeCurve.volume_curve_object_id in newobj_dict:
                    self.VolumeCurve.Copy(volume_curve_object_id=newobj_dict[self.VolumeCurve.volume_curve_object_id],
                                          object_object_id=target.cdb_object_id,
                                          calc_object_id=target.calc_object_id)
                else:
                    if target.parent_object_id:
                        target.Parent.VolumeCurve.Copy(
                            volume_curve_object_id=target.Parent.VolumeCurve.volume_curve_object_id,
                            object_object_id=target.cdb_object_id,
                            calc_object_id=target.calc_object_id)
                    else:
                        VolumeCurve.Create(object_object_id=target.cdb_object_id,
                                           calc_object_id=target.calc_object_id,
                                           volume_curve_object_id=cdbuuid.create_uuid(),
                                           primary_volume_curve=1)

            else:
                if not target.parent_object_id:
                    newvc = VolumeCurve.Create(object_object_id=target.cdb_object_id,
                                               calc_object_id=target.calc_object_id,
                                               volume_curve_object_id=cdbuuid.create_uuid(),
                                               primary_volume_curve=1)
                    for entry in self.VolumeCurve.Entries:
                        entry.Copy(volume_curve_object_id=newvc.volume_curve_object_id,
                                   calc_object_id=newvc.calc_object_id,
                                   primary_component_object_id=target.cdb_object_id)
                        newobj_dict[entry.volume_curve_object_id] = newvc.volume_curve_object_id
                else:
                    if not target.Parent:
                        parent = Component.ByKeys(target.parent_object_id)
                    else:
                        parent = target.Parent
                    self.VolumeCurve.Copy(object_object_id=target.cdb_object_id,
                                          calc_object_id=target.calc_object_id,
                                          volume_curve_object_id=parent.VolumeCurve.volume_curve_object_id)

    def copy_parameters(self, ctx):
        tmpl = Component.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        if tmpl:
            tmpl.copy_parameters_to(self)

    def copy_results(self, ctx):
        tmpl = Component.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        if tmpl:
            tmpl.copy_results_to(self)

    def copy_volume_curve(self, ctx):
        tmpl = Component.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        if tmpl:
            tmpl.copy_volume_curve_to(self)

    def copy_structure(self, ctx):
        old_comp = Component.ByKeys(ctx.cdbtemplate.cdb_object_id)
        Component.copy_structure_for_component(old_comp,
                                               self,
                                               copy_clones=False if self.parent_object_id else True)

    @classmethod
    def copy_structure_for_component(cls, old_comp, new_comp, newobj_dict={}, copy_clones=False):
        comps = Component2Component.KeywordQuery(parent_object_id=new_comp.parent_object_id,
                                                 calc_object_id=new_comp.calc_object_id)
        if comps:
            sort_order = max(comps.sort_order) + 10 if max(comps.sort_order) else 10
        else:
            sort_order = 10
        nl = Component2Component.Create(parent_object_id=new_comp.parent_object_id,
                                        comp_object_id=new_comp.cdb_object_id,
                                        calc_object_id=new_comp.calc_object_id,
                                        cloned=0,
                                        quantity=new_comp.quantity,
                                        sort_order=sort_order)
        if old_comp.Children:
            old_structure = old_comp.Calculation._get_component_structure_other(old_comp)
            new_to_old = {}
            new_to_old[old_comp.cdb_object_id] = new_comp
            new_to_old_links = {}
            new_to_old_links[old_comp.cdb_object_id] = nl
            old_curr = {c.name: c.cdb_object_id for c in
                        Currency.KeywordQuery(schema_object_id=old_comp.schema_object_id)}
            new_curr = {old_curr[nc.name]: nc.cdb_object_id for nc in
                        Currency.KeywordQuery(schema_object_id=new_comp.schema_object_id)}
            for c in old_structure:
                if c[0]:
                    component = c[0]
                    if component.cdb_object_id not in list(new_to_old):
                        nc = component.Copy(cdb_object_id=cdbuuid.create_uuid(),
                                            parent_object_id=new_to_old[c[1].parent_object_id].cdb_object_id if c[1] else new_to_old[component.parent_object_id].cdb_object_id,
                                            calc_object_id=new_comp.calc_object_id,
                                            cloned=component.cloned if copy_clones else new_comp.cloned,
                                            template_object_id=component.cdb_object_id)
                        component.copy_results_to(nc)
                        component.copy_parameters_to(nc)
                        new_to_old[component.cdb_object_id] = nc
                        newobj_dict[component.cdb_object_id] = nc.cdb_object_id
                        component.copy_volume_curve_to(nc, newobj_dict)
                        sig.emit(cls, COMPONENT_COPY_SIGNAL)(component, nc, new_to_old, new_curr)
                    if c[1].cdb_object_id not in list(new_to_old_links):
                        link = c[1].Copy(parent_object_id=new_to_old[c[1].parent_object_id].cdb_object_id,
                                         comp_object_id=new_to_old[c[1].comp_object_id].cdb_object_id,
                                         calc_object_id=new_comp.calc_object_id,
                                         cloned=c[1].cloned if copy_clones else new_comp.cloned,
                                         quantity=c[1].quantity,
                                         sort_order=c[1].sort_order)
                        new_to_old_links[c[1].cdb_object_id] = link
            if old_comp.schema_object_id != new_comp.schema_object_id:
                for curr in new_curr.keys():
                    Component.KeywordQuery(curr_object_id=curr,
                                           calc_object_id=new_comp.calc_object_id).Update(
                        curr_object_id=new_curr[curr])
                    ParameterValue.KeywordQuery(curr_object_id=curr,
                                                context_object_id=[
                                                    x.cdb_object_id for x in new_to_old.values()
                                                ]).Update(curr_object_id=new_curr[curr])
            if not copy_clones and old_comp.calc_object_id != new_comp.calc_object_id:
                # check complete structure for clones when copying structs between calculations outside indexing
                for top_component in new_comp.Calculation.TopComponents:
                    comp_oids = []
                    structure = top_component.Calculation.get_components_from_structure(top_component)
                    for c in structure:
                        if type(c) == tuple:
                            component = c[0]
                            comp2comp_oid = c[1].cdb_object_id
                        else:
                            component = c
                            comp2comp_oid = component.combined_id
                        if component.cdb_object_id in comp_oids:
                            if not component.cloned:
                                Component.ByKeys(component.cdb_object_id).Update(cloned=1)
                            Component2Component.ByKeys(comp2comp_oid).Update(cloned=1)
                        else:
                            comp_oids.append(component.cdb_object_id)

    def select_insert_type(self, ctx):
        if ctx.dialog and "insert_type" in ctx.dialog.get_attribute_names():
            if not self.Parent.parent_object_id:
                raise ue.Exception("costing_no_parent_above")
            ctx.keep("insert_type", ctx.dialog.parent_object_id)
            ctx.set("parent_object_id", self.Parent.parent_object_id)
            if self.Parent and self.Parent.Parent and self.Parent.Parent.cloned:
                self.cloned = 1
            else:
                self.cloned = 0

    def rearrange_child_component(self, ctx):
        if "insert_type" in ctx.ue_args.get_attribute_names():
            new_child = Component.ByKeys(ctx.ue_args.insert_type)
            new_child.Update(parent_object_id=self.cdb_object_id)
            new_child_comp2comp = Component2Component.KeywordQuery(
                                            comp_object_id=ctx.ue_args.insert_type,
                                            calc_object_id=self.calc_object_id)
            new_child_comp2comp.Update(parent_object_id=self.cdb_object_id)
            child_sort_order = new_child_comp2comp[0].sort_order
            Component2Component.KeywordQuery(comp_object_id=self.cdb_object_id,
                                             parent_object_id=self.parent_object_id,
                                             calc_object_id=self.calc_object_id)\
                .Update(sort_order=child_sort_order)
        else:
            if self.Parent and self.Parent.ResultValues:
                self.Parent.ResultValues.Delete()
                self.Parent.ParameterValues.Delete()
                self.Parent.create_default_parameters()

    def clone_component_mask(self, ctx):
        if ctx and "parent_cloned" in ctx.dialog.get_attribute_names() \
            and 'parent' in ctx.dialog.get_attribute_names():
            ctx.set("new_parent_object_id", ctx.dialog.parent)

    def clone_component(self, ctx):
        find_quantity = True
        old_parent_object_id = ""
        if ctx and "new_parent_object_id" in ctx.dialog.get_attribute_names():
            parent_object_id = ctx.dialog.new_parent_object_id
            if 'parent' in ctx.dialog.get_attribute_names():
                old_parent_object_id = ctx.dialog.parent
            else:
                old_parent_object_id = self.parent_object_id
        elif ctx and "parent" in ctx.dialog.get_attribute_names():
            parent_object_id = ctx.dialog.parent
            old_parent_object_id = parent_object_id
        else:
            parent_object_id = self.parent_object_id
            find_quantity = False

        if parent_object_id == old_parent_object_id:
            raise ue.Exception("cdbpco_same_parent_clone")

        if parent_object_id == self.cdb_object_id:
            raise ue.Exception("cdbpco_same_object_clone")

        pc = Component2Component.KeywordQuery(parent_object_id=parent_object_id,
                                              comp_object_id=self.cdb_object_id,
                                              calc_object_id=self.calc_object_id)
        if pc:
            raise ue.Exception("cdbpco_same_parent_clone")

        npcc = Component2Component.KeywordQuery(comp_object_id=parent_object_id,
                                                calc_object_id=self.calc_object_id)
        while(npcc):
            npc = npcc[0]
            if npc.comp_object_id == self.cdb_object_id:
                raise ue.Exception("cdbpco_same_object_clone")
            npcc = Component2Component.KeywordQuery(comp_object_id=npc.parent_object_id,
                                                    calc_object_id=self.calc_object_id)

        quantity = self.quantity
        if find_quantity:
            pc = Component2Component.KeywordQuery(parent_object_id=old_parent_object_id,
                                                  comp_object_id=self.cdb_object_id,
                                                  calc_object_id=self.calc_object_id)
            if pc:
                quantity = pc[0].quantity

        with transaction.Transaction():
            comps = Component2Component.KeywordQuery(parent_object_id=parent_object_id,
                                                     calc_object_id=self.calc_object_id)
            if comps:
                sort_order = max(comps.sort_order) + 10 if max(comps.sort_order) else 10
            else:
                sort_order = 10

            Component2Component.CreateNoResult(parent_object_id=parent_object_id,
                                               comp_object_id=self.cdb_object_id,
                                               calc_object_id=self.calc_object_id,
                                               cloned=1,
                                               quantity=quantity,
                                               sort_order=sort_order)
            if self.Children and not self.cloned:
                structure = self.Calculation.get_components_from_structure(self)
                for c in structure:
                    if type(c) == tuple:
                        component = c[0]
                    else:
                        component = c
                    if component:
                        sqlapi.SQLupdate("cdbpco_component set cloned=1 where cdb_object_id='%s'" % component.cdb_object_id)
            self.Update(cloned=1)

    def perform_clone_delete(self, parent=None):
        ccs = Component2Component.KeywordQuery(comp_object_id=self.cdb_object_id,
                                               calc_object_id=self.calc_object_id)
        for cc in ccs:
            if not parent or (parent and cc.parent_object_id == parent.cdb_object_id):
                cc.Delete()
                break
        for top_component in self.Calculation.TopComponents:
            all_comp_oids = []
            cloned_comp_oids = []
            cloned_struct_oids = []
            structure = top_component.Calculation.get_components_from_structure(top_component)
            for c in structure:
                if type(c) == tuple:
                    component = c[0]
                    comp2comp_oid = c[1].cdb_object_id
                else:
                    component = c
                    comp2comp_oid = component.combined_id
                if component.cdb_object_id in all_comp_oids:
                    if component.cdb_object_id not in cloned_comp_oids:
                        cloned_comp_oids.append(component.cdb_object_id)
                        cloned_struct_oids.append(comp2comp_oid)
                else:
                    all_comp_oids.append(component.cdb_object_id)
            if all_comp_oids:
                Component.KeywordQuery(calc_object_id=self.calc_object_id).Update(cloned=0)
                Component2Component.KeywordQuery(calc_object_id=self.calc_object_id).Update(cloned=0)
            if cloned_comp_oids:
                Component.KeywordQuery(cdb_object_id=cloned_comp_oids,
                                       calc_object_id=self.calc_object_id).Update(cloned=1)
                Component2Component.KeywordQuery(cdb_object_id=cloned_struct_oids,
                                                 calc_object_id=self.calc_object_id).Update(cloned=1)

    def calculate_comp_result(self, ctx=None):
        self.Calculation.calculate_component(self, ctx)

    def delete_original_clone(self, ctx=None):
        if ctx and "parent" in ctx.dialog.get_attribute_names():
            parent_object_id = ctx.dialog.parent
            parent = Component2Component.ByKeys(parent_object_id)
            if parent:
                # get component entry of parent comp2component
                parent = parent.Component
            self.perform_clone_delete(parent)
        elif self.parent_object_id:
            self.perform_clone_delete(self.Parent)
        ccs = Component2Component.KeywordQuery(comp_object_id=self.cdb_object_id,
                                               calc_object_id=self.calc_object_id)
        if len(ccs) == 0:
            self.cdbpco_delete()
            self.Delete()

        else:
            for cc in ccs:
                self.Update(parent_object_id=cc.parent_object_id)
                break
        self.delete_cleanup()

    def delete_cleanup(self):
        # delete all components not in structure
        comps_in_struct = set()
        top_comps = Component.KeywordQuery(calc_object_id=self.calc_object_id,
                                           parent_object_id="")
        for top_comp in top_comps:
            comps_in_struct.add(top_comp.cdb_object_id)
            comp_struct = self.Calculation.get_components_from_structure(top_comp)
            for comp in comp_struct:
                if type(comp) == tuple:
                    c = comp[0]
                else:
                    c = comp
                comps_in_struct.add(c.cdb_object_id)
        all_calc_components = sqlapi.RecordSet2(
            sql="select cdb_object_id from cdbpco_component where calc_object_id='%s'" % self.calc_object_id)
        for calc_comp in all_calc_components:
            if calc_comp.cdb_object_id not in comps_in_struct:
                comp_obj = Component.ByKeys(calc_comp.cdb_object_id)
                cc = Component2Component.KeywordQuery(comp_object_id=calc_comp.cdb_object_id,
                                                      calc_object_id=self.calc_object_id)
                if cc:
                    cc.Delete()
                comp_obj.cdbpco_delete()
                comp_obj.Delete()

    def delegate_component(self, ctx):
        self.subject_id = ctx.dialog.subject_id
        self.subject_type = ctx.dialog.subject_type

    def filter_default_parameters(self, pdefs):
        year = self.Calculation.para_year
        if not year:
            year = "%d" % datetime.date.today().year
        factory_oid = self.costplant_object_id
        for pdef in list(six.itervalues(pdefs)):
            real_dval = None
            factory_dval = None
            year_dval = None
            for dval in pdef.DefaultValues:
                if dval.valid_year == year and dval.costplant_object_id == factory_oid and dval.material_object_id == self.material_object_id:
                    real_dval = dval
                elif not real_dval and dval.costplant_object_id == factory_oid and dval.material_object_id == self.material_object_id and not dval.valid_year:
                    real_dval = dval
                elif dval.costplant_object_id == factory_oid and not dval.material_object_id and dval.valid_year == year:
                    factory_dval = dval
                elif not factory_dval and dval.costplant_object_id == factory_oid and not dval.valid_year and not dval.material_object_id:
                    factory_dval = dval
                elif dval.valid_year == year and not dval.material_object_id and not dval.costplant_object_id:
                    year_dval = dval
                elif not year_dval and dval.valid_year and not dval.material_object_id and not dval.costplant_object_id:
                    year_dval = dval
                else:
                    continue
            if not real_dval:
                if factory_dval:
                    factory_dval.copy_to_context_object(context_object_id=self.cdb_object_id)
                else:
                    if year_dval:
                        year_dval.copy_to_context_object(context_object_id=self.cdb_object_id)
                    else:
                        ParameterValue.createForContextObject(
                            pdef, context_object_id=self.cdb_object_id, value=0.0)
            else:
                real_dval.copy_to_context_object(context_object_id=self.cdb_object_id)

    def create_default_parameters(self, ctx=None):
        """
        Create default parameter values for a Component object.
        """
        saved_parameters = []
        for x in self.ParameterValues.KeywordQuery(overwrite=0):
            saved_parameters.append(dict(
                context_object_id=x.context_object_id,
                pdef_object_id=x.pdef_object_id,
                value=x.value
            ))

        self.ParameterValues.Delete()
#        if not self.werkstoff_nr and not self.technology_id:
        # can not identify component default parameters
        # without this two fields
#            return
        pdefs = self.Calculation.CalculationSchema.ParameterDefinitions
        real_pdefs = {}
        for pdef in pdefs:
            if pdef.has_defaults == 0:
                continue
            if pdef.code not in real_pdefs:
                real_pdefs[pdef.code] = pdef
            elif self.cdb_classname == pdef.classname:
                real_pdefs[pdef.code] = pdef
            elif real_pdefs[pdef.code].classname != self.cdb_classname and pdef.classname == "":
                real_pdefs[pdef.code] = pdef
            else:
                continue
        self.filter_default_parameters(real_pdefs)
        for saved_parameter in saved_parameters:
            if saved_parameter["value"]:
                ParameterValue.KeywordQuery(context_object_id=saved_parameter["context_object_id"],
                                            pdef_object_id=saved_parameter["pdef_object_id"]
                                            ).Update(value=saved_parameter["value"],
                                                     overwrite=0)

    def createCloneEntry(self, ctx):
        comps = Component2Component.KeywordQuery(parent_object_id=self.parent_object_id,
                                                 calc_object_id=self.calc_object_id)
        if comps:
            sort_orders = [int(comp.sort_order) for comp in comps]
            sort_order = max(sort_orders) + 10 if max(sort_orders) else 10
        else:
            sort_order = 10
        Component2Component.CreateNoResult(parent_object_id=self.parent_object_id,
                                           comp_object_id=self.cdb_object_id,
                                           calc_object_id=self.calc_object_id,
                                           cloned=self.Parent.cloned if self.Parent else 0,
                                           quantity=self.quantity,
                                           sort_order=sort_order)

    @classmethod
    def create_default_parameters_for_components(cls, components):
        for component in components:
            component.create_default_parameters()

    @classmethod
    def on_cdbpco_init_parameter_now(cls, ctx):
        """
        Create all parameters from default values.
        """
        init_parameter_cache(True)
        for obj in ctx.objects:
            component = cls.ByKeys(obj["cdb_object_id"])
            if component:
                component.create_default_parameters(ctx)

    def name_generator(self, ctx):
        pass

    def referencedAuditTrailObjects(self):
        return [self, self.Calculation]


class PartComponent(Component):
    __classname__ = "cdbpco_part_component"
    __match__ = fComponent.cdb_classname >= __classname__

    def name_generator(self, ctx):
        if self.Item:
            desc_string = "{teilenummer} / {t_index} {benennung} ({kategorie})"
            eng = desc_string.format(teilenummer=self.Item.teilenummer,
                                     t_index=self.Item.t_index,
                                     benennung=self.Item.eng_benennung,
                                     kategorie=self.Item.t_kategorie_name_en)
            de = desc_string.format(teilenummer=self.Item.teilenummer,
                                     t_index=self.Item.t_index,
                                     benennung=self.Item.benennung,
                                     kategorie=self.Item.t_kategorie_name_de)
            return eng, de
        return "", ""


class StepComponent(Component):
    __classname__ = "cdbpco_step_component"
    __match__ = fComponent.cdb_classname >= __classname__

    def name_generator(self, ctx):
        if self.Item:
            desc_string = "{teilenummer} / {t_index} {benennung} ({kategorie})"
            eng = desc_string.format(teilenummer=self.Item.teilenummer,
                                     t_index=self.Item.t_index,
                                     benennung=self.Item.eng_benennung,
                                     kategorie=self.Item.t_kategorie_name_en)
            de = desc_string.format(teilenummer=self.Item.teilenummer,
                                    t_index=self.Item.t_index,
                                    benennung=self.Item.benennung,
                                    kategorie=self.Item.t_kategorie_name_de)
            return eng, de
        return "", ""


class Component2Component(Object):
    """
        Used to indicate cloned components.
    """
    __maps_to__ = "cdbpco_comp2component"
    __classname__ = "cdbpco_comp2component"

    ParentComponent = Reference_1(
        fComponent,
        fComponent.cdb_object_id == fClonedComponent.parent_object_id)

    Children = Reference_N(
        fClonedComponent,
        fClonedComponent.parent_object_id == fClonedComponent.comp_object_id
    )

    Component = Reference_1(
        fComponent,
        fComponent.cdb_object_id == fClonedComponent.comp_object_id
    )

    event_map = {
        (('delete'), 'post'): ('reset_cloned'),
        (('modify'), 'post'): ('set_combined_quantity', 'update_volume_curve')
    }

    def reset_cloned(self, ctx):
        c = Component.ByKeys(self.comp_object_id)
        if c and not Component2Component.KeywordQuery(comp_object_id=self.comp_object_id):
            c.Update(cloned=0)

    def set_combined_quantity(self, ctx):
        if self.cloned:
            ccs = Component2Component.KeywordQuery(comp_object_id=self.comp_object_id,
                                                   parent_object_id=self.parent_object_id,
                                                   calc_object_id=self.calc_object_id)
            if len(ccs) > 1:
                ccs.Update(quantity=self.quantity)
        else:
            self.Component.Update(parent_object_id=self.parent_object_id)

    def update_volume_curve(self, ctx):
        if not self.cloned:
            parent = Component.ByKeys(self.parent_object_id)
            component = self.Component
            p_vc = parent.VolumeCurve
            c_vc = component.VolumeCurve

            if c_vc and p_vc:
                if c_vc.volume_curve_object_id != p_vc.volume_curve_object_id:
                    comp_structure = c_vc.Calculation._get_component_structure_other(component)
                    for calc_comp in comp_structure:
                        if type(calc_comp) == tuple:
                            c = calc_comp[0]
                        else:
                            c = calc_comp
                        if c.VolumeCurve.Entries:
                            c.VolumeCurve.Entries.Delete()
                        c.VolumeCurve.Update(volume_curve_object_id=p_vc.volume_curve_object_id)
                    if c_vc.Entries:
                        c_vc.Entries.Delete()
                    c_vc.Update(volume_curve_object_id=p_vc.volume_curve_object_id)
                    c_vc.set_volume_curve_values()


@sig.connect(FILE_EVENT, Component.__maps_to__, any)
def _file_event_handler(the_file, comp_obj_hndl, ctx):
    comp = Component.ByKeys(comp_obj_hndl.getValue('cdb_object_id', False))
    if comp is None:
        return
    if ctx.action in ('create', 'modify'):
        comp.fileUpdate(the_file, ctx)


@connect("officelink_metadata_write")
def get_paramter_values_from_excel_sheet(self, ctx):
    if ctx.object["cdb_classname"] == Component.__classname__:
        from cs.officelink.documentvariables import DocumentVariable
        calc_comp = Component.ByKeys(ctx.object["cdb_object_id"])
        for var_name, var_value in list(six.iteritems(ctx.document_variables)):
            var = DocumentVariable(var_name)
            if var.relationship == "cdbpco_comp2para_val":
                allocate_license("COSTING_013")
                calc_comp.updateParameterValue(var.parameter, float(var_value))
                calc_comp.Update(cdb_tpersno=auth.persno, cdb_tdate=datetime.datetime.now())


@connect("officelink_metadata_read")
def set_result_values_in_excel_sheet(self, ctx):
    if ctx.object["cdb_classname"] == Component.__classname__:
        from cs.officelink.documentvariables import DocumentVariable
        calc_comp = Component.ByKeys(ctx.object["cdb_object_id"])
        for var_name in ctx.document_variables:
            var = DocumentVariable(var_name)
            if var.relationship == "cdbpco_comp2result_val":
                allocate_license("COSTING_013")
                ctx.document_variables[var_name] = calc_comp.getResultValue(var.parameter)


class Product2Delivery(Object):
    """
    Relationship between Delivery and Product.
    """

    __maps_to__ = "cdbpco_product2delivery"
    __classname__ = "cdbpco_product2delivery"

    Product = Reference_1(fProduct,
                          fProduct2Delivery.product_object_id)

    Delivery = Reference_1(fDelivery,
                           fProduct2Delivery.delivery_object_id)

    def copy_to(self, newref, newobj_dict):
        """
        Copy the current object(relationship) to a new Calculation. Using the
        newobj_dict mapping to rebuild the relationships.
        """
        newdata = {"calc_object_id": newref.calc_object_id,
                   "product_object_id": newref.cdb_object_id,
                   "delivery_object_id": newobj_dict[self.delivery_object_id]}
        newdata.update(self.MakeChangeControlAttributes())
        newdata["cdb_object_id"] = cdbuuid.create_uuid()
        self.Copy(**newdata)

    def on_create_pre_mask(self, ctx):
        if ctx.dragged_obj:
            check_drag_drop_allowed(ctx.dragged_obj, self)

    @classmethod
    def prepareVariants(cls, calculation, deliveries=[], products=[], amount=0):
        _products = products or calculation.Products
        _deliveries = deliveries or calculation.Deliveries
        created = []
        if _products and _deliveries:
            for p in _products:
                for c in _deliveries:
                    created.append(
                        cls.Create(calc_object_id=calculation.cdb_object_id,
                                   delivery_object_id=c.cdb_object_id,
                                   product_object_id=p.cdb_object_id,
                                   amount=amount)
                    )
        return created

    @classmethod
    def deleteVariants(cls, product, delivery_condition):
        cond = "product_object_id = '%s'" % product.cdb_object_id
        cond += " AND delivery_object_id in "
        cond += " (select cdb_object_id from %s where calc_object_id='%s' AND %s)" % (
            Delivery.GetTableName(), product.calc_object_id, delivery_condition
        )
        cls.Query(cond).Delete()


class Component2Delivery(Object):
    """
    Relationship between Delivery and Component.
    """

    __maps_to__ = "cdbpco_component2delivery"
    __classname__ = "cdbpco_component2delivery"

    Component = Reference_1(fComponent,
                            fComponent2Delivery.comp_object_id)

    Delivery = Reference_1(fDelivery,
                           fComponent2Delivery.delivery_object_id)

    def copy_to(self, newref, newobj_dict):
        """
        Copy the current object(relationship) to a new Calculation. Using the
        newobj_dict mapping to rebuild the relationships.
        """
        newdata = {"calc_object_id": newref.calc_object_id,
                   "comp_object_id": newobj_dict[self.comp_object_id],
                   "delivery_object_id": newobj_dict[self.delivery_object_id],
                   "cdb_object_id": cdbuuid.create_uuid()}
        self.Copy(**newdata)

    def on_create_pre_mask(self, ctx):
        if ctx.dragged_obj:
            check_drag_drop_allowed(ctx.dragged_obj, self)


class Component2Product(Object):
    """
    Relationship between Product and Component.
    """

    __maps_to__ = "cdbpco_comp2product"
    __classname__ = "cdbpco_comp2product"

    Component = Reference_1(fComponent,
                            fComponent2Product.comp_object_id)
    Product = Reference_1(fProduct,
                          fComponent2Product.product_object_id)

    def copy_to(self, newref, newobj_dict):
        """
        Copy the current object(relationship) to a new Calculation. Using the
        newobj_dict mapping to rebuild the relationships.
        """
        if self.product_object_id in newobj_dict:
            newdata = {"calc_object_id": newref.calc_object_id,
                       "comp_object_id": newref.cdb_object_id,
                       "product_object_id":
                            newobj_dict[self.product_object_id]}
            newdata.update(self.MakeChangeControlAttributes())
            newdata["cdb_object_id"] = cdbuuid.create_uuid()
            self.Copy(**newdata)

    def on_create_pre_mask(self, ctx):
        if ctx.dragged_obj:
            check_drag_drop_allowed(ctx.dragged_obj, self)

    @classmethod
    def prepareVariants(cls, calculation, products=[], components=[], amount=0):
        _products = products or calculation.Products
        _components = components or calculation.Components
        if not _products or not _components:
            return
        changes = cls.MakeChangeControlAttributes()
        for p in _products:
            for c in _components:
                newcomp = cls.Create(calc_object_id=calculation.cdb_object_id,
                                     comp_object_id=c.cdb_object_id,
                                     product_object_id=p.cdb_object_id,
                                     amount=amount,
                                     **changes)


class ComponentFolder2Component(Object):

    __maps_to__ = "cdbpco_cfolder2comp"
    __classname__ = "cdbpco_cfolder2comp"

    ComponentFolder = Reference_1(fComponentFolder, fComponentFolder2Component.folder_object_id)
    Component = Reference_1(fComponent, fComponentFolder2Component.component_object_id)

    event_map = {
        (("create", "copy"), ("pre")): "preventContextChange",
        (("create", "copy"), ("post")): "ensureCardinality",
        }

    def preventContextChange(self, ctx):
        if self.Component.calc_object_id != self.ComponentFolder.calc_object_id:
            raise ue.Exception("cdbpco_calc_context")

    def ensureCardinality(self, ctx):
        if self.Component:
            asgn = ComponentFolder2Component.Query("component_object_id = '%s' and folder_object_id != '%s'" %
                                                   (self.Component.cdb_object_id, self.folder_object_id))
            if asgn:
                asgn.Delete()

    def copy_to(self, newref, newobj_dict):
        """
        Copy the current object(relationship) to a new Calculation. Using the
        newobj_dict mapping to rebuild the relationships.
        """
        if self.folder_object_id in newobj_dict:
            newdata = {"calc_object_id": newref.calc_object_id,
                       "component_object_id": newref.cdb_object_id,
                       "folder_object_id":
                           newobj_dict[self.folder_object_id]}
            newdata.update(self.MakeChangeControlAttributes())
            newdata["cdb_object_id"] = cdbuuid.create_uuid()
            self.Copy(**newdata)


class PartCost(Object):
    """
    The costs of part.
    """
    __maps_to__ = "cdbpco_part_cost"
    __classname__ = "cdbpco_part_cost"

    Item = Reference_1(fItem,
                       fComponent.teilenummer,
                       fComponent.t_index)

    event_map = {
        (('create', 'copy', 'modify'), 'pre'): ('check_value', 'check_uniqueness'),
        (('create', 'copy'), 'pre_mask'): ('set_defaults')
        }

    def check_uniqueness(self, ctx):
        """
        Check the uniqueness of the costs: at the same time there can only be
        one valid cost record for the same part, same plant and in same cost
        level. If a newer data record should be inserted or created, set the
        older one to invalid.
        """
        qstr = "teilenummer = '%s' and t_index = '%s' " % (self.teilenummer,
                                                           self.t_index)
        qstr += "and costplant_object_id = '%s' " % self.costplant_object_id
        qstr += "and ((valid_from<%s and not valid_until<%s) or " % \
                    (sqlapi.SQLdbms_date(self.valid_until),
                     sqlapi.SQLdbms_date(self.valid_from))
        qstr += "(valid_until>%s and not valid_from>%s)) " % \
                    (sqlapi.SQLdbms_date(self.valid_from),
                     sqlapi.SQLdbms_date(self.valid_until))
        if ctx.action == 'modify':
            qstr += "and cdb_object_id != '%s' " % self.cdb_object_id
        pcosts = PartCost.Query(qstr)
        if len(pcosts) > 0:
            # cost data exists
            if ctx and ctx.action in ("create", "copy"):
                # the older one should become obsolte
                newuntil = cdbtime.Time(self.valid_from).date() - datetime.timedelta(days=1)
                pcosts.Update(valid_until=newuntil)
            else:
                raise ue.Exception("cdbpco_pcost_unique",
                                   self.valid_from,
                                   self.valid_until)

    def set_defaults(self, ctx):
        # preset valid period
        today = datetime.date.today()
        self.valid_from = today
        self.valid_until = datetime.date(9999, 12, 31)
        # part data
        if self.Item:
            ctx.set("i18n_benennung", self.Item.i18n_benennung)
            ctx.set("mengeneinheit", self.Item.mengeneinheit)
        # default costs: 0
        if hasattr(ctx, "action") and ctx.action == "create":
            ctx.set("mek", 0.0)
            ctx.set("fek", 0.0)

    def check_value(self, ctx):
        # validate the cost inputs
        if "mek" in ctx.dialog.get_attribute_names() and \
                (ctx.dialog.mek == "" or ctx.dialog.mek is None):
            ctx.set("mek", 0.0)
        if "fek" in ctx.dialog.get_attribute_names() and \
                (ctx.dialog.fek == "" or ctx.dialog.fek is None):
            ctx.set("fek", 0.0)

    @classmethod
    def createPartCost(cls, **params):
        kwargs = dict(valid_from=datetime.date.today(),
                      valid_until=datetime.date(9999, 12, 31),
                      mek=0.0,
                      fek=0.0)
        kwargs.update(**PartCost.MakeChangeControlAttributes())
        kwargs.update(params)
        return operations.operation(constants.kOperationNew,
                                    PartCost,
                                    **kwargs)


class ComponentFolder(Object):
    """
    Component folder to organize the components.
    """

    __maps_to__ = "cdbpco_comp_folder"
    __classname__ = "cdbpco_comp_folder"

    Calculation = Reference_1(fCalculation,
                              fComponentFolder.calc_object_id)

    SubFolders = Reference_N(
        fComponentFolder,
        fComponentFolder.parent_object_id == fComponentFolder.cdb_object_id)

    ComponentAssignments = Reference_N(
        fComponentFolder2Component,
        fComponentFolder2Component.folder_object_id == fComponentFolder.cdb_object_id)

    event_map = {
            ('delete', 'post'): 'cdbpco_delete',
            (('create', 'copy'), 'pre'): 'set_position'
            }

    def set_position(self, ctx):
        # set the folder position to next possible value
        pos = 0
        maxposrec = sqlapi.RecordSet2(sql="select max(order_no) maxpos " +
                                         "from %s " % self.GetTableName() +
                                         "where calc_object_id='%s'" %
                                         self.calc_object_id)
        try:
            pos = int(maxposrec[0].maxpos) + 1
        except Exception:
            pass
        self.order_no = pos

    def check_delete(self, ctx):
        """
        Check the conditions before delete the current object.
        """
        if not ctx.interactive:
            # non-stop in batch mode
            return
        if len(self.SubFolders):
            # current object is referenced from sub folder,
            # should not be deleted
            raise ue.Exception("cdbpco_err_msg_04")

    def copy_to(self, newcalc, newobj_dict=None):
        """
        Copy the current object to a new Calculation.
        :Parameters:
            - `newcalc` : the new Calculation object which the current object
                          should be copy to
            - `newobj_dict` : to remember which object is copied from current
                              object. It can be used later to generate the
                              relationships etc.
        """
        newdata = {"calc_object_id": newcalc.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        newdata.update(self.MakeChangeControlAttributes())
        newobj = self.Copy(**newdata)
        if newobj_dict is None:
            newobj_dict = {}
        newobj_dict[self.cdb_object_id] = newobj.cdb_object_id
        # also copy the sub folders
        for subfd in self.SubFolders:
            subfd.copy_sub_folder(newobj, newobj_dict)
        return newobj

    def copy_sub_folder(self, newparent, newobj_dict):
        """
        Copy sub folders. It will be called recursively with setting
        corresponding parent folder as parameter.
        """
        newdata = {"calc_object_id": newparent.calc_object_id,
                   "parent_object_id": newparent.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        newdata.update(self.MakeChangeControlAttributes())
        newobj = self.Copy(**newdata)
        newobj_dict[self.cdb_object_id] = newobj.cdb_object_id
        for subfd in self.SubFolders:
            subfd.copy_sub_folder(newobj, newobj_dict)

    def on_cdbpco_set_pos_now(self, ctx):
        """
        Operation event handler to reset the position of a folder - move it up
        or down.
        """
        # show a list of objects to be selected: the current object
        # will be moved to the next position of the selected one
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name="cdbpco_cfolder_br",
                                calc_object_id=self.calc_object_id)
        else:
            cdb_object_id = ctx.catalog_selection[0]["cdb_object_id"]
            # find out the selected object
            targetobj = ComponentFolder.ByKeys(cdb_object_id)
            if targetobj:
                mypos = self.order_no
                targetpos = targetobj.order_no
                if mypos != targetpos + 1:
                    # current object is not next to the selected one: will be
                    # moved there
                    # CAUTION: not only the current object will be moved - but
                    # also the intermediate objects
                    # posstep: moving direction, 1=afterwards(downwards),
                    #          -1=forwards(upwards)
                    posstep = 1
                    # the "should be"-position for current object
                    newpos = targetpos + 1
                    cond = "order_no>%i and order_no<%i" % (targetpos, mypos)
                    if mypos < targetpos:
                        # current object is in front of the target position,
                        # so move the objects behind it forwards
                        cond = "order_no<=%i and order_no>%i" % (targetpos,
                                                                 mypos)
                        posstep = -1
                        newpos = targetpos
                    # find out which objects should be moved
                    moveobjs = ComponentFolder.Query(
                                            "calc_object_id='%s' and " %
                                            self.calc_object_id + cond)
                    for moveobj in moveobjs:
                        moveobj.order_no = moveobj.order_no + posstep
                    self.order_no = newpos

    def cdbpco_delete(self, ctx):
        self.ComponentAssignments.Delete()
        for sfolder in self.SubFolders:
            sfolder.delete_calculation_object(ctx)

    def delete_calculation_object(self, ctx):
        self.cdbpco_delete(ctx)
        self.Delete()


class Delivery(Object, WithCalculationSchema):
    """
    A Calculation contains optionally no Delivery, one Delivery or different
    Deliveries.
    A Delivery consists of DeliveryUnit(s).
    A Delivery must be assigned to a Calculation.
    """
    __maps_to__ = "cdbpco_delivery"
    __classname__ = "cdbpco_delivery"

    Calculation = Reference_1(fCalculation,
                              fDelivery.calc_object_id)

    ProductAssignments = Reference_N(
        fProduct2Delivery,
        fProduct2Delivery.delivery_object_id == fDelivery.cdb_object_id)

    ComponentAssignments = Reference_N(
        fComponent2Delivery,
        fComponent2Delivery.delivery_object_id == fDelivery.cdb_object_id)

    ParameterValues = Reference_N(
        fParameterValue,
        fParameterValue.context_object_id == fDelivery.cdb_object_id)

    ResultValues = Reference_N(
        fResultValue,
        fResultValue.context_object_id == fDelivery.cdb_object_id)

    event_map = {
            ('create', 'post'): ('prepareVariants', 'create_default_parameters'),
            ('delete', 'post'): 'cdbpco_delete',
            ('modify', 'pre_mask'): 'reset_modify_mask',
            ('copy', 'post'): 'copy_parameters'
            }

    def reset_modify_mask(self, ctx):
        # can not be assigned to other Calculation
        ctx.set_readonly("calc_object_id")

    def copy_to(self, newcalc, newobj_dict):
        """
        Copy the current object to a new Calculation.
        :Parameters:
            - `newcalc` : the new Calculation object which the current object
                          should be copy to
            - `newobj_dict` : to remember which object is copied from current
                              object. It can be used later to generate the
                              relationships etc.
        """
        newdata = {"calc_object_id": newcalc.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        newdata.update(self.MakeChangeControlAttributes())
        newobj = self.Copy(**newdata)
        newobj_dict[self.cdb_object_id] = newobj.cdb_object_id
        self.copy_parameters_to(newobj)
        for assignment in self.ComponentAssignments:
            assignment.copy_to(newobj, newobj_dict)

    def prepareVariants(self, ctx=None):
        if self.Calculation:
            Product2Delivery.prepareVariants(self.Calculation, deliveries=[self])

    def filter_default_parameters(self, pdefs):
        default_year = self.Calculation.para_year
        factory_oid = self.Calculation.costplant_object_id
        for pdef in list(six.itervalues(pdefs)):
            default_dval = None
            real_dval = None
            for dval in pdef.DefaultValues:
                if dval.valid_year == self.sales_year and dval.costplant_object_id == factory_oid:
                    real_dval = dval
                elif dval.valid_year == self.sales_year and not dval.costplant_object_id:
                    default_dval = dval
                elif not default_dval and dval.valid_year == default_year and dval.costplant_object_id == factory_oid:
                    default_dval = dval
                else:
                    continue
            if not real_dval:
                if default_dval:
                    default_dval.copy_to_context_object(context_object_id=self.cdb_object_id)
                else:
                    ParameterValue.createForContextObject(
                        pdef, context_object_id=self.cdb_object_id, value=0.0)
            else:
                real_dval.copy_to_context_object(context_object_id=self.cdb_object_id)

    def create_default_parameters(self, ctx=None):
        """
        Create default parameter values for a Delivery object.
        """
        self.ParameterValues.Delete()
        pdefs = self.Calculation.CalculationSchema.ParameterDefinitions
        real_pdefs = {}
        for pdef in pdefs:
            if pdef.has_defaults == 0:
                continue
            if pdef.classname:
                continue
            elif pdef.code not in real_pdefs:
                real_pdefs[pdef.code] = pdef

        self.filter_default_parameters(real_pdefs)

    @classmethod
    def create_default_parameters_for_deliveries(cls, deliveries):
        for delivery in deliveries:
            delivery.create_default_parameters()

    def cdbpco_delete(self, ctx=None):
        """
        Delete related objects.
        """
        self.ParameterValues.Delete()
        self.ResultValues.Delete()
        self.ComponentAssignments.Delete()

    def delete_calculation_object(self, ctx):
        """
        Delete or clean up the related objects of current object.
        Will be called by deleting the (parent) Calculation object.
        """
        self.cdbpco_delete(ctx)
        self.Delete()

    @classmethod
    def get_own_parameter_values(cls, record=None, classname=None, calculation=None,
                                    ctx=None, exch_factor=None):
        """
        Get parameter values from current object. (Overwrite the default
        method in `WithCalculationSchema`.)
        """
        result = super(Delivery, cls).get_own_parameter_values(ctx)
        # generate "PY"
        try:
            result["values"]["PY"] = int(record.sales_year) - int(calculation.sop)
        except Exception:
            result["values"]["PY"] = 0
        return result

    def copy_parameters_to(self, target):
        if self.Calculation.schema_object_id == target.Calculation.schema_object_id and\
           self.Calculation.costplant_object_id == target.Calculation.costplant_object_id:
            ParameterValue.copy_parameters_to(self, target)

    def copy_parameters(self, ctx):
        tmpl = Delivery.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        if tmpl:
            tmpl.copy_parameters_to(self)


class Product(Object, WithCalculationSchema, briefcases.BriefcaseContent):
    """
    A Delivery consists of Product(s).
    A Product consists of Component(s).
    If there is no Delivery, a Calculation can contain
    optionally no Product, one Product or different Products.
    A Product must be assigned to a Calculation.
    """

    __maps_to__ = "cdbpco_product"
    __classname__ = "cdbpco_product"

    Calculation = Reference_1(fCalculation,
                              fProduct.calc_object_id)

    DeliveryAssignments = Reference_N(
            fProduct2Delivery,
            fProduct2Delivery.product_object_id == fProduct.cdb_object_id)

    ComponentAssignments = Reference_N(
            fComponent2Product,
            fComponent2Product.product_object_id == fProduct.cdb_object_id)

    ParameterValues = Reference_N(
            fParameterValue,
            fParameterValue.context_object_id == fProduct.cdb_object_id)

    ResultValues = Reference_N(
            fResultValue,
            fResultValue.context_object_id == fProduct.cdb_object_id)

    Item = Reference_1(fItem,
                       fProduct.teilenummer,
                       fProduct.t_index)

    def _get_bom_components(self):
        # Valid components are assigned with amount > 0
        return [a.Component for a in self.ComponentAssignments.Query("amount > 0")]

    Components = ReferenceMethods_N(fComponent, lambda self: self._get_bom_components())

    event_map = {
            ('delete', 'post'): 'cdbpco_delete',
            ('modify', 'pre_mask'): 'reset_modify_mask',
            ('create', 'post'): ('prepareVariants', 'genComponentsFromBOM'),
            ('copy', 'post'): ('prepareVariants2Delivery', 'copy_parameters'),
            ('create', 'pre_mask'): 'setNameFromPart',
            ('create', 'pre'): 'prepareComponentsFromBOM'
            }

    def reset_modify_mask(self, ctx):
        # can not be assigned to other Calculation
        ctx.set_readonly("calc_object_id")

    def cdbpco_delete(self, ctx):
        """
        Delete related objects.
        """
        self.DeliveryAssignments.Delete()
        self.ParameterValues.Delete()
        self.ResultValues.Delete()

    def delete_calculation_object(self, ctx):
        """
        Delete or clean up the related objects of current object.
        Will be called by deleting the (parent) Calculation object.
        """
        self.cdbpco_delete(ctx)
        self.Delete()

    def copy_to(self, newcalc, newobj_dict):
        """
        Copy the current object to a new Calculation.
        :Parameters:
            - `newcalc` : the new Calculation object which the current object
                          should be copy to
            - `newobj_dict` : to remember which object is copied from current
                              object. It can be used later to generate the
                              relationships etc.
        """
        newdata = {"calc_object_id": newcalc.cdb_object_id,
                   "cdb_object_id": cdbuuid.create_uuid()}
        newdata.update(self.MakeChangeControlAttributes())
        newobj = self.Copy(**newdata)
        newobj_dict[self.cdb_object_id] = newobj.cdb_object_id
        # also copy the Delivery->Product relationships
        for asgn in self.DeliveryAssignments:
            asgn.copy_to(newobj, newobj_dict)
        self.copy_parameters_to(newobj)

    def prepareVariants(self, ctx=None):
        components = self.Calculation.Components.Query(
            "cdb_object_id not in "
            "(select comp_object_id from %s where product_object_id='%s')" % (
                Component2Product.GetTableName(), self.cdb_object_id
            ))
        Component2Product.prepareVariants(
            self.Calculation, products=[self], components=components)
        self.prepareVariants2Delivery(ctx)

    def prepareVariants2Delivery(self, ctx=None):
        Product2Delivery.prepareVariants(self.Calculation, products=[self])

    def on_cdbpco_create_sales_volume_pre_mask(self, ctx):
        deliveries = self.Calculation.Deliveries
        if len(deliveries):
            ctx.set("sop", deliveries[0].sales_year)
            ctx.set("eop", deliveries[-1].sales_year)
        else:
            raise ue.Exception("cdbpco_no_sales_years")

    def on_cdbpco_create_sales_volume_pre(self, ctx):
        cond = "sales_year = '%s'" % ctx.dialog.sop
        cond += " or sales_year = '%s'" % ctx.dialog.eop
        count = len(self.Calculation.Deliveries.Query(cond))
        if ctx.dialog.sop > ctx.dialog.eop or \
           (ctx.dialog.sop == ctx.dialog.eop and count < 1) or \
           (ctx.dialog.sop < ctx.dialog.eop and count < 2):
            # Start and end of production must conform to sales years
            raise ue.Exception("cdbpco_invalid_product_year")

    def on_cdbpco_create_sales_volume_now(self, ctx):
        total = int(ctx.dialog.total)
        cond = "sales_year >= '%s'" % ctx.dialog.sop
        cond += " AND sales_year <= '%s'" % ctx.dialog.eop
        deliveries = self.Calculation.Deliveries.Query(cond)
        count = len(deliveries)
        if count:
            amount, rest = divmod(total, count)
            Product2Delivery.deleteVariants(
                product=self, delivery_condition=cond)
            volumes = Product2Delivery.prepareVariants(
                self.Calculation,
                products=[self], deliveries=deliveries, amount=amount)
            if rest != 0 and volumes:
                last = volumes[-1]
                last.Update(amount=last.amount + rest)

    def setNameFromPart(self, ctx):
        if "gen_product_from_part" in ctx.sys_args.get_attribute_names() and \
            ctx.sys_args["gen_product_from_part"] == "1":
            ctx.set("name", self.Item.benennung)

    def prepareComponentsFromBOM(self, ctx):
        if "gen_product_from_part" in ctx.sys_args.get_attribute_names() and \
            ctx.sys_args["gen_product_from_part"] == "1":
            if not ctx.catalog_selection:
                ctx.start_selection(catalog_name="cdbpco_bom_item_br",
                                    baugruppe=ctx.dialog.teilenummer,
                                    b_index=ctx.dialog.t_index)

    def genComponentsFromBOM(self, ctx):
        if "gen_product_from_part" in ctx.sys_args.get_attribute_names() and \
            ctx.sys_args["gen_product_from_part"] == "1" and \
            ctx.catalog_selection:
            components = {}
            for pos in ctx.catalog_selection:
                poskey = (pos["teilenummer"], pos["t_index"])
                keys = dict([(k, pos[k]) for k in pos.get_attribute_names()])
                bom_item = AssemblyComponent.ByKeys(**keys)
                components[poskey] = \
                    components.setdefault(poskey, 0) + bom_item.menge
            for poskey, amount in list(six.iteritems(components)):
                Component.genComponentFromBOM(poskey[0], poskey[1], self, amount)

    def copy_parameters_to(self, target):
        if self.Calculation.schema_object_id == target.Calculation.schema_object_id and\
           self.Calculation.costplant_object_id == target.Calculation.costplant_object_id:
            ParameterValue.copy_parameters_to(self, target)

    def copy_parameters(self, ctx):
        tmpl = Product.ByKeys(ctx.cdbtemplate["cdb_object_id"])
        if tmpl:
            tmpl.copy_parameters_to(self)


class ManufacturingTechnology(Object):
    __maps_to__ = "cdbpco_manufact_techn"
    __classname__ = "cdbpco_manufact_techn"
