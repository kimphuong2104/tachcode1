#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

from cdb import ddl
from cdb import sqlapi


def _deleteData(table):
    if ddl.Table(table).exists():
        sqlapi.SQLdelete('FROM %s' % table)


class DeleteScoutMasterDataConfig(object):
    def run(self):
        _deleteData('csweb_attr_attribute')
        _deleteData('csweb_attr_class')
        _deleteData('csweb_attr_block')
        _deleteData('csweb_attr_group')


class DeleteHistoryItems(object):
    def run(self):
        _deleteData('cdbweb_history_item')


pre = [DeleteScoutMasterDataConfig, DeleteHistoryItems]
