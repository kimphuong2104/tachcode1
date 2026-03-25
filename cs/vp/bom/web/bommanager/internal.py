# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Internal app for the bom manager
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import cdbwrapc
import collections
import logging

import morepath
from cdb import i18n
from cdb import ue
from cdb import util
from cdb.objects import ByID
from cs.platform.web import JsonAPI
from cs.platform.web import root
from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.classdef.main import get_classdef
from cs.platform.web.rest.generic.convert import dump_value
from cs.platform.web.rest.support import get_restlink
from cs.platform.web.uisupport import get_ui_link
from webob import exc

from cs.vp import bom
from cs.vp import items
from cs.vp import products
from cs.vp.bom import differences, bomqueries
from cs.vp.bom.bomqueries_plugins import EffectivityDatesPlugin, SiteBomAttributePlugin, \
    Site2BomAttributePlugin, SiteBomAdditionalAttrFilterPlugin, SiteBomPurposeLoadPlugin, \
    SiteBomPurposeFindDifferencePlugin, SiteBomPurposeLoadDiffTablePlugin, SiteBomPurposeSyncPlugin, \
    ComponentJoinPlugin
from cs.vp.bom.enhancement import FlatBomRestEnhancement, FlatBomEnhancement
from cs.vp.bom.enhancement.plugin import AbstractPlugin
from cs.vp.bom.enhancement.register import BomTableScope, PluginRegister
from cs.vp.bom.productstructure import ProductStructure
from cs.vp.bom.search import BomItemAttributeAccessor, BomSearch
from cs.vp.bom.web.bommanager import _check_licenses_for_item
from cs.vp.bom.web.bommanager.main import BOM_TYPE_SETTING_1, BOM_TYPE_SETTING_2
from cs.vp.items import Item
from cs.vp.utils import get_description_tag
from cs.vp.variants import bomlinks
from cs.vp.variants.filter import CsVpVariantsAttributePlugin, CsVpVariantsFilterPlugin, \
    CsVpVariantsProductContextPlugin

LOG = logging.getLogger(__name__)

DIFFERENCE_IGNORED = "DIFFERENCE_IGNORED"
PART_IGNORED = "PART_IGNORED"
BOM_FIELD_NAMES = ["cdb_object_id", "baugruppe", "b_index", "teilenummer", "t_index"]


class BomInfoPlugin(AbstractPlugin):
    """
    This class implements a BOM enhancement plugin that extends the BOM item select statement.
    Specifically, this plugin adds the following properties to the result of the "SELECT" statement:

        is_leaf: 0 if the selected BOM item is not a "leaf", i.e. if the BOM item is referenced by other BOM
                 items as an assembly and thus has children. 1 if the selected BOM item if a "leaf" and thus
                 has no children.
    """

    DISCRIMINATOR = "cs.vp.bom.BomInfoPlugin"

    def __init__(self):
        super().__init__()

    def get_bom_item_select_stmt_extension(self):
        """
        Returns this plugin's SQL extension for the "SELECT" condition of the bom_item (einzelteile) query.
        This is joined with the statements of other plugins by the BOM enhancement.

        :return: string which get added to "SELECT" condition.
        """

        # Because imprecisely assembled BOM items can change whether they are leaves or not, we need to use
        # the joined component's teilenummer/t_index (via COMPONENT_TABLE_ALIAS) to determine whether the BOM
        # item is a leaf. Otherwise, we would derive is_leaf from the as_saved index of the BOM item, which
        # may differ from more recent indices and thus lead to wrong results.
        return f"""
            , CASE
                WHEN NOT EXISTS (
                    SELECT * FROM einzelteile et
                    WHERE et.baugruppe={self.COMPONENT_TABLE_ALIAS}.teilenummer
                        AND et.b_index={self.COMPONENT_TABLE_ALIAS}.t_index
                ) THEN 1
                ELSE 0
            END is_leaf        
        """


def _to_json(path):
    result = []
    for bom_component in path:
        result.append({
            field_name: getattr(bom_component, field_name)
            for field_name in BOM_FIELD_NAMES
            if hasattr(bom_component, field_name)
        })
    return result


def safe_number(value, t=int):
    try:
        return t(value)
    except (ValueError, TypeError):
        return value


class BommanagerInternal(JsonAPI):
    pass


@BommanagerInternal.path(path="acceptancetest_cleanup")
class BommanagerInternalTestCleanupModel(object):
    pass


@BommanagerInternal.path(path="{lbom_oid}")
class BommanagerInternalModel(object):
    _ADDITIONAL_ASSEMBLY_COMPONENT_ATTRIBUTE_FUNCTIONS = []
    bom_item_object_icon_id = None
    bom_enhancement: FlatBomRestEnhancement

    def __init__(self, lbom_oid, rbom_oid=None):
        self.lbom = items.Item.ByKeys(cdb_object_id=lbom_oid)
        if self.lbom is None:
            raise exc.HTTPNotFound()

        self.rbom = None
        if rbom_oid is not None:
            self.rbom = items.Item.ByKeys(cdb_object_id=rbom_oid)

        self.product = None
        self.bom_enhancement = None

    @classmethod
    def create_bom_enhancement(cls, scope):
        return FlatBomRestEnhancement(scope)

    def init_bom_enhancement(self, bom_enhancement: FlatBomRestEnhancement, request: morepath.Request):
        self.bom_enhancement = bom_enhancement
        self.bom_enhancement.initialize_from_request(request)
        product_context = self.bom_enhancement.plugins.get(CsVpVariantsProductContextPlugin)
        if product_context is not None and product_context.product_object_id is not None:
            self.product = products.Product.ByKeys(cdb_object_id=product_context.product_object_id)

    def handle_boms_view(self, request):
        """
        Handle the 'boms' view endpoint.
        Is used extended by other modules (e.g. cs.variants) to handle additional request parameters.

        :param request: Morepath request
        :return: BomTable Information
        """
        parents = request.json.get("parents")
        assemblies = items.Item.Query(_make_item_pk_statement(parents))
        self.init_bom_enhancement(self.create_bom_enhancement(BomTableScope.LOAD), request)

        result = []

        root_item = None
        for parent in parents:
            if 'baugruppe' not in parent:
                for item in assemblies:
                    if item['teilenummer'] == parent['teilenummer'] and item['t_index'] == parent['t_index']:
                        root_item = item
                        break

        if root_item:
            rest_root_item = request.view(root_item, app=get_collection_app(request))
            for attr in ["ce_valid_from", "ce_valid_to"]:
                # display ce_valid_from and to from root node in component_ce_valid_from and to as for all other rows
                if attr in rest_root_item:
                    rest_root_item["component_" + attr] = rest_root_item[attr]
                    rest_root_item[attr] = None
            result.append([rest_root_item])
        else:
            # The client expects a result for the root item, even if it was not requested explicitly.
            result.append([])

        bom_info_by_assembly_keys = self._get_mapped_bom_info(assemblies)

        for parent in parents:
            result.append(self._resolve_children(parent, bom_info_by_assembly_keys))

        return result

    def _resolve_children(self, parent, mapped_bom_info):
        if parent.get('t_index', None) is None:
            # if the parent is invalid it cannot have any children
            my_children = []
        else:
            # By default, pick the children that were already queried.
            my_children = mapped_bom_info[(parent.get('teilenummer'), parent.get('t_index'))]

        # The requested parent is currently loaded in the BOM, i.e. before any filters are applied. If the
        # imprecise view changes (and only then), the parent may not be in the BOM any longer or its index
        # may have changed, making the initially queried children potentially invalid. In that case, we look
        # up the parent's actual index _after filtering_ (using the initially queried BOM info) and then
        # re-query its children if needed.
        upper_parent_key = (parent.get('baugruppe'), parent.get('b_index'))
        upper_parent = mapped_bom_info.get(upper_parent_key)
        if upper_parent is not None:
            # Find the actual resolved BOM info for the requested parent.
            resolved_parent = next(
                (
                    child for child in upper_parent
                    if child.get('cdb_object_id') == parent.get('cdb_object_id')
                ),
                None
            )
            if resolved_parent is None or resolved_parent.get('t_index', None) is None:
                # If no info is found, the parent is no longer in the BOM for the current imprecise view.
                # Thus, its children are also no longer in the BOM.
                # If the parent is invalid it cannot have children.
                my_children = []
            elif (
                    resolved_parent.get('teilenummer') != parent.get('teilenummer') or
                    resolved_parent.get('t_index') != parent.get('t_index')
            ):
                # The parent was found in the resolved info, but the teilenummer or index differ.
                #   - The resolved teilenummer can differ due to modifying operations.
                #   - The resolved index can differ due to switching imprecise views.
                # The children need to be corrected in this case.
                resolved_parent_key = (resolved_parent.get('teilenummer'), resolved_parent.get('t_index'))
                if resolved_parent_key not in mapped_bom_info:
                    assembly = Item.ByKeys(*resolved_parent_key)
                    # Save the BOM info for the re-queried component, so that other parents that need to
                    # re-query the same component don't need to call Item.ByKeys() again.
                    mapped_bom_info.update(self._get_mapped_bom_info([assembly]))
                new_children = mapped_bom_info.get(resolved_parent_key)
                my_children = new_children

        return my_children

    def _get_mapped_bom_info(self, assemblies):
        bom_info = self.bom_info(assemblies)
        # For easier access, map keys of the requested parent components to their children info.
        return {
            (assembly.teilenummer, assembly.t_index): info
            for assembly, info in zip(assemblies, bom_info)
        }

    def _get_occurrences(self):
        components = bomqueries.flat_bom(self.lbom)
        result = collections.defaultdict(list)
        for comp in components:
            result[(comp.teilenummer, comp.t_index)].append(comp)
        return result

    def _collect_all_parent_occurrences(self, leaf_key, occurrences):
        result = []

        def paths_to_assembly(comp):
            parents = occurrences[(comp.baugruppe, comp.b_index)]

            if parents:
                for parent in parents:
                    for p in paths_to_assembly(parent):
                        p.append(comp)
                        yield p
            else:
                yield [comp]

        for o in occurrences[leaf_key]:
            for path in paths_to_assembly(o):
                yield path

    def find_in_lbom(self, teilenummer, t_index):
        """
        Find occurrences in the lBOM whose teilenummer/t_index match the passed values.

        :param teilenummer: Item no. to search for in the lBOM occurrences.
        :param t_index: Item index to search for in the lBOM occurrences.

        :return: List of BOM Item paths of the matching occurrences.
        """
        occurrences = self._get_occurrences()
        key = (teilenummer, t_index)
        if key not in occurrences:
            return []

        return list(self._collect_all_parent_occurrences(key, occurrences))

    @classmethod
    def _get_bom_icon(cls, bom_item_attribute_accessor):
        from cdb.objects import IconCache

        # Retrieve the object icon id for the bom_item class once
        if cls.bom_item_object_icon_id is None:
            if IconCache.getIcon("bomtable_part_icon", accessor=bom_item_attribute_accessor):
                cls.bom_item_object_icon_id = "bomtable_part_icon"
            else:
                bom_item_class_def = cdbwrapc.CDBClassDef("bom_item")
                cls.bom_item_object_icon_id = bom_item_class_def.getObjectIconId()
        return IconCache.getIcon(cls.bom_item_object_icon_id, accessor=bom_item_attribute_accessor)

    def get_bom_item_info(self, bom_item):
        bom_item_attribute_accessor = BomItemAttributeAccessor(bom_item)
        if bom_item["t_index"] is None:
            # no component index found either because the component does not exist or no validity dates are set.
            bom_node_tag = get_description_tag('bom_node_tag_web_error')
            description = bom_node_tag % bom_item_attribute_accessor
            tooltip_tag = \
                get_description_tag('bom_node_tag_web_error_tooltip_imprecise') if bom_item.is_imprecise \
                else get_description_tag('bom_node_tag_web_error_tooltip_precise')
            tooltip = tooltip_tag % bom_item_attribute_accessor
        else:
            bom_node_tag = get_description_tag('bom_node_tag_web')
            description = bom_node_tag % bom_item_attribute_accessor
            tooltip = util.get_label("cdbvp_elink_diffutils_item_tooltip") % description
        extra = {
            "is_leaf": bom_item.is_leaf,
            "description": description,
            "tooltip": tooltip,
            "bom_icon": BommanagerInternalModel._get_bom_icon(bom_item_attribute_accessor),
            "system:classname": getattr(bom_item, "cdb_classname", "bom_item")
        }
        comp_dict = bom_item_attribute_accessor.as_dict()
        comp_dict.update(**extra)

        additional_bom_item_attributes = self.bom_enhancement.get_additional_bom_item_attributes(bom_item)
        comp_dict.update(**additional_bom_item_attributes)

        return {k: dump_value(v) for k, v in comp_dict.items()}

    def bom_info_for_assembly(self, components_for_assembly):
        bom_item_infos = []
        for comp in components_for_assembly:
            bom_item_info = self.get_bom_item_info(comp)
            bom_item_infos.append(bom_item_info)

        result = sorted(bom_item_infos, key=bomqueries.get_sort_key)
        return result

    def bom_info(self, assemblies):
        if not assemblies:
            return []

        bom_enhancement = self.bom_enhancement if self.bom_enhancement else FlatBomEnhancement()
        if BomInfoPlugin not in bom_enhancement:
            bom_enhancement.add(BomInfoPlugin())

        flat_bom = bomqueries.filter_by_read_access(
            bomqueries.flat_bom(
                *assemblies,
                bom_enhancement=bom_enhancement,
                levels=1,
                part_attributes=[fd.name for fd in items.Item.GetTableKeys()]
            )
        )
        components_by_assembly_keys = collections.defaultdict(list)
        for comp in flat_bom:
            components_by_assembly_keys[(comp.baugruppe, comp.b_index)].append(comp)
        bom_infos = []
        for assembly in assemblies:
            components_for_assembly = components_by_assembly_keys[(assembly.teilenummer, assembly.t_index)]
            partial_result = self.bom_info_for_assembly(components_for_assembly)
            bom_infos.append(partial_result)
        return bom_infos

    def predicates_info(self, baugruppe, b_index, teilenummer, variante, position):
        if self.product is not None:
            predicates = bomlinks.BOM_Predicate.KeywordQuery(
                product_object_id=self.product.cdb_object_id,
                baugruppe=baugruppe,
                b_index=b_index,
                teilenummer=teilenummer,
                variante=variante,
                position=position,
            )

            return [
                {
                    "baugruppe": baugruppe,
                    "b_index": b_index,
                    "teilenummer": teilenummer,
                    "variante": variante,
                    "position": position,
                    "text": predicate.info_str(i18n.default()),
                    "predicate_id": predicate.predicate_id
                } for predicate in predicates
            ]
        else:
            return []


@BommanagerInternal.path(path="redirect/part/{identifier}")
class BommanagerInternalRedirectForPart(object):
    def __init__(self, identifier):
        try:
            self.teilenummer, self.index = identifier.split("@", 2)
        except ValueError:
            raise exc.HTTPNotFound()


@BommanagerInternal.view(model=BommanagerInternalRedirectForPart)
def item_redirect(model, request):
    """
    Redirection to Part/Assembly Information page
    :param model:
    :param request:
    :return:
    """
    item = Item.ByKeys(teilenummer=model.teilenummer, t_index=model.index)
    return morepath.redirect(get_ui_link(request, item))


@BommanagerInternal.path(path="{lbom_oid}/rbom/{rbom_oid}")
class BommanagerInternalModelWithRbom(BommanagerInternalModel):
    def __init__(self, lbom_oid, rbom_oid):
        super(BommanagerInternalModelWithRbom, self).__init__(lbom_oid, rbom_oid)

        if self.rbom is None:
            raise exc.HTTPNotFound()


@BommanagerInternal.path(path="search/{bom_oid}")
class BommanagerInternalSearchModel(object):
    bom_enhancement: FlatBomRestEnhancement

    def __init__(self, bom_oid):
        self.item = items.Item.ByKeys(cdb_object_id=bom_oid)

        if self.item is None:
            raise exc.HTTPNotFound()

    def init_bom_enhancement(self, bom_enhancement, request):
        self.bom_enhancement = bom_enhancement
        self.bom_enhancement.initialize_from_request(request)


@BommanagerInternal.path(path="operation_contexts")
class BommanagerInternalOperationContexts(object):
    def get_operation_contexts(self, request, bompos_object_id, teilenummer, t_index):
        result = []
        item = None
        if teilenummer is not None and t_index is not None:
            item = items.Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
        # We expect this to be None for the structure's root item, because there the cdb_object_id corresponds
        # to a part object instead of a bom_item object.
        assembly_component = bom.AssemblyComponent.ByKeys(bompos_object_id)

        objects = []
        # first append item to list
        # ensure order in operations list
        if item and item.CheckAccess("read"):
            objects.append(item)
        objects.append(assembly_component)

        for obj in objects:
            if obj is not None:
                result.append(self._get_operation_context(request, obj))

        return result

    @staticmethod
    def _get_operation_context(request, obj):
        return {
            "cdb_classname": obj.GetClassname(),
            "system:classname": obj.GetClassname(),
            "@id": get_restlink(obj, request),
            "@type": request.link(obj.GetClassDef(), app=get_classdef(request)),
            "__@object__": request.view(obj, app=get_collection_app(request)),
        }


@root.Internal.mount(app=BommanagerInternal, path="bommanager")
def _mount_internal():
    return BommanagerInternal()


@BommanagerInternal.json(
    model=BommanagerInternalModelWithRbom, name="diff_table", request_method="POST"
)
def diff_table(model: BommanagerInternalModelWithRbom, request: morepath.Request) -> dict:
    product_object_id = None
    if model.product is not None:
        product_object_id = model.product.cdb_object_id

    _check_licenses_for_item(model.lbom)
    _check_licenses_for_item(model.rbom)

    # We need one enhancement for each side, thus we can't use model.init_bom_enhancement(...) here.
    lbom_enhancement = rbom_enhancement = None
    bom_enhancement_json: dict = request.json.get('bomEnhancementData', {})
    if 'lbom' in bom_enhancement_json:
        lbom_enhancement = FlatBomRestEnhancement(BomTableScope.DIFF_LOAD)
        lbom_enhancement.initialize_plugins_with_rest_data(bom_enhancement_json.get('lbom'))
    if 'rbom' in bom_enhancement_json:
        rbom_enhancement = FlatBomRestEnhancement(BomTableScope.DIFF_LOAD)
        rbom_enhancement.initialize_plugins_with_rest_data(bom_enhancement_json.get('rbom'))

    try:
        diffs = differences.get_differences(
            model.lbom,
            lbom_enhancement,
            model.rbom,
            rbom_enhancement,
            product_object_id,
            use_mapping=request.json.get('use_mapping', True)
        )
    except differences.RecursiveBomException as rbe:
        return dict(rows=list(),
                    exception=dict(exceptionType='RecursiveBomException',
                                   nativeDBError=rbe.getNativeDBError(),
                                   bomDesc=rbe.getBomDescription()))

    result = []
    ignored_diffs = bom.IgnoredDifferences.KeywordQuery(context_teilenummer=model.rbom.teilenummer)
    for values in differences.calculate_hints(diffs, model.lbom, model.rbom):
        if any((
                diff.teilenummer == values["teilenummer"] and diff.ignored_difference == ''
                for diff in ignored_diffs
        )):
            values["ignored"] = PART_IGNORED
        elif any((
                diff.teilenummer == values["teilenummer"] and diff.ignored_difference == values.get("hint")
                for diff in ignored_diffs
        )):
            values["ignored"] = DIFFERENCE_IGNORED
        else:
            values["ignored"] = ""
        result.append(values)

    return dict(rows=result)


def _make_item_pk_statement(objects):
    ti = util.tables["teile_stamm"]
    keys = ["teilenummer", "t_index"]
    conditions = []
    for obj in objects:
        conditions.append("(%s)" % ti.condition(keys, [obj[k] for k in keys]))
    return " OR ".join(conditions)


@BommanagerInternal.json(model=BommanagerInternalModel, name="boms", request_method="POST")
def render_boms(model, request):
    from cs.vp.bom.enhancement import EnhancementPluginError
    try:
        return model.handle_boms_view(request)
    except ue.Exception as ex:
        # In case something throws an error when requesting the BOM view, we want to be able to handle the
        # error gracefully in the client.
        raise exc.HTTPUnprocessableEntity(detail=str(ex))
    except EnhancementPluginError as eex:
        raise exc.HTTPUnprocessableEntity(detail=str(eex))


@BommanagerInternal.json(model=BommanagerInternalSearchModel, request_method="POST")
def text_search(model, request):
    """ Perform a text search on a bom.
        The search string is mapped against the description tag of the bom components.

        We only match bom components, but the result will be the complete paths from the root node
        to the matched component. This way the front-end knows where to find the matches.

        The following GET paramaters are required

        :param condition: the search string
        :type condition: string
    """
    model.init_bom_enhancement(
        FlatBomRestEnhancement(BomTableScope.SEARCH),
        request)

    condition = request.json.get("condition", "")

    search = BomSearch(
        model.item,
        condition=condition,
        bom_enhancement=model.bom_enhancement
    )
    result = search.get_results()

    result_with_root = [[model.item] + p for p in result]
    result_json = [_to_json(path) for path in result_with_root]

    return result_json


@BommanagerInternal.json(model=BommanagerInternalSearchModel, name="mapping", request_method="POST")
def mapping_search(model, request):
    model.init_bom_enhancement(
        FlatBomRestEnhancement(BomTableScope.MAPPING), request)

    # The dictionary matches bom_item object IDs to a boolean value. It indicates whether the BOM item is
    # matched or not. We use it to avoid multiple checks in case a BOM item multiple times. Building the
    # description tag can be expensive, so we prefer to avoid doing it more than once.
    matches = {}

    # result is the list of the complete paths to the found bom positions.
    result = []

    activeBomType = request.json["activeBomType"]

    flat_bom = bomqueries.flat_bom_dict(
        model.item, bom_enhancement=model.bom_enhancement
    )

    def search_in_bom(path, item_or_comp):
        for comp in flat_bom[(item_or_comp.teilenummer, item_or_comp.t_index)]:
            bom_item_object_id = comp['cdb_object_id']
            if bom_item_object_id not in matches:
                mapping_tag = comp["mbom_mapping_tag"]
                depends_on = comp["cdb_depends_on"]
                # the type of the parent part must be the same as the type selected in the UI
                # and ignore if depends_on is empty or none
                is_parent_type_equal = item_or_comp.type_object_id == activeBomType["cdb_object_id"]
                is_mapping_tag_empty = mapping_tag is None or mapping_tag == ""
                is_depends_on_empty = depends_on is None or depends_on == ""
                is_matched_1 = is_mapping_tag_empty and is_parent_type_equal and not is_depends_on_empty
                is_matched_2 = is_mapping_tag_empty and is_parent_type_equal and comp["type_object_id"] != \
                               activeBomType["cdb_object_id"]
                is_matched = is_matched_1 or is_matched_2
                matches[bom_item_object_id] = is_matched

            comp_path = path + [comp]
            if matches[bom_item_object_id]:
                result.append(comp_path)

            search_in_bom(comp_path, comp)

    search_in_bom([model.item], model.item)

    result.sort(key=bomqueries.get_path_sort_key)

    return [_to_json(path) for path in result]


@BommanagerInternal.json(model=BommanagerInternalModel, name="rboms")
def rboms(model, request):
    collection_app = root.get_v1(request).child("collection")

    rboms = model.lbom.ManufacturingViews
    return [request.view(rbom, app=collection_app) for rbom in rboms]


@BommanagerInternal.json(
    model=BommanagerInternalModel, name="find_differences", request_method="POST"
)
def find_differences(model, request):
    json: dict = request.json

    diff_id_paths = json.get('diff_id_paths', {})
    if 'lpaths' not in diff_id_paths or 'rpaths' not in diff_id_paths:
        raise exc.HTTPBadRequest()

    left_id_paths = diff_id_paths['lpaths']
    right_id_paths = diff_id_paths['rpaths']

    # We need one enhancement for each side, thus we can't use model.init_bom_enhancement(...) here.
    lbom_enhancement = rbom_enhancement = None
    bom_enhancements: dict = json.get('bomEnhancementData', {})
    if 'lbom' in bom_enhancements:
        lbom_enhancement = FlatBomRestEnhancement(BomTableScope.DIFF_SEARCH)
        lbom_enhancement.initialize_plugins_with_rest_data(bom_enhancements.get('lbom'))
    if 'rbom' in bom_enhancements:
        rbom_enhancement = FlatBomRestEnhancement(BomTableScope.DIFF_SEARCH)
        rbom_enhancement.initialize_plugins_with_rest_data(bom_enhancements.get('rbom'))

    unique_left_ids = {bom_item_id for path in left_id_paths for bom_item_id in path}
    left_records = bomqueries.bom_item_record_dict(*unique_left_ids, bom_enhancement=lbom_enhancement)
    left_paths = [
        [left_records[bom_item_id] for bom_item_id in path]
        for path in left_id_paths
    ]

    unique_right_ids = {bom_item_id for path in right_id_paths for bom_item_id in path}
    right_records = bomqueries.bom_item_record_dict(*unique_right_ids, bom_enhancement=rbom_enhancement)
    right_paths = [
        [right_records[bom_item_id] for bom_item_id in path]
        for path in right_id_paths
    ]

    return {
        'left': [_to_json([model.lbom] + path) for path in left_paths],
        'right': [_to_json([model.rbom] + path) for path in right_paths]
    }


@BommanagerInternal.json(model=BommanagerInternalModel, name="sync_lbom", request_method="POST")
def synclbom(model, request):
    model.init_bom_enhancement(FlatBomRestEnhancement(BomTableScope.SYNC_LBOM), request)

    _path = request.json.get("path", [])
    use_mapping = request.json.get("use_mapping", True)

    # sync for root item
    if len(_path) == 1:
        return [_to_json([model.rbom])]

    rps = ProductStructure(model.rbom, model.bom_enhancement)

    no_mapping_tag = False
    nodes = []
    if use_mapping:
        bom_item = bom.AssemblyComponent.ByKeys(_path[-1]["cdb_object_id"])
        if bom_item.mbom_mapping_tag:
            nodes = rps.find_nodes(mbom_mapping_tag=bom_item.mbom_mapping_tag)
        else:
            no_mapping_tag = True
    if not use_mapping or no_mapping_tag:
        teilenummer = _path[-1]["teilenummer"]
        t_index = _path[-1]["t_index"]
        item = items.Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
        nodes = rps.get_nodes_by_item_keys(teilenummer, t_index)
        nodes += rps.get_imprecise_nodes(teilenummer)
        nodes += rps.find_nodes(cdb_depends_on=item.cdb_object_id)
        nodes = list(set(nodes))  # uniqueness
    nodes.sort(key=lambda node: node.sort_id)
    rpaths = [node.path_from_root(full_records=True) for node in nodes]
    result = [_to_json([model.rbom] + rpath) for rpath in rpaths]
    return result


@BommanagerInternal.json(model=BommanagerInternalModel, name="sync_rbom", request_method="POST")
def syncrbom(model, request):
    model.init_bom_enhancement(FlatBomRestEnhancement(BomTableScope.SYNC_RBOM), request)

    _path = request.json.get("path", [])
    use_mapping = request.json.get("use_mapping", True)

    # sync for root item
    if len(_path) == 1:
        return [_to_json([model.lbom])]

    lps = ProductStructure(model.lbom, model.bom_enhancement)

    no_mapping_tag = False
    nodes = []
    if use_mapping:
        bom_item = bom.AssemblyComponent.ByKeys(_path[-1]["cdb_object_id"])
        if bom_item.mbom_mapping_tag:
            nodes = lps.find_nodes(mbom_mapping_tag=bom_item.mbom_mapping_tag)
        else:
            no_mapping_tag = True
    if not use_mapping or no_mapping_tag:
        teilenummer = _path[-1]["teilenummer"]
        t_index = _path[-1]["t_index"]
        item = items.Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
        bom_item = bom.AssemblyComponent.ByKeys(_path[-1]["cdb_object_id"])
        if bom_item.is_imprecise:
            nodes = lps.get_nodes_by_item_number(teilenummer)
            if item.cdb_depends_on:
                resolved_item = items.Item.ByKeys(cdb_object_id=item.cdb_depends_on)
                nodes += lps.get_nodes_by_item_number(resolved_item.teilenummer)
        else:
            nodes = lps.get_nodes_by_item_keys(teilenummer, t_index)
            if item.cdb_depends_on:
                nodes += lps.find_nodes(item_object_id=item.cdb_depends_on)
        nodes = list(set(nodes))  # uniqueness

    nodes.sort(key=lambda node: node.sort_id)
    lpaths = [node.path_from_root(full_records=True) for node in nodes]
    result = [_to_json([model.lbom] + lpath) for lpath in lpaths]
    return result


@BommanagerInternal.json(model=BommanagerInternalModel, name="find_lboms", request_method="POST")
def find_in_lbom(model, request):
    """
    Find matching lBOM occurrences (BOM Item paths) for a specified rBOM path. This is used by cs.threed to
    highlight a component in the 3D preview when a position in the rBOM is selected.

    The matching is done by the teilenummer/t_index of the selected rBOM component. If the teilenummer/t_index
    do not occur in the lBOM, an empty list is returned.
    """
    model.init_bom_enhancement(
        FlatBomRestEnhancement(BomTableScope.FIND_LBOMS), request)

    _path = request.json.get("path", [])

    if not _path:
        raise exc.HTTPBadRequest("given path must contain at least one element")

    root_item = _path[0]
    if root_item["teilenummer"] != model.rbom.teilenummer or root_item["t_index"] != model.rbom.t_index:
        raise exc.HTTPNotFound("given root path rows not match the rbom")

    # Find lBOM components matching teilenummer/t_index of last component in requested path (which is the
    # selected rBOM component).
    last_in_path = _path[-1]
    lpaths = model.find_in_lbom(last_in_path['teilenummer'], last_in_path['t_index'])
    result = [_to_json([model.lbom] + lpath) for lpath in lpaths]
    return result


@BommanagerInternal.json(model=BommanagerInternalOperationContexts, request_method="GET")
def get_operation_contexts(model, request):
    g = request.GET
    return model.get_operation_contexts(
        request,
        g.get('cdb_object_id'),
        g.get('teilenummer'),
        g.get('t_index')
    )


@BommanagerInternal.json(model=BommanagerInternalOperationContexts, request_method="POST", name="multi")
def get_multi_operation_contexts(model, request):
    result = []
    for d in request.json:
        result.append(model.get_operation_contexts(
            request,
            d.get('cdb_object_id'),
            d.get('teilenummer'),
            d.get('t_index')
        ))
    return result


@BommanagerInternal.json(model=BommanagerInternalModel, name="ignore", request_method="POST")
def ignore_difference(model, request):
    payload = request.json

    context_teilenummer = model.rbom.teilenummer
    teilenummer = payload.get("teilenummer")
    difference = payload.get("difference", "")

    if teilenummer is None:
        raise exc.HTTPNotFound("'teilenummer' missing from request payload")

    diff = bom.IgnoredDifferences.ByKeys(
        context_teilenummer=context_teilenummer,
        teilenummer=teilenummer
    )
    if diff:
        diff.ignored_difference = difference
    else:
        bom.IgnoredDifferences.Create(
            context_teilenummer=context_teilenummer,
            teilenummer=teilenummer,
            ignored_difference=difference
        )

    if difference == '':
        result = PART_IGNORED
    else:
        result = DIFFERENCE_IGNORED
    return {"ignored": result}


@BommanagerInternal.json(model=BommanagerInternalModel, name="unignore", request_method="POST")
def ignore_difference(model, request):
    payload = request.json

    context_teilenummer = model.rbom.teilenummer
    teilenummer = payload.get("teilenummer")

    if teilenummer is None:
        raise exc.HTTPNotFound("'teilenummer' missing from request payload")

    diff = bom.IgnoredDifferences.KeywordQuery(
        context_teilenummer=context_teilenummer,
        teilenummer=teilenummer
    ).Delete()

    return {"ignored": ""}


@BommanagerInternal.json(model=BommanagerInternalTestCleanupModel, request_method="GET")
def preview_viewers(model, request):
    # Delete user setting for bomtype
    util.PersonalSettings().remove(BOM_TYPE_SETTING_1, BOM_TYPE_SETTING_2)
    raise exc.HTTPNoContent()


@BommanagerInternal.path("/by_id/{oid}")
class ByIdModel(object):
    def __init__(self, oid):
        self.object = ByID(oid)
        if self.object is None:
            raise exc.HTTPNotFound()


@BommanagerInternal.json(model=ByIdModel)
def object_by_id(model, request):
    collection_app = root.get_v1(request).child("collection")
    return request.view(model.object, app=collection_app)


@BommanagerInternal.json(model=BommanagerInternalModel, name="bom_predicates", request_method="POST")
def render_bom_predicates(model, request):
    model.init_bom_enhancement(
        FlatBomRestEnhancement(BomTableScope.DIFF_LOAD),
        request)
    payload = request.json
    return model.predicates_info(
        baugruppe=payload.get("baugruppe"),
        b_index=payload.get("b_index"),
        teilenummer=payload.get("teilenummer"),
        variante=payload.get("variante"),
        position=int(payload.get("position")),
    )


PluginRegister().register_plugin(
    ComponentJoinPlugin,
    [
        BomTableScope.INIT,
        BomTableScope.LOAD,
        BomTableScope.SEARCH,
        BomTableScope.DIFF_LOAD,
        BomTableScope.DIFF_SEARCH,
        BomTableScope.MAPPING,
        BomTableScope.FIND_LBOMS,
        BomTableScope.SYNC_LBOM,
        BomTableScope.SYNC_RBOM,
    ],
)

PluginRegister().register_plugin(
    CsVpVariantsAttributePlugin, [BomTableScope.LOAD, BomTableScope.INIT]
)

PluginRegister().register_plugin(
    CsVpVariantsFilterPlugin,
    [
        BomTableScope.SEARCH,
        BomTableScope.DIFF_LOAD,
        BomTableScope.DIFF_SEARCH,
        BomTableScope.MAPPING,
        BomTableScope.FIND_LBOMS,
        BomTableScope.SYNC_LBOM,
        BomTableScope.SYNC_RBOM,
    ],
)

PluginRegister().register_plugin(
    EffectivityDatesPlugin,
    [
        BomTableScope.LOAD,
        BomTableScope.SEARCH,
        BomTableScope.DIFF_LOAD,
        BomTableScope.DIFF_SEARCH,
        BomTableScope.MAPPING,
        BomTableScope.FIND_LBOMS,
        BomTableScope.SYNC_LBOM,
        BomTableScope.SYNC_RBOM,
    ],
)

PluginRegister().register_plugin(
    SiteBomAttributePlugin,
    [
        BomTableScope.INIT,
        BomTableScope.LOAD,
        BomTableScope.SEARCH,
        BomTableScope.DIFF_LOAD,
        BomTableScope.DIFF_SEARCH,
        BomTableScope.MAPPING,
        BomTableScope.FIND_LBOMS,
        BomTableScope.SYNC_LBOM,
        BomTableScope.SYNC_RBOM,
    ],
)

PluginRegister().register_plugin(
    Site2BomAttributePlugin,
    [
        BomTableScope.INIT,
        BomTableScope.LOAD,
        BomTableScope.SEARCH,
        BomTableScope.DIFF_LOAD,
        BomTableScope.DIFF_SEARCH,
        BomTableScope.MAPPING,
        BomTableScope.FIND_LBOMS,
        BomTableScope.SYNC_LBOM,
        BomTableScope.SYNC_RBOM,
    ],
)

PluginRegister().register_plugin(
    SiteBomAdditionalAttrFilterPlugin,
    [
        BomTableScope.INIT,
    ],
)

PluginRegister().register_plugin(SiteBomPurposeLoadPlugin, [BomTableScope.LOAD])
PluginRegister().register_plugin(SiteBomPurposeFindDifferencePlugin, [BomTableScope.DIFF_SEARCH])
PluginRegister().register_plugin(SiteBomPurposeLoadDiffTablePlugin, [BomTableScope.DIFF_LOAD])
PluginRegister().register_plugin(SiteBomPurposeSyncPlugin, [BomTableScope.SYNC_LBOM, BomTableScope.SYNC_RBOM])
