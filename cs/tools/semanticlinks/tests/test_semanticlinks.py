# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
from __future__ import print_function

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase
from cdb.wsgi.worker.clientrequest import application
from webtest import TestApp as Client
from cdb.objects import org
from cs.tools.semanticlinks import SemanticLinkType, SemanticLink, \
    LinkGraphConfig


class TestSemanticLinks(RollbackTestCase):

    def setUp(self):
        """
        Set up the test case
        """
        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        self.client = Client(application)
        super(TestSemanticLinks, self).setUp()
        self.used_link_type = operation(constants.kOperationNew,
                                        SemanticLinkType,
                                        name=u'used_link_type',
                                        object_object_classname=u'cdb_semantic_link_type',
                                        subject_object_classname=u'cdb_semantic_link_type',
                                        invalid=False)
        self.other_link_type = operation(constants.kOperationNew,
                                         SemanticLinkType,
                                         name=u'other_link_type',
                                         object_object_classname=u'cdb_semantic_link_type',
                                         subject_object_classname=u'cdb_semantic_link_type')
        self.sl1 = operation(constants.kOperationNew,
                             SemanticLink,
                             subject_object_id=self.used_link_type.cdb_object_id,
                             subject_object_classname=u'cdb_semantic_link_type',
                             object_object_id=self.other_link_type.cdb_object_id,
                             object_object_classname=u'cdb_semantic_link_type',
                             link_type_object_id=self.used_link_type.cdb_object_id)
        self.used_link_type.Reload()
        self.org_contact = org.Organization.ByKeys(name='CONTACT Software')
        self.link_graph_config = LinkGraphConfig.ByKeys(name='SemanticLinkGraph')
        assert self.used_link_type.isUsed()

    def test_used_linktype_modification_set_invalid(self):
        success = True
        try:
            operation(constants.kOperationModify, self.used_link_type, invalid=1)
        except RuntimeError as e:
            print(e)
            success = False
        self.used_link_type.Reload()
        assert self.used_link_type.invalid == 1, self.used_link_type.invalid
        try:
            operation(constants.kOperationModify, self.used_link_type, invalid=0)
        except RuntimeError as e:
            print(e)
            success = False
        assert success
        assert self.used_link_type.invalid == 0, self.used_link_type.invalid

    def test_used_linktype_modification_set_other_attributes(self):
        success = True
        try:
            operation(constants.kOperationModify, self.used_link_type, name=u'changed name')
            success = False
        except RuntimeError as e:
            print(e)
        assert success
        assert self.used_link_type.name == u"used_link_type", "'%s'!='%s' (used: %s)" % (self.used_link_type.name, u"used_link_type", self.used_link_type.isUsed())
