# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

""" Routes for documentation portal. """

import os
import re
import time
from datetime import date
from pathlib import Path
from threading import Lock
from urllib import parse as urllib_parse

import morepath
import morepath.traject
import webob.exc
import webob.static

from cs.docportal import models, util

__all__ = ['App']

_logger = util.get_logger(__name__)


# APPS #################################################################################
class App(morepath.App):
    lock = Lock()
    COMMITTED = False

    def __init__(self):
        super().__init__()

        self.current_route = None
        self.current_route_vars = {}

    @classmethod
    def guarded_commit(cls):
        """A threadsafe version of morepath.app.App.commit"""
        if cls.COMMITTED:
            return

        with util.locked_with_logger(cls.lock, _logger):
            if cls.COMMITTED:
                return
            cls.commit()
            cls.COMMITTED = True


# CLASSES ##############################################################################
class StartRoute:
    pass


class StaticRoute:
    def __init__(self, path: str):
        if Path(path).is_absolute():
            raise webob.exc.HTTPForbidden('Absolute paths NOT allowed')

        self.path = util.module_root_dir() / 'static' / path


class LanguageBundleRoute:
    def __init__(self, language_bundle, params):
        self.store = models.Store.instance()
        self.template = 'home.html'
        self.params = params or {}
        self.is_directory = True
        self.route_object = {'name': language_bundle}

        try:
            self.language_bundle = self.store.language_bundles[language_bundle]
        except KeyError:
            self._raise_not_found()

    @classmethod
    def _raise_not_found(cls):
        """
        :raises webob.exc.HTTPNotFound
        """
        name = cls.__name__
        parent_routes = list(reversed(cls.__mro__))[1:]
        level = len(parent_routes) + 1

        error = webob.exc.HTTPNotFound('Unknown {} (Level: {})'.format(name, level))
        error.routing_class = name
        error.routing_level = level
        error.parent_routes = parent_routes

        raise error

    def template_vars(self, environ):
        return {
            'model': self,
            'store': self.store,
            'sibling_bundles': self.store.get_sibling_bundles(
                language=self.language_bundle.language
            ),
            'sibling_languages': self.store.get_sibling_languages(
                bundle=self.language_bundle.bundle
            ),
            'language_bundle': self.language_bundle,
            'categories': self.store.get_all_categories(
                lang_id=self.language_bundle.language.identifier
            ),
            'query': '',
            'highlight': self.params.get('highlight', ''),
            'year': date.today().year,
            'base_uri': self.store.base_uri,
            'toc': self.store.get_bundle_toc(
                language_bundle=self.language_bundle,
                bundle=self.language_bundle.bundle.identifier,
                language=self.language_bundle.language.identifier,
            ),
            'toc_position': [],
            'route_type': self.__class__.__name__,
        }

    def __repr__(self):
        return f'{self.__class__.__name__}: {vars(self)}'


class CategoryRoute(LanguageBundleRoute):
    def __init__(self, language_bundle, category, params):
        super().__init__(language_bundle, params)
        self.template = 'category.html'
        self.category = self.store.get_category(
            category, self.language_bundle.language.identifier
        )
        if not self.category:
            self._raise_not_found()
        self.books = {
            b.identifier: b
            for b in self.store.get_books_by_category(
                bundle_id=self.language_bundle.bundle.identifier,
                language_id=self.language_bundle.language.identifier,
                category_id=category,
            )
        }
        self.route_object = self.category

    def template_vars(self, environ):
        tmpl_vars = super(CategoryRoute, self).template_vars(environ)

        tmpl_vars.update(
            {
                'category': self.category,
                'books': self.books.values(),
                'toc_position': [self.category.identifier],
            }
        )
        return tmpl_vars


class BookRoute(CategoryRoute):
    def __init__(self, language_bundle, category, book, params):
        super().__init__(language_bundle, category, params)
        self.template = 'book.html'
        try:
            self.book = self.books[book]
        except KeyError:
            self._raise_not_found()
        self.route_object = self.book

    def template_vars(self, environ):
        tmpl_vars = super(BookRoute, self).template_vars(environ)

        tmpl_vars.update(
            {
                'book': self.book,
                'page': self.book.index_page,
                'formats': self.book.formats,
                'breadcrumb': [(self.book.identifier, self.book.name)],
            }
        )
        tmpl_vars['toc_position'].extend(
            self.store.book_paths.get(self.book.identifier, []) + [self.book.identifier]
        )
        return tmpl_vars


class BookPageRoute(BookRoute):
    def __init__(self, language_bundle, category, book, page, params):
        super().__init__(language_bundle, category, book, params)
        self.page = self.book.page(page)
        if not self.page:
            self._raise_not_found()
        self.ancestors = self.book.ancestors(page)
        self.is_directory = False
        self.route_object = 'BookPage'

    def template_vars(self, environ):
        tmpl_vars = super(BookPageRoute, self).template_vars(environ)

        tmpl_vars['model'] = self
        tmpl_vars['page'] = self.page
        tmpl_vars['breadcrumb'] += self.ancestors
        tmpl_vars['toc_position'] += [x[0] for x in self.ancestors]
        return tmpl_vars


class BookDocumentRoute(BookRoute):
    """Download the book in a given format (typically only PDF)"""

    def __init__(self, language_bundle, category, book, document_format, params):
        super().__init__(language_bundle, category, book, params)
        self.document_format = document_format
        self.path = self.book.resource_path / self.document_format


class BookDownloadsRoute(BookRoute):
    """Download book resources referenced via RST ``:download:`` rules"""

    def __init__(self, language_bundle, category, book, resource, params):
        super().__init__(language_bundle, category, book, params)
        self.resource = resource
        self.path = self.book.resource_path / '_downloads' / self.resource


class BookImageRoute(BookRoute):
    def __init__(self, language_bundle, category, book, image_path, params):
        super().__init__(language_bundle, category, book, params)
        self.path = self.book.resource_path / '_images' / image_path


class SearchRoute(LanguageBundleRoute):
    def __init__(self, language_bundle, query, params):
        super().__init__(language_bundle, params)
        self.template = 'search.html'
        self.query = query
        self.is_directory = False
        self.route_object = 'Search'
        for term in query.split(' '):
            if term and term[0] == '*':
                raise webob.exc.HTTPForbidden(
                    'Terms with leading wildcards are not allowed: ' + term
                )

    def template_vars(self, environ):
        tmpl_vars = super(SearchRoute, self).template_vars(environ)

        res = self.language_bundle.bundle.search(
            self.store.get_all_categories(), self.query
        )
        if not res:
            raise RuntimeError('Error executing search')

        results, title_highlight, is_multi_query = res
        book_links = {}
        ignores = set()

        # corrections for typos etc.
        corrections = (
            self.language_bundle.bundle.search_index.corrections(self.query)
            if results.total == 0
            else None
        )

        for result in results:
            fields = result.fields()
            category = self.store.get_category_by_name(
                fields.get('category'), fields.get('lang')
            )

            if 'bookname' in fields and fields.get('bookname'):
                for book in self.store.get_books_by_category(
                    bundle_id=self.language_bundle.bundle.identifier,
                    category_id=category.identifier,
                    language_id=self.language_bundle.language.identifier,
                ):
                    if book.identifier == fields.get('bookname'):
                        book_links[result.docnum] = (book, category, result.score)
                        break
                else:
                    ignores.add(result.docnum)

        def get_uri(result, query):
            category = None
            uri = None
            uri_hash = None
            if 'category' in result.fields():
                category = self.store.get_category_by_name(
                    result.get('category'),
                    result.get('lang', self.language_bundle.language.identifier),
                )
            if not category:
                uri = result.get('uri')

            if not uri and result.fields().get('name', '') == 'teaser':
                uri = f'{category.identifier}/'
                uri_hash = result.get('bookname')

            if not uri and 'bookname' in result.fields():
                uri = '{category}/{book}/{uri}'.format(
                    category=category.identifier,
                    book=result.get('bookname'),
                    uri=result.get('uri'),
                )
            elif not uri:
                uri = f'{category.identifier}/{result.get("uri")}'
            highlight_query = {'highlight': query.encode('utf8')}
            link = urllib_parse.urlunparse(
                [
                    '',
                    '',
                    uri,
                    '',
                    urllib_parse.urlencode(highlight_query),
                    uri_hash,
                ]
            )
            return link

        tmpl_vars.update(
            {
                'search_results': results,
                'title_highlight': title_highlight,
                'book_links': book_links,
                'query': self.query,
                'get_uri': get_uri,
                'ignores': ignores,
                'corrections': corrections,
                'is_multi_query': is_multi_query,
            }
        )

        return tmpl_vars


class SearchACRoute(LanguageBundleRoute):
    def __init__(self, language_bundle, query, params):
        super().__init__(language_bundle, params)
        self.query = query

    def template_vars(self, environ):
        return self.language_bundle.bundle.suggest_terms(
            self.language_bundle.language.identifier, self.query
        )


class PackageRedirectRoute(LanguageBundleRoute):
    def __init__(self, language_bundle, package, book, page, params):
        super().__init__(language_bundle, params)
        self.package = package
        self.book = book
        self.page = page.replace('.html', '') if page else ''
        self.category = self.store.get_category_by_package(
            self.language_bundle.bundle.identifier,
            package,
            book,
            self.language_bundle.language.identifier,
        )

        # otherwise the resource does not exist
        if not self.category:
            _logger.debug('Package redirect does not exist %s', self)
            self._raise_not_found()


# ROUTES ###############################################################################
@App.path(model=StartRoute, path='')
def start_route():
    return StartRoute()


@App.path(model=StaticRoute, path='static/', absorb=True)
def static_route(absorb):
    return StaticRoute(path=absorb)


@App.path(model=LanguageBundleRoute, path='{language_bundle}/')
def bundle_route(app, language_bundle, extra_parameters):
    app.current_route = LanguageBundleRoute
    return LanguageBundleRoute(language_bundle, extra_parameters)


@App.path(model=CategoryRoute, path='{language_bundle}/{category}/')
def category_route(app, language_bundle, category, extra_parameters):
    app.current_route = CategoryRoute
    return CategoryRoute(language_bundle, category, extra_parameters)


@App.path(model=BookRoute, path='{language_bundle}/{category}/{book}/')
def book_route(app, language_bundle, category, book, extra_parameters):
    app.current_route = BookRoute
    return BookRoute(language_bundle, category, book, extra_parameters)


@App.path(
    model=BookPageRoute,
    absorb=True,
    path='{language_bundle}/{category}/{book}/{page}',
)
def book_page_route(
    app, language_bundle, category, book, page, extra_parameters, absorb
):
    # next 3 lines are necessary for js pages as their tails are also used
    # as their IDs
    if absorb and not absorb[0] == '/':
        absorb = '/' + absorb
    page = page + absorb
    app.current_route = BookPageRoute
    return BookPageRoute(language_bundle, category, book, page, extra_parameters)


@App.path(
    model=BookDocumentRoute,
    path='{language_bundle}/{category}/{book}/_document/{document_format}',
)
def book_document_route(
    app, language_bundle, category, book, document_format, extra_parameters
):
    app.current_route = BookDocumentRoute
    return BookDocumentRoute(
        language_bundle, category, book, document_format, extra_parameters
    )


@App.path(
    model=BookDownloadsRoute,
    path='{language_bundle}/{category}/{book}/_downloads/{resource}',
    absorb=True,
)
def book_downloads_route(
    app, language_bundle, category, book, resource, extra_parameters, absorb
):
    app.current_route = BookDownloadsRoute
    return BookDownloadsRoute(
        language_bundle, category, book, f'{resource}/{absorb}', extra_parameters
    )


@App.path(
    model=BookImageRoute,
    absorb=True,
    path='{language_bundle}/{category}/{book}/_images/',
)
def book_image_route(app, language_bundle, category, book, extra_parameters, absorb=''):
    app.current_route = BookImageRoute
    return BookImageRoute(language_bundle, category, book, absorb, extra_parameters)


@App.path(
    model=SearchRoute,
    path='{language_bundle}/search',
    converters={'searchlang': []},
    required=['q'],
    variables=lambda obj: {
        'q': obj.query,
        'page': obj.page,
        'category': obj.category,
        'searchlang': obj.lang,
    },
)
def search_route(app, language_bundle, extra_parameters, q=''):
    app.current_route = SearchRoute

    return SearchRoute(language_bundle, q, extra_parameters)


@App.path(
    model=SearchACRoute,
    path='{language_bundle}/search_ac',
    variables=lambda obj: {'q': obj.query},
)
def search_autocomplete_route(app, language_bundle, q, extra_parameters):
    app.current_route = SearchACRoute
    return SearchACRoute(language_bundle, q, extra_parameters)


@App.path(
    model=PackageRedirectRoute,
    absorb=True,
    path='{language_bundle}/_inpackage/{package}/{book}',
)
def package_redirect_route(
    app, language_bundle, package, book, extra_parameters, absorb=''
):
    page = absorb
    app.current_route = PackageRedirectRoute
    return PackageRedirectRoute(language_bundle, package, book, page, extra_parameters)


# VIEWS ################################################################################
def _check_trailing_slash_redirect(url, is_directory):
    """
    Enforce trailing slashes for URLs.

    :param url: str: the original URL
    :param is_directory: bool: should this URL end on a slash?
    :raises HTTPMovedPermanently: if URL state is wrong
    """
    parsed_url = urllib_parse.urlparse(url)
    base_uri = os.environ.get('DOCPORTAL_BASEURI', '/')

    def _redirect(new_path):
        new_url = urllib_parse.urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                new_path,
                parsed_url.params,
                parsed_url.query,
                parsed_url.fragment,
            )
        )
        raise webob.exc.HTTPMovedPermanently(location=new_url)

    # IF url doesn't end on a slash but IS a directory
    if is_directory and not parsed_url.path.endswith('/'):
        _redirect(base_uri + parsed_url.path[1:] + '/')

    # IF url does end on a slash but IS NO directory
    elif not is_directory and parsed_url.path.endswith('/'):
        _redirect(base_uri + parsed_url.path[1:-1])


def _view(model, request):
    """Base view for all other views"""
    _check_trailing_slash_redirect(request.environ['PATH_INFO_RAW'], model.is_directory)
    tvars = model.template_vars(request.environ)
    _logger.info('Request %s: "%s"', request.method, request.environ['PATH_INFO_RAW'])
    return util.load_template(model.template).render(router=request, **tvars)


@App.html(model=LanguageBundleRoute)
def bundle_view(model, morepath_request):
    return _view(model, morepath_request)


@App.html(model=CategoryRoute)
def category_view(model, morepath_request):
    return _view(model, morepath_request)


@App.html(model=BookRoute)
def book_view(model, morepath_request):
    return _view(model, morepath_request)


@App.html(model=BookPageRoute)
def page_view(model, morepath_request):
    return _view(model, morepath_request)


def _file_view(model, morepath_request):
    file_app = webob.static.FileApp(model.path)
    response = morepath_request.get_response(file_app)

    if response.status_code == 200:
        response.cache_control = 'public'
        response.expires = time.time() + (15 * 60)
    elif response.status_code == 404:
        return webob.exc.HTTPNotFound
    elif response.status_code == 403:
        return webob.exc.HTTPForbidden

    return response


@App.view(model=BookDocumentRoute)
def format_view(model, morepath_request):
    return _file_view(model, morepath_request)


@App.view(model=BookImageRoute)
def image_view(model, morepath_request):
    return _file_view(model, morepath_request)


@App.view(model=BookDownloadsRoute)
def resource_view(model, morepath_request):
    return _file_view(model, morepath_request)


@App.html(model=SearchRoute, request_method='POST')
def search_view(model, morepath_request):
    tvars = model.template_vars(morepath_request.environ)
    return util.load_template(model.template).render(router=morepath_request, **tvars)


@App.json(model=SearchACRoute)
def search_autocomplete_view(model, morepath_request):
    variables = model.template_vars(morepath_request.environ)
    return variables


@App.view(model=PackageRedirectRoute)
def package_redirect_view(model, morepath_request):
    routing_vars = {
        'language_bundle': model.language_bundle.identifier,
        'category': model.category.identifier,
        'book': model.book,
    }

    target_class = BookRoute

    if model.page:
        # route to a book page if there's a page ID
        routing_vars['page'] = model.page
        routing_vars['absorb'] = ''
        target_class = BookPageRoute

    link = morepath_request.class_link(target_class, variables=routing_vars)
    return morepath.redirect(link)


@App.html(model=webob.exc.HTTPNotFound)
def not_found_view(error, request):
    @request.after
    def _set_status_code(response):
        response.status_code = error.code

    template = util.load_template('not_found.html')
    path_parts = morepath.traject.parse_path(request.path)

    store = models.Store.instance()
    if not store:
        raise webob.exc.HTTPInternalServerError('Store could not be loaded')

    # sometimes we are behind a revproxy, sometimes we aren't
    bundle_pos = 0 if store.base_uri == '/' else 1

    # does the bundle part of the path tell us which bundle to display this 404 in?
    if path_parts and store.language_bundles.get(path_parts[bundle_pos]):
        language_bundle = store.language_bundles[path_parts[bundle_pos]]
    else:
        language_bundle = store.default_language_bundle

    parent_routes = None

    # cut up the path and attach helpful information to its parts
    if hasattr(error, 'parent_routes') and len(error.parent_routes) > 1:
        parent_routes = []
        for i in range(bundle_pos + 1, len(error.parent_routes)):
            current_parts = path_parts[: i + 1]
            path = morepath.traject.create_path(segments=current_parts)
            try:
                instance = request.resolve_path(path)
            except webob.exc.HTTPNotFound:
                instance = None

            if instance and instance.is_directory:
                path += '/'

            # consume any remaining tail of the path behind BookPageRoute
            if i + 1 == len(error.parent_routes):
                path_segment = ' / '.join(path_parts[i:])
            else:
                path_segment = current_parts[-1]

            word_splits = {
                x.strip()
                for x in re.split(r'[-_/]', path_segment)
                if len(x.strip()) > 2
            }

            parent_routes.append(
                {
                    'href': path,
                    'instance': instance,
                    'path_segment': path_segment,
                    'word_splits': ' '.join(sorted(word_splits)),
                }
            )

    return template.render(
        error=error,
        router=request,
        base_uri=store.base_uri,
        year=date.today().year,
        language_bundle=language_bundle,
        parent_routes=parent_routes,
        sibling_bundles=store.get_sibling_bundles(language=language_bundle.language),
        sibling_languages=store.get_sibling_languages(bundle=language_bundle.bundle),
    )


@App.view(model=StaticRoute)
def static_view(model, request):
    return request.get_response(webob.static.FileApp(model.path))


@App.view(model=StartRoute)
def start_view(model, morepath_request):
    store = models.Store.instance()
    client_language = util.get_client_lang(
        environ=morepath_request.environ,
        supported_languages=[x.identifier for x in store.get_all_languages()],
    )

    variables = {'language_bundle': store.default_language_bundle.identifier}

    if client_language:
        for language_bundle in store.language_bundles.values():
            if client_language == language_bundle.language.identifier:
                variables['language_bundle'] = language_bundle.identifier
                break

    url = morepath_request.class_link(LanguageBundleRoute, variables=variables) + '/'
    return morepath.redirect(location=url)
