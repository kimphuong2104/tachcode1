#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import absolute_import
from __future__ import print_function

import multiprocessing
import json
import platform
from cdbwrapc import getVersionDescription
from datetime import datetime
import psutil

from cdb import sqlapi
from cdb.comparch.packages import Package


def create_server_statistics():
    return {
        "cdb_version": getVersionDescription(),
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "dbms": sqlapi.dbms_information(),
        "database_size": {
            "zeichnung": count_relation("zeichnung"),
            "cdb_file": count_relation("cdb_file"),
            "teile_stamm": count_relation("teile_stamm"),
        },
        "packages": get_packages_and_versions(),
        "hardware": {
            "computer": platform.node(),
            "processor": platform.processor(),
            "cpu_count": multiprocessing.cpu_count(),
            "ram": psutil.virtual_memory().total,
        },
    }


def count_relation(rel):
    t = sqlapi.SQLselect("COUNT(*) FROM %s" % sqlapi.quote(rel))
    return sqlapi.SQLinteger(t, 0, 0)


def get_packages_and_versions():
    ret = {}
    for pkg in Package.Query():
        ret[pkg.name] = pkg.version
    return ret


if __name__ == "__main__":
    print(json.dumps(create_server_statistics(), indent=4))
