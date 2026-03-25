# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import logging
import json
import urllib.request, urllib.parse, urllib.error
from contextlib import contextmanager

import cdbwrapc
from cdb import constants
from cdb import fls
from cdb import sig
from cdb import ue
from cdb import transactions
from cdb.objects import operations
from cdb import util
from cdb import cdbuuid
from cdb.objects.operations import system_args
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import I18nCatalogEntry

from cs.vp import bom
from cs.vp.bom import AssemblyComponent
from cs.vp.bom import bomqueries
from cs.vp.items import Item
from cs.vp.items.mbom import DERIVED_BOM_CREATED
from cs.vp.variants.apps import generatorui

LOG = logging.getLogger(__name__)


XBOM_FEATURE = "BOM_012"
BOMMANAGER_FEATURES = ["BOM_003", "BOM_004", XBOM_FEATURE]
VERSION = "15.7.0"

BOM_TYPE_SETTING_1 = "cs.webcomponents.cs-vp-bom-web-bommanager-active_bomtype"
BOM_TYPE_SETTING_2 = "default"

OPEN_AS_MASTER = "0"
OPEN_AS_DERIVED = "1"

def _check_licenses_for_item(item):
    if item is not None:
        _check_licenses_for_type_id(item.type_object_id)


def _check_licenses_for_type_id(type_object_id):
    mbom_type_id = bom.get_mbom_bom_type().cdb_object_id
    ebom_type_id = bom.get_ebom_bom_type().cdb_object_id
    non_licensed_type_ids = {mbom_type_id, ebom_type_id}
    if type_object_id and type_object_id not in non_licensed_type_ids:
        # when the type is defined, but it is no mBOM, check for the availability of the XBOM feature
        try:
            fls.allocate_license(XBOM_FEATURE)
        except fls.LicenseError as e:
            # use ue.Exception instead of the original license error to only show the message without the stacktrace
            raise ue.Exception("xbom_allocation_failed", e.message)


@sig.connect(Item, "cdbvp_open_bommanager", "pre_mask")
def _open_bommanager_pre_mask (item, ctx):
    def IsDerived(item):
        return item.cdb_depends_on is not None and item.cdb_depends_on != ""

    # use the if statement, if the selection dialog should be shown
    #if n_bom_types() <= 1 or not IsDerived(item):
    ctx.skip_dialog()


@sig.connect(Item, "cdbvp_open_bommanager", "now")
def _open_bommanager_now(item, ctx):
    side = None

    if "cdbvp_open_bommanager_selection" in ctx.dialog.get_attribute_names():
        if ctx.dialog.cdbvp_open_bommanager_selection == OPEN_AS_MASTER:
            side = "left"
        else:
            side = "right"

    lbom, rbom = get_boms(item, side)

    _check_licenses_for_item(rbom)
    _check_licenses_for_item(lbom)

    if lbom is None:
        raise ue.Exception('cdbvp_no_lbom_selected')
    if rbom and rbom.type_object_id not in [active_bom_type.cdb_object_id for active_bom_type in bom.BomType.getActiveBOMTypes()]:
        raise ue.Exception('cdbvp_rbom_type_not_active')

    variability_model = None
    product = None
    if hasattr(lbom, "VariabilityModelLinks"):
        models = lbom.VariabilityModelLinks.Execute()
        if len(models) == 1:
            variability_model = models[0].VariabilityModel
    elif len(lbom.Products) == 1:
        product = lbom.Products[0]

    ctx.url(make_bommanager_url_from_objects(lbom, rbom, product, variability_model=variability_model))


class OpenBomManagerCatalog(CDBCatalog):
    """
    Catalog that fills the ComboBox of the refresh configuration
    within the personal settings
    """
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        result = []
        result.append(I18nCatalogEntry(OPEN_AS_MASTER, util.get_label("open_bommanager_master")))
        result.append(I18nCatalogEntry(OPEN_AS_DERIVED, util.get_label("open_bommanager_derived")))
        return result


_n_bom_types = None


def n_bom_types():
    global _n_bom_types
    if _n_bom_types is None:
        _n_bom_types = len(bom.BomType.KeywordQuery(is_enabled=1))
    return _n_bom_types


def get_active_bom_type_setting():
    try:
        active_bom_type_setting = json.loads(util.PersonalSettings().getValueOrDefault(BOM_TYPE_SETTING_1, BOM_TYPE_SETTING_2, None))
        for active_bom_type in bom.BomType.getActiveBOMTypes():
            if active_bom_type["code"] == active_bom_type_setting["code"]:
                return active_bom_type_setting
    except (KeyError, ValueError):
        LOG.warn("User Setting %s, %s is not valid.", BOM_TYPE_SETTING_1, BOM_TYPE_SETTING_2)
    return {"code": "mBOM"}


def get_active_bomtype():
    setting = get_active_bom_type_setting()
    return bom.BomType.GetBomTypeForCode(setting["code"])


def set_active_bom_type_setting(bomtype_code):
    setting_value = '{"code":"%s"}' % bomtype_code
    util.PersonalSettings().setValue(BOM_TYPE_SETTING_1, BOM_TYPE_SETTING_2, setting_value)


def get_boms(item, selected_side=None):
    lbom = None
    rbom = None

    if selected_side is None:
        if item.IsDerived() and item.cdb_depends_on:
            selected_side = "right"
        else:
            selected_side = "left"

    if item is not None:
        if selected_side == "right":
            lbom = item.EngineeringView
            rbom = item
        elif selected_side == "left":
            lbom = item
            active_bom_type = get_active_bomtype()
            rboms = []
            for xbom in item.ManufacturingViews:
                if active_bom_type is not None and xbom.type_object_id == active_bom_type.cdb_object_id:
                    rboms.append(xbom)
            if len(rboms) == 1:
                rbom = rboms[0]
    return lbom, rbom


def make_bommanager_url_from_objects(lbom, rbom=None, product=None, variant=None, signature=None, variability_model=None):
    url_params = {}

    if product is not None:
        url_params["product"] = product.cdb_object_id

    if variability_model is not None:
        url_params["variability_model"] = variability_model.cdb_object_id

    if product is not None and variant is not None:
        url_params["variant"] = variant.cdb_object_id
    elif product is not None and signature is not None:
        url_params["signature"] = signature

    if rbom is not None:
        url_params["rbom"] = rbom.cdb_object_id

    return make_bommanager_url(lbom.cdb_object_id, url_params)


def make_bommanager_url(lbom_oid, url_params):
    return "/bommanager/{lbom_oid}?{url_args}".format(
        lbom_oid=lbom_oid,
        url_args=urllib.parse.urlencode(url_params)
        )


@contextmanager
def _bom_change_context(teilenummer, t_index):
    xbom = Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
    if xbom is not None and xbom.IsDerived():
        _check_licenses_for_item(xbom)
        with transactions.Transaction():
            yield xbom
    # FIXME: throw Exception when xbom is not derived


@sig.connect(AssemblyComponent, list, "bommanager_batch_copy", "now")
def bommanager_batch_copy(bom_positions, ctx):
    with _bom_change_context(ctx.dialog.teilenummer, ctx.dialog.t_index) as xbom:
        xbom_components = xbom.Components
        xbom_positions = {comp.position for comp in xbom_components}

        for bom_position in bom_positions:
            args = {
                "baugruppe": xbom.teilenummer,
                "b_index": xbom.t_index,
            }
            if bom_position.position not in xbom_positions:
                args["position"] = bom_position.position

            new_bom_position = operations.operation(
                constants.kOperationCopy,
                bom_position,
                # Pass flag so that AssemblyComponent.skip_relships_for_rbom_copy() does not copy certain
                # relships (see cs.vp.bom.RELSHIPS_TO_SKIP_FOR_RBOM_COPY).
                system_args(is_copy_to_rbom=True),
                **args
            )

            xbom_positions.add(new_bom_position.position)


@sig.connect(AssemblyComponent, list, "bommanager_copy_and_create_xbom", "now")
def bommanager_copy_and_create_xbom(bom_positions, ctx):
    # Parameter bom_positions refers to the BOM positions that were selected by the user for the operation.

    # xbom refers to the target assembly for the operation (isDervied() must be True), i.e. the BOM that we
    # want to generate and assemble the derived BOMs on.
    with _bom_change_context(ctx.dialog.teilenummer, ctx.dialog.t_index) as xbom:
        # The target assembly's components ("children"). Used for checking whether we can also copy over the
        # existing position number or whether we need to generate a new one.
        xbom_components = xbom.Components

        # Gather site and desired BOM type for deriving a new part(s).
        site_object_id = getattr(ctx.dialog, "site_oid", None)
        type_object_id = getattr(ctx.dialog, "type_object_id", None)

        for bom_position in bom_positions:
            args = {
                "baugruppe": xbom.teilenummer,
                "b_index": xbom.t_index,
            }

            # If the to-be-copied BOM item's position number is not taken within the target assembly, we want
            # to copy it over as well.
            if not any(comp for comp in xbom_components if comp.position == bom_position.position):
                args["position"] = bom_position.position

            # We first need to generate the derived BOM so that we have a new teilenummer we can use for
            # copying the BOM position in the next step.
            new_xbom = bom_position.Item.generate_derived_bom(
                site_object_id=site_object_id,
                type_object_id=type_object_id,
                question_copy_stl_relship_1st_level=1
            )

            # Copy the BOM position so that the derived BOM is effectively assembled into the target assembly.
            # We are using copy here instead of create so that the position's relationships are copied over as
            # well.
            operations.operation(
                constants.kOperationCopy,
                bom_position,
                # Pass flag so that AssemblyComponent.skip_relships_for_rbom_copy() does not copy certain
                # relships (see cs.vp.bom.RELSHIPS_TO_SKIP_FOR_RBOM_COPY).
                system_args(is_copy_to_rbom=True),
                teilenummer=new_xbom.teilenummer,
                **args
            )


@sig.connect(AssemblyComponent, list, "bommanager_batch_move", "now")
def bommanager_batch_move(bom_positions, ctx):
    with _bom_change_context(ctx.dialog.teilenummer, ctx.dialog.t_index) as xbom:
        for bom_position in bom_positions:
            operations.operation(
                constants.kOperationModify,
                bom_position,
                baugruppe=xbom.teilenummer,
                b_index=xbom.t_index
            )


@sig.connect(AssemblyComponent, "bommanager_replace_position", "now")
def bommanager_replace_position(self, ctx):
    with _bom_change_context(ctx.dialog.teilenummer, ctx.dialog.t_index) as xbom:
        operations.operation(
            constants.kOperationModify,
            self,
            teilenummer=xbom.teilenummer,
            t_index=xbom.t_index
        )


def _is_item_of_active_bom_type(item):
    if item is None:
        # this should not happen, but if there is no item, it cannot be of any bom type,
        # so always return false
        return False
    active_bom_type = get_active_bomtype()
    return active_bom_type is not None and active_bom_type.cdb_object_id == item.type_object_id


@sig.connect(AssemblyComponent, "bommanager_synch_mapping", "now")
def bommanager_synch_mapping(ebom_position, ctx):
    xbom_position = AssemblyComponent.ByKeys(ctx.dialog.cdb_object_id)

    if not _is_item_of_active_bom_type(xbom_position.Assembly) and ebom_position.ID() != xbom_position.ID():
        active_bom_type = get_active_bomtype()
        raise ue.Exception("cs.vp.bommanager_sync_mapping_invalid_object", active_bom_type.code)

    if xbom_position is not None:
        if ebom_position.mbom_mapping_tag in ["", None]:
            ebom_position.mbom_mapping_tag = cdbuuid.create_uuid()

        xbom_position.mbom_mapping_tag = ebom_position.mbom_mapping_tag


@sig.connect(Item, "bommanager_create_rbom", "now")
def bommanager_create_rbom(item, ctx):
    return _generate_derived_bom_helper(item, ctx)


@sig.connect(Item, "bommanager_index_rbom", "now")
def bommanager_index_rbom(item, ctx):
    return _generate_derived_bom_helper(item, ctx, create_index=True)


def _generate_derived_bom_helper(item, ctx, create_index=False):
    site_object_id = getattr(ctx.dialog, "site_oid", None)
    type_object_id = getattr(ctx.dialog, "type_object_id", None)
    depends_on = getattr(ctx.dialog, "depends_on", None)
    _check_licenses_for_type_id(type_object_id)
    new_bom = item.generate_derived_bom(
        type_object_id=type_object_id,
        site_object_id=site_object_id,
        depends_on=depends_on,
        create_index=create_index,
        question_copy_stl_relship_1st_level=bom.safe_number(ctx.dialog.copy_bom)
    )

    sig.emit(DERIVED_BOM_CREATED)(item, new_bom, ctx)
    return new_bom


@sig.connect(AssemblyComponent, "bommanager_create_rbom", "now")
def bommanager_create_rbom_for_bom_position(comp, ctx):
    if "copy_from" in ctx.dialog.get_attribute_names():
        item = Item.ByKeys(cdb_object_id=ctx.dialog.copy_from)
    else:
        item = comp.Item

    if item is not None:
        site_object_id = getattr(ctx.dialog, "site_oid", None)
        type_object_id = getattr(ctx.dialog, "type_object_id", None)
        depends_on = getattr(ctx.dialog, "depends_on", None)
        _check_licenses_for_type_id(type_object_id)
        xbom = item.generate_derived_bom(
            type_object_id=type_object_id,
            site_object_id=site_object_id,
            depends_on=depends_on,
            question_copy_stl_relship_1st_level=bom.safe_number(ctx.dialog.copy_bom)
        )
        if xbom is not None:
            operations.operation(
                constants.kOperationModify,
                comp,
                teilenummer=xbom.teilenummer,
                t_index=xbom.t_index
            )


@sig.connect(Item, "index", "post")
def bommanager_index_post(item, ctx):
    # Get the BOM item that should point to the new item index.
    param_name = 'bom_item_to_update'
    bom_item_id = getattr(ctx.dialog, param_name, None)
    if bom_item_id is None:
        # If BOM item id is not part of context, then this index op is not a BOM Item replacement.
        return

    bom_item = AssemblyComponent.ByKeys(cdb_object_id=bom_item_id)
    if not bom_item:
        raise RuntimeError(f'BOM item with id {bom_item_id} not found')

    operations.operation(
        constants.kOperationModify,
        bom_item,
        teilenummer=item.teilenummer,
        t_index=item.t_index
    )


def show_bom_manager(state_id, selected_row, selected_maxbom_oid=None):
    # Allocate license "Variants: mBOM Manager"
    fls.allocate_license("VARIANTS_017")

    app = generatorui._getapp()

    state = app.getState(state_id)

    if state:
        generator = state.generator
        pvalues, vinfo = state.grid_data_mapping[int(selected_row)]
        product = generator._product
        variant = vinfo.variant_object

        maxbom = app._get_maxbom(product, selected_maxbom_oid)
        if maxbom.IsDerived() and maxbom.EngineeringView:
            lbom = maxbom.EngineeringView
            rbom = maxbom
        else:
            lbom = maxbom
            rbom = None

        signature = None
        if product is not None and variant is None:
            solution = generator.getFilterSolution(pvalues)
            signature = solution.split(';')[1]

        url = make_bommanager_url_from_objects(lbom, rbom, product, variant, signature)
        return {"url": url}


generatorui.register_plugin({
    "icon": "cdbvp_elink_diffutil",
    "label": "cdbvp_bommanager",
    "json_name": "show_bom_manager",
    "json": show_bom_manager
})
