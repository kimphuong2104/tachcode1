#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
User specific per-chart option settings.
"""


__revision__ = "$Id$"

from cdb import transactions
from cdb.objects import Object


class ChartConfig(Object):
    __maps_to__ = "cdbpcs_chart_config"
    __classname__ = "cdbpcs_chart_config"

    @classmethod
    def getValue(cls, persno, chart_oid, attr_type, attr):
        obj = cls.ByKeys(
            persno=persno, chart_oid=chart_oid, attr_type=attr_type, attr=attr
        )
        return obj.value if obj is not None else None

    @classmethod
    def setValue(cls, persno, chart_oid, attr_type, attr, value):
        obj = cls.ByKeys(
            persno=persno, chart_oid=chart_oid, attr_type=attr_type, attr=attr
        )
        if obj is None:
            cls.Create(
                persno=persno,
                chart_oid=chart_oid,
                attr_type=attr_type,
                attr=attr,
                value=value,
            )
        else:
            obj.value = value

    @classmethod
    def deleteValues(cls, **args):
        cls.KeywordQuery(**args).Delete()

    # The set of expanded IDs for a given chart is handled as a list of
    # attribute names, where an existing attribute means "expanded".

    @classmethod
    def getSetting(cls, persno, chart_oid, setting_name=""):
        entries = cls.KeywordQuery(
            persno=persno, chart_oid=chart_oid, attr_type=setting_name
        )
        return [
            x.attr
            for x in sorted(entries, key=lambda x: int(x.value) if x.value else 0)
        ]

    @classmethod
    def setSetting(cls, persno, chart_oid, id_list, setting_name=""):
        with transactions.Transaction():
            cls.deleteValues(persno=persno, chart_oid=chart_oid, attr_type=setting_name)
            for idx, expanded_id in enumerate(id_list):
                cls.Create(
                    persno=persno,
                    chart_oid=chart_oid,
                    attr_type=setting_name,
                    attr=expanded_id,
                    value=str(idx),
                )
