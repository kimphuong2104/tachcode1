# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function, unicode_literals

import datetime
import logging

from cdb import ElementsError, sqlapi, util
from cdb.objects import operations
from cdb.testcase import error_logging_disabled, without_error_logging
from cs.classification import api as classification_api
from cs.classification import prepare_read
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue

from .utils import RequirementsTestCase

LOG = logging.getLogger(__name__)


class TestBaselining(RequirementsTestCase):
    maxDiff = None

    def __init__(self, *args, **kwargs):
        super(TestBaselining, self).__init__(*args, need_uberserver=True,
                                             **kwargs)

    def setUp(self):
        RequirementsTestCase.setUp(self)
        prepare_read(RQMSpecObject.__classname__)
        self.base_spec = RQMSpecification.ByKeys(spec_id='ST000000017')
        new_classification = classification_api.get_new_classification(["RQM_TEST01"])
        new_classification['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
            {
                'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                'property_type': u'datetime',
                'value': datetime.datetime(2018, 2, 23, 0, 0)
            }
        )
        classification_api.update_classification(
            self.base_spec, new_classification, check_access=False
        )
        classification_api.update_classification(
            self.base_spec.Requirements[0], new_classification, check_access=False
        )
        classification_api.update_classification(
            self.base_spec.TargetValues[0], new_classification, check_access=False
        )
        self.base_spec.SetText('cdbrqm_specification_txt', 'this is a test')

    def _compare_classification(self, left, right):
        compare_data = classification_api.compare_classification(
            left.cdb_object_id,
            right.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertTrue(compare_data.get('classification_is_equal', False))

    def _compare_doc_refs(self, left, right):
        if hasattr(left, 'Documents'):
            self.assertEqual(
                [d.cdb_object_id for d in left.Documents],
                [d.cdb_object_id for d in right.Documents]
            )

    def _compare_semantic_links(self, left, right):
        if hasattr(left, 'SemanticLinks'):
            self.assertEqual(
                [sl.Object.GetDescription() for sl in left.SemanticLinks],
                [sl.Object.GetDescription() for sl in right.SemanticLinks],
            )

    def _compare_long_texts(self, left, right):
        for name in left.GetTextFieldNames():
            left_text = left.GetText(name)
            right_text = right.GetText(name)
            self.assertEqual(left_text, right_text)

    def _compare_files(self, left, right):
        if hasattr(left, 'Files'):
            self.assertEqual(
                [f.cdbf_blob_id for f in left.Files],
                [f.cdbf_blob_id for f in right.Files]
            )

    def _compare_attributes(self, left, right, filter_out_list):
        for attr in left.GetFieldNames():
            if attr not in filter_out_list:
                if attr not in left.GetTextFieldNames():
                    self.assertEqual(
                        getattr(left, attr), getattr(right, attr),
                        'different value for %s: %s != %s' % (
                            attr, getattr(left, attr), getattr(right, attr)))
                else:
                    self.assertEqual(
                        left.GetText(attr), right.GetText(attr),
                        'different value for %s: %s != %s' % (
                            attr, left.GetText(attr), right.GetText(attr)))

    def _compare(self, left_objs, right_objs):
        # base assumption we have stable sorted lists
        filter_out_list = util.PersonalSettings().getValueOrDefault(
            "cs.requirements.diff",
            "attribute_filter_out_list",
            u"cdb_cdate, reqif_id, cdb_mdate, cdb_object_id, ce_baseline_id, ce_baseline_cdate, specification_object_id, template_oid, ce_baseline_name, ce_baseline_creator, ce_baseline_comment, ce_baseline_origin_id, parent_object_id, ce_baseline_object_id, subject_type, position, sortorder, maxno,ce_baseline_info_tag"
        )
        filter_out_list += ',requirement_object_id'  # due to the fact that target values are not yet considered correctly
        i = 0
        try:
            for left in left_objs:
                right = right_objs[i]
                self._compare_attributes(left, right, filter_out_list)
                self._compare_doc_refs(left, right)
                self._compare_files(left, right)
                self._compare_classification(left, right)
                self._compare_long_texts(left, right)
                i += 1
        except IndexError as e:
            self.assertTrue(False, 'Missing requirement: %s (%s)' % (left, e))

    def _create_and_check_baseline(self, base_spec, initial_baseline_cnt=0):
        next_baseline_cnt = initial_baseline_cnt + 1
        baseline_name = 'Test Baseline %s' % (next_baseline_cnt)
        baseline_comment = 'Test Baseline Comment %s' % (next_baseline_cnt)
        self.assertEqual(
            len(base_spec.Baselines), initial_baseline_cnt,
            'precondition failed, %s has different count of baselines then expected: %s != %s' % (
                base_spec.GetDescription(), initial_baseline_cnt,
                len(base_spec.Baselines)
            )
        )
        baselined_spec = operations.operation(
            "ce_baseline_create",
            base_spec,
            ce_baseline_name=baseline_name,
            ce_baseline_comment=baseline_comment)
        baseline_obj = baselined_spec.BaselineDetails
        self.assertNotEqual(base_spec.cdb_object_id, baselined_spec.cdb_object_id)
        self.assertEqual(baseline_obj.ce_baseline_name, baseline_name)
        self.assertEqual(baselined_spec.ce_baseline_name, baseline_name)
        self.assertEqual(baseline_obj.ce_baseline_comment, baseline_comment)
        self.assertEqual(baselined_spec.ce_baseline_comment, baseline_comment)
        base_spec.Reload()
        self.assertEqual(len(base_spec.Baselines), next_baseline_cnt)
        self.assertIn(
            baselined_spec, base_spec.Baselines)
        self._compare([base_spec], [baselined_spec])
        self._compare(
            base_spec.Requirements.Query("1=1", order_by='sortorder'),
            baselined_spec.Requirements.Query("1=1", order_by='sortorder')
        )
        self._compare(
            base_spec.TargetValues.Query("1=1", order_by='pos'),
            baselined_spec.TargetValues.Query("1=1", order_by='pos')
        )
        # create baseline of base_spec and test whether:
        # + it has a baseline using python reference
        # + the baseline contains all elements of base_spec and sub elements
        # + the baseline has all attribute values of base_spec and sub elements
        # + the baseline has all long text alues of base_spec and sub elements
        # + the baseline has all doc references of base_spec and sub elements
        # - the baseline has all semantic links of base_spec and sub elements
        # + the baseline has all classification of base_spec and sub elements
        # + the baseline has all file attachments of base_spec and sub elements
        # change base_spec and test whether:
        # baselined elements stay unchanged
        # change should be based on all aspects (attributes+, reqs+, tvs+, kpis,
        # doc refs, semLinks, classification, file attachments
        return baselined_spec

    def _test_changes_against_current_and_check_baselines(
            self, base_spec, baselined_specs, reqs_count, tvs_count
    ):
        # requirement description text change

        old_text = base_spec.TopRequirements[0].SubRequirements[0].GetText(
            'cdbrqm_spec_object_desc_en'
        )
        base_spec.TopRequirements[0].SubRequirements[0].SetText(
            'cdbrqm_spec_object_desc_en', 'New text')

        for baselined_spec in baselined_specs:
            self.assertEqual(
                baselined_spec.TopRequirements[0].SubRequirements[0].GetText(
                    'cdbrqm_spec_object_desc_en'
                ),
                old_text
            )
            self.assertNotEqual(
                base_spec.TopRequirements[0].SubRequirements[0].GetText(
                    'cdbrqm_spec_object_desc_en'
                ),
                baselined_spec.TopRequirements[0].SubRequirements[0].GetText(
                    'cdbrqm_spec_object_desc_en'
                )
            )

        # target value description text change

        old_text = base_spec.TopRequirements[0].SubRequirements[1].TargetValues[0].GetText(
            'cdbrqm_target_value_desc_en'
        )
        base_spec.TopRequirements[0].SubRequirements[1].TargetValues[0].SetText(
            'cdbrqm_target_value_desc_en', 'New text'
        )
        for baselined_spec in baselined_specs:
            self.assertEqual(
                baselined_spec.TopRequirements[0].SubRequirements[1].TargetValues[0].GetText(
                    'cdbrqm_target_value_desc_en'
                ),
                old_text
            )
            self.assertNotEqual(
                base_spec.TopRequirements[0].SubRequirements[1].TargetValues[0].GetText(
                    'cdbrqm_target_value_desc_en'
                ),
                baselined_spec.TopRequirements[0].SubRequirements[1].TargetValues[0].GetText(
                    'cdbrqm_target_value_desc_en'
                )
            )

        # requirements & target value deletion
        ids = base_spec.Requirements.cdb_object_id + base_spec.TargetValues.cdb_object_id
        base_spec._delete_elements_by_ids(ids)
        base_spec.Reload()
        self.assertEqual(len(base_spec.Requirements), 0)
        self.assertEqual(len(base_spec.TargetValues), 0)
        for baselined_spec in baselined_specs:
            self.assertEqual(len(baselined_spec.Requirements), reqs_count)
            self.assertEqual(len(baselined_spec.TargetValues), tvs_count)

    def test_create_baseline(self):
        reqs_count = len(self.base_spec.Requirements)
        tvs_count = len(self.base_spec.TargetValues)
        baselined_spec = self._create_and_check_baseline(self.base_spec)
        self._test_changes_against_current_and_check_baselines(
            self.base_spec, [baselined_spec], reqs_count, tvs_count
        )

    def _create_revision(self):
        self.base_spec.Reload()
        self.base_spec.ChangeState(RQMSpecification.REVIEW, check_access=0)
        self.base_spec.ChangeState(RQMSpecification.RELEASED, check_access=0)
        operations.operation("cdbrqm_new_revision", self.base_spec)
        self.base_spec.Reload()
        indexed_base_spec = self.base_spec.OtherVersions[0]
        self.assertNotEqual(
            indexed_base_spec.ce_baseline_object_id, self.base_spec.ce_baseline_object_id,
            'Index operation fails to reset ce_baseline_object_id on specification'
        )
        self.assertEqual(
            indexed_base_spec.ce_baseline_object_id, indexed_base_spec.cdb_object_id,
            'Index operation fails to reset ce_baseline_object_id on specification'
        )
        return indexed_base_spec

    def test_create_baseline_on_new_index(self):
        # create index of base_spec
        # create baseline of new index of base_spec and test whether:
        # same conditions as for normal baseline creations are true +
        # the new index of base_spec then have two baselines when using the
        # python reference for baselines accross index versions and one
        # baseline inside the index version
        reqs_count = len(self.base_spec.Requirements)
        tvs_count = len(self.base_spec.TargetValues)
        baselined_spec = self._create_and_check_baseline(self.base_spec)
        indexed_base_spec = self._create_revision()
        baselined_spec2 = self._create_and_check_baseline(indexed_base_spec)
        self._test_changes_against_current_and_check_baselines(
            self.base_spec, [baselined_spec, baselined_spec2], reqs_count, tvs_count
        )
        self.assertEqual(len(self.base_spec.Baselines), 1)
        all_versions_cnt = len(self.base_spec.AllVersions)
        self.assertEqual(all_versions_cnt, 3, "%s != %s (%s)" % (all_versions_cnt, 3, [
            (s.BaselineDetails.ce_baseline_name if s.BaselineDetails else s.GetDescription()) for s in self.base_spec.AllVersions
        ]))
        all_versions_cnt = len(indexed_base_spec.AllVersions)
        self.assertEqual(all_versions_cnt, 3, "%s != %s (%s)" % (all_versions_cnt, 3, [
            (s.BaselineDetails.ce_baseline_name if s.BaselineDetails else s.GetDescription()) for s in self.base_spec.AllVersions
        ]))
        self.assertEqual(len(self.base_spec.AllVersionsInIndex), 1, [
            (s.BaselineDetails.ce_baseline_name if s.BaselineDetails else s.GetDescription()) for s in self.base_spec.AllVersionsInIndex
        ])
        self.assertEqual(len(indexed_base_spec.AllVersionsInIndex), 1, [
            (s.BaselineDetails.ce_baseline_name if s.BaselineDetails else s.GetDescription()) for s in indexed_base_spec.AllVersionsInIndex
        ])

    def test_create_baseline_from_old_revision(self):
        # create revision, try to create baseline from old revision -> should fail
        self._create_revision()
        with self.assertRaises(ElementsError):
            self._create_and_check_baseline(self.base_spec)

    def test_create_baseline_from_baseline(self):
        # create baseline, try to create baseline from baseline -> should fail
        baselined_spec = self._create_and_check_baseline(self.base_spec)
        with self.assertRaises(ElementsError):
            self._create_and_check_baseline(baselined_spec)

    def test_restore_baseline(self):
        # same as create_baseline +
        # change something and test that it is different now compared to it's baseline before
        # restore baseline and test whether
        # everything is the same as before (current state == first baseline state)
        # test whether the modification was saved in another baseline
        reqs_count = len(self.base_spec.Requirements)
        tvs_count = len(self.base_spec.TargetValues)
        baselined_spec = self._create_and_check_baseline(self.base_spec)
        self._test_changes_against_current_and_check_baselines(
            self.base_spec, [baselined_spec], reqs_count, tvs_count
        )
        self.assertEqual(len(self.base_spec.Requirements), 0)
        self.assertEqual(len(self.base_spec.TargetValues), 0)
        new_current_spec = operations.operation(
            "ce_baseline_restore",
            baselined_spec
        )
        new_current_spec.Reload()
        self.assertEqual(len(new_current_spec.Requirements), reqs_count)
        self.assertEqual(len(new_current_spec.TargetValues), tvs_count)
        # we expect the first baseline + a baseline of the current state before restore op
        self.assertEqual(len(new_current_spec.Baselines), 2)

    def test_restore_baseline_from_old_revision(self):
        # create baseline, index spec, try to restore baseline -> should fail
        baselined_spec = self._create_and_check_baseline(self.base_spec)
        self._create_revision()
        with self.assertRaises(ElementsError):
            operations.operation(
                "ce_baseline_restore",
                baselined_spec
            )

    def test_restore_of_non_baseline(self):
        # invoke restore operation of current state -> should fail
        with self.assertRaises(ElementsError):
            operations.operation(
                "ce_baseline_restore",
                self.base_spec
            )
