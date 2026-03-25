# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module translate

This is the documentation for the translate module.
"""
import glob
import logging
import os
import shutil

from cs.userassistance import arg, cs_cmd, die, doc, subcommand

_logger = logging.getLogger(__name__)


def _translate_export(args, extra, setup):
    workdir = os.path.abspath(os.path.normpath(args.workdir))
    if not os.path.exists(workdir):
        _logger.debug('Creating workdir at "%s"', workdir)
        os.makedirs(workdir)
        os.makedirs(os.path.join(workdir, 'context'))

    _logger.info('cdbpkg xliff --export')
    cmd_args = [
        'xliff',
        '--export',
        '--exportdir',
        os.path.join(workdir, 'xliff'),
        '--targetlang',
        args.language,
        setup['name'],
    ]
    # At least the Jsdoc builder requires this runtime level
    from cdb import rte

    rte.ensure_run_level(
        rte.INSTANCE_ATTACHED,
        prog='userassistance',
        instancedir=args.instancedir,
        init_pylogging=False,
    )
    cs_cmd(args, 'cdbpkg', *cmd_args)

    package_dir = os.path.join(args.prefix, setup.get('package_dir', {'': ''})[''])
    docsets_to_check = []
    userassistance = [rte.runtime_tool('powerscript'), '-m', 'cs.userassistance']

    # loop over all docsets
    for docset, name, lang, builders in doc.docsets(args, extra, setup):
        if extra and docset not in extra:
            continue
        if args.language and lang not in args.language:
            continue
        # check if the docset is marked as translated
        if not os.path.exists(os.path.join(package_dir, docset, 'doclink.txt')):
            _logger.warning(
                'skip %s: no doclink.txt file found; no translated documentation.',
                docset,
            )
            continue
        docset_basename = '/'.join(docset.split('/')[0:2])
        _logger.info(
            'userassistance sync_translation %s/%s', docset_basename, args.language
        )
        cmd_args = ['sync_translation', f'{docset_basename}/{args.language}']
        cs_cmd(args, *userassistance, *cmd_args)

        _logger.info(
            'userassistance doctranslate %s/%s', docset_basename, args.language
        )
        cmd_args = ['doctranslate', f'{docset_basename}/{args.language}']
        cs_cmd(args, *userassistance, *cmd_args)

        docsets_to_check.append(docset)

    # collect po files
    if docsets_to_check:
        po_workdir = os.path.join(workdir, 'doc')
        if not os.path.exists(po_workdir):
            os.makedirs(po_workdir)
        for docset in docsets_to_check:
            docset_name = docset.split('/')[1]
            out_path = os.path.join(po_workdir, docset_name)
            _logger.info('processing %s', docset)
            if not os.path.exists(out_path):
                os.makedirs(out_path)
            docset_dir = os.path.abspath(
                os.path.join(
                    package_dir, docset, 'locale', args.language, 'LC_MESSAGES'
                )
            )
            po_files = glob.glob('%s%s*.po' % (docset_dir, os.sep))
            for po_file in po_files:
                _logger.info('cp %s -> workdir', os.path.basename(po_file))
                shutil.copy2(po_file, os.path.join(out_path, os.path.basename(po_file)))


def _translate_import(args, extra, setup):
    workdir = os.path.abspath(os.path.normpath(args.workdir))
    if not os.path.isdir(workdir):
        die('workdir "%s" does not exist, cannot import.' % workdir)

    # At least the Jsdoc builder requires this runtime level
    from cdb import rte

    rte.ensure_run_level(
        rte.INSTANCE_ATTACHED,
        prog='userassistance',
        instancedir=args.instancedir,
        init_pylogging=False,
    )
    if os.path.exists(os.path.join(workdir, 'xliff', setup['name'])):
        _logger.info('cdbpkg xliff --import')
        cmd_args = [
            'xliff',
            '--import',
            '--importdir',
            os.path.join(workdir, 'xliff', setup['name']),
        ]
        cs_cmd(args, 'cdbpkg', *cmd_args)
    else:
        _logger.info('No xliff files found, skipping cdbpkg xliff --import')

    basedir = os.path.join(workdir, 'doc')
    docsets = os.listdir(basedir)
    userassistance = [rte.runtime_tool('powerscript'), '-m', 'cs.userassistance']

    for docset in docsets:
        basename = os.path.basename(docset)
        set_dir = os.path.join('doc', basename, args.language)

        _logger.info('Checking "%s"', basename)
        if os.path.exists(set_dir):
            _logger.info('Found docset at "%s"', set_dir)
            localedir = os.path.join(set_dir, 'locale', args.language, 'LC_MESSAGES')
            if not os.path.exists(localedir):
                os.makedirs(localedir)

            po_dir = os.path.join(basedir, docset)
            po_files = glob.glob('%s%s*.po' % (po_dir, os.sep))
            for po_file in po_files:
                _logger.info('Copying %s -> LC_MESSAGES', os.path.basename(po_file))
                shutil.copy2(po_file, localedir)

        # doctranslate doesn't support backslashes in docset names
        _set_dir = set_dir.replace('\\', '/')
        _logger.info('userassistance doctranslate %s', _set_dir)
        cmd_args = ['doctranslate', _set_dir]
        cs_cmd(args, *userassistance, *cmd_args)


@subcommand(
    arg('mode', help='"export" or "import" mode'),
    arg('language', help='Language to translate to'),
    arg('workdir', help='Directory to use for results.'),
)
def translate(args, extra, setup):
    """Run the full translation workflow

    In mode ``export`` this creates an export dir containing both the extracted
    messages and the po files from the documentation export.

    In mode ``import`` this loads the updated localization data from the workdir
    and imports it into a local installation.

    You need a working copy built with ``buildout`` for this to export or
    import like this.
    """
    if args.mode == 'export':
        return _translate_export(args, extra, setup)
    elif args.mode == 'import':
        return _translate_import(args, extra, setup)
    else:
        die('Invalid mode: "%s" use "export" or "import"' % args.mode)

    raise DeprecationWarning(
        'This is currently in the process of being replaced/removed'
    )
