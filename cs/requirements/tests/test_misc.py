# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from .utils import RequirementsTestCase
import logging
from cs.requirements import RQMSpecObject, RQMSpecification, TargetValue
from cs.activitystream.objects import SystemPosting
from cs.documents import Document

LOG = logging.getLogger(__name__)


class TestMisc(RequirementsTestCase):
    def test_check_specification_activity_stream(self):
        """ Check if GetActivityStreamTopics returns the correct objects on a RQMSpecification"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        spec.is_template = 1
        spec.ChangeState(100, check_access=0)
        spec.ChangeState(200, check_access=0)
        posting = SystemPosting.Create()
        astopics = spec.GetActivityStreamTopics(posting)
        self.assertIn(spec, astopics)
        self.assertIn(spec.Product, astopics)
        self.assertIn(spec.Project, astopics)

    def test_check_spec_object_activity_stream(self):
        """ Check if GetActivityStreamTopics returns the correct objects on a RQMSpecObject"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement = \
            RQMSpecObject.KeywordQuery(specification_object_id=spec.cdb_object_id,
                                       name_de=u"anf1")[0]
        posting = SystemPosting.Create()
        astopics = requirement.GetActivityStreamTopics(posting)
        self.assertIn(requirement, astopics)
        self.assertIn(requirement.Specification, astopics)
        self.assertIn(requirement.Specification.Product, astopics)
        self.assertIn(requirement.Specification.Project, astopics)

    def test_check_target_value_activity_stream(self):
        """ Check if GetActivityStreamTopics returns the correct objects on a TargetValue"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement = \
            RQMSpecObject.KeywordQuery(specification_object_id=spec.cdb_object_id,
                                       name_de=u"anf1-2")[0]
        tv = TargetValue.KeywordQuery(specification_object_id=spec.cdb_object_id,
                                      requirement_object_id=requirement.cdb_object_id,
                                      name_de="ziel2")[0]
        posting = SystemPosting.Create()
        astopics = tv.GetActivityStreamTopics(posting)
        self.assertIn(tv, astopics)
        self.assertIn(tv.Requirement, astopics)
        self.assertIn(tv.Specification, astopics)
        self.assertIn(tv.Specification.Product, astopics)
        self.assertIn(tv.Specification.Project, astopics)

    def test_check_spec_object_documents_ref(self):
        """ Check if Documents returns the correct documents of an RQMSpecObject"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement = \
            RQMSpecObject.KeywordQuery(specification_object_id=spec.cdb_object_id,
                                       name_de=u"anf1")[0]
        document = Document.ByKeys(z_nummer="TEST001", z_index="")
        self.assertIn(document, requirement.Documents)

    def test_check_specification_documents_ref(self):
        """ Check if Documents returns the correct documents of an RQMSpecification"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        document = Document.ByKeys(z_nummer="TEST001", z_index="")
        self.assertIn(document, spec.Documents)

    def test_audittrail_entries(self):
        """ Check if getAuditTrailEntries returns the correct ids """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        object_ids = spec.getAuditTrailEntries()
        self.assertIn(spec.cdb_object_id, object_ids)
        for so in spec.Requirements:
            self.assertIn(so.cdb_object_id, object_ids)
        for tv in spec.TargetValues:
            self.assertIn(tv.cdb_object_id, object_ids)
