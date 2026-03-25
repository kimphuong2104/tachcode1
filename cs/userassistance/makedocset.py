#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
import fnmatch
import logging
import os
import re
import shutil

from cs.userassistance import arg, subcommand

_logger = logging.getLogger(__name__)


@subcommand(
    arg('docset', help='Name of the documentation set'),
    arg('language', help='Language of the documentation set'),
    arg(
        '-x',
        '--overwrite=',
        action='append',
        dest='overwrite',
        help='Overwrite',
        default=[],
    ),
)
def makedocset(args, extra, setup):
    """
    Creates a new docset in the given language including the required directories and
    configuration files.
    You have to specify the docset name and the language.
    After creating, you have to add the new docset to the configuration
    file :file:`setup.py`.

    .. option:: --help, -h:

            Shows the help page.

            Example: :samp:`userassistance makedocset --help`.

    .. option:: --overwrite, -x:

                Overwrites existing files.

    Example usage of :command:`makedocset`:
    :samp:`userassistance makedocset userassistance_user en`
    """
    from cdb.comparch import constants

    dirname = os.path.dirname(__file__)
    templates = os.path.join(dirname, 'templates', 'makedocset')
    package = setup['name']
    if package == constants.kPlatformPackage:
        set_dir = os.path.join('cdb', 'python', 'doc', args.docset, args.language)
    else:
        set_dir = os.path.join('doc', args.docset, args.language)

    src_dir = os.path.abspath(
        os.path.normpath(os.path.join(args.prefix, set_dir, 'src'))
    )
    if not os.path.exists(src_dir):
        os.makedirs(src_dir)

    excluded = re.compile(fnmatch.translate('*.py[co]'))
    for file_name in os.listdir(templates):
        if excluded.match(file_name):
            # Skip binary files
            continue

        if not file_name.endswith('~'):
            path = os.path.join(templates, file_name)
            assert isinstance(path, str)

            with open(path, encoding='utf-8') as f:
                text = f.read()
                text = text.replace('%PKGNAME%', package)
                text = text.replace('%DOCSET%', args.docset)
                text = text.replace('%LANG%', args.language)
            outfile = os.path.join(src_dir, file_name)

            if not os.path.exists(outfile) or file_name in args.overwrite:
                tag = 'Creating'
                if os.path.exists(outfile):
                    shutil.copyfile(outfile, outfile + '.bak')
                    tag = 'Overwriting'
                assert isinstance(outfile, str)
                with open(outfile, 'w', encoding='utf-8') as f:
                    _logger.info('%s %s ...', tag, outfile)
                    f.write(text)
            else:
                _logger.info('Skipping existing %s ...', file_name)

    _logger.info(
        "\nDon't forget to add doc/%s/%s to the 'docsets' list in %s!",
        args.docset,
        args.language,
        args.setup,
    )
