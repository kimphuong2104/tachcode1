#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import logging
from collections import defaultdict
from itertools import groupby
from operator import itemgetter

from cdb import sqlapi
from cdb.objects.org import CommonRole, User
from cs.platform.web.rest.generic import convert
from cs.platform.web.rest.support import _REPLACEMENTS, values_from_rest_key
from webob.exc import HTTPBadRequest

from cs.pcs.projects import Role
from cs.pcs.projects.common import format_in_condition
from cs.pcs.projects.common.webdata import util


def group_by_first_value(values, transform):
    key = itemgetter(0)
    result = {
        first: [transform(value) for value in all_values]
        for first, all_values in groupby(sorted(values, key=key), key)
    }
    return result


def get_rest_objects(table, keynames, rest_keys):
    keys = [values_from_rest_key(rest_key) for rest_key in rest_keys]
    condition = util.get_sql_condition(table, keynames, keys)
    return sqlapi.RecordSet2(table, condition, access="read")


# somewhat similar to cs.pcs.projects.common.rest_objects.rest_key
def get_rest_key(keynames, obj):
    res = []

    for k in keynames:
        keyname = ""
        for c in str(convert.dump_value(obj[k])).encode("utf-8"):
            c = chr(c)
            keyname += _REPLACEMENTS[c]
        res.append(keyname)

    return "@".join(res)


def parse_rest_id(rest_id):
    ":returns: `(restname, restkey)`"
    parts = rest_id.rsplit("/", 2)
    if len(parts) != 3:
        raise ValueError
    return tuple(parts[1:])


def make_absolute_url(request, rest_name_and_key):
    (rest_name, rest_key) = rest_name_and_key
    return f"{request.application_url}/api/v1/collection/{rest_name}/{rest_key}"


class BaseRoleModel:
    @classmethod
    def _resolve(cls, obj, field):
        return obj[field]

    @classmethod
    def resolve(cls, obj, field):
        try:
            return cls._resolve(obj, field)
        except KeyError:
            logging.error(
                "object is missing field '%s': %s",
                field,
                obj,
            )
            return None

    @classmethod
    def get_icon_and_label(cls, subject):
        return (
            subject.GetObjectIcon(),
            subject.GetDescription(),
        )

    @classmethod
    def load_thumbnails(cls, subject_ids):
        raise NotImplementedError


class PersonModel(BaseRoleModel):
    TYPE = User.__subject_type__
    URL_PATTERN = "/api/v1/collection/person/caddok/files/{}"

    @classmethod
    def get_icon_and_label(cls, subject):
        thumbnail = subject.GetThumbnailFile()
        return (
            (cls.URL_PATTERN.format(thumbnail.cdb_object_id) if thumbnail else None),
            subject.GetDescription(),
        )

    @classmethod
    def load_thumbnails(cls, subject_ids):
        users = User.Query(
            format_in_condition("personalnummer", subject_ids),
            access="read",
        )
        return {user.personalnummer: cls.get_icon_and_label(user) for user in users}


class CommonRoleModel(BaseRoleModel):
    TYPE = CommonRole.__subject_type__

    @classmethod
    def load_thumbnails(cls, subject_ids):
        condition = format_in_condition("role_id", subject_ids)
        roles = CommonRole.Query(condition, access="read")
        return {role.role_id: cls.get_icon_and_label(role) for role in roles}


class PCSRoleModel(BaseRoleModel):
    TYPE = Role.__subject_type__
    CTX_FIELD = "cdb_project_id"
    QUERY_PATTERN = "(cdb_project_id = '{}' AND {})"

    @classmethod
    def _get_id(cls, obj, field):
        return (obj[cls.CTX_FIELD], obj[field])

    @classmethod
    def _resolve(cls, obj, field):
        return cls._get_id(obj, field)

    @classmethod
    def load_thumbnails(cls, subject_ids):
        ids_by_project_id = group_by_first_value(subject_ids, lambda values: values[1])

        condition = " OR ".join(
            [
                cls.QUERY_PATTERN.format(
                    sqlapi.quote(project_id),
                    format_in_condition(
                        "role_id",
                        ids_by_project_id[project_id],
                    ),
                )
                for project_id in ids_by_project_id
            ]
        )

        return {
            cls._get_id(role, "role_id"): cls.get_icon_and_label(role)
            for role in Role.Query(condition, access="read")
        }


class SubjectThumbnailModel:
    SUBJECT_ID = "subject_id"
    SUBJECT_TYPE = "subject_type"
    SUBJECT_MODELS = {
        model.TYPE: model for model in [PersonModel, CommonRoleModel, PCSRoleModel]
    }

    def bad_request(self, msg, *replacements):
        logging.error(f"%s {msg}", self.__class__.__name__, *replacements)
        raise HTTPBadRequest

    def read_payload(self, request):
        """
        Validates input and converts absolute REST ID keys to internal IDs
        (2-tuples `(restname, restkey)`).

        :returns: Values of JSON payload indexed by 2-tuples
            `(restname, restkey)`
            Empty payload values are filtered out.
        :rtype: dict

        :raises HTTPBadRequest: if JSON payload is not a dict or
            any key consists of less than three URL segments.
        """
        payload = request.json

        if not isinstance(payload, dict):
            self.bad_request("not a dict: %s", payload)

        try:
            return {
                parse_rest_id(rest_id): fields
                for rest_id, fields in payload.items()
                if fields
            }
        except ValueError:
            self.bad_request("invalid REST URLs: %s", payload)

    def _get_model(self, subject_type):
        try:
            model = self.SUBJECT_MODELS[subject_type]
        except KeyError:
            logging.error(
                "%s unknown subject type: '%s'",
                self.__class__.__name__,
                subject_type,
            )
            return None

        return model

    def _get_objects(self, rest_ids):
        """
        Loads objects with one SQL statement per restname
        and returns then indexed by 2-tuple `(restname, restkey)`.
        """
        names_and_keys = rest_ids.keys()

        by_restnames = group_by_first_value(names_and_keys, lambda values: values[1])
        result = {}

        for restname, keys in by_restnames.items():
            cldef, table = util.get_classinfo_REST(restname)
            keynames = cldef.getKeyNames()
            objs = get_rest_objects(table, keynames, keys)
            # construct rest ids from objs because we don't know
            # 1. their order or
            # 2. if any are missing due to denied read access
            result.update(
                {(restname, get_rest_key(keynames, obj)): obj for obj in objs}
            )

        return result

    def _collect_subjects(self, fields_by_id, objects_by_id):
        """
        Collects subjects to be loaded by type (so simple fields containing
        persons and subjects of type "Person" are combined, for example)
        and remembers data to map results later on.
        """
        subs_to_resolve = defaultdict(list)
        subs_by_id = defaultdict(dict)

        def _get_type(obj, field):
            if field == self.SUBJECT_ID:
                return obj[self.SUBJECT_TYPE]
            else:
                return PersonModel.TYPE

        def _get_id(obj, field, subject_type):
            model = self._get_model(subject_type)
            if not model:
                return None
            return model.resolve(obj, field)

        for rest_id, obj in objects_by_id.items():
            for field in fields_by_id[rest_id]:
                subject_type = _get_type(obj, field)
                subject_id = _get_id(obj, field, subject_type)

                if subject_id:
                    subs_to_resolve[subject_type].append(subject_id)
                    subs_by_id[rest_id][field] = (subject_id, subject_type)

        return subs_to_resolve, subs_by_id

    def _load_thumbnails(self, subs_to_resolve):
        """
        Loads thumbnails with one SELECT per subject type.
        Keys of `subs_to_resolve` already are de-duplicated subject_types.
        """
        result = {}

        for subject_type, subject_ids in subs_to_resolve.items():
            model = self._get_model(subject_type)

            if not model:
                continue

            thumbnails = model.load_thumbnails(subject_ids)
            result[subject_type] = thumbnails

        return result

    def _prepare_response(self, request, subs_by_id, thumbnails):
        """
        Constructs the response from internal data:

        - combines data from internal sources
        - convert (restname, restkey) tuples (internal IDs)
          back to absolute URLs (ID in the frontend)
        """
        result = {}

        def _get_thumbnail(subject_id, subject_type):
            return thumbnails.get(subject_type, {}).get(subject_id)

        for rest_id, subject in subs_by_id.items():
            result[make_absolute_url(request, rest_id)] = {
                field: _get_thumbnail(*id_and_type)
                for field, id_and_type in subject.items()
            }

        return result

    def get_data(self, request):
        """
        Resolves subject thumbnails and labels for given `request`.
        Subjects may be persons, common roles and project roles.
        A JSON payload like this is expected:

        .. code-block :: json

            {
                "https://host:4711/api/v1/collection/project/P0": [
                    "cdb_cpersno"
                ]
            }

        :returns: Lists with subject thumbnail URL and subject label each
            indexed by field name, indexed by rest ID (URL)
        :rtype: dict

        Example response:

        .. code-block :: json

            {
                "https://host:4711/api/v1/collection/project/P0": {
                    "subject_id": [
                        "/api/v1/collection/person/caddok/files/123",
                        " Administrator  (caddok)"
                    ]
                }
            }

        :raises HTTPBadRequest: if the payload is invalid
        """
        fields_by_id = self.read_payload(request)
        objects_by_id = self._get_objects(fields_by_id)
        subs_to_resolve, subs_by_id = self._collect_subjects(
            fields_by_id, objects_by_id
        )
        thumbnails = self._load_thumbnails(subs_to_resolve)
        result = self._prepare_response(request, subs_by_id, thumbnails)
        return result
