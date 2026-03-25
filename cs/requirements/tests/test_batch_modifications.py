# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import ElementsError
from cdb.platform import mom
from cdb.validationkit.op import make_argument_list
from cdb.validationkit.op import operation as interactive_operation
from cdbwrapc import Operation, createOperationFromCMSGUrl
import logging
import os
import sys

from cs.requirements import RQMSpecObject
from cs.requirements import RQMSpecification

from .utils import RequirementsTestCase


LOG = logging.getLogger(__name__)


class TestBatchModification(RequirementsTestCase):
    need_uberserver = False
    
    def setUp(self):
        super(TestBatchModification, self).setUp()
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        req = RQMSpecObject.KeywordQuery(name_de=u'anf3', specification_object_id=spec.cdb_object_id)[0]

    def test_batch_modification_with_inconsistent_parent_and_spec(self):
        """Check if batch_modification raises an exception when the user configured inconsistent spec/parent data"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        reqs_to_move = RQMSpecObject.KeywordQuery(
            specification_object_id=spec.cdb_object_id, specobject_id=["RT000000003","RT000000005"]
        )
        self.assertEqual(len(reqs_to_move), 2)
        new_parent_req = RQMSpecObject.ByKeys(specobject_id=u"RT000000045")
        self.assertNotEqual(spec.cdb_object_id, new_parent_req.specification_object_id)
        user_input = {
            "specification_object_id": spec.cdb_object_id,
            "parent_object_id": new_parent_req.cdb_object_id
        }
        with self.assertRaises(RuntimeError):
            interactive_operation(
                "cdbrqm_batch_modification", [r for r in reqs_to_move], user_input=user_input
            )


    def test_batch_modification_raises_exception(self):
        """Check if batch_modification raises an exception when requirements are not met.
        Test to check if the batch_modification operation is throwing an exception due to the requirement object
        not being in a state in which is possible.
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        spec.ChangeState(100, check_access=0)
        spec.ChangeState(200, check_access=0)
        requirement = RQMSpecObject.KeywordQuery(name_de=u'anf3', specification_object_id=spec.cdb_object_id)[0]
        self.assertTrue(requirement.Specification.status == 200)
        with self.assertRaises(RuntimeError):
            interactive_operation("cdbrqm_batch_modification", requirement)

    def test_batch_modification_possible(self):
        """Check if batch_modification changes a value on multiple requirements
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement1 = RQMSpecObject.KeywordQuery(name_de=u'anf1-1', specification_object_id=spec.cdb_object_id)[0]
        self.assertTrue(requirement1.Specification.status == 0)
        requirement2 = RQMSpecObject.KeywordQuery(name_de=u'anf2', specification_object_id=spec.cdb_object_id)[0]
        self.assertTrue(requirement1.Specification.status == 0)

        requirements = [requirement1.ToObjectHandle(), requirement2.ToObjectHandle()]
        # TODO E042390
        user_input = {"weight": 2}
        preset = {}
        dlg_args = make_argument_list(None, user_input)
        op_args = make_argument_list(None, preset)
        _operation = Operation("cdbrqm_batch_modification", requirements, mom.SimpleArgumentList())
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

        self.assertTrue(requirement1.weight == 2)
        self.assertTrue(requirement2.weight == 2)

    def test_batch_modififcation_move(self):
        """Check if batch_modification handles requirement movement correctly
        """

        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        requirement11 = \
            RQMSpecObject.KeywordQuery(name_de=u'anf1-1', specification_object_id=spec.cdb_object_id)[0]
        requirement12 = \
            RQMSpecObject.KeywordQuery(name_de=u'anf1-2', specification_object_id=spec.cdb_object_id)[0]
        self.assertEqual(requirement11.position, 1)
        self.assertEqual(requirement12.position, 2)
        requirement1 = \
            RQMSpecObject.KeywordQuery(cdb_object_id=requirement11.parent_object_id,
                                       specification_object_id=spec.cdb_object_id)[0]
        requirement2 = \
            RQMSpecObject.KeywordQuery(name_de=u'anf2', specification_object_id=spec.cdb_object_id)[
                0]
        interactive_operation("cdbrqm_easy_fulfilled", requirement11)
        requirement11.Reload()
        self.assertEqual(requirement11.act_value, 100.0)
        requirement1.Reload()
        self.assertEqual(requirement1.act_value, 50.0)
        user_input = {"parent_object_id": requirement2.cdb_object_id}
        preset = {}
        interactive_operation("cdbrqm_batch_modification", requirement11, user_input, preset)
        valid_objects = [u"anf1", u"anf1-2", u"anf2", u"anf1-1", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=spec.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
        requirement1.Reload()
        requirement11.Reload()
        requirement12.Reload()
        requirement2.Reload()
        self.assertEqual(requirement1.act_value, 0.0)
        self.assertEqual(requirement2.act_value, 100.0)
        self.assertEqual(len(requirement1.SubRequirements), 1)
        self.assertEqual(requirement12.position, 1)
        self.assertEqual(len(requirement2.SubRequirements), 1)
        self.assertEqual(requirement11.position, 1)

        user_input = {"parent_object_id": requirement1.cdb_object_id}
        preset = {}
        interactive_operation("cdbrqm_batch_modification", requirement11, user_input, preset)

        valid_sortations = [
            # see E061691 for details
            # expected is that moved elements are appended behind the other elements of the new parent.
            [u"anf1", u"anf1-2", u"anf1-1", u"anf2", u"anf3"]
        ]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=spec.cdb_object_id, order_by="sortorder")
        acceptable_sortation_found = False
        for sortation in valid_sortations:
            matching = True
            for specobj in requirements:
                matching = matching and sortation[requirements.index(specobj)] == specobj.name_de
                if not matching:
                    break
            if matching:
                acceptable_sortation_found = True
        self.assertTrue(acceptable_sortation_found, requirements.name_de)
        requirement1.Reload()
        requirement11.Reload()
        requirement12.Reload()
        requirement2.Reload()
        self.assertEqual(requirement2.act_value, None)
        self.assertEqual(len(requirement1.SubRequirements), 2)
        self.assertEqual(len(requirement2.SubRequirements), 0)
        self.assertEqual(requirement11.position, 2)
        self.assertEqual(requirement12.position, 1)

    def test_batch_modification_fails_when_changing_parent_to_self(self):
        # see E075901
        from cdb.objects import operations
        spec = operations.operation("CDB_Create", RQMSpecification, name="batch_modification_E075901")
        req_args = {
            "specification_object_id": spec.cdb_object_id,
            "parent_object_id": None,
            "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % "lorem_ipsum"
        }
        preset = {}
        req1 = interactive_operation("CDB_Create", RQMSpecObject, req_args, preset)
        req_args.update(parent_object_id=req1.cdb_object_id)
        req11 = interactive_operation("CDB_Create", RQMSpecObject, req_args, preset)
        
        user_input = {"parent_object_id": req11.cdb_object_id}
        with self.assertRaises(ElementsError):
            interactive_operation("cdbrqm_batch_modification", req11, user_input, preset)
        