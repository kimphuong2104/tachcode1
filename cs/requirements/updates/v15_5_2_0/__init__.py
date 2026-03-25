# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Installs the needed classification classes and properties
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class InstallRQMClassification(object):
    def run(self):
        import os
        from cs.classification.scripts.import_tool import run
        folder_path = os.path.abspath(os.path.dirname(os.path.join(__file__)))
        data_path = os.path.abspath(os.path.join(folder_path, '..', '..', 'install', 'rqm_classification'))
        run(data_path)

pre = []
post = [InstallRQMClassification]