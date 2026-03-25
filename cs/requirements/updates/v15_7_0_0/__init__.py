# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


"""
Migrates data to ensure baselines can be created also for existing
objects.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import logging

LOG = logging.getLogger(__name__)


class CleanupUnsupportedMultiLanguageData(object):
    def run(self):
        from cdb.comparch.updutils import TranslationCleaner  # needs CE 15.5 SL16+
        tc_rqm_base = TranslationCleaner('cs.requirements', ['zh', 'tr'])
        tc_rqm_base.run()
        tc_rqm_reqif = TranslationCleaner('cs.requirements_reqif', ['zh', 'tr'])
        tc_rqm_reqif.run()


class FillBaselineFields(object):
    def run(self):
        LOG = logging.getLogger(__name__)
        try:
            from cs.baselining.support import BaselineTools
            from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
            for relation in [
                RQMSpecification.__maps_to__,
                RQMSpecObject.__maps_to__,
                TargetValue.__maps_to__
            ]:
                LOG.info('Initialize baseline data within %s', relation)
                BaselineTools.fix_baseline_object_ids(
                    relation=relation
                )
        except ImportError as e:
            LOG.error(
                "Data migration error, baselining won't work for existing objects due to: %s",
                e
            )
            LOG.exception(e)


pre = []
post = [FillBaselineFields, CleanupUnsupportedMultiLanguageData]


def main():
    FillBaselineFields().run()
    CleanupUnsupportedMultiLanguageData().run()


# Guard importing as main module
if __name__ == "__main__":
    main()
