# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
"""

from __future__ import absolute_import
import logging
import os
import subprocess
import sys

from subprocess import CalledProcessError

from cdb import killableprocess
from cdb import misc
from cdb.comparch import pkgtools
from cs.web.make.util import MakeException, jsonread, rmrf, \
    get_javascript_bundles
from pathlib import Path

__docformat__ = "restructuredtext en"
__revision__ = "$Id: command.py 239645 2023-01-04 11:53:39Z tha $"

_LOGGER = logging.getLogger(__name__)
MSWINDOWS = sys.platform == "win32"


class Command(object):
    def __init__(self, packagename, command, configfile, builddir, dryrun, parallel=False, raise_retcode=False):
        if packagename is None:
            self.pkgdir = os.getcwd()
            try:
                self.apps = [
                    os.path.join(self.pkgdir, app_path)
                    for apps_json in Path(self.pkgdir).glob("*.egg-info/apps.json")
                    for app_path in jsonread(apps_json)
                ]
            except IOError:
                self.apps = []
                _LOGGER.debug("No javascript apps found in %s", self.pkgdir)
        else:
            self.pkgdir = pkgtools.path_join(packagename)
            self.apps = [
                os.path.join(self.pkgdir, app_path)
                for app_path in get_javascript_bundles(packagename)
            ]

        self.packagename = packagename
        self.command = command
        self.configfile = configfile
        self.builddir = builddir
        self.dryrun = dryrun
        self._parallel = parallel
        self._raise_retcode = raise_retcode

    def _run(self, workdir=None, env=None):
        if not os.path.exists(workdir):
            raise MakeException('Workdir %s does not exist' % workdir)

        check_result = self.check(workdir)
        if check_result:
            _LOGGER.warning(check_result)
            return None

        with misc.change_directory(workdir):
            if self.configfile is None or os.path.exists(self.configfile):
                _LOGGER.info("@ %s > %s", workdir, subprocess.list2cmdline(self.command))
                return killableprocess.Popen(self.command,
                                             env=env,
                                             processgroup=True if MSWINDOWS else False)

    def _handle_retcode(self, retcode, raise_retcode=False):
        if retcode and (self._raise_retcode or raise_retcode):
            raise CalledProcessError(retcode, self.command)

    def run(self, workdir=None, env=None):
        """
        run command on a single folder, that must contain the configfile if
        specified
        """
        proc = self._run(workdir, env)
        if proc is None:
            return

        self._handle_retcode(proc.wait(), True)

    def check(self, workdir):
        return None

    def check_dev_package(self):
        if self.packagename is not None:
            setupfile = pkgtools.path_join(self.packagename, 'setup.py')
            if not os.path.isfile(setupfile):
                raise MakeException('The package "{0}" is not a development package! '
                                    'Refusing to build!'.format(self.packagename))

    def run_all(self, env=None):
        """
        run command over all web applications in given package
        """
        procs = []
        # Spawn child processes for each bundle.
        # _run will return a process handle on which we wait
        for appdir in self.apps:
            proc = self._run(appdir, env)
            if proc:
                if self._parallel:
                    procs.append(proc)
                else:
                    self._handle_retcode(proc.wait())

        if self._parallel:
            # Wait for processes to terminate
            # and propagate first failed return code
            rets = [r for r in [p.wait() for p in procs] if r]
            if len(rets):
                self._handle_retcode(rets[0])

    def clean(self):
        """
        remove build fragments of command
        """
        if self.builddir:
            for appdir in [self.pkgdir] + self.apps:
                if self.configfile is None \
                        or os.path.exists(os.path.join(appdir, self.configfile)):
                    rmrf(os.path.join(appdir, self.builddir))
