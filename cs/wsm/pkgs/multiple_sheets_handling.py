#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Analyses content of appinfo files of drawing documents
and creates sheet documents if present in appinfo.
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import logging
import six

from lxml import etree as ET

from cdb import transaction
from cdbwrapc import SimpleArgument, Operation
from cs.documents import SheetReference
from cs.wsm.result import Result, Error
from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext
from cs.wsm.pkgs.pkgsutils import getAppinfoContent

CREATE_SHEETS = False


@timingWrapper
@timingContext("PDMPOSTPROCESSOR sync_sheets")
def sync_sheets(doc, combine_model_layout, files):
    """
    :param doc: Document
    """
    if hasattr(doc, "additional_document_type"):
        if doc.additional_document_type == "1":
            try:
                content = getAppinfoContent(files)
                if content is not None:
                    appinfo = ET.fromstring(content)

                    with transaction.Transaction():
                        sync_sheets_from_appinfo(doc, appinfo, combine_model_layout)

            except Exception:
                logging.exception("syncSheets, unexpected error")
                return Error(u"Unexpected error when creating sheets")
    return Result()


def sync_sheets_from_appinfo(main_sheet_doc, appinfo, combine_model_layout):
    """
    :param main_sheet_doc: Document containing the appinfo
                           file and the drawing cad file
    :param appinfo: string containing XML
    """
    app_info_sheets = get_sheets_of_appinfo(appinfo)
    db_sheets = get_existing_sheets_from_db(main_sheet_doc)

    deleted_ids = set(db_sheets) - set(app_info_sheets)
    for sheet_id in deleted_ids:
        delete_sheet_from_db(main_sheet_doc, db_sheets[sheet_id])
    #  creating sheets should only be enabled be a setting
    #  in a later version of WSM
    #  For EWE use cases the sheets are created manually
    #  When re enabled the workspace manager must refresh
    #  the content of sheet documents after running
    #  post commit
    if CREATE_SHEETS:
        new_ids = set(app_info_sheets) - set(db_sheets)
        for sheetId in new_ids:
            create_sheet(main_sheet_doc, app_info_sheets[sheetId])

    modified_ids = set(db_sheets) & set(app_info_sheets)
    for sheet_id in modified_ids:
        modify_sheet(db_sheets[sheet_id], app_info_sheets[sheet_id])

    if main_sheet_doc.blattnr == "1":
        if main_sheet_doc.additional_document_type == "1":
            # the first sheet of a drawing will be the main sheet
            # the additional_document_type = 1 will be set by talkapi
            if len(app_info_sheets) > 0:
                blattanz = len(app_info_sheets)
                if combine_model_layout:
                    blattanz = len(app_info_sheets) - 1
                main_sheet_doc.Update(blattanz=blattanz)


def get_sheets_of_appinfo(root_element):
    """
    Retrieve all sheets from the appinfo.

    :param root_element: ETree root element of the appinfo
    :return: dict(sheet id -> ElementTree Element)
    """
    sheets = {}
    for sheetElement in root_element.findall("sheets/sheet"):
        sheet_id = sheetElement.get("id").strip()
        # we do not have to worry, which sheets we should filter, because
        # they are created manually
        sheets[sheet_id] = sheetElement
    return sheets


def get_existing_sheets_from_db(doc):
    """
    :param doc: Document
    :return: dict(sheet id -> Document)
    """
    sheets = {}
    for sheet in doc.DrawingSheets:
        sheets[sheet.sheet_id] = sheet
    return sheets


def get_args_from_xml_sheet_element(sheet_element):
    sheet_number = sheet_element.get("number").strip()
    args = {"sheet_id": sheet_element.get("id").strip(), "blattnr": sheet_number}
    if int(sheet_number) > 1:
        # we have a secondary sheet
        args["additional_document_type"] = "2"
    frame_elements = sheet_element.findall("frames/frame")
    if frame_elements:
        # DOES NOT WORK FOR PRO_E
        frame_pdm_id = frame_elements[0].get("pdmid")
        if frame_pdm_id:
            z_format, z_format_gruppe = frame_pdm_id.split("@")
            args["z_format"] = z_format
            args["z_format_gruppe"] = z_format_gruppe
    return args


def create_sheet(main_sheet_doc, sheet_element):
    """
    :param main_sheet_doc: Document containing the appinfo
                           file and the drawing cad file
    :param sheet_element: ElementTree Element representing a sheet
    """
    args = get_args_from_xml_sheet_element(sheet_element)
    args.update(
        {
            "teilenummer": main_sheet_doc.teilenummer,
            "t_index": main_sheet_doc.t_index,
            "erzeug_system": main_sheet_doc.erzeug_system,
            "z_categ1": main_sheet_doc.z_categ1,
            "z_categ2": main_sheet_doc.z_categ2,
        }
    )
    args = [SimpleArgument(k, str(v)) for k, v in six.iteritems(args)]
    op = Operation("CDB_Create", "model", args)
    op.run()
    created_sheet = op.getObjectResult()
    SheetReference.Create(
        z_index_origin=main_sheet_doc.z_index,
        z_nummer=main_sheet_doc.z_nummer,
        z_index=main_sheet_doc.z_index,
        z_nummer2=created_sheet.z_nummer,
        z_index2=created_sheet.z_index,
    )


def modify_sheet(db_sheet_doc, sheet_element):
    """
    :param db_sheet_doc: Document object
    :param sheet_element: ElementTree Element representing the sheet
    """
    do_update = False
    args = get_args_from_xml_sheet_element(sheet_element)
    if "z_format" in args and "z_format_gruppe" in args:
        do_update = (
            args["z_format"] != db_sheet_doc.z_format
            or args["z_format_gruppe"] != db_sheet_doc.z_format_gruppe
        )
    do_update = do_update or args.get("blattnr") != db_sheet_doc.blattnr
    if do_update:
        args = [SimpleArgument(k, str(v)) for k, v in six.iteritems(args)]
        op = Operation("CDB_Modify", db_sheet_doc.ToObjectHandle(), args)
        op.run()


def delete_sheet_from_db(main_sheet_doc, db_sheet_doc):
    """
    :param main_sheet_doc: Document containing the appinfo
                           file and the drawing cad file
    :param db_sheets: Document representing the sheet to delete
    """
    # 1. Delete the the Entries in cdb_drawing2sheets
    sheet_ref_to_delete = SheetReference.KeywordQuery(
        z_nummer=main_sheet_doc.z_nummer,
        z_index=main_sheet_doc.z_index,
        z_nummer2=db_sheet_doc.z_nummer,
        z_index2=db_sheet_doc.z_index,
    )
    if sheet_ref_to_delete:
        sheet_ref_to_delete.Delete()
    # 2. Delete the sheets documents but only if it is not referenced
    # from other drawings
    other_refs = SheetReference.KeywordQuery(
        z_nummer2=db_sheet_doc.z_nummer, z_index2=db_sheet_doc.z_index
    )
    if not other_refs:
        try:
            op = Operation("CDB_Delete", db_sheet_doc.ToObjectHandle(), [])
            op.run()
        except Exception:
            # catch exception here since if this delete goes
            # wrong we still have to delete the other sheets
            logging.exception("syncSheets, unexpected error while deleting a sheet")
