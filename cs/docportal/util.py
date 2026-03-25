# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import hashlib
import logging
import os
from contextlib import contextmanager
from http import cookies
from pathlib import Path

import jinja2


def get_logger(name):
    """
    Get a logger for a given module name. The logger will log to terminal in
    Standalone mode and to a .log file in CDB mode.
    :param name: a full module name (e.g. foo.bar.baz_module)
    :return: a ``logging.Logger``
    """
    logger = logging.getLogger(name.split('.')[-1])
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt='[%(asctime)s.%(msecs)02d %(levelname)s %(name)s:%(lineno)s] %(message)s',
        datefmt='%H:%M:%S',
    )

    # log to file if we're in a CDB environment
    if os.environ.get('CADDOK_TMPDIR'):
        docportal_temp_dir = Path(os.environ['CADDOK_TMPDIR']) / 'docportal'
        docportal_temp_dir.mkdir(exist_ok=True)
        handler = logging.FileHandler(
            filename=docportal_temp_dir / 'docportal.log',
            mode='a',
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# pylint: disable=broad-except
@contextmanager
def locked_with_logger(lock, logger):
    lock.acquire()
    try:
        yield
    except Exception:
        logger.exception('Exception occurred, releasing lock')
    finally:
        lock.release()


def module_root_dir() -> Path:
    """The directory where DocPortal's core code base resides (.../cs/docportal/)."""
    return Path(__file__).parent


def project_root_dir() -> Path:
    """The directory at the top level of this package (.../)."""
    return module_root_dir().parent.parent


def string_hash(string: str) -> str:
    """
    Get a MD5 hash for a given string.
    :param string: any str
    :return: a 32 character long hash representation for the given str
    """
    return hashlib.md5(bytes(string, encoding='utf-8')).hexdigest()


_file_loader = jinja2.FileSystemLoader(module_root_dir() / 'html')
_jinja_env = jinja2.Environment(
    loader=_file_loader,
    lstrip_blocks=True,
    trim_blocks=True,
    autoescape=True,
)


def load_template(name: str) -> jinja2.Template:
    """Load a jinja2 template from the /html dir"""
    return _jinja_env.get_template(name)


def get_client_lang(environ, supported_languages):
    """
    Priorities:
    1. contact.language: Cookie
    2. CADDOK_ISOLANG: key in WSGI dictionary
    3. HTTP_ACCEPT_LANGUAGE: key in WSGI dictionary
    4. default language: fallback defined in docportal config
    :param environ: the WSGI environment for the request
    :param supported_languages: the available languages
    :return: 2 character language ID
    """

    if 'HTTP_COOKIE' in environ:
        _cookies = cookies.SimpleCookie(environ['HTTP_COOKIE'])
        contact_lang = _cookies.get('contact.language')
        if contact_lang and contact_lang.value in supported_languages:
            return contact_lang.value

    caddok_lang = environ.get('CADDOK_ISOLANG')
    if caddok_lang and caddok_lang in supported_languages:
        return caddok_lang

    if 'HTTP_ACCEPT_LANGUAGE' in environ:
        browser_languages = accept_languages(environ['HTTP_ACCEPT_LANGUAGE'])
        for browser_language in browser_languages:
            if browser_language and browser_language in supported_languages:
                return browser_language

    return None


def accept_languages(lang_string):
    """
    This takes an HTTP_ACCEPT_LANGUAGE header string, and returns a list of locales.
    Locales will be sorted in descending order without checking for the q-factor,
    because they should be delivered in order anyway, and we don't really care
    about the size of the difference.
    Invalid input will be handled and result in an empty list.
    :return: a descending list of 2 character language codes
    """
    locales = []

    try:
        languages = lang_string.split(',')
    except AttributeError:
        return locales

    for language in languages:
        # ignore the q-factor if present
        if ';' in language:
            language = language.split(';')[0]

        # reduce to 2 character language code
        locales.append(language.strip()[:2])

    return locales
