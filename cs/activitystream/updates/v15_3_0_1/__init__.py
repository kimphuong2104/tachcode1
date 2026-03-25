#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

from cdb import sqlapi

__docformat__ = "restructuredtext en"


class UpdateContextObjectID(object):
    """Update the context_object_id for postings, change null value to
    empty string.
    """

    def run(self):
        sqlapi.SQLupdate(
            "cdbblog_posting set context_object_id='' where context_object_id is null"
        )


pre = [UpdateContextObjectID]
post = []

# Guard importing as main module
if __name__ == "__main__":
    UpdateContextObjectID().run()
