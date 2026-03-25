#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import auth, fls
from cdb import sqlapi
from cs.platform.web.rest.support import decode_key_component


SPLIT_COUNT_ORACLE = 50
SPLIT_COUNT_MSSQL = 1000
SPLIT_COUNT_SQLITE = 500
SPLIT_COUNT_POSTGRES = 1000


def get_dbms_split_count():
    # Note: Oracle does not handle partitioning with bigger chunk sizes well,
    #       resulting in overall runtime increase. Therefore it has a smaller
    #       value than the other dbms, that still results in performance gain
    #       in comparison to no partitioning.
    db_type = sqlapi.SQLdbms()
    if db_type == sqlapi.DBMS_ORACLE:
        return SPLIT_COUNT_ORACLE
    elif db_type == sqlapi.DBMS_MSSQL:
        return SPLIT_COUNT_MSSQL
    elif db_type == sqlapi.DBMS_SQLITE:
        return SPLIT_COUNT_SQLITE
    elif db_type == sqlapi.DBMS_POSTGRES:
        return SPLIT_COUNT_POSTGRES
    else:
        raise KeyError(db_type)


def get_and_check_object(expectedClass, access_right, **kwargs):
    """
    Internal helper function for checking access right and retrieving
    requested object on REST EndPoint

    :param expectedClass: Objects class of requested object to check access rights on
    :type expectedClass: class derived from cdb.objects.Object

    :param access_right: access right to check
    :type access_right: string

    :param kwargs: keys to get requested object
    :type kwargs: dict

    :returns: requested object if found and requested access right given, None else
    :rtype: cdb.objects.Object
    """
    decoded_kwargs = {}
    for k, v in kwargs.items():
        decoded_kwargs[k] = decode_key_component(v) if type(v) is str else v
    obj = expectedClass.ByKeys(**decoded_kwargs)
    if not obj:
        return None
    if not obj.CheckAccess(access_right):
        logging.error(
            "REST-Model - user '%s' has no '%s' access on '%s': '%s'",
            auth.persno,
            access_right,
            expectedClass,
            decoded_kwargs,
        )
        return None
    return obj


def is_feature_licensed(feature_ids):
    """
    Internal helper function for checking if requested features are licensed.
    Logs a warning about missing license features, if any requested features
    are not licensed.

    :param feature_ids: List of feature ids to check for
    :type feature_ids: list of strings

    :returns: True if all requested feature are licensed, False else
    :rtype: boolean
    """
    unavailable = [
        feature_id for feature_id in feature_ids if not fls.is_available(feature_id)
    ]
    if unavailable:
        logging.warning("Missing license features %s", unavailable)
        return False
    return True
