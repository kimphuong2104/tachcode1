#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
import logging

from cdb import constants, sig, sqlapi, ue, util
from cdb.objects import (
    Forward,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_N,
    State,
)
from cdb.objects.operations import operation, system_args
from cdbwrapc import StatusInfo
from cs.audittrail import WithAuditTrail
from cs.classification import api, tools
from cs.classification.rest.utils import ensure_json_serialiability
from cs.currency import Currency
from cs.sharing.share_objects import WithSharing

fDiagram = Forward("cs.materials.diagram.Diagram")
fMaterial = Forward("cs.materials.Material")
fMaterial2Material = Forward("cs.materials.Material2Material")
fMaterial2Alternative = Forward("cs.materials.Material2Alternative")
fMaterial2Document = Forward("cs.materials.Material2Document")
fMaterial2Supplier = Forward("cs.materials.Material2Supplier")


class MaterialStates(object):
    """Lifecycle states for the standard materials lifecycle."""

    DRAFT = 0
    REVIEW = 100
    OBSOLETE = 180
    RELEASED = 200


class Material(Object, WithAuditTrail, WithSharing):
    """Implements the business logic for the csmat_material class as part of material data management."""

    __classname__ = "csmat_material"
    __maps_to__ = "csmat_material"

    LOG = logging.getLogger(__name__)

    EXPORT_ATTRIBUTES = [
        "material_id",
        "material_index",
        "name",
        "short_name",
        "status",
        "variant_type",
    ]

    Diagrams = Reference_N(
        fDiagram,
        fDiagram.material_id == fMaterial.material_id,
        fDiagram.material_index == fMaterial.material_index,
    )

    MaterialChildrenRel = Reference_N(
        fMaterial2Material,
        fMaterial2Material.parent_id == fMaterial.material_id,
        fMaterial2Material.parent_index == fMaterial.material_index,
    )

    MaterialAlternativeRel = Reference_N(
        fMaterial2Alternative,
        fMaterial2Alternative.material_id == fMaterial.material_id,
        fMaterial2Alternative.material_index == fMaterial.material_index,
    )

    MaterialDocumentRel = Reference_N(
        fMaterial2Document,
        fMaterial2Document.material_id == fMaterial.material_id,
        fMaterial2Document.material_index == fMaterial.material_index,
    )

    MaterialSupplierRel = Reference_N(
        fMaterial2Supplier,
        fMaterial2Supplier.material_id == fMaterial.material_id,
        fMaterial2Supplier.material_index == fMaterial.material_index,
    )

    def _get_material_from_rel(self):
        stmt = """SELECT m.*
                  FROM csmat_material2material m2m
                  JOIN csmat_material m ON m.material_id=m2m.child_id  AND m.material_index=m2m.child_index
                  WHERE m2m.parent_id='{}' AND m2m.parent_index='{}'
                  ORDER BY m.material_id, m.material_index""".format(
            self.material_id, self.material_index
        )
        result = Material.SQL(stmt)
        return result

    MaterialChildren = ReferenceMethods_N(fMaterial, _get_material_from_rel)

    MaterialVariants = Reference_N(
        fMaterial,
        fMaterial.variant_of_oid == fMaterial.cdb_object_id,
    )

    @staticmethod
    def is_index_operation(ctx):
        """Checks if a copy operation is actually a "create index" operation.

        :param ctx: The userexit context. If the sys_args of the context contain the key "isIndexOperation",
                    the operation is a "create index" operation, otherwise it is a plain "copy" operation.

        :return: True if the operation is a "create index" operation, False if it is a plain "copy" operation.
        """

        sysArgNames = ctx.sys_args.get_attribute_names()
        return "isIndexOperation" in sysArgNames

    @staticmethod
    def get_original_object(ctx):
        """Returns the object on which the create_index userexit was originally called.

        :param ctx: The userexit context. The sys_args of the context contain a key "originalObject"
                    which maps to a json string which holds the primary key attributes of the Material object.

        :return: The Material object on which the create_index userexit was originally called or None if
                 no such object was found.
        """

        originalObject = None
        sysArgNames = ctx.sys_args.get_attribute_names()
        if "originalObject" in sysArgNames:
            originalObject = ctx.sys_args["originalObject"]
            objectKeys = json.loads(originalObject)
            originalObject = Material.ByKeys(
                objectKeys["material_id"], objectKeys["material_index"]
            )
        return originalObject

    @staticmethod
    def _create_projection(alias=""):
        """Creates a list of all database columns of this class, optionally prepending each column name
        with a column alias.

        :param alias: The optional column alias for each column.
        :return: The comma separated list of columns for this class."""

        if alias:
            alias = alias + "."
        fields = [alias + x for x in Material.GetFieldNames()]
        result = ", ".join(fields)
        return result

    def get_parent_variants(self):
        """
        Recursively collects all parent variants of this material.
        The starting material itself is not part of the result.
        """

        # Execute hierarchical query of the variant structure.
        # * The first SELECT determines the start node
        # * The second SELECT executes the recursive query for each parent variant node
        column_list = Material._create_projection()
        projection1 = Material._create_projection("m")
        projection2 = Material._create_projection("t2")
        stmt = (
            "WITH {recursive} t({column_list}) AS ( "
            "   SELECT {p1} "
            "   FROM csmat_material m "
            "   WHERE m.material_id='{start_id}' AND m.material_index='{start_index}' "
            "UNION ALL "
            "   SELECT {p2} "
            "   FROM csmat_material t2 "
            "   JOIN t ON t.variant_of_oid = t2.cdb_object_id "
            ") SELECT * "
            "  FROM t "
            "  WHERE cdb_object_id <> '{myself}'".format(
                recursive="RECURSIVE"
                if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES
                else "",
                column_list=column_list,
                p1=projection1,
                p2=projection2,
                start_id=self.material_id,
                start_index=self.material_index,
                myself=self.cdb_object_id,
            )
        )
        result = Material.SQL(stmt)
        return result

    def get_variants_deep(self):
        """Recursively collects all variants which have been created from this material.
        The starting material itself is not part of the result.

        Note that this is not a real tree query - the result contains all variants in the tree,
        but the indentation level is not available in the result and also the order of the objects
        in the result does not reflect the real hierarchy."""

        # Execute hierarchical query of the variant structure.
        # * The first SELECT determines the start node
        # * The second SELECT executes the recursive query for each child variant node
        column_list = Material._create_projection()
        projection1 = Material._create_projection("m")
        projection2 = Material._create_projection("t2")

        stmt = (
            "WITH {recursive} t({column_list}) AS ( "
            "   SELECT {p1} "
            "   FROM csmat_material m "
            "   WHERE m.material_id='{start_id}' AND m.material_index='{start_index}' "
            "UNION ALL "
            "   SELECT {p2} "
            "   FROM csmat_material t2 "
            "   JOIN t ON t.cdb_object_id = t2.variant_of_oid "
            ") SELECT * "
            "  FROM t "
            "  WHERE cdb_object_id <> '{myself}'".format(
                recursive="RECURSIVE"
                if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES
                else "",
                column_list=column_list,
                p1=projection1,
                p2=projection2,
                start_id=self.material_id,
                start_index=self.material_index,
                myself=self.cdb_object_id,
            )
        )
        result = Material.SQL(stmt)
        return result

    def get_next_index(self):
        """Selects the maximum index used for this material object and returns the next index.
           This default implementation simply returns an increasing number ("1", "2", "3", ...),
           but can be customized to return any desired index number scheme.

        :return: A String with the new index.
        """

        newIndex = 1

        # query the current maximum number (No bind variables??)
        sql = (
            "select max(material_index) maxno "
            "from csmat_material "
            "where material_id='{}'".format(self.material_id)
        )
        r = sqlapi.RecordSet2(sql=sql)

        # Calculate the next index
        currentIndex = None
        if r:
            currentIndex = r[0].maxno
            try:
                # try to increment the number
                newIndex = int(currentIndex) + 1
            except ValueError:
                pass

        return str(newIndex)

    def set_previous_obsolete(self):
        """Sets all indexes of the current material which are in state RELEASED to OBSOLETE."""

        materials = Material.KeywordQuery(
            material_id=self.material_id, status=MaterialStates.RELEASED
        )
        for m in materials:
            m.ChangeState(MaterialStates.OBSOLETE)

    def ensure_children_released(self):
        """Ensures that all children of this material are in the RELEASED status.

        :raises ue.Exception: if at least one children is not in the RELEASED status."""

        for child in self.MaterialChildren:
            if child.status != MaterialStates.RELEASED:
                raise ue.Exception("csmat_material_childs_not_released")

    def ensure_short_name_unique(self, ctx):
        """Ensures that the short_name is unique when creating or copying a base material.

        :param ctx: The userexit context
        :raises ue.Exception: if the short name already exists."""

        if (
            ctx.relationship_name != "csmat_material2variant"
            and not self.is_index_operation(ctx)
        ):
            existing_materials = Material.KeywordQuery(short_name=self.short_name)
            if existing_materials:
                raise ue.Exception(
                    "csmat_material_short_name_not_unique", self.short_name
                )

    def ensure_modify_short_name_unique(self, ctx):
        """Ensures that the short_name is still unique when it was modified during a modify operation.

        :param ctx: The userexit context
        :raises ue.Exception: if the short name already exists."""

        if (
            ctx.relationship_name != "csmat_material2variant"
            and not self.is_index_operation(ctx)
            and ctx.object["short_name"] != self.short_name
        ):
            existing_materials = Material.KeywordQuery(short_name=self.short_name)
            if existing_materials:
                raise ue.Exception(
                    "csmat_material_short_name_not_unique", self.short_name
                )

    def set_default_id_and_index(self, ctx):
        """Sets the material id and index when a new material is created from scratch, by copying an
        existing material or through a create index operation.

        :param ctx: The userexit context"""

        if Material.is_index_operation(ctx):
            self.material_index = self.get_next_index()
        else:
            self.material_id = "M{:06d}".format(util.nextval("MATERIAL_ID_SEQ"))
            self.material_index = ""

    @staticmethod
    def set_status_text_hook(hook):
        """Maps the cdb_objektart and status attributes to the corresponding status name and sets it
        in corresponding field of the current Web UI dialog.

        :param hook: The dialog hook context."""

        cdb_objektart = hook.get_new_value("csmat_material.cdb_objektart")
        status_number = hook.get_new_value("csmat_material.status")

        info = StatusInfo(cdb_objektart, status_number)
        hook.set("status_text_calculated", info.getLabel())

    def set_status_text(self, ctx):
        """Maps the cdb_objektart and status attributes to the corresponding status name.

        :param ctx: The userexit context"""

        # pre-mask is also executed in unit tests, but dialog specific functions are not available there
        if ctx.dialog:
            if ctx.action in ["info", "modify"]:
                # for info and modify actions, get the status name and update the status_text_calculated field
                if self.cdb_objektart is not None and self.status is not None:
                    info = StatusInfo(self.cdb_objektart, self.status)
                    ctx.set("status_text_calculated", info.getLabel())
            else:
                # For all other actions, hide the status_text_calculated field
                ctx.set_hidden("status_text_calculated")

    def set_defaults_for_variant(self, ctx):
        """Sets the initial values for a new variant to the values from the original material.

        :param self: The new material object
        :param ctx: The userexit context"""

        if ctx.relationship_name == "csmat_material2variant":
            # Retrieve the source material
            sourceMaterial = Material.ByKeys(cdb_object_id=self.variant_of_oid)
            if sourceMaterial:
                # Copy all fields, skip primary keys, foreign keys and some system attributes
                for fieldName in self.GetFieldNames():
                    if fieldName not in [
                        "cdb_object_id",
                        "material_id",
                        "material_index",
                        "cdb_status_txt",
                        "status",
                        "cdb_objektart",
                        "cdb_cdate",
                        "cdb_cpersno",
                        "cdb_mdate",
                        "cdb_mpersno",
                        "variant_of_oid",
                        "variant_type",
                    ]:
                        ctx.set(fieldName, sourceMaterial[fieldName])

                # Setup the classification data in the derived material
                clsData = api.get_classification(sourceMaterial, narrowed=False)
                tools.preset_mask_data(clsData, ctx)

    def copy_relationships_for_variant(self, ctx):
        """Copies all necessary relationships from the base material to the newly created variant.

        :param self: The new material variant object
        :param ctx: The userexit context"""

        if ctx.relationship_name == "csmat_material2variant":
            sourceMaterial = Material.ByKeys(cdb_object_id=self.variant_of_oid)

            for materialChildrenRel in sourceMaterial.MaterialChildrenRel:
                create_args = {
                    "parent_id": self.material_id,
                    "parent_index": self.material_index,
                }
                operation(constants.kOperationCopy, materialChildrenRel, **create_args)

    def setup_fields(self, ctx):
        """Setup visibility of fields on the material masks."""

        if ctx.dialog:
            # Handle the create mask
            if ctx.action == "create":
                if ctx.relationship_name != "csmat_material2variant":
                    ctx.set_hidden("variant_of_oid")
                    ctx.set_hidden("mapped_variant_type_name")
                    ctx.set_optional("mapped_variant_type_name")

            # Handle info- and modify masks
            elif ctx.action not in ["query", "requery"]:
                # base material - hide the variant specific fields
                if not self.variant_of_oid:
                    ctx.set_hidden("variant_of_oid")
                    ctx.set_hidden("mapped_variant_type_name")
                    ctx.set_optional("mapped_variant_type_name")

    def set_variant_query_condition(self, ctx):
        """Extends the search condition for variants, depending on the setting of the
        "Variants Only" checkbox in the search mask

        :param ctx: The userexit context
        """

        if "is_material_variant" in ctx.dialog.get_attribute_names():
            if ctx.dialog["is_material_variant"] == "1":
                ctx.set_additional_query_cond(
                    "variant_type is not null and variant_type <> ''"
                )
            elif ctx.dialog["is_material_variant"] == "0":
                ctx.set_additional_query_cond(
                    "variant_type is null or variant_type = ''"
                )

    def create_index(self, ctx):
        """Creates a new Index for the currently selected material."""

        if self.status != MaterialStates.RELEASED:
            raise ue.Exception("csmat_material_not_released")

        # Get name/value pairs for the primary key
        keyValues = {key: self[key] for key in self.KeyNames()}
        keyValueString = json.dumps(keyValues)

        # Call the CDB_Copy operation with a flag to indicate that this is really an Index operation
        sys_args = system_args(isIndexOperation=True, originalObject=keyValueString)
        material_idx = operation("CDB_Copy", self.ToObjectHandle(), sys_args)
        ctx.set_object_result(material_idx)

    def export(self, ctx):
        from cs.materials.material_export import export_material

        export_material(self, ctx)

    def to_json(self):
        curve_data = []
        for diagram in self.Diagrams:
            curve_data.append(diagram.to_json())
        classification_data = api.get_classification(self)
        json_data = {
            "curve_data": curve_data,
            "properties": ensure_json_serialiability(classification_data["properties"]),
        }
        for attr in Material.EXPORT_ATTRIBUTES:
            json_data[attr] = self[attr]

        variant_of_id = None
        variant_of_index = None
        if self.variant_of_oid:
            baseMaterial = Material.ByKeys(cdb_object_id=self.variant_of_oid)
            variant_of_id = baseMaterial.material_id
            variant_of_index = baseMaterial.material_index
        json_data["variant_of_id"] = variant_of_id
        json_data["variant_of_index"] = variant_of_index

        return json_data

    class RELEASED(State):
        status = MaterialStates.RELEASED

        def pre(state, self, ctx):
            """pre-action userexit for material RELEASED state.

            :param state: The state object (RELEASED).
            :param self: The Material object on which the state change is executed.
            :param ctx: The userexit context."""

            # Make sure that all child materials of this material are in RELEASED state
            self.ensure_children_released()

            # Before changing the state of the current material to RELEASED, set all materials
            # which are currently in RELEASED state to OBSOLETE.
            self.set_previous_obsolete()

    event_map = {
        ("create", "pre_mask"): "set_defaults_for_variant",
        ("create", "post"): "copy_relationships_for_variant",
        ("*", "pre_mask"): ("set_status_text", "setup_fields"),
        ("modify", "pre"): "ensure_modify_short_name_unique",
        (("create", "copy"), "pre"): (
            "ensure_short_name_unique",
            "set_default_id_and_index",
        ),
        (("query", "requery", "query_catalog"), "pre"): "set_variant_query_condition",
        ("csmat_create_index", "now"): "create_index",
        ("csmat_material_export", "now"): "export",
    }


@sig.connect(Material, list, "csmat_diff", "now")
def material_diff(materials, ctx):
    from urllib.parse import urlencode

    url_params = {}
    if materials:
        url_params["material_0"] = "{}@{}".format(
            materials[0].material_id, materials[0].material_index
        )
    if len(materials) > 1:
        url_params["material_1"] = "{}@{}".format(
            materials[1].material_id, materials[1].material_index
        )

    url = "/byname/csmat_diff?{url_args}".format(url_args=urlencode(url_params))
    ctx.url(url)


class Material2Material(Object):
    """Implements the business logic for the csmat_material2material relationship."""

    __classname__ = "csmat_material2material"
    __maps_to__ = "csmat_material2material"

    MaterialData = Reference_1(
        Material,
        Material.material_id == fMaterial2Material.child_id,
        Material.material_index == fMaterial2Material.child_index,
    )

    def check_recursion(self, _):
        """Checks if assigning a material to another material would lead to an endless recursion.

        :raises ue.Exception: if adding the material would lead to an endless recursion in the material
                              hierarchy.
        """

        # Check trivial case: assigning a material to itself
        if self.child_id == self.parent_id and self.child_index == self.parent_index:
            raise ue.Exception("csmat_material_recursion")

        # Execute hierarchical query of the path upwards to a top level node.
        # * The first SELECT determines the start node
        # * The second SELECT executes the recursive query for each parent node
        # This would result in a list of all nodes from the given parent up to a top level node
        # (with no parent). The final WHERE clause reduces this list to at most one row (where the
        # parent is identical to the child to be added). If such a row exists, it indicates that
        # adding the new child would lead to an endless recursion.
        stmt = (
            "WITH {recursive} t(child_id, child_index, parent_id, parent_index) AS ( "
            "   SELECT child_id, child_index, parent_id, parent_index "
            "   FROM csmat_material2material "
            "   WHERE child_id='{parent_id}' AND child_index='{parent_index}' "
            "UNION ALL "
            "   SELECT t2.child_id, t2.child_index, t2.parent_id, t2.parent_index "
            "   FROM csmat_material2material t2 "
            "   JOIN t ON t.parent_id = t2.child_id AND t.parent_index=t2.child_index "
            ") SELECT * "
            "  FROM t "
            "  WHERE parent_id = '{child_id}' AND parent_index = '{child_index}'".format(
                recursive="RECURSIVE"
                if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES
                else "",
                parent_id=self.parent_id,
                parent_index=self.parent_index,
                child_id=self.child_id,
                child_index=self.child_index,
            )
        )
        rset = sqlapi.RecordSet2(sql=stmt)
        if rset:
            raise ue.Exception("csmat_material_recursion")

    event_map = {
        ("create", "pre"): "check_recursion",
    }


class Material2Supplier(Object):
    """Implements the business logic for the csmat_material2supplier relationship."""

    __classname__ = "csmat_material2supplier"
    __maps_to__ = "csmat_material2supplier"

    def presetCurrency(self, ctx):
        if not self.currency_object_id:
            dft_curr = Currency.getDefaultCurrency()
            if dft_curr:
                self.currency_object_id = dft_curr.cdb_object_id

    event_map = {
        (("copy", "create", "modify"), "pre_mask"): "presetCurrency",
    }


class Material2Document(Object):
    """Implements the business logic for the csmat_material2document relationship."""

    __classname__ = "csmat_material2document"
    __maps_to__ = "csmat_material2document"


class Material2Alternative(Object):
    """Implements the business logic for the csmat_material2alternative relationship."""

    __classname__ = "csmat_material2alternative"
    __maps_to__ = "csmat_material2alternative"


class VariantType(Object):
    """Implements the business logic for the variant types catalog."""

    __classname__ = "csmat_material_vartype"
    __maps_to__ = "csmat_material_vartype"


class MaterialUnit(Object):
    """Implements the business logic for the material specific quantity units catalog."""

    __classname__ = "csmat_material_unit"
    __maps_to__ = "csmat_material_unit"
