#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import datetime
import logging
from urllib.parse import quote, urlencode

import webob
from cdb import sqlapi, util
from cdb.objects import ByID
from cdb.objects.iconcache import IconCache, _LabelValueAccessor
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.olc import StatusInfo
from cs.documents import Document
from cs.platform.web import rest
from cs.platform.web.rest.support import get_restlink
from cs.platform.web.uisupport import get_webui_link
from cs.platform.web.uisupport.resttable import RestTableDefWrapper
from cs.web.components.configurable_ui import SinglePageModel

from cs.pcs.projects_documents import AbstractTemplateDocRef

DOCUMENT_CLASS_NAME = "document"
DOC_TEMPLATES_APP_TABLE_DEF = "cdb_doc_templates_group"
valid_index = "valid_index"


def get_icon_url(icon_id, query):
    icon_url = f"/resources/icons/byname/{quote(icon_id)}"

    if query:
        query_str = urlencode(query)
        return f"{icon_url}?{query_str}"
    else:
        return icon_url


def get_status_label(kind, status):
    try:
        info = StatusInfo(kind, status)
    except (TypeError, ValueError):
        logging.exception("invalid status: '%s', %s", kind, status)
        return None

    return info.getLabel()


class DocTemplatesModel(SinglePageModel):
    def __init__(self, object_id):
        self.object_id = object_id

    def _is_icon_column(self, col):
        return col.get("kind", -1) == 100

    def get_columns_data(self, document, col):
        """
        :param document: document with its properties.
        :type document: dict

        :param col: Table column with its properties.
        :type col: dict

        :returns: single column value
        :rtype: datetime/float/otherwise

        This method computes for a datetime object its ISO
        format representation, rounds float values to
        two digits, or returns the object itself.
        """
        attr = col["attribute"]
        if self._is_icon_column(col):
            if attr == "State Color":
                query = [
                    ("sys::workflow", document.z_art),
                    ("sys::status", document.status),
                ]
                return {
                    "icon": {
                        "src": get_icon_url(attr, query),
                        "title": get_status_label(document.z_art, document.status),
                    }
                }
            else:
                return {
                    "icon": {
                        "src": IconCache.getIcon(
                            attr, accessor=_LabelValueAccessor(document)
                        )
                    }
                }
        value = document[attr]
        if isinstance(value, datetime.date):
            return value.isoformat()
        elif isinstance(value, float):
            return round(value, 2)
        else:
            return value

    @classmethod
    def update_doc_title(cls, doc_templates_data, doc_templates_rows):
        for doc_template in doc_templates_data:
            _doc_list = [
                x
                for x in doc_templates_rows
                if (
                    x["z_index"] == doc_template["title_index"]
                    and x["z_nummer"] == doc_template["z_nummer"]
                )
            ]
            if _doc_list:
                doc_template["title"] = _doc_list[0]["titel"]
            else:
                doc_template["title"] = util.get_label("missed_document")

    @staticmethod
    def get_sorted_rows(rows):
        return sorted(rows, key=lambda x: (len(x.z_index), x.z_index))

    def update_cond_stmt(self, doc_templates_data, stmt_cond):
        """
        for each doc_template_link, will update the SQL statment condition to return documents
        based on the tmpl_index value of the doc_template_link
              - Case 1:
                      If tmpl_index is empty string will return all document
                      indexes with same z_nummer as of doc_template_link
              - Case 2:
                      If tmpl_index is equal to valid_index will return only
                      latest valid_document with same z_nummer as of doc_template_link
                      and newer indexes
              - Case 3:
                      If tmpl_index is equal to specifc index, then will return all documents
                      with that specific index and newer indexes where z_nummer is same as
                      of doc_template_link
        """
        length_cond = "LEN" if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL else "LENGTH"
        for doc_template in doc_templates_data:
            z_nummer_stmt = f"z_nummer = '{doc_template['z_nummer']}' "
            if not doc_template["tmpl_index"]:
                doc_template["title_index"] = ""
                stmt_cond.append(z_nummer_stmt)
            elif doc_template["tmpl_index"] == valid_index:
                doc_index_rows = Document.KeywordQuery(
                    z_nummer=doc_template["z_nummer"]
                )
                valid_doc = AbstractTemplateDocRef.get_valid_doc(doc_index_rows)
                if valid_doc:
                    title_index = valid_doc.z_index
                elif doc_index_rows:
                    title_index = self.get_sorted_rows(doc_index_rows)[0].z_index
                else:
                    title_index = util.get_label("missed_document")
                doc_template["title_index"] = title_index
                stmt_cond.append(
                    f"({z_nummer_stmt} AND ((z_index >= '{title_index}' "
                    f"AND {length_cond}(z_index) = {len(title_index)}) "
                    f"OR {length_cond}(z_index) > {len(title_index)})) "
                )
            else:
                doc_template["title_index"] = doc_template["tmpl_index"]
                stmt_cond.append(
                    f"({z_nummer_stmt} "
                    f"AND ((z_index >= '{doc_template['tmpl_index']}' "
                    f"AND {length_cond}(z_index) = {len(doc_template['tmpl_index'])}) "
                    f"OR {length_cond}(z_index) > {len(doc_template['tmpl_index'])})) "
                )

    def get_row_data(self, document, cols, request):
        """
        :param document: document with its properties.
        :type document: dict

        :param cols: Table columns with its properties.
        :type cols: dict

        :param request: HTML request information.
        :type request: HTML Request

        :returns: Document with all its properties.
        :rtype: dict

        This method generates a dict of a Document.
        """
        collection = rest.get_collection_app(request)
        document_rest_obj = request.view(document, app=collection)

        document_rest_obj.update(
            {
                "id": document["cdb_object_id"],
                "restLink": document_rest_obj["@id"]
                if "@id" in document_rest_obj
                else get_restlink(document),
                "persistent_id": document["cdb_object_id"],
                "uiLink": get_webui_link(None, document),
                "columns": [self.get_columns_data(document, col) for col in cols],
            }
        )
        return document_rest_obj

    def get_doc_templates_data(self, request):
        """
        :param request: HTML request information.
        :type request: HTML Request

        :returns: Doc Templates data for specific object.
        :rtype: dict

        """
        result = {}

        try:
            if not self.object_id:
                logging.exception("No date passed or wrong date format used.")
                raise webob.exc.HTTPBadRequest()
        except ValueError as exc:
            logging.exception("No date passed or wrong date format used.")
            raise webob.exc.HTTPBadRequest() from exc

        parent_object = ByID(self.object_id)
        relship_objects = parent_object.get_doc_template_references()

        stmt_cond = []
        doc_templates_data = [
            {
                "restLink": get_restlink(obj, request),
                "z_nummer": obj.z_nummer,
                "instantiation_state": obj.instantiation_state,
                "tmpl_index": obj.tmpl_index,
                "instantiation_state_txt": AbstractTemplateDocRef.get_instantion_state_txt(
                    obj.instantiation_state, parent_object.cdb_objektart
                ),
                "project_id": parent_object.cdb_project_id,
            }
            for obj in relship_objects
        ]

        self.update_cond_stmt(doc_templates_data, stmt_cond)

        for doc in doc_templates_data:
            if doc["tmpl_index"] == valid_index:
                doc["tmpl_index"] = util.get_label(valid_index)
            elif doc["tmpl_index"] == "":
                doc["tmpl_index"] = util.get_label("initial_index")

        cond = "OR ".join(stmt_cond)
        if cond:
            doc_templates_rows = Document.Query(cond)
        else:
            doc_templates_rows = []

        cols = ColumnsModel.get_columns()["columns"]
        doc_templates_rows = [
            self.get_row_data(document, cols, request)
            for document in doc_templates_rows
        ]

        default_group_by = []
        for col in cols:
            if col["attribute"] == "z_nummer":
                default_group_by.append(col["id"])

        # Set a title for the relation document, as there might be different title for each index
        self.update_doc_title(doc_templates_data, doc_templates_rows)

        result = {
            "rows": doc_templates_rows,
            "columns": cols,
            "initGroupBy": default_group_by,
            "object_doc_templates": doc_templates_data,
        }

        return result


class ColumnsModel(SinglePageModel):
    @classmethod
    def get_columns(cls):
        """
        :returns: JSON structure which contains the table definition.
        :rtype: dict

        This method returns the table definition for the document class.
        """
        class_def = CDBClassDef(DOCUMENT_CLASS_NAME)
        tabledef = class_def.getProjection(DOC_TEMPLATES_APP_TABLE_DEF, True)
        return RestTableDefWrapper(tabledef).get_rest_data()
