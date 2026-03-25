# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
"""
from __future__ import absolute_import
import argparse
import logging
import os
import sys

import shutil

from cdb import rte, CADDOK
from cdb.comparch import pkgtools
from cs.web.make.command import Command
from cs.web.make.util import (
    rmrf,
    find_webdev_packages,
    get_javascript_bundles,
    resource_dir,
    MakeException,
)

__docformat__ = "restructuredtext en"
__revision__ = "$Id: build.py 239157 2022-11-28 11:56:31Z tha $"

_LOGGER = logging.getLogger(__name__)


def task_run_webpack(js_root='js'):
    def _run_webpack(args):
        _Webpack(args.package.module.package,
                 production=False,
                 dryrun=args.dry_run).run(args.package.dir(js_root))
    return _run_webpack


class _Webpack(Command):
    def __init__(self, packagename, production, dryrun, watch=False, colors=False, raise_retcode=True, **kwargs):
        super(_Webpack, self).__init__(packagename,
                                       command=None,
                                       configfile='webpack.config.js',
                                       builddir='build',
                                       dryrun=dryrun,
                                       raise_retcode=raise_retcode,
                                       **kwargs)
        self.check_dev_package()
        self._parallel = watch or kwargs.get('parallel', False)
        node = shutil.which('node')
        if node is None:
            raise MakeException("No 'node' on PATH.")
        node = os.path.abspath(node)
        self.command = [node,
                        os.path.join(CADDOK.BASE, 'node_modules', 'webpack', 'bin', 'webpack.js',)]
        rte.environ['NODE_PATH'] = os.path.join(CADDOK.BASE, 'node_modules')
        rte.environ['WEBPACK_CONFIG_COMMON'] = str(resource_dir() / 'webpack.config.common.js')
        self._production = production
        if production:
            self.command.append('--mode=production')
        else:
            self.command.append('--mode=development')
        if colors:
            self.command.append('--colors')

    def check(self, workdir):
        cfg_path = os.path.join(workdir, self.configfile)
        if not os.path.exists(cfg_path) and os.path.dirname(cfg_path) != self.pkgdir:
            # We only consider a missing config an error if it's not in the
            # implicitly added package directory
            return 'Configuration file %s does not exist' % cfg_path
        return None

    def run(self, workdir, env=None):
        if self._production:
            if env is None:
                env = rte.environ
            env = env.copy()
            env['NODE_ENV'] = 'production'

        super(_Webpack, self).run(workdir, env)

    def run_all(self, env=None):
        if self._production:
            if env is None:
                env = rte.environ
            env = env.copy()
            env['NODE_ENV'] = 'production'

        super(_Webpack, self).run_all(env)

    @classmethod
    def _parserfunc(cls, args):
        """
        a helper function called from argparser, to call run_all
        """
        webpack = cls(args.cdbpackage, args.production, args.dry_run,
                      watch=args.watch, colors=args.colors)

        if args.watch:
            webpack.command.append('-w')

        if args.wpargs:
            webpack.command.extend(args.wpargs)
            if '--watch' in args.wpargs or '-w' in args.wpargs:
                webpack._parallel = True

        if args.workdir:
            webpack.run(os.path.join(webpack.pkgdir, args.workdir))
        else:
            webpack.run_all()

    @classmethod
    def add_parser(cls, parser):
        """
        webpack can be added as subcommand to a subparser
        """
        prsr = parser.add_parser('webpack',
                                 help='run webpack on all applications')
        prsr.add_argument('cdbpackage',
                          help='Name of cdbpackage in which to look for '
                               'webapps.')
        prsr.add_argument('workdir', default=None, nargs='?',
                          help='Optional working directory for webpack.')
        prsr.add_argument('-nc', '--no-cache', default=False,
                          action='store_true',
                          help='Ignored.')
        prsr.add_argument('-p', '--production', default=False,
                          action='store_true',
                          help='Run in production mode and minify sources.')
        prsr.add_argument('-w', '--watch', default=False, action='store_true',
                          help='Run watch mode of webpack.')
        prsr.add_argument('-c', '--colors', default=False, action='store_true',
                          help='Force output of ansi colors')
        prsr.add_argument('wpargs', nargs=argparse.REMAINDER)
        prsr.set_defaults(func=cls._parserfunc)


class _Yarn(Command):
    """
    Wrapper class for running yarn. The used yarn is from elements installation
    """
    def __init__(self, packagename, dryrun, *args, **kwargs):
        yarn_img = shutil.which('yarn')
        if yarn_img is None:
            raise MakeException("No 'yarn' on PATH.")
        yarn_img = os.path.abspath(yarn_img)
        command = [yarn_img]
        if args:
            command.extend(*args)
        kwargs.pop('parallel', False)

        super(_Yarn, self).__init__(packagename, command, 'package.json', 'node_modules', dryrun, **kwargs)
        self.apps.append(self.pkgdir)

        self.check_dev_package()

    @classmethod
    def _parserfunc(cls, args):
        """
        a helper function called from argparser, to call run_all
        """
        yarn = cls(args.cdbpackage, args.dry_run, args.command)

        if args.yarnargs:
            yarn.command.extend(args.yarnargs)

        yarn.run_all()

    @classmethod
    def add_parser(cls, parser):
        """
        yarn can be added as subcommand to a subparser
        """
        prsr = parser.add_parser('yarn', help='run yarn <cmd> on all applications')
        prsr.add_argument('cdbpackage', help='Name of cdbpackage in which to look for webapps.')
        prsr.add_argument('command', nargs='+')
        prsr.add_argument('yarnargs', nargs=argparse.REMAINDER)
        prsr.set_defaults(func=cls._parserfunc)


class _DevUpdate(_Yarn):
    def __init__(self, dryrun, *args, **kwargs):
        super(_DevUpdate, self).__init__(None, dryrun, *args, raise_retcode=True)
        self.pkgdir = kwargs.get('targetdir') or CADDOK.BASE
        try:
            os.makedirs(self.pkgdir)
        except os.error:
            # Ignore, if it already exists
            pass

        shutil.copy(resource_dir() / 'package-base.json',
                    os.path.join(self.pkgdir, 'package.json'))
        # E051527: to really pin all versions, copy yarn.lock too
        source_pth = resource_dir() / 'yarn-base.lock'
        if source_pth.exists():
            shutil.copy(source_pth, os.path.join(self.pkgdir, 'yarn.lock'))
        local_modules_target = os.path.join(self.pkgdir, 'local_modules')
        if os.path.isdir(local_modules_target):
            shutil.rmtree(local_modules_target)
        shutil.copytree(resource_dir() / 'local_modules', local_modules_target)

    @classmethod
    def add_parser(cls, parser):
        parser_devupdate = parser.add_parser('devupdate',
                                             help='Prepare web modules as base dependencies '
                                                  'in the instance')
        parser_devupdate.add_argument('--targetdir')
        parser_devupdate.add_argument('--update', action='store_true', default=False)
        parser_devupdate.set_defaults(func=cls.default_func)

    @staticmethod
    def default_func(args):
        yarn_args = ['install', '--no-progress']
        if not args.update:
            yarn_args.append('--frozen-lockfile')
        cmd = _DevUpdate(False, yarn_args, targetdir=args.targetdir)
        cmd.run(cmd.pkgdir)
        if args.update:
            # Copy back updated lockfile
            pkgdir = args.targetdir or CADDOK.BASE
            source_pth = resource_dir() / 'yarn-base.lock'
            if source_pth.exists():
                shutil.copy(os.path.join(pkgdir, 'yarn.lock'), source_pth)
                _LOGGER.info(f'Updated {source_pth}')



class _Outdated(_Yarn):
    def __init__(self, dryrun, *args, **kwargs):
        super(_Outdated, self).__init__(None, dryrun, *args)
        self.pkgdir = kwargs.get('targetdir') or CADDOK.BASE

    @classmethod
    def add_parser(cls, parser):
        parser_outdated = parser.add_parser('outdated',
                                             help='Find outdated base dependencies.')
        parser_outdated.set_defaults(func=cls.default_func)
        parser_outdated.add_argument('--targetdir')

    @staticmethod
    def default_func(args):
        cmd = _Outdated(False, ('outdated',), targetdir=args.targetdir)
        cmd.run(cmd.pkgdir)


def clean_cache(packagename, dryrun=False):
    _LOGGER.warning('webmake cache-clean has been removed, as only-if-changed-webpack-plugin does not support Webpack 5.')


def _clean_cache(args):
    clean_cache(args.cdbpackage, args.dry_run)


def clean(packagename, dryrun=True):
    """
    Remove all files from yarn install and webpack and additionally remove all
    .pyc files.
    """
    _Yarn(packagename, dryrun=dryrun).clean()
    _Webpack(packagename, dryrun=dryrun, production=True).clean()
    # recursive remove *.pyc files
    for root, _, files in os.walk(pkgtools.path_join(packagename)):
        for fname in files:
            if fname.endswith(".pyc"):
                _LOGGER.info("> rm %s", os.path.join(root, fname))
                if not dryrun:
                    os.unlink(os.path.join(root, fname))


def _clean(args):
    clean(args.cdbpackage, args.dry_run)


def build_webapps(packagename, mode=None, parallel=False):
    """
    Initial build step to create all webapplications used by setup.py during
    buildout process. Calls yarn install first and the webpack on each
    application.
    """
    _Yarn(packagename, False,
        ('install', '--no-progress', '--frozen-lockfile'),
        parallel=parallel, raise_retcode=True).run_all()
    if mode in [None, 'both', 'production']:
        _Webpack(packagename, dryrun=False, production=True, parallel=parallel).run_all()
    if mode in [None, 'both', 'development']:
        _Webpack(packagename, dryrun=False, production=False, parallel=parallel).run_all()


def _build_webapps(args):
    """CLI Wrapper for buildwebwebapps"""
    if (args.clean):
        _clean(args)

    mode = 'production' if args.production else args.mode
    return build_webapps(args.cdbpackage, mode=mode, parallel=args.parallel)


def _cache_clean_all(args):
    _LOGGER.warning('webmake cache-clean-all has been removed, as only-if-changed-webpack-plugin does not support Webpack 5.')


def _clean_all(args):
    for pkg in find_webdev_packages():
        clean(pkg, args.dry_run)


def _buildall(args):
    if args.clean:
        _clean_all(args)

    for pkg in find_webdev_packages():
        mode = args.production if args.production else args.mode
        build_webapps(pkg, mode=mode, parallel=args.parallel)


def add_parameters(subparsers):
    parser_buildwebapps = subparsers.add_parser('build',
                                                help='prepare and build all webapplications')
    parser_buildwebapps.add_argument('cdbpackage',
                                     help='Name of cdbpackage in which to look for webapps.')
    parser_buildwebapps.add_argument('--parallel',
                                     default=False,
                                     action='store_true',
                                     help='Run builds in parallel. Runs faster but makes error '
                                          'logs harder to read.')
    parser_buildwebapps.add_argument('--production',
                                     default=False,
                                     action='store_true',
                                     help='Build code for production(release)')
    parser_buildwebapps.add_argument('--mode',
                                     choices=['both', 'production', 'development'],
                                     default='both',
                                     help='Build code for specified mode.')
    parser_buildwebapps.add_argument('--clean',
                                     default=False,
                                     action='store_true',
                                     help='Clean caches and build artifacts before building.')
    parser_buildwebapps.set_defaults(func=_build_webapps)

    parser_buildall = subparsers.add_parser('buildall',
                                            help='prepare and build all webapplications in all '
                                                 'packages')
    parser_buildall.add_argument('--parallel',
                                 default=False,
                                 action='store_true',
                                 help='Run builds in parallel. Runs faster but makes error '
                                      'logs harder to read.')
    parser_buildall.add_argument('--production',
                                 default=False,
                                 action='store_true',
                                 help='Build code for production(release)')
    parser_buildall.add_argument('--mode',
                                 choices=['both', 'production', 'development'],
                                 default='both',
                                 help='Build code for specified mode.')
    parser_buildall.add_argument('--clean',
                                 default=False,
                                 action='store_true',
                                 help='Clean caches and build artifacts before building.')
    parser_buildall.set_defaults(func=_buildall)

    _Yarn.add_parser(subparsers)
    _Webpack.add_parser(subparsers)

    _DevUpdate.add_parser(subparsers)
    _Outdated.add_parser(subparsers)

    parser_clean = subparsers.add_parser('clean',
                                         help='remove all downloaded/generated node_module directories')
    parser_clean.add_argument('cdbpackage',
                              help='Name of cdbpackage in which to look for webapps.')
    parser_clean.set_defaults(func=_clean)

    parser_clean_all = subparsers.add_parser('clean-all',
                                             help='clean all packages')
    parser_clean_all.set_defaults(func=_clean_all)

    parser_clean = subparsers.add_parser('cache-clean',
                                         help='remove only-if-changed cache')
    parser_clean.add_argument('cdbpackage',
                              help='Name of cdbpackage in which to look for webapps.')
    parser_clean.set_defaults(func=_clean_cache)

    parser_cache_clean_all = subparsers.add_parser('cache-clean-all',
                                                   help='clean cache for all applications')
    parser_cache_clean_all.set_defaults(func=_cache_clean_all)
