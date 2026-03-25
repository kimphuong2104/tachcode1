# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import datetime
import logging
import os
import unittest

from lxml import etree
from webtest import TestApp
from xmldiff.diff import Differ

from cdb.objects import operations
from cdb.objects.cdb_file import CDB_File
from cdb.testcase import RollbackTestCase
from cs.requirements.tests.utils import RequirementsTestCase
from cs.classification import api as classification_api
from cs.platform.web.root import root as RootApp
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.tests.test_specification import TestSpecification
from cs.requirements.web.rest.diff.acceptance_criterion_model import \
    ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID
from cs.requirements.web.rest.diff.diff_indicator_model import (
    DiffCriterionRegistry, DiffIndicatorAPIModel)
from cs.requirements.web.rest.diff.file_model import DiffFileAPIModel
from cs.requirements.web.rest.diff.main import MOUNT_PATH as API_MOUNT_PATH
from cs.requirements.web.rest.diff.matching_model import DiffMatchingAPIModel
from cs.requirements.web.rest.diff.richtext_model import DiffRichTextAPIModel
from cs.requirements.richtext import RichTextModifications

LOG = logging.getLogger(__name__)


class TestDiffRichtextAPIModel(RollbackTestCase):
    def setUp(self):
        self.maxDiff = None
        RollbackTestCase.setUp(self)
        self.spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 001')
        self.left_req = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='RQMDiffModels Req 001'
        )
        self.right_req = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='RQMDiffModels Req 001'
        )
        self.spec.Reload()

    def assertEqual(self, first, second, msg=None):
        if (
            isinstance(first, str) and isinstance(second, str) and
            first.startswith('<') and second.startswith('<')
        ):
            # compare both xml normalized to default representation
            kwargs = RichTextModifications.force_serializations({
                "first": first,
                "second": second,
            })
            super(TestDiffRichtextAPIModel, self).assertEqual(msg=msg, **kwargs)
        else:
            super(TestDiffRichtextAPIModel, self).assertEqual(first=first, second=second, msg=msg)

    def _diff(self, left_obj=None, right_obj=None, languages=None):
        if languages is None:
            languages = ['en']
        if left_obj is None:
            left_obj_id = self.left_req.cdb_object_id
        else:
            left_obj_id = left_obj
        if right_obj is None:
            right_obj_id = self.right_req.cdb_object_id
        else:
            right_obj_id = right_obj
        model = DiffRichTextAPIModel(
            left_cdb_object_id=left_obj_id,
            right_cdb_object_id=right_obj_id
        )
        return model.diff(languages)

    def _get_matches(self, left, right):
        differ = Differ(F=0.8, ratio_mode='accurate')
        left_tree, right_tree = etree.fromstring(left), etree.fromstring(right)
        return differ.match(left_tree, right_tree)

    def _setTexts(self, left=None, right=None):
        if left is not None:
            self.left_req.SetText(
                "cdbrqm_spec_object_desc_en",
                left.replace('\n', '')
            )
        if right is not None:
            self.right_req.SetText(
                "cdbrqm_spec_object_desc_en",
                right.replace('\n', '')
            )

    def _wrap_with_xml(self, text):
        return '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml">{}</xml>'.format(text)

    def _wrap_with_diffxml(self, text):
        return '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff">{}</xml>'.format(text)

    def test_one_side_empty(self):
        left = """<xhtml:div>this is a test with only one side</xhtml:div>"""
        self._setTexts(left)
        result = self._diff(right_obj="null")['diff_dict']['en']
        self.assertEqual(result['xhtml_left'], "single_object")
        self.assertEqual(result['xhtml_right'], "single_object")
        self.assertEqual(
            result['xhtml_single'],
            self._wrap_with_xml(left)
        )

    def test_no_difference(self):
        left = """<xhtml:div>this is a test with no difference</xhtml:div>"""
        right = left
        self._setTexts(left, right)
        result = self._diff()['diff_dict']['en']
        self.assertEqual(result['xhtml_left'], None)
        self.assertEqual(result['xhtml_right'], None)
        self.assertEqual(
            result['xhtml_single'],
            self._wrap_with_xml(left)
        )

    def test_simple_difference_in_one_tag(self):
        left = """<xhtml:div>this is a test with no difference</xhtml:div>"""
        right = """<xhtml:div>this is a test with one difference</xhtml:div>"""
        self._setTexts(left, right)
        result = self._diff()['diff_dict']['en']
        self.assertEqual(
            result['xhtml_left'],
            self._wrap_with_diffxml(
                """<xhtml:div>this is a test with <del>n</del>o<ins>ne</ins> difference</xhtml:div>"""
            )
        )
        self.assertEqual(
            result['xhtml_right'],
            self._wrap_with_diffxml(
                """<xhtml:div>this is a test with <del>n</del>o<ins>ne</ins> difference</xhtml:div>"""
            )
        )
        self.assertEqual(result['xhtml_single'], None)

    def test_multiple_differences_in_one_tag(self):
        left = """<xhtml:div>this is a test with no difference</xhtml:div>"""
        right = """<xhtml:div>this is not a test with just one difference</xhtml:div>"""
        self._setTexts(left, right)
        result = self._diff()['diff_dict']['en']
        self.assertEqual(
            result['xhtml_left'],
            self._wrap_with_diffxml(
                """<xhtml:div>this is <ins>not </ins>a test with <del>no</del><ins>just one</ins> difference</xhtml:div>"""
            )
        )
        self.assertEqual(
            result['xhtml_right'],
            self._wrap_with_diffxml(
                """<xhtml:div>this is <ins>not </ins>a test with <del>no</del><ins>just one</ins> difference</xhtml:div>"""
            )
        )
        self.assertEqual(result['xhtml_single'], None)

    def test_simple_difference_in_multiple_tags(self):
        left = """<xhtml:div><xhtml:div>this is a test</xhtml:div><xhtml:div> with no difference</xhtml:div></xhtml:div>"""
        right = """<xhtml:div><xhtml:div>this is the test</xhtml:div><xhtml:div> with one difference</xhtml:div></xhtml:div>"""
        self._setTexts(left, right)
        result = self._diff()['diff_dict']['en']
        self.assertEqual(
            result['xhtml_left'],
            self._wrap_with_diffxml(
                """<xhtml:div><xhtml:div>this is <del>a</del><ins>the</ins> test</xhtml:div><xhtml:div> with <del>n</del>o<ins>ne</ins> difference</xhtml:div></xhtml:div>"""
            )
        )
        self.assertEqual(
            result['xhtml_right'],
            self._wrap_with_diffxml(
                """<xhtml:div><xhtml:div>this is <del>a</del><ins>the</ins> test</xhtml:div><xhtml:div> with <del>n</del>o<ins>ne</ins> difference</xhtml:div></xhtml:div>"""
            )
        )
        self.assertEqual(result['xhtml_single'], None)

    def test_multiple_differences_in_multiple_tags(self):
        left = """<xhtml:div><xhtml:div>this is a test</xhtml:div><xhtml:div> with no difference</xhtml:div></xhtml:div>"""
        right = """<xhtml:div><xhtml:div>what is the test</xhtml:div><xhtml:div>that contains one difference</xhtml:div></xhtml:div>"""
        self._setTexts(left, right)
        result = self._diff()['diff_dict']['en']
        self.assertEqual(
            result['xhtml_left'],
            self._wrap_with_diffxml(
                """<xhtml:div diff:delete=""><xhtml:div diff:delete="">this is a test</xhtml:div><xhtml:div diff:delete=""> with no difference</xhtml:div></xhtml:div>"""
            )
        )
        self.assertEqual(
            result['xhtml_right'],
            self._wrap_with_diffxml(
                """<xhtml:div diff:insert=""><xhtml:div diff:insert="">what is the test</xhtml:div><xhtml:div diff:insert="">that contains one difference</xhtml:div></xhtml:div>"""
            )
        )
        self.assertEqual(result['xhtml_single'], None)
        matches = self._get_matches(self._wrap_with_xml(left), self._wrap_with_xml(right))
        self.assertEqual(len(matches), 1)


class TestDiffMatchingAPIModel(RollbackTestCase):

        def setUp(self):
            self.maxDiff = None
            RollbackTestCase.setUp(self)
            self.test_file_path = os.path.join(os.path.dirname(__file__), 'dummy_file_01.txt')
            self.test_file_path2 = os.path.join(os.path.dirname(__file__), 'dummy_file_02.txt')
            # ensure that in the system there are also files which are assigned to different objects
            # but the system have to find the right differences anyway!
            dummy_spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 000')
            CDB_File.NewFromFile(
                for_object_id=dummy_spec.cdb_object_id,
                from_path=self.test_file_path,
                primary=False
            )
            CDB_File.NewFromFile(
                for_object_id=dummy_spec.cdb_object_id,
                from_path=self.test_file_path2,
                primary=False
            )
            self.spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 001')
            self.req1 = operations.operation(
                'CDB_Create',
                RQMSpecObject,
                specification_object_id=self.spec.cdb_object_id,
                cdbrqm_spec_object_desc_en='RQMDiffModels Req 001'
            )
            self.spec.Reload()
            self.criterions = [
                x.get('id') for x in DiffCriterionRegistry.get_criterions(RQMSpecObject)
            ]
            self.languages = ['de', 'en']

        def test_actual_and_baselined_spec(self):
            baselined_spec = operations.operation(
                'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
                ce_baseline_comment='baseline1 with one req'
            )
            model = DiffMatchingAPIModel(
                baselined_spec.cdb_object_id, self.spec.cdb_object_id, self.req1.cdb_object_id,
                'left'
            )
            left_object = model.get_matching_object()
            self.assertNotEqual(left_object, None)
            # should be the same requirement BUT another version of it
            self.assertEqual(self.req1.specobject_id, left_object.specobject_id)
            self.assertNotEqual(self.req1.cdb_object_id, left_object.cdb_object_id)
            self.assertEqual(left_object.specification_object_id, baselined_spec.cdb_object_id)

        def test_actual_and_previous_index_spec(self):
            self.spec.ChangeState(RQMSpecification.REVIEW)
            self.spec.ChangeState(RQMSpecification.RELEASED)
            operations.operation('cdbrqm_new_revision', self.spec)
            newspec = RQMSpecification.ByKeys(spec_id=self.spec.spec_id, revision=1)
            new_req1 = newspec.Requirements[0]
            model = DiffMatchingAPIModel(
                self.spec.cdb_object_id, newspec.cdb_object_id, new_req1.cdb_object_id,
                'left'
            )
            left_object = model.get_matching_object()
            self.assertNotEqual(left_object, None)
            # should be the same requirement BUT another version of it
            self.assertEqual(new_req1.specobject_id, left_object.specobject_id)
            self.assertNotEqual(new_req1.cdb_object_id, left_object.cdb_object_id)
            self.assertEqual(left_object.specification_object_id, self.spec.cdb_object_id)

        def test_actual_and_previous_index_baseline_spec(self):
            prev_index_baselined_spec = operations.operation(
                'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
                ce_baseline_comment='baseline1 with one req'
            )
            self.spec.ChangeState(RQMSpecification.REVIEW)
            self.spec.ChangeState(RQMSpecification.RELEASED)
            operations.operation('cdbrqm_new_revision', self.spec)
            newspec = RQMSpecification.ByKeys(spec_id=self.spec.spec_id, revision=1)
            new_req1 = newspec.Requirements[0]
            model = DiffMatchingAPIModel(
                prev_index_baselined_spec.cdb_object_id,
                newspec.cdb_object_id,
                new_req1.cdb_object_id,
                'left'
            )
            left_object = model.get_matching_object()
            self.assertNotEqual(left_object, None)
            # should be the same requirement BUT another version of it
            self.assertEqual(new_req1.specobject_id, left_object.specobject_id)
            self.assertNotEqual(new_req1.cdb_object_id, left_object.cdb_object_id)
            self.assertEqual(
                left_object.specification_object_id, prev_index_baselined_spec.cdb_object_id)

        def test_actual_index_baseline_and_previous_index_spec(self):
            self.spec.ChangeState(RQMSpecification.REVIEW)
            self.spec.ChangeState(RQMSpecification.RELEASED)
            operations.operation('cdbrqm_new_revision', self.spec)
            newspec = RQMSpecification.ByKeys(spec_id=self.spec.spec_id, revision=1)
            baselined_spec = operations.operation(
                'ce_baseline_create', newspec, ce_baseline_name='baseline1',
                ce_baseline_comment='baseline1 with one req'
            )
            baselined_req1 = baselined_spec.Requirements[0]
            model = DiffMatchingAPIModel(
                self.spec.cdb_object_id, baselined_spec.cdb_object_id, baselined_req1.cdb_object_id,
                'left'
            )
            left_object = model.get_matching_object()
            self.assertNotEqual(left_object, None)
            # should be the same requirement BUT another version of it
            self.assertEqual(baselined_req1.specobject_id, left_object.specobject_id)
            self.assertNotEqual(baselined_req1.cdb_object_id, left_object.cdb_object_id)
            self.assertEqual(left_object.specification_object_id, self.spec.cdb_object_id)

        def test_actual_index_baseline_and_previous_index_baseline(self):
            prev_index_baselined_spec = operations.operation(
                'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
                ce_baseline_comment='baseline1 with one req'
            )
            self.spec.ChangeState(RQMSpecification.REVIEW)
            self.spec.ChangeState(RQMSpecification.RELEASED)
            operations.operation('cdbrqm_new_revision', self.spec)
            newspec = RQMSpecification.ByKeys(spec_id=self.spec.spec_id, revision=1)
            new_index_baselined_spec = operations.operation(
                'ce_baseline_create', newspec, ce_baseline_name='baseline2',
                ce_baseline_comment='baseline2 with one req'
            )
            new_req1 = new_index_baselined_spec.Requirements[0]
            model = DiffMatchingAPIModel(
                prev_index_baselined_spec.cdb_object_id,
                new_index_baselined_spec.cdb_object_id,
                new_req1.cdb_object_id,
                'left'
            )
            left_object = model.get_matching_object()
            self.assertNotEqual(left_object, None)
            # should be the same requirement BUT another version of it
            self.assertEqual(new_req1.specobject_id, left_object.specobject_id)
            self.assertNotEqual(new_req1.cdb_object_id, left_object.cdb_object_id)
            self.assertEqual(
                left_object.specification_object_id, prev_index_baselined_spec.cdb_object_id)

        def test_template_and_instantiated_spec(self):
            template_spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
            TestSpecification.make_spec_to_template_spec(template_spec)
            # instantiate from template
            spec_instance = operations.operation(
                "CDB_Copy", template_spec, is_template=0
            )
            spec_instance.Reload()
            self.assertNotEqual(
                template_spec.spec_id,
                spec_instance.spec_id
            )
            self.assertNotEqual(
                template_spec.ce_baseline_origin_id,
                spec_instance.ce_baseline_origin_id
            )
            self.assertEqual(
                spec_instance.ce_baseline_object_id,
                spec_instance.cdb_object_id
            )
            template_req1 = template_spec.Requirements[0]
            instance_req1 = spec_instance.Requirements[0]
            self.assertNotEqual(
                template_req1.specobject_id,
                instance_req1.specobject_id
            )
            self.assertNotEqual(
                template_req1.cdb_object_id,
                instance_req1.cdb_object_id
            )
            self.assertNotEqual(
                template_req1.ce_baseline_object_id,
                instance_req1.ce_baseline_object_id
            )
            self.assertEqual(
                instance_req1.ce_baseline_object_id,
                instance_req1.cdb_object_id
            )
            self.assertNotEqual(
                template_req1.ce_baseline_origin_id,
                instance_req1.ce_baseline_origin_id
            )
            self.assertEqual(
                template_req1.cdb_object_id,
                instance_req1.SemanticLinks[0].Object.cdb_object_id
            )
            self.assertEqual(instance_req1.SemanticLinks[0].linktype_name, 'Copy of')
            model = DiffMatchingAPIModel(
                template_spec.cdb_object_id,
                spec_instance.cdb_object_id,
                instance_req1.cdb_object_id,
                'left'
            )
            left_object = model.get_matching_object()
            self.assertNotEqual(left_object, None)
            self.assertEqual(template_req1.cdb_object_id, left_object.cdb_object_id)

class TestDiffIndicatorAPIModel(RequirementsTestCase):
    need_uberserver = True

    def setUp(self):
        self.maxDiff = None
        RollbackTestCase.setUp(self)
        self.test_file_path = os.path.join(os.path.dirname(__file__), 'dummy_file_01.txt')
        self.test_file_path2 = os.path.join(os.path.dirname(__file__), 'dummy_file_02.txt')
        # ensure that in the system there are also files which are assigned to different objects
        # but the system have to find the right differences anyway!
        dummy_spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 000')
        CDB_File.NewFromFile(
            for_object_id=dummy_spec.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        CDB_File.NewFromFile(
            for_object_id=dummy_spec.cdb_object_id,
            from_path=self.test_file_path2,
            primary=False
        )
        self.spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 001')
        self.req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='RQMDiffModels Req 001'
        )
        self.spec.Reload()
        self.criterions = [
            x.get('id') for x in DiffCriterionRegistry.get_criterions(RQMSpecObject)
        ]
        self.languages = ['de', 'en']

    def test_indicator_with_file_differences(self):
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        self.req1.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        # overwrite file content with different content
        self.req1.Files[0].checkin_file(self.test_file_path2)
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')

    def test_indicator_with_metadata_differences(self):
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        self.req1.is_defined = 1
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')

    def test_indicator_with_initial_classification_differences(self):
        """ Check whether previous not classified objects are marked as changed by classification if they got classified the first time"""
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='before first classification'
        )
        data = classification_api.get_new_classification(["RQM_TEST01"])
        data['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
            {
                'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                'property_type': u'datetime',
                'value': datetime.datetime.now()
            }
        )
        classification_api.update_classification(
            self.req1, data, check_access=False
        )

        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')

    def test_indicator_with_classification_differences(self):
        data = classification_api.get_new_classification(["RQM_TEST01"])
        data['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
            {
                'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                'property_type': u'datetime',
                'value': datetime.datetime(2018, 2, 23, 0, 0)
            }
        )
        classification_api.update_classification(
            self.req1, data, check_access=False
        )
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        data = classification_api.get_new_classification(["RQM_TEST01"])
        data['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
            {
                'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                'property_type': u'datetime',
                'value': datetime.datetime.now()
            }
        )
        classification_api.update_classification(
            self.req1, data, check_access=False
        )

        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')

    def test_without_differences(self):
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertEqual(len(diffs), 0)

    def test_with_new_requirements(self):
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        new_req = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='RQMDiffModels Req 002'
        )
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_req.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[new_req.cdb_object_id]['type'], 'added')

    def test_with_new_req_with_new_target_value(self):
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1'
        )
        new_req = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='RQMDiffModels Req 002'
        )
        new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            requirement_object_id=new_req.cdb_object_id
        )
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_tv.cdb_object_id, diffs)
        self.assertIn(new_req.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 3)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[new_req.cdb_object_id]['type'], 'added')
        self.assertEqual(diffs[new_tv.cdb_object_id]['type'], 'added')

    def test_with_new_target_value(self):
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1'
        )
        new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            requirement_object_id=self.req1.cdb_object_id
        )
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_tv.cdb_object_id, diffs)
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 3)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        # a requirement should be marked as changed in case of changed or added acceptance criteria
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')
        self.assertEqual(diffs[new_tv.cdb_object_id]['type'], 'added')

    def test_with_target_value_metadata_change(self):
        new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            requirement_object_id=self.req1.cdb_object_id,
            weight=1
        )
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        new_tv.weight = 2
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_tv.cdb_object_id, diffs)
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 3)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        # a requirement should be marked as changed in case of changed or added acceptance criteria
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')
        self.assertEqual(diffs[new_tv.cdb_object_id]['type'], 'changed')

    def test_with_target_value_file_change(self):
        new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            requirement_object_id=self.req1.cdb_object_id,
        )
        CDB_File.NewFromFile(
            for_object_id=new_tv.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        self.req1.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        # overwrite file content with different content
        new_tv.Files[0].checkin_file(self.test_file_path2)
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_tv.cdb_object_id, diffs)
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 3)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        # a requirement should be marked as changed in case of changed or added acceptance criteria
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')
        self.assertEqual(diffs[new_tv.cdb_object_id]['type'], 'changed')

    def test_with_target_value_classification_change(self):
        new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            requirement_object_id=self.req1.cdb_object_id,
        )
        data = classification_api.get_new_classification(["RQM_TEST01"])
        data['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
            {
                'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                'property_type': u'datetime',
                'value': datetime.datetime(2018, 2, 23, 0, 0)
            }
        )
        classification_api.update_classification(
            new_tv, data, check_access=False
        )
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        data['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
            {
                'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                'property_type': u'datetime',
                'value': datetime.datetime.now()
            }
        )
        classification_api.update_classification(
            new_tv, data, check_access=False
        )
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_tv.cdb_object_id, diffs)
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 3)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        # a requirement should be marked as changed in case of changed or added acceptance criteria
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')
        self.assertEqual(diffs[new_tv.cdb_object_id]['type'], 'changed')

    def test_with_target_value_richtext_change(self):
        new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            requirement_object_id=self.req1.cdb_object_id
        )
        new_tv.SetText('cdbrqm_target_value_desc_de', '''
        <xhtml:div>
            Dies ist ein Testtext, welcher nicht geändert wird
        </xhtml:div>
        ''')
        new_tv.SetText('cdbrqm_target_value_desc_en', '''
        <xhtml:div>
            This is a test text with some tapos within it.
        </xhtml:div>
        ''')
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        new_tv.SetText('cdbrqm_target_value_desc_en', '''
        <xhtml:div>
            This is a test text with some typos within it.
        </xhtml:div>
        ''')
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(new_tv.cdb_object_id, diffs)
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 3)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        # a requirement should be marked as changed in case of changed or added acceptance criteria
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')
        self.assertEqual(diffs[new_tv.cdb_object_id]['type'], 'changed')
        # check only for a language which is unchanged -> should not find differences of other langs
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, ['de'])
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertEqual(len(diffs), 0)

    def test_indicator_with_richtext_differences(self):
        self.req1.SetText('cdbrqm_spec_object_desc_de', '''
        <xhtml:div>
            Dies ist ein Testtext, welcher nicht geändert wird
        </xhtml:div>
        ''')
        self.req1.SetText('cdbrqm_spec_object_desc_en', '''
        <xhtml:div>
            This is a test text with some tapos within it.
        </xhtml:div>
        ''')
        self.req1.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        self.req1.SetText('cdbrqm_spec_object_desc_en', '''
        <xhtml:div>
            This is a test text with some typos within it.
        </xhtml:div>
        ''')
        model = DiffIndicatorAPIModel(baselined_spec.cdb_object_id, self.spec.cdb_object_id)
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, self.languages)
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertIn(self.req1.cdb_object_id, diffs)
        self.assertIn(self.spec.cdb_object_id, diffs)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(diffs[self.spec.cdb_object_id]['type'], 'indirect')
        self.assertEqual(diffs[self.req1.cdb_object_id]['type'], 'changed')
        # check only for a language which is unchanged -> should not find differences of other langs
        diffs = model.get_diff_indicator_for_all_tree_nodes(
            DiffCriterionRegistry.get_settings_by_criterions(self.criterions, ['de'])
        )
        diffs = {k:v for (k,v) in diffs.items() if k not in ["plugin_errors", "plugin_warnings"]}
        self.assertEqual(len(diffs), 0)


class TestDiffFileAPIModel(RollbackTestCase):

    def setUp(self):
        self.maxDiff = None
        RollbackTestCase.setUp(self)
        self.test_file_path = os.path.join(os.path.dirname(__file__), 'dummy_file_01.txt')
        self.test_file_path2 = os.path.join(os.path.dirname(__file__), 'dummy_file_02.txt')
        # ensure that in the system there are also files which are assigned to different objects
        # but the system have to find the right differences anyway!
        dummy_spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 000')
        CDB_File.NewFromFile(
            for_object_id=dummy_spec.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        CDB_File.NewFromFile(
            for_object_id=dummy_spec.cdb_object_id,
            from_path=self.test_file_path2,
            primary=False
        )
        self.spec = operations.operation('CDB_Create', RQMSpecification, name='RQMDiffModels Spec 001')
        self.req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='RQMDiffModels Req 001'
        )
        self.spec.Reload()
        criterions = [
            x.get('id') for x in DiffCriterionRegistry.get_criterions(RQMSpecObject)
        ]
        self.settings = DiffCriterionRegistry.get_settings_by_criterions(criterions, ['de', 'en'])
        self.settings['criterions_per_class'][RQMSpecification.__maps_to__] = []

    def test_file_fast_comparison_same_file_count_different_file(self):
        """ Test whether the model finds differences for changed files """
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        self.req1.Reload()
        self.spec.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        req1_baselined = baselined_spec.Requirements[0]
        self.assertEqual(req1_baselined.Files[0].cdbf_name, self.req1.Files[0].cdbf_name)
        self.req1.Files[0].checkin_file(self.test_file_path2)
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))

    def test_file_fast_comparison_new_files(self):
        """ Test whether the model finds differences for new files (1 -> 2)"""
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        self.req1.Reload()
        self.spec.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with one file'
        )
        req1_baselined = baselined_spec.Requirements[0]
        self.assertEqual(req1_baselined.Files[0].cdbf_name, self.req1.Files[0].cdbf_name)
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path2,
            primary=False
        )
        self.req1.Reload()
        self.assertGreater(len(self.req1.Files), len(req1_baselined.Files))
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))

    def test_file_fast_comparison_new_files_initial(self):
        """ Test whether the model finds differences for new files (0 -> 1)"""
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 without file'
        )
        req1_baselined = baselined_spec.Requirements[0]
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path2,
            primary=False
        )
        self.req1.Reload()
        self.assertGreater(len(self.req1.Files), len(req1_baselined.Files))
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))

    def test_file_fast_comparison_deleted_files(self):
        """ Test whether the model finds differences for deleted files (2->1)"""
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path2,
            primary=False
        )
        self.req1.Reload()
        self.spec.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with two files'
        )
        req1_baselined = baselined_spec.Requirements[0]
        self.assertEqual(req1_baselined.Files[0].cdbf_name, self.req1.Files[0].cdbf_name)
        self.req1.Files[1].Delete()
        self.req1.Reload()
        self.assertLess(len(self.req1.Files), len(req1_baselined.Files))
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))

    def test_file_fast_comparison_deleted_files_initial(self):
        """ Test whether the model finds differences for deleted files (1->0)"""
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path,
            primary=False
        )
        self.req1.Reload()
        self.spec.Reload()
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 with two files'
        )
        req1_baselined = baselined_spec.Requirements[0]
        self.req1.Files[0].Delete()
        self.req1.Reload()
        self.assertLess(len(self.req1.Files), len(req1_baselined.Files))
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))

    def test_file_fast_comparison_no_file_add_delete(self):
        """ Test whether the model finds differences for added/deleted files in a more complex scenario with multiple baselines """
        baselined_spec = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline1',
            ce_baseline_comment='baseline1 without file'
        )
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertNotIn(self.req1.cdb_object_id, diffs.get('changed_ids'))
        self.assertEqual(len(diffs.get('changed_ids', [])), 0)
        req1_baselined = baselined_spec.Requirements[0]
        CDB_File.NewFromFile(
            for_object_id=self.req1.cdb_object_id,
            from_path=self.test_file_path2,
            primary=False
        )
        self.req1.Reload()
        self.assertGreater(len(self.req1.Files), len(req1_baselined.Files))
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))
        self.assertEqual(len(diffs.get('changed_ids', [])), 1)
        baselined_spec2 = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline2',
            ce_baseline_comment='baseline2 with 1 file'
        )
        req1_baselined2 = baselined_spec2.Requirements[0]
        self.req1.Files[0].Delete()
        self.req1.Reload()
        self.assertLess(len(self.req1.Files), len(req1_baselined2.Files))
        baselined_spec3 = operations.operation(
            'ce_baseline_create', self.spec, ce_baseline_name='baseline3',
            ce_baseline_comment='baseline3 without file'
        )
        self.assertEqual(len(self.req1.Files), 0)
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec2, self.spec,
            settings=self.settings
        )
        self.assertIn(self.req1.cdb_object_id, diffs.get('changed_ids'))
        self.assertEqual(len(diffs.get('changed_ids', [])), 1)
        diffs = DiffFileAPIModel.fast_file_diff_ids(
            baselined_spec3, self.spec,
            settings=self.settings
        )
        self.assertNotIn(self.req1.cdb_object_id, diffs.get('changed_ids'))
        self.assertEqual(len(diffs.get('changed_ids', [])), 0)


class TestRQMDiffRESTAPIEndpoints(RollbackTestCase):

    def __init__(self, *args, **kwargs):
        super(TestRQMDiffRESTAPIEndpoints, self).__init__(*args, **kwargs)
        self.client = None
        self.maxDiff = None

    def setUp(self):
        RollbackTestCase.setUp(self)
        self.client = TestApp(RootApp)

    def assertEqual(self, first, second, msg=None):
        if (
            isinstance(first, str) and isinstance(second, str) and
            first.startswith('<') and second.startswith('<')
        ):
            # compare both xml normalized to default representation
            kwargs = RichTextModifications.force_serializations({
                "first": first,
                "second": second,
            })
            super(TestRQMDiffRESTAPIEndpoints, self).assertEqual(msg=msg, **kwargs)
        else:
            super(TestRQMDiffRESTAPIEndpoints, self).assertEqual(first=first, second=second, msg=msg)

    # Side by Side Plugin
    def test_side_by_side_same_requirement(self):
        """Tests that an object returns an empty diff when compared to itself"""
        left_cdb_object_id = 'c003ef91-2353-11eb-b0bf-34e12d2f8428'
        right_cdb_object_id = 'c003ef91-2353-11eb-b0bf-34e12d2f8428'
        languages = 'de,en'
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], None)
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], None)
        expected_single = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>Anforderung</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_single)

    def test_side_by_side_different_simple_desc(self):
        """Tests a small change in the german description"""
        left_cdb_object_id = 'bba38f1a-34a1-11eb-b0c2-34e12d2f8428'
        right_cdb_object_id = '0f057dc9-3549-11eb-b0c2-34e12d2f8428'
        languages = 'de,en'
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        # Side check German
        expected_left_de = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div diff:delete="">Deutsch - \xc4nderung</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_left_de)
        expected_right_de = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div diff:insert="">Deutsch - \xc4nderung wurde gemacht</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_right_de)
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], None)
        # Side check English
        expected_left_en = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div diff:delete="">Englisch - Changes</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_left_en)
        expected_right_en = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div diff:insert="">Englisch - Changes were done</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_right_en)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], None)

    def test_side_by_side_new_requirement(self):
        """Tests the result of comparing a new requirement"""
        left_cdb_object_id = 'null'
        right_cdb_object_id = '0f057dc6-3549-11eb-b0c2-34e12d2f8428'
        languages = 'de,en'
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        # Side check German
        expected_left_de = u"single_object"
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_left_de)
        expected_right_de = u"single_object"
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_right_de)
        expected_single = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>Deutsch - Neu</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_single)
        # Side check English
        expected_left_en = u"single_object"
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_left_en)
        expected_right_en = u"single_object"
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_right_en)
        expected_single = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>English - New</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], expected_single)

    def test_side_by_side_deleted_requirement(self):
        """Tests the result of comparing a deleted requirement"""
        left_cdb_object_id = 'bba38f18-34a1-11eb-b0c2-34e12d2f8428'
        right_cdb_object_id = 'null'
        languages = 'de,en'
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        # Side check German
        expected_left_de = u"single_object"
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_left_de)
        expected_right_de = u"single_object"
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_right_de)
        expected_single = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>Deutsch - Löschen</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_single)
        # Side check English
        expected_left_en = u"single_object"
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_left_en)
        expected_right_en = u"single_object"
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_right_en)
        expected_single = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>English - Delete</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], expected_single)

    def test_side_by_side_deleted_xhtml(self):
        """Tests the result of comparing an element with completely empty description"""
        # Requirement: RT000000074
        # Specification: ST000000018
        # Baseline: Middle State Baseline
        left_cdb_object_id = '0f057dc8-3549-11eb-b0c2-34e12d2f8428'

        # Requirement: RT000000074
        # Specification: ST000000018
        # Baseline: -
        right_cdb_object_id = 'a23ee6c7-353f-11eb-b0c2-34e12d2f8428'
        left_requirement = RQMSpecObject.ByKeys(cdb_object_id=left_cdb_object_id)
        right_requirement = RQMSpecObject.ByKeys(cdb_object_id=right_cdb_object_id)
        languages = 'de,en'
        target_desc = "cdbrqm_spec_object_desc_de"
        desc_left_raw = left_requirement.GetText(target_desc)
        expected_desc_left_raw = u"<xhtml:div></xhtml:div>"
        self.assertEqual(desc_left_raw, expected_desc_left_raw)
        desc_right_raw = right_requirement.GetText(target_desc)
        expected_desc_right_raw = u""
        self.assertEqual(desc_right_raw, expected_desc_right_raw)
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        # Side check German
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], None)
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], None)
        expected_single = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div/></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_single)
        # Side check English
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], None)
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], None)
        expected_single = u'<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div/></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], expected_single)

    def test_metadata_changes(self):
        """Tests the result of comparing an Specification with different metadata"""
        # Specification: ST000000018
        # Baseline: Middle State Baseline
        left_cdb_object_id = 'bba38f16-34a1-11eb-b0c2-34e12d2f8428'

        # Specification: ST000000018
        # Requirement: RT000000074
        # Baseline: -
        right_cdb_object_id = 'aec6555c-34a0-11eb-b0c2-34e12d2f8428'
        languages = 'de,en'
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_columns = sorted(list(res))
        self.assertEqual(len(res_columns), 3)
        expected_columns = sorted(['color','act_value','target_value'])
        self.assertEqual(res_columns, expected_columns)

    def test_metadata_no_changes(self):
        """Tests the result of comparing an Specification with itself"""
        # Specification: ST000000018
        # Baseline: -
        left_cdb_object_id = 'aec6555c-34a0-11eb-b0c2-34e12d2f8428'

        # Requirement: RT000000074
        # Specification: ST000000018
        # Baseline: -
        right_cdb_object_id = 'aec6555c-34a0-11eb-b0c2-34e12d2f8428'
        languages = 'de,en'
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        self.assertEqual(len(res_rows), 23)

    def test_spec_metadata_richtext_changes(self):
        """Tests the result of comparing a Specification with a baseline where Metadata and Rich Text has been edited"""
        # Specification: ST000000019
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab48-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad372-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Rich text comparison
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        # Expect one key for the dictionary
        self.assertEqual(len(res_rows), 1)
        self.assertEqual(res_rows, ['diff_dict'])
        dict_rows = list(res['diff_dict'])
        # Expect one key for the spec
        self.assertEqual(len(dict_rows), 1)
        self.assertEqual(dict_rows, ['spec'])
        sides_keys = sorted(list(res['diff_dict']['spec']))
        expected_sides = sorted(['xhtml_left', 'xhtml_single', 'xhtml_right'])
        self.assertEqual(sides_keys, expected_sides)
        # Sigle should be none since there is a diff
        self.assertEqual(res['diff_dict']['spec']['xhtml_single'], None)
        expected_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div>Only english description in this text field. \nMetadata fields to change:\n-Category: \t<del>Customer Requirements</del><ins>System specification</ins></xhtml:div></xml>'
        expected_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div>Only english description in this text field. \nMetadata fields to change:\n-Category: \t<del>Customer Requirements</del><ins>System specification</ins></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['spec']['xhtml_left'], expected_left)
        self.assertEqual(res['diff_dict']['spec']['xhtml_right'], expected_right)

        # Metadata comparison
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res_metadata = self.client.get(url).json
        meta_rows = sorted(list(res_metadata))
        self.assertEqual(len(meta_rows), 2)
        expected_fields = sorted(['mapped_category', 'act_value'])
        self.assertEqual(meta_rows, expected_fields)
        # Check category field
        meta_column_map_cat = sorted(list(res_metadata['mapped_category']))
        expected_columns = sorted(['right', 'label', 'left'])
        self.assertEqual(meta_column_map_cat, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['mapped_category']['left'], 'Kundenanforderungen')
        self.assertEqual(res_metadata['mapped_category']['right'], 'Systemspezifikation') # TODO util get label
        self.assertEqual(res_metadata['mapped_category']['label'], 'Kategorie')
        # Check current value field
        meta_column_act_val = sorted(list(res_metadata['act_value']))
        expected_columns = sorted(['right', 'label', 'left'])
        self.assertEqual(meta_column_act_val, expected_columns)
        # Check if the values are what we expect 
        self.assertEqual(res_metadata['act_value']['left'], None)
        self.assertEqual(res_metadata['act_value']['right'], 0.0) # TODO util get label
        self.assertEqual(res_metadata['act_value']['label'], 'Erfüllungsgrad [%]')

    def test_req_long_richtext_changes(self):
        """Tests changing a longer rich text in a requirement"""
        # Requirement: RT000000080
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab4d-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad379-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Rich text comparison
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        # Expect one key for the dictionary
        self.assertEqual(len(res_rows), 1)
        self.assertEqual(res_rows, ['diff_dict'])
        dict_rows = sorted(list(res['diff_dict']))
        # Expect two keys for de, en languages
        self.assertEqual(len(dict_rows), 2)
        expected_rows = sorted(['de', 'en'])
        self.assertEqual(dict_rows, expected_rows)
        sides_keys = sorted(list(res['diff_dict']['de']))
        expected_side_keys = sorted(['xhtml_left', 'xhtml_single', 'xhtml_right'])
        self.assertEqual(sides_keys, expected_side_keys)
        # Check german side
        expected_de_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Langer Text mit Änderungen</xhtml:div><xhtml:div/><xhtml:div>JavaScript Object Notation (JSON) ist ein <ins>super </ins>leicht<del>gewichtig</del>es, textbasiertes, sprachunabhängiges Datenaustauschformat. Es wurde aus dem ECMAScript Programming Language Standard abgeleitet.  JSON definiert einen kleinen Satz von Formatierungsregeln für die portable Darstellung von strukturierten Daten<ins> des Computers</ins>.</xhtml:div><xhtml:div/><xhtml:div>Dieses Dokument beseitigt Inkonsistenzen mit anderen JSON-Spezifikationen, behebt Spezifikationsfehler und bietet eine erfahrungsbasierte Anleitung zur Interoperabilität.</xhtml:div><xhtml:div/><xhtml:div>Dies ist ein Dokument des Internet Standards Track. Dieses Dokument ist ein Produkt der Internet Engineering Task Force (IETF).  Es repräsentiert den Konsens der IETF-Community.  Es wurde öffentlich geprüft und von der Internet Engineering Steering Group (IESG) zur Veröffentlichung freigegeben.  Weitere Informationen zu Internet-Standards finden Sie in Abschnitt 2 von RFC 5741.</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_de_left)
        expected_de_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Langer Text mit Änderungen</xhtml:div><xhtml:div/><xhtml:div>JavaScript Object Notation (JSON) ist ein <ins>super </ins>leicht<del>gewichtig</del>es, textbasiertes, sprachunabhängiges Datenaustauschformat. Es wurde aus dem ECMAScript Programming Language Standard abgeleitet.  JSON definiert einen kleinen Satz von Formatierungsregeln für die portable Darstellung von strukturierten Daten<ins> des Computers</ins>.</xhtml:div><xhtml:div/><xhtml:div>Dieses Dokument beseitigt Inkonsistenzen mit anderen JSON-Spezifikationen, behebt Spezifikationsfehler und bietet eine erfahrungsbasierte Anleitung zur Interoperabilität.</xhtml:div><xhtml:div/><xhtml:div>Dies ist ein Dokument des Internet Standards Track. Dieses Dokument ist ein Produkt der Internet Engineering Task Force (IETF).  Es repräsentiert den Konsens der IETF-Community.  Es wurde öffentlich geprüft und von der Internet Engineering Steering Group (IESG) zur Veröffentlichung freigegeben.  Weitere Informationen zu Internet-Standards finden Sie in Abschnitt 2 von RFC 5741.</xhtml:div><xhtml:div diff:insert=""/><xhtml:div diff:insert="">Hier neue Linie</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_de_right)
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], None)
        # Check english side
        expected_en_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Long text with changes.</xhtml:div><xhtml:div/><xhtml:div>JavaScript Object Notation (JSON) is a <del>lightweight</del><ins>not heavy</ins>, text-based, language-independent data interchange format. It was derived from the ECMAScript Programming Language Standard.  JSON defines a small set of formatting rules for the portable representation of structured data.</xhtml:div><xhtml:div/><xhtml:div>This document removes <del>inconsistencies </del>with other specifications of JSON, repairs specification errors, and offers experience-based interoperability guidance<ins> for computers</ins>.</xhtml:div><xhtml:div/><xhtml:div>This is an Internet Standards Track document. This document is a product of the Internet Engineering Task Force (IETF).  It represents the consensus of the IETF community.  It has received public review and has been approved for publication by the Internet Engineering Steering Group (IESG).  Further information on Internet Standards is available in Section 2 of RFC 5741.</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_en_left)
        expected_en_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Long text with changes.</xhtml:div><xhtml:div/><xhtml:div>JavaScript Object Notation (JSON) is a <del>lightweight</del><ins>not heavy</ins>, text-based, language-independent data interchange format. It was derived from the ECMAScript Programming Language Standard.  JSON defines a small set of formatting rules for the portable representation of structured data.</xhtml:div><xhtml:div/><xhtml:div>This document removes <del>inconsistencies </del>with other specifications of JSON, repairs specification errors, and offers experience-based interoperability guidance<ins> for computers</ins>.</xhtml:div><xhtml:div/><xhtml:div>This is an Internet Standards Track document. This document is a product of the Internet Engineering Task Force (IETF).  It represents the consensus of the IETF community.  It has received public review and has been approved for publication by the Internet Engineering Steering Group (IESG).  Further information on Internet Standards is available in Section 2 of RFC 5741.</xhtml:div><xhtml:div diff:insert=""/><xhtml:div diff:insert="">This is a new line</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_en_right)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], None)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)
        # Metadata comparison
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res_metadata = self.client.get(url).json
        meta_rows = list(res_metadata)
        self.assertGreaterEqual(len(meta_rows), 24)
        # Check category field
        meta_column_map_cat = sorted(list(res_metadata['mapped_category']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_map_cat, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['mapped_category']['right'], 'Anforderung')
        self.assertEqual(res_metadata['mapped_category']['label'], 'Kategorie')
        # Check current value field
        meta_column_act_val = sorted(list(res_metadata['act_value']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_act_val, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['act_value']['right'], None)
        self.assertEqual(res_metadata['act_value']['label'], 'Erfüllungsgrad [%]')

    def test_req_img_changes(self):
        """Tests changing an embedded image in a requirement"""
        # Requirement: RT000000081
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab73-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad37f-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Rich text comparison
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        self.assertEqual(len(res_rows), 1) # Expect one key for the dictionary
        self.assertEqual(res_rows, ['diff_dict'])
        dict_rows = sorted(list(res['diff_dict']))
        self.assertEqual(len(dict_rows), 2) # Expect two keys for de, en languages
        expected_rows = sorted(['de', 'en'])
        self.assertEqual(dict_rows, expected_rows)
        sides_keys = sorted(list(res['diff_dict']['de']))
        expected_side_keys = sorted(['xhtml_left', 'xhtml_single', 'xhtml_right'])
        self.assertEqual(sides_keys, expected_side_keys)
        # Check german side
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], None)
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], None)
        expected_de_single = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div><xhtml:div>Anforderung mit Bild (Änderungen)</xhtml:div><xhtml:div/><xhtml:div> <xhtml:object type="image/jpeg" data="/api/v1/collection/spec_object/861ad37f-8190-11eb-b0ca-34e12d2f8428/files/861ad403-8190-11eb-b0ca-34e12d2f8428?inline=1" width="1334" height="1001" title="tarsier1.jpg" name="/resources/icons/byname/CDBFileType?cdbf_type=JPG"> </xhtml:object> </xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_de_single)
        # Check english side
        expected_en_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Requirement with picture (changes)</xhtml:div><xhtml:div/><xhtml:div> <xhtml:object type="image/jpeg" data="/api/v1/collection/spec_object/c259ab73-8190-11eb-b0ca-34e12d2f8428/files/c259abd3-8190-11eb-b0ca-34e12d2f8428?inline=1" width="1334" height="1001" title="tarsier1.jpg" name="/resources/icons/byname/CDBFileType?cdbf_type=JPG" diff:update-attr="data:tarsier1.jpg;title:tarsier1.jpg"> </xhtml:object> </xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_en_left)
        expected_en_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Requirement with picture (changes)</xhtml:div><xhtml:div/><xhtml:div> <xhtml:object type="image/jpeg" data="/api/v1/collection/spec_object/861ad37f-8190-11eb-b0ca-34e12d2f8428/files/e2716c3b-8190-11eb-b0ca-34e12d2f8428?inline=1" width="1334" height="1001" title="tarsier2.jpg" name="/resources/icons/byname/CDBFileType?cdbf_type=JPG" diff:update-attr="data:tarsier1.jpg;title:tarsier1.jpg"> </xhtml:object> </xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_en_right)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], None)
        # Metadata comparison
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res_metadata = self.client.get(url).json
        meta_rows = list(res_metadata)
        self.assertGreaterEqual(len(meta_rows), 24)
        # Check category field
        meta_column_map_cat = sorted(list(res_metadata['mapped_category']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_map_cat, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['mapped_category']['right'], 'Anforderung')
        self.assertEqual(res_metadata['mapped_category']['label'], 'Kategorie')
        # Check current value field
        meta_column_act_val = sorted(list(res_metadata['act_value']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_act_val, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['act_value']['right'], None)
        self.assertEqual(res_metadata['act_value']['label'], 'Erfüllungsgrad [%]')
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there is a diff
        self.assertEqual(res['changedFiles'], True)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_ordered_list_changes(self):
        """Tests changing an ordered list"""
        # Requirement: RT000000082
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab6d-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad384-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Rich text comparison
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        self.assertEqual(len(res_rows), 1) # Expect one key for the dictionary
        self.assertEqual(res_rows, ['diff_dict'])
        dict_rows = sorted(list(res['diff_dict']))
        self.assertEqual(len(dict_rows), 2) # Expect two keys for de, en languages
        expected_rows = sorted(['de', 'en'])
        self.assertEqual(dict_rows, expected_rows)
        sides_keys = sorted(list(res['diff_dict']['de']))
        expected_side_keys = sorted(['xhtml_left', 'xhtml_single', 'xhtml_right'])
        self.assertEqual(sides_keys, expected_side_keys)
        # Check german side
        expected_de_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Anforderung mit ordered list.</xhtml:div><xhtml:ol><xhtml:li>optionalArray: PropTypes.array</xhtml:li><xhtml:li diff:delete="">optionalBool: PropTypes.bool</xhtml:li><xhtml:li>optionalFunc: PropTypes.func</xhtml:li><xhtml:li diff:delete="">optionalNumber: PropTypes.number</xhtml:li><xhtml:li>optionalObject: PropTypes.object</xhtml:li><xhtml:li>optionalString: PropTypes.string</xhtml:li><xhtml:li diff:delete="">optionalSymbol: PropTypes.Symbol</xhtml:li></xhtml:ol><xhtml:div>Ende der Liste</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_de_left)
        expected_de_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Anforderung mit ordered list.</xhtml:div><xhtml:ol><xhtml:li>optionalArray: PropTypes.array</xhtml:li><xhtml:li>optionalFunc: PropTypes.func</xhtml:li><xhtml:li diff:insert="">optionalNumber: PropTypes.Sollte eine Nummer sein</xhtml:li><xhtml:li>optionalObject: PropTypes.object</xhtml:li><xhtml:li>optionalString: PropTypes.string</xhtml:li><xhtml:li diff:insert="">Objects are keine Primitiven</xhtml:li><xhtml:li diff:insert="">optionalSymbol: PropTypes.Symbol</xhtml:li></xhtml:ol><xhtml:div>Ende der Liste</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_de_right)
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], None)
        # Check english side
        expected_en_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Requirement with ordered list.</xhtml:div><xhtml:ol><xhtml:li>optionalArray: PropTypes.array</xhtml:li><xhtml:li diff:delete="">optionalBool: PropTypes.bool</xhtml:li><xhtml:li>optionalFunc: PropTypes.func</xhtml:li><xhtml:li diff:delete="">optionalNumber: PropTypes.number</xhtml:li><xhtml:li>optionalObject: PropTypes.object</xhtml:li><xhtml:li>optionalString: PropTypes.string</xhtml:li><xhtml:li diff:delete="">optionalSymbol: PropTypes.symbol</xhtml:li></xhtml:ol><xhtml:div>That will be the whole list.</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_en_left)
        expected_en_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Requirement with ordered list.</xhtml:div><xhtml:ol><xhtml:li>optionalArray: PropTypes.array</xhtml:li><xhtml:li>optionalFunc: PropTypes.func</xhtml:li><xhtml:li diff:insert="">optionalNumber: Should be a number</xhtml:li><xhtml:li>optionalObject: PropTypes.object</xhtml:li><xhtml:li>optionalString: PropTypes.string</xhtml:li><xhtml:li diff:insert="">Obejcts are not primitives</xhtml:li><xhtml:li diff:insert="">optionalSymbol: PropTypes.symbol</xhtml:li></xhtml:ol><xhtml:div>That will be the whole list.</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_en_right)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], None)
        # Metadata comparison
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res_metadata = self.client.get(url).json
        meta_rows = list(res_metadata)
        self.assertGreaterEqual(len(meta_rows), 24)
        # Check category field
        meta_column_map_cat = sorted(list(res_metadata['mapped_category']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_map_cat, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['mapped_category']['right'], 'Anforderung')
        self.assertEqual(res_metadata['mapped_category']['label'], 'Kategorie')
        # Check current value field
        meta_column_act_val = sorted(list(res_metadata['act_value']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_act_val, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['act_value']['right'], None)
        self.assertEqual(res_metadata['act_value']['label'], 'Erfüllungsgrad [%]')
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_unordered_list_changes(self):
        """Tests changing an unordered list"""
        # Requirement: RT000000083
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab62-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad377-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Rich text comparison
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        # Expect one key for the dictionary
        self.assertEqual(len(res_rows), 1)
        self.assertEqual(res_rows, ['diff_dict'])
        dict_rows = sorted(list(res['diff_dict']))
        # Expect two keys for de, en languages
        self.assertEqual(len(dict_rows), 2)
        expected_rows = sorted(['de', 'en'])
        self.assertEqual(dict_rows, expected_rows)
        sides_keys = sorted(list(res['diff_dict']['de']))
        expected_side_keys = sorted(['xhtml_left', 'xhtml_single', 'xhtml_right'])
        self.assertEqual(sides_keys, expected_side_keys)
        # Check german side
        expected_de_left = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Anforderung mit unordered list.</xhtml:div><xhtml:ul><xhtml:li>String - speichert Text, z. B. "Hallo". String-Werte sind von doppelten Anführungszeichen umgeben.</xhtml:li><xhtml:li>int - speichert ganze Zahlen ohne Nachkommastellen, z. B. 123 oder -123</xhtml:li><xhtml:li diff:delete="">float - speichert Fließkommazahlen mit Nachkommastellen, z. B. 19,99 oder -19,99</xhtml:li><xhtml:li>char - speichert einzelne Zeichen, wie z. B. "a" oder "B". Char-Werte sind von einfachen Anführungszeichen umgeben</xhtml:li><xhtml:li>boolean - speichert Werte mit zwei Zuständen: wahr oder falsch</xhtml:li></xhtml:ul><xhtml:div>Ender der Liste</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_de_left)
        expected_de_right = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Anforderung mit unordered list.</xhtml:div><xhtml:ul><xhtml:li>String - speichert Text, z. B. "Hallo". String-Werte sind von doppelten Anführungszeichen umgeben.</xhtml:li><xhtml:li>int - speichert ganze Zahlen ohne Nachkommastellen, z. B. 123 oder -123</xhtml:li><xhtml:li>char - speichert einzelne Zeichen, wie z. B. "a" oder "B". Char-Werte sind von einfachen Anführungszeichen umgeben</xhtml:li><xhtml:li>boolean - speichert Werte mit zwei Zuständen: wahr oder falsch</xhtml:li><xhtml:li diff:insert="">Neuer Wert am Ende</xhtml:li></xhtml:ul><xhtml:div>Ender der Liste</xhtml:div></xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_de_right)
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], None)
        # Check english side
        expected_en_left = """<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Requirement with unordered list.</xhtml:div><xhtml:ul><xhtml:li>String - stores text, such as "<del>Hello</del><ins>Contact</ins>". String values are surrounded by <del>double quotes</del><ins>""</ins></xhtml:li><xhtml:li>int - stores integers (whole numbers), without decimals, such as 123 or -123</xhtml:li><xhtml:li diff:delete="">float - stores floating point numbers, with decimals, such as 19.99 or -19.99</xhtml:li><xhtml:li>char - stores single characters, such as 'a' or 'B'. Char values are surrounded by single quotes</xhtml:li><xhtml:li>boolean - stores values with two states: true or false</xhtml:li></xhtml:ul><xhtml:div>That will be the whole list.</xhtml:div></xhtml:div></xml>"""
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_en_left)
        expected_en_right = """<xml xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:diff="http://namespaces.shoobx.com/diff"><xhtml:div><xhtml:div>Requirement with unordered list.</xhtml:div><xhtml:ul><xhtml:li>String - stores text, such as "<del>Hello</del><ins>Contact</ins>". String values are surrounded by <del>double quotes</del><ins>""</ins></xhtml:li><xhtml:li>int - stores integers (whole numbers), without decimals, such as 123 or -123</xhtml:li><xhtml:li>char - stores single characters, such as 'a' or 'B'. Char values are surrounded by single quotes</xhtml:li><xhtml:li>boolean - stores values with two states: true or false</xhtml:li><xhtml:li diff:insert="">Last new value</xhtml:li></xhtml:ul><xhtml:div>That will be the whole list.</xhtml:div></xhtml:div></xml>"""
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_en_right)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], None)
        # Metadata comparison
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res_metadata = self.client.get(url).json
        meta_rows = list(res_metadata)
        self.assertGreaterEqual(len(meta_rows), 24)
        # Check category field
        meta_column_map_cat = sorted(list(res_metadata['mapped_category']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_map_cat, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['mapped_category']['right'], 'Anforderung')
        self.assertEqual(res_metadata['mapped_category']['label'], 'Kategorie')
        # Check current value field
        meta_column_act_val = sorted(list(res_metadata['act_value']))
        expected_columns = sorted(['right', 'label'])
        self.assertEqual(meta_column_act_val, expected_columns)
        # Check if the values are what we expect
        self.assertEqual(res_metadata['act_value']['right'], None)
        self.assertEqual(res_metadata['act_value']['label'], 'Erfüllungsgrad [%]')
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_deleted(self):
        """Tests querying a deleted requirement"""
        # Requirement: RT000000084
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab4e-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = 'null'
        languages = 'de,en'
        # Check rich text api
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        # Check for expected rich text values
        expected_single_object = 'single_object'
        expected_richtext_de_single = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>Diese Anforderung wird gelöscht</xhtml:div></xml>'
        expected_richtext_en_single = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>This requirement will be deleted</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_single_object)
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_single_object)
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_richtext_de_single)
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_single_object)
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_single_object)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], expected_richtext_en_single)
        # Check metadata api
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        self.assertGreaterEqual(len(res_rows), 24)
        # Classification diff comparison
        url = '/internal/%s/classification/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['case', 'classification_is_equal', 'assigned_classes_left', 'assigned_classes_right', 'assigned_classes', 'properties', 'metadata'])
        self.assertEqual(res_rows, expected_keys_dict)
        api_class_expected_diff = False
        self.assertEqual(res['classification_is_equal'], api_class_expected_diff)
        expected_assigned = []
        self.assertEqual(res['assigned_classes'], expected_assigned)
        expected_assigned_left = ['RQM_RATING']
        self.assertEqual(res['assigned_classes_left'], expected_assigned_left)
        expected_assigned_right = []
        self.assertEqual(res['assigned_classes_right'], expected_assigned_right)
        # Check that the contens of properties is the change in date of the calculated rating
        expected_properties = sorted(['RQM_RATING_RQM_RATING_MDATE', 'RQM_RATING_RQM_RATING_CALCULATED'])
        self.assertEqual(sorted(list(res['properties'])), expected_properties)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_file_changes(self):
        """Tests changing files contained in a requirement"""
        # Requirement: RT000000085
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab66-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad386-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there is a diff
        self.assertEqual(res['changedFiles'], True)
        # Confirm the result has tree files
        expected_files = sorted(['emu2.jpg', 'emu3.jpg', 'emu1.jpg'])
        self.assertEqual(sorted(list(res["files"])), expected_files)
        # Confirm status of each file
        self.assertEqual(res["files"]['emu1.jpg']['status'], 'diff')
        self.assertEqual(res["files"]['emu2.jpg']['status'], 'same')
        self.assertEqual(res["files"]['emu3.jpg']['status'], 'new')
        # Confirm routes for each file # Probably wont work? 
        f1_expected_A = '/api/v1/collection/spec_object/c259ab66-8190-11eb-b0ca-34e12d2f8428/files/c259abd4-8190-11eb-b0ca-34e12d2f8428'
        f1_expected_B = '/api/v1/collection/spec_object/861ad386-8190-11eb-b0ca-34e12d2f8428/files/765a68fd-8194-11eb-b0ca-34e12d2f8428'
        self.assertEqual(res["files"]['emu1.jpg']['url_A'].endswith(f1_expected_A), True)
        self.assertEqual(res["files"]['emu1.jpg']['url_B'].endswith(f1_expected_B), True)
        f2_expected_A = '/api/v1/collection/spec_object/c259ab66-8190-11eb-b0ca-34e12d2f8428/files/c259abd5-8190-11eb-b0ca-34e12d2f8428'
        f2_expected_B = '/api/v1/collection/spec_object/861ad386-8190-11eb-b0ca-34e12d2f8428/files/861ad402-8190-11eb-b0ca-34e12d2f8428'
        self.assertEqual(res["files"]['emu2.jpg']['url_A'].endswith(f2_expected_A), True)
        self.assertEqual(res["files"]['emu2.jpg']['url_B'].endswith(f2_expected_B), True)
        f3_expected_A = ''
        f3_expected_B = '/api/v1/collection/spec_object/861ad386-8190-11eb-b0ca-34e12d2f8428/files/7d3054b9-8194-11eb-b0ca-34e12d2f8428'
        self.assertEqual(res["files"]['emu3.jpg']['url_A'].endswith(f3_expected_A), True)
        self.assertEqual(res["files"]['emu3.jpg']['url_B'].endswith(f3_expected_B), True)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_add_classification_class(self):
        """Tests adding a classification class to a requirement"""
        # Requirement: RT000000086
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab5b-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad382-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Classification diff comparison
        url = '/internal/%s/classification/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['classification_is_equal', 'assigned_classes_left', 'assigned_classes_right', 'assigned_classes', 'properties', 'metadata'])
        self.assertEqual(res_rows, expected_keys_dict)
        api_class_expected_diff = False
        self.assertEqual(res['classification_is_equal'], api_class_expected_diff)
        expected_assigned_left = []
        self.assertEqual(res['assigned_classes_left'], expected_assigned_left)
        expected_assigned_right = ['RQM_TEST01']
        self.assertEqual(res['assigned_classes_right'], expected_assigned_right)
        #Check some properties in the new right side class
        expected_test_int_einwertig_left = None
        self.assertEqual(res['properties']['RQM_TEST01_test_int_einwertig'][0]['value_left'], expected_test_int_einwertig_left)
        expected_test_int_einwertig_right = 14782
        self.assertEqual(res['properties']['RQM_TEST01_test_int_einwertig'][0]['value_right'], expected_test_int_einwertig_right)
        expected_test_text_einwertig_left = None
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig'][0]['value_left'], expected_test_text_einwertig_left)
        expected_test_text_einwertig_right = 'This value belongs to the new class'
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig'][0]['value_right'], expected_test_text_einwertig_right)
        expected_text_einwertig_enum_left = None
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value_left'], expected_text_einwertig_enum_left)
        expected_text_einwertig_enum_right = 'test1'
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value_right'], expected_text_einwertig_enum_right)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_delete_classification_class(self):
        """Tests deleting a classification class from a requirement"""
        # Requirement: RT000000087
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab77-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad37e-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Classificaation diff comparison
        url = '/internal/%s/classification/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['classification_is_equal', 'assigned_classes_left', 'assigned_classes_right', 'assigned_classes', 'properties', 'metadata'])
        self.assertEqual(res_rows, expected_keys_dict)
        api_class_expected_diff = False
        self.assertEqual(res['classification_is_equal'], api_class_expected_diff)
        # Check that the deleted classification class appears only on the left side
        expected_assigned_left = ['RQM_TEST01']
        self.assertEqual(res['assigned_classes_left'], expected_assigned_left)
        # Check that none was added
        expected_assigned_right = []
        self.assertEqual(res['assigned_classes_right'], expected_assigned_right)
        # Check some properties of the deleted class
        expected_test_text_einwertig_left = 'Text to fill the class'
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig'][0]['value_left'], expected_test_text_einwertig_left)
        expected_test_text_einwertig_right = None
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig'][0]['value_right'], expected_test_text_einwertig_right)
        expected_test_text_einwertig_enum_left = 'test1'
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value_left'], expected_test_text_einwertig_enum_left)
        expected_test_text_einwertig_enum_right = None
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value_right'], expected_test_text_einwertig_enum_right)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_modify_one_classification_class(self):
        """Tests modifying one of two classification classes of a requirement"""
        # Requirement: RT000000088
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab69-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad37d-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Classification diff comparison
        url = '/internal/%s/classification/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['classification_is_equal', 'assigned_classes_left', 'assigned_classes_right', 'assigned_classes', 'properties', 'metadata'])
        self.assertEqual(res_rows, expected_keys_dict)
        api_class_expected_diff = False
        self.assertEqual(res['classification_is_equal'], api_class_expected_diff)
        # Check that both classes appear in the object
        expected_assigned = sorted(['RQM_RATING', 'RQM_TEST01'])
        self.assertEqual(sorted(res['assigned_classes']), expected_assigned)
        # Check that no classes appear in just one side
        expected_assigned_left = []
        self.assertEqual(res['assigned_classes_left'], expected_assigned_left)
        expected_assigned_right = []
        self.assertEqual(res['assigned_classes_right'], expected_assigned_right)
        # Check some properties of the class that changed
        # External comment
        expected_comment_extern_left = 'External coment for an accepted rating'
        expected_comment_extern_right = 'External coment for a partially accepted rating'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_EXTERN'][0]['value_left'], expected_comment_extern_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_EXTERN'][0]['value_right'], expected_comment_extern_right)
        # Internal comment
        expected_comment_intern_left = 'Internal comment for an accepted rating'
        expected_comment_intern_right = 'Internal comment for a partially accepted rating'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_INTERN'][0]['value_left'], expected_comment_intern_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_COMMENT_INTERN'][0]['value_right'], expected_comment_intern_right)
        # Check rating german
        expected_rating_de_left = 'akzeptiert'
        expected_rating_de_right = 'teilweise akzeptiert'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]['value_left']['de']['text_value'], expected_rating_de_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]['value_right']['de']['text_value'], expected_rating_de_right)
        # Check rating english
        expected_rating_en_left = 'accepted'
        expected_rating_en_right = 'partially accepted'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]['value_left']['en']['text_value'], expected_rating_en_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][0]['value']['child_props']['RQM_RATING_VALUE'][0]['value_right']['en']['text_value'], expected_rating_en_right)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_req_modify_all_classification_classes(self):
        """Tests modifying both classification classes of a requirement"""
        # Requirement: RT000000089
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab57-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad380-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Classification diff comparison
        url = '/internal/%s/classification/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['classification_is_equal', 'assigned_classes_left', 'assigned_classes_right', 'assigned_classes', 'properties', 'metadata'])
        self.assertEqual(res_rows, expected_keys_dict)
        api_class_expected_diff = False
        self.assertEqual(res['classification_is_equal'], api_class_expected_diff)
        # Check that both classes appear in the object
        expected_assigned = sorted(['RQM_RATING', 'RQM_TEST01'])
        self.assertEqual(sorted(res['assigned_classes']), expected_assigned)
        # Check that no classes appear in just one side
        expected_assigned_left = []
        self.assertEqual(res['assigned_classes_left'], expected_assigned_left)
        expected_assigned_right = []
        self.assertEqual(res['assigned_classes_right'], expected_assigned_right)
        # Check some properties of RQM_RATING
        # Overall rating de
        expected_rating_de_left = 'nicht akzeptiert'
        expected_rating_de_right = 'teilweise akzeptiert'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value_left']['de']['text_value'], expected_rating_de_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value_right']['de']['text_value'], expected_rating_de_right)
        # Overall rating en
        expected_rating_en_left = 'not accepted'
        expected_rating_en_right = 'partially accepted'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value_left']['en']['text_value'], expected_rating_en_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value_right']['en']['text_value'], expected_rating_en_right)
        # Check updated rating german
        expected_upd_rating_de_left = 'teilweise akzeptiert'
        expected_upd_rating_de_right = 'nicht relevant'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][1]['value']['child_props']['RQM_RATING_VALUE'][0]['value_left']['de']['text_value'], expected_upd_rating_de_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][1]['value']['child_props']['RQM_RATING_VALUE'][0]['value_right']['de']['text_value'], expected_upd_rating_de_right)
        # Check updated rating english
        expected_upd_rating_en_left = 'partially accepted'
        expected_upd_rating_en_right = 'not relevant'
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][1]['value']['child_props']['RQM_RATING_VALUE'][0]['value_left']['en']['text_value'], expected_upd_rating_en_left)
        self.assertEqual(res['properties']['RQM_RATING_RQM_RATING'][1]['value']['child_props']['RQM_RATING_VALUE'][0]['value_right']['en']['text_value'], expected_upd_rating_en_right)
        # Check some properties of RQM_TEST
        expected_test_int_einwerting_left = 6543
        expected_test_int_einwerting_right = 8526
        self.assertEqual(res['properties']['RQM_TEST01_test_int_einwertig'][0]['value_left'], expected_test_int_einwerting_left)
        self.assertEqual(res['properties']['RQM_TEST01_test_int_einwertig'][0]['value_right'], expected_test_int_einwerting_right)
        expected_test_int_einwerting_enum_left = 1
        expected_test_int_einwerting_enum_right = 2
        self.assertEqual(res['properties']['RQM_TEST01_test_int_einwertig_enum'][0]['value_left'], expected_test_int_einwerting_enum_left)
        self.assertEqual(res['properties']['RQM_TEST01_test_int_einwertig_enum'][0]['value_right'], expected_test_int_einwerting_enum_right)
        expected_test_text_einwerting_left = 'This text will be updated'
        expected_test_text_einwerting_right = 'This text has been updated'
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig'][0]['value_left'], expected_test_text_einwerting_left)
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig'][0]['value_right'], expected_test_text_einwerting_right)
        expected_test_text_einwerting_enum_left = 'test1'
        expected_test_text_einwerting_enum_right = 'test2'
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value_left'], expected_test_text_einwerting_enum_left)
        self.assertEqual(res['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value_right'], expected_test_text_einwerting_enum_right)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)

    def test_acceptance_criteria(self):
        """Tests modifying both classification classes of a requirement"""
        # Requirement: RT000000090
        # Baseline: Baseline all cases
        left_cdb_object_id = 'c259ab76-8190-11eb-b0ca-34e12d2f8428'
        right_cdb_object_id = '861ad381-8190-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there is a diff
        self.assertEqual(res['changedAC'], True)
        # Object ids from the acceptance criteria
        ac_diff = 'affe892d-8185-11eb-b0ca-34e12d2f8428'
        ac_same_1 = 'affe8959-8185-11eb-b0ca-34e12d2f8428'
        ac_same_2 = 'bde4926f-8185-11eb-b0ca-34e12d2f8428'
        ac_del = 'bde492aa-8185-11eb-b0ca-34e12d2f8428'
        # Check the status of each ac
        expected_status_diff = "diff"
        expected_status_same = "same"
        expected_status_del = 'del'
        self.assertEqual(res['target_values'][ac_diff]['status'], expected_status_diff)
        self.assertEqual(res['target_values'][ac_same_1]['status'], expected_status_same)
        self.assertEqual(res['target_values'][ac_same_2]['status'], expected_status_same)
        self.assertEqual(res['target_values'][ac_del]['status'], expected_status_del)
        # Check the description of each ac and their sides
        expected_desc_diff_left = 'This acceptance criteria will be edited: (AT0000014) ( %)'
        expected_desc_diff_right = '[Baseline all cases] This acceptance criteria will be edited: (AT0000014) ( %)'
        self.assertEqual(res['target_values'][ac_diff]['desc_l'], expected_desc_diff_left)
        self.assertEqual(res['target_values'][ac_diff]['desc_r'], expected_desc_diff_right)
        expected_desc_same_1_left = 'This acceptance criteria will not be edited (AT0000015) ( %)'
        expected_desc_same_1_right = '[Baseline all cases] This acceptance criteria will not be edited (AT0000015) ( %)'
        self.assertEqual(res['target_values'][ac_same_1]['desc_l'], expected_desc_same_1_left)
        self.assertEqual(res['target_values'][ac_same_1]['desc_r'], expected_desc_same_1_right)
        expected_desc_same_2_left = 'This acceptance criteria has a classification class change (AT0000016) ( %)'
        expected_desc_same_2_right = '[Baseline all cases] This acceptance criteria has a classification class change (AT0000016) ( %)'
        self.assertEqual(res['target_values'][ac_same_2]['desc_l'], expected_desc_same_2_left)
        self.assertEqual(res['target_values'][ac_same_2]['desc_r'], expected_desc_same_2_right)
        expected_desc_del = '[Baseline all cases] This acceptance criteria will be deleted (AT0000017) ( %)'
        self.assertEqual(res['target_values'][ac_del]['desc'], expected_desc_del)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)

    def test_req_new(self):
        """Tests querying a deleted requirement"""
        # Requirement: RT000000104
        # Baseline: Baseline all cases
        left_cdb_object_id = 'null'
        right_cdb_object_id = '70d918e3-819e-11eb-b0ca-34e12d2f8428'
        languages = 'de,en'
        # Check rich text api
        url = '/internal/%s/richtext/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_languages = list(res)
        # Structure check
        self.assertEqual(res_languages[0], 'diff_dict')
        self.assertEqual(set(list(res['diff_dict'])), set(['de', 'en']))
        self.assertEqual(set(list(res['diff_dict']['de'])), set(['xhtml_left', 'xhtml_single', 'xhtml_right']))
        # Check for expected rich text values
        expected_single_object = 'single_object'
        expected_richtext_de_single = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>Neue Anforderung</xhtml:div></xml>'
        expected_richtext_en_single = '<xml xmlns:xhtml="http://www.w3.org/1999/xhtml"><xhtml:div>Requirement added</xhtml:div></xml>'
        self.assertEqual(res['diff_dict']['de']['xhtml_left'], expected_single_object)
        self.assertEqual(res['diff_dict']['de']['xhtml_right'], expected_single_object)
        self.assertEqual(res['diff_dict']['de']['xhtml_single'], expected_richtext_de_single)
        self.assertEqual(res['diff_dict']['en']['xhtml_left'], expected_single_object)
        self.assertEqual(res['diff_dict']['en']['xhtml_right'], expected_single_object)
        self.assertEqual(res['diff_dict']['en']['xhtml_single'], expected_richtext_en_single)
        # Check metadata api
        url = '/internal/%s/metadata/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = list(res)
        self.assertGreaterEqual(len(res_rows), 24)
        # Classification diff comparison
        url = '/internal/%s/classification/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['case', 'classification_is_equal', 'assigned_classes_left', 'assigned_classes_right', 'assigned_classes', 'properties', 'metadata'])
        self.assertEqual(res_rows, expected_keys_dict)
        api_class_expected_diff = False
        self.assertEqual(res['classification_is_equal'], api_class_expected_diff)
        expected_assigned = []
        self.assertEqual(res['assigned_classes'], expected_assigned)
        expected_assigned_left = []
        self.assertEqual(res['assigned_classes_left'], expected_assigned_left)
        expected_assigned_right = ['RQM_RATING']
        self.assertEqual(res['assigned_classes_right'], expected_assigned_right)
        # Check that the contens of properties is the change in date of the calculated rating
        expected_properties = sorted(['RQM_RATING_RQM_RATING_MDATE', 'RQM_RATING_RQM_RATING_CALCULATED'])
        self.assertEqual(sorted(list(res['properties'])), expected_properties)
        # File diff comparison
        url = '/internal/%s/file/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['files', 'changedFiles'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedFiles'], False)
        # AC diff comparison
        url = '/internal/%s/acceptancecriterion/%s/%s/?languages=%s' % (API_MOUNT_PATH, left_cdb_object_id, right_cdb_object_id, languages)
        res = self.client.get(url).json
        res_rows = sorted(list(res))
        expected_keys_dict = sorted(['changedAC', 'target_values'])
        self.assertEqual(res_rows, expected_keys_dict)
        # Confirm there isnt a diff
        self.assertEqual(res['changedAC'], False)
