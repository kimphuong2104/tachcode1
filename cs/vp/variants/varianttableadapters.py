#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module VariantTableAdapters

This is the documentation for the VariantTableAdapters module.
"""

import codecs
import encodings.utf_8
import enum

from cs.vp.variants.vpmsolvers import BasicVPMSolver
from cs.vp.variants.vpmsolvers import NestedVPMSolver
from cs.vp.variants.vpmsolvers import NestedVPMFilteredSolver
from cs.vp.variants.solvers import InnerProblem

from cdb.objects.core import parse_raw
from cdb.objects import Forward
from cdb.sqlapi import NULL
from cdb import util
from cdb.platform import gui

fViewVariant = Forward("cs.vp.variants.ViewVariant")
fProductVariant = Forward("cs.vp.variants.ProductVariant")
fVariantMapping = Forward("cs.vp.variants.VariantMapping")
fPropertyValue = Forward("cs.vp.variants.properties.PropertyValue")
fEnumDefinition = Forward("cs.vp.variants.properties.EnumDefinition")
fEnumDefPropertyValue = Forward("cs.vp.variants.properties.EnumDefPropertyValue")


# Solver status as defined in table cdbvp_enums
class SyncStatus(enum.Enum):
    manual = 0
    ok = 1
    invalid = 2
    new = 3
    incomplete = 4


class MappingStatus(enum.Enum):
    manual = 0
    ok = 1
    invalid = 2
    new = 3


def _get_syncstatus_from_text(status_text):
    try:
        return eval("SyncStatus.%s" % status_text)
    except AttributeError:
        pass


class VariantTableAdapter(object):

    def __init__(self):
        self._solver = None
        self._pager = None
        self._hidden_props = []

    def getSolver(self):
        if not self._solver:
            self._solver = self.makeSolver()
        return self._solver

    def getFilterSolution(self, outer_sol):
        return None

    def makeSolver(self):
        """ To be implemented by subclasses. """
        pass

    def getPager(self):
        if not self._pager:
            self._pager = self.makePager()
        return self._pager

    def makePager(self):
        """ To be implemented by subclasses """
        return None

    def resetPager(self):
        self.getPager().reset()

    def getTitle(self):
        """ To be implemented by subclasses.
        Returns the title for the variant result page. """
        return ""

    def sync_new(self, variant, variant_info, context=None):
        """ To be implemented by subclasses """
        pass

    def sync_manual(self, variant, variant_info, context=None):
        # Thinkabout:
        # Set to ok, if this is a valid variant?
        pass

    @staticmethod
    def sync_invalid(variant, variant_info, context=None):
        if not variant_info.variant_object.solver_status == SyncStatus.invalid.value:
            variant_info.variant_object.solver_status = SyncStatus.invalid.value
        return variant_info.variant_object

    @staticmethod
    def sync_ok(variant, variant_info, context=None):
        if not variant_info.variant_object.solver_status == SyncStatus.ok.value:
            variant_info.variant_object.solver_status = SyncStatus.ok.value
        return variant_info.variant_object

    def sync_variant(self, variant, variant_info, context=None):
        f = getattr(self, "sync_" + variant_info.state)
        return f(variant, variant_info, context)

    def sync_variants(self, variants):
        for v in variants:
            self.sync_variant(*v)

    def get_views(self):
        # For ProductAdapter implementations only.
        return []

    def get_inner_views(self):
        # For CombinedViewAdapter implementations only.
        return []

    @staticmethod
    def _get_image_path():
        from cs.vp.variants.apps import generatorui
        app = generatorui._getapp()
        return app.getOptions()["localres"]

    def _make_status_icon(self, status):
        state_obj = _get_syncstatus_from_text(status)
        if state_obj:
            result = '<img src="%simages/sync_status_%s.png" title="%s" width=16 height=16>' % \
                     (self._get_image_path(), state_obj.value, str(state_obj.name))
        else:
            result = "invalid state '%s'" % status
        return result

    @staticmethod
    def _make_hyperlink(obj, action=None, display_text=None):
        return '<a href="%s">%s</a>' % (obj.MakeURL(action=action), display_text if display_text else obj.GetDescription())

    def compute_result(self, presettings=None, addtl_search_args=None, page_size=0, start_row=0):
        if addtl_search_args is None:
            addtl_search_args = {}

        result = []
        metrics = {}
        solver = self.getSolver()
        solver._initMetrics()  # Fix E032537

        pager = self.getPager()
        if solver and pager:
            result = pager.nextpage(presettings, addtl_search_args, page_size, start_row)
            # add state icon
            for _variant, variant_info in result:
                variant_info.generator_infos["state"] = self._make_status_icon(variant_info.state)

            # add some metrics
            metrics = solver.getMetrics()
            metrics.update(pager.getMetrics())
            metrics["n_result"] = len(result)
        else:
            metrics["all_solved"] = 1
            metrics["iTotalRecords"] = 0

        return result, metrics

    def csv_export(self, presettings=None, addtl_search_args=None, filename=None, fileobj=None):
        if addtl_search_args is None:
            addtl_search_args = {}

        if not fileobj:
            if not filename:
                import os
                from cdb import rte
                filename = os.path.abspath(rte.environ["CADDOK_BASE"] + r"\tmp\variant_table.csv")

            assert isinstance(filename, str)
            # since the module csv does not support unicode, we need to write
            # bytestrings to the file, therefore we cannot use io.open
            fileobj = open(filename, "wb")

            # manually write BOM to file this is necessary for excel
            fileobj.write(codecs.BOM_UTF8)
        stream = encodings.utf_8.StreamWriter(fileobj)

        import csv
        writer = csv.writer(stream, delimiter=";")

        # build header
        solver = self.getSolver()
        variables = solver.getAllVariables()
        row = []

        columns = ['status']
        vcsv = util.get_prop('vcsv')
        if vcsv:
            columns = vcsv.split(",")
            columns = [c.strip() for c in columns]
        # allowed columns to be used in prop vcsv and their labels
        coldefs = {"status": "cdbvp_state",
                   "id": "cdbvp_id",
                   "name": "cdbvp_name",
                   "items": "cdbvp_part"}
        for col in columns:
            if col not in coldefs:
                raise RuntimeError("Invalid column name '%s' in property vcsv" % col)
            row.append(util.get_label(coldefs[col]))

        # we need to write byte strings in the csv file
        # because the python module csv does not support unicode
        row += [v.getName() for v in variables]
        writer.writerow(row)

        pager = self.getPager()
        pager.setup(presettings, addtl_search_args, 1000)
        rownr = 0
        data = pager.nextpage(presettings, addtl_search_args, 1000, rownr)

        item_dmsg = gui.Message.ByName('cdbvp_item_description_in_ve')
        item_dtag = item_dmsg.Text[''] if item_dmsg else None

        # add additional attributes as configured by prop vcsv
        for r in data:
            obj = r[1].variant_object
            r[1].generator_infos["status"] = r[1].state
            if "id" in columns:
                r[1].generator_infos["id"] = obj.id if obj else ""
            if "name" in columns:
                r[1].generator_infos["name"] = getattr(obj, "name", "") if obj else ""
            if "items" in columns:
                # für persistente varianten die ausgeprägten Artikel hinzufügen
                state_obj = _get_syncstatus_from_text(r[1].state)
                product = getattr(obj, "Product", None)
                if state_obj and state_obj != SyncStatus.new and product is not None:
                    display_texts = []
                    for partref in obj.PartsRefs:
                        part = partref.Part
                        if part and partref.MaxBOM in product.MaxBoms:
                            accessor = _PartReferenceAttributeAccessor(partref)
                            if item_dtag:
                                display_texts.append(parse_raw(item_dtag) % accessor)
                            else:
                                display_texts.append("%s/%s" % (part.teilenummer, part.t_index))
                    r[1].generator_infos["items"] = "\n".join(display_texts)
                else:
                    r[1].generator_infos["items"] = ""

        while data:
            for variant, variant_info in data:
                row = []
                for col in columns:
                    row.append(variant_info.generator_infos[col])

                row += ([v.getValueName(variant[v.getId()])
                        if v.getId() in variant else ""
                        for v in variables])

                # same as before: we must write byte strings in the csv file
                writer.writerow(row)
            rownr += len(data)
            data = pager.nextpage(presettings, addtl_search_args, 1000, rownr)

        fileobj.close()
        return filename

    def getDataTableColumns(self):
        return [self.getStateColumn()] + self.getAdditionalColumns() + self.getSolutionVariableColumns()

    def getAdditionalColumns(self):
        return []

    def getSolutionVariableColumns(self):
        from cs.vp.variants.apps.generatorui import SolutionVariableColumn
        columns = []
        solver = self.getSolver()
        for var in solver.getSolutionVariables():
            columns.append(SolutionVariableColumn(var, searchable=True))
        return columns

    @staticmethod
    def getStateColumn(addtl_id=None):
        from cs.vp.variants.apps.generatorui import AdditionalColumn
        filter_values = []
        if addtl_id is None:
            filter_values = [SyncStatus.ok.name,
                             SyncStatus.new.name,
                             SyncStatus.invalid.name,
                             SyncStatus.manual.name,
                             SyncStatus.incomplete.name]
        name = "state" if addtl_id is None else "state_%s" % addtl_id
        return AdditionalColumn(name, util.get_label("cdbvp_state"), filter_values)

    @staticmethod
    def getHiddenToolbarButtonIds():
        return []

    @staticmethod
    def getDisabledToolbarButtonIds():
        return []

    @staticmethod
    def showProductInfo():
        return False

    def getProduct(self):
        return None

    def getMaxboms(self):
        return []


class ProductAdapter(VariantTableAdapter):

    def __init__(self, product):
        super(ProductAdapter, self).__init__()
        self._product = product

    def getTitle(self):
        return self._product.GetDescription()

    def makeSolver(self):
        return BasicVPMSolver(self._product, self._product.VariantDrivingProperties)

    def makePager(self):
        from cs.vp.variants.pagers import CombinedPager
        return CombinedPager(self.getSolver(), self._product.Variants, forward_solved_pages=5)

    def compute_result(self, presettings=None, addtl_search_args=None, page_size=0, start_row=0):
        result, metrics = super(ProductAdapter, self).compute_result(presettings, addtl_search_args, page_size, start_row)
        item_dmsg = gui.Message.ByName('cdbvp_item_description_in_ve')
        item_dtag = item_dmsg.Text[''] if item_dmsg else None

        # add additional attributes
        for r in result:
            obj = r[1].variant_object
            r[1].generator_infos["id"] = self._make_hyperlink(obj, "CDB_ShowObject", obj.id) if obj else ""

            if obj:
                name = getattr(obj, "name", "")
                if obj.CheckAccess("save"):
                    r[1].generator_infos["name"] = '<div class="editable">%s</div>' % name
                else:
                    r[1].generator_infos["name"] = name
            else:
                r[1].generator_infos["name"] = ""

            # für persistente varianten die ausgeprägten Artikel anzeigen
            state_obj = _get_syncstatus_from_text(r[1].state)
            product = getattr(obj, "Product", None)
            if state_obj and state_obj != SyncStatus.new and product is not None:
                items_html = ""
                for partref in obj.PartsRefs:
                    part = partref.Part
                    if part and partref.MaxBOM in product.MaxBoms:
                        display_text = None
                        accessor = _PartReferenceAttributeAccessor(partref)
                        if item_dtag:
                            display_text = parse_raw(item_dtag) % accessor

                        items_html += "<span data-maxbom=\"%s\">%s</span>" % (
                            "%(max_bom_teilenummer)s#%(max_bom_t_index)s" % accessor,
                            self._make_hyperlink(part, "CDB_ShowObject", display_text=display_text)
                        )
                        items_html += "<br>"
                r[1].generator_infos["items"] = items_html
            else:
                r[1].generator_infos["items"] = ""
        return result, metrics

    def getAdditionalColumns(self):
        from cs.vp.variants.apps.generatorui import AdditionalColumn
        columns = super(ProductAdapter, self).getAdditionalColumns()
        cols = [("id", util.get_label("cdbvp_id")),
                ("name", util.get_label("cdbvp_name")),
                ("items", util.get_label("cdbvp_part"))]
        for name, label in cols:
            columns.append(AdditionalColumn(name, label))
        return columns

    def get_views(self):
        return self._product.Views

    def sync_new(self, variant, variant_info, context=None):
        variant_values = {}
        for prop in self._product.VariantDrivingProperties:
            variant_values[prop.id] = variant[prop.id]
        signature = self.getSolver().getFilteredSolutionSignature(variant_values)

        v = fProductVariant.CreateVariant(variant_values,
                                          clear_generator_cache=False,
                                          product_object_id=self._product.cdb_object_id,
                                          solver_status=SyncStatus.ok.value,
                                          signature=signature)
        return v

    def getFilterSolution(self, outer_sol):
        max_bom_view = self._product.MaxBOMView

        if max_bom_view:
            combined_adapter = CombinedViewAdapter(self._product, [max_bom_view])
            solutions = [sol[1] for sol in combined_adapter.getSolver().iterate_combined(outer_sol)]

            if (len(solutions) != 1 or
                InnerProblem.MISSING_INNER_SOLUTION_VALUE in solutions[0].values() or
                    InnerProblem.UNDEFINED_INNER_SOLUTION_VALUE in solutions[0].values()):
                return None
            solution = solutions[0]
        else:
            solution = outer_sol

        return self._product.cdb_object_id + ";" + ",".join(["%s:%s" % pair for pair in solution.items()])

    def createManualVariant(self, variant_values):
        obj = None
        if self.getSolver().containsAllVariables(variant_values, True):
            signature = self.getSolver().getFilteredSolutionSignature(variant_values)
            # check existence
            obj = fProductVariant.BySignature(self._product.cdb_object_id, signature)
            if not obj:
                solver_status = SyncStatus.manual.value
                if self.getSolver().validate(variant_values):
                    solver_status = SyncStatus.ok.value

                obj = fProductVariant.CreateVariant(variant_values,
                                                    product_object_id=self._product.cdb_object_id,
                                                    solver_status=solver_status,
                                                    signature=signature)

                if solver_status == SyncStatus.manual.value:
                    constraints = obj.get_violated_constraints()
                    obj._generate_links_to_violated_constraints(constraints)

        return obj

    def showProductInfo(self):
        return True

    def getProduct(self):
        return self._product

    def getMaxboms(self):
        return self._product.MaxBoms


class CombinedViewAdapter(ProductAdapter):

    def __init__(self, product, inner_views=None):
        self._inner_views = inner_views if inner_views is not None else []
        super(CombinedViewAdapter, self).__init__(product)

    def makeSolver(self):
        inner_prop_sets = []
        for v in self._inner_views:
            inner_prop_sets.append(v.VariantDrivingProperties)

        return NestedVPMSolver(self._product,
                               self._product.VariantDrivingProperties,
                               inner_prop_sets)

    def makePager(self):
        from cs.vp.variants.pagers import CombinedPager
        return CombinedPager(self.getSolver(), self._product.Variants, forward_solved_pages=5)

    def get_inner_views(self):
        return self._inner_views

    def _make_link_icon(self, status):
        state_index = -1
        try:
            state_obj = eval("MappingStatus.%s" % status)
            state_index = state_obj.value
        except AttributeError:
            pass
        return '<img src="%simages/link_%s.png" title="%s" width=16 height=16>' % (self._get_image_path(), state_index, str(state_obj.name))

    def compute_result(self, presettings=None, addtl_search_args=None, page_size=0, start_row=0):
        result, metrics = super(CombinedViewAdapter, self).compute_result(presettings, addtl_search_args, page_size, start_row)

        # add data for inner solutions
        for r in result:
            for i, _inner_problem in enumerate(self.getSolver().inner_problems):
                # state icon
                state_col = "state_%s" % i
                if r[1].inner_variant_infos[i].state:
                    r[1].generator_infos[state_col] = self._make_status_icon(r[1].inner_variant_infos[i].state)
                else:
                    r[1].generator_infos[state_col] = ""
                # mapping state icon
                mapping_state_col = "mapping_state_%s" % i
                mapping_state_icon_col = "mapping_state_icon_%s" % i
                if r[1].generator_infos[mapping_state_col]:
                    r[1].generator_infos[mapping_state_icon_col] = self._make_link_icon(r[1].generator_infos[mapping_state_col])
                else:
                    r[1].generator_infos[mapping_state_icon_col] = ""
                # inner variant id
                inner_id_col = "inner_id_%s" % i
                obj = r[1].inner_variant_infos[i].variant_object
                if obj:
                    r[1].generator_infos[inner_id_col] = self._make_hyperlink(obj, "CDB_ShowObject", obj.id) if obj else ""
                else:
                    r[1].generator_infos[inner_id_col] = ""

        # add/update metrics
        metrics["n_views"] = len(self._inner_views)
        return result, metrics

    def getAdditionalColumns(self):
        from cs.vp.variants.apps.generatorui import AdditionalColumn
        columns = super(CombinedViewAdapter, self).getAdditionalColumns()
        cols = [("outer_solution_number", "#")]
        for name, label in cols:
            columns.append(AdditionalColumn(name, label))
        return columns

    def getSolutionVariableColumns(self):
        from cs.vp.variants.apps.generatorui import SolutionVariableColumn, AdditionalColumn
        columns = super(CombinedViewAdapter, self).getSolutionVariableColumns()

        # add columns for inner solutions
        for i, inner_problem in enumerate(self.getSolver().inner_problems):
            columns.append(AdditionalColumn("mapping_state_icon_%s" % i,
                                            util.get_label("cdbvp_mapping")))
            # [MappingStatus.ok.name,
            #  MappingStatus.new.name,
            #  MappingStatus.invalid.name,
            #  MappingStatus.manual.name]))
            columns.append(self.getStateColumn(i))
            columns.append(AdditionalColumn("inner_id_%s" % i,
                                            util.get_label("cdbvp_id")))

            for var in inner_problem.getVariables():
                columns.append(SolutionVariableColumn(var, searchable=True))
        return columns

    def getFilterSolution(self, outer_sol):
        max_bom_view = self._product.MaxBOMView

        if max_bom_view and (max_bom_view.id in [view.id for view in self._inner_views]):
            max_bom_properties = [prop.id for prop in max_bom_view.Properties]
            filter_solution = {id: outer_sol[id] for id in outer_sol.keys() if id in max_bom_properties}
            if (not filter_solution or
                InnerProblem.MISSING_INNER_SOLUTION_VALUE in filter_solution.values() or
                    InnerProblem.UNDEFINED_INNER_SOLUTION_VALUE in filter_solution.values()):
                return None
            else:
                return self._product.cdb_object_id + ";" + ",".join(["%s:%s" % pair for pair in filter_solution.items()])
        else:
            return super(CombinedViewAdapter, self).getFilterSolution(outer_sol)

    def sync_variants(self, variants):
        context = {}
        context["created_variants"] = {}
        for v in variants:
            self.sync_variant(*v, context=context)

    def sync_variant(self, variant, variant_info, context=None):
        # Kopfvariante synchronisieren
        head_variant_obj = super(CombinedViewAdapter, self).sync_variant(variant, variant_info, context)

        # Varianten der Sichten synchronisieren
        self.sync_inner_variants(head_variant_obj, variant, variant_info, context)
        return head_variant_obj

    def sync_inner_variants(self, head_variant_obj, variant, variant_info, context):
        for i, inner_problem in enumerate(self.getSolver().inner_problems):
            inner_variant_info = variant_info.inner_variant_infos[i]
            inner_variant = inner_problem.extract(variant)
            if inner_variant:
                f = getattr(self, "sync_inner_" + inner_variant_info.state)
                inner_variant_obj = f(head_variant_obj, inner_problem, inner_variant, inner_variant_info, context)
                # update variant mapping
                mapping_state = variant_info.generator_infos["mapping_state_%s" % i]
                if mapping_state == MappingStatus.new.name:
                    view_id = inner_problem.inner_variables[0].getProperty().view_id
                    fVariantMapping.Create(product_object_id=self._product.cdb_object_id,
                                           variant_id=head_variant_obj.id,
                                           view_variant_id=inner_variant_obj.id,
                                           view_id=view_id,
                                           manual=0)

    def sync_inner_new(self, head_variant_obj, inner_problem, inner_variant, inner_variant_info, context):
        # Variante in der Sicht anlegen
        view_id = inner_problem.inner_variables[0].getProperty().view_id
        checksum, signature = inner_problem.getSolutionChecksum(inner_variant)

        # Variante kann schon angelegt sein, da die selbe innere Variante
        # für mehrere äußere Varianten gelten kann und innerhalb eines
        # Speichervorganges dann schon für eine andere äußere Variante angelegt wurde.
        v = context["created_variants"].get(checksum, None)

        if not v:
            v = fViewVariant.CreateVariant(inner_variant,
                                           product_object_id=self._product.cdb_object_id,
                                           view_id=view_id,
                                           solver_status=SyncStatus.ok.value,
                                           signature=signature)
            context["created_variants"][checksum] = v
        return v

    @staticmethod
    def sync_inner_ok(head_variant_obj, inner_problem, inner_variant, inner_variant_info, context):
        if not inner_variant_info.variant_object.solver_status == SyncStatus.ok.value:
            inner_variant_info.variant_object.solver_status = SyncStatus.ok.value
        return inner_variant_info.variant_object

    @staticmethod
    def sync_inner_invalid(head_variant_obj, inner_problem, inner_variant, inner_variant_info, context):
        if not inner_variant_info.variant_object.solver_status == SyncStatus.invalid.value:
            inner_variant_info.variant_object.solver_status = SyncStatus.invalid.value
        return inner_variant_info.variant_object

    @staticmethod
    def sync_inner_manual(self, head_variant_obj, inner_problem, inner_variant, inner_variant_info, context):
        return inner_variant_info.variant_object

    def createManualVariant(self, variant_values):
        outer_variant_obj = None
        outer_variant_dict = self.getSolver().extract(variant_values)
        if outer_variant_dict:
            outer_variant_obj = super(CombinedViewAdapter, self).createManualVariant(outer_variant_dict)

        if outer_variant_obj:
            for inner_problem in self.getSolver().inner_problems:
                inner_variant_dict = inner_problem.extract(variant_values)
                if inner_variant_dict:
                    view_id = inner_problem.inner_variables[0].getProperty().view_id
                    inner_signature = BasicVPMSolver.getSolutionSignature(inner_variant_dict)
                    inner_variant_obj = fViewVariant.BySignature(self._product.cdb_object_id, inner_signature)
                    if not inner_variant_obj:
                        # Validate and create inner variant with status manual or ok depending on the validation result
                        solver_status = SyncStatus.manual.value
                        if inner_problem.validateStandalone(inner_variant_dict):
                            solver_status = SyncStatus.ok.value
                        inner_variant_obj = fViewVariant.CreateVariant(inner_variant_dict,
                                                                       product_object_id=self._product.cdb_object_id,
                                                                       view_id=view_id,
                                                                       solver_status=solver_status,
                                                                       signature=inner_signature)

                        if solver_status == SyncStatus.manual.value:
                            constraints = inner_variant_obj.get_violated_constraints()
                            inner_variant_obj._generate_links_to_violated_constraints(constraints)

                    # create mapping to outer variant
                    fVariantMapping.Create(product_object_id=self._product.cdb_object_id,
                                           variant_id=outer_variant_obj.id,
                                           view_variant_id=inner_variant_obj.id,
                                           view_id=view_id,
                                           manual=1)
        return outer_variant_obj


class CombinedFilteredAdapter(CombinedViewAdapter):
    def __init__(self, product, inner_views=None, hidden_props=None):
        super(CombinedFilteredAdapter, self).__init__(product, inner_views)
        self._hidden_props = hidden_props if hidden_props is not None else []

    def makeSolver(self):
        inner_prop_sets = []
        for v in self._inner_views:
            inner_prop_sets.append(v.VariantDrivingProperties)

        return NestedVPMFilteredSolver(self._product,
                                       self._product.VariantDrivingProperties,
                                       inner_prop_sets,
                                       self._hidden_props)

    def makePager(self):
        from cs.vp.variants.pagers import CombinedPager
        pager = CombinedPager(self.getSolver(), self._product.Variants,
                              forward_solved_pages=5)

        return pager

    def getSolutionVariableColumns(self):
        from cs.vp.variants.apps.generatorui import SolutionVariableColumn, AdditionalColumn
        # HINT: Not calling the direct parent class is a feature, not an accident here!
        columns = super(CombinedViewAdapter, self).getSolutionVariableColumns()

        # add columns for inner solutions
        for i, inner_problem in enumerate(self.getSolver().inner_problems):
            columns.append(AdditionalColumn("number_of_variants_%s" % i,
                                            util.get_label("cdbvp_number_of_variants")))

            for var in inner_problem.getVariables():
                if var._id not in self._hidden_props:
                    columns.append(SolutionVariableColumn(var, searchable=True))
        return columns

    def compute_result(self, presettings=None, addtl_search_args=None, page_size=0, start_row=0):
        # HINT: Not calling the direct parent class is a feature, not an accident here!
        result, metrics = super(CombinedViewAdapter, self).compute_result(presettings, addtl_search_args, page_size, start_row)

        solver = self.getSolver()

        # add data for inner solutions
        for r in result:
            for i, _inner_problem in enumerate(self.getSolver().inner_problems):
                signature = solver.getFilteredSignature(r[0])

                # number of variants
                number_of_variants = "number_of_variants_%s" % i
                if _inner_problem.getFilteredSolutionSignature(r[0]):
                    r[1].generator_infos[number_of_variants] = \
                            solver._visited.get(signature, 0)
                else:
                    r[1].generator_infos[number_of_variants] = ""

        return result, metrics

    def sync_variant(self, variant, variant_info, context):
        raise util.ErrorMessage("cdbvp_ve_context_err")

    def getDisabledToolbarButtonIds(self):
        return ["save_button", "delete_saved_variants", "exclude_variants",
                "show_in_catia_button", "show_bom_button",
                "show_bom_report_button", "show_bom_comparison_button"]


class ViewAdapter(VariantTableAdapter):

    def __init__(self, product, view):
        super(ViewAdapter, self).__init__()
        self._product = product
        self._view = view

    def getTitle(self):
        return "%s - %s" % (self._product.GetDescription(),
                            self._view.GetDescription())

    def makeSolver(self):
        view_props = list(self._view.VariantDrivingProperties)
        return BasicVPMSolver(self._product, view_props + list(self._product.VariantDrivingProperties), view_props)

    def makePager(self):
        from cs.vp.variants.pagers import CombinedPager
        return CombinedPager(self.getSolver(), self._view.Variants, forward_solved_pages=5)

    def compute_result(self, presettings=None, addtl_search_args=None, page_size=0, start_row=0):
        result, metrics = super(ViewAdapter, self).compute_result(presettings, addtl_search_args, page_size, start_row)
        # add additional attributes
        for r in result:
            obj = r[1].variant_object
            r[1].generator_infos["id"] = self._make_hyperlink(obj, "CDB_ShowObject", obj.id) if obj else ""
            r[1].generator_infos["name"] = obj.name if obj else ""

        # add additional metrics
        metrics["n_views"] = 1
        return result, metrics

    def getAdditionalColumns(self):
        from cs.vp.variants.apps.generatorui import AdditionalColumn
        columns = super(ViewAdapter, self).getAdditionalColumns()
        cols = [("id", util.get_label("cdbvp_id")),
                ("name", util.get_label("cdbvp_name"))]
        for name, label in cols:
            columns.append(AdditionalColumn(name, label))
        return columns

    def sync_new(self, variant, variant_info, context=None):
        signature = self.getSolver().getSolutionSignature(variant)
        v = fViewVariant.CreateVariant(variant,
                                       product_object_id=self._view.product_object_id,
                                       view_id=self._view.id,
                                       solver_status=SyncStatus.ok.value,
                                       signature=signature)
        return v

    def createManualVariant(self, variant_values):
        obj = None
        if self.getSolver().containsAllVariables(variant_values, True):
            signature = self.getSolver().getFilteredSolutionSignature(variant_values)
            # check existence
            obj = fViewVariant.BySignature(self._product.cdb_object_id, signature)
            if not obj:
                obj = fViewVariant.CreateVariant(variant_values,
                                                 product_object_id=self._product.cdb_object_id,
                                                 view_id=self._view.id,
                                                 solver_status=SyncStatus.manual.value,
                                                 signature=signature)

                constraints = obj.get_violated_constraints()
                obj._generate_links_to_violated_constraints(constraints)

        return obj

    def getFilterSolution(self, outer_sol):
        from cs.vp.variants.pagers import CombinedPager

        if self._product.MaxBOMView and (self._product.MaxBOMView.id == self._view.id):
            # If self is the maxbom view, then outer_sol is already the filter
            # solution
            return self._product.cdb_object_id + ";" + ",".join(["%s:%s" % pair for pair in outer_sol.items()])
        else:
            # Otherwise we look for a unique mapping with a product variant

            # Compute all the product variants that map to outer_sol
            combined_adapter = CombinedViewAdapter(self._product, [self._view])
            pager = CombinedPager(combined_adapter.getSolver(), self._product.Variants,
                                  forward_solved_pages=0)
            solutions = [sol
                         for sol, _vinfo in
                         pager.nextpage(presettings=outer_sol, addtl_args={},
                                        page_size=2, start_row=0)]

            if (len(solutions) != 1 or
                InnerProblem.MISSING_INNER_SOLUTION_VALUE in solutions[0].values() or
                    InnerProblem.UNDEFINED_INNER_SOLUTION_VALUE in solutions[0].values()):
                return None
            else:
                # If outer_sol maps to a unique product variant,
                # we compute the filter solution from that
                solution = solutions[0]
                product_adapter = ProductAdapter(self._product)
                return product_adapter.getFilterSolution(solution)

    def showProductInfo(self):
        return True

    def getProduct(self):
        return self._product

    def getMaxboms(self):
        return self._product.MaxBoms


class PropertyAdapter(VariantTableAdapter):

    def __init__(self, prop):
        super(PropertyAdapter, self).__init__()
        self._property = prop
        self._product = prop.Product

    def getTitle(self):
        return "%s - %s" % (self._property.Product.GetDescription(),
                            self._property.GetDescription())

    def makeSolver(self):
        return BasicVPMSolver(self._property.Product, self._property.AttachedProperties)

    def makePager(self):
        from cs.vp.variants.pagers import CombinedPager
        return CombinedPager(self.getSolver(), self._property.EnumValues, forward_solved_pages=5)

    def compute_result(self, presettings=None, addtl_search_args=None, page_size=0, start_row=0):
        result, metrics = super(PropertyAdapter, self).compute_result(presettings, addtl_search_args, page_size, start_row)

        # add additional attributes
        for r in result:
            r[1].generator_infos["name"] = r[1].variant_object.ValueText[''] if r[1].variant_object else ""

        return result, metrics

    def getAdditionalColumns(self):
        from cs.vp.variants.apps.generatorui import AdditionalColumn
        columns = super(PropertyAdapter, self).getAdditionalColumns()
        columns.append(AdditionalColumn("name", util.get_label("cdbvp_name")))
        return columns

    def sync_new(self, variant, variant_info, context=None):
        signature = self.getSolver().getSolutionSignature(variant)
        enum_def = fEnumDefinition.CreateGenerated(product_object_id=self._property.product_object_id,
                                                   id=self._property.id,
                                                   signature=signature)
        for prop in self._property.AttachedProperties:
            fEnumDefPropertyValue\
                    .CreateWithChangeLog(product_object_id=self._property.product_object_id,
                                         property_id=self._property.id,
                                         property_value=enum_def.value,
                                         rated_property_id=prop.id,
                                         rated_property_value=variant[prop.id])

        from cdb.objects import resolve
        VT = resolve(fEnumDefinition.ValueText)
        args = {}
        for lang in VT.keys():
            args[VT[lang].name] = enum_def.generate_name(lang)
        args["name"] = enum_def.generate_erp_name()

        enum_def.Update(**args)

    def getHiddenToolbarButtonIds(self):
        return ["show_bom_button", "export_csv", "create_manual_variant", "show_in_catia_button",
                "show_bom_report_button", "show_bom_comparison_button", "exclude_variants"]


class _PartReferenceAttributeAccessor(object):
    _ATTRS = ["max_bom_teilenummer",
              "max_bom_t_index",
              "variant_id",
              "product_object_id"]

    def __init__(self, partref):
        self.partref = partref
        self.item = partref.Part

    def __getitem__(self, name):
        if name in self._ATTRS:
            obj = self.partref
        else:
            obj = self.item

        v = obj.__getitem__(name)
        if v == NULL:
            return ""
        else:
            if isinstance(v, str):
                return str(v)
            return v
