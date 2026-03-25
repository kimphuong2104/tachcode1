# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


"""
Adjust to changes of cs.requirements 15.9.0
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import logging

LOG = logging.getLogger(__name__)

class ChangeRQMRatingClassificationApplicability(object):
    def run(self):
        LOG = logging.getLogger(__name__)
        try:
            from cs.classification.applicability import ClassificationApplicability
            rqm_rating_uc_class_id = "aed54013-58a1-11ea-89f3-a08cfdd70ffa"
            rqm_rating_applicability = ClassificationApplicability.ByKeys(
                **{"classification_class_id": rqm_rating_uc_class_id, "dd_classname": "cdbrqm_spec_object"}
            )
            if rqm_rating_applicability:
                rqm_rating_applicability.Update(write_access_obj="rqm_rating")
            else:
                from cs.classification.classes import ClassificationClass
                rqm_rating_uc_class = ClassificationClass.ByKeys(code="RQM_RATING")
                if not rqm_rating_uc_class:
                    LOG.error("RQM_RATING UC class is missing")
                elif rqm_rating_uc_class_id != rqm_rating_uc_class.cdb_object_id:
                    LOG.error("RQM_RATING UC class has different cdb_object_id")
                else:
                    LOG.error("RQM_RATING UC class applicability for 'cdbrqm_spec_object' is missing.")
        except ImportError as e:
            LOG.error(
                "Failed to change RQM_RATING applicability write access object permission to rqm_rating: %s",
                e
            )
            LOG.exception(e)


pre = []
post = [ChangeRQMRatingClassificationApplicability]


def main():
    ChangeRQMRatingClassificationApplicability().run()


# Guard importing as main module
if __name__ == "__main__":
    main()
