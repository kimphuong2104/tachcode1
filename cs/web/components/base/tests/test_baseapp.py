#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import, print_function

import json
import logging
import os
import subprocess
import sys
import unittest

import coverage
from webtest import TestApp

import cdbwrapc
from cdb import auth, rte
from cdb.testcase import PlatformTestCase
from cdb.version import getVersionDescription
from cs.platform.web.root import root as RootApp
from cs.web.components.base.main import BaseApp
from cs.webtest.main import WebtestApp

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

LOG = logging.getLogger(__file__)


class TestBaseApp(PlatformTestCase):
    def __init__(self, *args, **kwargs):
        super(TestBaseApp, self).__init__(*args, **kwargs)
        self.client = None

    def setUp(self):
        super(TestBaseApp, self).setUp()
        self.client = TestApp(RootApp)


    def test_currentUserLinkOuter(self):
        """ Check whether currentUser link is correctly escaped within the app setup links (outer)"""
        raise unittest.SkipTest("Broken in 15.5.0")

        if getVersionDescription().startswith("16"):
            raise unittest.SkipTest("Makes no sense in CE 16")

        if "NOSETESTS_USER_SWITCH_INNER" not in os.environ:

            def get_filtered_sys_argv(filter_keys):
                args = []
                skip_next = False
                for arg in sys.argv:
                    if 'python' in arg:
                        continue
                    if skip_next:
                        skip_next = False
                        continue
                    elif arg in filter_keys:
                        skip_next = True
                        continue
                    else:
                        args.append(arg)
                return args

            sub_env = os.environ.copy()
            sub_env['NOSETESTS_USER_SWITCH_INNER'] = '1'
            try:
                base_cmd = [rte.runtime_tool('python')]
                filtered_cmd = (
                    get_filtered_sys_argv(['-m', '-A']) +  # to prevent nose -A from ci which overrides $
                    ['-a', 'user=test@contact.de']
                )
                if "nosetests" not in " ".join(filtered_cmd):
                    cmd = base_cmd + ['-m', 'nose'] + filtered_cmd
                else:
                    cmd = base_cmd + filtered_cmd
                print(cmd)
                p = subprocess.Popen(
                    cmd,
                    env=sub_env,
                    stderr=subprocess.PIPE
                )
                (_, stderr_data) = p.communicate()
                self.assertEqual(p.returncode, 0, stderr_data)
            except subprocess.CalledProcessError as e:
                LOG.exception(e)
                self.assertTrue(False)
        else:
            self.skipTest('should only be executed on the outer test process')

    def test_currentUserLinkInner(self):
        """ Check whether currentUser link is correctly escaped within the app setup links (inner)"""
        if "NOSETESTS_USER_SWITCH_INNER" in os.environ:
            coverage.process_startup()
            cdbwrapc.set_user('test@contact.de')
        from cdb.objects.org import Person
        from cs.platform.web.rest.support import rest_key
        # It checks whether the response of BaseApp contain a tag with id 'application-root-base-data'
        # and if that contains a data attribute 'data-app-setup' containing a map of link maps
        # where one key is 'common' with a sub key 'currentUser' and whether the last segment of its
        # value is the rest_key of the current_user.
        current_user_rest_key = rest_key(Person.ByKeys(personalnummer=auth.persno))
        response = self.client.get(WebtestApp.__DEFAULT_MOUNTPOINT__)
        application_root_base_data = response.lxml.xpath('//*[@id="application-root-base-data"]')
        if application_root_base_data:
            application_root_base_data = {k: v for (k, v) in application_root_base_data[0].items()}
            data_app_setup = json.loads(json.loads(application_root_base_data.get('data-app-setup')))
            self.assertIn('links', data_app_setup)
            self.assertIn('common', data_app_setup['links'])
            self.assertIn('currentUser', data_app_setup["links"]["common"])
            self.assertEqual(
                    data_app_setup["links"]["common"]["currentUser"].split('/')[-1],
                    current_user_rest_key
                    )
