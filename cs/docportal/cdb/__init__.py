# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
The CDBService starting up and exposing the documentation portal
when running inside a CDB environment (e.g. platform)
"""

import os
from datetime import date
from pathlib import Path

from cdb.wsgi.messages import MessageCache

CADDOK_BASE: Path = Path(os.environ.get('CADDOK_BASE'))


def get_branding_labels(language_id):
    year = date.today().year
    branding_labels = {
        'branding_company_name': 'CONTACT Software',
        'branding_full_company_name': 'CONTACT Software GmbH',
        'branding_company_homepage': 'https://www.contact-software.com',
        'branding_doc_portal_title': 'Documentation Portal',
        'branding_product_name': 'CONTACT Elements',
        'branding_product_name_acronym': 'CE',
        'branding_copyright': f'Copyright &copy; 1990-{year} CONTACT Software',
        'branding_copyright_year': year,
    }

    for label in branding_labels:
        _label = MessageCache.get(label, language_id)
        if not _label.startswith('ConfigError'):
            branding_labels[label] = _label

    return branding_labels
