# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Module updater

Help System Updater
"""

import itertools
import logging
import sys
from collections import namedtuple
from pathlib import Path
from typing import Iterable

from cdb import i18n, sqlapi
from cdb.comparch import packages
from cdb.transactions import Transaction

from cs.docportal.cdb.helptools.checkref import HelpIDChecker
from cs.docportal.cdb.helptools.crossref import CrossRefCatalogue
from cs.docportal.cdb.helptools.utils import find_inventories, get_package_doc_dir

HelpEntry = namedtuple(
    'HelpEntry', ('help_id', 'package', 'help_file', 'help_target', 'help_language')
)


class HelpSystemUpdater:
    """
    Update the Help References for the Installed Documentation.
    ``docroots`` is a list of package names.
    """

    def __init__(self, package_names: Iterable, catalogue=':memory:'):
        """
        :param package_names:
            The packages that should be updated
        :param catalogue:
            The path to the database to store the cross-references
        """
        self.cat = CrossRefCatalogue(catalogue)
        self.checker = HelpIDChecker()
        self.inventory_map = {}
        self.package_names = package_names
        for package_name in package_names:
            doc_dir = self._get_documentation_dir(package_name)
            if doc_dir and doc_dir.is_dir():
                self.inventory_map[package_name] = find_inventories(doc_dir)
        self._logger = logging.getLogger(__name__)

    def run(self):
        self._create_inventory()
        self._write_cdb_help()
        self._get_help_usage_info()

    @staticmethod
    def _get_documentation_dir(package_name: str) -> Path:
        """Returns the directory for the documentation of a package"""
        return get_package_doc_dir(package_name)

    @staticmethod
    def _label_from_path(doc_root: str, path: str) -> str:
        """
        Create a normalized label based on the path

        This strips the doc_root prefix, replaces backslashes with unix style forward
        slashes and strips off any ``objects.inv`` filename and turns.
        """
        base = len(doc_root) + 1
        label = path[base:]
        label = label.replace('\\', '/')
        if label.endswith('/objects.inv'):
            label = label[: -len('/objects.inv')]
        return label.lower()

    def _create_inventory(self):
        """Create the index file from all roots"""
        for package_name, inventories in self.inventory_map.items():
            package_doc_dir = self._get_documentation_dir(package_name)
            for inv in inventories:
                # FIXME: Modularization, create proper simple labels
                label = self._label_from_path(str(package_doc_dir), inv)
                self.cat.add_inventory(package_name, label, inv)

    def _get_help_usage_info(self):
        """Check the help usage data"""
        needed_help_ids = self.checker.used_help_ids()

        missing = []
        for help_id in needed_help_ids:
            if f'helpid_{help_id}' not in self.cat:
                missing.append(help_id)

        all_help_ids = self.cat.get_help_links()

        msg = [
            f'\n{len(needed_help_ids)} HelpIDs referenced',
            f'\n{len(all_help_ids)} HelpIDs available',
            f'\n{len(missing)} HelpIDs missing',
        ]
        for m in missing:
            msg.append(f'  {m}')
        self._logger.info('\n'.join(msg))

    @staticmethod
    def _strip_help_id(doc_id: str) -> str:
        """Remove the HelpID prefix from a docID"""
        if doc_id.startswith('helpid_'):
            return doc_id[len('helpid_') :]

        return doc_id

    @staticmethod
    def _guess_lang(book_label: str) -> str:
        """Find the language from the booklabel/path"""
        # At this time there is no rule for the language part, so search for a part
        # of the label that has two characters starting at the back of the list
        parts = reversed(book_label.split('/'))
        for candidate in parts:
            if len(candidate) == 2:
                return candidate

        return 'de'

    @staticmethod
    def _guess_book(book_label: str) -> str:
        """Find the bookname from the booklabel/path"""
        # At this time there is no rule for the language part, so search for a part
        # of the label that seems to be not the language and not the output format
        parts = book_label.split('/')
        parts.reverse()
        for candidate in parts:
            if len(candidate) != 2 and candidate not in ('html', 'pickle'):
                return candidate

        return book_label

    @staticmethod
    def _get_link(lang: str, langs: dict, fallbacks):
        """Get the link data from langs with fallback languages"""
        if lang in langs:
            return langs[lang]

        for fallback in fallbacks:
            if fallback in langs:
                return langs[fallback]

    def _collect_links(self, links, languages, fallbacks) -> tuple[list, dict]:
        """
        Group the links by language for processing. Returns two dicts:

        - The first contains a mapping for every docID and language to a URL and book.
        - The second contains any ID only available in one language.

        Language fallbacks are evaluated statically, using the list
        provided in `fallbacks`.
        """
        entries = []
        untranslated = {}
        for k, g in itertools.groupby(links, lambda key: key[0]):
            langs = {self._guess_lang(link[2]): link for link in g}
            if len(langs) == 1:
                untranslated[self._strip_help_id(k)] = [list(langs)[0]]

            for lang in languages:
                link = self._get_link(lang, langs, fallbacks)
                if not link:
                    continue

                docid, package, book, _, _, uri = link
                entry = HelpEntry(self._strip_help_id(docid), package, book, uri, lang)
                entries.append(entry)

        return entries, untranslated

    def _get_url(self, entry):
        """Retrieve the url that can be used to address the entry"""
        if entry.package:
            package = f'_inpackage/{entry.package}/'
        else:
            package = ''

        return (
            f'/doc/{entry.help_language}/'
            f'{package}{self._guess_book(entry.help_file)}/'
            f'{entry.help_target.replace(".html", "", 1)}'
        )

    def _write_cdb_help(self):
        """Write the cdb_help entries for the installed documentation"""
        langs = i18n.Languages()
        entries, _ = self._collect_links(self.cat.get_help_links(), langs, [])

        books = set(self._guess_book(e.help_file) for e in entries)
        self._logger.info('Writing HelpIDs for books:\n %s', '\n '.join(books))
        if entries:
            help_ids = set(e.help_id for e in entries)
            with Transaction():
                # Delete all Help-IDs that belong to the package we install
                sqlapi.SQLdelete(
                    'FROM cdb_help '
                    "WHERE help_type = 'CDBHelp'"
                    ' AND package IN (%s)'
                    % ','.join("'%s'" % pkg for pkg in self.package_names)
                )
                sqlapi.SQLdelete(
                    'FROM cdb_help WHERE LOWER(help_id) IN (%s)'
                    % ','.join("'%s'" % id_ for id_ in help_ids)
                )
                for entry in entries:
                    rec = sqlapi.Record(
                        'cdb_help',
                        package=entry.package,
                        help_language=entry.help_language,
                        help_target=self._get_url(entry),
                        help_id=entry.help_id,
                        help_type='CDBHelp',
                        help_file='',
                    )
                    rec.delete()
                    rec.insert()


def update_help_links():
    pkgs = packages.get_package_names()
    hsu = HelpSystemUpdater(pkgs)
    hsu.run()


if __name__ == '__main__':
    # Disable platform loggers, to report info events on stdout
    logging.root.handlers = []
    logging.basicConfig(format='%(message)s', stream=sys.stdout, level=logging.INFO)
    update_help_links()
