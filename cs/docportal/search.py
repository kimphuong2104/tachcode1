# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Search logic for the documentation portal.
"""
import math
import re
from enum import Enum
from itertools import chain
from multiprocessing import cpu_count
from pathlib import Path

import whoosh.analysis
import whoosh.fields
import whoosh.formats
import whoosh.highlight
import whoosh.index
import whoosh.qparser
import whoosh.query
import whoosh.searching
import whoosh.sorting
import whoosh.spelling

from cs.docportal.loader import StandaloneDocPortalData
from cs.docportal.util import get_logger

__all__ = ['SearchIndex']


_logger = get_logger(__name__)


class ExcerptFormatter(whoosh.highlight.HtmlFormatter):
    """Custom highlight formatter for search result page"""

    def __init__(self):
        super().__init__(tagname='span', classname='match', termclass='term')
        self.newline_re = re.compile(r'[\n\r]+')

    def format_fragment(self, fragment, replace=False):
        res = super(ExcerptFormatter, self).format_fragment(fragment, replace)
        res = self.newline_re.sub(' &hellip; ', res)
        return '<span class="match-block">%s</span>' % (res,)

    def format(self, fragments, replace=False):
        formatted = [self.format_fragment(f, replace=replace) for f in fragments]
        return ''.join(formatted)


class IndexStage(Enum):
    READY = 0
    OPTIMIZING = 1
    MERGING = 2
    INITIATED = 3


class SearchIndex:
    """
    This class provides search index operations.

    class attributes:
        title_multiplier    If the query term is found in the title field, the result
                            score will be multiplied by this numeric value
        whoosh_schema       Predefines all the fields our whoosh search indexes will use
    """

    title_multiplier = 2.0

    whoosh_schema = whoosh.fields.Schema(
        kind=whoosh.fields.ID(stored=True),
        title=whoosh.fields.TEXT(stored=True, field_boost=title_multiplier),
        uri=whoosh.fields.ID(stored=True, unique=True),
        time=whoosh.fields.STORED,
        body=whoosh.fields.TEXT(stored=True),
        name=whoosh.fields.ID(stored=True),
        lang=whoosh.fields.ID(stored=True),
        bookname=whoosh.fields.ID(stored=True),
        category=whoosh.fields.ID(stored=True),
        title_de=whoosh.fields.TEXT(stored=True, field_boost=title_multiplier),
        title_en=whoosh.fields.TEXT(stored=True, field_boost=title_multiplier),
        body_de=whoosh.fields.TEXT(stored=True),
        body_en=whoosh.fields.TEXT(stored=True),
    )

    def __init__(self, name, path, packages):
        """
        Initialize a Whoosh search index in a target directory from a list of given CDB
        package directories. These packages usually contain prebuilt search indexes and
        will be merged into a single search index in order to allow for queries against
        all packages that are contained in an umbrella release (or custom) bundle.
        :param path: storage directory for the search index
        """
        path.mkdir(exist_ok=True)
        self.index = None
        self.name = name
        self.path = path
        self.stage = IndexStage.INITIATED
        self.packages = packages

        index_args = {
            'dirname': self.path,
            'indexname': f'index-{name}-{self.packages.hash}',
        }

        if whoosh.index.exists_in(**index_args):
            try:
                self.index = whoosh.index.open_dir(**index_args)
                if self.index.doc_count() > 0:
                    self.stage = IndexStage.READY
                    _logger.info(self)
                    return
            except (whoosh.index.IndexError, OSError) as e:
                _logger.debug('Broken SearchIndex: %s (Exception: %s)', self, e)
                _logger.debug('Cleaning index directory: %s', self.path)
                for node in self.path.iterdir():
                    node.unlink()

        _logger.info('Creating new SearchIndex: %s', self)
        self.index = whoosh.index.create_in(schema=self.whoosh_schema, **index_args)

        self.stage = IndexStage.MERGING
        _logger.info(self)
        self._merge(packages)

        self.stage = IndexStage.OPTIMIZING
        _logger.info(self)
        self.index.optimize()

        self.stage = IndexStage.READY
        _logger.info(self)

    def __repr__(self):
        return 'SearchIndex({name}|[{val}]{stage}|{doc_hash}|n={count})'.format(
            name=self.name,
            stage=self.stage.name,
            val=self.stage.value,
            doc_hash=self.packages.hash[:8],
            count=len(self.packages),
        )

    def _merge(self, packages):
        """Recreates the hierarchical search index"""
        writer_opts = {'limitmb': 300, 'procs': cpu_count(), 'multisegment': True}
        with self.index.writer(**writer_opts) as writer:
            # > When you're indexing in large batches with a one-shot instance of the
            # > analyzer, consider using an unbounded cache:
            # https://whoosh.readthedocs.io/en/latest/batch.html

            _logger.debug(
                'Merging into new SearchIndex for %d packages.', len(packages)
            )
            for package in packages:
                try:
                    pkg_index = whoosh.index.open_dir(package.index_path, readonly=True)
                except (OSError, whoosh.index.EmptyIndexError) as e:
                    _logger.debug(
                        'Problematic SearchIndex for package %s. (%s)', package.path, e
                    )
                    continue

                with pkg_index.searcher() as pkg_searcher:
                    for doc in pkg_searcher.documents():
                        lang = doc['lang']
                        doc[f'title_{lang}'] = doc['title']
                        doc[f'body_{lang}'] = doc['body']
                        writer.add_document(**doc)

                pkg_index.close()

    def search(self, categories, query_str, length=50, page_number=1):
        """Searches for documents that match the query_string, category
        and language. This method allows pagination by setting the
        `length` to a small value and changing the `page` parameter.

        :param categories: The name of the category or categories to search in.
               It can be ``None`` or `all` to ignore
        :param query_str: The search query.
        :param length: The maximum size of the result pages.
        :param page_number: The number of the page to fetch results for.

        :return: There are three result objects:
                 - A whoosh page object containing the search results
                 - A whoosh highlighter object for visualization of found text excerpts
                 - A boolean telling us whether the query is multi-word or not
        """
        if page_number < 1:
            raise ValueError('Page number must be >= 1')

        def lang_sort_fn(key):
            return 0 if key == categories[0].lang_id else 10

        match_str_parser = whoosh.qparser.MultifieldParser(
            fieldnames=['body', 'title'],
            schema=self.index.schema,
        )
        q = match_str_parser.parse(query_str)

        # collapse entries into single result, when kind, uri and bookname are the same
        name_facet = whoosh.sorting.MultiFacet(['kind', 'uri', 'bookname'])

        # prefer current portal language when collapsing into single result
        collapse_order_facet = whoosh.sorting.TranslateFacet(
            lang_sort_fn, whoosh.sorting.StoredFieldFacet('lang')
        )

        searcher = self.index.searcher()

        filter_query = whoosh.query.NullQuery()
        category_query = whoosh.query.NullQuery()
        for cat in categories:
            filter_query = whoosh.query.Or(
                [filter_query, whoosh.query.Term('lang', cat.lang_id)]
            )
            category_query = whoosh.query.Or(
                [category_query, whoosh.query.Term('category', cat.name)]
            )

        filter_query = whoosh.query.And([filter_query, category_query])

        _query = whoosh.query.And([q, filter_query])
        _collector = searcher.collector(
            limit=None, collapse=name_facet, collapse_order=collapse_order_facet
        )

        searcher.search_with_collector(_query, _collector)

        page = whoosh.searching.ResultsPage(_collector.results(), page_number, length)
        # workaround for a whoosh issue, where pagelen, pagecount and total
        # don't reflect collapsed results
        page.total = len(page.results.top_n)
        page.pagecount = int(math.ceil(page.total / float(length)))
        page.pagelen = max(0, min(length, page.total - ((page_number - 1) * length)))
        page.results.formatter = ExcerptFormatter()
        page.results.order = whoosh.highlight.SCORE

        title_hl = whoosh.highlight.Highlighter(
            fragmenter=whoosh.highlight.WholeFragmenter()
        )

        # This condition is used to identify single vs. multi-word queries based
        # on how whoosh partitions the query into objects.
        # A search for one word will end up as a search for "term" in the titles or in
        # the bodies and therefore look like an ``Or(term:body, term:title)``.
        # Therefore we can say, if the toplevel is an ``Or`` and the query does
        # not have more than 2 subqueries (title and body for each term) then the given
        # query must be a single word query; otherwise it's a multi-word query.
        if isinstance(q, whoosh.query.compound.Or) and len(q.subqueries) <= 2:
            is_multi_query = False
        else:
            is_multi_query = True

        return page, title_hl, is_multi_query

    def suggest_terms(self, lang_id, query_str, number=10):
        """
        Grabs the terms matching the query string from the whoosh index.
        Used for suggesting terms / autocompletion in search.

        Whoosh only supports `most_distinctive_terms` per table column.
        Therefore, it is not possible to get tf-idf for a specific query since
        it is saved in SearchIndex.

        To bypass this we duplicate the columns for each language.
        """
        res = []
        q = query_str.lower()
        if q.strip():
            with self.index.reader() as reader:
                result_iterator = chain(
                    reader.most_distinctive_terms(
                        fieldname=f'title_{lang_id}', number=number, prefix=q
                    ),
                    reader.most_distinctive_terms(
                        fieldname=f'body_{lang_id}', number=number, prefix=q
                    ),
                )
                for score, term in result_iterator:
                    decoded_term = term.decode('utf-8')
                    if decoded_term not in res:
                        res.append(decoded_term)
        return res

    def corrections(self, query, maxdist=2):
        """
        Generate a list of closely matching words from the search index for
        a given query.This is used to show the user alternative search terms
        in case his search did not produce any results.

        :param query: A search query consisting of one or more words
        :param maxdist: maximum distance to other words (default: 2 char diff)
        :return: A list of close matches to the input query
        """
        field = whoosh.fields.FieldType(
            format=whoosh.formats.Format(), analyzer=whoosh.analysis.Analyzer()
        )
        corrector = whoosh.spelling.ReaderCorrector(
            reader=self.index.reader(), fieldname='body', fieldobj=field
        )
        return corrector.suggest(query, limit=5, maxdist=maxdist)


def prebuild_searchindex_cdb():
    """Generate DocPortal's search index for running inside a CDB instance."""
    from cs.docportal.loader import CDBDocPortalData
    from cs.docportal.models import DocBundle

    data = CDBDocPortalData()
    bundle_args = data.bundles[0]
    bundle = DocBundle(**bundle_args)

    SearchIndex(
        path=data.temp_folder,
        name=bundle.identifier,
        packages=bundle.packages,
    )


def prebuild_searchindex_standalone(path: Path):
    """
    Prebuild a search index for all documentation bundles inside that directory.

    :param path: path to the directory containing the documentation bundles
    """
    for bundle_path in path.iterdir():
        if not bundle_path.is_dir():
            continue

        index_path = bundle_path / '_docindex'
        packages = StandaloneDocPortalData.load_packages(bundle_path)
        if not packages:
            raise RuntimeError(f'No CDB packages found at {bundle_path}')

        _logger.info('Trying to generate SearchIndex for %s', bundle_path.name)
        SearchIndex(name=bundle_path.name, path=index_path, packages=packages)


if __name__ == '__main__':
    from sys import argv

    _logger.debug('Pre-building SearchIndex for the Documentation Portal...')

    if len(argv) < 2:
        prebuild_searchindex_cdb()

    elif Path(argv[1]).is_dir():
        prebuild_searchindex_standalone(path=Path(argv[1]))

    else:
        raise ValueError(
            'First argument is neither empty nor a directory containing '
            'documentation bundles for a standalone DocPortal. Aborting!'
        )

    _logger.debug('Finished pre-building SearchIndex for the Documentation Portal.')
