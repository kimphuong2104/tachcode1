# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import os
import re
import shutil

from selenium.common.exceptions import WebDriverException

from cdb import CADDOK, transactions
from cdb.objects import operations
from cdb.testcase import run_level_setup
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.web.tests.test_specificationeditor import TableMixin
from cs.web.automation import WebTest


class TestCreateFromTemplateApp(WebTest, TableMixin):

    @classmethod
    def setup_class(cls):
        run_level_setup()
        super(TestCreateFromTemplateApp, cls).setUpClass()

    def setUp(self):
        WebTest.setUp(self)
        self._prepare_data()

    def tearDown(self):
        WebTest.tearDown(self)
        self._delete_data()

    def _delete_data(self):
        with transactions.Transaction():
            if self.spec:
                for s in RQMSpecification.KeywordQuery(spec_id=self.spec.spec_id):
                    for t in s.TargetValues:
                        t.Delete()
                    for r in s.Requirements:
                        r.Delete()
                    s.Delete()
            if self.copied_spec_id:
                for s in RQMSpecification.KeywordQuery(spec_id=self.copied_spec_id):
                    for t in s.TargetValues:
                        t.Delete()
                    for r in s.Requirements:
                        r.Delete()
                    s.Delete()

    @run_with_roles(["public", "Requirements: Manager"])
    def _prepare_data(self):
        self.copied_spec_id = None
        self.spec = operations.operation(
            'CDB_Create', RQMSpecification, name='E061272: New from template (Web)', is_template=1
        )
        self.req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMTemplate Req 001</xhtml:div>'
        )
        self.req2 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMTemplate Req 002</xhtml:div>'
        )
        self.tv1 = operations.operation(
            'CDB_Create',
            TargetValue,
            specification_object_id=self.spec.cdb_object_id,
            requirement_object_id=self.req1.cdb_object_id,
            cdbrqm_target_value_desc_en='<xhtml:div>RQMTemplate TV 001</xhtml:div>'
        )
        self.new_req = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMTemplate Req 003</xhtml:div>'
        )
        self.new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            specification_object_id=self.spec.cdb_object_id,
            requirement_object_id=self.new_req.cdb_object_id,
            cdbrqm_target_value_desc_en='<xhtml:div>RQMTemplate TV 002</xhtml:div>'
        )
        self.spec.ChangeState(RQMSpecification.REVIEW)
        self.spec.ChangeState(RQMSpecification.RELEASED)

    def test_create_spec_from_template(self):
        # Navigate to copy from template page
        # Filter the template Specification created for the test
        # Copy it and update the name
        # Check the name of the copied Specification
        # Check the requirements in the copied Specification against the template requirements
        self.navigate_to("/cs-requirements-web-TemplateCreateApp/specification")
        self.disable_animations()
        # Filter the test template
        filter_field = self.wait_for_element_by_css('input[name=cs-web-components-base-table-filter')
        filter_field.send_keys(self.spec.spec_id)

        table_container = self.wait_for_element_by_css(".cs-web-components-base-table-catalog")
        self.spec_row_selection = self.get_row_by_key_part(
            table_container, self.spec.cdb_object_id
        )
        self.spec_row_selection.click()
        
        continue_button = self.wait_for_element_by_css(
            ".cs-web-components-base-form-actions .cs-web-components-base-semantic-button-primary"
        )
        self._driver.get_screenshot_as_file(
            os.path.join(CADDOK.TMPDIR, 'test_create_spec_from_template_before_continue.png')
        )
        continue_button.click()
        self._driver.get_screenshot_as_file(
            os.path.join(CADDOK.TMPDIR, 'test_create_spec_from_template_after_continue.png')
        )
        success = False
        for try_number in range(0, 3):
            try:
                title_field = self.wait_for_element_by_css("input[name='cdbrqm_specification.name']")
                title_field.send_keys("- Copied for testing purposes")
                self._driver.get_screenshot_as_file(
                    os.path.join(CADDOK.TMPDIR, 'test_create_spec_from_template_%d_after_text.png' % try_number)
                )
                title_field = self.wait_for_element_by_css("input[name='cdbrqm_specification.name']")
                self.assertIn('for testing', title_field.get_attribute('value'))
                success = True
                break
            except (AssertionError, WebDriverException):
                try:
                    self._driver.get_screenshot_as_file(
                        os.path.join(CADDOK.TMPDIR, 'test_create_spec_from_template_%d.png' % try_number)
                    )
                    shutil.copytree(os.path.join(CADDOK.BASE, 'etc'), os.path.join(CADDOK.TMPDIR, 'etc'))
                    shutil.copytree(os.path.join(CADDOK.BASE, 'certs'), os.path.join(CADDOK.TMPDIR, 'certs'))
                except BaseException:
                    pass
        self.assertTrue(success)

        for _ in range(0, 3):
            try:
                copy_button = self.get_ce_element("type-0")
                copy_button.click()
            except (AttributeError, WebDriverException):
                pass

        # Check values of the copied specification
        title_label = self.wait_for_element_by_css(".cs-web-components-base-object-header__description")
        title_label_str = title_label.text
        spec_id_matcher = re.compile(".*\((S\d+/\d+)\).*")
        match = spec_id_matcher.match(title_label_str)
        if match:
            groups = match.groups()[0].split('/')
            spec_from_template_id = groups[0]
            spec_from_template_rev = groups[1]
        # Query the created spec
        spec_from_template = RQMSpecification.ByKeys(
            spec_id=spec_from_template_id, revision=spec_from_template_rev, ce_baseline_id='')
        self.assertNotEqual(
            spec_from_template, None,
            'Failed to get %s with %s and %s' % (
                title_label_str, spec_from_template_id, spec_from_template_rev
            )
        )
        # Save spec for deletion afterwards
        self.copied_spec_id = spec_from_template_id
        # Check that the copied spec is an instance of the template
        self.assertEqual(spec_from_template.template_oid, self.spec.cdb_object_id)
        # Query the specifications
        title_label_expected = 'E061272: New from template (Web)- Copied for testing purposes'
        self.assertIn(title_label_expected, title_label_str)  # Copy of semantic link

        # Create dictionary with Requirements from queried Spec
        reqs_copied_spec = {req.name: req for req in spec_from_template.Requirements}
        tv_copied_spec = {}
        # Iterate over reqs in template spec and compare semantic links
        for req in self.spec.Requirements:
            template_req_name = req.name
            copied_req = reqs_copied_spec[template_req_name]
            self.assertEqual(req.cdb_object_id, copied_req.template_oid)
            self.assertEqual(template_req_name, copied_req.name)
            # Fill target values dict
            for tv in req.TargetValues:
                tv_copied_spec[template_req_name] = {"name": tv.name, "id": tv.cdb_object_id}
        # Check target values
        for req in spec_from_template.Requirements:
            for tv in req.TargetValues:
                self.assertEqual(tv.template_oid, tv_copied_spec[req.name]["id"])
                self.assertEqual(tv.name, tv_copied_spec[req.name]["name"])
