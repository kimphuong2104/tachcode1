# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals, print_function

import argparse
import logging
import sys

import colorama

from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements_reqif.exceptions import ReqIFValidationError
from cs.requirements_reqif.reqif_validator import ReqIFValidator

LOG = logging.getLogger(__name__)


def invalid_rqm_obj_attrs(validator, obj, attr_prefix, ignore_empty=True):
    errors = []
    for long_text_attr in obj.GetTextFieldNames():
        if long_text_attr.startswith(attr_prefix):
            content = obj.GetText(long_text_attr)
            if content or not ignore_empty:
                try:
                    validator.has_valid_xhtml_field_content(content)
                except ReqIFValidationError as e:
                    errors.append("{}:{}".format(long_text_attr, str(e)))
    return errors


def invalid_richtext_attrs(validator, req, ignore_empty):
    return invalid_rqm_obj_attrs(validator, req,
                                 RQMSpecObject.__description_attrname_format__.format(iso=''),
                                 ignore_empty)


def invalid_target_value_attrs(validator, tar, ignore_empty):
    return invalid_rqm_obj_attrs(validator, tar,
                                 TargetValue.__description_attrname_format__.format(iso=''),
                                 ignore_empty)


def find_invalid_elements(spec_ids, verbose, ignore_empty):
    validator = ReqIFValidator()
    if spec_ids:
        specs = RQMSpecification.KeywordQuery(spec_id=spec_ids.split(','))
    else:
        specs = RQMSpecification.Query()
    total_count = 0
    for s in specs:
        spec_errors = 0
        if verbose:
            LOG.info('Processing %s', s.spec_id)
        for r in s.Requirements.Query("1=1", order_by='specobject_id'):
            attrs = invalid_richtext_attrs(validator, r, ignore_empty)
            if attrs and verbose:
                LOG.info('    Found invalid: %s',
                         r.specobject_id)
                LOG.info('        Attribute(s): \n            %s', ",\n".join(attrs))
            spec_errors += len(attrs)
        for t in s.TargetValues.Query("1=1", order_by='targetvalue_id'):
            attrs = invalid_target_value_attrs(validator, t, ignore_empty)
            if attrs and verbose:
                LOG.info('    Found invalid: %s',
                         t.targetvalue_id)
                LOG.info('        Attribute(s): \n            %s', ",\n".join(attrs))
            spec_errors += len(attrs)
        if spec_errors and verbose:
            LOG.info('%s has %s invalid richtexts.', s.spec_id, spec_errors)
        total_count += spec_errors
    LOG.info('Found %s invalid richtexts in total.', total_count)
    return total_count


def main():
    handler = logging.StreamHandler(stream=sys.stdout)
    x = logging.getLogger(__name__)
    x.addHandler(handler)
    x.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(
        description='Simple Helper Tool to find invalid richtexts within requirements and acceptance criterions which are reachable from a specification'
    )
    parser.add_argument(
        '--specifications',
        '-specs',
        dest='spec_ids',
        help='Search only within the specifications given by its comma separated IDs e.g. S000000000,S000000001')
    parser.add_argument(
        '--verbose',
        '-v',
        dest='verbose', action="store_true")
    parser.add_argument(
        '--show-empty',
        dest='ignore_empty', action="store_false", default=True)
    args = parser.parse_args()
    success = find_invalid_elements(args.spec_ids, args.verbose, args.ignore_empty) == 0
    if args.ignore_empty:
        LOG.info('Ignoring empty values')
    if success:
        print('RichText Validness: ' + colorama.Fore.GREEN + 'PASSED' + colorama.Style.RESET_ALL)
        return True
    else:
        print('RichText Validness: ' + colorama.Fore.RED + 'FAILED' + colorama.Style.RESET_ALL)
        return False


if __name__ == '__main__':
    colorama.init()
    main()
