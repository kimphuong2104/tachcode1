# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import shutil


class InstallClassificationSolrCore(object):

    def copy_solr_config(self, solr_template_path):
        from cdb import CADDOK
        from cdb.comparch import protocol
        from cdb.platform.uberserver import Services  # @UnresolvedImport

        if not os.path.isdir(solr_template_path):
            protocol.logError(
                "Manual Solr configuration required! Solr configuration template not found at {}".format(
                    solr_template_path
                )
            )
            return
        search_index_path = os.path.abspath(os.path.join(CADDOK.BASE, 'storage', 'index', 'search'))
        indexServices = Services.KeywordQuery(svcname='cdb.uberserver.services.index.IndexService')
        if len(indexServices) == 0:
            protocol.logError(
                "Manual Solr configuration required! No index service found!"
            )
            return
        if len(indexServices) > 1:
            protocol.logError(
                "Manual Solr configuration required! Multiple index services found!"
            )
            return
        indexService = indexServices[0]
        if indexService and indexService.get_option('--workdir'):
            search_index_path = indexService.get_option('--workdir')

        if not os.path.isdir(search_index_path):
            protocol.logError(
                "Manual Solr configuration required! No search index path found!"
            )
            return

        classification_config_path = os.path.join(search_index_path, 'classification')
        if os.path.exists(classification_config_path):
            protocol.logError(
                "Manual Solr configuration required! Existing Solr configuration found at {}".format(
                    classification_config_path
                )
            )
            return

        try:
            # for shutil.copytree the destination directory must not exist
            for subdir in os.listdir(solr_template_path):
                src = os.path.join(solr_template_path, subdir)
                dst = os.path.join(search_index_path, subdir)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        except BaseException:
            protocol.logError(
                "Manual Solr configuration required! Could not copy Solr configuration to {}".format(
                    search_index_path
                )
            )

    def run(self):
        import cs.classification
        cs_classification_path = os.path.dirname(cs.classification.__file__)
        solr_template_path = os.path.abspath(
            os.path.join(cs_classification_path, 'solr-core-template'))
        self.copy_solr_config(solr_template_path)


class UpdateDecompositions(object):

    def run(self):
        from cdb.platform.gui import Decomposition
        d = Decomposition.ByKeys("CDB_LIC_FEATURE_ASSIGN")
        d.generate_decomposition()


pre = []
post = [InstallClassificationSolrCore, UpdateDecompositions]

if __name__ == "__main__":
    InstallClassificationSolrCore().run()
