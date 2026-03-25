# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Models of the documentation portal.
"""

import os
from collections import defaultdict
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from threading import Lock

from cs.docportal import DocPortalError, EmptyDocPortalError, search
from cs.docportal.loader import load_mode_data
from cs.docportal.util import get_logger, locked_with_logger

__all__ = ['Store', 'DocBundle', 'DocCategory', 'DocLanguage']

_logger = get_logger(__name__)


class Store:
    """
    The Store keeps all required data in one place and provides an API to query it.
    """

    CACHED_STORE = None
    lock = Lock()

    def __init__(self):
        # data
        self.language_bundles: dict[str, LanguageBundle] = {}
        self._bundles: dict[str, DocBundle] = {}
        self._categories: dict[tuple[str, str], DocCategory] = {}
        self._languages: dict[str, DocLanguage] = {}
        self._books: dict[(DocBundle, DocCategory), list[DocBook]] = defaultdict(list)

        # defaults
        self.default_bundle = None
        self.default_language = None
        self.default_language_bundle = None

        # misc
        self.base_uri = '/'
        self.temp_folder = None

        # category tree
        self.book_paths = {}

    def __repr__(self):
        return 'Store(b:{},l:{},c:{},b:{})'.format(
            len(self._bundles),
            len(self._languages),
            len(self._categories),
            sum(len(lst) for lst in self._books),
        )

    @classmethod
    def _build(cls, mode_data):
        from apsw import Error as APSWError

        store = Store()

        # Books are supplied with a category name instead of the category identifier.
        # Therefore, we need this dict to map cat names to their respective cat IDs.
        _category_name_id_map = {}

        # BUNDLES
        for bundle_args in mode_data.bundles:
            store._bundles[bundle_args['identifier']] = DocBundle(**bundle_args)
        if not any(store._bundles.values()):
            raise EmptyDocPortalError('Store does not contain any Bundles')

        # LANGUAGES
        for language_args in mode_data.languages:
            store._languages[language_args['identifier']] = DocLanguage(**language_args)
        if not any(store._languages.values()):
            raise EmptyDocPortalError('Store does not contain any Languages')

        # LANGUAGE BUNDLES
        for identifier, (bundle_id, language_id) in mode_data.language_bundles.items():
            store.language_bundles[identifier] = LanguageBundle(
                identifier=identifier,
                bundle=store._bundles[bundle_id],
                language=store._languages[language_id],
            )

        # CATEGORIES
        def _make_subcategories(categories):
            """Recursively discover subcategories"""
            res_subcategories = []
            for category in categories:
                _subcategories = (
                    _make_subcategories(category['subcategories'])
                    if 'subcategories' in category
                    else []
                )
                category['subcategories'] = _subcategories
                res_subcategories.append(DocCategory(**category))
            return res_subcategories

        for category_args in mode_data.categories:
            subcategories = _make_subcategories(category_args['subcategories'])
            category_args['subcategories'] = subcategories
            store._categories[
                (category_args['identifier'], category_args['lang_id'])
            ] = DocCategory(**category_args)
            _category_name_id_map[
                (category_args['name'], category_args['lang_id'])
            ] = category_args['identifier']
        if not any(store._categories.values()):
            raise EmptyDocPortalError('Store does not contain any Categories')

        # BOOKS
        for bundle in store._bundles.values():
            for package in bundle.packages:
                # skip if encountering errors or no books are contained
                if not Path(package.docdb.db_path).is_file():
                    _logger.info('Missing DB file for %s', package)
                    continue

                try:
                    with package.docdb as docdb:
                        if len(list(docdb.books())) < 1:
                            _logger.info('Empty DB file for %s', package)
                            continue
                except APSWError as e:
                    _logger.warning('Problematic DB file for %s: %s', package, e)
                    continue

                # load all books in this package
                with package.docdb as docdb:
                    for book_args in docdb.books():
                        # skip if blacklisted
                        if book_args['identifier'] in mode_data.blacklist:
                            _logger.debug(
                                'Skipped %s because of blacklist entry',
                                book_args['identifier'],
                            )
                            continue

                        # pop args that are only needed here
                        relative_path = book_args.pop('relpath')
                        book_category_name = book_args.pop('cat_title')

                        # find out category ID from category name
                        try:
                            book_category_id = _category_name_id_map[
                                (book_category_name, book_args['lang_id'])
                            ]
                            book_category = store._categories[
                                (book_category_id, book_args['lang_id'])
                            ]
                        except KeyError:
                            _logger.warning(
                                'Could not find the category "%s" for book "%s" (%s)',
                                book_category_name,
                                book_args['name'],
                                book_args['identifier'],
                            )
                            continue

                        book = DocBook(
                            path=package.doc_path / relative_path,
                            docdb=docdb,
                            package=package,
                            **book_args,
                        )

                        # append book to its respective category
                        try:
                            store._books[(bundle, book_category)].append(book)
                        except KeyError:
                            store._books[(bundle, book_category)] = [book]

            # sort each book list by name
            for book_list in store._books.values():
                book_list.sort(key=lambda x: x.name.lower())
        if not any(store._books.values()):
            raise EmptyDocPortalError('Store does not contain any Books')

        # DEFAULTS
        store.default_bundle = (
            store._bundles.get(mode_data.default_bundle_id)
            or list(store._bundles.values())[-1]
        )
        store.default_language = (
            store._languages.get(mode_data.default_language_id)
            or store._languages['en']
        )
        # We only know about the default bundle and language and therefore have to
        # derive the default LanguageBundle by looking at all of them and choosing the
        # one that consists of the default bundle and the default language
        for language_bundle in store.language_bundles.values():
            if (
                language_bundle.bundle == store.default_bundle
                and language_bundle.language == store.default_language
            ):
                store.default_language_bundle = language_bundle
                break
        else:
            raise DocPortalError('Default LanguageBundle could not be set')

        # MISC
        store.base_uri = mode_data.base_uri
        store.temp_folder = mode_data.temp_folder

        # SAVE
        cls.CACHED_STORE = store

    @classmethod
    def instance(cls):
        """
        Return the singleton instance of the store.
        If not initialized or an update is needed, do it now.
        """
        if not cls.CACHED_STORE:
            with locked_with_logger(cls.lock, _logger):
                cls._build(load_mode_data())

        return cls.CACHED_STORE

    @lru_cache()
    def get_sibling_languages(self, bundle):
        """The sibling language of DE is normally only EN and vice versa."""
        sibling_languages = []
        for lb in self.language_bundles.values():
            if lb.bundle == bundle:
                sibling_languages.append(lb)
        return sibling_languages

    @lru_cache()
    def get_sibling_bundles(self, language):
        """
        Sibling bundles for a bundle 15.4 are all other bundles
        (e.g. 15.1, 15.2 and 15.3)
        """
        sibling_bundles = []
        for lb in self.language_bundles.values():
            if lb.language == language:
                sibling_bundles.append(lb)
        return sibling_bundles

    def get_bundle(self, bundle_id):
        """
        Get a bundle by its identifier
        :param bundle_id: bundle ID (str)
        :return: DocBundle object
        """
        return self._bundles.get(bundle_id)

    @lru_cache()
    def get_all_bundles(self):
        """
        Get the list of bundles available in the Store
        :return: a list of DocBundle objects
        """
        return list(self._bundles.values())

    def get_language(self, language_id):
        """
        Get a language by its 2 character ISO identifier. E.g.: `en`.
        :param language_id: language ID (str)
        :return: DocLanguage object
        """
        return self._languages.get(language_id)

    @lru_cache()
    def get_all_languages(self):
        """
        Get a list containing all languages that are supported by the Store.
        :return: a list of DocLanguage objects
        """
        return list(self._languages.values())

    def get_category(self, cat_id, lang_id):
        """
        Find a category by its category and language identifiers
        :param cat_id: str identifier
        :param lang_id: 2 character ISO lang code
        :return: DocCategory object
        """
        return self._categories.get((cat_id, lang_id))

    @lru_cache()
    def get_category_by_name(self, cat_name, lang_id):
        """
        Find a category object by its name
        :param cat_name: a category name e.g. 'User Manuals'
        :param lang_id: a language identifier e.g. 'en'
        :return: either the corresponding ``DocCategory`` object or None
        """
        for cat in self._categories.values():
            if cat.name == cat_name and cat.lang_id == lang_id:
                return cat
        return None

    @lru_cache()
    def get_all_categories(self, lang_id=None, ignore_unlisted=True):
        cats = []
        for c in self._categories.values():
            if lang_id and c.lang_id != lang_id:
                continue
            if ignore_unlisted and c.identifier == 'unlisted':
                continue
            cats.append(c)
        cats.sort(key=lambda cat: cat.orderval)
        return cats

    @lru_cache()
    def get_category_by_package(self, bundle_id, package_name, book_id, lang_id):
        """
        If you have a book, but don't know under which category you can find it,
        you can use this function. It will iterate over all books in the store and
        return the one that matches the given book ID, language and package name.

        If we did not find the correct category in current language then we try
        to look it up in the default language.

        :returns: either the corresponding category object or None
        """
        bundle = self._bundles[bundle_id]

        # Current docportal language
        for category in self.get_all_categories(lang_id=lang_id):
            books = self._books[bundle, category]
            for book in books:
                if book.identifier == book_id and book.package.name == package_name:
                    return category

        # Default language
        for category in self.get_all_categories(
            lang_id=self.default_language.identifier
        ):
            books = self._books[bundle, category]
            for book in books:
                if book.identifier == book_id and book.package.name == package_name:
                    return category

        return None

    @lru_cache()
    def get_books_by_category(self, bundle_id, language_id, category_id):
        """
        If the parameter `language_id` is equal to the default language ID of the store,
        this simply returns the list of books available for that query tuple.

        If it differs from the default language it compiles a list of books from two
        sets. The first set is the list of books for the queried language and the
        second is the list of books available for an identical query, but with its
        language set to the default language of the store. The first set is then
        expanded by the second. Therefore, books that supply both languages will show
        up in the queried language as expected, but books that don't support the
        requested language will still be visible.

        This is necessary because we want users that browse some category in their
        native language (e.g. German) to know that documentation for some book exists
        in English only without forcing them to look for it in the default language
        manually. Of course the "foreign" entries should be highlighted in the
        frontend somehow.
        :param bundle_id: string identifier for a bundle. e.g. '15.4'
        :param language_id: string identifier for a language. e.g. 'en'
        :param category_id: string identifier for a category. e.g. 'admin'
        :return: a list of books for the query tuple of bundle, language and category
        """
        category_books = set()
        bundle = self._bundles[bundle_id]

        try:
            category_books.update(
                self._books[bundle, self._categories[category_id, language_id]]
            )
        except KeyError:
            return []

        if not self.default_language.identifier == language_id:
            try:
                # expand set of books with books that only exist in the default language
                cat_default_lang = self._categories[
                    category_id, self.default_language.identifier
                ]
                category_books_default_lang = set(self._books[bundle, cat_default_lang])
                category_books.update(category_books_default_lang)
            except KeyError:
                pass

        return sorted(category_books, key=lambda x: x.name)

    @lru_cache()
    def get_bundle_toc(self, language_bundle, bundle, language):
        res = []

        def recurse_book_tree(result, toc, href, is_index=False):
            for elem in toc:
                # prevent creating a toc elem for inner page jumps
                if elem.anchor_id:
                    continue

                # append child
                result[-1].children.append(
                    DocTreeNode(
                        uid=elem.identifier,
                        name=elem.name,
                        href=href + elem.identifier,
                        package=None,
                        node_type=DocTreeNodeType.BOOK_INDEX
                        if is_index
                        else DocTreeNodeType.BOOK_PAGE,
                    )
                )
                recurse_book_tree(result[-1].children, elem, href)

        def recurse_category_tree(result, subcategories, href, topcat_id, categ_path):
            for subcat in sorted(subcategories, key=lambda s: s.orderval):
                result.append(
                    DocTreeNode(
                        uid=subcat.identifier,
                        name=subcat.name,
                        href=href,
                        package=None,
                        node_type=DocTreeNodeType.SUB_CATEGORY,
                    )
                )
                recurse_category_tree(
                    result[-1].children,
                    subcat.subcategories,
                    href,
                    topcat_id,
                    categ_path + [subcat.identifier],
                )

                for book_id in subcat.books:
                    for book_sub in self.get_books_by_category(
                        bundle, language, topcat_id
                    ):
                        if book_sub.identifier == book_id:
                            book_subhref = href + '/' + book_sub.identifier + '/'
                            self.book_paths[book_sub.identifier] = categ_path + [
                                subcat.identifier
                            ]
                            result[-1].children.append(
                                DocTreeNode(
                                    uid=book_sub.identifier,
                                    name=book_sub.name,
                                    href=book_subhref,
                                    package=book_sub.package.name,
                                    node_type=DocTreeNodeType.BOOK_INDEX,
                                )
                            )
                            recurse_book_tree(
                                result=result[-1].children,
                                toc=book_sub.toc(),
                                href=book_subhref,
                            )

        base_url = f'{self.base_uri}{language_bundle.identifier}/'

        for cat in self.get_all_categories(lang_id=language):
            cat_href = base_url + cat.identifier + '/'
            res.append(
                DocTreeNode(
                    uid=cat.identifier,
                    name=cat.name,
                    href=cat_href,
                    package=None,
                    node_type=DocTreeNodeType.MAIN_CATEGORY,
                )
            )

            if os.environ.get('DOCPORTAL_CUSTOM_CATEGORY_YAML'):
                # nested ToC
                recurse_category_tree(
                    result=res[-1].children,
                    subcategories=cat.subcategories,
                    href=cat_href,
                    topcat_id=cat.identifier,
                    categ_path=[],
                )

                for book_id in cat.books:
                    for book in self.get_books_by_category(
                        bundle, language, cat.identifier
                    ):
                        if book.identifier == book_id:
                            book_href = cat_href + book.identifier + '/'
                            res[-1].children.append(
                                DocTreeNode.from_book(
                                    book=book,
                                    href=book_href,
                                    node_type=DocTreeNodeType.BOOK_INDEX,
                                )
                            )
                            recurse_book_tree(
                                res[-1].children,
                                book.toc(),
                                book_href,
                            )

            else:
                # normal flat ToC
                cat_books = self.get_books_by_category(bundle, language, cat.identifier)
                if not cat_books:
                    continue

                for book in cat_books:
                    book_href = cat_href + book.identifier + '/'
                    res[-1].children.append(
                        DocTreeNode.from_book(
                            book=book,
                            href=book_href,
                            node_type=DocTreeNodeType.BOOK_INDEX,
                        )
                    )
                    recurse_book_tree(
                        result=res[-1].children, toc=book.toc(), href=book_href
                    )

        return res


class LanguageBundle:
    def __init__(self, identifier, bundle, language):
        self.identifier = identifier
        self.bundle = bundle
        self.language = language

    def __repr__(self):
        return f'LanguageBundle({self.identifier}, {self.bundle}, {self.language})'


class DocLanguage:
    """Language definition and all associated translations for that language."""

    def __init__(self, identifier, name, translations):
        self.identifier = identifier
        self.name = name
        self._translations = translations

    def translate_label(self, label):
        """Translates the specified label if a localisation is provided"""
        try:
            translated_label = self._translations[label]
        except KeyError:
            translated_label = f'!{label}!'
        return translated_label

    def __repr__(self):
        return f'DocLanguage({self.identifier}, {len(self._translations)})'


class DocBundle:
    """The entirety of documentation for one CONTACT Elements umbrella release"""

    def __init__(self, identifier, name, packages, index_path):
        self.identifier = identifier
        self.name = name
        self.packages = packages
        self.index_path = index_path
        self.search_index = None
        self.lock = Lock()

    def _initialize_index(self):
        with locked_with_logger(self.lock, _logger):
            if self.search_index and self.search_index.stage.name == 'READY':
                return

            self.search_index = search.SearchIndex(
                path=self.index_path,
                name=self.identifier,
                packages=self.packages,
            )

    def search(self, categories, query_str, length=500, page=1):
        """Search for a query inside the search index"""
        self._initialize_index()
        return self.search_index.search(
            categories=categories, query_str=query_str, length=length, page_number=page
        )

    def suggest_terms(self, lang_id, query_str):
        """Search for a term inside the search index"""
        self._initialize_index()
        return self.search_index.suggest_terms(lang_id, query_str)

    def __repr__(self):
        return f'DocBundle({self.identifier}, "{self.name}")'


class DocCategory:
    """A category has many books"""

    def __init__(
        self,
        name,
        identifier,
        lang_id,
        teaser,
        orderval,
        icon,
        subcategories=None,
        books=None,
    ):
        """
        TODO: document
        :param name:
        :param identifier:
        :param lang_id:
        :param teaser:
        :param orderval:
        :param icon:
        :param subcategories:
        :param books:
        """
        self.name = name
        self.identifier = identifier
        self.lang_id = lang_id
        self.icon = icon
        self.teaser = teaser
        self.orderval = orderval

        self.subcategories = subcategories
        self.books = books

    def __repr__(self):
        return f'DocCategory({self.name}, {self.identifier}, {self.lang_id})'


class DocBook:
    """A general book contains many localisations and stores common data
    between them."""

    _INTERNAL_FORMATS = ['html', 'pickle', 'chm']

    def __init__(
        self,
        identifier,
        name,
        lang_id,
        db_id,
        docdb,
        teaser,
        path,
        extra_formats,
        package=None,
    ):
        self.identifier = identifier
        self.name = name
        self.db_id = db_id
        self.lang_id = lang_id
        self.teaser = teaser
        self.package = package
        self.resource_path = path / lang_id / 'html'
        self.formats = {
            fmt: extra_formats[fmt]
            for fmt in extra_formats
            if fmt not in DocBook._INTERNAL_FORMATS
        }
        self._pages = self._read_db_pages(docdb)
        self.index_page = self.page('index')
        self._toc = self._read_db_toc(docdb)

    def _read_db_pages(self, docdb):
        res = {}
        for row in docdb.pages(self.db_id):
            res[row.get('identifier')] = DocPage(**row)
        return res

    def _read_db_toc(self, docdb):
        tocs = {}
        res_toc = None

        def inner_page_jumps(page, tid, parent_tid):
            if page:
                if page.table_id == parent_tid:
                    tree.table_id = tid
                    page.toc.append(tree)
                else:
                    for tree_item in page.toc:
                        if tree_item.table_id == parent_tid:
                            tree_item.append(tree)
                            break

        for tid, parent_tid, title, uri, anchor in docdb.toc(self.db_id):
            tree = DocTree(title, uri, anchor)

            if anchor:
                inner_page_jumps(self.page(uri), tid, parent_tid)
                continue

            if parent_tid in tocs:
                tocs[parent_tid].append(tree)
                page = self.page(uri)
                if page:
                    page.parent_id = tocs[parent_tid].identifier
                    page.table_id = tid

            if not parent_tid:
                res_toc = tree
            tocs[tid] = tree

        return res_toc

    def page(self, page_id):
        return self._pages.get(page_id)

    def page_toc(self, page_id):
        raise NotImplementedError('Not yet implemented')

    def toc(self):
        return self._toc or []

    def info(self):
        return [
            ('Package', self.package.name),
            ('Version', self.package.version),
            ('Date', datetime.fromtimestamp(self.package.stat.st_mtime).date()),
        ]

    def ancestors(self, current_page_id):
        """
        A DocPage doesn't know about the number of ancestors it may have.
        This method recursively collects tuples of DocPage IDs and names until it finds
        the index page of the respective book and no further ancestors exist.
        :param current_page_id: The ID of the current page (leaf node ID)
        :return ancestors: A list of page IDs of current page's ancestors (ancestor IDs)
        """

        def recurse_ancestors(page):
            if page and page.parent_id:
                return recurse_ancestors(self.page(page.parent_id)) + [
                    (page.identifier, page.name)
                ]
            else:
                return []

        return recurse_ancestors(self.page(current_page_id))

    def __repr__(self):
        return f'DocBook(name={self.name}, id={self.identifier}, lang={self.lang_id})'

    def __eq__(self, other):
        if isinstance(other, DocBook):
            return self.identifier == other.identifier
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.identifier)


class DocPage:
    """A page is part of a localized book and has content"""

    def __init__(self, identifier, name, next_link, prev_link, body):
        self.identifier = identifier
        self.name = name
        self.next_link = next_link
        self.prev_link = prev_link
        self.content = body
        self.parent_id = None
        self.toc = DocTree(name, identifier, None)
        if self.content:
            for tag in ['<html><body>', '</body>', '</html>']:
                self.content = self.content.replace(tag, '')
        self.table_id = None

    def __repr__(self):
        return f'DocPage(id={self.identifier}, name={self.name})'


class DocTree(list):
    """A tree has many nodes and is used for representing a TOC."""

    def __init__(self, name, identifier, anchor_id):
        super().__init__()
        self.name = name
        self.identifier = identifier
        self.anchor_id = anchor_id
        self.table_id = None

    def is_current(self, router, book):
        """Convenience method for checking current node in a hierarchical structure"""
        is_current = router.is_current(
            'overview.category.book.page',
            {'book_id': book.identifier, 'page_id': self.identifier},
        )
        is_descendant = any(child.is_current(router, book) for child in self)
        return is_current or is_descendant

    def __repr__(self):
        result = f'DocTree name="{self.name}" id={self.identifier} size={len(self)}'
        if self:
            result += f' [{super(DocTree, self).__repr__()}]'

        return result


class DocTreeNodeType(Enum):
    BOOK_INDEX = 0
    BOOK_PAGE = 1
    CATEGORY = 2
    SUB_CATEGORY = 3
    MAIN_CATEGORY = 4


class DocTreeNode:
    def __init__(self, uid, name, href, package, node_type):
        self.uid = uid
        self.name = name
        self.children = []
        self.href = href
        self.package = package
        self.node_type = node_type

    @classmethod
    def from_book(cls, book, href, node_type):
        return DocTreeNode(
            uid=book.identifier,
            name=book.name,
            href=href,
            package=book.package.name,
            node_type=node_type,
        )
