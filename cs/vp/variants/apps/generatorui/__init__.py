#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module generatorui
"""

from cdb import CADDOK
from cdb import cdbuuid
from cdb import constants
from cdb import elink
from cdb import fls
from cdb import ue
from cdb import util
from cdb.objects import ByID
from cdb.objects.operations import operation
from collections import namedtuple
import json
import os

from cs.shared.elink_plugins.picture_uploader import PictureUploader
from cs.vp.variants.properties import Property
from cs.vp.products import Product
from cs.vp.variants import Variant
from cs.vp.variants import productviews as ProductViews
from cs.vp.variants.filter import CatiaRemoteControl
from cs.vp.variants.util import VariantInfoTextGenerator


__docformat__ = "restructuredtext en"

# Exported objects
__all__ = []

RowInfo = namedtuple("RowInfo", "rownum cells")


class DataTableInfo(object):
    def __init__(self, columns):
        self._columns = columns

    def getColumnNames(self):
        return [col.name for col in self._columns]

    def getColumns(self):
        return self._columns

    def getColumn(self, index):
        return self._columns[index]

    def getColumnFilterValues(self):
        result = []
        for col in self._columns:
            result.append(col.getColumnFilterValues())
        return result


class DataTableColumn(object):
    def __init__(self, key, name):
        self.key = key
        self.name = name

    def getDisplayValue(self, variant, variant_info):
        pass

    def getColumnFilterValues(self):
        pass


class SolutionVariableColumn(DataTableColumn):
    def __init__(self, solution_variable, searchable):
        super(SolutionVariableColumn, self).__init__(solution_variable.getId(),
                                                     solution_variable.getName())
        self.solution_variable = solution_variable
        self.searchable = searchable

    def getDisplayValue(self, variant, variant_info):
        return self.solution_variable.getValueName(variant.get(self.key, None))

    def getColumnFilterValues(self):
        if self.searchable:
            return self.solution_variable.getValueNames()
        else:
            return []

    def isSolutionColumn(self):
        return True


class AdditionalColumn(DataTableColumn):

    def __init__(self, key, name, filter_values=[]):
        super(AdditionalColumn, self).__init__(key, name)
        self._filter_values = filter_values

    def getDisplayValue(self, variant, variant_info):
        return variant_info.generator_infos.get(self.key, "'%s' is missing in variant info" % self.key)

    def getColumnFilterValues(self):
        return self._filter_values

    def isSolutionColumn(self):
        return False


def setup(state, **kwargs):

    # get generator
    generator = state.context_object.getVariantTableAdapter(**kwargs)
    state.generator = generator

    # Setup data table info
    data_table_info = DataTableInfo(generator.getDataTableColumns())
    state.data_table_info = data_table_info

    # initialize additional state data
    state.grid_data_mapping = {}


# Application pages
class ProductViewPage(elink.Template):
    __template__ = "productview.html"

    labels = ["cdbvp_elink_reload",
              "cdbvp_elink_toggle_md",
              "cdbvp_elink_show_result_footer",
              "cdbvp_elink_show_solution_size",
              "cdbvp_elink_show_prop_footer",
              "cdbvp_elink_show_view_footer",
              "cdbvp_elink_prev_footer",
              "cdbvp_elink_next_footer",
              "cdbvp_elink_first_footer",
              "cdbvp_elink_last_footer",
              "cdbvp_elink_info_footer",
              "cdbvp_elink_menu_entries",
              "cdbvp_variant_name_placeholder",
              "cdbvp_confirm_delete_variants"]

    def set_product_image(self):
        product = ByID(self.request.form_data["cdb_object_id"])
        # Using preview image mechanism(save picture as CDBFile to object).
        return PictureUploader.set_image(self.request,
                                         product,
                                         max_size=220)

    def _get_labels(self):
        labels = {}
        for label in self.labels:
            labels[label] = util.get_label(label)
        return labels

    def _get_vecf_prop(self):
        prop = util.get_prop('vecf')
        if prop is not None:
            if prop.lower() == 'true':
                return True
            else:
                return False
        else:
            return None

    def render(self, context, cdb_object_id, embedded="0"):
        self.request.charset = "utf-8"

        init_msg = []
        if self.request.upstreams:
            init_msg = self.set_product_image()

        # setup a state object to keep all information
        # for later JSON-calls
        state = self.application.addState()
        obj = ByID(cdb_object_id)
        state.context_object = obj
        setup(state)
        if state and state.generator:
            product = state.generator._product
            if product.CheckAccess("read"):
                context.state_id = state.state_id
                context.title = state.generator.getTitle()
                context.page_title = util.get_label('cdbvp_variant_editor_title') % context.title
                context.json_data_url = self.application.getModuleURL() + \
                                        "view/json_load_table_data"

                context.show_product_info = state.generator.showProductInfo()
                context.product = state.generator.getProduct()
                context.maxboms = state.generator.getMaxboms()
                context.readable = True
            else:
                context.readable = False

        try:
            embedded = int(embedded)
        except ValueError:
            embedded = 0

        if isinstance(state.context_object, ProductViews.ProductView):
            obj_type = "view"
        elif isinstance(state.context_object, Product):
            obj_type = "product"
        elif isinstance(state.context_object, Property):
            obj_type = "property"
        else:
            obj_type = ""

        return {"get_preview_img": PictureUploader.get_preview_img,
                "elink_startup_cdb_messages": init_msg,
                "labels": json.dumps(self._get_labels()),
                "vecf": json.dumps(self._get_vecf_prop()),
                "plugins": sorted(_PLUGINS,
                                  key=lambda plugin: ((-1) * plugin["position"],
                                                      plugin["json_name"])),
                "embedded": embedded,
                "obj_type": obj_type
                }

    render.view_id = int


class CADControlPage(elink.Resource):
    def render(self, state_id):
        app_state = self.application.getState(state_id)
        if app_state and app_state.generator:
            product = app_state.generator._product
            if product.CheckAccess("read"):
                self.extra_http_header("Content-Disposition", "attachment; filename=cad.cadmsg")
                self.content_type("text/vnd.contact.cad")
                for line in app_state.catia_ctrl:
                    self.write(line + "\n")
            else:
                self.content_type("text/plain")


class ApplicationState():
    """
    Container for application states. Instances are
    only created and managed by the ApplicationStateManager.
    """

    def __init__(self):
        self.state_id = cdbuuid.create_uuid()


class ApplicationStateManager():
    """
    Simple application state manager, which
    uses a LRU list with a maximum limit of states to be
    hold in memory.
    If the limit exeeds by adding a new state, the
    most unused state will be removed.
    """

    def __init__(self, max_states):
        self.max_states = max_states
        self.states = {}
        self.lru = []

    def addState(self):
        state = ApplicationState()
        self.states[state.state_id] = state
        self.lru.append(state.state_id)
        to_delete = self.lru[:-self.max_states]
        for del_id in to_delete:
            if del_id in self.states:
                del self.states[del_id]
        del self.lru[:len(to_delete)]
        return state

    def getState(self, state_id):
        try:
            del self.lru[self.lru.index(state_id)]
        except ValueError:
            pass
        state = self.states.get(state_id, None)
        if state:
            self.lru.append(state_id)
        return state


@elink.using_template_engine("chameleon")
class VPApplication(elink.Application):
    def __init__(self):
        super(VPApplication, self).__init__("VPM")
        self.add("view", ProductViewPage())
        self.add("cad.cadmsg", CADControlPage())
        self.addJSON(self.grid_sync)
        self.addJSON(self.json_get_column_filter_values)
        self.addJSON(self.json_load_table_data)
        self.addJSON(self.json_view_selected)
        self.addJSON(self.json_get_columns)
        self.addJSON(self.json_get_column_infos)
        self.addJSON(self.json_get_views)
        self.addJSON(self.json_get_view_properties)
        self.addJSON(self.json_hide_properties)
        self.addJSON(self.show_filtered_bom)
        self.addJSON(self.show_bom_report)
        self.addJSON(self.show_bom_comparison)
        self.addJSON(self.create_manual_variant)
        self.addJSON(self.json_get_hidden_toolbarbuttons)
        self.addJSON(self.json_get_disabled_toolbarbuttons)
        self.addJSON(self.table_reload)
        self.addJSON(self.delete_variants)
        self.addJSON(self.instantiate_max_bom)
        self.addJSON(self.export_csv)
        self.addJSON(self.exclude_variants_from_solution_space)
        self.addJSON(self.edit_variant_name)

        for plugin in _PLUGINS:
            self.addJSON(plugin["json"], plugin["json_name"])

        self.state_manager = ApplicationStateManager(10)

    def addState(self):
        return self.state_manager.addState()

    def getState(self, state_id):
        state = self.state_manager.getState(state_id)
        if state and state.generator:
            product = state.generator._product
            if not product.CheckAccess("read"):
                raise util.ErrorMessage("w3_nopermission")
        return self.state_manager.getState(state_id)

    def grid_sync(self, state_id, selected_rows):
        if type(selected_rows) != list:
            selected_rows = [selected_rows]
        state = self.getState(state_id)
        if state:
            variants = []
            for r in selected_rows:
                variants.append(state.grid_data_mapping[int(r)])
            try:
                state.generator.sync_variants(variants)
            except KeyError:
                raise util.ErrorMessage("cdbvp_variant_model_changed")
            except RuntimeError as ex:
                raise util.ErrorMessage("just_a_replacement", str(ex))
            finally:
                VariantInfoTextGenerator().clear_cache()
            self._table_reload(state)
        else:
            # FIXME: Error handling if state is not available any more
            pass

    def json_load_table_data(self, **args):
        state_id = args["state_id"]
        app_state = self.getState(state_id)

        # Args for pagination
        sEcho = args["sEcho"]
        iDisplayLength = int(args["iDisplayLength"])
        iDisplayStart = int(args["iDisplayStart"])

        # Extract search args
        variant_presettings = {}
        addtl_search_args = {}
        for i, col in enumerate(app_state.data_table_info.getColumns()):
            searchable = args["bSearchable_%s" % (i)]
            search_val = args["sSearch_%s" % (i)]

            if searchable and search_val:
                if isinstance(col, SolutionVariableColumn):
                    variant_presettings[col.key] = col.solution_variable.getValueByName(search_val)
                else:
                    addtl_search_args[col.key] = search_val

        # for k,v in variant_presettings.items():
        #    misc.cdblogv(misc.kLogErr, 0, "  %s: %s" % (k,v))

        # app_state = self.getState(state_id)
        data, metrics = self.compute_variant_table(app_state,
                                                   variant_presettings,
                                                   addtl_search_args,
                                                   page_size=iDisplayLength,
                                                   start_row=iDisplayStart)

        # Note: sEcho is a draw count of the data table which must be increased.
        # Else the data table wouldn't redrawed.
        response = {"grid_data": data,
                    "metrics": metrics,
                    "sEcho": int(sEcho) + 1,
                    "iTotalRecords": metrics["iTotalRecords"],  # unfiltered result
                    "iTotalDisplayRecords": metrics["iTotalRecords"]}  # FIXME: filtered overall result
        return response

    def compute_variant_table(self, app_state, variant_presettings={}, addtl_search_args={}, page_size=0, start_row=0):

        # solve variants
        variants, generator_metrics = app_state.generator.compute_result(variant_presettings,
                                                                         addtl_search_args,
                                                                         page_size,
                                                                         start_row)
        # clear cached grid data, if pager has been resetted
        # (e.g. due to changed search arguments)
        if generator_metrics.get("pager_resetted", False):
            app_state.grid_data_mapping = {}

        # build result
        data = []
        rownum = start_row
        for variant, variant_info in variants:
            row = {}
            for colnum, col in enumerate(app_state.data_table_info.getColumns()):
                row[colnum] = col.getDisplayValue(variant, variant_info)
            row["DT_RowId"] = "%d" % (rownum)

            app_state.grid_data_mapping[rownum] = (variant, variant_info)
            data.append(row)
            rownum += 1

        return (data, generator_metrics)

    def json_get_column_filter_values(self, state_id):
        app_state = self.getState(state_id)
        result = {"filter_values": list(map(sorted, app_state.data_table_info.getColumnFilterValues())),
                  "is_solution_column": [col.isSolutionColumn()
                                         for col in app_state.data_table_info.getColumns()]}

        return result

    def json_view_selected(self, state_id, views):
        if type(views) != list:
            views = [views]
        view_ids = [int(v) for v in views if v]

        app_state = self.getState(state_id)
        setup(app_state, views=view_ids)
        return self.json_get_column_infos(state_id)

    def json_get_columns(self, state_id):
        app_state = self.getState(state_id)
        return app_state.data_table_info.getColumnNames()

    def json_get_column_infos(self, state_id):
        app_state = self.getState(state_id)
        col_infos = []
        for col in app_state.data_table_info._columns:
            col_infos.append({"id": col.key, "name": col.name})
        return {"result": col_infos}

    def json_get_views(self, state_id):
        app_state = self.getState(state_id)
        result = {}
        selectable_views = []
        for v in app_state.generator.get_views():
            if v.Properties:
                selectable_views.append((v.id, v.Name['']))
        result["selectable_views"] = selectable_views
        return result

    def json_get_view_properties(self, state_id, view_ids):
        if isinstance(view_ids, str):
            view_ids = [int(view_ids)] if view_ids != "" else []
        else:
            view_ids = [int(view_id) for view_id in view_ids if view_id != ""]

        app_state = self.getState(state_id)
        product = app_state.generator._product

        result = []
        if view_ids:
            views = ProductViews.ProductView\
                    .KeywordQuery(product_object_id=product.cdb_object_id)\
                    .Query(ProductViews.ProductView.id.one_of(*view_ids), access="read")

            if views:
                result = [[(prop.id, prop.Name[''],
                            prop.id in app_state.generator._hidden_props)
                           for prop in view.VariantDrivingProperties]
                          for view in views]

        return result

    def json_hide_properties(self, state_id, view_ids=[], hidden_props=[]):
        app_state = self.getState(state_id)

        if type(hidden_props) != list:
            hidden_props = [hidden_props]
        hidden_props = [int(prop_id) for prop_id in hidden_props if prop_id]

        if type(view_ids) != list:
            view_ids = [view_ids]
        view_ids = [int(v) for v in view_ids if v]

        setup(app_state, views=view_ids, hidden_props=hidden_props)
        return self.json_get_column_infos(state_id)

    def create_manual_variant(self, state_id, values):
        app_state = self.getState(state_id)
        variant_props = {}
        for i, col in enumerate(app_state.data_table_info.getColumns()):
            if isinstance(col, SolutionVariableColumn):
                variant_props[col.key] = col.solution_variable.getValueByName(values[i])
        try:
            app_state.generator.createManualVariant(variant_props)
        except RuntimeError as ex:
            raise util.ErrorMessage("just_a_replacement", str(ex))
        self._table_reload(app_state)

    def _table_reload(self, app_state):
        app_state.generator.resetPager()
        app_state.grid_data_mapping = {}

    def table_reload(self, state_id):
        app_state = self.getState(state_id)

        app_state.context_object.Reload()  # Needed to update the constraints

        views = [view.id for view in app_state.generator.get_inner_views()]
        setup(app_state, views=views,
              hidden_props=app_state.generator._hidden_props)

        return self.json_get_column_infos(state_id)

    def json_get_hidden_toolbarbuttons(self, state_id):
        app_state = self.getState(state_id)
        return app_state.generator.getHiddenToolbarButtonIds()

    def json_get_disabled_toolbarbuttons(self, state_id):
        app_state = self.getState(state_id)
        return app_state.generator.getDisabledToolbarButtonIds()

    def _get_inner_max_bom_variant(self, product, vinfo):
        """ In the case of a combined table with the MaxBOMView,
            returns the saved variant of the MaxBOMView, if any.
            Otherwise returns None.
        """
        var = vinfo.variant_object
        max_bom_view = product.MaxBOMView
        if var and var.View == max_bom_view:
            return var
        elif vinfo.inner_variant_infos:
            interior_variants = [ivar.variant_object
                                 for ivar in vinfo.inner_variant_infos
                                 if ivar.variant_object]
            filter_variants = [ivar for ivar in interior_variants
                               if ivar.View == max_bom_view]
            if len(filter_variants) == 1:
                return filter_variants[0]
        else:
            return None

    def _get_filter_variant(self, product, vinfo):
        """ Returns the mapped variant relative to the MaxBOMView,
            if it exists and if it's unique.
            Otherwise returns None.
        """
        if vinfo.variant_object:
            var = vinfo.variant_object
            fvar = self._get_inner_max_bom_variant(product, vinfo)
            if not fvar:
                max_bom_variants = var.get_max_bom_variants()
                if len(max_bom_variants) == 1:
                    return max_bom_variants[0]
            return fvar

    def _get_operation_url(self, state_id, selected_row, opname, selected_maxbom_oid):
        if type(selected_row) != list:
            state = self.getState(state_id)
            if state:
                generator = state.generator
                maxbom = self._get_maxbom(generator._product, selected_maxbom_oid)
                op_args = {"cdb::argument.maxbom_oid": maxbom.ID()}

                pvalues, vinfo = state.grid_data_mapping[int(selected_row)]

                var = self._get_filter_variant(generator._product, vinfo)
                if var:
                    # Found the saved variant for max bom filtering.
                    # Call the operation on the variant object.
                    url = var.MakeURL(opname, plain=0, **op_args)
                else:
                    # Try to solve the solution and call the operation on product level.
                    solution = generator.getFilterSolution(pvalues)
                    if solution:
                        op_args["cdb::argument.filter_id"] = solution
                        url = generator._product.MakeURL(opname, plain=0, **op_args)
                    else:
                        raise util.ErrorMessage("cdbvp_err_no_unique_mapping")
                return url

    def show_filtered_bom(self, state_id, selected_row, selected_maxbom_oid=None):
        return {"url": self._get_operation_url(state_id, selected_row,
                                               "cdbvp_filtered_bom",
                                               selected_maxbom_oid)}

    def _get_maxbom(self, product, selected_maxbom_oid):
        maxbom = None
        if selected_maxbom_oid:
            maxbom = ByID(selected_maxbom_oid)
            if not maxbom:
                raise util.ErrorMessage("just_a_replacement",
                                        "Unexpected error: "
                                        "Selected MaxBOM '%s' not found." % selected_maxbom_oid)
        elif len(product.ToplevelAssemblyLinks) == 1:
            maxbom = product.ToplevelAssemblyLinks[0].Item

        if maxbom is None:
                raise util.ErrorMessage("cdbvp_choose_a_maxbom2")
        return maxbom

    def show_bom_report(self, state_id, selected_row, selected_maxbom_oid=None):
        return {"url": self._get_operation_url(state_id, selected_row,
                                               "cdbvp_variant_bom_report",
                                               selected_maxbom_oid)}

    def show_bom_comparison(self, state_id, selected_rows, selected_maxbom_oid=None):
        state = self.getState(state_id)
        if state:
            generator = state.generator
            maxbom = self._get_maxbom(generator._product, selected_maxbom_oid)
            op_args = {"cdb::argument.maxbom_oid": maxbom.ID()}
            product_object_id = generator._product.cdb_object_id
            filter_args = [product_object_id]
            for row in selected_rows:
                pvalues, _vinfo = state.grid_data_mapping[int(row)]
                solution = generator.getFilterSolution(pvalues)
                if solution:
                    filter_args.append(solution.split(";")[1])
                else:
                    filter_args.append(None)

            if not all(filter_args):
                raise util.ErrorMessage("cdbvp_err_no_unique_mapping")

            op_args["cdb::argument.filter_id"] = ';'.join(filter_args)
            url = generator._product.MakeURL("cdbvp_bom_comparison", plain=0, **op_args)
            return {"url": url}

    def delete_variants(self, state_id, selected_rows):
        from cdb.platform import mom
        import cdbwrapc

        state = self.getState(state_id)
        if state:
            if not isinstance(selected_rows, list):
                # E055338: if there is only one row selected, 'selected_rows' is a string
                selected_rows = [selected_rows]

            for row in selected_rows:
                _pvalues, vinfo = state.grid_data_mapping[int(row)]
                if vinfo.variant_object:
                    # Using the kernel operation, because of access rights
                    # and references
                    op = cdbwrapc.Operation("CDB_Delete",
                                            vinfo.variant_object.ToObjectHandle(),
                                            mom.SimpleArguments())
                    try:
                        op.run()
                    except RuntimeError as ex:
                        raise util.ErrorMessage("just_a_replacement", str(ex))
            self._table_reload(state)

    def edit_variant_name(self, state_id, row, name):
        state = self.getState(state_id)
        if state:
            _, vinfo = state.grid_data_mapping[int(row)]
            if vinfo.variant_object:
                # Allocate license "Variants: Model Variability"
                fls.allocate_license("VARIANTS_003")
                try:
                    modified_variant_object = operation(constants.kOperationModify, vinfo.variant_object, name=name)
                except Exception as ex:
                    raise util.ErrorMessage("just_a_replacement", str(ex))
                return modified_variant_object.name

    def instantiate_max_bom(self, state_id, selected_row, selected_maxbom_oid=None):
        state = self.getState(state_id)
        if state:
            if type(selected_row) != list:
                generator = state.generator
                maxbom = self._get_maxbom(generator._product, selected_maxbom_oid)
                op_args = {"cdb::argument.maxbom_oid": maxbom.ID()}

                _pvalues, vinfo = state.grid_data_mapping[int(selected_row)]
                if not vinfo.variant_object:
                    raise util.ErrorMessage("cdbvp_all_saved_variants")
                else:
                    url = vinfo.variant_object.MakeURL("cdbvp_instantiate_max_bom",
                                                       plain=0,
                                                       **op_args)
                    return {"url": url}

    def export_csv(self, state_id, **args):
        # Extract search args
        variant_presettings = {}
        addtl_search_args = {}

        app_state = self.getState(state_id)
        for i, col in enumerate(app_state.data_table_info.getColumns()):
            cond = args["col_%s" % i]
            filtered = (cond != "")
            if filtered:
                if isinstance(col, SolutionVariableColumn):
                    variant_presettings[col.key] = col.solution_variable.getValueByName(cond)
                else:
                    addtl_search_args[col.key] = cond

        filename = os.path.join(CADDOK.TMPDIR, "cdbvp_ve_%s.csv" % state_id)
        app_state.generator.csv_export(variant_presettings,
                                       addtl_search_args,
                                       filename=filename)
        cmsg = Product.MakeCdbcmsg("cdbvp_upload_csv_to_client",
                                            filename=filename)

        url = cmsg.eLink_url()
        # url = app_state.generator._product.MakeURL("cdbvp_upload_csv_to_client", filename=filename)

        return {"url": url}

    def exclude_variants_from_solution_space(self, state_id, selected_rows):
        # Allocate license "Variants: Model Variability"
        fls.allocate_license("VARIANTS_003")

        if type(selected_rows) != list:
            selected_rows = [selected_rows]

        state = self.getState(state_id)

        if isinstance(state.context_object, ProductViews.ProductView):
            args = {"product_object_id": state.context_object.product_object_id,
                    "view_id": state.context_object.id}
        elif isinstance(state.context_object, Product):
            args = {"product_object_id": state.context_object.cdb_object_id,
                    "view_id": 0}
        else:
            raise util.ErrorMessage("cdbvp_function_not_available")

        if state:
            for row in selected_rows:
                pvalues, vinfo = state.grid_data_mapping[int(row)]
                if vinfo.state != "invalid":
                    if vinfo.variant_object:
                        vinfo.variant_object.make_invalid()
                    else:
                        Variant.exclude_from_solution_space(pvalues, **args)

    @classmethod
    def on_cdbvp_calculate_variants_now(cls, ctx):
        product_id = ctx.object.cdb_object_id
        url = cls.getModuleURL()
        url = url + "/product?product_id=%s" % product_id
        return ue.Url4Context(url)

    @classmethod
    def on_cdbvp_product_view_now(cls, ctx):
        url = cls.getModuleURL()
        url = url + "/view?cdb_object_id=%s" % ctx.object.cdb_object_id
        return ue.Url4Context(url)


# - plugins "show in CAD system" ----------------------------------------------

_PLUGINS = []


def register_plugin(plugin):
    """ Register a plugin for a button of the type "Show in .." in the
        variant editor

        :param plugin: a dictionary with the following keys
            - position     the position in the dropdown-menu,
                           ordered descending (optional)
            - icon         the name of the icon for the button
            - label        a cdb-label for the tooltip
            - json         a json method
            - json_name    the public name of the json method
            - open_new_window  if true, the link will be opened in a new window
                            (except in embedded mode). Optional, default true.

        :type plugin: dict
    """

    global _PLUGINS
    el = {
        "position": 0,
        "open_new_window": True,
        "multiselect": False,
    }
    el.update(plugin)
    _PLUGINS.append(el)


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = VPApplication()
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)


# - CATIA Plugin --------------------------------------------------------------

def show_in_catia(state_id, selected_row, selected_maxbom_oid=None):
    app = _getapp()

    state = app.getState(state_id)

    if state:
        state.catia_ctrl = []
        generator = state.generator
        pvalues, vinfo = state.grid_data_mapping[int(selected_row)]
        product = generator._product
        # determine max bom
        maxbom = app._get_maxbom(product, selected_maxbom_oid)

        # determine filterable variant and build catia ctrl lines
        variant = app._get_filter_variant(product, vinfo)
        if variant:
            catia_rc = CatiaRemoteControl(maxbom)
            state.catia_ctrl = catia_rc.get_variant_ctrl_lines(variant)
        else:
            # Try to retrieve the max bom view solution from the solver
            solution = generator.getFilterSolution(pvalues)
            if solution:
                catia_rc = CatiaRemoteControl(maxbom)
                state.catia_ctrl = catia_rc.get_ctrl_lines(product.cdb_object_id, pvalues)
            else:
                raise util.ErrorMessage("cdbvp_err_no_unique_mapping")
        return {"url": "cad.cadmsg?state_id=%s" % state_id}


register_plugin({"icon": "cdbvp_show_in_catia",
                 "label": "cdbvp_show_in_catia",
                 "json_name": "show_in_catia",
                 "open_new_window": False,
                 "json": show_in_catia})
