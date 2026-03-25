#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import logging

import cdbwrapc
from cdb import dberrors, sqlapi
from cs.platform.web.rest.support import values_from_rest_key
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common.webdata import util


class GenericAsyncDataModel:
    PAYLOAD_KEYS = set(["keys", "texts", "fields", "mapped"])

    def __init__(self):
        self.classdefs = {}
        self.tables = {}
        self.keynames = {}

    def _resolve_class(self, classname):
        "raises HTTPBadRequest if DB table and classdef cannot be found for classname"
        cldef, table = util.get_classinfo(classname)
        keynames = cldef.getKeyNames()
        self.classdefs[classname] = cldef
        self.tables[classname] = table
        self.keynames[classname] = keynames

    def read_payload(self, request):
        return {
            classname: self._resolve_query(classname, query)
            for classname, query in request.json.items()
        }

    def _resolve_query(self, classname, query):
        self._resolve_class(classname)

        try:
            # mandatory payload keys
            raw_keys = query["keys"]
        except KeyError as exc:
            logging.error(
                "GenericAsyncDataModel request missing 'keys': %s",
                query,
            )
            raise HTTPBadRequest from exc

        table = self.tables[classname]
        keynames = self.keynames[classname]
        keys = [values_from_rest_key(raw_key) for raw_key in raw_keys]
        condition = util.get_sql_condition(table, keynames, keys)

        # optional payload keys
        fields = query.get("fields", [])
        mapped = query.get("mapped", [])
        texts = query.get("texts", [])

        return condition, fields, mapped, texts

    def _get_data(self, classname, condition):
        table = self.tables[classname]
        return sqlapi.RecordSet2(table, condition, access="read")

    def get_fields(self, classname, data, fields):
        cldef = self.classdefs[classname]
        keynames = self.keynames[classname]
        return {
            util.get_rest_key(record, keynames): util.filter_dict(
                record,
                fields,
                cldef,
            )
            for record in data
        }

    def get_mapped(self, classname, data, mapped):
        keynames = self.keynames[classname]
        referers = util.get_mapped_referers(classname, mapped)

        return {
            util.get_rest_key(record, keynames): util.get_mapped_attrs(
                classname,
                record,
                referers,
                mapped,
            )
            for record in data
        }

    def get_text(self, keynames, keys, condition, text):
        try:
            data = sqlapi.RecordSet2(
                text,
                condition,  # only includes readable key combinations
                addtl=f"ORDER BY {keys}, zeile",
            )
        except dberrors.DBError as exc:
            # most likely DB table "text" does not exist
            logging.exception("get_text")
            raise HTTPBadRequest from exc

        results = [
            # is constructing rest keys repeatedly expensive?
            {util.get_rest_key(record, keynames): cdbwrapc.unescape_string(record.text)}
            for record in data
        ]

        merged = util.merge_results_str(*results)
        return {
            rest_key: {text: resolved_text}
            for rest_key, resolved_text in merged.items()
        }

    def get_texts(self, classname, readable_data, texts):
        table = self.tables[classname]
        keynames = self.keynames[classname]

        readable_condition = util.get_sql_condition(
            table,
            keynames,
            [[record[key] for key in keynames] for record in readable_data],
        )
        keys = ", ".join(keynames)
        return util.merge_results_dict(
            *[self.get_text(keynames, keys, readable_condition, text) for text in texts]
        )

    def get_data(self, request):
        # read_payload checks if payload is correct
        result = {}
        queries = self.read_payload(request)

        for classname, query in queries.items():
            condition, fields, mapped, texts = query
            # NOTE: _get_data checks for read access, but finding no object due to
            #       condition is as likely as finding no data due to missing read
            #       access, so algorithm is continued anyway
            data = self._get_data(classname, condition)

            result_fields = self.get_fields(classname, data, fields)
            result_mapped = self.get_mapped(classname, data, mapped)
            result_texts = self.get_texts(classname, data, texts)

            result[classname] = util.merge_results_dict(
                result_fields,
                result_mapped,
                result_texts,
            )

        return result
