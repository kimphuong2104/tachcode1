# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
This updates the _empyty_values field in solr.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import shutil
from cdb.comparch import protocol


class UpdateSolrEmptyValuesField(object):

    def run(self):
        from cdb import CADDOK
        import cs.classification
        cs_classification_path = os.path.dirname(cs.classification.__file__)

        source_path = os.path.abspath(
            os.path.join(
                cs_classification_path,
                '..',
                '..',
                'solr-core-template',
                'classification',
                'conf',
                'managed-schema'
            )
        )
        if not os.path.isfile(source_path):
            raise RuntimeError("Updating solr configuration failed! Solr template file is missing: %s" % source_path)

        error_text = '''\
The solr schema must be extended by a new field named "_empty_values". The attempt to replace the solr configuration \
file (managed-schema) of your instance failed. Reason:

%s

The solr schema file must be replaced manually. Please replace the managed-schema file of the classification solr core \
by %s and restart solr.

Hint:
Typically the path to the managed-schema file looks like this: storage/index/search/classification/conf/managed-schema

Warning:
Do not accidentally modify the configuration of the enterprise search solr core!
'''

        destination_path = os.path.abspath(
            os.path.join(
                CADDOK.BASE,
                'storage',
                'index',
                'search',
                'classification',
                'conf',
                'managed-schema'
            )
        )

        if not os.path.isfile(destination_path):
            err_reason = 'Destination file not found: %s' % destination_path
            detail_txt = error_text % (err_reason, source_path)
            protocol.logError('Updating solr configuration failed! (see protocol entry for details)', detail_txt)
            return

        try:
            shutil.copy2(source_path, destination_path)
        except IOError as exc:
            err_reason = 'Copy failed: %s -> %s\nException: %s' % (source_path, destination_path, exc)
            detail_txt = error_text % (err_reason, source_path)
            protocol.logError('Updating solr configuration failed! (see protocol entry for details)', detail_txt)


pre = []
post = [UpdateSolrEmptyValuesField]
