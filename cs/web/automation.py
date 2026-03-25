#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
# File: selenium
# Author: cla
# Creation: 18.03.2016
# Purpose:

from __future__ import absolute_import, print_function

import contextlib
import logging
import os
import time
import types

import psutil
import six
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, ElementNotVisibleException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from cdb import CADDOK
from cdb.testcase import RollbackTestCase, require_service
from cdb.validationkit.util import get_server_url, login_webdriver

WEBUI_USER_MENU_CSS_SELECTOR = '.cs-web-components-base-titlebar__usermenu'
WEBUI_MENU_LOGOUT = 'cs-web-components-base-webui_menu_logout'

DEFAULT_TIMEOUT = 20

LOG = logging.getLogger(__name__)


class SidebarMixin(object):
    """
    Mixin to control the ApplicationSidebar of the Application.

    .. code-block:: python

        with self.sidebar_expanded() as sidebar:
            pass
    """
    @contextlib.contextmanager
    def sidebar_expanded(self):
        try:
            sidebar_element = self.get_ce_element('ApplicationSidebar')
            # if not wrapper_element.get_attribute('class'):
            if sidebar_element.get_ce_state() == 'collapsed':
                burger_element = self.get_ce_element('Burger')
                burger_element.click()

            yield sidebar_element

        finally:
            burger_element = self.get_ce_element('Burger')
            burger_element.click()  # Einklappen
            self.wait_for(lambda _: not self.get_ce_element('FavoritesView',
                                                            parent=sidebar_element).is_displayed())


class ModalStillOpenException(BaseException):
    pass


class ModalNotOpenException(BaseException):
    pass


class ModalMixin(object):
    """
    Mixin to find a modal in the Application
    """

    def get_modal_xpath(self, sub_xpath=None):
        xpath = '/html/body/*//div[@role=\'dialog\']'
        if sub_xpath is not None:
            xpath = xpath + sub_xpath
        return xpath

    def get_modal(self):
        try:
            return self.wait_for_element_by_xpath(self.get_modal_xpath())
        except TimeoutException:
            return None

    @contextlib.contextmanager
    def modal(self, raise_if_open_on_exit=True):
        """
        Modal dialog context manager
        to write test code which should be executed in context of a modal.

            .. code-block:: python

        with self.modal(raise_if_open_on_exit=True) as modal:
            pass
        """
        try:
            modal = self.get_modal()
            if modal is None:
                raise ModalNotOpenException()
            yield modal
        except TimeoutException:
            raise ModalNotOpenException()
        finally:
            if raise_if_open_on_exit:
                try:
                    self.wait_for_not_element_by_xpath(self.get_modal_xpath())
                    if self.get_modal() is not None:
                        raise ModalStillOpenException()
                except TimeoutException:
                    raise ModalStillOpenException()


class TableMixin(object):
    def get_table_rows(self, element):
        self.wait_for(lambda _: (element.find_elements(By.CLASS_NAME, 'fixedDataTableRowLayout_rowWrapper')))
        return element.find_elements(By.CLASS_NAME, 'fixedDataTableRowLayout_rowWrapper')


class OverlayMixin(object):
    def get_overlay_container(self):
        overlay_container = self.wait_for(lambda _: (
            self._driver.find_element(By.ID, "cs-web-components-base-overlay-container")
        ))
        return WebTest._enhance_web_element(overlay_container)

    def get_overlay_menu_item(self, select_key):
        container = self.get_overlay_container()
        css_query = "li[data-ce-select-key={select_key}] a".format(select_key=select_key)
        self.wait_for(lambda _: (container.find_element(By.CSS_SELECTOR, css_query)))
        return container.find_element(By.CSS_SELECTOR, css_query)

    def get_overlay_menu_item_by_content(self, content):
        container = self.get_overlay_container()
        return container.wait_for_element_by_xpath("*//a/span/span[contains(text(), '%s')]/../.." % content)

def by_ce_id(ce_id):
    return By.XPATH, WebTest.ce_id_to_xpath(ce_id)


def xpath_for_table_row(persistent_id):
    return "*//tbody/tr[contains(concat(' ', @data-row-id,' '), '%s')]/td[1]" \
        % (persistent_id,)


def disable_animations(webdriver):
    """
    This methods disables all (or at least most) animations within the WebUI to ease
    automated testing. To use it in a test, it must be called each time the
    webdriver has loaded a new page.

    :param webdriver: the webdriver (chromedriver/iedriver/...) instance
    """
    script = 'document.querySelector("body").classList.add("animations-transitions-disabled");'
    webdriver.execute_script(script)


class WebTest(RollbackTestCase):

    kill_leaked_servers = False

    def get_username(self):
        """ This method returns the username which should be used to login into the system and
        is intended to be overwritten in sub classes"""
        return os.environ.get('INSTANCE_TEST_USER', 'caddok')

    def get_password(self):
        """ This method returns the password which should be used to login into the system and
        is intended to be overwritten in sub classes"""
        return os.environ.get('INSTANCE_TEST_PWD', '')

    def get_language(self):
        """ This method returns the language which should be used to login into the system and
        is intended to be overwritten in sub classes"""
        return 'de'

    @classmethod
    def setUpClass(cls):
        super(WebTest, cls).setUpClass()
        require_service("cdb.uberserver.services.apache.Apache")

    @staticmethod
    def ce_id_to_xpath(ce_id):
        return ".//*[@data-ce-id='%s']" % ce_id

    def create_action_chains(self):
        return ActionChains(self._driver)

    def _create_ce_element(self, element):
        setattr(element, 'get_ce_state',
                types.MethodType(lambda lself: lself.get_attribute("data-ce-state"), element))
        setattr(element, 'get_ce_element',
                types.MethodType(lambda lself, lelements_id: self.get_ce_element(lelements_id, parent=lself), element))
        element = WebTest._enhance_web_element(element)
        return element

    def get_ce_element(self, elements_id, parent=None):
        return self._create_ce_element(
            (parent if parent else self._driver).find_element(By.XPATH, WebTest.ce_id_to_xpath(elements_id)))

    def wait_for(self, condition, timeout=DEFAULT_TIMEOUT):
        return WebDriverWait(self._driver, timeout).until(condition)

    def wait_for_element_by_xpath(self, xpath_str, timeout=DEFAULT_TIMEOUT):
        return WebTest._wait_for_element_by_xpath(self._driver, xpath_str, timeout)

    def wait_for_not_element_by_xpath(self, xpath_str, timeout=DEFAULT_TIMEOUT):
        return WebTest._wait_for_not_element_by_xpath(self._driver, xpath_str, timeout)

    @staticmethod
    def _wait_for_element_by_xpath(element, xpath_str, timeout=DEFAULT_TIMEOUT):
        return WebTest._enhance_web_element(
            WebDriverWait(element, timeout).until(
                EC.visibility_of_element_located(
                    (By.XPATH, xpath_str)
                )
            )
        )

    @staticmethod
    def _wait_for_not_element_by_xpath(element, xpath_str, timeout=DEFAULT_TIMEOUT):
        return WebTest._enhance_web_element(
            WebDriverWait(element, timeout=timeout, ignored_exceptions=(ElementNotVisibleException)).until_not(
                EC.visibility_of_element_located(
                    (By.XPATH, xpath_str)
                )
            )
        )

    @staticmethod
    def _enhance_web_element(element):
        if isinstance(element, bool):
            return element
        if element is not None:
            setattr(
                element,
                'wait_for_element_by_xpath',
                types.MethodType(
                    lambda lself, lxpath_str, ltimeout=DEFAULT_TIMEOUT:
                    WebTest._wait_for_element_by_xpath(lself, lxpath_str, timeout=ltimeout),
                    element
                )
            )
            setattr(
                element,
                'wait_for_not_element_by_xpath',
                types.MethodType(
                    lambda lself, lxpath_str, ltimeout=DEFAULT_TIMEOUT:
                    WebTest._wait_for_not_element_by_xpath(lself, lxpath_str, timeout=ltimeout),
                    element
                )
            )
            setattr(
                element,
                'wait_for_element_by_css',
                types.MethodType(
                    lambda lself, lcss_query, ltimeout=DEFAULT_TIMEOUT:
                    WebTest._wait_for_element_by_css(lself, lcss_query, timeout=ltimeout),
                    element
                )
            )
        return element

    def wait_for_element_by_css(self, css_selector, timeout=DEFAULT_TIMEOUT):
        return WebTest._wait_for_element_by_css(self._driver, css_selector, timeout)

    @staticmethod
    def _wait_for_element_by_css(element, css_query, timeout=DEFAULT_TIMEOUT):
        return WebTest._enhance_web_element(
            WebDriverWait(element, timeout).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, css_query)
                )
            )
        )

    def wait_for_element(self, elements_id, is_displayed=False, is_enabled=False, timeout=DEFAULT_TIMEOUT):
        self.wait_for(lambda _: self.get_ce_element(elements_id), timeout=timeout)

        element = self.get_ce_element(elements_id)
        if is_displayed:
            self.wait_for(lambda _: element.is_displayed(), timeout=timeout)
        if is_enabled:
            self.wait_for(lambda _: element.is_enabled(), timeout=timeout)
        return self.get_ce_element(elements_id)

    def disable_animations(self):
        disable_animations(self._driver)

    def get_chrome_options(self):
        options = webdriver.ChromeOptions()
        options.ensure_clean_session = True
        # try to disable as much animations as possible
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-app-list-dismiss-on-blur")
        options.add_argument("--disable-core-animation-plugins")
        options.add_argument("--start-maximized")
        if "CI" in os.environ:
            # this test is running in GitLab CI
            options.add_argument("--headless")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("window-size=1920,1080")
        return options

    def setup_webdriver(self):
        chrome_options = self.get_chrome_options()
        driver = webdriver.Chrome(
            chrome_options=chrome_options,
            service_log_path=os.path.join(CADDOK.LOGDIR, 'chromedriver.log')
        )
        driver.implicitly_wait(0)
        self._driver = driver
        self._driver.maximize_window()
        if login_webdriver(
            driver=driver,
            username=self.get_username(),
            password=self.get_password(),
            language=self.get_language()
        ):
            self.driver_logged_in = True
            self.server_url = get_server_url()
            self.navigate_to('/')
        else:
            raise Exception("login failed")

    def navigate_to(self, relative_url):
        if not isinstance(relative_url, six.string_types):
            raise ValueError('invalid relative url: %s' % relative_url)
        url = relative_url if relative_url[0] != '/' else relative_url[1:]
        self._driver.get(self.server_url + url)

    def init_web_ui(self):
        self.setup_webdriver()
        try:
            self.wait_for(EC.presence_of_element_located((By.CSS_SELECTOR, WEBUI_USER_MENU_CSS_SELECTOR)))
        except BaseException:
            self._driver.quit()
            self._driver = None
            raise

    def setUp(self):
        self._server_processes_before = (
            {
                p.pid: p for p in psutil.process_iter(
                    attrs=['pid', 'name']) if 'cdbsrv' in p.info['name']
            }
        )
        self.init_web_ui()

    def tearDown(self):
        if self._driver:
            try:
                self.wait_for(EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    WEBUI_USER_MENU_CSS_SELECTOR
                )))
                settings_element = self.wait_for_element_by_css(
                    WEBUI_USER_MENU_CSS_SELECTOR
                )
                settings_element.click()

                self.wait_for(EC.presence_of_element_located((By.ID, WEBUI_MENU_LOGOUT)))
                quit_element = self._driver.find_element(By.ID, WEBUI_MENU_LOGOUT)
                quit_element.click()

                # Handle "Something changed, do you really want to leave?" stuff
                if "logout" not in self._driver.current_url:
                    time.sleep(10)
                    self._driver.switch_to.alert.accept()

                self.wait_for(EC.url_contains("logout"))
            except BaseException as e:
                LOG.exception(e)
            finally:
                self.navigate_to("/logout")
                self._driver.quit()
                self._server_processes_after = (
                    {
                        p.pid: p for p in psutil.process_iter(
                            attrs=['pid', 'name']) if 'cdbsrv' in p.info['name']
                    }
                )
                if len(self._server_processes_after) > len(self._server_processes_before):
                    possible_leaked_pids = (
                        set(self._server_processes_after.keys()) -
                        set(self._server_processes_before.keys())
                    )
                    LOG.warning('leaked cdbsrv processes: %s', possible_leaked_pids)
                    if self.kill_leaked_servers:

                        def on_terminate(proc):
                            LOG.info(
                                "process %s terminated with exit code %s",
                                proc, proc.returncode
                            )

                        procs = [
                            self._server_processes_after.get(pid) for pid in possible_leaked_pids]
                        for p in procs:
                            p.terminate()
                        _, alive = psutil.wait_procs(procs, timeout=3, callback=on_terminate)
                        for p in alive:
                            p.kill()
