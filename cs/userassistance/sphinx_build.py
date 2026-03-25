# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import glob
import logging
import os
import shutil
import sys

import pkg_resources
import polib
from cdb import rte, version

from cs.userassistance import die, rmdir, shell

_logger = logging.getLogger(__name__)


def _compile_mo_files(build_dir):
    """Generates .MO files from a directory of .PO files"""
    language = os.path.basename(build_dir)
    for po_file in glob.glob(
        os.path.join(build_dir, 'locale', language, 'LC_MESSAGES', '*.po')
    ):
        _logger.debug('Compiling %s', po_file)
        po = polib.pofile(po_file)
        po.save_as_mofile(f'{os.path.splitext(po_file)[0]}.mo')


def _sphinx_build():
    if sys.platform == 'win32':
        sphinx_default = rte.runtime_tool(os.path.join('Scripts', 'sphinx-build'))
    else:
        sphinx_default = rte.runtime_tool('sphinx-build')
    sphinx_build = rte.environ.get('SPHINXBUILD', sphinx_default)
    if not (os.path.exists(sphinx_build) or os.path.exists(sphinx_build + '.exe')):
        die(f'{sphinx_build} not found')
    return sphinx_build


def _sphinx_opts(setup):
    # Get version information from platform
    release = setup['version']
    if setup['name'].startswith('cs.platform'):
        # Use Marketing Version in cs.platform packages for documentation
        if (
            setup['version'].startswith(version.verstring(False))
            or setup['version'] == 'trunk.dev'
        ):
            release = version.getVersionDescription()
            # Strip Buildnumber from string
            release = release[: release.find(' (Build #')]

    return [
        '-q',
        '-N',
        '-j',
        '2',
        '-D',
        f'version={setup["version"]}',
        '-D',
        f'release="{release}"',
    ]


def _sphinx(builder, args, setup, build_dir, src_dir):
    _logger.info('sphinx %s on %s', builder, build_dir)

    sphinx_extended_opts = list(_sphinx_opts(setup))
    sphinx_extended_opts.append('-A')
    sphinx_extended_opts.append(f'bodyclasses={builder}')
    if 'fail_on_warnings' in args and args.fail_on_warnings:
        sphinx_extended_opts.append('-W')
    env = dict(rte.environ)
    # pass parameters to conf.py
    env['SPHINXPACKAGE'] = setup['name']

    # Workaround: the 3rdpartylics doc package requires a powerscript with at
    # least applications loaded. Therefore, we need an instance, which !absolute!
    # path is given to Makefile/build.bat via CADDOK_BASE variable.
    # The installation dir should not be given as CADDOK_BASE Variable here, but
    # via snapp -D parameter
    if args.instancedir:
        env['CADDOK_BASE'] = args.instancedir

    if sys.platform == 'win32':
        env['BUILDDIR'] = build_dir
        env['SPHINXBUILD'] = _sphinx_build()
        env['SPHINXOPTS'] = ' '.join(sphinx_extended_opts)
        cmd = pkg_resources.resource_filename(
            'cs.userassistance',
            os.path.join('resources', 'sphinx.bat'),
        )
        shell(args, [cmd, builder, '&', 'exit'], shell=True, env=env, cwd=src_dir)
    else:
        ua_sphinx = pkg_resources.resource_filename(
            'cs.userassistance',
            os.path.join('resources', 'sphinx.mk'),
        )

        shell(
            args,
            [
                'make',
                '-f',
                ua_sphinx,
                f'BUILDDIR={build_dir}',
                f'SPHINXBUILD={_sphinx_build()}',
                f'SPHINXOPTS={" ".join(sphinx_extended_opts)}',
                str(builder),
            ],
            env=env,
            cwd=src_dir,
        )


def _use_builder(builders, args, b):
    """Check if we want to build output format 'b' in this run"""
    return (b in builders or b == 'gettext') and b in args.builder


def build(builders, args, setup, docsetname, build_dir, src_dir):
    """Run sphinx build for several output formats"""

    html_dir = os.path.join(build_dir, 'html')
    do_pickle = False

    # .mo files are only required if we really build docs, but not for
    # e.g. gettext
    if _use_builder(builders, args, 'html') or _use_builder(builders, args, 'pdf'):
        do_pickle = True
        _compile_mo_files(build_dir)

    if _use_builder(builders, args, 'html'):
        _sphinx('html', args, setup, build_dir, src_dir)

    if _use_builder(builders, args, 'pdf'):
        _sphinx('latexpdf', args, setup, build_dir, src_dir)
        pdf_file = f'{docsetname}.pdf'
        # copy result to where egg packaging picks it up
        if not os.path.exists(html_dir):
            os.makedirs(html_dir)
        shutil.copy2(
            os.path.join(build_dir, 'latex', pdf_file),
            os.path.join(html_dir, pdf_file),
        )
    if _use_builder(builders, args, 'gettext'):
        _sphinx('gettext', args, setup, build_dir, src_dir)
    if do_pickle:
        _sphinx('pickle', args, setup, build_dir, src_dir)
    return do_pickle


def clean(args, package_dir, docset):
    docset_dir = os.path.join(args.prefix, package_dir, docset)
    for subdir in ('doctrees', 'html', 'htmlhelp', 'latex', 'pickle'):
        rmdir(args, [os.path.normpath(os.path.join(docset_dir, subdir))])
    rmdir(args, [os.path.normpath(os.path.join(docset_dir, 'src', '_build'))])
