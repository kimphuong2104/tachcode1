# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

import logging
import json


from cdb import ue, util
from cdb import cad
from cdb.classbody import classbody
from cdb.objects import Object
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import Forward

from cs import documents
from cs.documents import Document
from cs.vp.items import Item
from cs.vp.cad.file_type_list import FileTypeList

from cs.vp.cad.queries import (
    model_query_with_classified_parts,
    model_query_including_variant_parts,
    create_part_condition)

from cs.web.components.outlet_config import OutletPositionCallbackBase

fCADVariant = Forward(__name__ + ".CADVariant")

FILE_TYPE_PDF = "Acrobat"
SUPPORTED_IMAGE_TYPES = FileTypeList("PNG", "JPG", "JPEG")
FILE_TYPE_SCZ = "Hoops:SCZ"

LOGGER = logging.getLogger(__name__)


class CADVariant(Object):
    """Stores information about variants of documents from the Workspace Manager.
    This information is used in the automatic BOM creation (Stücklistenausleitung).
    """
    __maps_to__ = "cad_variant"
    __classname__ = "cad_variant"

    Item = Reference_1(Item, fCADVariant.teilenummer, fCADVariant.t_index)

    def _check_partno(self, ctx=None):
        """ Checks that the part number / index point to a valid part
        """
        if self.teilenummer and not self.Item:
            raise ue.Exception("part_number", self.teilenummer, self.t_index)

    event_map = {(('create', 'modify', 'copy'), 'pre'): '_check_partno'
                 }


class CADVariantCategory(Object):
    __maps_to__ = "cdb_cad_variant_categ"


class CADVariantStatus(Object):
    __maps_to__ = "cdb_cad_variant_status"


class CADVariantDocumentAssignment(Object):
    __maps_to__ = "cad_variant2document"


@classbody
class Document(object):
    CADVariants = Reference_N(
        CADVariant,
        CADVariant.z_nummer == Document.z_nummer,
        CADVariant.z_index == Document.z_index)

    def __get_files_of_type(self, file_types):
        found_derived_or_associated_files = []
        found_primary_files = []
        found_other_files = []

        files = self.Files
        for f in files:
            type_requested = file_types.contains(f.cdbf_type)
            if not type_requested:
                continue

            # Preview derived/associated first, then primary files and others last.
            if f.cdbf_derived_from or f.cdb_belongsto:
                found_derived_or_associated_files.append(f)
            elif f.cdbf_primary == "1":
                found_primary_files.append(f)
            else:
                found_other_files.append(f)

        return found_derived_or_associated_files + found_primary_files + found_other_files

    def get_2d_preview_pdfs(self):
        """
        Searches for all pdf files. The files are returned in the following order:

        - PDF-Files derived of or associated to other files are sorted first.
        - Primary PDF files are sorted second.
        - The remaining PDFs are sorted last.

        :return: list of CDB_Files if found, empty list else
        """
        return self.__get_files_of_type(FileTypeList(FILE_TYPE_PDF))

    def get_2d_supported_preview_images(self):
        """
        Searches for all images suitable for the image preview. The files are returned in the following order:

        - Images derived of or associated to other files are sorted first.
        - Primary images are sorted second.
        - The remaining images are sorted last.

        :return: list of CDB_Files if found, empty list else
        """
        return self.__get_files_of_type(SUPPORTED_IMAGE_TYPES)

    def is_3d_preview_available(self):
        """
        Reports whether an .scz-file (required for the 3D preview) is present on the document.

        :return: True if the document contains an .scz-File and can thus be previewed by the 3D viewer,
                 False otherwise.
        """
        files = self.Files
        return any(f.cdbf_type == FILE_TYPE_SCZ for f in files)

    def cad_change_gensystem(self, new_system):
        """
        Called by the component ``cad_change_gensystem`` due to an integration
        import with a different ``erzeug_system``.
        You may overwrite this function to implement different behaviour.
        The methods `cad_change_gensystem_change_primary_flag` and
        `cad_change_gensystem_remove_files` might help you to implement.
        If you want to cancel the integration function and show a message
        in the integration use return [1001, "<your text>"],
        for example:
        return [1001, "Changing application isn't supported."]
        """

        LOGGER.debug("cad_change_gensystem to %s", new_system)

        if (self.erzeug_system, new_system) in [("ProE:Part", "ProE:GenPart"),
                                                ("ProE:GenPart", "ProE:Part"),
                                                ("ProE:Asmbly", "ProE:GenAsmbly"),
                                                ("ProE:GenAsmbly", "ProE:Asmbly")]:
            self.Update(erzeug_system=new_system)
            self.cad_change_gensystem_change_primary_flag_if_primaryfile(new_system)

        else:
            self.Update(erzeug_system=new_system, z_format="", z_format_gruppe="")
            self.cad_change_gensystem_change_primary_flag(new_system)

        return [0, ""]

    def cad_change_gensystem_change_primary_flag_if_primaryfile(self, new_system):
        """
        Set primary flag and cdbf_type in files with the new system.
        To use in `cad_change_gensystem`.
        """

        for f in self.Files:
            if (f.cdbf_type, new_system) in [("ProE:Part", "ProE:GenPart"),
                                             ("ProE:GenPart", "ProE:Part"),
                                             ("ProE:Asmbly", "ProE:GenAsmbly"),
                                             ("ProE:GenAsmbly", "ProE:Asmbly")]:
                f.Update(cdbf_type=new_system, cdbf_primary="1")
                LOGGER.debug("cdbf_type set to '%s' in file %s",
                             new_system, f.cdbf_name)
                LOGGER.debug("primary flag set to '1' in file %s", f.cdbf_name)
            else:
                if f.cdbf_type != new_system and f.cdbf_primary != "0":
                    f.Update(cdbf_primary="0")
                    LOGGER.debug("primary flag set to '0' in file %s",
                                 f.cdbf_name)
                if f.cdbf_type == new_system and f.cdbf_primary == "0":
                    f.Update(cdbf_primary="1")
                    LOGGER.debug("primary flag set to '1' in file %s",
                                 f.cdbf_name)

    def cad_change_gensystem_change_primary_flag(self, new_system):
        """
        Set primary flag in files with the new system.
        To use in `cad_change_gensystem`.
        """

        for f in self.Files:
            if f.cdbf_type != new_system and f.cdbf_primary != "0":
                f.Update(cdbf_primary="0")
                LOGGER.debug("primary flag set to '0' in file %s", f.cdbf_name)
            if f.cdbf_type == new_system and f.cdbf_primary == "0":
                f.Update(cdbf_primary="1")
                LOGGER.debug("primary flag set to '1' in file %s", f.cdbf_name)

    def cad_change_gensystem_remove_files(self):
        """
        Delete all files.
        To use in `cad_change_gensystem`,
        if you want to delete the old files before importing a new file.
        """

        LOGGER.debug("cad_change_gensystem_remove_files called")
        for f in self.PrimaryFiles:
            f.delete_file()
        for f in self.Files:
            f.delete_file()


class Model(documents.Document):
    __classname__ = "model"
    __match__ = documents.Document.cdb_classname >= __classname__

    def GetThumbnailFile(self):
        preview_images = self.get_2d_supported_preview_images()
        return preview_images[0] if preview_images else None

    def modify_query_condition(self, ctx):
        # Get the Consider CAD variant items flag - supported in both PC Client and Web UI
        consider_cad_variant_items = False
        if hasattr(ctx.dialog, "consider_cad_variant_items"):
            consider_cad_variant_items = ctx.dialog.consider_cad_variant_items == '1'

        # Get the part classification search parameters - currently only supported in Web UI
        part_classification_params = None
        if (ctx.uses_webui and hasattr(ctx.dialog, "part_classification_web_ctrl")
                and ctx.dialog.part_classification_web_ctrl):
            part_classification_params = json.loads(ctx.dialog.part_classification_web_ctrl)

        # TODO: Untersuchen: Leere dictionary-elemente - kann passieren wenn klasse wieder rausgenommen wird
        # => assigned_classes = {}
        if consider_cad_variant_items:
            # Get name/value pairs for the search criteria along with the final WHERE condition
            attrs = {name: ctx.dialog[name] for name in ctx.dialog.get_attribute_names()}
            part_attributes, where_stmt = create_part_condition(attrs)

            # Setup temporary table with all models which match the search criteria
            cond = model_query_including_variant_parts("model", "zeichnung_v", part_classification_params,
                                                       where_stmt)

            # Setup the final query - TODO: Only if something is set!
            ctx.ignore_in_query(part_attributes)
            ctx.set_additional_query_cond(cond[0])
            ctx.set_additional_from_rel(cond[1])
        elif part_classification_params:
            cond = model_query_with_classified_parts("model", "zeichnung_v", part_classification_params)

            # cond[0]: Additional condition to join classified data from the temporary table
            #         (e.g. "tt_classified.uuid='c2a0f860-5119-43b5-8b4a-500129cac27a' AND
            #                tt_classified.relation='part_v' AND
            #                tt_classified.cdb_object_id=ts.cdb_object_id")
            # cond[1]: Additional table and alias to query from (e.g. 'ftrquery tt_classified')

            # Setup the final query - TODO: only if something is to set!
            ctx.set_additional_query_cond(cond[0])
            ctx.set_additional_from_rel(cond[1])

        # else:
        #    Normal search, no part classification, no variants

    @staticmethod
    def is_cad_variant_support_enabled():
        """
        :return: True if CAD variants are enabled on the system, False otherwise.
        """

        cven = util.get_prop("cven")
        return cven == '1'

    def setup_classification_register(self, ctx):
        """
        Disables the client specific search mask registers for the part classification search.
        Currently, only the Web UI is supported - in the case of the PC client, the Web UI specific mask
        register is just disabled.

        :param ctx: The userexit context.
        """

        if not ctx.uses_webui:
            ctx.disable_registers(['cs_vp_part_classification_s_web'])

    def setup_variant_search_flag(self, ctx):
        """
        Hides the "Consider CAD variant items" checkbox if CAD variants are not supported in this installation.

        :param ctx: The userexit context.
        """

        if not Model.is_cad_variant_support_enabled():
            ctx.set_hidden("consider_cad_variant_items")

    event_map = {
        (("query", "requery"), 'pre'): 'modify_query_condition',
        (("query", "requery"), 'pre_mask'): ('setup_classification_register', 'setup_variant_search_flag')
    }


class SelectedObjectInfoConfig(OutletPositionCallbackBase):
    """Setup class for the SelectedObjectInfo outlet - configures the cad variant table to be shown or
    hidden"""

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        """
        Store a flag to determine whether CAD variant support is enabled in the Outlet properties.
        This flag will be passed to the frontend as a React prop.

        :param pos_config: A dictionary containing the properties for the Outlet position.
        :param cldef: The class definition of the object which is selected.
        :param obj: The selected object.
        :return: The modified Outlet properties dictionary. Needs to be returned as list to fulfill the
                 caller contract.
        """

        pos_config["properties"]["cad_variant_search_enabled"] = Model.is_cad_variant_support_enabled()
        return [pos_config]


def hook_model_max_part_index(hook):
    """
    Dialog hook for model indexing dialog to handle checkbox `Maximum existing` (part index).

    On checkbox activation:
    - Disables the checkbox `Create Part Index`
    - Presets the maximum available part index
    - Sets the model index to the next minor index, if minor indexing is activated (see properties spix and ixsf)

    On checkbox deactivation:
    - Sets the part index to the current index of the model
    """
    use_max_part_index = hook.get_new_value("cdb::argument.max_part_index")
    if use_max_part_index:
        # clear other checkbox as only one can be active
        hook.set("cdb::argument.create_part_index", 0)
        # set max existing part index
        max_index = cad.getMaxIndex(
            hook.get_new_value("teilenummer"), "teile_stamm"
        )
        hook.set("cdb::argument.t_index_neu", max_index)

        new_doc_index_without_part_index, new_doc_index_with_part_index = cad.get_next_doc_index(
            hook.get_new_value("z_nummer"))
        hook.set("cdb::argument.z_index_neu", new_doc_index_without_part_index)
    else:
        # use current part index
        hook.set("cdb::argument.t_index_neu", hook.get_new_value("t_index"))


def hook_model_create_part_index(hook):
    """
    Dialog hook for model indexing dialog to handle checkbox `Create Part Index`.

    On checkbox activation:
    - Disables the checkbox `Maximum existing`
    - Sets the part index to the next index (part index to be created)
    - Sets the document index to the next index, which is always a major index

    On checkbox deactivation
    - Sets the part index to the current index of the model
    - Sets the model index to the next minor index, if minor indexing is activated (see properties spix and ixsf)
    """
    new_doc_index_without_part_index, new_doc_index_with_part_index = cad.get_next_doc_index(
        hook.get_new_value("z_nummer"))
    create_part_index = hook.get_new_value("cdb::argument.create_part_index")
    if create_part_index:
        # clear other checkbox as only one can be active
        hook.set("cdb::argument.max_part_index", 0)
        # set next available part index
        next_index = cad.get_next_part_index(hook.get_new_value("teilenummer"))
        hook.set("cdb::argument.t_index_neu", next_index[0])
        hook.set("cdb::argument.z_index_neu", new_doc_index_with_part_index)
    else:
        # use current part index
        hook.set("cdb::argument.t_index_neu", hook.get_new_value("t_index"))
        hook.set("cdb::argument.z_index_neu", new_doc_index_without_part_index)

