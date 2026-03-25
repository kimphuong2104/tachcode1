# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import json
import logging
import os
from argparse import Namespace
from multiprocessing.pool import ThreadPool
from pathlib import Path

import pkg_resources

from cs.userassistance import arg, cs_cmd, die, docportal, sphinx_build, subcommand

_logger = logging.getLogger(__name__)


def docsets(args, extra, setup):
    """retrieve all docsets from setup.py"""
    from cdb.comparch import pkgtools

    docsets = [pkgtools.parse_docset(d) for d in setup.get('docsets', [])]

    if docsets:
        # error out on duplicate docset entries
        docset_counts = {d[0]: docsets.count(d) for d in docsets}
        duplicate_docsets = [k for k, v in docset_counts.items() if v > 1]
        if duplicate_docsets:
            raise ValueError(
                'Duplicate docset references in your setup.py! '
                'Please resolve/clear all duplicates and rerun! '
                f'Duplicate docsets: {duplicate_docsets}'
            )

    for docset in docsets:
        yield docset


def translated_docsets(args, extra, setup) -> list[tuple[str, str]]:
    """
    Find docsets that are translated from another language.

    These are identified by having a ``doclink.txt`` file in their root pointing to
    its source documentation.

    :param args:
    :param extra:
    :param setup: the contents of a setup.py:setup call as a dictionary
    :return: a tuple of (translated docset, src of translated docset),
        e.g ('doc/admin/en', 'doc/admin/de')
    """
    result = []
    extra_found = False
    package_dir = setup.get('package_dir', {'': ''})['']

    for docset, name, lang, builders in docsets(args, extra, setup):
        # e.g. ("doc/foo_user/en", "foo_user", "en", ['html', 'pdf'])
        if not extra or docset.startswith(extra[0]):
            doclink_path = Path(args.prefix) / package_dir / docset / 'doclink.txt'
            if not doclink_path.is_file():
                _logger.debug(
                    'no %s file found, '
                    '%s will not be processed as translated docset.',
                    doclink_path.absolute(),
                    docset,
                )
                extra_found = True
                continue

            with open(doclink_path, encoding='utf-8') as file_in:
                result.append((docset, json.load(file_in)['src']))

    if extra:
        for r in result:
            if r[0].startswith(extra[0]):
                extra_found = True
        if not extra_found:
            _logger.error('"%s" is not a valid translated docset', extra[0])

    return result


class DocTask:
    """Task object to run the job through multiprocessing"""

    def __init__(
        self, docportal_dir, source_dir, build_dir, docset, lang, builders, args, setup
    ):
        self.docportal_dir = docportal_dir
        self.source_dir = source_dir
        self.build_dir = build_dir
        self.docset = docset
        self.docsetname = self.docset.split('/')[1]
        self.lang = lang
        self.builders = builders
        self.args = args
        self.setup = setup
        self.did_pickle = None

    def build(self):
        """Run Sphinx Build on the task"""
        self.did_pickle = sphinx_build.build(
            self.builders,
            self.args,
            self.setup,
            self.docsetname,
            self.build_dir,
            self.source_dir,
        )
        return self.did_pickle

    def update_docportal(self):
        """Update the docportal db and search index"""
        if self.did_pickle:
            return docportal.parse_docset(
                self.docportal_dir, self.build_dir, self.builders, self.docsetname
            )


def _run_task(task):
    """Picklable func for multiprocessing; methods don't work"""
    return task.build()


@subcommand(
    arg(
        '-b',
        '--builder',
        action='append',
        help='Specify the preferred builders to use (default: html, pdf). '
        'Make sure to only build PDF in case you do not have LaTeX installed.',
    ),
    arg(
        '-i',
        '--help_ids',
        action='store_true',
        help='Generate Help-Ids after documentation build',
    ),
    arg(
        '-W',
        action='store_true',
        dest='fail_on_warnings',
        help='Treat Sphinx warnings as errors',
    ),
    arg(
        '--language',
        action='append',
        help='only build the given languages (default: all)',
        default=[],
    ),
    arg('docset', nargs='*', help='docset(s) to build (default: all)'),
)
def doc(args: Namespace, extra, setup: dict):
    """
    Build all documentation sets in all formats (html, latexpdf)
    and put the output files in those places where egg
    packaging picks them up. Normally builds all docsets defined in setup.py,
    the docsets to build can be restricted by passing docset names on the
    command line.


    .. option:: --help, -h:

                Shows the help page.
                You can also call this option for a subcommand.

                Example: :samp:`userassistance doc --help`.


    .. option:: --builder, -b <outputformat>:

                Builds the documentation in the specified output format.

                Example: :samp:`userassistance doc -b html`

    .. option:: --help_ids, -i:

                Generate Help-Ids upon completion of the documentation build.

    .. option:: -W

                Set Sphinx warnings to be treated as errors.

    .. option:: --language <language>:

                Choose to exclusively build the specified languages.  (default: all)
    """

    # Note: This function assumes that args is an ``argparse.Namespace`` object that was
    # created by parsing a command line for the doc subcommand.
    # However, in some cases this is not true (see implementation of snapp upload);
    # and this means that the argument declarations above are *NOT* applied.
    # Therefore, all arguments, even those with a default, may be missing!
    if not hasattr(args, 'builder'):
        args.builder = []
    if not hasattr(args, 'language'):
        args.language = []
    if not hasattr(args, 'docset'):
        args.docset = []

    if not args.builder:
        args.builder = ['html', 'pdf']

    found_docsets = []
    all_docsets = []
    package_dir = setup.get('package_dir', {'': ''})['']
    package_name = setup.get('name')
    tasks = []

    # At least the JSdoc builder requires this runtime level (E051675)
    from cdb import rte

    rte.ensure_run_level(
        rte.INSTANCE_ATTACHED,
        prog='userassistance',
        instancedir=args.instancedir,
        init_pylogging=False,
    )

    # Package dir containing setup.py
    root_dir = os.path.abspath(os.path.join(args.prefix, package_dir))

    # Put the built documentation into a docs/<package_name> subfolder
    # in the instance to have all documentation in a single place.
    # Can't rely on args.instancedir here, as it might not be set.
    # Explicitly use CADDOK_BASE instead.
    if (
        # Builders that put stuff into the sources should still target the doc/ dir.
        # Only doc build builders like "html" and "pdf" should do so
        args.builder == ['gettext']
        # "cs.platform" docs as well, as we do not install the platform
        # as a regular wheel. Thus, we can't ship the docs otherwise.
        # Leave them in the doc folder, just as before.
        or package_name == 'cs.platform'
    ):
        target_root = os.path.join(root_dir, 'doc')
    else:
        target_root = os.path.join(os.environ['CADDOK_BASE'], 'docs', package_name)

    # Collect all the jobs we need to do first
    for docset, name, lang, builders in docsets(args, extra, setup):
        all_docsets.append(docset)
        if args.docset and not docset.startswith(tuple(args.docset)):
            continue
        if args.language and lang not in args.language:
            continue

        build_dir = os.path.abspath(os.path.join(target_root, name, lang))
        source_dir = os.path.abspath(os.path.join(root_dir, docset, 'src'))

        found_docsets.append(docset)

        # Todo: should probably also moved to DocTask, but mostly harmless here
        if docset in setup['jsdoc']:
            try:
                # Building JS-Docs currently requires cs.web to be installed
                pkg_resources.require('cs.web')
                from cs.userassistance.jsdoc import Jsdoc

                jsdoc = Jsdoc(setup['name'], False, docset, False)
                jsdoc.run_all()
            except pkg_resources.DistributionNotFound:
                # cs.web not installed. Skip building JS-Docs
                # TODO: shouldn't this be an ERROR?
                pass

        tasks.append(
            DocTask(
                docportal_dir=target_root,
                source_dir=source_dir,
                build_dir=build_dir,
                docset=docset,
                lang=lang,
                builders=builders,
                args=args,
                setup=setup,
            )
        )

    # Run tasks in a thread pool
    # Run up to 8 builders in parallel, should be more than enough for the
    # around 30 books in the platform and even more for the apps.
    doc_threads = int(os.environ.get('DOCBUILDER_DOC_THREADS', '8'))
    pool = ThreadPool(processes=doc_threads)
    pool.map(_run_task, tasks)
    pool.close()
    pool.join()

    # Must be done serialized, due to apsw access
    for task in tasks:
        task.update_docportal()

    if args.builder != ['gettext']:
        # Remove all docsets from the documentation database, which no longer exist
        # or were removed from the setup.py.
        docportal.clean_docsets(target_root, exclude=all_docsets)

    # TODO: Fix helpID links for new cs.docportal
    if hasattr(args, 'help_ids') and args.help_ids:
        cs_cmd(args, 'powerscript', '-m', 'cs.docportal.cdb.helptools.updater')

    leftover_docsets = set()
    for ds in args.docset:
        for fds in found_docsets:
            if not fds.startswith(ds):
                leftover_docsets.add(ds)
    if leftover_docsets:
        die('No docsets found that match:\n  %s\n' % '\n  '.join(leftover_docsets))
