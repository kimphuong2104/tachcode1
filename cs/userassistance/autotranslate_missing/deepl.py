# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import logging
import os

import requests
from cdb import CADDOK

from cs.userassistance.autotranslate_missing import helpers

_DEEPL_API_URL = 'https://api.deepl.com/v1'
_logger = logging.getLogger(__name__)


def _get_api_key():
    if os.environ.get('DEEPLAUTHKEY'):
        return os.environ['DEEPLAUTHKEY']
    with open(
        os.path.join(CADDOK.HOME, '..', 'devtools', 'deepl_api.key'), 'r'
    ) as keyfile:
        return keyfile.read().strip()


def _call_deepl_api(func, authkey, method='POST', **kwargs):
    """kwargs are any parameters the DeepL api (https://www.deepl.com/api.html)
    understands."""
    _logger.debug('Sending payload to DeepL: %s', kwargs)
    payload = {
        'auth_key': authkey if authkey else _get_api_key(),
    }
    payload.update(**kwargs)
    if method == 'POST':
        response = requests.post(f'{_DEEPL_API_URL}/{func}', data=payload)
    elif method == 'GET':
        response = requests.get(f'{_DEEPL_API_URL}/{func}', data=payload)
    else:
        raise RuntimeError(f'Unknown method {method}')
    response.raise_for_status()
    result = response.json()
    _logger.debug('Response from DeepL: %s', result)
    return result


def _translate(authkey, target_lang, source_lang, text):
    resp = _call_deepl_api(
        'translate',
        authkey,
        text=text,
        target_lang=target_lang,
        source_lang=source_lang,
    )
    return resp['translations'][0]['text']


def statistics(authkey):
    return _call_deepl_api('usage', authkey, 'GET')


def translate(target_language, msgid, input_language, authkey):
    msgstr = _translate(
        authkey, target_language, input_language, helpers.mask_rst(msgid)
    )
    return helpers.unmask_rst(msgstr) if msgstr else msgstr
