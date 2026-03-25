# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function

import datetime
import logging
import os
import time
import time

from cdb import ElementsError, rte, ue
from cdb.objects import operations
from cdb.objects.cdb_file import CDB_File
from cdb.testcase import PlatformTestCase
from cdb.validationkit.op import operation as interactive_operation
from cdbwrapc import getFileTypeByFilename
from cs.audittrail import AuditTrailObjects
from cs.classification import api as classification_api
from cs.platform.web.root import root as RootApp
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.requirements import RQMSpecification, RQMSpecObject
from webtest import TestApp
from cdb.validationkit.SwitchRoles import run_with_roles

from .utils import RequirementsTestCase

LOG = logging.getLogger(__name__)


class TestSpecObject(RequirementsTestCase):
    def __init__(self, *args, **kwargs):
        super(TestSpecObject, self).__init__(*args, need_uberserver=False,
                                             **kwargs)

    def setUp(self, *args, **kwargs):
        super(TestSpecObject, self).setUp(*args, **kwargs)
        self.spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        self.structure_spec = RQMSpecification.KeywordQuery(name=u"StructureTests")[0]
        for req in self.spec.Requirements:
            interactive_operation("cdbrqm_reset_fulfillment", req)
        self.req = RQMSpecObject.KeywordQuery(name_de=u'anf1-1', specification_object_id=self.spec.cdb_object_id)[0]

    def test_sortorder_on_non_interactive_creation(self):
        spec = operations.operation(
            'CDB_Create', RQMSpecification, name='RQMSpecificationEditor Spec 001'
        )
        req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_en=u'<xhtml:div>RQMSpecificationEditor Req 001</xhtml:div>',
            position=1
        )
        req2 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_en=u'<xhtml:div>RQMSpecificationEditor Req 002</xhtml:div>',
            position=2
        )
        self.assertEqual(int(req1.chapter), 1)
        self.assertEqual(int(req2.chapter), 2)
        self.assertLess(req1.sortorder, req2.sortorder)

    def test_requirement_description_to_shortdescription_logic(self):
        """ (R00002806) Check if creating a new requirement with a description in one language leads to a short description in the same language"""
        self.assertEqual(self.spec.status, 0)
        description = 'req3'
        user_input = {}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "parent_object_id": self.req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        r = interactive_operation("CDB_Create", RQMSpecObject, user_input, preset)
        self.assertEqual(r.GetText('cdbrqm_spec_object_desc_de'), "<xhtml:div>%s</xhtml:div>" % description)
        self.assertEqual(r.name_de, description)

    def test_requirement_creation_fails(self):
        """ (R00002806) Check if creating a new requirement on a specification with status 200 fails"""
        self.spec.ChangeState(100, check_access=0)
        self.spec.ChangeState(200, check_access=0)
        self.assertEqual(self.spec.status, 200)
        description = 'req3'
        user_input = {}
        preset = {"specification_object_id": self.spec.cdb_object_id,
                  "parent_object_id": self.req.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        with self.assertRaises(RuntimeError):
            interactive_operation("CDB_Create", RQMSpecObject, user_input, preset)

    def test_copy_spec_object(self):
        """ (R000002812) Check if CDB_Copy on a requirement returns an intact structure
        """
        interactive_operation("cdbrqm_update_sortorder", self.spec)

        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id, name_de=u"anf1")[0]
        result = interactive_operation("CDB_Copy", requirement,
                                       user_input={"specification_object_id": self.spec.cdb_object_id}, preset=None)
        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"anf3", u"anf1", u"anf1-1", u"anf1-2"]
        valid_target_values = {u"anf1-2": u"ziel2"}
        requirements = RQMSpecObject.KeywordQuery(specification_object_id=result.specification_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
            self.assertEqual(specobj.Specification.status, 0)
            # we do a copy in an existing structure thus act_value can be 0 or None
            self.assertTrue(specobj.act_value in [0, None])
            if specobj.name_de in valid_target_values:
                self.assertEqual(specobj.TargetValues[0].name_de, valid_target_values[specobj.name_de])
                self.assertTrue(specobj.act_value in [0, None])

    def test_is_defined_hierachical(self):
        """ Check if changing the is_defined attribute to 1 sets the is_defined on sub requirements"""

        interactive_operation("cdbrqm_update_sortorder", self.spec)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id, name_de=u"anf1")[0]
        result = interactive_operation("CDB_Modify", requirement,
                                       user_input={"is_defined": 1}, preset=None)
        self.assertEqual(result.is_defined, 1)
        for sub_req in RQMSpecObject.KeywordQuery(parent_object_id=result.cdb_object_id, order_by="sortorder"):
            self.assertEqual(sub_req.is_defined, 1)

    def test_is_defined_parent_requirement(self):
        """ Check if changing the is_defined attribute to 0 sets the is_defined to 0 on parent requirement"""
        self.spec.Requirements.Update(is_defined=1)
        interactive_operation("cdbrqm_update_sortorder", self.spec)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id, name_de=u"anf1-2")[0]
        result = interactive_operation("CDB_Modify", requirement,
                                       user_input={"is_defined": 0}, preset=None)
        parent = RQMSpecObject.ByKeys(cdb_object_id=result.ParentRequirement.cdb_object_id)
        self.assertEqual(parent.is_defined, 0)
        unaffected_requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id, name_de=u"anf1-1")[0]
        self.assertEqual(unaffected_requirement.is_defined, 1)

    def test_delete_requirement(self):
        """ Check if sortorder and positions are correct after deleting a requirement"""
        self._skip_before_specific_platform_version(major=15, minor=6, sl=1)
        interactive_operation("cdbrqm_update_sortorder", self.spec)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id, name_de=u"anf1-1")[0]
        requirement2 = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                  name_de=u"anf1-2")[0]
        self.assertNotEqual(requirement.position, requirement2.position)
        self.assertNotEqual(requirement.sortorder, requirement2.sortorder)
        self.assertNotEqual(requirement.chapter, requirement2.chapter)
        interactive_operation("CDB_Delete", requirement)
        requirement2 = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                  name_de=u"anf1-2")[0]

        self.assertEqual(requirement.position, requirement2.position)
        self.assertEqual(requirement.sortorder, requirement2.sortorder)
        self.assertEqual(requirement.chapter, requirement2.chapter)
    
    def test_delete_requirement_also_deletes_sub_elements(self):
        """ Check if all sub elements of a requirement are deleted after deletion of the requirement"""
        from cs.requirements import TargetValue
        spec = operations.operation(
            'CDB_Create', RQMSpecification, name='E072772 - Test RQM Spec Object deep delete'
        )
        req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_en=u'<xhtml:div>Test1</xhtml:div>',
            position=1
        )
        req11 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            parent_object_id=req1.cdb_object_id,
            specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_en=u'<xhtml:div>Test1</xhtml:div>',
            position=1
        )
        req2 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=spec.cdb_object_id,
            cdbrqm_spec_object_desc_en=u'<xhtml:div>Test2</xhtml:div>',
            position=2
        )
        user_input = {
            "value_type": 0,
            "value_unit": "min",
            "target_value_mask": "<=5"}
        preset = {"specification_object_id": spec.cdb_object_id,
                  "requirement_object_id": req11.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>ac01</xhtml:div>","en":"<xhtml:div></xhtml:div>"}'}
        ac01 = interactive_operation("CDB_Create", TargetValue, user_input, preset)
        preset = {"specification_object_id": spec.cdb_object_id,
                  "requirement_object_id": req2.cdb_object_id,
                  "richtext_desc": u'{"de":"<xhtml:div>ac02</xhtml:div>","en":"<xhtml:div></xhtml:div>"}'}
        ac02 = interactive_operation("CDB_Create", TargetValue, user_input, preset)
        interactive_operation("CDB_Delete", req1)
        self.assertEqual(RQMSpecObject.ByKeys(req1.cdb_object_id), None)
        self.assertEqual(RQMSpecObject.ByKeys(req11.cdb_object_id), None)
        self.assertEqual(TargetValue.ByKeys(ac01.cdb_object_id), None)
        self.assertNotEqual(RQMSpecObject.ByKeys(req2.cdb_object_id), None)
        self.assertNotEqual(TargetValue.ByKeys(ac02.cdb_object_id), None)
        interactive_operation("CDB_Delete", req2)
        self.assertEqual(RQMSpecObject.ByKeys(req2.cdb_object_id), None)
        self.assertEqual(TargetValue.ByKeys(ac02.cdb_object_id), None)

    def test_move_requirement_left(self):
        """ Check if moving a new requirement on a specification to the left works"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1-2")[0]
        old_parent_id = requirement.parent_object_id
        interactive_operation("cdbrqm_spec_object_move_left", requirement)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1-2")[0]
        new_parent_id = requirement.parent_object_id
        self.assertNotEqual(old_parent_id, new_parent_id)
        self.assertEqual(new_parent_id, "")

    def test_move_requirement_left_deep_structure(self):
        """ Check if moving a new requirement on a specification to the left works also on deep structures"""

        # step 1: 1.1.3 to left for the first time
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                 name_de=u"--- --- --- 1.1.3")[0]
        old_parent_id = requirement.parent_object_id
        interactive_operation("cdbrqm_spec_object_move_left", requirement)
        # verify step 1
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                 name_de=u"--- --- --- 1.1.3")[0]
        new_parent_id = requirement.parent_object_id
        expected_new_parent = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                         name_de=u"--- --- --- 1")[0]
        self.assertNotEqual(old_parent_id, new_parent_id)
        self.assertEqual(new_parent_id, expected_new_parent.cdb_object_id)
        self.assertEqual(requirement.position, 2)
        self.assertEqual(requirement.chapter, "1.2")

        # step 2: 1.1.3 to left for the second time
        old_parent_id = expected_new_parent.cdb_object_id
        interactive_operation("cdbrqm_spec_object_move_left", requirement)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                 name_de=u"--- --- --- 1.1.3")[0]
        new_parent_id = requirement.parent_object_id
        self.assertNotEqual(old_parent_id, new_parent_id)
        self.assertEqual(new_parent_id, "")
        self.assertEqual(requirement.position, 2)
        self.assertEqual(requirement.chapter, "2")

    def test_move_requirement_left_fails(self):
        """ Check if moving a new requirement on a specification to the left fails"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1")[0]
        old_parent_id = requirement.parent_object_id
        interactive_operation("cdbrqm_spec_object_move_left", requirement)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1")[0]
        new_parent_id = requirement.parent_object_id
        self.assertEqual(old_parent_id, new_parent_id)
        self.assertEqual(new_parent_id, "")

    def test_move_requiremnet_right(self):
        """ Check if moving a new requirement on a specification to the right works"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf2")[0]
        old_parent_id = requirement.parent_object_id
        interactive_operation("cdbrqm_spec_object_move_right", requirement)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf2")[0]
        new_parent_id = requirement.parent_object_id
        self.assertNotEqual(old_parent_id, new_parent_id)
        requirement2 = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                  name_de=u"anf1")[0]
        self.assertEqual(new_parent_id, requirement2.cdb_object_id)

    def test_move_requiremnet_right_deep_structure(self):
        """ Check if moving a new requirement on a specification to the right works also on deep structures"""
        # step 1: 1.2 to right for the first time
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                 name_de=u"--- --- --- 1.2")[0]
        old_parent_id = requirement.parent_object_id
        interactive_operation("cdbrqm_spec_object_move_right", requirement)
        # verify step 1
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                 name_de=u"--- --- --- 1.2")[0]
        new_parent_id = requirement.parent_object_id
        expected_new_parent = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                         name_de=u"--- --- --- 1.1")[0]
        self.assertNotEqual(old_parent_id, new_parent_id)
        self.assertEqual(new_parent_id, expected_new_parent.cdb_object_id)
        self.assertEqual(requirement.position, 4)
        self.assertEqual(requirement.chapter, "1.1.4")

        # step 2: 1.2 to left for the second time
        old_parent_id = expected_new_parent.cdb_object_id
        interactive_operation("cdbrqm_spec_object_move_right", requirement)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                 name_de=u"--- --- --- 1.2")[0]
        new_parent_id = requirement.parent_object_id
        expected_new_parent = RQMSpecObject.KeywordQuery(specification_object_id=self.structure_spec.cdb_object_id,
                                                         name_de=u"--- --- --- 1.1.3")[0]
        self.assertNotEqual(old_parent_id, new_parent_id)
        self.assertEqual(new_parent_id, expected_new_parent.cdb_object_id)
        self.assertEqual(requirement.position, 1)
        self.assertEqual(requirement.chapter, "1.1.3.1")

    def test_move_requiremnet_right_fails(self):
        """ Check if moving a new requirement on a specification to the right fails"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1")[0]
        old_parent_id = requirement.parent_object_id
        interactive_operation("cdbrqm_spec_object_move_right", requirement)
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1")[0]
        new_parent_id = requirement.parent_object_id
        self.assertEqual(old_parent_id, new_parent_id)

    def test_move_requirement_up(self):
        """ Check if moving a new requirement on a specification up works"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf2")[0]
        interactive_operation("cdbrqm_spec_object_move_up", requirement)
        valid_objects = [u"anf2", u"anf1", u"anf1-1", u"anf1-2", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=self.spec.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)

    def test_move_requirement_up_fails(self):
        """ Check if moving a new requirement on a specification up fails"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1")[0]
        interactive_operation("cdbrqm_spec_object_move_up", requirement)
        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=self.spec.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)

    def test_move_requirement_down(self):
        """ Check if moving a new requirement on a specification down works"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf1")[0]
        interactive_operation("cdbrqm_spec_object_move_down", requirement)
        valid_objects = [u"anf2", u"anf1", u"anf1-1", u"anf1-2", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=self.spec.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)

    def test_move_requirement_down_fails(self):
        """ Check if moving a new requirement on a specification down fails"""
        requirement = RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                                 name_de=u"anf3")[0]
        interactive_operation("cdbrqm_spec_object_move_down", requirement)
        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=self.spec.cdb_object_id, order_by="sortorder")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)

    def test_check_concurrent_modification_fails(self):
        """ Check if a modify date below the current time fails"""
        requirement = \
            RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                       name_de=u"anf3")[0]
        requirement.cdb_mdate = datetime.datetime.now() - datetime.timedelta(minutes=1)
        user_input = {"cdb_mdate": datetime.datetime.now()}
        description = 'test'
        preset = {"name_de": description,
                  "richtext_desc": u'{"de":"<xhtml:div>%s</xhtml:div>","en":"<xhtml:div></xhtml:div>"}' % description}
        interactive_operation("CDB_Modify", requirement, preset=preset, user_input=user_input, interactive=False)
        self.assertRaises(ue.Exception)

    def test_create_below(self):
        """ Check if a new requirement is created below when perforing the cdbrqm_spec_object_create_below operation"""
        requirement = \
            RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                       name_de=u"anf2")[0]
        result = interactive_operation("cdbrqm_spec_object_create_below", requirement,
                                       user_input=None,
                                       preset=None)
        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=result.specification_object_id, order_by="sortorder")
        self.assertEqual(result.parent_object_id, requirement.cdb_object_id)
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
            self.assertEqual(specobj.Specification.status, 0)
            # we do a copy in an existing structure thus act_value can be 0 or None
            self.assertTrue(specobj.act_value in [0, None])

    def test_create_beside(self):
        """ Check if a new requirement is created beside when perforing the cdbrqm_spec_object_create_beside operation"""
        requirement = \
            RQMSpecObject.KeywordQuery(specification_object_id=self.spec.cdb_object_id,
                                       name_de=u"anf2")[0]
        result = interactive_operation("cdbrqm_spec_object_create_beside", requirement,
                                       user_input=None,
                                       preset=None)
        valid_objects = [u"anf1", u"anf1-1", u"anf1-2", u"anf2", u"", u"anf3"]
        requirements = RQMSpecObject.KeywordQuery(
            specification_object_id=result.specification_object_id, order_by="sortorder")
        self.assertEqual(result.parent_object_id, "")
        for specobj in requirements:
            self.assertEqual(valid_objects[requirements.index(specobj)], specobj.name_de)
            self.assertEqual(specobj.Specification.status, 0)
            # we do a copy in an existing structure thus act_value can be 0 or None
            self.assertTrue(specobj.act_value in [0, None])


class TestSpecObjectPermissions(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpecObjectPermissions, self).__init__(
            *args, **kwargs
        )

    def setUp(self):
        super(TestSpecObjectPermissions, self).setUp()
        self.client = TestApp(RootApp)
        self.requirement = RQMSpecObject.ByKeys(specobject_id='RT000000061')
        self.requirement_with_object = RQMSpecObject.ByKeys(specobject_id='RTG000000061')

        def setup_requirement(obj, description):
            desc = "<xhtml:div>%s</xhtml:div>" % description
            for text_field in ['cdbrqm_spec_object_desc_de', 'cdbrqm_spec_object_desc_en']:
                obj.SetText(text_field, desc)
            obj.is_defined = False
            obj.Reload()
            for text_field in ['cdbrqm_spec_object_desc_de', 'cdbrqm_spec_object_desc_en']:
                self.assertEqual(obj.GetText(text_field), desc)

        description = 'Hello'
        setup_requirement(self.requirement, description)
        if self.requirement_with_object is None:
            self.requirement_with_object = self.requirement.Copy(specobject_id='RTG000000061')
        description = 'Hello<xhtml:object data="01_notExcelDoc.png">world</xhtml:object>'
        setup_requirement(self.requirement_with_object, description)
        if len(self.requirement_with_object.Files) == 0:
            test_file_name = '01_notExcelDoc.png'
            test_file = os.path.join(os.path.dirname(__file__), test_file_name)
            ftype = getFileTypeByFilename(test_file_name)
            CDB_File.NewFromFile(
                self.requirement_with_object.cdb_object_id,
                test_file,
                primary=True,
                additional_args=dict(
                    cdbf_name=test_file_name,
                    cdbf_type=ftype.getName()
                )
            )
            self.requirement_with_object.Reload()
        self.assertEqual(len(self.requirement_with_object.Files), 1)

    def count_audittrail_entries_for_object(self, obj):
        return len(AuditTrailObjects.KeywordQuery(object_id=obj.cdb_object_id))

    def test_richtext_permission_caddok_pcclient(self):
        """ Check whether a requirement description is editable using if one has 'save' and 'rqm_richtext_save' permission """
        description = u'test123'
        richtext_desc = u'{"de": "<xhtml:div>%s</xhtml:div>","en": "<xhtml:div></xhtml:div>"}' % description
        self.assertNotEqual(self.requirement.GetText('cdbrqm_spec_object_desc_de'), u"<xhtml:div>%s</xhtml:div>" % description)
        r = operations.operation('CDB_Modify', self.requirement, operations.form_input(
            RQMSpecObject,
            **{
                '.richtext_desc': richtext_desc
            }
        ))
        r.Reload()
        self.assertEqual(r.GetText('cdbrqm_spec_object_desc_de'), u"<xhtml:div>%s</xhtml:div>" % description)

    def test_richtext_permission_caddok_rest(self):
        url = '/api/v1/collection/spec_object/{cdb_object_id}'.format(cdb_object_id=self.requirement.cdb_object_id)
        title = 'the new title'
        body = 'the new body'
        richtext = '<xhtml:div><xhtml:div>{title}</xhtml:div><xhtml:div>{body}</xhtml:div></xhtml:div>'.format(body=body, title=title)
        for iso in ['de', 'en']:
            attr_name = 'cdbrqm_spec_object_desc_{iso}'.format(iso=iso)
            short_attr_name = 'name_{iso}'.format(iso=iso)
            audittrail_count_before = self.count_audittrail_entries_for_object(self.requirement)
            self.assertNotEqual(self.requirement.GetText(attr_name), richtext)
            self.assertNotEqual(getattr(self.requirement, short_attr_name), title)

            self.client.put_json(url, {attr_name: richtext})
            self.requirement.Reload()
            # the new richtext was saved correctly
            self.assertEqual(self.requirement.GetText(attr_name), richtext)
            self.assertEqual(getattr(self.requirement, short_attr_name), title)
            audittrail_count_after = self.count_audittrail_entries_for_object(self.requirement)
            self.assertGreater(audittrail_count_after, audittrail_count_before)
        self.requirement.Reload()
        self.assertEqual(self.requirement.name_de, title)
        self.assertEqual(self.requirement.name_en, title)

    def test_richtext_permission_contributor_test_only_meta_pcclient(self):
        """ Check whether an user with 'save' but not 'rqm_richtext_save' permission cannot change a requirement description but meta data (inner)"""
        @run_with_roles(["public", "Requirements: Contributor (test)"])
        def testIt():
            description = u'test456'
            with self.assertRaises(ElementsError) as cm:
                richtext_desc = u'{"de": "<xhtml:div>%s</xhtml:div>","en": "<xhtml:div></xhtml:div>"}' % description
                self.assertNotEqual(self.requirement.GetText('cdbrqm_spec_object_desc_de'), u"<xhtml:div>%s</xhtml:div>" % description)
                r = operations.operation('CDB_Modify', self.requirement, operations.form_input(
                    RQMSpecObject,
                    **{
                        '.richtext_desc': richtext_desc
                    }
                ))
            self.assertIn(str(ue.Exception('cdbrqm_desc_change_perm_miss')), str(cm.exception))
            self.assertNotEqual(self.requirement.GetText('cdbrqm_spec_object_desc_de'), u"<xhtml:div>%s</xhtml:div>" % description)
            r = interactive_operation("CDB_Modify", self.requirement, user_input={'is_defined': 1})
            self.assertEqual(r.is_defined, 1)
        testIt()

    def test_richtext_permission_contributor_test__only_meta_rest(self):
        """ Check whether an user with 'save' but not 'rqm_richtext_save' permission cannot change a requirement description but meta data via REST (inner)"""
        @run_with_roles(["public", "Requirements: Contributor (test)"])
        def testIt():
            self.assertNotEqual(self.requirement.is_defined, 1)
            url = '/api/v1/collection/spec_object/{cdb_object_id}'.format(cdb_object_id=self.requirement.cdb_object_id)
            title = 'the new title'
            body = 'the new body'
            richtext = '<xhtml:div><xhtml:div>{title}</xhtml:div><xhtml:div>{body}</xhtml:div></xhtml:div>'.format(body=body, title=title)
            for iso in ['de', 'en']:
                attr_name = 'cdbrqm_spec_object_desc_{iso}'.format(iso=iso)
                short_attr_name = 'name_{iso}'.format(iso=iso)
                self.assertNotEqual(self.requirement.GetText(attr_name), richtext)
                self.assertNotEqual(getattr(self.requirement, short_attr_name), title)
                self.client.put_json(url, {attr_name: richtext}, status=403)
                self.requirement.Reload()
                self.assertNotEqual(self.requirement.GetText(attr_name), richtext)
                self.assertNotEqual(getattr(self.requirement, short_attr_name), title)
            self.client.put_json(url, {'is_defined': 1})
            self.requirement.Reload()
            self.assertEqual(self.requirement.is_defined, 1)
        testIt()

    def test_richtext_permission_contributor_test_only_meta_pcclient_with_image(self):
        """ Check whether an user with 'save' but not 'rqm_richtext_save' permission cannot change a requirement description but meta data for requirements which have images (inner)"""

        @run_with_roles(["public", "Requirements: Contributor (test)"])
        def testIt():
            description = u'test456'
            with self.assertRaises(ElementsError) as cm:
                richtext_desc = u'{"de": "<xhtml:div>%s</xhtml:div>","en": "<xhtml:div></xhtml:div>"}' % description
                self.assertNotEqual(self.requirement_with_object.GetText('cdbrqm_spec_object_desc_de'), u"<xhtml:div>%s</xhtml:div>" % description)
                r = operations.operation('CDB_Modify', self.requirement_with_object, operations.form_input(
                    RQMSpecObject,
                    **{
                        '.richtext_desc': richtext_desc
                    }
                ))
            self.assertIn(str(ue.Exception('cdbrqm_desc_change_perm_miss')), str(cm.exception))
            self.assertNotEqual(self.requirement_with_object.GetText('cdbrqm_spec_object_desc_de'), u"<xhtml:div>%s</xhtml:div>" % description)
            r = interactive_operation("CDB_Modify", self.requirement_with_object, user_input={'is_defined': 1})
            self.assertEqual(r.is_defined, 1)
        testIt()

    def test_richtext_permission_contributor_test_only_meta_rest_with_image(self):
        """ Check whether an user with 'save' but not 'rqm_richtext_save' permission cannot change a requirement description but meta data for requirements which have images via REST (inner)"""
        @run_with_roles(["public", "Requirements: Contributor (test)"])
        def testIt():
            self.assertNotEqual(self.requirement_with_object.is_defined, 1)
            url = '/api/v1/collection/spec_object/{cdb_object_id}'.format(cdb_object_id=self.requirement_with_object.cdb_object_id)
            title = 'the new title'
            body = 'the new body'
            richtext = '<xhtml:div><xhtml:div>{title}</xhtml:div><xhtml:div>{body}</xhtml:div></xhtml:div>'.format(body=body, title=title)
            for iso in ['de', 'en']:
                attr_name = 'cdbrqm_spec_object_desc_{iso}'.format(iso=iso)
                short_attr_name = 'name_{iso}'.format(iso=iso)
                self.assertNotEqual(self.requirement_with_object.GetText(attr_name), richtext)
                self.assertNotEqual(getattr(self.requirement_with_object, short_attr_name), title)
                self.client.put_json(url, {attr_name: richtext}, status=403)
                self.requirement_with_object.Reload()
                self.assertNotEqual(self.requirement_with_object.GetText(attr_name), richtext)
                self.assertNotEqual(getattr(self.requirement_with_object, short_attr_name), title)
            self.client.put_json(url, {'is_defined': 1})
            self.requirement_with_object.Reload()
            self.assertEqual(self.requirement_with_object.is_defined, 1)
        testIt()

    def test_classification_timestamps(self):

        @run_with_roles(["public", "Requirements: Manager"])
        def testIt():
            spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
            req = spec.Requirements.KeywordQuery(specobject_id=u'RT000000000')[0]
            classification = classification_api.get_new_classification(["RQM_RATING"])
            classification_api.update_classification(req, classification)
            req.Reload()
            req_classification = classification_api.get_classification(req)
            timestamp = req_classification['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value']
            time.sleep(1)
            classification_api.update_classification(req, req_classification)
            self.assertEqual(timestamp, req_classification['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value'])
            req_classification['properties']['RQM_RATING_RQM_RATING_VALUE'][0]['value']['de']['text_value'] = False
            classification_api.update_classification(req, req_classification)
            self.assertNotEqual(timestamp, req_classification['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value'])

            classification = classification_api.get_new_classification(["RQM_RATING", "RQM_TEST01"])
            classification_api.update_classification(req, classification)
            req.Reload()
            req_classification = classification_api.get_classification(req)
            timestamp = req_classification['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value']
            req_classification['properties']['RQM_TEST01_test_date_einwertig_enum'].append(
                {
                    'id': u'0458ed70-3e51-11e8-a885-cb5b1e310df5',
                    'property_type': u'datetime',
                    'value': datetime.datetime(2018, 2, 23, 0, 0)
                }
            )
            time.sleep(1)
            classification_api.update_classification(req, req_classification)
            self.assertEqual(timestamp, req_classification['properties']['RQM_RATING_RQM_RATING_MDATE'][0]['value'])
        testIt()

    def test_rating_by_contributor_works(self):
        @run_with_roles(["public", "Requirements: Contributor"])
        def testIt():
            spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
            req = spec.Requirements.KeywordQuery(specobject_id=u'RT000000000')[0]
            classification = classification_api.get_new_classification(["RQM_RATING"])
            classification_api.update_classification(req, classification)
        testIt()

    def test_req_change_by_contributor_fails(self):
        @run_with_roles(["public", "Requirements: Contributor"])
        def testIt():
            spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
            req = spec.Requirements.KeywordQuery(specobject_id=u'RT000000000')[0]
            with self.assertRaises(ElementsError):
                operations.operation("CDB_Modify", req, weight=4)
        testIt()
