#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.typeconversion import from_legacy_date_format, to_legacy_date_format


def date_from_legacy_str(legacy_date_str):
    if legacy_date_str:
        return from_legacy_date_format(legacy_date_str).date()
    return None


def to_legacy_str(date):
    return to_legacy_date_format(date, full=False)


def to_iso_date(date):
    return date.strftime("%Y-%m-%d")
