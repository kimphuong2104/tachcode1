# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Word Count Module

Counts the number of words in parts or the entirety of our documentation
"""
import csv
import os
from functools import lru_cache
from logging import DEBUG, getLogger
from pathlib import Path

from pkg_resources import get_distribution

from cs.docportal.loader import CDBDocPortalData, CDBPackage

_logger = getLogger(__name__)
_logger.setLevel(DEBUG)
cdb_packages = CDBDocPortalData().bundles[0]['packages']


def _get_package(package: str | CDBPackage) -> CDBPackage:
    """
    Allow for interchangeably using pkg_resources.Distribution and their str identifiers
    :param package: any string identifier of a package or a CDBPackage
    :return: a cs.docportal.loader.CDBPackage type object
    """
    if isinstance(package, CDBPackage):
        return package

    if isinstance(package, str):
        dist = get_distribution(package)
        return CDBPackage.from_path(dist.location)

    raise TypeError('Argument `package` needs to be either `str` or `CDBPackage`')


@lru_cache()
def get_book_word_count(package: str | CDBPackage, book: int, doc_db=None) -> int:
    """
    Count the number of words in the documentation of a single book in a CDB package
    :param package:
    :param book: the unique number identifier of a book within some CDB package
    :param doc_db: the cs.docportal.database.DocDB SQLite file of some CDB package
    :return: the total number of words in the requested book
    """
    package = _get_package(package)

    if not doc_db:
        with package.docdb as _doc_db:
            return _doc_db.count_book_words(db_id=book)

    return doc_db.count_book_words(db_id=book)


@lru_cache()
def get_package_word_count(package: str | CDBPackage) -> int:
    """Count the number of words in the documentation of a CDB package
    :param package: any of our CDB packages
    :return: the total number of words in the documentation of the requested package
    """
    package = _get_package(package)
    word_count = 0

    with package.docdb as doc_db:
        for book_row in doc_db.books():
            word_count += get_book_word_count(
                package=package, book=book_row['db_id'], doc_db=doc_db
            )

    return word_count


@lru_cache()
def get_bundle_word_count() -> int:
    """
    Count the number of words in the documentation of all CDB packages in this
    Python environment
    :return: the total number of words in all the documentation
    """
    word_count = 0
    for cdb_pkg in cdb_packages:
        word_count += get_package_word_count(package=cdb_pkg)

    return word_count


def write_csv_overview():
    """
    Generate an exhaustive report CSV and write it to the temporary directory of your
    instance (default: ${INST}/tmp/docportal/word_count.csv).
    Each row contains information about one book:
    <PACKAGE>,<VERSION>,<BOOK>,<CATEGORY>,<LANGUAGE>,<WORD_COUNT>

    Please note that the category of a book is itself localized. So in order to find
    all books of a certain category over all languages you have to first find out the
    names of the categories for all the languages you are looking for:
    E.g.: ['Anwendung', 'User Manuals'] for German and English.
    """
    data = [
        (
            'package',
            'version',
            'book',
            'category',
            'language',
            'word_count',
        )
    ]

    _logger.info(
        'WARNING: Starting to count all words in documentation over ALL packages. '
        'This can potentially take a very long time.'
    )
    for i, package in enumerate(cdb_packages):
        with package.docdb as doc_db:
            for book in package.docdb.books():
                data.append(
                    (
                        package.name,
                        package.version,
                        book['name'],
                        book['cat_title'],
                        book['lang_id'],
                        get_book_word_count(
                            package=package, book=book['db_id'], doc_db=doc_db
                        ),
                    )
                )
        _logger.info(
            'Finished counting words for %s (package %d of %d)',
            package.name,
            i + 1,
            len(cdb_packages),
        )

    file_path = Path(os.environ['CADDOK_TMPDIR']) / 'docportal' / 'word_count.csv'
    _logger.info('\nAll packages done! Writing CSV to %s', file_path)
    with open(file_path, 'w', encoding='utf-8', newline='') as file_out:
        csv_writer = csv.writer(file_out)
        csv_writer.writerows(data)
    _logger.info('\nFinished program. Exiting...')
