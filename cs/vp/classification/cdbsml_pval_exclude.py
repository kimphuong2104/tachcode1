#!/usr/bin/env powerscript
# -*- coding: iso-8859-1 -*-
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import misc
from cdb import sqlapi
from cdb import ue
from cdb import util

from cdb.transactions import Transaction


def doit(ctx):
    misc.cdblogv(misc.kLogMsg, 1, "%s" % ctx)
    misc.cdblogv(misc.kLogMsg, 1, "%s Objekte." % len(ctx.objects))
    with Transaction():
        records = sqlapi.RecordSet2("cdbsml_pval_subset",
                                    "pset_id='%s' AND prop_mk='%s'" % (
                                        ctx.parent.pset_id,
                                        ctx.objects[0].prop_mk))

        Entries = dict([(record.pval_value, record) for record in records])
        value = {'cdbsml_pval_exclude': '1',
                 'cdbsml_pval_include': '0'}[ctx.action]
        for obj in ctx.objects:
            entry = Entries.get(obj.pval_value, None)
            if entry:
                entry.update(pval_exclude=value)
            else:
                ins = util.DBInserter("cdbsml_pval_subset")
                ins.add("pset_id", ctx.parent.pset_id)
                ins.add("prop_mk", obj.prop_mk)
                ins.add("pval_value", obj.pval_value)
                ins.add("pval_exclude", value)
                ins.insert()
        ctx.refresh_tables(['cdbsml_pval_subset', 'cdbsml_pval_subset_v'])

if __name__ == '__main__':
    ue.run(doit, "cdbscript")
