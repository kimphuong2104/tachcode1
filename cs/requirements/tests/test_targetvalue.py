# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals, print_function

import logging
import sys

from cdb.platform import mom
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cdb.validationkit.op import make_argument_list
from cdb.validationkit.op import operation as interactive_operation
from cdbwrapc import Operation, createOperationFromCMSGUrl

from .utils import RequirementsTestCase


LOG = logging.getLogger(__name__)


class TestTargetValue(RequirementsTestCase):
    def __init__(self, *args, **kwargs):
        kwargs.update({'need_uberserver': False})
        super(TestTargetValue, self).__init__(*args, **kwargs)

    def setUp(self, *args, **kwargs):
        super(TestTargetValue, self).setUp(*args, **kwargs)
        self.spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        self.req = RQMSpecObject.KeywordQuery(name_de=u'anf1-1', specification_object_id=self.spec.cdb_object_id)[0]
        user_input = {"name_de": u"ziel3",
                      "value_type": 0,
                      "value_unit": "g",
                      "target_value_mask": "100"}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "requirement_object_id": self.req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>ziel3</xhtml:div>","en":"<xhtml:div></xhtml:div>"}'}
        interactive_operation("CDB_Create", TargetValue, user_input, preset)

    def test_target_value_description_to_shortdescription_logic(self):
        """ (R000002808) Check if creating a new acceptance criteria with a description in one language leads to a short description in the same language"""
        self.assertEqual(self.spec.status, 0)
        description = 'ziel3'
        user_input = {
            "value_type": 0,
            "value_unit": "g",
            "target_value_mask": "100"}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "requirement_object_id": self.req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        t = interactive_operation("CDB_Create", TargetValue, user_input, preset)
        self.assertEqual(t.GetText('cdbrqm_target_value_desc_de'), "<xhtml:div>%s</xhtml:div>" % description)
        self.assertEqual(t.name_de, description)

    def test_evaluate_raises_exception(self):
        """ (R00002886) Check if cdbrqm_evaluate raises an exception in case the type differs between target values.
        """
        self.spec.ChangeState(100, check_access=0)
        self.spec.ChangeState(200, check_access=0)

        targetvalue1 = TargetValue.KeywordQuery(name_de=u'ziel1', specification_object_id=self.spec.cdb_object_id)[0]
        self.assertTrue(targetvalue1.Requirement.Specification.status == 200)
        self.assertTrue(targetvalue1.Requirement.isLeafReq())
        targetvalue2 = TargetValue.KeywordQuery(name_de=u'ziel3', specification_object_id=self.spec.cdb_object_id)[0]
        self.assertTrue(targetvalue2.Requirement.Specification.status == 200)
        self.assertTrue(targetvalue2.Requirement.isLeafReq())

        targetvalues = [targetvalue1.ToObjectHandle(), targetvalue2.ToObjectHandle()]
        user_input = {}
        preset = {}
        # TODO E042390
        dlg_args = make_argument_list(None, user_input)
        op_args = make_argument_list(None, preset)
        with self.assertRaises(RuntimeError):
            _operation = Operation("cdbrqm_evaluate", targetvalues, mom.SimpleArgumentList())
            _operation.runAsTest(op_args, dlg_args, True)
            targetvalue1.Reload()
            targetvalue2.Reload()
            while True:
                # Operations may return an URL which defines a follow-up operation
                # Try to execute such operations (or operation-chains)
                urlresult = _operation.getUrlResult()
                if urlresult is not None:
                    url = urlresult[0]
                    try:
                        followOp = createOperationFromCMSGUrl(url)
                    except ValueError as exc:
                        followOp = None
                        if url.find("byname") != -1:
                            sys.stderr.write("ERROR: Could not create an operation from URL '%s', details: '%s'\n" % (url, exc))
                        else:
                            sys.stdout.write("WARNING: Cannot interpret URL '%s' skipping the follow-up operation, details: '%s'\n" % (url, exc))
                    if followOp is not None:
                        _operation = followOp
                        _operation.runAsTest(make_argument_list(None, {}),
                                             make_argument_list(None, {}),
                                             True)
                        continue
                break

    def test_evaluate_possible(self):
        """ (R00002886) Check if cdbrqm_evaluate changes the act_value on multiple target values.
        """
        self.spec.ChangeState(100, check_access=0)
        self.spec.ChangeState(200, check_access=0)

        targetvalue1 = TargetValue.KeywordQuery(name_de=u'ziel1', specification_object_id=self.spec.cdb_object_id)[0]
        self.assertTrue(targetvalue1.Requirement.Specification.status == 200)
        self.assertTrue(targetvalue1.Requirement.isLeafReq())
        targetvalue2 = TargetValue.KeywordQuery(name_de=u'ziel2', specification_object_id=self.spec.cdb_object_id)[0]
        self.assertTrue(targetvalue2.Requirement.Specification.status == 200)
        self.assertTrue(targetvalue2.Requirement.isLeafReq())

        targetvalues = [targetvalue1.ToObjectHandle(), targetvalue2.ToObjectHandle()]
        user_input = {"act_value_mask": "100"}
        preset = {}
        # TODO E042390
        dlg_args = make_argument_list(None, user_input)
        op_args = make_argument_list(None, preset)
        _operation = Operation("cdbrqm_evaluate", targetvalues, mom.SimpleArgumentList())
        _operation.runAsTest(op_args, dlg_args, True)
        targetvalue1.Reload()
        targetvalue2.Reload()
        while True:
            # Operations may return an URL which defines a follow-up operation
            # Try to execute such operations (or operation-chains)
            urlresult = _operation.getUrlResult()
            if urlresult is not None:
                url = urlresult[0]
                try:
                    followOp = createOperationFromCMSGUrl(url)
                except ValueError as exc:
                    followOp = None
                    if url.find("byname") != -1:
                        sys.stderr.write("ERROR: Could not create an operation from URL '%s', details: '%s'\n" % (url, exc))
                    else:
                        sys.stdout.write("WARNING: Cannot interpret URL '%s' skipping the follow-up operation, details: '%s'\n" % (url, exc))
                if followOp is not None:
                    _operation = followOp
                    _operation.runAsTest(make_argument_list(None, {}),
                                         make_argument_list(None, {}),
                                         True)
                    continue
            break
        self.assertTrue(int(targetvalue1.act_value) == 100)
        self.assertTrue(int(targetvalue2.act_value) == 100)

    def test_creation_fails1(self):
        """ (R000002808) Check if creation below a requirement groups returns an error"""
        req = RQMSpecObject.KeywordQuery(name_de=u'anf1',
                                         specification_object_id=self.spec.cdb_object_id)[0]
        self.assertEqual(self.spec.status, 0)
        description = 'ziel3'
        user_input = {
            "value_type": 0,
            "value_unit": "g",
            "target_value_mask": "100"}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "requirement_object_id": req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        with self.assertRaises(RuntimeError):
            interactive_operation("CDB_Create", TargetValue, user_input, preset)

    def test_creation_fails2(self):
        """ (R000002808) Check if creation on a specification where the status is not 0 fails"""
        self.spec.ChangeState(100, check_access=0)
        self.spec.ChangeState(200, check_access=0)
        self.assertEqual(self.spec.status, 200)
        description = 'ziel3'
        user_input = {
            "value_type": 0,
            "value_unit": "g",
            "target_value_mask": "100"}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "requirement_object_id": self.req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        with self.assertRaises(RuntimeError):
            interactive_operation("CDB_Create", TargetValue, user_input, preset)

    def test_creation_with_custom_target_value_mask_and_unit(self):
        """ (E048168) Check if creation with a different target_value_mask and unit leads to an acceptance criterion with that target_value and unit"""
        self.skipTest('currently testing with values for mask only fields are not possible')
        self.assertEqual(self.spec.status, 0)
        description = 'ziel3'
        user_input = {
            "value_type": 0,
            "value_unit": "min",
            "target_value_mask": "<=5"}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "requirement_object_id": self.req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        t = interactive_operation("CDB_Create", TargetValue, user_input, preset)
        self.assertEqual(t.target_value, user_input.get('target_value_mask'))
        self.assertEqual(t.mapped_unit, user_input.get('target_value_mask'))
