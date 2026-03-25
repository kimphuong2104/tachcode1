#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

"""
Module foreignmigration

This module offers with create_links_for_workspaces()
a function for creating correct links in CIM DATABASE
and creates appinfos for the given links.

First all documents must be stored in CIM DATABASE:
After this all the links and the needed appinfos can
be created with create_links_for_workspaces().
"""

from __future__ import absolute_import
from __future__ import print_function

__docformat__ = "restructuredtext en"

import logging
import collections
import uuid
import tempfile
import os
import sys
from xml.etree import ElementTree

import six

from cdb.objects.cdb_file import CDB_File, cdb_link_item
from cdb import sqlapi, dberrors
from cdb import constants

from cs.wsm.cdbfilewsm import Cdb_file_wsm

CDBMiscLinkDescription = collections.namedtuple(
    "CDBLinkDesctription",
    [
        "dst_doc",
        "link_type",
        "link_id",
    ],
)


CDBDrawLinkDescription = collections.namedtuple(
    "CDBDrawLinkDesctription",
    [
        "dst_doc",
        "dst_variant",
        "sheet_id",
        "view_id",
    ],
)


CDBOccLinkDescription = collections.namedtuple(
    "CDBIOccLinkDesctription",
    [
        "dst_doc",
        "dst_variant",
        "occ_id",
    ],
)


class NotUniqueException(Exception):
    pass


class InvalidDocumentException(Exception):
    pass


def _build_dict(l):
    """
    Build a dictionary from cdb_object_id to list of LinkDescription
    """
    d = collections.defaultdict(list)
    if l:
        for e in l:
            d[e.dst_doc.cdb_object_id].append(e)
    return d


def _createDocRelEntry(document, referenced, cdb_link=0):
    if referenced.GetTableName() == "zeichnung":
        r = sqlapi.Record(
            "cdb_doc_rel",
            z_nummer=document.z_nummer,
            z_index=document.z_index,
            z_nummer2=referenced.z_nummer,
            z_index2=referenced.z_index,
            t_nummer2="",
            t_index2="",
            logischer_name="",
            reltype="WSM",
            owner_application="WSM",
            cdb_link=cdb_link,
            classname="",
            cad_link=0,
            cad_link_bez="",
            checkoutname="",
        )

        r.insert()


def _createCadReference(link):
    """ """
    cadref_element = ElementTree.Element("cadreference")
    fName = _getPrimaryFilepath(link.dst_doc)
    cadref_element.attrib["path"] = fName
    if link.dst_variant:
        cadref_element.attrib["variantid"] = link.dst_variant
    return cadref_element


def _getPrimaryFilepath(doc):
    primaryFile = doc.getPrimaryFile()
    fName = primaryFile.cdbf_name

    folderId = primaryFile.cdb_folder
    if folderId:
        folderPath = _getRelativePath(doc.cdb_object_id, folderId)
        if folderPath:
            fName = folderPath + fName
    return fName


def _getRelativePath(cdbf_object_id, folderId):
    relPath = ""
    while folderId:
        rs = sqlapi.RecordSet2(
            sql="SELECT cdbf_name, cdb_folder FROM cdb_file WHERE cdbf_object_id='%s' "
            "AND cdb_wspitem_id='%s'"
            % (sqlapi.quote(cdbf_object_id), sqlapi.quote(folderId))
        )
        if len(rs) == 1:
            folderName = rs[0].cdbf_name  # pylint: disable=no-member
            folderId = rs[0].cdb_folder  # pylint: disable=no-member
            relPath = folderName + "/" + relPath
        else:
            return None
    return relPath


def _add_sheet_links(appinfo_root, draw_links):
    sheets_node = ElementTree.Element("sheets")
    appinfo_root.append(sheets_node)
    sheet_to_views = collections.defaultdict(list)
    sheet_cnt = 1
    sort_value = 0

    for draw in draw_links:
        sheet_to_views[draw.sheet_id].append(draw)
    used_sheet_ids = set(sheet_to_views)
    for sheet_id, draw_links in six.iteritems(sheet_to_views):
        if not sheet_id:
            sheet_id = "%02d" % sheet_cnt
            while sheet_id in used_sheet_ids:
                sheet_cnt += 1
                sheet_id = "%02d" % sheet_cnt
            used_sheet_ids.add(sheet_id)
        sheet_element = ElementTree.Element("sheet")
        sheet_element.attrib["sortval"] = "%s" % sort_value
        sheet_element.attrib["id"] = sheet_id
        sheet_element.attrib["name"] = sheet_id
        sheet_element.attrib["number"] = "%s" % (sort_value + 1)
        sheets_node.append(sheet_element)
        sort_value += 1
        if draw_links:
            views_node = ElementTree.Element("views")
            sheet_element.append(views_node)
            for view in draw_links:
                view_id = view.view_id
                if not view_id:
                    view_id = "%s" % uuid.uuid4()
                view_node = ElementTree.Element("view")
                views_node.append(view_node)
                view_node.attrib["id"] = view_id
                view_node.attrib["scale"] = "1.0"  # assumed scale but is mandatory
                view_node.append(_createCadReference(view))


def _add_occ_links(appinfo_root, occ_links):
    occs_node = ElementTree.Element("occurrences")
    appinfo_root.append(occs_node)
    sort_val = 0
    for occ in occ_links:
        occ_id = occ.occ_id
        if not occ_id:
            occ_id = "%s" % uuid.uuid4()
        occ_el = ElementTree.Element("occurrence")
        occs_node.append(occ_el)
        occ_el.attrib["id"] = occ_id
        occ_el.attrib["suppressed"] = "no"
        occ_el.attrib["bom-relevant"] = "yes"
        occ_el.attrib["sortval"] = "%s" % sort_val
        occ_el.append(_createCadReference(occ))


def _add_link_elements(appinfo_root, misc_links):
    misc_links_node = ElementTree.Element("links")
    appinfo_root.append(misc_links_node)
    for link in misc_links:
        link_id = link.link_id
        if not link_id:
            link_id = "%s" % uuid.uuid4()
        link_el = ElementTree.Element("link")
        misc_links_node.append(link_el)
        link_el.attrib["id"] = link_id
        link_el.attrib["path"] = _getPrimaryFilepath(link.dst_doc)
        l_type = link.link_type
        if not l_type:
            l_type = "external"
        link_el.attrib["type"] = l_type


def writeAppinfoToTempFile(appinfo_root, work_dir, doc):
    dst_name = os.path.join(work_dir, doc.getPrimaryFile().cdbf_name + ".appinfo")
    with open(dst_name, "wb") as f:
        f.write(ElementTree.tostring(appinfo_root, encoding="utf-8"))
    return dst_name


def _createLink(src_doc, dst_doc, is_external):
    """
    Create links between src_doc and dst_doc. Create no link if src_doc.z_nummer == dst_doc.z_nummer
    """
    if src_doc.z_nummer == dst_doc.z_nummer:
        return

    condition = (
        "cdb_classname='cdb_link_item' AND "
        "cdbf_object_id = '%s' AND cdb_link='%s'"
        % (src_doc.cdb_object_id, dst_doc.cdb_object_id)
    )
    linksWithSameTarget = cdb_link_item.Query(condition)
    if not linksWithSameTarget:
        link_wsp_item_id = "%s" % uuid.uuid4()
        linkAttrs = {
            "cdbf_object_id": src_doc.cdb_object_id,
            "cdb_wspitem_id": link_wsp_item_id,
            "cdb_link": dst_doc.cdb_object_id,
            "cdb_folder": "",
        }
        cdb_link_item.Create(**linkAttrs)

        if is_external:
            fAttrs = {
                "is_external_link": 1,
                "wsm_manual_assigned": 0,
                "cdbf_object_id": src_doc.cdb_object_id,
                "file_wspitem_id": link_wsp_item_id,
            }
            Cdb_file_wsm.Create(**fAttrs)

    try:
        _createDocRelEntry(src_doc, dst_doc, 1 if is_external else 0)
    except dberrors.DBConstraintViolation:
        pass


def create_links_for_workspaces(
    doc,
    draw_links,
    occ_links,
    misc_links,
    mark_as_incomplete=True,
    overwrite_existing_appinfo=False,
    project_env=None,
):

    """
    :param doc: cs.documents.Document.
                The referencing document with exactly one primary file.
                For this document the appinfo will be written and
                appended as a file if it does not exist or
                overwrite_existing_appinfo is True.


    :param drawlinks: List of CDBOccLinkDescriptions.
               A destination document can be inserted more then once.
               All links with an emtpty sheet_id will be inserted
               in one sheet with a random unique_sheet_id.
               Non-empty sheet_ids must be unique.

               If view_id is empty for every document a random
               unique_sheet_id will be used.
               Not empty view_ids must be unique per sheet.


    :param occlinks: List of CDBOccLinkDescriptions.
                A destination document can be inserted more then once
                in case you like an appinfo with the correct number of
                occurrences. In case of occ_id is empty or None a
                random unique occ_id for this occurence will be
                generated.

    :param misc_links: List of CDBMiscLinkDescription.
                Link types are mandantory. (Standard is external).
                Non-empty link_ids must be unique. If link_id is
                empty an unique_link id will be generated.

    :param mark_as_incomplete: Boolean.
               if the given occ-links are complete and correct this flag
               can be set to False.

    :param overwrite_existing_appinfo:  Boolean.
               If an appinfo file for the primary file exists the existing
               file will be overwritten by the generated file
               from the given values.

    :param project_env: String.
               if not appinfo a projectenv tag will be created in a
               new or overwritten appinfo. If the appinfo exists no
               changes for the projectenv tag will be made.

    All destination documents must have excatly one primary file.


    Raises:
       NotUniqueException or underlying database exceptions
    """
    draw_dict = _build_dict(draw_links)
    occ_dict = _build_dict(occ_links)
    misc_dict = _build_dict(misc_links)
    direct_links = set(list(draw_dict) + list(occ_dict))
    only_misc = set(misc_dict.keys()) - direct_links
    if len(doc.PrimaryFiles) != 1:
        raise InvalidDocumentException(
            "No unique primary files %s %s" % (doc.z_nummer, doc.z_index)
        )
    primaryFile = doc.PrimaryFiles[0]
    existing_appinfos = doc.Files.KeywordQuery(
        cdb_belongsto=primaryFile.cdb_wspitem_id, cdbf_type=u"Appinfo"
    )
    existing_appinfo = None
    if existing_appinfos:
        existing_appinfo = existing_appinfos[0]
    needs_appinfo = overwrite_existing_appinfo or not existing_appinfo
    appinfo_root = None
    for l in direct_links:
        draw_link = draw_dict.get(l)
        if draw_link:
            dst_doc = draw_link[0].dst_doc
        else:
            dst_doc = occ_dict.get(l)[0].dst_doc
        _createLink(doc, dst_doc, False)
    for l in only_misc:
        _createLink(doc, misc_dict.get(l)[0].dst_doc, True)
    if needs_appinfo:
        appinfo_root = ElementTree.Element("appinfo")
        if project_env:
            p_el = ElementTree.Element("projectenv")
            p_el.attrib["value"] = project_env
            appinfo_root.append(p_el)
        if mark_as_incomplete:
            appinfo_root.attrib["incomplete-nodes"] = "noStructure"
        appinfo_root.attrib["parameterhash"] = "IGNORE"
        if draw_links:
            _add_sheet_links(appinfo_root, draw_links)
        if occ_links:
            _add_occ_links(appinfo_root, occ_links)
        if misc_links:
            _add_link_elements(appinfo_root, misc_links)
        work_dir = tempfile.mkdtemp(prefix="cdb_mig_")
        appinfo_filename = writeAppinfoToTempFile(appinfo_root, work_dir, doc)
        if existing_appinfo:
            existing_appinfo.checkin_file(
                appinfo_filename, {constants.kArgumentActiveIntegration: "wspmanager"}
            )
        else:
            args = {
                constants.kArgumentActiveIntegration: "wspmanager",
                "cdb_belongsto": doc.getPrimaryFile().cdb_wspitem_id,
                "cdbf_type": "Appinfo",
                "cdb_folder": primaryFile.cdb_folder,
            }
            appinfo_wspitemid = _find_appinfo_wspitem_id(doc)
            if appinfo_wspitemid is not None:
                args["cdb_wspitem_id"] = appinfo_wspitemid
            CDB_File.NewFromFile(doc.cdb_object_id, appinfo_filename, False, args)
        os.remove(appinfo_filename)
        os.rmdir(work_dir)


def _find_appinfo_wspitem_id(doc):
    """
    :param doc: Document
    :param appinfo_filename: str
    :return: cdb_wspitem_id or None
    """
    # find appinfos of primary files, belonging to documents with same z_nummer
    t = sqlapi.SQLselect(
        "af.cdb_wspitem_id, pf.cdb_wspitem_id, z_index"
        " FROM zeichnung z"
        " JOIN cdb_file af"  # appinfo
        "   ON af.cdbf_object_id = z.cdb_object_id"
        "  AND af.cdbf_type = 'Appinfo'"
        " JOIN cdb_file pf"  # primary file
        "   ON pf.cdbf_object_id = z.cdb_object_id"
        "  AND pf.cdbf_primary = '1'"
        " WHERE z.z_nummer = '%s'"
        "   AND af.cdb_belongsto = pf.cdb_wspitem_id"
        "   AND af.cdbf_object_id = pf.cdbf_object_id" % sqlapi.quote(doc.z_nummer)
    )
    has_inconsistencies = False
    primary_wspitem_id = None
    appinfo_wspitem_id = None
    for i in six.moves.range(sqlapi.SQLrows(t)):
        if primary_wspitem_id is None:
            primary_wspitem_id = sqlapi.SQLstring(t, 1, i)
        elif sqlapi.SQLstring(t, 1, i) != primary_wspitem_id:
            has_inconsistencies = True
        if appinfo_wspitem_id is None:
            appinfo_wspitem_id = sqlapi.SQLstring(t, 0, i)
        elif sqlapi.SQLstring(t, 0, i) != appinfo_wspitem_id:
            has_inconsistencies = True
    if has_inconsistencies:
        _log_warning(
            "WARNING: The files of a document should have the same cdb_wspitem_id accross different indexes."
        )
        for i in six.moves.range(sqlapi.SQLrows(t)):
            _log_warning(
                "cdb_wspitem_id of %s-%s\t: primary %s, appinfo %s"
                % (
                    doc.z_nummer,
                    sqlapi.SQLstring(t, 2, i),
                    sqlapi.SQLstring(t, 1, i),
                    sqlapi.SQLstring(t, 0, i),
                )
            )
    return appinfo_wspitem_id


def _log_warning(msg):
    logging.warning(msg)
    print(msg, file=sys.stderr)


def _test_sample():
    from cdb import transaction
    from cs.documents import Document

    with transaction.Transaction():
        doc = Document.ByKeys("000011-2", "")
        draw1_obj = Document.ByKeys("000000-3", "")
        draw2_obj = Document.ByKeys("000004-1", "")
        only_misc_obj = Document.ByKeys("000002-1", "")
        occ_obj = Document.ByKeys("000003-1", "")
        misc_links = [
            CDBMiscLinkDescription(only_misc_obj, "ext1", ""),
            CDBMiscLinkDescription(occ_obj, "ext2", "MyExtId"),
        ]
        occ_links = [CDBOccLinkDescription(occ_obj, "variant01", "MyOccId1")]
        draw_links = [
            CDBDrawLinkDescription(draw1_obj, "", "", ""),
            CDBDrawLinkDescription(draw2_obj, "", "named_sheet_id01", "name_view01"),
            CDBDrawLinkDescription(draw1_obj, "", "named_sheet_id01", ""),
        ]
        create_links_for_workspaces(
            doc, draw_links, occ_links, misc_links, project_env="TESTPR"
        )
        raise Exception("KK")


# Guard importing as main module
if __name__ == "__main__":
    # _test_sample()
    x = 1
