#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class InitializeFinishOption(object):
    def run(self):
        sqlapi.SQLupdate("cdbwf_task SET finish_option=0 "
                         "WHERE finish_option IS NULL")


pre = []
post = [InitializeFinishOption]
