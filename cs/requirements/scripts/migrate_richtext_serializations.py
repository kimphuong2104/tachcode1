# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function, unicode_literals

import argparse
import logging
import sys

import colorama

from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.richtext import RichTextModifications
from cs.requirements.rqm_utils import RQMHierarchicals
from cdb import transactions

LOG = logging.getLogger(__name__)


def migrate_richtexts(spec_ids, verbose, fix=False, serialization_method=None):
    if spec_ids:
        specs = RQMSpecification.KeywordQuery(spec_id=spec_ids.split(','))
    else:
        specs = RQMSpecification.Query()
    total_count = 0
    for s in specs:
        with transactions.Transaction():
            spec_errors = 0

            if verbose:
                LOG.info('Processing %s', s.spec_id)
            tree_down_context = RQMHierarchicals.get_tree_down_context(specification=s)
            long_text_cache = tree_down_context.get('long_text_cache')
            req_text_cache = long_text_cache.get(RQMSpecObject.__classname__)
            tv_text_cache = long_text_cache.get(TargetValue.__classname__)
            for r in tree_down_context.get('spec_object_cache').values():
                richtext_attribute_values = RichTextModifications.get_richtext_attribute_values(
                    obj=r, long_text_cache=req_text_cache
                )
                patched_richtext_attribute_values = RichTextModifications.force_serializations(
                    attribute_values=richtext_attribute_values, serialization_method=serialization_method
                )
                for attr_key, attr_val in richtext_attribute_values.items():
                    patched_val = patched_richtext_attribute_values.get(attr_key)
                    if patched_val != attr_val:
                        if fix:
                            r.SetText(attr_key, patched_val)
                        spec_errors += 1
            for tvs in tree_down_context.get('target_value_cache').values():
                for t in tvs:
                    richtext_attribute_values = RichTextModifications.get_richtext_attribute_values(
                        obj=t, long_text_cache=tv_text_cache
                    )
                    patched_richtext_attribute_values = RichTextModifications.force_serializations(
                        attribute_values=richtext_attribute_values, serialization_method=serialization_method
                    )
                    for attr_key, attr_val in richtext_attribute_values.items():
                        patched_val = patched_richtext_attribute_values.get(attr_key)
                        if patched_val != attr_val:
                            if fix:
                                t.SetText(attr_key, patched_val)
                            spec_errors += 1
        if verbose:
            LOG.info('%s : found %s richtexts with different serialization.', s.GetDescription(), spec_errors)

        total_count += spec_errors
    LOG.info('Found %s richtexts with different serialization in total.', total_count)
    return total_count


def main():
    handler = logging.StreamHandler(stream=sys.stdout)
    x = logging.getLogger(__name__)
    x.addHandler(handler)
    x.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(
        description='Simple Helper Tool to find/migrate invalid richtext serialization within requirements and acceptance criterions which are reachable from a specification'
    )
    parser.add_argument(
        '--specifications',
        '-specs',
        dest='spec_ids',
        help='Search/ only within the specifications given by its comma separated IDs e.g. S000000000,S000000001')
    parser.add_argument(
        '--verbose',
        '-v',
        dest='verbose', action="store_true")
    parser.add_argument(
        '--fix',
        dest='fix',
        action="store_true",
        help='Fix richtext serializations in database, make a database backup before!'
    )
    parser.add_argument(
        '--serialization-method',
        dest="serialization_method",
        default=None
    )

    args = parser.parse_args()
    success = migrate_richtexts(
        spec_ids=args.spec_ids,
        verbose=args.verbose,
        fix=args.fix,
        serialization_method=args.serialization_method
    ) == 0
    if success:
        print('RichText Serialization Validness: ' + colorama.Fore.GREEN + 'PASSED' + colorama.Style.RESET_ALL)
        return True
    else:
        print('RichText Serialization Validness: ' + colorama.Fore.RED + 'FAILED' + colorama.Style.RESET_ALL)
        return False


if __name__ == '__main__':
    colorama.init()
    main()
