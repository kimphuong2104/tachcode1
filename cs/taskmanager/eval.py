#! /usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
cs.taskmanager attribute mapping term evaluation
"""

import contextlib
import inspect
import logging
from datetime import date, datetime

import cdbwrapc
from cdb import sqlapi
from cdb.objects import Object, ObjectCollection


@contextlib.contextmanager
def error_logging_disabled():
    # copied over from cdb.testcase to save expensive import
    cdbwrapc.cdblog_suppress_stderr(1)
    try:
        yield
    finally:
        cdbwrapc.cdblog_suppress_stderr(0)


def _eval(obj, simple_expression, **kwargs):
    # pylint: disable=too-many-return-statements
    if simple_expression.startswith("_"):
        logging.error(
            "cs.taskmanager.eval: trying to access private attribute '%s'",
            simple_expression,
        )
        return None

    error = False

    try:
        result = getattr(obj, simple_expression)
    except AttributeError:
        try:
            with error_logging_disabled():
                result = obj.GetText(simple_expression)
            if result == "":
                error = True
        except AttributeError:
            error = True

    if error:
        raise AttributeError

    if result == sqlapi.NULL or result is None:
        return None

    if isinstance(result, (Object, dict, str, str, int, float)):
        return result

    if isinstance(result, datetime):
        return result.isoformat()

    if isinstance(result, date):
        return "{}T00:00:00".format(result.isoformat())

    if isinstance(result, (ObjectCollection, list)):
        return len(result)

    if inspect.ismethod(result):
        try:
            return result(**kwargs)
        except:  # noqa: E722
            logging.exception(
                "could not evaluate method of object '%s' (%s)",
                obj.cdb_object_id,
                obj.__class__,
            )
            raise

    raise AttributeError


def evaluate(obj, complex_expression, **kwargs):
    if not (isinstance(obj, Object) and isinstance(complex_expression, str)):
        return None

    result = [obj]
    for path_expression in complex_expression.split("."):
        # if not done yet, we need an Object for further evaluation
        if not isinstance(result[-1], Object):
            return None

        # keep pushing evaluated results to result, eval on last result
        try:
            if path_expression == "":
                result.append(None)
            else:
                result.append(_eval(result[-1], path_expression, **kwargs))
        except AttributeError:
            logging.error(
                "cs.taskmanager.eval: "
                "trying to access non-existing attribute '%s' of object "
                "with id '%s'",
                path_expression,
                getattr(result[-1], "cdb_object_id", None),
            )
            result.append(None)
    return result[-1]
