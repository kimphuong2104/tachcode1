# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import os

from cdb import rte
from cdb.plattools import killableprocess
from cdb.uberserver.management import Management

from cs.documents import Document


__all__ = ["install_testdata"]


FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCEPTTEST_DIR = os.path.join(FILE_DIR, "..", "..", "..", "..", "tests", "accepttests")


def install_testdata():
    blobstore = "cdb.uberserver.services.blobstore.BlobStore"
    svc = Management()
    if Document.ByKeys(z_nummer="000061-1", z_index="") is None:
        stop_blobstore = False
        if not svc._check_if_its_up(blobstore):
            svc.start_service(blobstore)
            stop_blobstore = True
        powerscript = rte.runtime_tool("powerscript")

        env = dict(rte.environ)
        args = [
            powerscript,
            os.path.join(ACCEPTTEST_DIR, "data", "testdata_acceptance.py"),
            "--autoinstall"
        ]
        process = killableprocess.Popen(args, env=env)
        process.wait()

        if stop_blobstore:
            svc.stop_service(blobstore)
