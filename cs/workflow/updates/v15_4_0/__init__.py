#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import os
from cdb import CADDOK
from cdb.comparch import protocol


class EnableCSRFProtection(object):
    def run(self):
        conf = os.path.join(CADDOK.BASE, "etc", "csrf_opt_out.conf")

        with open(conf, "a") as opt_out:
            opt_out.write("/powerscript/cs.workflow.designer\n")


pre = []
post = [EnableCSRFProtection]
