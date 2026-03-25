#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
#
# $Id$
#
# Copyright (c) 2001,2002 by CONTACT Software GmbH.
# All rights reserved


from cdb.objects import Object, LocalizedField, State
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Reference_Methods
from cdb.objects import Forward
from cdb import util
from cdb import ue

from cs.vp.variants.vptools import WithChangeLog

fCatalogueProperty = Forward(__name__ + ".CatalogueProperty")
fCatalogueFolder = Forward(__name__ + ".CatalogueFolder")
fCatalogueEnumDefinition = Forward(__name__ + ".CatalogueEnumDefinition")
fCatalogueProperty2Folder = Forward(__name__ + ".CatalogueProperty2Folder")
fValueFolder = Forward(__name__ + ".ValueFolder")

fProperty = Forward("cs.vp.variants.properties.Property")


class CatalogueProperty(Object, WithChangeLog):
    __classname__ = "cdbvp_catalogue_property"
    __maps_to__ = "cdbvp_catalogue_property"

    Name = LocalizedField("name", fala=True)
    NameNoFala = LocalizedField("name")

    Values = Reference_N(fCatalogueEnumDefinition,
                         fCatalogueEnumDefinition.catalogue_property_object_id == fCatalogueProperty.cdb_object_id)
    ConnectionToFolders = Reference_N(fCatalogueProperty2Folder,
                                      fCatalogueProperty2Folder.property_object_id == fCatalogueProperty.cdb_object_id)

    def _getFolders(self):
        return [CatalogueFolder.ByKeys(conn.folder_object_id) for conn in self.ConnectionToFolders]
    Folders = Reference_Methods(fCatalogueFolder, _getFolders)

    ValueFolders = Reference_N(fValueFolder,
                               fValueFolder.property_object_id == fCatalogueProperty.cdb_object_id)

    Usages = Reference_N(fProperty,
                         fProperty.catalogue_property_object_id == fCatalogueProperty.cdb_object_id)

    class CREATED(State):
        status = 0

    class VALID(State):
        status = 100

    class INVALID(State):
        status = 200

    def assignFolder(self, ctx=None):
        if not ctx or ctx.relationship_name != "cdbvp_catalogue_folder2property":
            CatalogueProperty2Folder.CreateWithChangeLog(folder_object_id=CatalogueFolder.RootObjectID,
                                                         property_object_id=self.cdb_object_id)

    def fill_localized_fields(self, ctx=None):
        from cs.vp.variants.properties import fill_localized_fields
        fill_localized_fields(self.NameNoFala)

    def check_data_type(self, ctx):
        """
        Check switch of data types.
        Not allowed:
        alphanumeric -> numeric,
        alphanumeric -> boolean,
        numeric -> boolean
        """
        if (ctx.object.data_type == "alphanumeric" and self.data_type == "numeric") or \
           (ctx.object.data_type == "alphanumeric" and self.data_type == "boolean") or \
           (ctx.object.data_type == "numeric" and self.data_type == "boolean"):
                raise ue.Exception("cdbvp_data_type_modify", ctx.object.data_type, self.data_type)

    def set_erp_code(self, ctx):
        from cs.vp.variants.properties import set_erp_code
        set_erp_code(self, "sap_property")

    def preset_name(self, ctx):
        self.sap_property = "-- auto --"

    def set_erp_code_readonly(self, ctx):
        ctx.set_readonly("sap_property")

    def create_bool_prop_values(self, ctx):
        """
        Creates two catalogue property values if selected data_type is 'boolean'
        """
        if self.data_type == 'boolean':
            BOOL_VALUES = [0, 1]
            for value in BOOL_VALUES:
                args = dict(value=value,
                            name=value,
                            catalogue_property_object_id=self.cdb_object_id,
                            value_folder_object_id='')

                for lang in CatalogueEnumDefinition.ValueTxt.keys():
                    attrname = CatalogueEnumDefinition.ValueTxt[lang].name
                    args[attrname] = value

                CatalogueEnumDefinition.CreateWithChangeLog(**args)

    event_map = {("create", ("post")): ("assignFolder", "create_bool_prop_values"),
                 (("create", "modify", "copy"), "post_mask"): "fill_localized_fields",
                 ("modify", ("post_mask", "pre")): "check_data_type",
                 (("create", "copy"), ("post_mask")): "set_erp_code",
                 ("modify", "pre_mask"): "set_erp_code_readonly",
                 (("create", "copy"), ("pre_mask")): "preset_name"
                 }


class CatalogueFolder(Object, WithChangeLog):
    __classname__ = "cdbvp_catalogue_folder"
    __maps_to__ = "cdbvp_catalogue_folder"

    Parent = Reference_1(fCatalogueFolder, fCatalogueFolder.parent_object_id)
    SubFolders = Reference_N(fCatalogueFolder,
                             fCatalogueFolder.parent_object_id == fCatalogueFolder.cdb_object_id)

    LinkToProperties = Reference_N(fCatalogueProperty2Folder,
                                   fCatalogueProperty2Folder.folder_object_id == fCatalogueFolder.cdb_object_id)

    def _getProperties(self):
        return [lnk.Property for lnk in self.LinkToProperties]
    Properties = Reference_Methods(fCatalogueProperty, _getProperties)

    Name = LocalizedField("name")
    RootObjectID = "b70e3c2e-4e4c-11e1-8f85-001bfc744136"

    def update_parent_folder(self, parent_folder):
        """ Set the parent folder

            :param parent_folder: The parent folder, as a CatalogueFolder object.
                                  If None the root folder will be set as parent.
        """
        if not parent_folder and self.parent_object_id != self.RootObjectID:
            self.parent_object_id = self.RootObjectID
        elif self.parent_object_id != parent_folder.cdb_object_id:
            self.parent_object_id = parent_folder.cdb_object_id

    def move_properties(self, ctx):
        for prop in self.Properties:
            prop.assignFolder()

    event_map = {("delete", "pre"): "move_properties"}


class CatalogueEnumDefinition(Object, WithChangeLog):
    __classname__ = "cdbvp_catalogue_enum_def"
    __maps_to__ = "cdbvp_catalogue_enum_def"

    CatalogueProperty = Reference_1(fCatalogueProperty,
                                    fCatalogueProperty.cdb_object_id == fCatalogueEnumDefinition.catalogue_property_object_id)

    ValueFolder = Reference_1(fValueFolder,
                              fValueFolder.cdb_object_id == fCatalogueEnumDefinition.value_folder_object_id)

    ValueTxt = LocalizedField("value_txt", fala=True)
    ValueTxtNoFala = LocalizedField("value_txt")

    def makeValue(self, ctx=None):
        self.value = util.nextval("cdbvp_catalogue_enum_def_value")

    def preset_name(self, ctx):
        if self.CatalogueProperty.data_type == 'alphanumeric':
            self.name = "-- auto --"

    def set_name(self, ctx):
        if self.CatalogueProperty.data_type == 'alphanumeric' and self.name == "-- auto --":
            from cs.vp.variants.properties import generate_erp_name
            self.name = generate_erp_name(self.value_txt_de, CatalogueEnumDefinition.name.length)

    def setup_value_register(self, ctx):
        if self.CatalogueProperty:
            if self.CatalogueProperty.data_type == 'alphanumeric':
                ctx.disable_registers(["cdbvp_catalogue_number_def"])
                ctx.disable_registers(["cdbvp_catalogue_boolean_def"])
            elif self.CatalogueProperty.data_type == 'numeric':
                ctx.disable_registers(["cdbvp_catalogue_enum_def_reg"])
                ctx.disable_registers(["cdbvp_catalogue_boolean_def"])
            else:
                ctx.disable_registers(["cdbvp_catalogue_enum_def_reg"])
                ctx.disable_registers(["cdbvp_catalogue_number_def"])

    def handle_number_value(self, ctx=None):
        # TODO: check / convert number format
        if self.CatalogueProperty.data_type == 'numeric' or \
            self.CatalogueProperty.data_type == 'boolean':
                for lang in self.ValueTxt.keys():
                    self.ValueTxt[lang] = self.name

    def fill_localized_fields(self, ctx=None):
        if self.CatalogueProperty.data_type == 'alphanumeric':
            from cs.vp.variants.properties import fill_localized_fields
            fill_localized_fields(self.ValueTxtNoFala)

    def set_erp_code_readonly(self, ctx):
        ctx.set_readonly("name")

    def check_drag_and_drop(self, ctx):
        if ctx.dragged_obj_relationship_name == "cdbvp_catalogue_property2enum_def_wfolder":
            if self.CatalogueProperty.data_type == "boolean":
                raise ue.Exception("cdbvp_data_type_modify_bool")
            cat_prop = CatalogueProperty.ByKeys(value=ctx.dragged_obj.value,
                                                cdb_object_id=ctx.dragged_obj.catalogue_property_object_id)

            if cat_prop and self.CatalogueProperty.data_type == "numeric" and cat_prop.data_type == "alphanumeric":
                    raise ue.Exception("cdbvp_data_type_modify", self.CatalogueProperty.data_type, cat_prop.data_type)

    event_map = {(("create", "copy"), ("pre")): "makeValue",
                 (("create", "copy"), ("pre_mask")): "preset_name",
                 (("create", "copy"), ("post_mask")): "set_name",
                 (("create", "copy", "modify", "info", "query"), "pre_mask"): "setup_value_register",
                 (("create", "copy", "modify"), ("pre_mask", "pre")): "handle_number_value",
                 (("create", "modify", "copy"), "post_mask"): "fill_localized_fields",
                 ("create", "pre_mask"): "check_drag_and_drop",
                 ("modify", "pre_mask"): "set_erp_code_readonly"
                 }


class ValueFolder(Object, WithChangeLog):
    __maps_to__ = "cdbvp_catalogue_value_folder"
    __classname__ = "cdbvp_catalogue_value_folder"

    Parent = Reference_1(fValueFolder, fValueFolder.parent_object_id)
    SubFolders = Reference_N(fValueFolder,
                             fValueFolder.parent_object_id == fValueFolder.cdb_object_id)
    CatalogueProperty = Reference_1(fCatalogueProperty,
                                    fValueFolder.property_object_id)

    Values = Reference_N(fCatalogueEnumDefinition,
                         fCatalogueEnumDefinition.value_folder_object_id == fValueFolder.cdb_object_id)

    Name = LocalizedField("name")

    def check_catalogue_property(self, ctx):
        if self.property_object_id != ctx.object.property_object_id:
            raise ue.Exception("cdbvp_catalogue_value_folder_property_modified")

    def set_property_readonly(self, ctx):
        ctx.set_readonly("property_object_id")

    event_map = {("modify", "pre_mask"): "set_property_readonly",
                 ("modify", "post_mask"): "check_catalogue_property"}


class CatalogueProperty2Folder(Object, WithChangeLog):
    __classname__ = "cdbvp_catalogue_prop2folder"
    __maps_to__ = "cdbvp_catalogue_prop2folder"

    Property = Reference_1(fCatalogueProperty,
                           fCatalogueProperty.cdb_object_id == fCatalogueProperty2Folder.property_object_id)
    Folder = Reference_1(fCatalogueFolder,
                         fCatalogueFolder.cdb_object_id == fCatalogueProperty2Folder.folder_object_id)

    def assignProperty(self, ctx=None):
        if len(self.Property.Folders) == 1:
            if self.Folder.cdb_object_id == CatalogueFolder.RootObjectID:
                raise ue.Exception(9835)
            else:
                self.Property.assignFolder()

    def deleteAssignmentToRoot(self, ctx):
        if self.folder_object_id != CatalogueFolder.RootObjectID:
            assignments = CatalogueProperty2Folder.KeywordQuery(property_object_id=self.Property.cdb_object_id,
                                                                folder_object_id=CatalogueFolder.RootObjectID)
            for ass in assignments:
                ass.Delete()

    event_map = {("delete", ("pre")): "assignProperty",
                 ("create", ("post")): "deleteAssignmentToRoot"
                 }
