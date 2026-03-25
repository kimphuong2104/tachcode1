# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import datetime
import hashlib
import logging
import os
import sys
import time
import unittest
from contextlib import contextmanager
from selenium.common.exceptions import WebDriverException
from cdb import CADDOK, rte, testcase
from cdb.wsgi.util import jail_filename

"""
Module rqm test utils

This is the documentation for the utils module.
"""

__docformat__ = u"restructuredtext en"
__revision__ = u"$Id$"

LOG = logging.getLogger(__name__)

# Some imports


class RequirementsTestCase(testcase.RollbackTestCase):
    need_uberserver = False
    need_classification_core = False
    need_report_server = False

    def __init__(self, *args, **kwargs):
        need_uberserver = kwargs.pop('need_uberserver', True)
        need_classification_core = kwargs.pop('need_classification_core', True)
        need_report_server = kwargs.pop('need_report_server', False)
        if need_uberserver:
            RequirementsTestCase.need_uberserver = True
        if need_classification_core:
            RequirementsTestCase.need_classification_core = True
        if need_report_server:
            RequirementsTestCase.need_report_server = True

        super(RequirementsTestCase, self).__init__(*args, **kwargs)

    def _skip_before_specific_platform_version(self, major=15, minor=5, sl=0):
        from cdb.comparch.packages import Package
        import sys
        platform = Package.ByKeys('cs.platform')
        platform_version = platform.version
        parts = platform_version.split('.')
        if len(parts) == 4:
            p_major, p_minor, p_sl, _ = parts
        elif len(parts) == 3:
            p_major, p_minor, p_sl = parts
        elif len(parts) == 2:
            p_major, p_minor = parts
            p_sl = 0
        else:
            raise ValueError()
        if 'dev' in p_sl:
            p_sl = sys.maxsize
        p_major = int(p_major)
        p_minor = int(p_minor)
        p_sl = int(p_sl)
        if (
            p_major < major or
            (p_major == major and (p_minor < minor or (p_minor == minor and p_sl < sl)))
        ):
            self.skipTest('to old platform version to test, waiting for %s.%s.%s' % (
                major, minor, sl
            ))

    def persist_export_run(self, testcase_name):
        """
            To be able to debug test failures write the export run contents to CADDOK.TMPDIR
            as the database contents will be deleted due to rollback in case of errors.
         """
        try:
            dirname = os.path.join(CADDOK.TMPDIR, testcase_name)
            if os.path.isdir(dirname):
                hash_infos = datetime.datetime.now().isoformat()
                hash_infos = hash_infos.encode('utf-8')
                dirname += '_' + hashlib.sha1(hash_infos).hexdigest()
            os.makedirs(dirname)
            for run in self.spec.ExportRuns:
                for f in run.Files:
                    f.checkout_file(jail_filename(dirname, f.cdbf_name))
                with open(jail_filename(dirname, 'export_run.log'), 'w+') as f:
                    for protocol in run.Protocols:
                        for entry in protocol.ProtocolEntries:
                            description = entry.GetText('cdbrqm_protocol_entry_detail')
                            f.write("{}\n".format(description))
        except BaseException:
            LOG.exception('failed to export all export runs')

    @classmethod
    def ensure_running_classification_core(cls, timeout=120):
        from cs.classification import solr
        solr_connection = solr._get_solr_connection()
        t = time.time()
        while t + timeout > time.time():
            try:
                testcase.without_error_logging(solr_connection.get_fields)()
                break
            except Exception:
                time.sleep(1)
        else:
            raise IOError("Solr did not start up within %d seconds" % timeout)

    @classmethod
    def setUpClass(cls):
        super(RequirementsTestCase, cls).setUpClass()

        def fixture_installed():
            try:
                import cs.requirementstests
                return True
            except ImportError:
                return False

        def openpyxl_installed():
            try:
                import openpyxl
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.requirementtests not installed")
        if not openpyxl_installed():
            raise unittest.SkipTest("Test dependency openpyxl not installed")
        if cls.need_uberserver and cls.need_classification_core:
            testcase.require_service("cdb.uberserver.services.index.IndexService")
            cls.ensure_running_classification_core()

    @classmethod
    def get_tree_string_repr(cls, root, count=False):
        output_lines = [u""]

        def get_tree_string_repr_inner(parent, obj, next_elems, level, **context_data):
            indent = u"".join([u"  " for _ in range(0, level)])  # @UnusedVariable
            content = u""
            for long_text_key in obj.GetTextFieldNames():
                content += u"{k}: {v} #### ".format(v=obj.GetText(long_text_key), k=long_text_key)
            output_lines.append(u"%s%s (s:%d) (p:%d) (q:%d) (qa:%d) %s" % (
                indent,
                obj.GetDescription(),
                int(obj.status) if hasattr(obj, u'status') and obj.status is not None else -1,
                int(obj.position) if hasattr(obj,
                                             u'position') and obj.position is not None else -1,
                int(obj.act_value) if obj.act_value and obj.act_value is not None else -1,
                int(obj.fulfillment_kpi_active) if obj.fulfillment_kpi_active else -1,
                content
            ))

        root._walk(obj=root,
                   post=True,
                   func=get_tree_string_repr_inner)
        if count:
            return u"\n".join(output_lines), len(output_lines) - 1
        else:
            return u"\n".join(output_lines)


class RequirementsNoRollbackTestCase(testcase.PlatformTestCase):
    pass


@contextmanager
def screenshot_context(driver, screenshot_name, *args, **kwargs):
    """ take a screenshot if the test fails due to Assertion or Webdriver Exceptions """
    try:
        yield 
    except (AssertionError, WebDriverException):
        driver.get_screenshot_as_file(
            os.path.join(CADDOK.TMPDIR, screenshot_name)
        )
        LOG.exception(screenshot_name)
        raise 


def robust_run(driver, name, f, count, *args, **kwargs):
    from selenium.common import exceptions as SeleniumExceptions
    fail_handler = kwargs.pop("fail_handler") if "fail_handler" in kwargs else None
    success = False
    run = 0
    for i in range(0, count):
        LOG.error('Try %s %d/%d', f, i, count)
        try:
            return f(*args, **kwargs)
        except (
            SeleniumExceptions.TimeoutException, 
            SeleniumExceptions.StaleElementReferenceException,
            SeleniumExceptions.ElementNotInteractableException
        ) as e:
            LOG.exception(e)
        except SeleniumExceptions.WebDriverException as e:
            if "Other element would receive the click" not in str(e):
                raise
        if not success:
            try:
                screenshot_fp = os.path.join(CADDOK.TMPDIR, name + '%d.png' % i)
                driver.get_screenshot_as_file(screenshot_fp)
                browser_log_fp = os.path.join(CADDOK.TMPDIR, name + '_browser%d.log' % i)
                with open(browser_log_fp, 'w+') as browser_log_file:
                    browser_log_file.write(driver.get_log('browser'))
                if fail_handler is not None:
                    fail_handler(name=name, cnt=i)
            except BaseException:
                pass
            time.sleep(0.1 * run)
        run += 1
    if not success:
        LOG.error('%s failed after %d/%d tries', f, run, count)
        raise Exception('%s failed after %d/%d tries' % (f, run, count))


class ChangedEnvironment(object):

    def __init__(self, patches):
        self.old_environ = None
        self.patches = patches
        self.patched = False

    def __enter__(self):
        self.old_environ = rte.environ.copy()
        for k, v in self.patches.items():
            rte.environ[k] = v
            if not self.patched:
                self.patched = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.patched:
            for k, v in self.old_environ.items():
                rte.environ[k] = v


class ChangedFile(object):
    """
        Test helper context manager to ensure that a specific file has a specific content
        while the test execution is within this context
        and restore previous state afterwards
    """

    def __init__(self, filepath, temp_content):
        self.filepath = filepath
        self.old_content = None
        self.temp_content = temp_content

    def __enter__(self):
        if os.path.isfile(self.filepath):
            with open(self.filepath) as f:
                self.old_content = f.read()
        with open(self.filepath, 'w+') as f:
            f.write(self.temp_content)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.isfile(self.filepath):
            if self.old_content:
                with open(self.filepath, 'w+') as f:
                    f.write(self.old_content)
            else:
                os.remove(self.filepath)
        elif self.old_content:
            with open(self.filepath, 'w+') as f:
                    f.write(self.old_content)
        else:
            pass  # no file before, no file after
