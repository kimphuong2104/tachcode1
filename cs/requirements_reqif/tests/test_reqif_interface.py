# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import datetime
import io
import json
import logging
import os
import subprocess
import tempfile
import zipfile

from cdb import CADDOK, objects, ue
from cdb.objects import operations
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import form_input, operation
from cs.audittrail import AuditTrail, AuditTrailDetail, AuditTrailObjects
from cs.classification import api as classification_api
from cs.classification.classes import ClassProperty
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.classes import RequirementCategory
from cs.requirements.document_export import DocumentExportTools
from cs.requirements.richtext import RichTextVariables
from cs.requirements.rqm_utils import createUniqueIdentifier, statement_count
from cs.requirements.tests.utils import RequirementsTestCase
from cs.requirements_reqif import (ReqIFProfile, ReqIFProfileAttribute,
                                   ReqIFProfileEntity, ReqIFProfileEnumerationValue, unPrefixID)
from cs.requirements_reqif.reqif_export_ng import ReqIFExportNG
from cs.requirements_reqif.reqif_import_ng import ReqIFImportNG
from cs.requirements_reqif.reqif_parser import ReqIFParser, ReqIFzHandler

try:
    from exceptions import WindowsError
    subprocess_error = WindowsError
except ImportError:
    subprocess_error = OSError

LOG = logging.getLogger(__name__)


class TestReqIFInterface(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        kwargs['need_uberserver'] = False
        self.maxDiff = None
        super(TestReqIFInterface, self).__init__(*args, **kwargs)

    def _test_roundtrip(
            self,
            profile_name,
            assured_attributes,
            spec_id,
            delta=False,
            assured_relations=None
    ):
        LOG.setLevel(logging.ERROR)
        spec = RQMSpecification.ByKeys(spec_id=spec_id, ce_baseline_id='')
        informations = []

        def get_dict_from_obj(obj):
            obj.Reload()  # ensure that it is refreshed
            data = {
                k: getattr(obj, k) if hasattr(obj, k) else
                (
                    obj.GetText(k)
                    if k in obj.GetTextFieldNames() else None
                ) for k in assured_attributes.get(obj.__classname__)
            }
            if assured_relations is not None:
                data['__semantic_link_targets__'] = {}
                links = obj.SemanticLinks
                for link in links:
                    if link.linktype_name in assured_relations:
                        data['__semantic_link_targets__'][link.linktype_name] = link.Object.reqif_id
            return data

        def insert_information(
            parent, obj, next_elems, level, **context_data
        ):
            informations.append(get_dict_from_obj(obj))

        # calculate informations for later comparison
        spec._walk(spec, insert_information)
        file_dummy = io.BytesIO()

        self.assertTrue(spec.reqif_id_locked == 0)

        print("spec before export: " + self.get_tree_string_repr(spec) + "\n")
        export_start_cnt = statement_count()
        # export content of our spec and the spec itself
        profile = ReqIFProfile.ByKeys(profile_name=profile_name)
        exporter = ReqIFExportNG(profile.cdb_object_id, spec, logger=LOG)
        exporter.export(file_dummy)
        export_stop_cnt = statement_count()
        print("export statement count: %d" % (export_stop_cnt - export_start_cnt))
        # with open('test.reqifz', 'w+b') as f:
        #     f.write(file_dummy.getvalue())
        #     f.seek(0)
        self.assertTrue(spec.reqif_id_locked == 1)

        if not delta:
            # delete content of our spec and the spec itself
            for r in spec.Requirements:
                for s in r.SemanticLinks:
                    s.Delete()
                r.Delete()
            for t in spec.TargetValues:
                for s in t.SemanticLinks:
                    s.Delete()
                t.Delete()
            for s in spec.SemanticLinks:
                s.Delete()
            spec.Delete()

            # create a new empty spec with other information than the exported
            new_spec_args = {
                u"name": u'Test Specification %s' % datetime.datetime.now(),
                u"is_template": 0,
                u"category": u'System Specification'
            }
            new_spec = objects.operations.operation("CDB_Create",
                                                    RQMSpecification,
                                                    **new_spec_args)
            self.assertTrue(new_spec.reqif_id_locked == 0)
        else:
            leaf_reqs = []

            def find_req_leafs(parent, obj, next_elems, level, **context_data):
                if isinstance(obj, RQMSpecObject) and not obj.SubRequirements:
                    leaf_reqs.append(obj)

            spec._walk(spec, find_req_leafs)
            r = leaf_reqs[0]
            r.Delete()

            for t in spec.TargetValues.Query("1=1", order_by=TargetValue.pos):
                t.Delete()
            spec.Update(name='something else')
            new_spec = spec

        informations_to_check = []
        import_start_cnt = statement_count()
        # re-import the spec information and spec content from ReqIF
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: new_spec,
                new_spec.reqif_id: new_spec
            },
            profile=profile.cdb_object_id,
            import_file=file_dummy,
            logger=LOG)
        importer.imp()
        import_stop_cnt = statement_count()
        print("import statement count: %d" % (import_stop_cnt - import_start_cnt))
        new_spec.Reload()
        self.assertTrue(new_spec.reqif_id_locked == 1)

        def insert_information_to_check(parent, obj, next_elems, level, **context_data):
            informations_to_check.append(get_dict_from_obj(obj))

        # calculate informations for later comparison
        spec._walk(new_spec, insert_information_to_check)
        print("spec after re-import: " + self.get_tree_string_repr(new_spec) + "\n")
        self.assertEqual(len(informations), len(informations_to_check), 'Different Length')
        self.assertEqual(informations, informations_to_check)

    def _test_roundtrip_classification(self, profile_name, assured_attributes, spec_id):
        LOG.setLevel(logging.ERROR)
        spec = RQMSpecification.ByKeys(spec_id=spec_id)
        informations = []

        def get_dict_from_obj(obj):
            # \n do not have to be preserved in xml/xhtml
            classification_data = classification_api.get_classification(obj)
            if 'RQM_TEST01' in classification_data.get('assigned_classes'):
                properties = classification_data.get('properties')
                def fix_float_rounding_issues_in_oracle(value):
                    from cdb import sqlapi
                    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE and isinstance(value, dict):
                        if 'float_value' in value and isinstance(value['float_value'], float):
                            value['float_value'] = round(value['float_value'], 14)
                        if 'float_value_normalized' in value and isinstance(value['float_value_normalized'], float):
                            value['float_value_normalized'] = round(value['float_value_normalized'], 14)
                    return value
                cdata = {k: [fix_float_rounding_issues_in_oracle(x.get('value')) for x in properties[k]] for k in assured_attributes.get(obj.__classname__, [])}
                return {obj.name: cdata}
            else:
                return {obj.name: {}}

        def insert_information(parent, obj, next_elems, level, **context_data):
            informations.append(get_dict_from_obj(obj))

        # calculate informations for later comparison
        spec._walk(spec, insert_information)
        file_dummy = io.BytesIO()

        # export content of our spec
        profile = ReqIFProfile.ByKeys(profile_name=profile_name)
        exporter = ReqIFExportNG(profile.cdb_object_id, spec, logger=LOG)
        exporter.export(file_dummy)

        # delete content of our spec
        for r in spec.Requirements:
            r.Delete()
        for t in spec.TargetValues:
            t.Delete()
        spec.Delete()

        # create a new empty spec with other information than the exported
        new_spec_args = {
            u"name": u'Test Specification %s' % datetime.datetime.now(),
            u"is_template": 0,
            u"category": u'System Specification'
        }
        new_spec = objects.operations.operation("CDB_Create", RQMSpecification, **new_spec_args)
        informations_to_check = []

        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: new_spec
            },
            profile=profile.cdb_object_id,
            import_file=file_dummy,
            logger=LOG
        )
        importer.imp()
        new_spec.Reload()

        def insert_information_to_check(parent, obj, next_elems, level, **context_data):
            informations_to_check.append(get_dict_from_obj(obj))

        # calculate informations for later comparison
        spec._walk(new_spec, insert_information_to_check)
        self.assertEqual(informations, informations_to_check)

    def test_reqif_roundtrip_reqman(self):
        """Check if a specification can be exported and re-imported without structure or information loss using the "ReqMan V2" Profile.
        """
        base_attr_list = [
            "cdbrqm_spec_object_desc_en",
            "category",
            "external_chapter",
            "ext_specobject_id",
            "reqif_id",
            "fulfillment_kpi_active"
        ]
        assured_attributes = {
            RQMSpecification.__classname__: [
                "name",
                "cdbrqm_specification_txt",
                "reqif_id"
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip("ReqMan V2", assured_attributes, "ST000000002")

    def test_reqif_roundtrip_cdb(self):
        """Check if a specification can be exported and re-imported without structure or information loss using the "CIM DATABASE Standard" Profile.
        """
        base_attr_list = [
            "category",
            "cdbrqm_spec_object_desc_de",
            "cdbrqm_spec_object_desc_en",
            "cdbrqm_specification_txt",
            "cdbrqm_target_value_desc_de",
            "cdbrqm_target_value_desc_en",
            "ext_spec_id",
            "ext_specobject_id",
            "priority",
            "source",
            "target_value",
            "value_type",
            "value_unit",
            "weight",
            "reqif_id",
            "fulfillment_kpi_active"
        ]
        assured_attributes = {
            RQMSpecification.__classname__: base_attr_list + [
                "name",
                "cdbrqm_specification_txt"
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip("CIM DATABASE Standard", assured_attributes, "ST000000001")

    def _ensure_req_category_description_exists(self):
        if not RequirementCategory.ByKeys('Description'):
            RequirementCategory.Create(name='Description', ml_name_de='Beschreibung', ml_name_en='Description')

    def test_reqif_roundtrip_polarion(self):
        """Check if a specification can be exported and re-imported without structure or information loss using the "Polarion Test" Profile.
        """
        self._ensure_req_category_description_exists()
        base_attr_list = [
            "cdbrqm_spec_object_desc_en",
            "category",
            "reqif_id",
            "fulfillment_kpi_active"
        ]
        assured_attributes = {
            RQMSpecification.__classname__: [
                "reqif_id",
                "fulfillment_kpi_active"
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip("Polarion Test", assured_attributes, "ST000000003")

    def test_reqif_roundtrip_reqman_classification(self):
        """Check if a specification can be exported and re-imported without structure or classification loss using the "ReqMan V2 (classification test)" Profile.
        """
        classification_data = classification_api.get_new_classification(["RQM_TEST01"])
        empty_spec_object = RQMSpecObject.ByKeys(specobject_id='RT000000024')
        classification_api.update_classification(empty_spec_object, classification_data)
        spec_object = RQMSpecObject.ByKeys(specobject_id='RT000000026')

        def resize(data, key, count):
            val = data['properties'][key]
            template = val[0]
            multi_value_count = len(val)
            # increase size
            if multi_value_count < count:
                for _ in range(0, abs(count - multi_value_count)):
                    data['properties'][key].append(dict(template))
            else:
                # replace with reduced size
                data['properties'][key] = val[0:-abs(multi_value_count - count)]

        assured_properties = {
            RQMSpecification.__classname__: [
            ],
            RQMSpecObject.__classname__: [
                "RQM_TEST01_test_date_einwertig",
                "RQM_TEST01_test_date_einwertig_enum",
                "RQM_TEST01_test_date_mehrwertig_enum",
                "RQM_TEST01_test_float_einwertig",
                "RQM_TEST01_test_float_einwertig_enum",
                "RQM_TEST01_test_float_mehrwertig_enum",
                "RQM_TEST01_test_int_einwertig",
                "RQM_TEST01_test_int_einwertig_enum",
                "RQM_TEST01_test_int_mehrwertig_enum",
                "RQM_TEST01_test_text_einwertig",
                "RQM_TEST01_test_text_einwertig_enum",
                "RQM_TEST01_test_text_mehrwertig_enum"
            ]
        }
        # date
        classification_data['properties']['RQM_TEST01_test_date_einwertig'][0]['value'] = datetime.datetime.now()

        classification_data['properties']['RQM_TEST01_test_date_einwertig_enum'][0]['value'] = datetime.datetime(year=2018, month=2, day=24)

        resize(classification_data, 'RQM_TEST01_test_date_mehrwertig_enum', 2)
        classification_data['properties']['RQM_TEST01_test_date_mehrwertig_enum'][0]['value'] = datetime.datetime(year=2018, month=2, day=23, hour=10)
        classification_data['properties']['RQM_TEST01_test_date_mehrwertig_enum'][1]['value'] = datetime.datetime(year=2018, month=2, day=24, hour=12)

        # float
        classification_data['properties']['RQM_TEST01_test_float_einwertig'][0]['value']['float_value'] = 3.1415

        classification_data['properties']['RQM_TEST01_test_float_einwertig_enum'][0]['value']['float_value'] = 4.2

        resize(classification_data, 'RQM_TEST01_test_float_mehrwertig_enum', 2)
        classification_data['properties']['RQM_TEST01_test_float_mehrwertig_enum'][0]['value']['float_value'] = 1.34
        classification_data['properties']['RQM_TEST01_test_float_mehrwertig_enum'][1]['value']['float_value'] = 3.1415

        # int
        classification_data['properties']['RQM_TEST01_test_int_einwertig'][0]['value'] = 42

        classification_data['properties']['RQM_TEST01_test_int_einwertig_enum'][0]['value'] = 2

        resize(classification_data, 'RQM_TEST01_test_int_mehrwertig_enum', 2)
        classification_data['properties']['RQM_TEST01_test_int_mehrwertig_enum'][0]['value'] = 1
        classification_data['properties']['RQM_TEST01_test_int_mehrwertig_enum'][1]['value'] = 3

        # text
        classification_data['properties']['RQM_TEST01_test_text_einwertig'][0]['value'] = "Die Antwort auf alle Fragen?"

        classification_data['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value'] = "test1"

        resize(classification_data, 'RQM_TEST01_test_text_mehrwertig_enum', 2)
        classification_data['properties']['RQM_TEST01_test_text_mehrwertig_enum'][0]['value'] = "test1"
        classification_data['properties']['RQM_TEST01_test_text_mehrwertig_enum'][1]['value'] = "test3"

        classification_api.update_classification(spec_object, classification_data)
        self._test_roundtrip_classification("ReqMan V2 (classification test)", assured_properties, "ST000000002")

    def test_reqif_delta_roundtrip_cdb(self):
        """Check if a specification can be exported and re-imported into a changed specification and re-imports the previously structure and information using the "CIM DATABASE Standard" Profile.
        """
        base_attr_list = [
            "category",
            "cdbrqm_spec_object_desc_de",
            "cdbrqm_spec_object_desc_en",
            "cdbrqm_specification_txt",
            "cdbrqm_target_value_desc_de",
            "cdbrqm_target_value_desc_en",
            "ext_spec_id",
            "ext_specobject_id",
            "priority",
            "source",
            "target_value",
            "value_type",
            "value_unit",
            "weight",
            "reqif_id",
            "fulfillment_kpi_active"
        ]
        assured_attributes = {
            RQMSpecification.__classname__: base_attr_list + [
                "name",
                "cdbrqm_specification_txt"
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip("CIM DATABASE Standard", assured_attributes, "ST000000001", delta=True)

    def test_reqif_delta_roundtrip_reqman(self):
        """Check if a specification can be exported and re-imported into a changed specification and re-imports the previously structure and information using the "ReqMan V2" Profile.
        """
        base_attr_list = [
            "cdbrqm_spec_object_desc_en",
            "category",
            "external_chapter",
            "ext_specobject_id",
            "reqif_id",
            "fulfillment_kpi_active"
        ]
        assured_attributes = {
            RQMSpecification.__classname__: [
                "name",
                "cdbrqm_specification_txt",
                "reqif_id"
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip("ReqMan V2", assured_attributes, "ST000000002", delta=True)

    def test_reqif_delta_roundtrip_polarion(self):
        """Check if a specification can be exported and re-imported into a changed specification and re-imports the previously structure and information using the "Polarion Test" Profile.
        """
        self._ensure_req_category_description_exists()
        base_attr_list = [
            "cdbrqm_spec_object_desc_en",
            "category",
            "reqif_id",
            "fulfillment_kpi_active"
        ]
        assured_attributes = {
            RQMSpecification.__classname__: [
                "reqif_id"
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip("Polarion Test", assured_attributes, "ST000000003", delta=True)

    def test_reqif_export_of_xhtml_attribute_into_reqif_string_field(self):
        """ Check whether XHTML markup is automatically stripped when exporting a XHTML attribute into a ReqIF string field """
        spec = RQMSpecification.ByKeys(spec_id="ST000000006")
        file_dummy = io.BytesIO()

        self.assertTrue(spec.reqif_id_locked == 0)
        # export content of our spec and the spec itself
        profile = ReqIFProfile.ByKeys(profile_name="E052722")
        exporter = ReqIFExportNG(profile.cdb_object_id, spec, logger=LOG)
        exporter.export(file_dummy)
        self.assertTrue(spec.reqif_id_locked == 1)
        with zipfile.ZipFile(file_dummy, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                        content = f.read()
                self.assertIn('THE-VALUE="Testtext in XHTML"', content.decode())
                self.assertNotIn('<xhtml:b>XHTML</xhtml:b>', content.decode())

    def test_reqif_enum_mapping_export(self):
        """ Check whether mapped enum values only appear with their mapped value in exports """
        spec = RQMSpecification.ByKeys(spec_id="ST000000007")
        req = spec.Requirements[0]
        with open(os.path.join(os.path.dirname(__file__), 'classification_E052755.json')) as f:
            data = json.load(fp=f)
        classification_api.update_classification(obj=req, data=data)
        file_dummy = io.BytesIO()

        self.assertTrue(spec.reqif_id_locked == 0)
        # export content of our spec and the spec itself
        profile = ReqIFProfile.ByKeys(profile_name="E052755")
        exporter = ReqIFExportNG(profile.cdb_object_id, spec, logger=LOG)
        exporter.export(file_dummy)
        self.assertTrue(spec.reqif_id_locked == 1)
        with zipfile.ZipFile(file_dummy, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                        content = f.read()
                self.assertIn('RQM_TEST01_test_text_einwertig_enum__new_mapped_test1', content.decode())
                self.assertTrue(
                    '<reqif:ENUM-VALUE-REF>cdb----test1_mapped---</reqif:ENUM-VALUE-REF>' in content.decode() or
                    '<REQIF:ENUM-VALUE-REF>cdb----test1_mapped---</REQIF:ENUM-VALUE-REF>' in content.decode()
                )

    def test_reqif_enum_mapping_import(self):
        """ Check whether mapped enum values only appear with their mapped internal value in the db """
        spec = RQMSpecification.ByKeys(spec_id="ST000000007")
        req = spec.Requirements[0]
        with open(
            os.path.join(os.path.dirname(__file__), 'classification_E052755_reset.json')
        ) as f:
            data = json.load(fp=f)
        classification_api.update_classification(obj=req, data=data)
        profile = ReqIFProfile.ByKeys(profile_name="E052755")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E052755.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        req.Reload()
        data = classification_api.get_classification(obj=req)
        self.assertIn('properties', data)
        self.assertIn('RQM_TEST01_test_text_einwertig_enum', data['properties'])
        self.assertIn('value', data['properties']['RQM_TEST01_test_text_einwertig_enum'][0])
        self.assertEqual(
            'test1', data['properties']['RQM_TEST01_test_text_einwertig_enum'][0]['value'])

    def test_reqif_modification_date_unchanged_for_unchanged_reqs(self):
        """ Check whether the modification date stays unchanged for requirements which do not have different content within the ReqIF file """
        # export a specification as preparation, change a single value, gather all cdb_mdates, re-import the reqif, compare the cdb_mdates -- only the changed one should be different
        spec = RQMSpecification.ByKeys(spec_id="ST000000012")
        unchanged_req = RQMSpecObject.ByKeys(specobject_id="RT000000058")
        changed_req = RQMSpecObject.ByKeys(specobject_id="RT000000059")

        # change something so that we have a diff only on this element
        changed_req.SetText('cdbrqm_spec_object_desc_de', changed_req.GetText('cdbrqm_spec_object_desc_de') + " geändert ")
        changed_req.Reload()

        # store dates for comparison
        unchanged_req_mdate = unchanged_req.cdb_mdate
        changed_req_mdate = changed_req.cdb_mdate

        # import the unchanged spec which then have a diff only on the changed element
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E055093.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        unchanged_req.Reload()
        changed_req.Reload()
        self.assertEqual(unchanged_req_mdate, unchanged_req.cdb_mdate)
        self.assertNotEqual(changed_req_mdate, changed_req.cdb_mdate)

    def test_reqif_reqs_sort_order_is_the_same_than_in_reqif_initial_import(self):
        """ Check whether the sort order is correctly imported """
        # see E057029
        spec = operations.operation("CDB_Create", RQMSpecification)
        profile = ReqIFProfile.ByKeys(profile_name="ReqMan V2")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        print(self.get_tree_string_repr(spec))
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))

    def test_reqif_reqs_sort_order_is_the_same_than_in_reqif_import_ng_with_added_reqs_between(self):
        """ Check whether the sort order of requirements is correctly imported when importing an updated ReqIF with new requirements between old ones."""
        # see E057029
        # initial import
        spec = operations.operation("CDB_Create", RQMSpecification)
        profile = ReqIFProfile.ByKeys(profile_name="ReqMan V2")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        # second import with more requirements
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029-2.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        print(self.get_tree_string_repr(spec))
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[3].GetText('cdbrqm_spec_object_desc_en'))

    def test_reqif_reqs_sort_order_is_the_same_than_in_reqif_import_ng_with_added_reqs_before(self):
        """ Check whether the sort order of requirements is correctly imported when importing an updated ReqIF with new requirements before old ones."""
        # see E057029
        # initial import
        spec = operations.operation("CDB_Create", RQMSpecification)
        profile = ReqIFProfile.ByKeys(profile_name="ReqMan V2")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        # second import with more requirements
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029-3.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        print(self.get_tree_string_repr(spec))
        self.assertIn('Test 0', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 1', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[3].GetText('cdbrqm_spec_object_desc_en'))

    def test_reqif_reqs_sort_order_is_the_same_than_in_reqif_import_ng_with_added_reqs_after(self):
        """ Check whether the sort order of requirements is correctly imported when importing an updated ReqIF with new requirements after old ones."""
        # see E057029
        # initial import
        spec = operations.operation("CDB_Create", RQMSpecification)
        profile = ReqIFProfile.ByKeys(profile_name="ReqMan V2")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        # second import with more requirements
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029-4.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        print(self.get_tree_string_repr(spec))
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 4', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 5', spec.TopRequirements[3].GetText('cdbrqm_spec_object_desc_en'))

    def test_reqif_tv_sort_order_is_the_same_than_in_reqif_import_ng_with_added_tvs_between(self):
        """ Check whether the sort order of requirements is correctly imported when importing an updated ReqIF with new acceptance criterion between old ones."""
        # see E057029
        # initial import
        spec = operations.operation("CDB_Create", RQMSpecification)
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029-tv-1.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test A', spec.TopRequirements[2].TargetValues[0].GetText('cdbrqm_target_value_desc_en'))
        self.assertIn('Test C', spec.TopRequirements[2].TargetValues[1].GetText('cdbrqm_target_value_desc_en'))
        # second import with more requirements
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), 'E057029-tv-2.reqifz'),
            logger=LOG)
        importer.imp()
        spec.Reload()
        print(self.get_tree_string_repr(spec))
        self.assertIn('Test 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_en'))
        self.assertIn('Test 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_en'))
        spec.TopRequirements[2].Reload()  # seems to be necessary, as spec.Reload does not reload the objects below
        self.assertIn('Test A', spec.TopRequirements[2].TargetValues[0].GetText('cdbrqm_target_value_desc_en'))
        self.assertIn('Test B', spec.TopRequirements[2].TargetValues[1].GetText('cdbrqm_target_value_desc_en'))
        self.assertIn('Test C', spec.TopRequirements[2].TargetValues[2].GetText('cdbrqm_target_value_desc_en'))

    def _assert_unique_top_level_positions(self, spec):
        positions = set()
        # assert that there are only unique positions
        for r in spec.TopRequirements:
            if r.position not in positions:
                positions.add(r.position)
            else:
                self.assertTrue(False, "position: %s is not unique" % r.position)

    def _import_test_spec_from_file(self, filename, spec=None, profile_name=None, create_baseline=True):
        spec = spec if spec is not None else operations.operation("CDB_Create", RQMSpecification)
        profile = ReqIFProfile.ByKeys(
            profile_name="CIM DATABASE Standard" if profile_name is None else profile_name
        )
        importer = ReqIFImportNG(
            specification_mappings={
                ReqIFImportNG.DEFAULT_MAPPING_KEY: spec,
                spec.reqif_id: spec
            },
            profile=profile.cdb_object_id,
            import_file=os.path.join(os.path.dirname(__file__), filename),
            logger=LOG,
            create_baseline=create_baseline
        )
        importer.imp()
        spec.Reload()
        return spec

    def test_reqif_positions_after_reimport_of_same_sortation(self):
        """ E059827: Check whether the positions of the requirements are stable
         after multiple (min 2) imports of the same ReqIF source data"""
        spec = self._import_test_spec_from_file(filename='E059827.reqifz')
        self.assertIn('test anf 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_de'))
        first_positions = {}
        for r in spec.Requirements:
            first_positions[r.cdb_object_id] = r.position
        spec = self._import_test_spec_from_file(filename='E059827.reqifz', spec=spec)
        for r in spec.Requirements:
            self.assertEqual(first_positions[r.cdb_object_id], r.position)
        self._assert_unique_top_level_positions(spec)

    def test_reqif_positions_after_reimport_with_changed_external_sortation(self):
        """ E059827: Check whether the internal sortation is the same as the changed ReqIF source"""
        spec = self._import_test_spec_from_file(filename='E059827.reqifz')
        self.assertIn('test anf 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_de'))

        spec = self._import_test_spec_from_file(
            filename='E059827-changed-sortation.reqifz',
            spec=spec
        )

        self.assertIn('test anf 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_de'))
        self._assert_unique_top_level_positions(spec)

    def test_reqif_positions_after_reimport_with_changed_internal_and_external_sortation(self):
        """ E059827: Check sortation after re-import with externally changed sortation after internal re-ordering"""
        spec = self._import_test_spec_from_file(filename='E059827.reqifz')
        self.assertIn('test anf 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_de'))

        # change position of req1 and req3 internally
        req1_old_pos = spec.TopRequirements[0].position
        req3_old_pos = spec.TopRequirements[2].position
        spec.TopRequirements[0].position = req3_old_pos
        spec.TopRequirements[2].position = req1_old_pos
        spec.Reload()
        spec.update_sortorder()
        spec.Reload()

        spec = self._import_test_spec_from_file(
            filename='E059827-changed-sortation.reqifz',
            spec=spec
        )

        self.assertIn('test anf 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_de'))
        self._assert_unique_top_level_positions(spec)

    def test_reqif_positions_after_reimport_with_int_added_reqs_and_ext_changed_sort(self):
        """ E059827: Check sortation after re-import with externally changed sortation after new internal requirements"""
        spec = self._import_test_spec_from_file(filename='E059827.reqifz')
        self.assertIn('test anf 1', spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', spec.TopRequirements[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', spec.TopRequirements[2].GetText('cdbrqm_spec_object_desc_de'))

        req2_old_pos = spec.TopRequirements[1].position
        # move new internal requirement to position 2
        spec.TopRequirements[1].position += 1
        spec.TopRequirements[2].position += 1

        internal_req = operations.operation(
            "CDB_Create", RQMSpecObject, specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_de=u"test int 1"
        )
        internal_req.position = req2_old_pos
        spec.Reload()
        spec.update_sortorder()
        spec.Reload()

        internal_req2 = operations.operation(
            "CDB_Create", RQMSpecObject, specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_de=u"test int 2",
        )
        internal_req2.position = max(spec.TopRequirements.position) + 1
        int_positions = {}
        for r in (internal_req, internal_req2):
            int_positions[r.cdb_object_id] = r.position
        spec.Reload()

        spec = self._import_test_spec_from_file(
            filename='E059827-changed-sortation.reqifz',
            spec=spec
        )
        int_reqs = []
        ext_reqs = []
        for r in spec.TopRequirements:
            if 'test int' in r.GetText('cdbrqm_spec_object_desc_de'):
                int_reqs.append(r)
            else:
                ext_reqs.append(r)
        # check external requirements are in the right order
        self.assertIn('test anf 1', ext_reqs[0].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 3', ext_reqs[1].GetText('cdbrqm_spec_object_desc_de'))
        self.assertIn('test anf 2', ext_reqs[2].GetText('cdbrqm_spec_object_desc_de'))
        # check internal requirement positions are unchanged
        for r in int_reqs:
            self.assertEqual(int_positions[r.cdb_object_id], r.position)
        self._assert_unique_top_level_positions(spec)

    def test_reqif_import_with_images_in_subfolders(self):
        spec = self._import_test_spec_from_file(filename='images_in_subfolder_S000000019.reqifz')
        self.assertEqual(len(spec.Requirements), 1)
        self.assertIn(
            'data="2021-08-09 09_34_44-ReqIF Test for pictures in subfolders (S000000019_0).png',
            spec.Requirements[0].GetText('cdbrqm_spec_object_desc_de')
        )

    def test_reqif_import_with_date_field(self):
        spec = self._import_test_spec_from_file(
            filename='with_date_field_S000000022.reqifz',
            profile_name='CIM DATABASE Standard (date test)'
        )
        self.assertEqual(len(spec.Requirements), 1)
        self.assertEqual(
            spec.Requirements[0].cdbrqm_edate,
            datetime.datetime(
                year=2021, month=8, day=9, hour=14, minute=2, second=11
            )
        )

    def test_reqif_import_with_inner_links(self):
        spec = self._import_test_spec_from_file(
            filename='with_inner_links_S000000025.reqifz',
        )
        self.assertEqual(len(spec.Requirements), 3)
        self.assertEqual(len(spec.Requirements[0].SemanticLinks), 1)
        self.assertEqual(len(spec.Requirements[2].SemanticLinks), 1)
        self.assertEqual(
            spec.Requirements[0].SemanticLinks[0].Object.cdb_object_id,
            spec.Requirements[2].cdb_object_id
        )
        self.assertEqual(
            spec.Requirements[2].SemanticLinks[0].Object.cdb_object_id,
            spec.Requirements[0].cdb_object_id
        )
        self.assertEqual(spec.Requirements[0].SemanticLinks[0].linktype_name, 'Trace')
        self.assertEqual(spec.Requirements[2].SemanticLinks[0].linktype_name, 'Trace')

    def test_reqif_roundtrip_with_inner_links(self):
        spec = self._import_test_spec_from_file(
            filename='with_inner_links_S000000025.reqifz',
        )
        self.assertEqual(len(spec.Requirements), 3)
        self.assertEqual(len(spec.Requirements[0].SemanticLinks), 1)
        spec.Update(reqif_id_locked=0)
        base_attr_list = [
        ]
        assured_attributes = {
            RQMSpecification.__classname__: base_attr_list + [
            ],
            RQMSpecObject.__classname__: base_attr_list,
            TargetValue.__classname__: base_attr_list
        }
        self._test_roundtrip(
            "CIM DATABASE Standard", assured_attributes, spec.spec_id,
            assured_relations=['Trace']
        )

    def test_reqifz_exports_can_be_extracted(self):
        spec = RQMSpecification.ByKeys(spec_id="ST000000001", ce_baseline_id='')
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard").cdb_object_id
        tmp_dir_path = tempfile.mkdtemp(dir=CADDOK.TMPDIR)
        try:
            exported_file = operation(
                'cdbrqm_reqif_export',
                spec,
                form_input(
                    spec,
                    reqif_profile=profile,
                    export_path='export.reqifz'
                )
            )
            self.assertIsInstance(exported_file, CDB_File)
            exported_file_path = os.path.join(tmp_dir_path, 'export.reqifz')
            exported_file.checkout_file(exported_file_path)
            subprocess.check_call(['unzip', '-o', exported_file_path], shell=True)
        except BaseException as e:
            LOG.exception(e)
            self.persist_export_run('reqifz_exports_can_be_extracted')
            self.assertTrue(False, 'failed to extract reqifz file')
        finally:
            DocumentExportTools.cleanup_folder(tmp_dir_path)
        self.assertTrue(spec.reqif_id_locked == 1)

    def test_reqif_import_fails_on_wrong_spec(self):
        with self.assertRaises(ue.Exception):
            # importing a reqifz file two times into a newly created spec
            # MUST fail as otherwise the reqif ids are more than once in the system
            self._import_test_spec_from_file(
                filename='with_inner_links_S000000025.reqifz',
            )
            self._import_test_spec_from_file(
                filename='with_inner_links_S000000025.reqifz',
            )

    def test_reqif_import_with_xhtml_attribute_mapped_to_char_field(self):
        profile = ReqIFProfile.Create(
            profile_name='Test with xhtml attribute mapped to char attribute'
        )
        self.assertIsInstance(profile, ReqIFProfile)
        ReqIFProfileEntity.Create(
            external_object_type='Spezifikation',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecification.__maps_to__,
            is_top_level=1
        )
        spec_object_entity = ReqIFProfileEntity.Create(
            external_object_type='Anforderung',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecObject.__maps_to__,
        )
        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=spec_object_entity.cdb_object_id,
            data_type="char",
            object_type_classname=RQMSpecObject.__classname__,
            external_identifier="description_de",
            external_field_name="cdbrqm_spec_object_desc_de",
            internal_field_name='discipline'
        )
        spec = self._import_test_spec_from_file(
            filename='with_inner_links_S000000025.reqifz',
            profile_name=profile.profile_name
        )
        self.assertEqual(spec.Requirements[0].discipline, "Requirement 1")

    def test_reqif_import_with_static_attribute_value(self):
        static_value = "hello world"
        profile = ReqIFProfile.Create(profile_name='Test with static attribute value')
        self.assertIsInstance(profile, ReqIFProfile)
        spec_entity = ReqIFProfileEntity.Create(
            external_object_type='Spezifikation',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecification.__maps_to__,
            is_top_level=1
        )
        ReqIFProfileEntity.Create(
            external_object_type='Anforderung',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecObject.__maps_to__,
        )
        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=spec_entity.cdb_object_id,
            data_type="char",
            object_type_classname=RQMSpecification.__classname__,
            external_identifier="does_not_exist",
            external_field_name="does not exist",
            static_internal_field_value=static_value,
            internal_field_name='discipline'
        )
        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=spec_entity.cdb_object_id,
            data_type="char",
            object_type_classname=RQMSpecification.__classname__,
            external_identifier="source",
            external_field_name="source",
            static_internal_field_value=static_value,
            internal_field_name='source'
        )
        spec = self._import_test_spec_from_file(
            filename='with_inner_links_S000000025.reqifz',
            profile_name=profile.profile_name
        )
        self.assertEqual(spec.discipline, static_value)
        self.assertEqual(spec.source, static_value)
        # check whether reqif import correctly creates audittrail entries
        audittrailobjects = AuditTrailObjects.KeywordQuery(object_id=spec.cdb_object_id)
        self.assertTrue(audittrailobjects)
        audittrail = AuditTrail.KeywordQuery(object_id=spec.cdb_object_id,
                                             type=u"modify")  # the spec already exists before reqif import
        self.assertTrue(audittrail)
        source_audittrail_detail = AuditTrailDetail.KeywordQuery(
            audittrail_object_id=audittrail.audittrail_object_id,
            attribute_name='source'
        )
        self.assertTrue(source_audittrail_detail)
        self.assertEqual(source_audittrail_detail[0].old_value, u'')
        self.assertEqual(source_audittrail_detail[0].new_value, static_value)

    def test_reqif_import_doors(self):
        from cs.requirementstests import reqif_test_data
        profile = ReqIFProfile.Create(profile_name='Test with doors heuristic')
        ReqIFProfileEntity.Create(
            external_object_type='_45715feb-019b-11ec-92bd-6805ca576edd',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecification.__maps_to__,
            is_top_level=1
        )
        heading_entity = ReqIFProfileEntity.Create(
            external_object_type='_055fe199-019b-11ec-92bd-6805ca576edd',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecObject.__maps_to__,
            object_type_field_name='category',
            object_type_field_value='Heading',
            ext_object_type_field_value='Heading',
            external_object_type_longname='Heading'
        )

        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=heading_entity.cdb_object_id,
            data_type="char",
            object_type_classname=RQMSpecification.__classname__,
            external_identifier=createUniqueIdentifier(),
            external_field_name="Category",
            internal_field_name='category',
            static_internal_field_value='Heading',
        )

        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=heading_entity.cdb_object_id,
            internal_field_name='cdbrqm_spec_object_desc_en',
            external_identifier="_055fe199-019b-11ec-92bd-6805ca576edd_OBJECTHEADING",
            external_field_name="ReqIF.ChapterName",
            data_type="xhtml",
            object_type_classname=RQMSpecification.__classname__
        )

        requirement_entity = ReqIFProfileEntity.Create(
            external_object_type='_055fe199-019b-11ec-92bd-6805ca576edd',
            reqif_profile_id=profile.cdb_object_id,
            internal_object_type=RQMSpecObject.__maps_to__,
            object_type_field_name='category',
            object_type_field_value='Requirement',
            external_object_type_longname='Requirement'
        )

        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=requirement_entity.cdb_object_id,
            data_type="char",
            object_type_classname=RQMSpecification.__classname__,
            external_identifier=createUniqueIdentifier(),
            external_field_name="Category",
            internal_field_name='category',
            static_internal_field_value='Requirement',
        )

        ReqIFProfileAttribute.Create(
            reqif_profile_id=profile.cdb_object_id,
            entity_object_id=requirement_entity.cdb_object_id,
            internal_field_name='cdbrqm_spec_object_desc_en',
            external_identifier="_055fe199-019b-11ec-92bd-6805ca576edd_OBJECTTEXT",
            external_field_name="ReqIF.Text",
            data_type="xhtml",
            object_type_classname=RQMSpecification.__classname__,
        )

        self.assertIsInstance(profile, ReqIFProfile)
        doors_test_file = os.path.join(
            os.path.dirname(reqif_test_data.__file__),
            'doors_test.reqif'
        )
        spec = self._import_test_spec_from_file(
            doors_test_file, profile_name=profile.profile_name
        )
        self.assertEqual(len(spec.Requirements), 2)
        self.assertEqual(len(spec.TopRequirements), 1)
        self.assertEqual(spec.TopRequirements[0].category, 'Heading')
        self.assertEqual(
            spec.TopRequirements[0].GetText('cdbrqm_spec_object_desc_en'),
            '<xhtml:div>Document targets</xhtml:div>'
        )
        self.assertEqual(spec.Requirements[1].category, 'Requirement')
        self.assertEqual(
            spec.Requirements[1].GetText('cdbrqm_spec_object_desc_en'),
            '<xhtml:div>Requirement text</xhtml:div>'
        )

    def test_reqif_import_with_umlauts_in_attachment_filenames(self):
        spec = self._import_test_spec_from_file(
            filename='E055277.reqifz',
        )
        self.assertEqual(len(spec.Requirements), 1)

    def test_reqif_import_with_variables_and_values_strips_values(self):
        variable_id = "RQM_RATING_RQM_COMMENT_EXTERN"
        variable_value = "###Test IMPORT Comment###"
        spec = self._import_test_spec_from_file(
            filename='with_variables_and_values.reqif',
        )
        self.assertEqual(len(spec.Requirements), 1)
        content_de = spec.Requirements[0].GetText("cdbrqm_spec_object_desc_de")
        self.assertIn(variable_id, content_de)
        self.assertIn(RichTextVariables.get_variable_xhtml(variable_id), content_de)
        self.assertNotIn(variable_value, content_de)

    def _spec_with_one_req_and_variable(self, variable_id, replace_variables=True):
        new_spec_args = {
            u"name": u'Test Specification %s' % datetime.datetime.now(),
            u"is_template": 0,
            u"category": u'System Specification'
        }
        spec = operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )
        content = u"<xhtml:div>{variable}</xhtml:div>".format(
            variable=RichTextVariables.get_variable_xhtml(variable_id)
        )
        req1 = operations.operation(
            "CDB_Create",
            RQMSpecObject,
            specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_de=content,
            cdbrqm_spec_object_desc_en=content
        )
        self.assertTrue(spec.reqif_id_locked == 0)
        # export content of our spec and the spec itself
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard")
        exporter = ReqIFExportNG(profile.cdb_object_id, spec, logger=LOG, replace_variables=replace_variables)
        return exporter, spec, req1

    def _set_classification_val(self, obj, code=None, value=None):
        if value is None:
            value = "###Test Comment###"
        if code is None:
            code = "RQM_RATING_RQM_COMMENT_EXTERN"

        classification_data = classification_api.get_classification(obj)
        classification_data["properties"][code][0]["value"] = value
        classification_api.update_classification(obj, classification_data)
        return value

    def test_reqif_export_with_variables_replaced_with_values(self):
        file_dummy = io.BytesIO()
        variable_id = "RQM_RATING_RQM_COMMENT_EXTERN"
        exporter, spec, req1 = self._spec_with_one_req_and_variable(variable_id)
        variable_value = self._set_classification_val(req1)
        exporter.export(file_dummy)
        self.assertTrue(spec.reqif_id_locked == 1)
        with zipfile.ZipFile(file_dummy, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                    content = f.read().decode('utf-8')
                self.assertIn(variable_value, content)
                self.assertNotIn(variable_id, content)

    def test_reqif_export_with_variables_replaced_without_values(self):
        file_dummy = io.BytesIO()
        variable_id = "RQM_RATING_RQM_COMMENT_EXTERN"
        exporter, _spec, _req1 = self._spec_with_one_req_and_variable(variable_id)
        with self.assertRaises(ue.Exception):
            exporter.export(file_dummy)

    def test_reqif_export_with_only_ids_and_missing_values(self):
        file_dummy = io.BytesIO()
        variable_id = "RQM_RATING_RQM_COMMENT_EXTERN"
        exporter, spec, _req1 = self._spec_with_one_req_and_variable(variable_id, replace_variables=False)
        exporter.export(file_dummy)
        self.assertTrue(spec.reqif_id_locked == 1)
        with zipfile.ZipFile(file_dummy, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                    content = f.read().decode('utf-8')
                self.assertIn(variable_id, content)

    def test_reqif_export_with_only_ids(self):
        file_dummy = io.BytesIO()
        variable_id = "RQM_RATING_RQM_COMMENT_EXTERN"
        exporter, spec, req1 = self._spec_with_one_req_and_variable(variable_id, replace_variables=False)
        variable_value = self._set_classification_val(req1)
        exporter.export(file_dummy)
        self.assertTrue(spec.reqif_id_locked == 1)
        with zipfile.ZipFile(file_dummy, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                    content = f.read().decode('utf-8')
                self.assertIn(variable_id, content)
                self.assertNotIn(variable_value, content)

    def test_reqif_update_import_with_new_requirement_with_object(self):
        # important : the spec also have images after the first import (otherwise the file_cache is not used)
        spec = self._import_test_spec_from_file(
            filename='E070639-v1.reqifz',
        )
        self.assertEqual(len(spec.Requirements), 1)
        self.assertEqual(len(spec.Requirements[0].Files), 1)
        spec = self._import_test_spec_from_file(
            filename='E070639-v2.reqifz',
            spec=spec
        )
        self.assertEqual(len(spec.Requirements), 2)
        self.assertEqual(len(spec.Requirements[1].Files), 1)

    def test_reqif_export_contains_default_values_for_enumerations_with_default_value(self):
        # test for E067555: ReqIF enumerations with default value
        file_dummy = io.BytesIO()
        spec = RQMSpecification.ByKeys(spec_id="ST000000002")
        profile = ReqIFProfile.ByKeys(profile_name="ReqMan V2 (classification test)")
        exporter = ReqIFExportNG(
            profile.cdb_object_id, spec, logger=LOG
        )
        exporter.export(file_dummy)
        with ReqIFzHandler(file_dummy) as (
            reqif_files, binary_files, extraction_time
        ):
            with ReqIFParser(reqif_files) as parser_result:
                result = parser_result.to_dict(parser_result)
                try:
                    # _14d05aef-c966-437f-b1a1-693bb0489dc5 is reqif ID of spec type for requirements
                    for property_code in [ # normal enumerations without enum value mapping
                        "RQM_TEST01_test_text_einwertig_enum_with_default",
                    ]:
                        prop_default_value_oid = unPrefixID(
                            result["spec_attributes"]["_14d05aef-c966-437f-b1a1-693bb0489dc5"][property_code]["default"]["values"][0]
                        )
                        prop = ClassProperty.ByKeys(code=property_code)
                        self.assertEqual(prop.default_value_oid, prop_default_value_oid)
                    for property_code in [ # enumerations with enum value mapping (and default value is a mapped enum)
                        "RQM_TEST01_test_text_einwertig_enum_with_default_1"
                    ]:
                        prop_default_value_oid = unPrefixID(
                            result["spec_attributes"]["_14d05aef-c966-437f-b1a1-693bb0489dc5"][property_code]["default"]["values"][0]
                        )
                        enum_value_mapping = ReqIFProfileEnumerationValue.ByKeys(
                            reqif_profile_id=profile.cdb_object_id,
                            external_identifier=prop_default_value_oid
                        )
                        prop = ClassProperty.ByKeys(code=property_code)
                        self.assertEqual(prop.default_value_oid, enum_value_mapping.internal_identifier)
                except (KeyError, AttributeError) as e:
                    LOG.exception("failed")
                    self.assertEqual(False, True, "failed")

    def test_import_export_with_identical_file_names_between_requirements(self):
        spec = self._import_test_spec_from_file(
            filename='identical_filenames.reqifz'
        )
        self.assertIn(
            'test.png', spec.Requirements[0].GetText('cdbrqm_spec_object_desc_de')
        )
        self.assertIn(
            'test.png', spec.Requirements[1].GetText('cdbrqm_spec_object_desc_de')
        )
        self.assertEqual(spec.Requirements[0].Files[0].cdbf_name, 'test.png')
        self.assertEqual(spec.Requirements[1].Files[0].cdbf_name, 'test.png')
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard").cdb_object_id
        test_file = io.BytesIO()
        exporter = ReqIFExportNG(profile, spec)
        exporter.export(test_file)
        with zipfile.ZipFile(test_file, allowZip64=True) as zfile:
            names = zfile.namelist()
            self.assertIn('/'.join((spec.Requirements[0].reqif_id, 'test.png')), names)
            self.assertIn('/'.join((spec.Requirements[1].reqif_id, 'test.png')), names)
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                    content = f.read()
                self.assertIn('<xhtml:object data="' + '/'.join((spec.Requirements[0].reqif_id, 'test.png')), content.decode())
                self.assertIn('<xhtml:object data="' + '/'.join((spec.Requirements[1].reqif_id, 'test.png')), content.decode())

    def test_acceptance_criterion_not_exporting(self):
        spec = self._import_test_spec_from_file(
            filename='test_acceptance_criterions_export.reqifz'
        )
        profile = ReqIFProfile.ByKeys(profile_name="CIM DATABASE Standard (Without Acceptance Criterions)").cdb_object_id
        test_file = io.BytesIO()
        exporter = ReqIFExportNG(profile, spec, export_target_values=True)
        self.assertEqual(spec.Requirements[1].TargetValues[0].name, "test-criterion")
        with self.assertRaises(ue.Exception):
            exporter.export(test_file)
        exporter = ReqIFExportNG(profile, spec, export_target_values=False)
        exporter.export(test_file)
        with zipfile.ZipFile(test_file, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                    content = f.read()
                self.assertNotIn('<reqif:SPEC-OBJECT DESC="test-criterion', content.decode())

        profile = ReqIFProfile.ByKeys(
            profile_name="CIM DATABASE Standard").cdb_object_id

        exporter = ReqIFExportNG(profile, spec, export_target_values=True)
        exporter.export(test_file)
        with zipfile.ZipFile(test_file, allowZip64=True) as zfile:
            names = [x for x in zfile.namelist() if x.endswith('.reqif')]
            for name in names:
                with zfile.open(name) as f:
                    content = f.read()
                self.assertIn('<reqif:SPEC-OBJECT DESC="test-criterion', content.decode())

    def test_baseline_creation(self):
        spec = self._import_test_spec_from_file(
            filename='test_acceptance_criterions_export.reqifz',
        )
        self.assertEqual(2, len(RQMSpecification.KeywordQuery(spec_id=spec.spec_id)))
        self._import_test_spec_from_file(
            spec=spec,
            filename='test_acceptance_criterions_export.reqifz',
            create_baseline=True
        )
        self.assertEqual(3, len(RQMSpecification.KeywordQuery(spec_id=spec.spec_id)))
        self._import_test_spec_from_file(
            spec=spec,
            filename='test_acceptance_criterions_export.reqifz',
            create_baseline=False
        )
        self.assertEqual(3, len(RQMSpecification.KeywordQuery(spec_id=spec.spec_id)))



