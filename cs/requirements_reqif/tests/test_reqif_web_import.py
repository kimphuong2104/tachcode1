# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import logging
import os
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from cdb.objects.operations import operation
from cdb.validationkit.util import login_webdriver, get_server_url
from cs.requirements import RQMSpecification
from cs.requirements.tests.utils import RequirementsNoRollbackTestCase, robust_run
from cs.web import automation
from cdb import rte

LOG = logging.getLogger(__name__)


def start_op(driver, operation_names):
    LOG.info('start_op')
    detail_page_object_header = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".cs-web-components-base-object-header__main"))
    )
    LOG.info('1')
    ActionChains(driver).context_click(detail_page_object_header).perform()  
    LOG.info('2')
    for operation_name in operation_names:
        overlay_container_ops = WebDriverWait(driver, 120).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#cs-web-components-base-overlay-container a .cs-web-components-base-icon-and-label__label"))
        )
        for op in overlay_container_ops:
            if op.text == operation_name:
                op.click()
                LOG.info('3')
                break


def insert_file_into_filedrop_area(driver, import_path):
    LOG.info('insert_file_into_filedrop_area')
    selector = ".cs-web-components-base-operation-file-dropzone__wrapper input.cs-web-components-base-file-droparea-trigger"
    dropzone_input = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((
            By.CSS_SELECTOR,
            selector
        ))
    )
    LOG.info('7')
    dropzone_input.send_keys(import_path)
    LOG.info('8')


def run_operation(driver):
    LOG.info('run_operation')
    selector = "button[data-ce-id=type-0]"
    submit_button = WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((
            By.CSS_SELECTOR,
            selector
        ))
    )
    submit_button.click()


def disable_animations(driver):
    LOG.info('disable_animations')
    # try to disable as much animations as possible
    res = driver.execute_script("document.getElementsByTagName('body')[0].style='transition-property: none !important;-o-transition-property: none !important;-moz-transition-property: none !important;-ms-transition-property: none !important;-webkit-transition-property: none !important;transform: none !important;-o-transform: none !important;-moz-transform: none !important;-ms-transform: none !important;-webkit-transform: none !important;animation: none !important;-o-animation: none !important;-moz-animation: none !important;-ms-animation: none !important;-webkit-animation: none !important;'")
    LOG.info(res)


def cleanup_spec(specification_url):
    spec_object_id = specification_url.split('/')[-1]
    spec = RQMSpecification.ByKeys(cdb_object_id=spec_object_id)
    if not spec:
        LOG.error('specification_url is wrong: %s', specification_url)
    # LOG.error('Deleting all elements within %s in 5 seconds', spec)
    # time.sleep(5)
    for r in spec.Requirements:
        r.Delete()
    for t in spec.TargetValues:
        t.Delete()
    time.sleep(1)
    spec.Reload()
    LOG.error('Deleted all elements within %s waiting for backend to be in sync', spec)
    time.sleep(10)


def wait_for_first_requirement_as_richtext_editor(driver):
    any_richtext_editor_text = WebDriverWait(driver, 300).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-text=true]"))
    )
    LOG.info('found first richtext editor text: %s', any_richtext_editor_text.text)


def check_result(specification_url, top_req_cnt, req_cnt, any_req_description):
    spec_object_id = specification_url.split('/')[-1]
    spec = RQMSpecification.ByKeys(cdb_object_id=spec_object_id)
    spec.Reload()
    assert len(spec.TopRequirements) == top_req_cnt, 'wrong count of top requirements %d vs %d' % (len(spec.TopRequirements), top_req_cnt)
    assert len(spec.Requirements) == req_cnt, 'wrong count of requirements %d vs %d' % (len(spec.Requirements), req_cnt)
    found = False
    for r in spec.Requirements:
        if any_req_description in r.GetText('cdbrqm_spec_object_desc_de') or any_req_description in r.GetText('cdbrqm_spec_object_desc_en'):
            found = True
            break
    assert found, '%s not found in requirement descriptions' % any_req_description


def get_chrome_options():
    options = webdriver.ChromeOptions()

    options.ensure_clean_session = True

    # try to disable as much animations as possible
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-app-list-dismiss-on-blur")
    options.add_argument("--disable-core-animation-plugins")
    # options.add_experimental_option('w3c', False)
    options.add_argument("--start-maximized")

    if "CI" in rte.environ:
        # this test is running in GitLab CI
        options.add_argument("headless")
        options.add_argument("window-size=1920,1080")

    return options


def _import(import_path, import_profile, specification_url, top_req_cnt, req_cnt, any_req_description):
    cleanup_spec(specification_url)
    driver = webdriver.Chrome(
        chrome_options=get_chrome_options(),
        service_log_path='chromedriver.log'
    )
    automation.disable_animations(driver)  # disable the animations (cs.web way)
    assert login_webdriver(driver=driver), 'login failed'
    driver.get(specification_url)
    automation.disable_animations(driver)  # disable the animations (cs.web way)
    try:
        disable_animations(driver)
        robust_run(
            driver, 'test_import_CDB_start_op',
            start_op, 3, driver, operation_names=['ReqIF', 'Import']
        )
        robust_run(
            driver, 'test_import_CDB_insert_file_into_filedrop_area',
            insert_file_into_filedrop_area, 3, driver, import_path=import_path
        )
        robust_run(
            driver, 'test_import_CDB_run_op', run_operation, 3, driver
        )
        robust_run(
            driver, 'test_import_CDB_wait_for_first_req',
            wait_for_first_requirement_as_richtext_editor, 3, driver
        )
        try:
            check_result(
                specification_url,
                top_req_cnt=top_req_cnt,
                req_cnt=req_cnt,
                any_req_description=any_req_description
            )
            LOG.error('success')
            return True
        except AssertionError as e:
            LOG.exception(e)
    finally:
        driver.quit()
    return False


class TestReqIFWebImport(RequirementsNoRollbackTestCase):
    def test_import_CDB(self):
        import_path = os.path.join(os.path.dirname(__file__), 'dummy.reqifz')
        profile_name = 'CIM DATABASE Standard'
        specification = RQMSpecification.ByKeys(reqif_id='cdb-cd07f910-cbe2-46a1-b466-e6f9ce2eeb9d', ce_baseline_id='')
        if not specification:
            specification = RQMSpecification.ByKeys(reqif_id='cd07f910-cbe2-46a1-b466-e6f9ce2eeb9d', ce_baseline_id='')
            if not specification:
                specification = operation('CDB_Create', RQMSpecification, name='TestSpec', reqif_id='cdb-cd07f910-cbe2-46a1-b466-e6f9ce2eeb9d')
        specification_url = get_server_url() + 'info/specification/' + specification.cdb_object_id
        LOG.error('specification url: %s', specification_url)
        self.assertTrue(
            _import(
                import_path=import_path,
                import_profile=profile_name,
                specification_url=specification_url,
                top_req_cnt=8,
                req_cnt=9,
                any_req_description='<xhtml:b>test1</xhtml:b>'
            )
        )
