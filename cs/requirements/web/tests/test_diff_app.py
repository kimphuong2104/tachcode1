# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals
import getpass

import logging
import urllib

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from cdb import auth, sqlapi, transactions
from cdb.objects import operations
from cdb.testcase import run_level_setup
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.platform.web.uisupport import get_webui_link
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.tests.utils import robust_run, screenshot_context
from cs.requirements.web.diff.main import MOUNT_PATH
from cs.requirements.web.rest.diff.diff_indicator_model import \
    DiffCriterionRegistry
from cs.web.automation import WebTest
from cs.requirements.web.tests.test_specificationeditor import TableMixin, OverlayMixin, SideBarMixin, ZoomMixin

LOG = logging.getLogger(__name__)


class TestDiffApp(WebTest, TableMixin, OverlayMixin, SideBarMixin, ZoomMixin):

    @classmethod
    def setup_class(cls):
        run_level_setup()
        super(TestDiffApp, cls).setUpClass()

    def setUp(self):
        WebTest.setUp(self)
        # cleanup previous page state data
        sqlapi.SQLdelete("FROM csweb_ui_settings WHERE persno='%s'" % sqlapi.quote(auth.persno))
        self.hide_sidebar()
        self.set_page_zoom(75 if getpass.getuser() == "khi" else 100)
        self._prepare_data()

    def tearDown(self):
        WebTest.tearDown(self)
        self._delete_data()

    def _delete_data(self):
        with transactions.Transaction():
            for s in RQMSpecification.KeywordQuery(spec_id=self.spec.spec_id):
                for t in s.TargetValues:
                    t.Delete()
                for r in s.Requirements:
                    r.Delete()
                s.Delete()

    @run_with_roles(["public", "Requirements: Manager"])
    def _prepare_data(self):
        self.spec = operations.operation(
            'CDB_Create', RQMSpecification, name='RQMDiffModels Spec 001'
        )
        self.req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMDiffModels Req 001</xhtml:div>'
        )
        self.req2 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMDiffModels Req 002</xhtml:div>'
        )
        self.tv1 = operations.operation(
            'CDB_Create',
            TargetValue,
            specification_object_id=self.spec.cdb_object_id,
            requirement_object_id=self.req1.cdb_object_id,
            cdbrqm_target_value_desc_en='<xhtml:div>RQMDiffModels TV 001</xhtml:div>'
        )
        self.baselined_spec = operations.operation(
            "ce_baseline_create",
            self.spec,
            ce_baseline_name='Baseline1',
            ce_baseline_comment='Baseline1Comment'
        )
        self.new_req = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMDiffModels Req 003</xhtml:div>'
        )
        self.new_tv = operations.operation(
            'CDB_Create',
            TargetValue,
            specification_object_id=self.spec.cdb_object_id,
            requirement_object_id=self.new_req.cdb_object_id,
            cdbrqm_target_value_desc_en='<xhtml:div>RQMDiffModels TV 002</xhtml:div>'
        )
        self.req2.Delete()

    @classmethod
    def generate_diff_url(
            cls,
            left_spec,
            right_spec,
            selected_object=None,
            languages=None,
            criterions=None
    ):
        side = 'right'
        selected_object_id = ''
        if languages is None:
            languages = ['de', 'en']
        if criterions is None:
            criterions = [
                x.get('id') for x in DiffCriterionRegistry.get_criterions(RQMSpecObject)
            ]
        if selected_object:
            side = 'left' if selected_object.specification_object_id == left_spec.cdb_object_id else 'right'
            selected_object_id = selected_object.cdb_object_id
        langs = ",".join(languages)
        crits = ",".join(criterions)
        url = "{basepath}/{left}/{right}?{params}"
        return url.format(
            basepath=MOUNT_PATH,
            left=left_spec.cdb_object_id,
            right=right_spec.cdb_object_id,
            params=urllib.parse.urlencode(
                dict(
                    selected_obj_id=selected_object_id,
                    side=side,
                    criterions=crits,
                    languages=langs
                )
            )
        )

    def test_open_from_bookmark_with_selection(self):
        # navigate to link with selected requirement and two different specs and check whether the
        # diff details are loaded, selection is correct (header plugin check of object description)
        # check number of diffs from stepper, check whether stepper forward correctly selects the next expected one
        # and the stepper previous the first one again
        with screenshot_context(self._driver, "test_open_from_bookmark_with_selection.png"):
            url = self.generate_diff_url(
                self.baselined_spec, self.spec, self.new_req
            )
            LOG.debug('navigate to %s', url)
            self.navigate_to(url)
            self.disable_animations()
            header_link = self.wait_for_element_by_css('.cs-requirements-web-diff-inner-header .cs-requirements-web-diff-truncate a')
            new_req_ui_link = get_webui_link(request=None, target_obj=self.new_req)
            self.assertTrue(header_link.get_attribute('href').endswith(new_req_ui_link.lower()))
            previous_button = self.get_ce_element("search-previous")
            next_button = self.get_ce_element("search-next")
            search_label = self.get_ce_element("search-label")
            # Check initial state of the diff lable
            self.assertEqual(search_label.text, "1 / 2")
            next_button.click()
            # Check updated  state of the diff lable
            self.assertEqual(search_label.text, "2 / 2")
            new_tv_ui_link = get_webui_link(request=None, target_obj=self.new_tv)
            header_link = self.wait_for_element_by_css('.cs-requirements-web-diff-inner-header .cs-requirements-web-diff-truncate a')
            self.assertTrue(header_link.get_attribute('href').endswith(new_tv_ui_link.lower()))
            previous_button.click()
            # Check updated state of the diff lable
            self.assertEqual(search_label.text, "1 / 2")

    def test_open_from_baselining_tab(self):
        # Navigate to Specification detail page webui_link
        # Navigate to baseline tab
        # Select baseline
        # Start diff operation
        # Check number of diffs
        # Check the first diff entry is selected and is displayed in details
        # Select one deleted entry and check whether it is displayed in details
        with screenshot_context(self._driver, "test_open_from_baselining_tab.png"):
            req_ui_link = get_webui_link(request=None, target_obj=self.spec)
            self.navigate_to(req_ui_link)
            self.disable_animations()
            self.hide_sidebar()
            baseline_tab = self.wait_for_element_by_css("li[role=presentation][title=Baselines]")
            baseline_tab.click()
            baseline_tab_data_key = baseline_tab.get_attribute("data-key")
            baseline_tab_body_container_css = "#cs-web-components-base-object-details-pane-{data_key}".format(
                data_key=baseline_tab_data_key
            )
            baseline_tab_body_container = self.wait_for_element_by_css(baseline_tab_body_container_css)
            baseline_tab_first_row = self.get_row_by_key_part(
                baseline_tab_body_container, self.baselined_spec.cdb_object_id
            )
            baseline_tab_first_row.click()

            def open_spec_diff():
                ActionChains(self._driver).context_click(baseline_tab_first_row).perform()  
                operation_name = 'Spezifikationsvergleich'
                overlay_container = self._enhance_web_element(self.get_overlay_container())
                modify_operation_link = self.get_overlay_menu_item_by_content(overlay_container, operation_name)
                if modify_operation_link:
                    modify_operation_link.click()

            robust_run(self._driver, "test_open_from_baselining_tab_open_spec_diff", open_spec_diff, 3)
            header_req_first_link = self.wait_for_element_by_css(
                ".cs-requirements-web-diff-plugin-area .cs-requirements-web-diff-sticky-header a:nth-child(1)"
            )
            req_ui_link = get_webui_link(request=None, target_obj=self.new_req)
            self.assertTrue(
                header_req_first_link.get_attribute('href').endswith(req_ui_link.lower()),
                msg="{} does not endswith {}".format(header_req_first_link.get_attribute('href'), req_ui_link.lower())
            )
            left_object_field = self.wait_for_element_by_css('[data-ce-id=cs-requirements-web-diff-specification-left] input')
            expected_version_label_left = '{baseline_tag}{name} ({id}/{rev})'.format(
                baseline_tag=self.baselined_spec.ce_baseline_info_tag,
                name=self.baselined_spec.name,
                id=self.baselined_spec.spec_id,
                rev=str(self.baselined_spec.revision)
            )
            self.assertEqual(left_object_field.get_attribute("value"), expected_version_label_left)
            right_object_field = self.wait_for_element_by_css('[data-ce-id=cs-requirements-web-diff-specification-right] input')
            expected_version_label_right = '{name} ({id}/{rev})'.format(
                name=self.spec.name, id=self.spec.spec_id, rev=str(self.spec.revision)
            )
            self.assertEqual(right_object_field.get_attribute("value"), expected_version_label_right)

    def test_open_from_search_page(self):
        # Navigate to the Specification page
        # Filter the test specification
        # Select specification
        # Start diff operation
        # Check if left side is empty
        # Select an entry from tree
        # Check that the link in the header plugin updates
        with screenshot_context(self._driver, "test_open_from_search_page.png"):
            search_query = "?search_attributes[0]=cdbrqm_specification.spec_id&search_attributes[1]=.ce_baselines&search_values[0]={spec_id}&search_values[1]=0&search_on_navigate=true"
            search_query = search_query.format(spec_id=self.spec.spec_id)
            self.navigate_to("/info/specification{query}".format(query=search_query))
            self.disable_animations()
            # Get twice to wait for table to load
            search_tab = self.wait_for_element_by_css("li[role=presentation][title='{}; ✗ Baselines?']".format(self.spec.spec_id))
            search_tab.click()
            search_tab_data_key = search_tab.get_attribute("data-key")
            search_tab_body_container_css = "#cs-web-components-base-class-search-tabs-pane-{data_key}".format(
                data_key=search_tab_data_key
            )
            search_tab_body_container = self.wait_for_element_by_css(search_tab_body_container_css)

            def select_searchtable_row():
                WebDriverWait(self._driver, 120).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".table-layout-content.table.table-striped.table-bordered.table-condensed tbody tr"))
                )
                filter_field = self.wait_for_element_by_css('.cs-web-components-base-table-filter-placeholder.cs-web-components-base-form-input.no-ie-text-input-clear-button.form-control')
                filter_field.clear()
                filter_field = self.wait_for_element_by_css('.cs-web-components-base-table-filter-placeholder.cs-web-components-base-form-input.no-ie-text-input-clear-button.form-control')
                filter_field.send_keys(self.spec.spec_id)
                self.spec_row_selection = self.get_row_by_key_part(
                    search_tab_body_container, self.spec.cdb_object_id
                )
                self.spec_row_selection.click()

            def open_spec_diff():
                table_first_row = self.wait_for_element_by_css(".cs-web-components-base-tab__content.tab-content table tbody tr:nth-child(1)")
                ActionChains(self._driver).context_click(table_first_row).perform()  
                operation_names = ['Spezifikationsvergleich']
                for operation_name in operation_names:
                    overlay_container_ops = WebDriverWait(self._driver, 120).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#cs-web-components-base-overlay-container a .cs-web-components-base-icon-and-label__label"))
                    )
                    for op in overlay_container_ops:
                        if op.text == operation_name:
                            op.click()
                            break

            robust_run(
                self._driver, 'test_open_from_search_page_select_search_table_row',
                select_searchtable_row, 3
            )
            robust_run(
                self._driver, 'test_open_from_search_page_open_spec_diff',
                open_spec_diff, 3
            )
            left_object_field = self.wait_for_element_by_css('[data-ce-id=cs-requirements-web-diff-specification-left] input')
            self.assertEqual(left_object_field.get_attribute("value"), "")
            right_object_field = self.wait_for_element_by_css('[data-ce-id=cs-requirements-web-diff-specification-right] input')
            expected_version_label_right = '{name} ({id}/{rev})'.format(name=self.spec.name, id=self.spec.spec_id, rev=str(self.spec.revision))
            self.assertEqual(right_object_field.get_attribute("value"), expected_version_label_right)
            tree_table_rows = WebDriverWait(self._driver, 120).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".table-layout-content.table.table-striped.table-bordered.table-condensed tbody tr"))
            )
            self.assertEqual(len(tree_table_rows), 3)
            for row in tree_table_rows:
                if "RQMDiffModels Req 001" in row.text:
                    row.click()
                    break
            header_link = self.wait_for_element_by_css(".cs-requirements-web-diff-space-between-header.cs-requirements-web-diff-inner-header a")
            req_ui_link = get_webui_link(request=None, target_obj=self.req1)
            self.assertTrue(header_link.get_attribute('href').endswith(req_ui_link.lower()))
