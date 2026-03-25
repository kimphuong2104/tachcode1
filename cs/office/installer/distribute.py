#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import os
import shutil
import sys
from dist_tools import ws_integration


def distribute_bin(cad_name):
    """
    Copy build release installer to package installer_bin dir
    """
    files = [ws_integration.installer.get_msi_name()
             ]
    dst_dir = os.path.join("cs", cad_name, "installer_bin")
    if os.path.isdir(dst_dir):
        shutil.rmtree(dst_dir)
    os.makedirs(dst_dir)
    for f in files:
        src = os.path.join("release", "installer", f)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst_dir, f))
        else:
            raise Exception("ERROR: not existing installer %s" % src)


if __name__ == "__main__":
    distribute_bin(sys.argv[1])
