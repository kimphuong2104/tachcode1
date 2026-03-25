#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Command to run JavaScript tests using Jest.
"""

from __future__ import absolute_import
__revision__ = "$Id: run_tests.py 238718 2022-11-03 10:21:45Z tha $"

import argparse
import json
import io
import logging
import os
import posixpath
import sys

from tempfile import NamedTemporaryFile

from cdb import CADDOK, rte
from cdb.comparch import pkgtools
from .command import Command
from .util import find_webui_apps, resource_dir

from cs.platform.web import static

_LOGGER = logging.getLogger(__name__)


class RunTests(Command):
    def __init__(self, packagename, dryrun, *jestargs, **kwargs):
        command = [os.path.join(CADDOK.BASE, 'node_modules', '.bin',
                                'jest%s' % ('.cmd' if sys.platform == 'win32' else ''))]
        command.extend(jestargs)
        super(RunTests, self).__init__(packagename, command,
                                       'jest.config.js', 'node_modules', dryrun, **kwargs)

    @classmethod
    def _external_mappings(cls):
        """ Return mappings for the external JavaScript libs. This is needed by
            jest to resolve imports from Web UI libs for various 3rd party libs
            that are mentioned in the webpack "externals" section.
        """
        return {'^React$': 'react',
                '^ReactDOM$': 'react-dom',
                '^Immutable$': 'immutable',
                '^ReactBootstrap': 'react-bootstrap'}

    @classmethod
    def _build_module_mappings(cls):
        """ Build a dictionary of JavaScript module names to paths in the file
            system, and store it as JSON in a temp file. This dict is used as
            `moduleNameMapper` in the Jest configuration.
        """
        rte.ensure_run_level(rte.APPLICATIONS_LOADED)
        apps = find_webui_apps()
        mappings = {}
        registry = static.Registry()
        for app in apps:
            libs = registry.getall(app.component_name_space)
            lib = libs[0] if libs else None
            lib_path = None

            if not libs:
                continue
            elif len(libs) > 1:
                _LOGGER.warn("More than one registry entry for %s! Using first entry: %s", app.pkg_name, lib)

            for f in lib.files:
                if f.endswith(".js"):
                    lib_path = lib.find_hashed_filepath(f)

            if os.path.isfile(lib_path):
                regex = '^%s$' % app.component_name_space
                mappings[regex] = lib_path
        mappings.update(cls._external_mappings())
        with NamedTemporaryFile(
            suffix=".json",
            dir=CADDOK.TMPDIR,
            delete=False,
            mode="w",
            encoding="UTF-8"
        ) as tf:
            tmp_file_name = tf.name
            json.dump(mappings, tf, indent=4)
        return tmp_file_name

    @classmethod
    def _external_node_modules(cls):
        """ Return the filesystem path to the externals JavaScript lib. This is
            needed by the jest infrastructure to resolve imports for various 3rd
            party libs that are bundled in the externals, but imported as if
            they were not (eg. React).
        """
        return posixpath.join(pkgtools.path_join('cs.web'),
                              'cs', 'web', 'components', 'externals', 'js',
                              'node_modules')

    @classmethod
    def _parserfunc(cls, args):
        mapping_file_name = cls._build_module_mappings()
        try:
            webpkg = pkgtools.path_join('cs.web')
            rte.environ['NODE_PATH'] = os.path.join(CADDOK.BASE, 'node_modules')
            rte.environ['JEST_COMMON_CONFIG_DIR'] = str(resource_dir())
            rte.environ['JEST_MODULE_MAPPINGS'] = mapping_file_name
            rte.environ['JEST_EXTERNAL_NODE_MODULES'] = cls._external_node_modules()
            cmd = cls(args.cdbpackage, args.dry_run, *args.jestargs, raise_retcode=True)

            # reset config file and use the jest.config.js of the projects
            cmd.configfile = None
            # check for a config
            apps = [app for app in cmd.apps if os.path.exists(os.path.join(app, "jest.config.js"))]
            if apps:
                cmd.command += ['--projects', ] + apps
                cmd.run(workdir=cmd.pkgdir)
        finally:
            os.remove(mapping_file_name)

    def _run(self, workdir=None, env=None):
        if env is None:
            env = rte.environ
        env = env.copy()
        env['JEST_JUNIT_OUTPUT_DIR'] = env.get('JEST_JUNIT_OUTPUT_DIR', '.')

        # Try to determine NS and prefix report fname if possible.
        fname_prefix = ''
        fname_suffix = 'junit.xml'
        try:
            with io.open(os.path.join(workdir, 'namespace.json')) as nsfile:
                fname_prefix = '%s.' % json.load(nsfile)
        except IOError:
            pass

        env['JEST_JUNIT_OUTPUT_NAME'] = '%s%s' % (fname_prefix, fname_suffix)

        return super(RunTests, self)._run(workdir, env)

    @classmethod
    def add_parser(cls, subparsers):
        parser = subparsers.add_parser('run-tests', help='Run JavaScript unit tests')
        parser.add_argument('cdbpackage',
                            help='Name of cdbpackage in which to look for webapps.')
        parser.add_argument('jestargs', nargs=argparse.REMAINDER, metavar='...',
                            help='Additional parameters, these are passed through to jest')
        parser.set_defaults(func=cls._parserfunc)
