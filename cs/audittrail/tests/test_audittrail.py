# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import random

from cdb import constants
from cdbwrapc import Operation
from cdb.platform.mom import SimpleArguments, SimpleArgumentList
from cdb.objects.operations import operation
from cdb.validationkit.op import operation as interactive_operation
from cdb.testcase import RollbackTestCase

from cdb.objects import org
from cs.audittrail import WithAuditTrail, AuditTrailConfig, AuditTrailConfigField,\
                          AuditTrail, AuditTrailView, AuditTrailObjects, AuditTrailDetail, shortenText


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

    def test_create_org_non_interactive(self):
        user_input = {"name": u"TEST ORG"}
        contact = self.tOrganization.KeywordQuery(name=u"CONTACT Software")[0]
        op = Operation("CDB_Copy",
                       contact.ToObjectHandle(),
                       [])
        op.runAsTest([],
                     SimpleArguments(**user_input),
                     False)
        result = op.getObjectResult()
        org_object_id = result.cdb_object_id
        audittrailobjects = AuditTrailObjects.KeywordQuery(object_id=org_object_id)
        self.assertTrue(audittrailobjects)
        audittrail = AuditTrail.KeywordQuery(
            audittrail_object_id=audittrailobjects[-1].audittrail_id,
            type=u"create")

        self.assertTrue(audittrail)

    def test_create_org(self):
        user_input = {"name": u"TEST ORG"}
        preset = {}
        contact = self.tOrganization.KeywordQuery(name=u"CONTACT Software")[0]
        result = interactive_operation("CDB_Copy", contact, user_input, preset)
        org_object_id = result.cdb_object_id
        audittrailobjects = AuditTrailObjects.KeywordQuery(object_id=org_object_id)
        self.assertTrue(audittrailobjects)
        audittrail = AuditTrail.KeywordQuery(audittrail_object_id=audittrailobjects[-1].audittrail_id,
                                             type=u"create")
        self.assertTrue(audittrail)

    def test_modify_org(self):
        user_input = {"name": u"TEST ÖRG"}
        preset = {}
        contact = self.tOrganization.KeywordQuery(name=u"CONTACT Software")[0]
        interactive_operation("CDB_Modify", contact, user_input, preset)
        audittrailobjects = AuditTrailObjects.KeywordQuery(object_id=contact.cdb_object_id)
        self.assertTrue(audittrailobjects)
        audittrail = AuditTrail.KeywordQuery(audittrail_object_id=audittrailobjects[-1].audittrail_id,
                                             type=u"modify")
        self.assertTrue(audittrail)
        audittrailDetail = AuditTrailDetail.KeywordQuery(audittrail_object_id=audittrail.audittrail_object_id)[0]
        self.assertEqual(audittrailDetail.old_value, u"CONTACT Software")
        self.assertEqual(audittrailDetail.new_value, u"TEST ÖRG")

    def test_delete_org(self):
        user_input = {"name": u"TEST ORG"}
        preset = {}
        contact = self.tOrganization.KeywordQuery(name=u"CONTACT Software")[0]
        result = interactive_operation("CDB_Copy", contact, user_input, preset)
        org_object_id = result.cdb_object_id
        user_input = {}
        interactive_operation("CDB_Delete", result, user_input, preset)
        audittrailobjects = AuditTrailObjects.KeywordQuery(object_id=org_object_id)
        self.assertTrue(audittrailobjects)
        audittrail = AuditTrail.KeywordQuery(audittrail_object_id=audittrailobjects[-1].audittrail_id,
                                             type=u"delete")
        self.assertFalse(audittrail)

    def test_classification_event(self):
        from cdb import sig
        u_d = {
            'assigned_classes': ['RQM_RATING'],
            'values_checksum': 'invalid',
            'deleted_properties': [],
            'deleted_classes': [],
            'new_classes': [],
            'properties': {
                'RQM_RATING_RQM_RATING': [{
                    'value_path': 'RQM_RATING_RQM_RATING',
                    'property_type': 'block',
                    'id': 'RQM_RATING_RQM_RATING',
                    'value': {
                        'description': 'not relevant',
                        'child_props': {
                            'RQM_EVALUATOR': [{
                                'value_path': 'RQM_RATING_RQM_RATING/RQM_EVALUATOR',
                                'property_type': 'objectref',
                                'addtl_value': {
                                    'ui_link': 'cdbcmsg://byname/classname/angestellter/CDB_ShowObject/interactive?angestellter.personalnummer:caddok',
                                    'ui_text': ' Administrator  (caddok)'
                                },
                                'id': 'ad291e7d-af01-11ea-b195-54e1ad05fbed',
                                'value': '99504583-76e1-11de-a2d5-986f0c508d59',
                            }],
                            'RQM_COMMENT_EXTERN': [{
                                'value_path': 'RQM_RATING_RQM_RATING/RQM_COMMENT_EXTERN',
                                'property_type': 'text',
                                'id': 'ad291e7f-af01-11ea-b195-54e1ad05fbed',
                                'value': 'yz'
                            }],
                            'RQM_RATING_VALUE': [{
                                'value_path': 'RQM_RATING_RQM_RATING/RQM_RATING_VALUE',
                                'property_type': 'multilang',
                                'addtl_value': {
                                    'description': ''
                                },
                                'id': 'RQM_RATING_RQM_RATING/RQM_RATING_VALUE',
                                'value': {
                                    'de': {
                                        'text_value': 'nicht relevant',
                                        'id': 'ad291e81-af01-11ea-b195-54e1ad05fbed',
                                        'iso_language_code': 'de'
                                    },
                                    'en': {
                                        'text_value': 'not relevant',
                                        'id': 'ad291e83-af01-11ea-b195-54e1ad05fbed',
                                        'iso_language_code': 'en'
                                    }
                                }
                            }],
                            'RQM_COMMENT_INTERN': [{
                                'old_value': 'wx',
                                'value': 'N_IN',
                                'value_path': 'RQM_RATING_RQM_RATING/RQM_COMMENT_INTERN',
                                'property_type': 'text',
                                'addtl_value': None,
                                'id': 'ad291e85-af01-11ea-b195-54e1ad05fbed',
                            }]
                        }
                    }
                }]
            }
        }

        contact = self.tOrganization.KeywordQuery(name=u"CONTACT Software")[0]
        contact.initAuditTrail()
        sig.emit(self.tOrganization, "classification_update", "post")(contact, u_d)

        audittrailobjects = AuditTrailObjects.KeywordQuery(object_id=contact.cdb_object_id)
        self.assertTrue(audittrailobjects)
        audittrail = AuditTrail.KeywordQuery(
            audittrail_object_id=audittrailobjects[-1].audittrail_id,
            type=u"modify_classification")
        self.assertTrue(audittrail)
        audittrailDetail = \
        AuditTrailDetail.KeywordQuery(audittrail_object_id=audittrail.audittrail_object_id)[0]
        self.assertEqual(audittrailDetail.old_value, u'wx ')
        self.assertEqual(audittrailDetail.new_value, u'N_IN ')

    def test_shortenText(self):
        ot = u"aüöbcüdöüefaäghüöißjöklmnopqrüäsööltuüävwöäxüööäüüäöääüyzöüäö"

        nt = shortenText(ot, 3)
        self.assertEqual(u"...", nt)
        nt = shortenText(ot, 20)
        self.assertEqual(u'aüöbcüdöüefa...', nt)
        nt = shortenText(ot, 100)
        self.assertEqual(u"aüöbcüdöüefaäghüöißjöklmnopqrüäsööltuüävwöäxüööäüüäöääüyzöüäö", nt)
        nt = shortenText(u"abc", 3)
        self.assertEqual(u"abc", nt)
        nt = shortenText(u"abä", 3)
        self.assertEqual(u"...", nt)
        nt = shortenText(u"abä", 4)
        self.assertEqual(u"abä", nt)
        nt = shortenText(u"ääää", 4)
        self.assertEqual(u"...", nt)

    def test_shortentext_pure_unicode(self):
        for i in range(3, 100):
            text = u"ä" * i
            for maxlength in range(3, 2 * i + 1):
                short = shortenText(text, maxlength)
                length = len(short)
                if not length <= maxlength:
                    print("error with text length: %s allowed: %s < %s (short length), text: %s, short text: %s" % (
                        i, maxlength, length, text, short))
                    self.assertLess(length, maxlength)
                self.assertTrue(text.startswith(short[:-3]))

    def test_shortentext_mixed_mode(self):
        for i in range(3, 100):
            text = ""
            random_chars = [u"ä", "a"]
            for c in range(0, i):
                text += random_chars[random.randint(0, 1)]
            for maxlength in range(3, 2 * i + 1):
                short = shortenText(text, maxlength)
                length = len(short)
                if not length <= maxlength:
                    print("error with text length: %s allowed: %s < %s (short length), text: %s, short text: %s" % (
                        i, maxlength, length, text, short))
                    self.assertLess(length, maxlength)
                self.assertTrue(text.startswith(short[:-3]))

    def test_shortentext_pure_ascii(self):
        for i in range(3, 100):
            text = u"a" * i
            for maxlength in range(3, i + 1):
                short = shortenText(text, maxlength)
                length = len(short)
                if not length <= maxlength:
                    print("error with text length: %s allowed: %s < %s (short length), text: %s, short text: %s" % (
                        i, maxlength, length, text, short))
                    self.assertLess(length, maxlength)
