#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
import argparse
from cs.metrics import qualitycharacteristics
from cdb.objects.util import paginated, iterate


def _prepare_identifier(args, func):
    if not args.module_ids and not args.codes:
        args.subparser.print_help()
    else:
        if args.module_ids:
            for m_id in args.module_ids:
                func(cdb_module_id=m_id)
        if args.codes:
            for code in args.codes:
                func(identifier=code)


def _create_missing_qcs(**kwargs):
    args = dict(status=qualitycharacteristics.QCDefinition.VALID.status)
    args.update(kwargs)
    qcdefs = qualitycharacteristics.QCDefinition\
        .KeywordQuery(**args)
    for qcdef in qcdefs:
        print("processing: '%s'" % qcdef.GetDescription())
        for asso in qcdef.Associations:
            asso.createQCs()


def create_missing_qcs(args):
    _prepare_identifier(args, _create_missing_qcs)


def _activate_qcds(**kwargs):
    args = dict(status=qualitycharacteristics.QCDefinition.CREATED.status)
    args.update(kwargs)
    qcdefs = qualitycharacteristics.QCDefinition\
            .KeywordQuery(**args)
    for qcdef in qcdefs:
        print("processing: '%s'" % qcdef.GetDescription())
        try:
            qcdef.ChangeState(qualitycharacteristics.QCDefinition.VALID.status)
        except RuntimeError:
            pass


def activate_qcds(args):
    _prepare_identifier(args, _activate_qcds)


def adjust_qgrade_for_qcs(args):
    _prepare_identifier(args, _adjust_qgrade_for_qcs)


def _adjust_qgrade_for_qcs(**kwargs):
    # computed kpi's will be automatically updated on next calculation
    kwargs.setdefault('computed', 0)
    qcdefs = qualitycharacteristics.QCDefinition.KeywordQuery(**kwargs)
    for qcdef in qcdefs:
        print("processing: '%s'" % qcdef.GetDescription())
        # iterates in chunks of 200 qcs
        for qc in iterate(qcdef.QualityCharacteristics):
            # workaround for selecting the latest history element for all dbms
            for page in paginated(qc.Historie,
                                  pagesize=1,
                                  order_by="%s DESC" % qualitycharacteristics.History.cdb_cdate.to_string()):
                for hist in page:
                    qc.Update(cdbqc_qgrade_object_id=hist.cdbqc_qgrade_object_id)
                    break
                break


parser = argparse.ArgumentParser(description='Tool to manage quality characteristics')
action_parsers = parser.add_subparsers(title='action',
                                       description='supported actions')
activate = action_parsers.add_parser('activate',
                                     help='Activate Quality Characteristic Definitions',
                                     description='Activate Quality Characteristic Definitions')
activate.set_defaults(func=activate_qcds,
                      subparser=activate)
create_missing = action_parsers.add_parser('create-missing',
                                           help="Create Quality Characteristics for given active Definitions",
                                           description="Create Quality Characteristics for given active Definitions")
create_missing.set_defaults(func=create_missing_qcs,
                            subparser=create_missing)
adjust_qgrades = action_parsers.add_parser('update-qgrade',
                                           help='Adjust Quality Grade Values of Quality Characteristics',
                                           description="""Adjusts the Quality Characteristic Quality Grade value to the last from history.
                                           Computed Quality Characteristics won't be processed as they will be automatically updated on next computation""")
adjust_qgrades.set_defaults(func=adjust_qgrade_for_qcs,
                            subparser=adjust_qgrades)
for p in [activate, adjust_qgrades, create_missing]:
    group = p.add_argument_group(title='Selections',
                                 description="Select Quality Characteristic Definitions"
                                 " - If more than one option is used they will be combined not intersected")
    group.add_argument('--identify-by-module-ids', '-im', dest='module_ids',
                       nargs='*', metavar='N',
                       help="Quality Characteristic Definitions identified by Module IDs")
    group.add_argument('--identify-by-codes', '-ic', dest='codes', nargs='*',
                       metavar='N',
                       help="Quality Characteristic Definitions identified by Codes")
args = parser.parse_args()
args.func(args)
