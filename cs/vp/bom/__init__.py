# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

from datetime import datetime
import json
import math

from cdb import sqlapi, auth
from cdb import ue
from cdb import sig
from cdb import constants
from cdb import cdbuuid
from cdb import kernel
from cdb import fls
from cdb import util

from cdb.classbody import classbody

from cdb.objects import Object, ViewObject
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_N
from cdb.objects import ReferenceMapping_N
from cdb.objects import Forward
from cdb.objects import operations


from cs.vp.items import Item

from cs.tools.batchoperations import WithBatchOperations


AssemblyComponent = Forward(__name__ + ".AssemblyComponent")

ASSEMBLY_DELETE_POST = sig.signal()
MBOM_ASSEMBLY_TYPE = None

# sys_arg that signals the relships in RBOM_COPY_ARG_NAME should be skipped for the current copy operation.
RBOM_COPY_ARG_NAME = "cdb::argument.is_copy_to_rbom"


def get_ebom_bom_type():
    return BomType.GetBomTypeForCode("eBOM")


def get_mbom_bom_type():
    return BomType.GetBomTypeForCode("mBOM")


def get_sbom_bom_type():
    return BomType.GetBomTypeForCode("sBOM")


def is_installed(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def safe_number(value, default=None, t=int):
    try:
        return t(value)
    except (ValueError, TypeError):
        return default


CHUNK_SIZE = 300


def _chunked(lst, size=CHUNK_SIZE):
    steps = int(math.ceil(len(lst) / float(size)))
    for i in range(steps):
        yield lst[i * size:(i + 1) * size]


class AssemblyComponentOccurrence(Object):
    """
    For generated BOMs, we store occurrence ids and pathnames for every
    entry such that we will later be able to resynchronize correctly.
    ("Rueckabgleich" to be implemented in a future version.)
    """
    __maps_to__ = "bom_item_occurrence"
    __classname__ = "bom_item_occurrence"



class AssemblyComponent(Object, WithBatchOperations):
    __maps_to__ = "einzelteile"
    __classname__ = "bom_item"

    Assembly = Reference_1(Item, AssemblyComponent.baugruppe, AssemblyComponent.b_index)

    Item = Reference_1(Item, AssemblyComponent.teilenummer, AssemblyComponent.t_index)

    Occurrences = Reference_N(
        AssemblyComponentOccurrence,
        AssemblyComponentOccurrence.bompos_object_id == AssemblyComponent.cdb_object_id)

    def make_mbom_mapping_tag(self, ctx):
        if not self.Assembly or not self.Assembly.IsDerived():
            self.mbom_mapping_tag = cdbuuid.create_uuid()

    def IsDerived(self):
        """
        Checks if this assembly component is derived from an eBOM.

        :return: true if this component is derived, false else
        :rtype: bool
        """
        ebom_bom_type_id = get_ebom_bom_type().cdb_object_id
        return self.type_object_id is not None and self.type_object_id != ebom_bom_type_id

    def is_effectivity_period_valid(self, ctx):
        if self.ce_valid_from is None or self.ce_valid_to is None:
            return

        if self.ce_valid_to < self.ce_valid_from:
            raise ue.Exception("cdbvp_bom_invalid_effectivity_period")

    @staticmethod
    def get_relships_to_skip_for_rbom_copy():
        """
        Returns a list of relationship names that should be skipped when copying a BOM item to the rBOM
        within the xBOM manager. This list is used in the on_relship_copy_pre() handler and can be customized
        depending on which relationships should be copied to the rBOM item as well. This is useful if e.g.
        a relationship from a source eBOM item would not make sense on its derived mBOM/sBOM item.

        The default behavior is to skip the BOM item's Occurrences (bom_item_to_occurrences from
        cs.bomcreator) and FilterRules (bom_item2bom_filter_rule from cs.variants).

        :return: List of relationship names that are skipped when copying BOM items to the rBOM.
        """

        return [
            # Relship Occurrences from cs.bomcreator.
            "bom_item_to_occurrences"
        ]

    def skip_relships_for_rbom_copy(self, ctx):
        # If relship should be copied to the rBOM item, we do not need to do anything.
        if ctx.relationship_name not in self.get_relships_to_skip_for_rbom_copy():
            return

        # Get context of the surrounding copy operation (the BOM item copy) so that we can check for the
        # RBOM_COPY_ARG_NAME sys_arg.
        from cdb.platform.mom import OperationContext
        octx = OperationContext(ctx.superior_operation_context_id)

        if not octx:
            return

        # Skip relships only in the context of the "bommanager_copy_and_create_xbom" operations, signaled by
        # the RBOM_COPY_ARG_NAME sys_arg.
        is_copy_to_rbom_op = octx.getArgumentValueByName(RBOM_COPY_ARG_NAME)
        if is_copy_to_rbom_op == "1":
            ctx.skip_relationship_copy()

    BOM_MODE_PRECISE = "precise"
    BOM_MODE_PREFERRED_PRECISE = "preferred_precise"
    BOM_MODE_IMPRECISE = "imprecise"
    BOM_MODE_PREFERRED_IMPRECISE = "preferred_imprecise"

    @classmethod
    def get_bom_mode(cls):
        bom_mode = util.get_prop("bomi")
        return bom_mode if bom_mode else cls.BOM_MODE_PRECISE

    def disable_imprecise_flag(self, ctx):
        bom_mode = self.get_bom_mode()
        if bom_mode in [self.BOM_MODE_PRECISE, self.BOM_MODE_IMPRECISE]:
            ctx.set_fields_readonly(['is_imprecise'])

    def set_default_imprecise_value(self, ctx):
        if self.is_imprecise is None:
            bom_mode = self.get_bom_mode()
            if bom_mode in [self.BOM_MODE_PRECISE, self.BOM_MODE_PREFERRED_PRECISE]:
                self.is_imprecise = 0
            elif bom_mode in [self.BOM_MODE_IMPRECISE, self.BOM_MODE_PREFERRED_IMPRECISE]:
                self.is_imprecise = 1

    def handle_change_assembly(self, ctx):
        """
        On bom_item's CDB_Modify, set the 'baugruppe' and cdb_m2date/cdb_m2persno attirbutes for the target
        assembly. Note: the 'baugruppe' attribute is used for internal optimizations to determine whether an
        item is an assembly and thus as children or not.
        """

        # Check whether assembly was changed at all. If not, don't do anything.
        if ctx.mode == 'pre' and self.baugruppe != ctx.object.baugruppe or self.b_index != ctx.object.b_index:

            missing_right = None
            # Check that we are allowed to remove the BOM item from the source BOM.
            if not Item.ByKeys(ctx.object.baugruppe, ctx.object.b_index).CheckAccess('delete_bom'):
                missing_right = 'delete_bom'
            # Check that we are allowed to add the BOM item to the target BOM.
            if not missing_right and not self.Assembly.CheckAccess('create_bom'):
                missing_right = 'create_bom'

            if missing_right:
                from cdb.platform.mom.operations import OperationInfo
                op_label: str = OperationInfo('bom_item', 'CDB_Modify').get_label().strip()
                raise ue.Exception('authorization_fail', op_label, 'teile_stamm', missing_right)

            # Access check was successful, we may continue.
            ctx.keep('assembly_changed', '1')

        elif ctx.mode == 'post' and 'assembly_changed' in ctx.ue_args.get_attribute_names():
            if ctx.error:
                return

            now = datetime.utcnow()
            changed_by = auth.persno

            sqlapi.SQLupdate(
                f"""
                    teile_stamm SET
                    baugruppenart='Baugruppe',
                    cdb_m2date={sqlapi.SQLdate_literal(now)},
                    cdb_m2persno='{sqlapi.quote(changed_by)}'
                    WHERE (
                        teilenummer='{sqlapi.quote(self.baugruppe)}'
                        AND t_index='{sqlapi.quote(self.b_index)}'
                    )
                """
            )

    event_map = {
        (('create', 'copy', 'modify'), 'pre_mask'): "disable_imprecise_flag",
        (('create'), ('pre_mask', 'pre')): 'set_default_imprecise_value',
        (('create', 'copy'), 'pre'): 'make_mbom_mapping_tag',
        (("create", "copy", "modify"), "pre"): "is_effectivity_period_valid",
        ('relship_copy', 'pre'): 'skip_relships_for_rbom_copy',
        ('modify', ('pre', 'post')): 'handle_change_assembly'
    }


@classbody
class Item(object):
    Usage = Reference_N(AssemblyComponent,
                        AssemblyComponent.teilenummer == Item.teilenummer,
                        (AssemblyComponent.t_index == Item.t_index) | (AssemblyComponent.is_imprecise == 1))

    Components = Reference_N(AssemblyComponent,
                             AssemblyComponent.baugruppe == Item.teilenummer,
                             AssemblyComponent.b_index == Item.t_index,
                             order_by=AssemblyComponent.position)

    ComponentsByPosition = ReferenceMapping_N(AssemblyComponent,
                                              AssemblyComponent.baugruppe == Item.teilenummer,
                                              AssemblyComponent.b_index == Item.t_index,
                                              indexed_by=AssemblyComponent.position,
                                              order_by=AssemblyComponent.position)

    def _getSubparts(self):
        """
        Method to get all parts which belong to the BOM of the current part

        :return: a list of part objects (1, n, none)
        """
        return [component.Item for component in self.Components if component.Item is not None]

    Subparts = ReferenceMethods_N(Item, _getSubparts)

    def _getAssembly(self):
        """
        Method to get the assemblies which contain the current part

        :return: a list of assemblies (1, n, none)
        """
        return [component.Assembly for component in self.Usage if component.Assembly is not None]

    Assemblies = ReferenceMethods_N(Item, _getAssembly)

    def resolveComponents(self, depth=0, result=None):
        """
        Resolves all Items of the product structure down to
        the given depth. Default depth 0 resolves the complete
        product structure.
        """
        if not result:
            result = []
        if self.isAssembly():
            for comp in self.Components:
                if comp.Item not in result:
                    result.append(comp.Item)
                    if (depth != 1) and comp.Item.isAssembly():
                        comp.Item.resolveComponents(depth - 1, result)
        return result

    def maxPosition(self):
        result = 0
        if self.isAssembly():
            t = sqlapi.SQLselect("max(position) from einzelteile where baugruppe = '%s' and b_index = '%s'"
                                 % (self.teilenummer, self.t_index))
            result = sqlapi.SQLinteger(t, 0, 0)
        return result

    @sig.connect(Item, 'query_catalog', 'pre')
    def _handle_mbom_catalog(self, ctx):
        if ctx.catalog_name == "cdb_mbom_browser":
            item = Item.ByKeys(ctx.catalog_invoking_op_object.teilenummer,
                               ctx.catalog_invoking_op_object.t_index)
            ctx.set("cdb_depends_on", item.cdb_object_id)

    @sig.connect(Item, 'delete', 'post')
    def _delete_ignored_differences(self, ctx):
        self.delete_ignored_differences(ctx)

    def delete_ignored_differences(self, ctx):
        if not Item.Query("teilenummer='%s' AND t_index!='%s'" % (self.teilenummer, self.t_index)):
            IgnoredDifferences.KeywordQuery(context_teilenummer=self.teilenummer).Delete()

    def on_cdbvp_diffutil_new_stl_position_now(self, ctx):
        cmsg = AssemblyComponent.MakeCdbcmsg(constants.kOperationNew,  # @UndefinedVariable
                                             baugruppe=self.teilenummer,
                                             b_index=self.t_index)
        ctx.url(cmsg.get_url())

    def _handle_copy_and_replace_bom_item_pre(self, ctx):
        param_name = 'bom_item_to_replace'
        bom_item_id = getattr(ctx.sys_args, param_name, None)
        if bom_item_id is None:
            # If BOM item id is not part of context, then this copy op is not a BOM Item replacement.
            # Just quit in this case.
            return

        item = ctx.cdbtemplate
        bom_item = AssemblyComponent.ByKeys(cdb_object_id=bom_item_id)
        bom_item_matches = bom_item and item.teilenummer == bom_item.teilenummer and item.t_index == bom_item.t_index
        if not bom_item_matches:
            raise RuntimeError("BOM item with id {} not found".format(bom_item_id))

        # We need to check here whether user may replace ("delete") the BOM Item on the parent assembly,
        # in case the assembly is already released.
        if not bom_item.Assembly.CheckAccess("delete_bom"):
            raise ue.Exception("authorization8", "cdb_copy_and_replace_bom_item")

    def _handle_copy_and_replace_bom_item(self, ctx):
        param_name = 'bom_item_to_replace'

        # Try to read BOM Item id from context.
        bom_item_id = getattr(ctx.sys_args, param_name, None)
        if bom_item_id is None:
            # If BOM item id is not part of context, then this copy op is not a BOM Item replacement.
            # Just quit in this case.
            return

        bom_item = AssemblyComponent.ByKeys(cdb_object_id=bom_item_id)

        self.copy_and_replace_bom_item(ctx, bom_item)

    def copy_and_replace_bom_item(self, ctx, bom_item):
        """
        This handler is invoked during an item's CDB_Copy 'post' step if it was triggered by the
        cdb_copy_and_replace_bom_item operation. This handler replaces bom_item's component with the copied
        item.

        :param ctx: The `cdb._ctx.Context` of the current operation.
        :param bom_item: The `cs.vp.bom.AssemblyComponent` that is determined by the `bom_item_to_replace` id
               during the copy operation invocation.
        """

        operations.operation(
            constants.kOperationModify,
            bom_item,
            teilenummer=self.teilenummer,
            t_index=self.t_index
        )

    def _assembly_keep_bom_item_cdb_object_ids(self, ctx):
        if self.isAssembly():
            query = f"""
                einzelteile.cdb_object_id FROM einzelteile
                WHERE einzelteile.baugruppe = '{self.teilenummer}' 
                    AND einzelteile.b_index = '{self.t_index}'
            """
            data = sqlapi.SQLselect(query)
            result = [sqlapi.SQLstring(data, 0, row) for row in range(sqlapi.SQLrows(data))]
            ctx.keep("bom_item_cdb_object_ids", json.dumps(result))

    def _assembly_delete_post(self, ctx):
        if self.isAssembly():
            bom_item_cdb_object_ids = json.loads(ctx.ue_args["bom_item_cdb_object_ids"])
            sig.emit(ASSEMBLY_DELETE_POST)(bom_item_cdb_object_ids, ctx)
            self._delete_bom_item_occurrences_of_bom_items(bom_item_cdb_object_ids)

    def _delete_bom_item_occurrences_of_bom_items(self, bom_item_cdb_object_ids):
        if bom_item_cdb_object_ids:
            in_condition = AssemblyComponentOccurrence.bompos_object_id.one_of(*bom_item_cdb_object_ids)
            query = f"""
                FROM bom_item_occurrence 
                WHERE {in_condition}
            """
            sqlapi.SQLdelete(query)

    event_map = {
        ('copy', 'pre'): '_handle_copy_and_replace_bom_item_pre',
        ('copy', 'post'): '_handle_copy_and_replace_bom_item',
        ('delete', 'pre'): '_assembly_keep_bom_item_cdb_object_ids',
        ('delete', 'post'): '_assembly_delete_post'
    }


class Plantfilter(kernel.TableFilter):
    def execute(self, data, filter_info=None):
        if (filter_info and filter_info.getClassname() == "bom_item") or not filter_info:
            site_object_id = self.get_filter_id()

            colindex = {}
            for col in range(sqlapi.SQLcols(data)):
                name = sqlapi.SQLname(data, col)
                colindex[name] = col

            def get(name, row):
                return sqlapi.SQLstring(data, colindex[name], row)

            deletions = []
            for row in range(sqlapi.SQLrows(data)):

                item = Item.ByKeys(get("teilenummer", row), get("t_index", row))

                if item and item.site_object_id and item.site_object_id != site_object_id:
                    deletions.append(row)

            deletions.reverse()
            for x in deletions:
                ref = data.rowof(x)
                data.remove(ref)


class IgnoredDifferences(Object):
    __maps_to__ = "cdbvp_diffutil_ignored"
    __classname__ = "cdbvp_diffutil_ignored"


class BomType(Object):
    __maps_to__ = "cdbvp_bom_type"
    __classname__ = "cdbvp_bom_type"

    __bom_types = None
    __bom_types_by_id = None

    _recovery = {'eBOM': {'cdb_object_id': 'af664278-1938-11eb-9e9d-10e7c6454cd1',
                          'name_de': 'Konstruktionsstückliste',
                          'name_en': 'Engineering BOM'},
                 'mBOM': {'cdb_object_id': '5d9558bd-351f-11e9-b15d-8851fb5f62f1',
                          'name_de': 'Fertigungsstückliste',
                          'name_en': 'Manufacturing BOM'},
                 }

    @classmethod
    def _init_bom_types(cls):
        if cls.__bom_types is None:
            bom_types = cls.Query()
            cls.__bom_types = {t.code: t for t in bom_types}
            cls.__bom_types_by_id = {t.cdb_object_id: t for t in bom_types}

            for bom_type in cls._recovery:
                if bom_type not in cls.__bom_types:
                    cls._recover(bom_type)

    @classmethod
    def _recover(cls, code):
        if code in cls._recovery:
            t = cls.Create(code=code, is_enabled=1, cdb_icon_id='bom_type_default', **cls._recovery[code])
            cls.__bom_types[code] = t
            cls.__bom_types_by_id[t.cdb_object_id] = t
            return t

    @classmethod
    def GetBomTypeForCode(cls, code):
        cls._init_bom_types()
        return cls.__bom_types[code]

    @classmethod
    def GetBomTypeForID(cls, type_id):
        cls._init_bom_types()
        return cls.__bom_types_by_id[type_id]

    @classmethod
    def getActiveBOMTypes(cls):
        cls._init_bom_types()
        if not fls.is_available("BOM_012"):
            # when the XBOM feature is not available, only return the mBOM BOM Type
            return [t for t in cls.__bom_types.values() if t.is_enabled == 1 and t.code in ["eBOM", "mBOM"]]
        else:
            return [t for t in cls.__bom_types.values() if t.is_enabled == 1]

    def allow_delete(self, ctx):
        if self.code in self._recovery:
            raise ue.Exception("cdbvp_err_delete_bom_type", self.code)

    def prevent_deactivate(self, ctx):
        if not self.is_enabled and self.code in self._recovery:
            raise ue.Exception("cdbvp_err_deactivate_bom_type", self.code)

    def disable_activate(self, ctx):
        if self.code in self._recovery:
            ctx.set_readonly('is_enabled')

    event_map = {
        ("delete", "pre"): "allow_delete",
        ('modify', 'pre_mask'): "disable_activate",
        ('modify', 'pre'): "prevent_deactivate"
    }


class PartUsage(ViewObject):
    __maps_to__ = "cdb_part_usage_v"
    __classname__ = "bom_item_usage"
