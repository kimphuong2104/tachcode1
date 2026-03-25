# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
from cdb import constants
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase

from cdb.objects import org
from cs.audittrail import WithAuditTrail, AuditTrailConfig, AuditTrailConfigField,\
                          AuditTrailApi, AuditTrailObjects, AuditTrailView


class TestAuditTrail(RollbackTestCase):
    class tOrganization(org.Organization, WithAuditTrail):
        pass

    def setUp(self):
        """
        Set up the test case
        """
        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestAuditTrail, self).setUp()
        audittrail_config = operation(constants.kOperationNew,
                                           AuditTrailConfig,
                                           name=u'ORG TEST CONFIG',
                                           classname=u'cdb_organization')
        operation(constants.kOperationNew,
                  AuditTrailConfigField,
                  config_name=audittrail_config.name,
                  classname=audittrail_config.classname,
                  field_name=u'name')
        operation(constants.kOperationNew,
                  AuditTrailConfigField,
                  config_name=audittrail_config.name,
                  classname=audittrail_config.classname,
                  field_name=u'org_type')
        operation(constants.kOperationNew,
                  AuditTrailConfigField,
                  config_name=audittrail_config.name,
                  classname=audittrail_config.classname,
                  field_name=u'org_id')

    def test_create_audittrail_with_details_via_api(self):
        new_org = org.Organization.Create(
            name="TEST Corp",
            org_type="Lieferant",
            org_id=815
        )
        new_org2 = org.Organization.Create(
            name="TEST Corp2",
            org_type="Lieferant",
            org_id=816
        )

        objs = [{"cdb_object_id": new_org.cdb_object_id,
                 "idx": "-",
                 "description": "TEST Corp (Lieferant)",
                 "classname": "cdb_organization",
                 "attach_to": [new_org.cdb_object_id],
                 "changes": [{
                     "attribute_name": "name",
                     "old_value": "",
                     "new_value": "TEST Corp",
                     "longtext": 0}, {
                     "attribute_name": "org_type",
                     "old_value": "",
                     "new_value": "Lieferant",
                     "longtext": 0}, {
                     "attribute_name": "org_id",
                     "old_value": "",
                     "new_value": "815",
                     "longtext": 0}]}, {
                 "cdb_object_id": new_org2.cdb_object_id,
                 "idx": "-",
                 "description": "TEST Corp2 (Lieferant)",
                 "classname": "cdb_organization",
                 "attach_to": [new_org2.cdb_object_id],
                 "changes": [{
                     "attribute_name": "name",
                     "old_value": "",
                     "new_value": "TEST Corp2",
                     "longtext": 0}, {
                     "attribute_name": "org_type",
                     "old_value": "",
                     "new_value": "Lieferant",
                     "longtext": 0}, {
                     "attribute_name": "org_id",
                     "old_value": "",
                     "new_value": "816",
                     "longtext": 0}]}]

        AuditTrailApi.createAuditTrailsWithDetails(
            category="create",
            objs=objs
        )

        self.assertEqual(len(AuditTrailObjects.KeywordQuery(object_id=[new_org.cdb_object_id,
                                                                       new_org2.cdb_object_id])), 2)
        self.assertEqual(len(AuditTrailView.KeywordQuery(object_id=[new_org.cdb_object_id,
                                                                    new_org2.cdb_object_id])), 8)
