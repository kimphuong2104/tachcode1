# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb.platform import mom
from cdb.validationkit.op import make_argument_list
from cdb.validationkit.op import operation as interactive_operation
from cdbwrapc import Operation, createOperationFromCMSGUrl
import logging
import sys

from cs.requirements import RQMSpecObject
from cs.requirements import RQMSpecification

from .utils import RequirementsTestCase


LOG = logging.getLogger(__name__)


class TestChangeFulfillment(RequirementsTestCase):
    def setUp(self):
        super(TestChangeFulfillment, self).setUp()
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]

    def test_change_fulfillment_value_raises_exception(self):
        """Check if cdbrqm_easy_fulfilled & cdbrqm_easy_not_fulfilled raises an exception when requirements are not met.
        Test to check if the cdbrqm_easy_fulfilled & cdbrqm_easy_not_fulfilled operation are throwing an exception due
        to the requirement object not being a leaf and not being editable although being in a state in which this should
        be possible.
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement = spec.TopRequirements[0]
        self.assertTrue(requirement.Specification.status == 0)
        self.assertFalse(requirement.isLeafReq())
        with self.assertRaises(RuntimeError):
            interactive_operation("cdbrqm_easy_fulfilled", requirement)
        with self.assertRaises(RuntimeError):
            interactive_operation("cdbrqm_easy_not_fulfilled", requirement)

    def test_change_fulfillment_value_possible(self):
        """Check if cdbrqm_easy_fulfilled changes the act_value on multiple requirements
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        spec.ChangeState(100, check_access=0)
        spec.ChangeState(200, check_access=0)
        requirement1 = RQMSpecObject.KeywordQuery(name_de=u'anf1-1', specification_object_id=spec.cdb_object_id)[0]
        self.assertTrue(requirement1.Specification.status == 200)
        self.assertTrue(requirement1.isLeafReq())
        requirement2 = RQMSpecObject.KeywordQuery(name_de=u'anf2', specification_object_id=spec.cdb_object_id)[0]
        self.assertTrue(requirement2.Specification.status == 200)
        self.assertTrue(requirement2.isLeafReq())

        requirements = [requirement1.ToObjectHandle(), requirement2.ToObjectHandle()]
        user_input = {}
        preset = {}
        # TODO E042390
        dlg_args = make_argument_list(None, user_input)
        op_args = make_argument_list(None, preset)
        _operation = Operation("cdbrqm_easy_fulfilled", requirements, mom.SimpleArgumentList())
        _operation.runAsTest(op_args, dlg_args, True)
        requirement1.Reload()
        requirement2.Reload()
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
        self.assertTrue(int(requirement1.act_value) == 100)
        self.assertTrue(int(requirement2.act_value) == 100)

    def test_reset_fulfillment(self):
        """ Check if the fulfillment reset operation really resets the fulfillment of the object it operates on and their whole children including target values. """
        # --- start generating pre condition ---
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement0 = RQMSpecObject.KeywordQuery(name_de=u'anf1', specification_object_id=spec.cdb_object_id)[0]
        requirement1 = RQMSpecObject.KeywordQuery(name_de=u'anf1-1', specification_object_id=spec.cdb_object_id)[0]
        requirement1.set_act_value(100)
        requirement2 = RQMSpecObject.KeywordQuery(name_de=u'anf1-2', specification_object_id=spec.cdb_object_id)[0]
        tv = requirement2.TargetValues[0]
        tv.set_act_value(100)
        spec.ChangeState(100, check_access=0)
        spec.ChangeState(200, check_access=0)
        spec.Reload()
        requirement0.Reload()
        requirement1.Reload()
        requirement2.Reload()
        tv.Reload()
        self.assertEqual(requirement0.act_value, 100.0)  # one subtree is set to fulfilled
        self.assertAlmostEqual(spec.act_value, 100.0 / len(spec.TopRequirements))

        # --- pre condition end ---

        interactive_operation(u"cdbrqm_reset_fulfillment", requirement0)

        # --- refresh to check post condition ---
        spec.Reload()
        requirement0.Reload()
        requirement1.Reload()
        requirement2.Reload()
        tv.Reload()

        # --- check post conditions ---
        self.assertEqual(spec.act_value, 0.0)
        self.assertEqual(requirement0.act_value, None)
        self.assertEqual(requirement1.act_value, None)
        self.assertEqual(requirement2.act_value, None)
        self.assertEqual(tv.act_value, None)
