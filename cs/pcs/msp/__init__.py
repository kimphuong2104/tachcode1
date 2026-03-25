#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
The interface between |cs.pcs| and |tm.project| is based on
|tm.project| own XML-format.
For further information regarding the XML schema please refer to
`Microsofts Developer Network <https://msdn.microsoft.com/en-us/library/bb428843.aspx>`_.
"""

from cdb import CADDOK, cad, kernel, ue, util
from cdb.classbody import classbody
from cdb.constants import kOperationCopy
from cdb.objects import Object
from cdb.objects.operations import operation, system_args

from cs.pcs.msp.export_mapping import XmlExportConfiguration
from cs.pcs.msp.import_mapping import XmlMergeImportConfiguration
from cs.pcs.msp.misc import logger
from cs.pcs.msp.web.exports import APP
from cs.pcs.msp.web.imports.main import IMPORT_RESULT_APP_NAME
from cs.pcs.projects import Project

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@classbody  # noqa
class Project:
    """This class provides the logic of the |tm.project| interface"""

    XML_IMPORT_CLASS = XmlMergeImportConfiguration
    """Reference to the class in which the behavior during the import is
    completely embedded.

    You can customize the reference in derived classes.
    """
    XML_EXPORT_CLASS = XmlExportConfiguration
    """Reference to the class in which the behavior during the export is
    completely embedded.

    You can customize the reference in derived classes.
    """

    def on_import_from_xml_now(self, ctx):
        if ctx.uses_webui:
            return
        doc_keys = None
        if set(["z_nummer", "z_index"]) <= set(ctx.sys_args.get_attribute_names()):
            # called from OfficeLink
            doc_keys = {
                "z_nummer": ctx.sys_args.z_nummer,
                "z_index": ctx.sys_args.z_index,
            }
        elif ctx.catalog_selection:
            doc_keys = ctx.catalog_selection[0]

        if not doc_keys:
            catalog_attr = {
                "cdb_project_id": self.cdb_project_id,
                "erzeug_system": "MS-Project or XML",
            }
            ctx.start_selection(catalog_name="cdbpcs_msp_xml_brows", **catalog_attr)

        else:
            called_from_officelink = getattr(ctx, "active_integration") == "OfficeLink"
            if ctx.interactive:
                ctx.url(
                    f"/{IMPORT_RESULT_APP_NAME}?cdb_project_id={self.cdb_project_id}&ce_baseline_id={''}"
                    f"&z_nummer={doc_keys['z_nummer']}"
                    f"&z_index={doc_keys['z_index']}"
                    f"&called_from_officelink={called_from_officelink}"
                )
            else:  # support batch mode (e.g. for automated tests)
                self.XML_IMPORT_CLASS.import_project_from_xml(
                    self, doc_keys, False, called_from_officelink
                )

    def get_readonly_task_fields(self):
        return self.XML_IMPORT_CLASS.get_readonly_task_fields()

    def on_export_to_xml_pre_mask(self, ctx):
        if not ctx.uses_webui:
            xml_filename = f"{CADDOK.CLIENT_WORKDIR}{self.cdb_project_id}.xml"
            logger.info("presetting dialog with file name '%s'", xml_filename)
            ctx.set("xml_filename", xml_filename)

    def get_temp_export_xml_file(self):
        return self.XML_EXPORT_CLASS.generate_xml_from_project(self)

    def on_export_to_xml_now(self, ctx):
        if not self.CheckAccess("read"):
            raise ue.Exception("cdbpcs_no_project_right")

        if ctx.uses_webui:
            ctx.url(f"/internal/{APP}/export/{self.cdb_project_id}")
        else:
            temp_filename = self.get_temp_export_xml_file()
            client_file_path = ctx.dialog["xml_filename"]
            logger.info("uploading xml file to client file path '%s'", client_file_path)
            ctx.upload_to_client(temp_filename, client_file_path)

    def set_msp_default_times(self):
        """
        This method gets called before importing and exporting XML projects.
        It can be used to fully or partially customize the times.

        Example: Different duration of 8.5 hours by changing the default end time to 17:30

        .. code-block:: python

            if self.CalendarProfile.name.startswith("Switzerland"):
                self.XML_IMPORT_CLASS.DEFAULT_FINISH_TIME = "17:30"
                self.XML_IMPORT_CLASS.DEFAULT_DURATION = 8.5
                self.XML_EXPORT_CLASS.DEFAULT_FINISH_TIME = "17:30"
                self.XML_EXPORT_CLASS.DEFAULT_DURATION = 8.5
        """
        pass

    def get_msp_time_schedule_template(self):
        """
        Returns a system-wide defined time schedule document template.
        This method can be overwritten when there's a need to return different
        templates e.g. depending on the project category.

        :return: time schedule document template
        :rtype: instance of cs.documents.Document
        """
        return self.get_msp_template()

    def get_msp_template(self):
        """
        Retrieve a globally defined MS Project template. This method can be overwritten when there's
        a need to return different MS Project templates e.g. depending on the project category.
        """
        from cs.documents import Document

        template_doc = None
        template_config = util.PersonalSettings().getValueOrDefault(
            "cs.pcs.msp.template", "", ""
        )
        if template_config:
            index = cad.getMaxIndex(template_config, Document.__maps_to__)
            template_doc = Document.ByKeys(z_nummer=template_config, z_index=index)
            while (
                template_doc
                and template_doc.cdb_obsolete
                and template_doc.z_status != 200
            ):
                index = kernel.get_prev_index(
                    template_doc.z_nummer,
                    template_doc.z_index,
                    template_doc.__maps_to__,
                )
                template_doc = Document.ByKeys(
                    z_nummer=self.template_config, z_index=index
                )
        return template_doc

    def addMSPSchedule(self, ctx=None, force=False):
        """
        Auto copy a globally defined MS Project document into a project (not yet having a defined MS
        Project plan), when..
        - the project just got switched to have MSP as the project editor.
        - the project got copied from a another project having MS Project set as the project editor.
        - the project just got created with MS Project set as the project editor.
        When 'force' is True then also add the document even if MSP is not set as project editor.
        On success returns the copied template document, else returns None.
        """
        persistent_object = self.getPersistentObject()
        new_doc = None
        if (
            persistent_object.msp_active or force
        ) and not persistent_object.msp_z_nummer:
            template_doc = persistent_object.get_msp_time_schedule_template()
            if template_doc:
                from cs.documents import Document

                attr_length = getattr(Document, "titel").length
                proj_desc = persistent_object.GetDescription()
                kwargs = {
                    "vorlagen_kz": 0,
                    "cdb_project_id": persistent_object.cdb_project_id,
                    "titel": proj_desc,
                    "dateiname": ""
                    if len(proj_desc) <= attr_length
                    else (proj_desc[: attr_length - 3] + "..."),
                }
                new_doc = operation(
                    kOperationCopy,
                    template_doc,
                    system_args(force_new_filename=1),
                    **kwargs,
                )
                persistent_object.msp_z_nummer = new_doc.z_nummer
        return new_doc

    def on_cdbpcs_msp_import_preview_now(self, ctx):
        latest_primary = self.getLastPrimaryMSPDocument()
        if not latest_primary:
            raise ue.Exception("cdbpcs_msp_no_primary_mpp", self.cdb_project_id)
        url = (
            f"/cs-pcs-msp-imports-result?cdb_project_id={self.cdb_project_id}"
            f"&z_nummer={latest_primary.z_nummer}&z_index={latest_primary.z_index}"
        )
        ctx.url(url)


class MSPActiveOptions(Object):
    __maps_to__ = "cdbpcs_msp_active_options"
    __classname__ = "cdbpcs_msp_active_options"
