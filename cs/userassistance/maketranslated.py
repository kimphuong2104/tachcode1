#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


# Create a folder for a translated docset and copy all required from origin

import json
import logging
import os
import shutil

from cdb.plattools import killableprocess

from cs.userassistance import arg, die, subcommand

_logger = logging.getLogger(__name__)


@subcommand(
    arg('docset', help='Name of the original documentation set (e.g. "foo_user")'),
    arg('language', help='Language of the original documentation set (e.g. "de")'),
    arg(
        'targetlanguage',
        help='Language of the translated documentation set (e.g. "en")',
    ),
    arg(
        '-x',
        '--overwrite=',
        action='append',
        dest='overwrite',
        help='Overwrite',
        default=[],
    ),
    arg(
        '--noscm',
        dest='use_scm',
        default=True,
        help='Do not copy to src directory using Git/SVN',
    ),
)
def maketranslated(args, extra, setup):
    """
    Creates a subdirectory for the translation of a documentation set including required
    subdirectories and configuration files.

    Translated documentation has a :file:`doclink.txt`, which refers to
    the original language documentation and a set of directories
    :file:`locale/{LANG}/LC_MESSAGES`
    with the translated texts in :file:`*.po` files.

    Example: :samp:`sqlite\\bin\\userassistance
    maketranslated userassistance_user en de`

    .. option:: --help, -h:

                Shows the help page.

                Example: :samp:`userassistance makedocset --help`.

    .. option:: --noscm:

                Do not copy to the source directory using Git / SVN.
    """
    set_dir = os.path.join('doc', args.docset, args.targetlanguage)
    set_dir_prefixed = os.path.join(args.prefix, set_dir)
    set_dir_src = os.path.join(set_dir_prefixed, 'src')
    basedir = os.path.join('doc', args.docset, args.language)
    basedir_prefixed = os.path.join(args.prefix, basedir)
    basedir_src = os.path.join(basedir_prefixed, 'src')

    if not os.path.isdir(basedir_prefixed):
        die(f'original docset not found: "{basedir_prefixed}"')

    _create_dir_layout(set_dir_prefixed, args.targetlanguage)
    _write_doclink(basedir, set_dir_prefixed)

    if args.use_scm:
        _svn_copy_src(basedir_src, set_dir_src)
    else:
        _copy_src(basedir_src, set_dir_src)
    if args.use_scm:
        # Always try adding the new docset to a Git repo, since using both Git
        # and SVN simultaneously on the same local source is a justified use case.
        _logger.debug('git add %s', set_dir_prefixed)
        try:
            # Suppress Git's "fatal: not a git repository" output
            with open(os.devnull, 'w') as devnull:
                killableprocess.check_call(
                    ['git', 'add', set_dir_prefixed], stderr=devnull
                )
        except (OSError, killableprocess.CalledProcessError) as ex:
            _logger.debug('Error calling git: %s', ex)

        _logger.info(
            'Please edit doc/%s/%s/src/conf.py to adjust the language '
            'and add a translated title.',
            args.docset,
            args.targetlanguage,
        )
        _logger.info(
            "Don't forget to add doc/%s/%s to the 'docsets' list in %s!",
            args.docset,
            args.targetlanguage,
            args.setup,
        )


#################################################################
# Helpers
#################################################################
def _create_dir_layout(set_dir, target_lang):
    """Create the basic dir layout for a translated docset"""
    _logger.info('creating "%s" docset at "%s"', target_lang, set_dir)
    # Set up the gettext target stuff
    localedir = os.path.abspath(os.path.normpath(os.path.join(set_dir, 'locale')))
    msg_dir = os.path.join(localedir, target_lang, 'LC_MESSAGES')
    if not os.path.exists(msg_dir):
        os.makedirs(msg_dir)


def _write_doclink(src_dir, set_dir):
    # Write information about doc source
    with open(os.path.join(set_dir, 'doclink.txt'), 'w', encoding='utf-8') as fd:
        json.dump(
            {'__doc__': 'Translated docset', 'src': src_dir.replace('\\', '/')},
            fd,
            indent=2,
        )


def _copy_src(src_dir, set_dir):
    """Copy the src dir via filesystem only"""
    _logger.info('copy original src "%s" to "%s"', src_dir, set_dir)
    try:
        shutil.copytree(src_dir, set_dir)
    except shutil.Error as exc:
        die(exc)
    try:
        os.unlink(os.path.join(set_dir, 'docset.info'))
    except Exception:
        pass


def _svn_copy_src(src_dir, set_dir):
    """Copy the src dir via 'svn copy'"""
    from cdb import svncmd

    client = svncmd.Client()
    basedir = os.path.dirname(set_dir)
    try:
        client.info(src_dir)
    except svncmd.ClientError:
        # no svn dir
        _logger.warning('src seems not svn version controlled, doing std copy')
        return _copy_src(src_dir, set_dir)

    _logger.info('svn add %s', basedir)
    client.add(basedir)
    _logger.info('svn copy %s %s', src_dir, set_dir)
    client.copy(src_dir, set_dir)
    try:
        os.unlink(os.path.join(set_dir, 'docset.info'))
    except Exception:
        pass
