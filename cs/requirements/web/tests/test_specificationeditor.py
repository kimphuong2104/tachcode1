# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals
import getpass

import logging
import os
import time

from cdb import auth, CADDOK, sqlapi, transactions
from cdb.objects import operations
from cdb.testcase import run_level_setup
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.classification import api as classification_api
from cs.platform.web.uisupport import get_webui_link
from cs.requirements import (RQMSpecification, RQMSpecObject, TargetValue,
                             rqm_utils)
from cs.requirements.richtext import RichTextVariables
from cs.requirements.tests.utils import robust_run
from cs.web.automation import WebTest, xpath_for_table_row
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.common.by import By

LOG = logging.getLogger(__name__)

class ZoomMixin(object):
    def set_page_zoom(self, zoom_percent: float):
        if self._driver.capabilities['browserName'] == 'chrome':
            try:
                zoom_level = zoom_percent / 100.0
                self._driver.get("chrome://settings/")
                self._driver.execute_script(
                    "chrome.settingsPrivate.setDefaultZoom({zoom_level});".format(
                        zoom_level=zoom_level
                    )
                )
                LOG.info("set browser zoom level to %s (%s)", zoom_level, zoom_percent)
            except BaseException:
                LOG.warning("set_page_zoom failed to set %s", zoom_percent)
        else:
            LOG.warning("set_page_zoom is currently only supported using chrome")

class SideBarMixin(object):
    def hide_sidebar(self):
        sidebar_element = self.get_ce_element('ApplicationSidebar')
        # if not wrapper_element.get_attribute('class'):
        if sidebar_element.get_ce_state() != 'collapsed':
            menu_button = sidebar_element.find_element(
                By.CSS_SELECTOR, ".cs-web-components-base-application-frame__menu-button"
            )
            menu_button.click()

class TableMixin(object):
    def get_row_by_key_part(self, container, key_part, max_tries=3):
        def get_row_by_key_part_inner(container, key_part):
            xpath = xpath_for_table_row(key_part)
            return container.wait_for_element_by_xpath(xpath)
        
        def fail_handler(name, cnt):
            self._driver.execute_script('console.log($x("*//tbody/tr[1]/@data-row-id")[0].value)')

        return robust_run(
            self._driver, 'get_row_by_key_part',
            get_row_by_key_part_inner, 3, container, key_part,
            fail_handler=fail_handler
        )

class OverlayMixin(object):
    def get_overlay_container(self):
        overlay_container = self.wait_for(lambda _: (self._driver.find_element(By.ID, "cs-web-components-base-overlay-container")))
        return overlay_container

    def get_overlay_menu_item(self, select_key):
        container = self.get_overlay_container()
        css_query = "li[data-ce-select-key={select_key}] a".format(select_key=select_key)
        self.wait_for(lambda _: (container.find_element(By.CSS_SELECTOR, css_query)))
        return container.find_element(By.CSS_SELECTOR, css_query)

    def get_overlay_menu_item_by_content(self, container, content):
        return container.wait_for_element_by_xpath("*//a/span/span[contains(text(), '%s')]/../.." % content)
    
class SpecificationEditorMixin(TableMixin):
    def get_editor_container(self):
        editor_container = self.wait_for_element_by_css(".cs-requirements-web-specification-editor-editor")
        return editor_container

    def get_requirement_description_in_modal_op(self):
        css_query = ".cs-requirements-web-weblib-richtext-container .public-DraftEditor-content"
        description_container = self.wait_for_element_by_css(css_query)
        if description_container and description_container.is_displayed():
            return description_container

    def get_requirements_in_editor(self):
        container = self.get_editor_container()
        css_query = ".cs-requirements-web-specification-editor-requirement .public-DraftEditor-content"
        self.wait_for(lambda _: (container.find_elements(By.CSS_SELECTOR, css_query)))
        return [x for x in container.find_elements(By.CSS_SELECTOR, css_query) if x.is_displayed()]

    def get_editor_toolbar_buttons(self):
        container = self.get_editor_container()
        css_query = ".cs-requirements-web-specification-editor-requirement-toolbar button"
        self.wait_for(lambda _: (container.find_elements(By.CSS_SELECTOR, css_query)))
        return [x for x in container.find_elements(By.CSS_SELECTOR, css_query) if x.is_displayed()]

    def switch_editor_language(self, language):
        language_field_selector = "#cs-requirements-web-specification-editor-editor-data-language-selection"
        lf_selector = self.wait_for_element_by_css(language_field_selector)
        lf_selector.click()
        language_select_key = "cs-requirements-web-specification-editor-i18n-" + language
        lf_menu_item = self.get_overlay_menu_item(language_select_key)
        if lf_menu_item:
            lf_menu_item.click()
            return True
        return False
    
    def get_draftjs_writeable_editor(self):
        container = self.get_editor_container()
        css_query = ".public-DraftEditor-content[contenteditable=true]"
        return container.find_element(By.CSS_SELECTOR, css_query)
    
    def add_text_into_requirement(self, requirement, text):
        requirement.click()
        draftjs_editor = self.get_draftjs_writeable_editor()
        draftjs_editor.send_keys(text)
        self.save_draftjs_editor()
    
    def save_draftjs_editor(self):
        container = self.get_editor_container()
        css_query = ".cs-requirements-web-specification-editor-save-button"
        save_button = container.wait_for_element_by_css(css_query)
        save_button.click()
        time.sleep(1)
    
    def add_variable_into_requirement(self, requirement, uc_prop_object_id):
        try:
            container = self.get_editor_container()
            requirement.click()
            self.get_draftjs_writeable_editor()
            css_query = ".cs-requirements-web-specification-editor-variables-button"
            variables_button = container.wait_for_element_by_css(css_query)
            variables_button.click()
            variables_dialog_css = ".cs-requirements-web-specification-editor-variables-button-dialog"
            variable_dialog = self.wait_for_element_by_css(variables_dialog_css)
            table_row_to_select = self.get_row_by_key_part(variable_dialog, key_part=uc_prop_object_id)
            table_row_to_select.click()
            variable_dialog_btn_select_css = "[data-ce-id=flatcatalog-action-] .btn-default"
            variable_dialog_btn_select = variable_dialog.wait_for_element_by_css(variable_dialog_btn_select_css)
            variable_dialog_btn_select.click()
            time.sleep(1)
            self.save_draftjs_editor()
            time.sleep(1)
        except (TimeoutException, ElementClickInterceptedException):
            self._driver.get_screenshot_as_file(
                os.path.join(
                    CADDOK.TMPDIR, 
                    'add_variable_into_requirement_failed.png'
                )
            )
            LOG.error("add_variable_into_requirement failed")
            raise

class TestSpecificationEditorApp(
    WebTest, SpecificationEditorMixin, OverlayMixin, SideBarMixin, ZoomMixin
):
    default_variable_id = "RQM_RATING_RQM_COMMENT_EXTERN"
    default_uc_property = "RQM_RATING_RQM_COMMENT_EXTERN"
    default_uc_class = "RQM_RATING"
    default_uc_property_value = "### test comment ###"

    @classmethod
    def setUpClass(cls):
        run_level_setup()
        super(TestSpecificationEditorApp, cls).setUpClass()

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
        from cdb import auth
        LOG.info("trying to prepare using auth: %s", auth.persno)
        self.spec = operations.operation(
            'CDB_Create', RQMSpecification, name='RQMSpecificationEditor Spec 001'
        )
        self.req1 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMSpecificationEditor Req 001</xhtml:div>',
            position=1
        )
        self.req2 = operations.operation(
            'CDB_Create',
            RQMSpecObject,
            specification_object_id=self.spec.cdb_object_id,
            cdbrqm_spec_object_desc_en='<xhtml:div>RQMSpecificationEditor Req 002</xhtml:div>',
            position=2
        )
        self.tv1 = operations.operation(
            'CDB_Create',
            TargetValue,
            specification_object_id=self.spec.cdb_object_id,
            requirement_object_id=self.req1.cdb_object_id,
            cdbrqm_target_value_desc_en='<xhtml:div>RQMSpecificationEditor TV 001</xhtml:div>'
        )
        operations.operation("cdbrqm_update_sortorder", self.spec)
        self.assertEqual(int(self.req1.chapter), 1)
        self.assertEqual(int(self.req2.chapter), 2)
        self.req1_classification_value = self._add_class_classification_to_req(self.req1)
    
    def _navigate_to_spec_in_en(self):
        url = get_webui_link(None, self.spec)
        self.navigate_to(url)
        self.disable_animations()
        self.switch_editor_language("en")
    
    def _add_class_classification_to_req(self, requirement, uc_class_code=None, uc_class_prop_code=None, value=None):
        # take care it overwrites all other classification!
        if uc_class_code is None:
            uc_class_code = self.default_uc_class
        if uc_class_prop_code is None:
            uc_class_prop_code = self.default_uc_property
        if value is None:
            value = self.default_uc_property_value    
        classification_data = classification_api.get_new_classification(
            [uc_class_code], narrowed=False
        )
        classification_data['properties'][uc_class_prop_code][0]['value'] = value
        classification_api.update_classification(requirement, classification_data)
        return value
    
    def _set_variable_into_requirement_backend(self, requirement, variable_id=None):
        if variable_id is None:
            variable_id = self.default_variable_id
        variable_richtext = """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        )
        requirement.SetText("cdbrqm_spec_object_desc_de", variable_richtext)
        requirement.SetText("cdbrqm_spec_object_desc_en", variable_richtext)

    def test_specification_editor_can_edit_add_variable_to_a_requirement(self):
        self._navigate_to_spec_in_en()
        requirements_in_editor = self.get_requirements_in_editor()
        # RQM_RATING_RQM_COMMENT_EXTERN
        self.add_variable_into_requirement(
            requirements_in_editor[0], uc_prop_object_id="eb0ea209-434d-11ea-89f0-a08cfdd70ffa"
        )
        self._driver.refresh()
        self._navigate_to_spec_in_en()
        requirements_in_editor = self.get_requirements_in_editor()
        self.assertIn(self.req1_classification_value, requirements_in_editor[0].text)

    def test_specification_editor_can_edit_a_requirement(self):
        self._navigate_to_spec_in_en()
        requirements_in_editor = self.get_requirements_in_editor()
        new_text = " - Something new..."
        self.add_text_into_requirement(requirements_in_editor[1], new_text)
        self._driver.refresh()
        self.switch_editor_language("en")
        requirements_in_editor = self.get_requirements_in_editor()
        self.assertEqual(len(requirements_in_editor), 2)
        self.assertEqual(
            requirements_in_editor[0].text, 
            "{} {}".format(self.req1.chapter, rqm_utils.strip_tags(self.req1.GetText('cdbrqm_spec_object_desc_en')))
        )
        self.assertIn(new_text, self.req2.GetText('cdbrqm_spec_object_desc_en'))
        self.assertEqual(
            requirements_in_editor[1].text, 
            "{} {}".format(self.req2.chapter, rqm_utils.strip_tags(self.req2.GetText('cdbrqm_spec_object_desc_en')))
        )
        
    def test_specification_editor_can_be_opened_and_show_the_spec_requirements(self):
        self._navigate_to_spec_in_en()
        requirements_in_editor = self.get_requirements_in_editor()
        self.assertEqual(len(requirements_in_editor), 2)
        self.assertEqual(
            requirements_in_editor[0].text, 
            "{} {}".format(self.req1.chapter, rqm_utils.strip_tags(self.req1.GetText('cdbrqm_spec_object_desc_en')))
        )
        self.assertEqual(
            requirements_in_editor[1].text, 
            "{} {}".format(self.req2.chapter, rqm_utils.strip_tags(self.req2.GetText('cdbrqm_spec_object_desc_en')))
        )

    def test_specification_editor_modify_operation_can_be_opened_with_variables(self):
        self._set_variable_into_requirement_backend(self.req1)
        try:
            self._driver.get_screenshot_as_file(
                os.path.join(
                    CADDOK.TMPDIR, 
                    'test_specification_editor_modify_operation_can_be_opened_with_variables_before_navigation.png'
                )
            )
            self._navigate_to_spec_in_en()
            self._driver.get_screenshot_as_file(
                os.path.join(
                    CADDOK.TMPDIR, 
                    'test_specification_editor_modify_operation_can_be_opened_with_variables_after_navigation.png'
                )
            )
            buttons = self.get_editor_toolbar_buttons()
            buttons[0].click()
            self._driver.get_screenshot_as_file(
                os.path.join(
                    CADDOK.TMPDIR, 
                    'test_specification_editor_modify_operation_can_be_opened_with_variables_toolbar_opened.png'
                )
            )
            overlay_container = self._enhance_web_element(self.get_overlay_container())
            modify_operation_link = self.get_overlay_menu_item_by_content(overlay_container, "Ändern")
            if modify_operation_link:
                modify_operation_link.click()
                self._driver.get_screenshot_as_file(
                    os.path.join(
                        CADDOK.TMPDIR, 
                        'test_specification_editor_modify_operation_can_be_opened_with_variables_modify_op.png'
                    )
                )
                description_node = self.get_requirement_description_in_modal_op()
                expected = "{}={}".format(self.default_variable_id, self.default_uc_property_value)
                self.assertNotEqual(description_node, None)
                self.assertIn(expected, description_node.text)
        except (AssertionError, TimeoutException):
            self._driver.get_screenshot_as_file(
                os.path.join(
                    CADDOK.TMPDIR, 
                    'test_specification_editor_modify_operation_can_be_opened_with_variables_error.png'
                )
            )
            LOG.exception("test_specification_editor_modify_operation_can_be_opened_with_variables failed")
            raise
