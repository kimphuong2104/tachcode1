# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


# Module doctranslate
# This is the documentation for the doctranslate module.


import logging
import os
import shutil
from argparse import Namespace
from pathlib import Path

import polib

from cs.userassistance import arg, cs_cmd, doc, subcommand

# Do not wrap lines in the PO files, otherwise
# the fragile tools of some translators break badly.
# So, we only wrap blocks larger 64kB (should not happen,
# and if it does the text should be reformatted anyway).
WRAP_NOBREAK = 65535

_logger = logging.getLogger(__name__)


def _create_empty_po() -> polib.POFile:
    """
    Create an empty PO-File with default metadata
    :return: an empty polib.POFile
    """
    po = polib.POFile(wrapwidth=WRAP_NOBREAK, check_for_duplicates=True)
    po.metadata = {
        'Project-Id-Version': '1.0',
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
    }
    return po


def sort_key_poentry(x):
    """
    TODO: document
    :param x:
    :return:
    """
    for occurrence in x.occurrences:
        try:
            if occurrence[1]:
                return occurrence[0], int(occurrence[1])
        except ValueError:
            pass

    return '', 0


def _merge_po_files(pot_files: list[Path], msg_dir: Path):
    """
    TODO: docstring
    :param pot_files:
    :param msg_dir:
    :return:
    """
    translation_status = {}
    for pot_file in pot_files:
        _logger.debug('Processing "%s"', pot_file)
        po_name = msg_dir / f'{pot_file.stem}.po'
        try:
            if po_name.is_file():
                # Do not throw exceptions for duplicates, so this can be used
                # to fix svn merges. Duplicates will be eliminated later.
                pofile = polib.pofile(
                    str(po_name), wrapwidth=WRAP_NOBREAK, check_for_duplicates=False
                )
                is_new = False
            else:
                pofile = _create_empty_po()
                is_new = True

            pofile.merge(polib.pofile(str(pot_file)))
            _logger.debug('Writing PO "%s"', po_name.name)
            pofile.sort(key=sort_key_poentry)

            # Remove duplicates / merge artifacts
            clean_po_file = _create_empty_po()
            msg_ids = set()
            conflicts = 0
            for entry in pofile:
                try:
                    clean_po_file.append(entry)
                    if entry.msgid in msg_ids:
                        # Duplicate with different text...
                        _logger.error(
                            'Translation Conflict. '
                            'Duplicate msg-ID with different translation: %s',
                            entry.msgid,
                        )
                        conflicts += 1
                    else:
                        msg_ids.add(entry.msgid)
                except ValueError:
                    # Duplicate, ignore
                    _logger.debug(
                        'Discarding identical duplicate entry: %s', entry.msgid
                    )

            clean_po_file.save(str(po_name))
            total = len(clean_po_file)
            untranslated = len(clean_po_file.untranslated_entries())
            _logger.debug(
                'Translated: %3d %% [%d total, %d untranslated, %d conflicts]',
                clean_po_file.percent_translated(),
                total,
                untranslated,
                conflicts,
            )
            translation_status[po_name] = (total, untranslated, is_new)
        except Exception as e:
            _logger.exception('Error while processing %s (%s)', po_name, e)

    return translation_status


def gettext(args: Namespace, docset: str, language: str):
    """
    TODO: document me
    :param args:
    :param docset:
    :param language:
    """
    if not args.instancedir and os.environ.get('CADDOK_BASE') is not None:
        args.instancedir = os.environ['CADDOK_BASE']

    # At least the JSDoc builder requires this runtime level
    from cdb import rte

    rte.ensure_run_level(
        rte.INSTANCE_ATTACHED,
        prog='userassistance',
        instancedir=args.instancedir,
        init_pylogging=False,
    )
    kwargs = {}
    with open(os.devnull, 'w') as stderr:
        if not args.verbose:
            # Sphinx displays lots of false warnings, which at most makes sense
            # when actually building the docs, not when only calling 'gettext'
            kwargs['stderr'] = stderr

        cs_cmd(
            args,
            rte.runtime_tool('powerscript'),
            '-m',
            'cs.userassistance',
            'doc',
            '-b',
            'gettext',
            '--language',
            language,
            f'doc/{docset}/{language}',
            **kwargs,
        )


def do_cleanup(localedir: Path):
    """
    Clean the doctrees and old .POT files.
    The first is required because Sphinx hangs when the doctree is messed up,
    so throw it away before doing a rebuild.
    """
    _logger.debug('cleanup old .doctrees/ dir')
    doctrees = localedir / '.doctrees'
    shutil.rmtree(doctrees, ignore_errors=True)

    _logger.debug('cleanup old .pot files')
    for filename in localedir.glob('*.pot'):
        try:
            filename.unlink()
        except OSError:
            pass


def report_translation_status(
    docset: str, language: str, translation_status: dict
) -> int:
    """TODO: docstring
    :param docset: a book (e.g. 'foo_user')
    :param language: the language of the book (e.g. 'en')
    :param translation_status: a mapping of all labels that should be translated
    :return: how many translations are missing
    """
    totals = 0
    totals_missing = 0
    new_files = []
    report = []

    for key, (count, missing, is_new) in sorted(translation_status.items()):
        totals += count
        totals_missing += missing
        if missing:
            report.append(f'{key}:0: error: {missing:d} translations missing')
        if is_new:
            new_files.append(str(key))

    if report:
        report = [f'Translation status for {docset} [{language}]'] + report
        _logger.info('\n'.join(report))

    if new_files:
        report = ['NEW:']
        for filename in new_files:
            report.append(filename)
        _logger.info('\n  '.join(report))

    if totals_missing:
        _logger.warning('Missing %d of %d translatable entries', totals_missing, totals)

    return totals_missing


@subcommand(
    arg(
        '--mergeonly',
        dest='merge_only',
        default=False,
        action='store_true',
        help='Only merge the POT/PO files, do not build them.',
    )
)
def doctranslate(args, extra, setup):
    """
    Runs the translation workflow, which extracts the translatable
    text from the documentation into segments of the target language.
    Any changes are merged into the existing translations in the :file:`*.po`
    files in the folder :file:`locale/{LANG}/LC_MESSAGES`.

    After completing the translation, you can build the translated documentation
    with :program:`userassistance doc`.

    .. option:: --help, -h:

            Shows the help page.

            Example: :samp:`userassistance doctranslate --help`.

    .. option:: --mergeonly

            Only merge the POT/PO file, do not build them.
    """

    totals_missing = 0

    docsets: list[tuple[str, str]] = []
    translated_ds = doc.translated_docsets(args, extra, setup)

    # TODO: what is this block filtering for?
    for docset, _ in translated_ds:
        if extra and not docset.startswith(tuple(extra)):
            continue
        _, dset, lang = docset.split('/')
        docsets.append((dset, lang))

    if not docsets:
        raise ValueError('No translated Docsets could be found')

    for docset, language in docsets:
        docset_dir = Path(args.prefix) / 'doc' / docset / language
        locale_dir = docset_dir / 'locale'
        msg_dir = locale_dir / language / 'LC_MESSAGES'
        msg_dir.mkdir(exist_ok=True, parents=True)

        if not args.merge_only:
            do_cleanup(locale_dir)
        gettext(args, docset, language)

        # collect .pot files and find/create matching .po files
        pot_files = list(locale_dir.glob('*.pot'))
        if not pot_files:
            raise OSError(f'No .pot files found at {locale_dir.resolve()}')

        _logger.debug('Found %d POT files in %s', len(pot_files), locale_dir)
        translation_status = _merge_po_files(pot_files, msg_dir)
        totals_missing += report_translation_status(
            docset, language, translation_status
        )

    if totals_missing:
        return 2
