#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi


class FixExtensionClass(object):
    """
    Set ``cdbwf_task.cdb_extension_class`` to empty string where NULL
    so My Tasks rules can be matched.
    """
    def run(self):
        sqlapi.SQLupdate("cdbwf_task SET cdb_extension_class = '' WHERE cdb_extension_class IS NULL")


pre = [FixExtensionClass]
post = []
