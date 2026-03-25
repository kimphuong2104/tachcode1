# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import glob
import logging
import os

import polib

from cs.userassistance import arg, doc, doctranslate, subcommand
from cs.userassistance.autotranslate_missing import deepl

# Do not wrap lines in the PO files, otherwise
# the fragile tools of some translators break badly.
# So, we only wrap blocks larger 64kB (should not happen,
# and if it does the text should be reformatted anyway).
WRAP_NOBREAK = 65535

_logger = logging.getLogger(__name__)


@subcommand(
    arg(
        '--deeplauthkey',
        default=None,
        type=str,
        help='The authentication key as provided by DeepL. '
        'Can also be set via environment variable DEEPLAUTHKEY.',
    )
)
def autotranslate_missing(args, extra, setup):
    total_untranslated = 0
    total_translated = 0
    docsets = []
    for docset, src in doc.translated_docsets(args, extra, setup):
        if extra and not docset.startswith(tuple(extra)):
            continue
        _, dset, lang = docset.split('/')
        srclang = src.split('/')[-1]
        docsets.append((dset, srclang, lang))

    for docset, srclang, language in docsets:
        po_files = glob.glob(
            os.path.join(
                args.prefix,
                'doc',
                docset,
                language,
                'locale',
                language,
                'LC_MESSAGES',
                '*.po',
            )
        )
        for po_name in po_files:
            po_file = polib.pofile(
                po_name, wrapwidth=WRAP_NOBREAK, check_for_duplicates=True
            )
            save = False
            for entry in po_file.untranslated_entries():
                # Means entries are not obsolete, not fuzzy and untranslated
                translation = deepl.translate(
                    language, entry.msgid, srclang, args.deeplauthkey
                )
                if not translation:
                    total_untranslated += 1
                else:
                    save = True
                    total_translated += 1
                    _logger.debug('Got translation: "%s"', translation)
                    entry.msgstr = translation
                    # Mark the translation as 'fuzzy': It needs to be checked
                    # by the author
                    if 'fuzzy' not in entry.flags:
                        entry.flags.append('fuzzy')
            if save:
                po_file.sort(key=doctranslate.sort_key_poentry)
                po_file.save()
    if total_untranslated:
        _logger.error(
            'Error: Not all missing entries could be translated! '
            'Missing: %d/%d translations',
            total_untranslated,
            total_translated + total_untranslated,
        )
        return 2
    elif total_translated:
        _logger.info('Successfully translated %d missing entries!', total_translated)
        _logger.info('DeepL usage statistics: %s', deepl.statistics(args.deeplauthkey))
    return 0
