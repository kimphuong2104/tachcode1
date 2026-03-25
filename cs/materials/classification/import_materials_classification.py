#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module cs.materials.classification.import_materials_classification
"""

from cdb.comparch import protocol

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def run():
    import os

    from cs.classification.scripts.import_tool import run

    data_path = os.path.join(
        os.path.abspath(os.path.dirname(os.path.join(__file__))),
        "data",
    )
    run(data_path)
    protocol.logMessage(
        "Remember to update the classification search index after starting the server: "
        + "powerscript.exe -m cs.classification.scripts.solr_resync --schema"
    )


if __name__ == "__main__":
    run()
