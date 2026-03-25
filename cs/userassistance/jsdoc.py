#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import io
import logging
import os
import subprocess
import sys

from cdb import rte
from cdb.comparch import pkgtools
from cs.web.make.command import Command
from cs.web.make.packages import PackageAction
from cs.web.make.util import resource_dir as webmake_resource_dir
from cs.web.make.util import rmrf

_LOGGER = logging.getLogger(__name__)


def cmd_jsdoc_clean(cdbpackage, docset):
    rmrf(pkgtools.path_join(cdbpackage, docset, 'src', '_jsapi'))


def _cmd_jsdoc_clean(args):
    cmd_jsdoc_clean(args.cdbpackage, args.docset)


class Jsdoc(Command):
    """
    A wrapper around jsdoc to generate rst/sphinx docs from js code
    """

    def __init__(self, packagename, dryrun, docset, verbose):
        super(Jsdoc, self).__init__(
            packagename, command=None, configfile=None, builddir=None, dryrun=dryrun
        )
        self.command = [
            os.path.join(os.environ['CADDOK_BASE'], 'node_modules', '.bin', 'jsdoc'),
            '--template',
            os.path.join(
                os.environ['CADDOK_BASE'],
                'node_modules',
                'jsdoc-sphinx-contact',
                'template',
            ),
            '--recurse',
        ]
        rte.environ['JSDOC_CONFIG_COMMON'] = str(
            webmake_resource_dir() / 'jsdoc.conf.common.js'
        )

        self.builddir = os.path.join(self.pkgdir, docset, 'src', '_js')
        if verbose:
            self.command.append('--verbose')
        self.dryrun = dryrun

    def run_all(self):
        rmrf(self.builddir)
        return super(Jsdoc, self).run_all()

    @staticmethod
    def wait():
        return 0

    def run(self, workdir=None, env=None):
        self._run(workdir)

    def _run(self, workdir=None, env=None):
        def pkgname(dirname):
            # FIXME: This does some voodoo to generate names like names from
            # _PackageConfig.js_name
            name = os.path.split(
                os.path.relpath(os.path.normpath(os.path.relpath(dirname, self.pkgdir)))
            )[0]
            return name.replace(os.sep, '-')

        if not os.path.exists(os.path.join(workdir, 'src')):
            _LOGGER.error(
                '%s contains no src-folder. I expect source files in src', workdir
            )
            return

        # Create bundle directory
        destdir = os.path.join(self.builddir, pkgname(workdir))
        if not self.dryrun and not os.path.exists(destdir):
            os.makedirs(destdir)

        # Append bundle specific arguments to command
        command = list(self.command)
        command.extend(
            [
                os.path.join(workdir, 'src'),  # list of dirs, for sources
                '--destination',
                destdir,
            ]
        )  # build destination

        # Find a configuration for jsdoc in bundle directory
        conf_path = os.path.join(workdir, 'jsdoc.conf.js')
        # It may either have .js or .json extension
        if not os.path.exists(conf_path):
            conf_path = os.path.join(workdir, 'jsdoc.conf.json')
        # If it does not exist use default config
        if not os.path.exists(conf_path):
            conf_path = webmake_resource_dir() / 'jsdoc.conf.js'
        command.extend(['--configure', str(conf_path)])

        # Run jsdoc
        _LOGGER.info('> %s', subprocess.list2cmdline(command))
        if not self.dryrun:
            subprocess.check_call(command, env=env, shell=sys.platform == 'win32')

        # Generate toctree.rst
        files = [
            f
            for f in os.listdir(self.builddir)
            if (
                os.path.isdir(os.path.join(self.builddir, f))
                and os.path.exists(
                    os.path.join(self.builddir, f, '__package_index__.rst')
                )
            )
        ]
        if files:
            with io.open(
                os.path.join(self.builddir, 'toctree.rst'), 'w'
            ) as toctree_file:
                toctree_file.write('Index\n=====\n\n')
                toctree_file.write('.. toctree::\n   :maxdepth: 2\n\n')

                for bundle_dir in files:
                    toctree_file.write(f'   {bundle_dir}/__package_index__\n')

        # XXX return self for run_all to call a no-op wait() on
        return self

    @classmethod
    def _parserfunc(cls, args):
        """
        a helper function called from argparser, to call run_all
        """
        jsdoc = cls(args.cdbpackage, args.dry_run, args.docset, args.verbose)
        if args.packages:
            for pkg in args.packages:
                workdir = os.path.join(pkg.dir(), 'js')
                jsdoc.run(workdir)
        else:
            jsdoc.run_all()

    @classmethod
    def add_parser(cls, parser):
        prsr = parser.add_parser('jsdoc', help='run jsdoc on all/selected webapps')
        prsr.add_argument(
            'cdbpackage',
            help='Name of cdbpackage in which to look for webapps. '
            'Ignored if packages are specified',
        )
        prsr.add_argument('docset', help='docset in which to generate documentation')
        prsr.add_argument(
            'packages',
            nargs='*',
            action=PackageAction,
            help='webapps for which to generate documentation',
        )
        prsr.set_defaults(func=Jsdoc._parserfunc)


def build(packagename, docset):
    return Jsdoc(packagename, False, docset=docset, verbose=False).run_all()


def add_parameters(subparsers):
    Jsdoc.add_parser(subparsers)

    parser_jsdoc_clean = subparsers.add_parser(
        'jsdoc-clean', help='remove .rst-files generated by jsdoc'
    )
    parser_jsdoc_clean.add_argument(
        'cdbpackage',
        help='Name of cdbpackage in which to look for webapps. '
        'Ignored if packages are specified',
    )
    parser_jsdoc_clean.add_argument(
        'docset', help='docset in which to generate documentation'
    )
    parser_jsdoc_clean.set_defaults(func=_cmd_jsdoc_clean)
