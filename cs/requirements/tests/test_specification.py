# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import json
import logging
import os
import sys

from cdb.objects import operations
from cdb.objects.cdb_file import CDB_File
from cdb.validationkit.op import operation as interactive_operation
from cs.classification import api as classification_api
from cs.classification.rest.utils import ensure_json_serialiability
from cs.requirements import RQMSpecification, RQMSpecObject, rqm_utils
from cs.tools.semanticlinks import SemanticLink, SemanticLinkType

from .utils import RequirementsTestCase

LOG = logging.getLogger(__name__)


class TestSpecification(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpecification, self).__init__(*args, **kwargs)
        self.maxDiff = None

    @classmethod
    def make_spec_to_template_spec(cls, spec):
        spec.fulfillment_kpi_active = 0
        spec_fulfillment_kpi = rqm_utils.getFulfillmentQC(spec)
        if spec_fulfillment_kpi:
            spec_fulfillment_kpi.Delete()
        for r in spec.Requirements:
            r.fulfillment_kpi_active = 0
            r_fulfillment_kpi = rqm_utils.getFulfillmentQC(r)
            if r_fulfillment_kpi:
                r_fulfillment_kpi.Delete()
        for t in spec.TargetValues:
            t.fulfillment_kpi_active = 0
            t_fulfillment_kpi = rqm_utils.getFulfillmentQC(t)
            if t_fulfillment_kpi:
                t_fulfillment_kpi.Delete()
        spec.is_template = 1
        spec.Reload()

    def test_create_from_template_kpi_usable(self):
        """ Check if cdbrqm_create_from_template using a specification template returns a kpi usable spec"""
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        self.make_spec_to_template_spec(spec)
        # instantiate from template
        spec_instance = interactive_operation(
            "CDB_Copy", spec, user_input=None, preset={'is_template': 0})
        spec_instance.Reload()
        # it is expectet that newly created by not evaluated elements have no evaluation
        # see E061284 for details.
        self.assertEqual(spec_instance.act_value, None)
        # set at least one fulfillment value to see whether the aggregation works
        first_leaf = [r for r in spec_instance.Requirements if not r.is_group][0]
        first_leaf.set_act_value(0.0)
        spec_instance.Reload()
        self.assertEqual(spec_instance.act_value, 0.0)
        self.assertEqual(spec_instance.fulfillment_kpi_active, 1)
        self.assertNotEqual(rqm_utils.getFulfillmentQC(spec_instance), None,
                            "missing fulfillment kpi for %s" % spec_instance)
        for r in spec_instance.Requirements:
            self.assertEqual(r.fulfillment_kpi_active, 1)
            self.assertNotEqual(rqm_utils.getFulfillmentQC(r), None,
                                "missing fulfillment kpi for %s" % r)
            if not r.is_group:
                r.set_act_value(100.0)
        for t in spec_instance.TargetValues:
            self.assertEqual(t.fulfillment_kpi_active, 1)
            self.assertNotEqual(rqm_utils.getFulfillmentQC(t), None,
                                "missing fulfillment kpi for %s" % t)
            t.set_act_value(100.0)
        spec_instance.Reload()
        self.assertEqual(spec_instance.act_value, 100.0)

    def test_copy_specification(self):
        """ (R000002812) Check if CDB_Copy on a specification returns an intact structure as a new specfication
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        test_file = os.path.join(os.path.dirname(__file__), '01_notExcelDoc.png')
        CDB_File.NewFromFile(for_object_id=spec.cdb_object_id, from_path=test_file, primary=1)
        self.assertEqual(len(spec.Files), 1)
        old_reqif_ids = set([spec.reqif_id] + [x.reqif_id for x in spec.Requirements + spec.TargetValues])
        old_human_readable_ids = set([spec.spec_id] + [r.specobject_id for r in spec.Requirements] + [t.targetvalue_id for t in spec.TargetValues])
        interactive_operation("cdbrqm_update_sortorder", spec)
        result = interactive_operation("CDB_Copy", spec, user_input=None, preset=None)

        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"anf3"]
        valid_target_values = {u"anf3": u"ziel1", u"anf1-2": u"ziel2"}
        requirements = RQMSpecObject.KeywordQuery(specification_object_id=result.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
            self.assertEqual(specobj.Specification.status, 0)
            self.assertIsNone(specobj.act_value)
            if specobj.name_de in valid_target_values:
                self.assertEqual(specobj.TargetValues[0].name_de, valid_target_values[specobj.name_de])
                self.assertIsNone(specobj.TargetValues[0].act_value)
        new_reqif_ids = set([result.reqif_id] + [x.reqif_id for x in result.Requirements + result.TargetValues])
        self.assertFalse(old_reqif_ids.intersection(new_reqif_ids), 'Not all reqif_ids were resetted')
        new_human_readable_ids = set([result.spec_id] + [r.specobject_id for r in result.Requirements] + [t.targetvalue_id for t in result.TargetValues])
        self.assertFalse(old_human_readable_ids.intersection(new_human_readable_ids), 'Not all human readable ids (spec_id, specobject_id, targetvalue_id) were resetted')
        self.assertEqual(len(result.Files), 1)

    def test_copy_specification_without_target_values(self):
        """ (R000002812) Check if CDB_Copy without target values on a specification returns an intact structure as a new specfication
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        old_reqif_ids = set([spec.reqif_id] + [x.reqif_id for x in spec.Requirements + spec.TargetValues])
        old_human_readable_ids = set([spec.spec_id] + [r.specobject_id for r in spec.Requirements] + [t.targetvalue_id for t in spec.TargetValues])
        interactive_operation("cdbrqm_update_sortorder", spec)
        result = interactive_operation("CDB_Copy", spec, user_input={"copy_target_values": "0"}, preset=None)

        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"anf3"]
        valid_target_values = {u"anf3": u"ziel1", u"anf1-2": u"ziel2"}
        requirements = RQMSpecObject.KeywordQuery(specification_object_id=result.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
            self.assertEqual(specobj.Specification.status, 0)
            self.assertIsNone(specobj.act_value)
            if specobj.name_de in valid_target_values:
                self.assertTrue(specobj.TargetValues == [])
        new_reqif_ids = set([result.reqif_id] + [x.reqif_id for x in result.Requirements + result.TargetValues])
        self.assertFalse(old_reqif_ids.intersection(new_reqif_ids), 'Not all reqif_ids were resetted')
        new_human_readable_ids = set([result.spec_id] + [r.specobject_id for r in result.Requirements] + [t.targetvalue_id for t in result.TargetValues])
        self.assertFalse(old_human_readable_ids.intersection(new_human_readable_ids), 'Not all human readable ids (spec_id, specobject_id, targetvalue_id) were resetted')

    def test_copy_specification_depth_one(self):
        """ (R000002812) Check if CDB_Copy with depth = 1 on a specification returns an intact structure as a new specfication
        """
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        old_reqif_ids = set([spec.reqif_id] + [x.reqif_id for x in spec.Requirements + spec.TargetValues])
        old_human_readable_ids = set([spec.spec_id] + [r.specobject_id for r in spec.Requirements] + [t.targetvalue_id for t in spec.TargetValues])
        interactive_operation("cdbrqm_update_sortorder", spec)
        result = interactive_operation("CDB_Copy", spec, user_input={"copy_first_level": 1}, preset=None)

        valid_objects = [u"anf1", u"anf2", u"anf3"]
        valid_target_values = {u"anf3": u"ziel1"}
        requirements = RQMSpecObject.KeywordQuery(specification_object_id=result.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
            self.assertEqual(specobj.Specification.status, 0)
            self.assertIsNone(specobj.act_value)
            if specobj.name_de in valid_target_values:
                self.assertTrue(specobj.TargetValues[0].name_de == valid_target_values[specobj.name_de])
                self.assertIsNone(specobj.TargetValues[0].act_value)
        new_reqif_ids = set([result.reqif_id] + [x.reqif_id for x in result.Requirements + result.TargetValues])
        self.assertFalse(old_reqif_ids.intersection(new_reqif_ids), 'Not all reqif_ids were resetted')
        new_human_readable_ids = set([result.spec_id] + [r.specobject_id for r in result.Requirements] + [t.targetvalue_id for t in result.TargetValues])
        self.assertFalse(old_human_readable_ids.intersection(new_human_readable_ids), 'Not all human readable ids (spec_id, specobject_id, targetvalue_id) were resetted')

    def test_index_specification(self):
        """ (R000002848) Check if generate index on a specification returns an intact structure with an updated revision"""

        def compare_objects(a, b):
            fields_to_ignore = ["cdb_object_id", 'cdb_cdate', 'cdb_mdate',
                                'cdb_cpersno', 'cdb_mpersno', 'parent_object_id',
                                'template_oid', 'cdbrqm_edate', 'cdbrqm_epersno',
                                'status', 'revision', 'specification_object_id',
                                'requirement_object_id']
            for k, v in a._fields.items():
                if k in fields_to_ignore:
                    continue
                self.assertEqual(v, b[k])
            if hasattr(a, "SemanticLinks"):
                self.assertEqual(len(a.SemanticLinks), len(b.SemanticLinks))
            a_classification_data = classification_api.get_classification(a)
            del a_classification_data['values_checksum']
            for prop_key, values in a_classification_data.get('properties').items():
                for value in values:
                    if 'id' in value:
                        del value['id']
            b_classification_data = classification_api.get_classification(b)
            del b_classification_data['values_checksum']
            for prop_key, values in b_classification_data.get('properties').items():
                for value in values:
                    if 'id' in value:
                        del value['id']
            self.assertDictEqual(
                ensure_json_serialiability(a_classification_data),
                ensure_json_serialiability(b_classification_data)
            )

        spec = RQMSpecification.KeywordQuery(name=u"RQM ReqIF Interface (TEST)")[0]
        spec2 = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]

        linktype = SemanticLinkType.getValidLinkTypes(subject_object_classname="cdbrqm_specification",
                                                      object_object_classname="cdbrqm_specification")
        args = {"subject_object_id": spec.cdb_object_id,
                "link_type_object_id": linktype[0].cdb_object_id,
                "object_object_id": spec2.cdb_object_id,
                "object_object_classname": "cdbrqm_specification",
                "subject_object_classname": "cdbrqm_specification"}
        change_control_values = SemanticLink.MakeChangeControlAttributes()
        args.update(change_control_values)
        created_sem_link = SemanticLink.Create(**args)
        created_sem_link.generateMirrorLink("cdbrqm_specification", "cdbrqm_specification")

        from collections import defaultdict
        import datetime
        obj_to_classify = RQMSpecObject.ByKeys(specobject_id="RT000000016")
        classification_api.update_classification(
            obj_to_classify,
            {
                'assigned_classes': [u'RQM_TEST01', u'RQM_RATING'],
                'properties': defaultdict(list, {
                    u'RQM_TEST01_test_date_einwertig': [
                        {
                            'property_type': u'datetime',
                            'id': u'0458ed56-3e51-11e8-98e3-cb5b1e310df5',
                            'value': datetime.datetime(2018, 4, 12, 0, 0)
                        }
                    ],
                    u'RQM_TEST01_test_date_mehrwertig': [
                        {
                            'property_type': u'datetime',
                            'id': u'0458ed58-3e51-11e8-9eb5-cb5b1e310df5',
                            'value': datetime.datetime(2018, 4, 12, 0, 0)
                        },
                        {
                            'property_type': u'datetime',
                            'id': u'0458ed5a-3e51-11e8-9ae2-cb5b1e310df5',
                            'value': datetime.datetime(2018, 4, 13, 0, 0)
                        }
                    ],
                    u'RQM_TEST01_test_text_einwertig_enum': [
                        {
                            'property_type': u'text',
                            'id': u'0458ed5e-3e51-11e8-b499-cb5b1e310df5',
                            'value': u'test1'
                        }
                    ],
                    u'RQM_TEST01_test_int_einwertig_enum': [
                        {
                            'property_type': u'integer',
                            'id': u'0458ed60-3e51-11e8-a162-cb5b1e310df5',
                            'value': 2
                        }
                    ],
                    u'RQM_TEST01_test_int_mehrwertig_enum': [
                        {
                            'property_type': u'integer',
                            'id': u'0458ed62-3e51-11e8-807a-cb5b1e310df5',
                            'value': 1
                        },
                        {
                            'property_type': u'integer',
                            'id': u'0458ed64-3e51-11e8-a927-cb5b1e310df5',
                            'value': 2
                        }
                    ],
                    u'RQM_TEST01_test_text_mehrwertig': [
                        {
                            'property_type': u'text',
                            'id': u'0458ed66-3e51-11e8-90b7-cb5b1e310df5',
                            'value': u'test_text_mehrwertig'
                        },
                        {
                            'property_type': u'text',
                            'id': u'0458ed68-3e51-11e8-9856-cb5b1e310df5',
                            'value': u'test_text_mehrwertig2'
                        }
                    ],
                    u'RQM_TEST01_test_int_mehrwertig': [
                        {
                            'property_type': u'integer',
                            'id': u'0458ed6a-3e51-11e8-85b4-cb5b1e310df5',
                            'value': 3
                        },
                        {
                            'property_type': u'integer',
                            'id': u'0458ed6c-3e51-11e8-afda-cb5b1e310df5',
                            'value': 2
                        },
                        {
                            'property_type': u'integer',
                            'id': u'0458ed6e-3e51-11e8-9033-cb5b1e310df5',
                            'value': 1
                        }
                    ],
                    u'RQM_TEST01_test_date_einwertig_enum': [
                        {
                            'property_type': u'datetime',
                            'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                            'value': datetime.datetime(2018, 2, 23, 0, 0)
                        }
                    ],
                    u'RQM_TEST01_test_int_einwertig': [
                        {
                            'property_type': u'integer',
                            'id': u'0458ed72-3e51-11e8-b77b-cb5b1e310df5',
                            'value': 1
                        }
                    ],
                    u'RQM_TEST01_test_date_mehrwertig_enum': [
                        {
                            'property_type': u'datetime',
                            'id': u'0458ed76-3e51-11e8-bf29-cb5b1e310df5',
                            'value': datetime.datetime(2018, 2, 23, 10, 0)
                        },
                        {
                            'property_type': u'datetime',
                            'id': u'0458ed78-3e51-11e8-aca0-cb5b1e310df5',
                            'value': datetime.datetime(2018, 2, 24, 12, 0)
                        }
                    ],
                    u'RQM_TEST01_test_text_einwertig': [
                        {
                            'property_type': u'text',
                            'id': u'0458ed7e-3e51-11e8-bc83-cb5b1e310df5',
                            'value': u'test_text_einwertig'
                        }
                    ],
                    u'RQM_TEST01_test_text_mehrwertig_enum': [
                        {
                            'property_type': u'text',
                            'id': u'0458ed80-3e51-11e8-b2da-cb5b1e310df5',
                            'value': u'test1'
                        },
                        {
                            'property_type': u'text',
                            'id': u'0458ed82-3e51-11e8-9a1b-cb5b1e310df5',
                            'value': u'test2'
                        }
                    ],
                    u"RQM_RATING_RQM_RATING_VALUE": [
                        {
                            "property_type": u"multilang",
                            "value": {
                                "de": {
                                    "iso_language_code": u"de",
                                    "id": None,
                                    "text_value": None
                                },
                                "en": {
                                    "iso_language_code": u"en",
                                    "id": None,
                                    "text_value": None
                                }
                            }
                        }
                    ],
                    u"RQM_RATING_RQM_RATING_MDATE": [
                        {
                            "property_type": u"datetime",
                            "id": u"efd9e5da-5cb1-11eb-92ae-6805ca576edd",
                            "value": datetime.datetime(2018, 2, 24, 12, 0)
                        }
                    ],
                    u"RQM_RATING_RQM_RATING": [
                        {
                            "property_type": u"block",
                            "id": None,
                            "value": {
                                "description": u"",
                                "child_props": {
                                    u"RQM_EVALUATOR": [
                                        {
                                            "property_type": u"objectref",
                                            "id": None,
                                            "value": None
                                        }
                                    ],
                                    u"RQM_COMMENT_EXTERN": [
                                        {
                                            "property_type": u"text",
                                            "id": None,
                                            "value": None
                                        }
                                    ],
                                    u"RQM_RATING_VALUE": [
                                        {
                                            "property_type": u"multilang",
                                            "value": {
                                                "de": {
                                                    "iso_language_code": u"de",
                                                    "id": None,
                                                    "text_value": None
                                                },
                                                "en": {
                                                    "iso_language_code": u"en",
                                                    "id": None,
                                                    "text_value": None
                                                }
                                            }
                                        }
                                    ],
                                    u"RQM_COMMENT_INTERN": [
                                        {
                                            "property_type": u"text",
                                            "id": None,
                                            "value": None
                                        }
                                    ]
                                }
                            }
                        }
                    ],
                    u"RQM_RATING_RQM_RATING_SET_BY": [
                        {
                            "property_type": u"objectref",
                            "id": None,
                            "value": None
                        }
                    ],
                    u"RQM_RATING_RQM_REQ_TAGS": [
                        {
                            "property_type": u"multilang",
                            "id": None,
                            "value": {
                                "de": {
                                    "iso_language_code": u"de",
                                    "text_value": None
                                },
                                "en": {
                                    "iso_language_code": u"en",
                                    "text_value": None
                                }
                            }
                        }
                    ],
                    u"RQM_RATING_RQM_RATING_CALCULATED": [
                        {
                            "property_type": u"boolean",
                            "id": u"efd9e5e0-5cb1-11eb-92ae-6805ca576edd",
                            "value": True
                        }
                    ],
                    u"RQM_RATING_RQM_COMMENT_EXTERN": [
                        {
                            "property_type": u"text",
                            "id": u"efd9e5dc-5cb1-11eb-92ae-6805ca576edd",
                            "value": u"test"
                        }
                    ]
                })
            }
        )

        interactive_operation("cdbrqm_update_sortorder", spec)
        spec.ChangeState(100, check_access=0)
        spec.ChangeState(200, check_access=0)
        result = interactive_operation("cdbrqm_new_revision", spec, user_input=None, preset=None)

        valid_objects = [u"RT000000006",
                         u"RT000000009",
                         u"RT000000010",
                         u"RT000000011",
                         u"RT000000007",
                         u"RT000000012",
                         u"RT000000013",
                         u"RT000000008",
                         u"RT000000014",
                         u"RT000000016",
                         u"RT000000015"]
        valid_target_values = {u"RT000000016": [u"AT0000003",
                                                u"AT0000004"]}

        self.assertEqual(result.status, 190)
        self.assertEqual(result.revision, 0)
        newspec = RQMSpecification.KeywordQuery(spec_id=spec.spec_id, revision=1)[0]

        self.assertEqual(newspec.status, 0)
        self.assertEqual(newspec.revision, 1)
        self.assertEqual(len(spec.SemanticLinks), len(newspec.SemanticLinks))
        compare_objects(spec, newspec)

        requirements = RQMSpecObject.KeywordQuery(specification_object_id=newspec.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.specobject_id)
            self.assertEqual(specobj.Specification.status, 0)
            self.assertTrue(specobj.act_value in [0, None])
            if specobj.specobject_id in valid_target_values:
                for targetvalue in specobj.TargetValues:
                    self.assertTrue(targetvalue.targetvalue_id in valid_target_values[specobj.specobject_id])
                    self.assertTrue(targetvalue.act_value in [0, None])
                    compare_objects(targetvalue,
                                    spec.TargetValues.KeywordQuery(targetvalue_id=targetvalue.targetvalue_id)[0])
            compare_objects(specobj, spec.Requirements.KeywordQuery(specobject_id=specobj.specobject_id)[0])
