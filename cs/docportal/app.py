# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Serves the documentation portal
"""

import argparse
import logging
from http import client
from multiprocessing import cpu_count
from os import environ
from typing import Callable

import waitress
from pkg_resources import get_distribution

from cs.docportal import DocPortalError, routes, util
from cs.docportal.models import Store

# pylint: disable=W0703

__all__ = ['main']

_logger = util.get_logger(__name__)


def error_response(start_response: Callable, http_code: int, msg=b'', header=None):
    if header is None:
        header = []
    status = f'{http_code} {client.responses[http_code]}'
    start_response(status, header)
    return [msg]


def application(env: dict, start_response: Callable):
    """Serves the documentation portal application."""
    try:
        # morepath strips trailing slashes, so we preserve the original path info
        # to decide whether we have to redirect
        env['PATH_INFO_RAW'] = env['PATH_INFO']
        app = routes.App()
        app.guarded_commit()
        return app(env, start_response)
    except Exception as exc:
        _logger.critical('Application Error: %s (%s)', exc, env.get('wsgi.errors'))
        return error_response(
            start_response=start_response,
            http_code=client.INTERNAL_SERVER_ERROR,
            msg=b'Unhandled Exception occurred',
        )


def main(args):
    # warn for accidental base URI override
    if args.revproxy is not None:
        if 'DOCPORTAL_BASEURI' in environ:
            _logger.warning('overwriting "DOCPORTAL_BASEURI" with %s', args.revproxy)
        environ['DOCPORTAL_BASEURI'] = args.revproxy

    _instance = Store.instance()
    if not _instance:
        raise DocPortalError('Could not instantiate Store')

    if 'DOCPORTAL_CPU_CORES' in environ:
        cpu_cores = int(environ['DOCPORTAL_CPU_CORES'])
    else:
        cpu_cores = cpu_count()
    _logger.debug('Running docportal on %s threads', cpu_cores)

    waitress.serve(
        app=application,
        port=args.port,
        _quiet=bool(environ.get('CADDOK_HOME')),
        threads=cpu_cores,
        url_prefix=environ.get('DOCPORTAL_BASEURI', ''),
    )
    logging.getLogger('waitress').setLevel(logging.DEBUG)


if __name__ == '__main__':
    version = get_distribution('cs.docportal').version

    parser = argparse.ArgumentParser(description=f'Documentation Portal v{version}')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='runs the program in verbose mode',
    )
    parser.add_argument(
        '-q',
        '--quiet',
        action='store_true',
        help='runs the program in quiet mode (this is overridden by verbose mode)',
    )
    parser.add_argument(
        '-p',
        '--port',
        default=8080,
        help='the port to be used (default=8080)',
        type=int,
    )
    parser.add_argument(
        '-r', '--revproxy', default=None, help='path prefix for a rev-proxy'
    )

    main(parser.parse_args())
