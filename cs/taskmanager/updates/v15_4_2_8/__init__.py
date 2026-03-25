#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.comparch import protocol


class UpdateUserViewLabels(object):
    def run(self):
        # this change has been rolled back in 15.6.0, so skip migration
        protocol.logWarning("Update not relevant.")


pre = []
post = [UpdateUserViewLabels]


if __name__ == "__main__":
    UpdateUserViewLabels().run()
