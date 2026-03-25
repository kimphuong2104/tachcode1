# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module lmain

Commandline Runner for the licensereport

Usage Example:
    cdblic --start 10.10.2017 --end 10.10.2018 --out report.xsls

"""

import argparse
import datetime
import logging
import sys

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = ['main']


def parse_date(strval):
    """Parse a date string into a datetime object"""
    fmt = "%d.%m.%Y"
    return datetime.datetime.strptime(strval, fmt)


def setup_options(parser):
    """Setup commandline options"""
    parser.add_argument("--start", type=parse_date,
                        help="Start date in format DD.MM.YYYY")
    parser.add_argument("--end", type=parse_date,
                        help="End date in format DD.MM.YYYY")
    parser.add_argument("--out",
                        help="Filename of the reportfile.")
    parser.add_argument("--job", type=argparse.FileType(mode='rb'),
                        help="Job description file as json.")
    parser.add_argument(
        "--loglevel",
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help="Logging verbosity")
    parser.add_argument(
        "--customer",
        help="Customer name to use in report.")
    parser.add_argument(
        "--unmasked",
        help="Disable anonymization of the report.",
        dest='unmasked',
        action='store_true'
    )
    parser.add_argument(
        "--step",
        help="Select which steps to run. Can be 'extract', 'report', 'all'.",
        choices=['extract', 'report', 'all'])

    parser.add_argument(
        "--no-reset-log",
        dest='resetlog',
        action='store_false',
        help=argparse.SUPPRESS)

    parser.add_argument(
        "--reindex",
        dest='reindex',
        action='store_true',
        help="Recreate the necessary indices on lstatistics.")
    return parser


def run_report(options):
    """Create a license report with the given options"""
    from cs.licreport import errors
    from cs.licreport.utils import format_timestamp

    params = {
        'version': '',
        'tables': {
            'lstatistics': 'lstatistics',
            'cdbfls_license_site': 'cdbfls_license_site',
            'angestellter': 'angestellter'
        },
        'start_time': '',
        'end_time': '',
        'customer': 'Generic',
        'loglevel': 'INFO',
        'reportfile': 'LicReport.xlsx',
        'pseudonymize': '1',
        'step': 'all'
    }

    if options.job:
        import json
        params_extra = json.load(options.job)

        # Merge the data
        if 'tables' in params_extra:
            params['tables'].update(params_extra['tables'])
            del params_extra['tables']
        if 'mode' in params_extra:
            del params_extra['mode']

        params.update(params_extra)

    if options.loglevel:
        params['loglevel'] = options.loglevel

    if options.customer:
        params['customer'] = options.customer

    if options.unmasked:
        params['pseudonymize'] = '0'

    if options.start:
        params['start_time'] = format_timestamp(options.start)
    if options.end:
        # Make it inclusive, e.g. add 23:59:59 to it.
        ts = options.end + datetime.timedelta(seconds=86399)
        params['end_time'] = format_timestamp(ts)

    lvl = getattr(logging, params['loglevel'].upper())
    if options.resetlog:
        # Reset root logger for 15.x, so this goes to stdout instead of
        # powerscript Logfile
        logging.root.handlers = []
        logging.basicConfig(level=lvl,
                            format='%(asctime)s %(message)s',
                            datefmt='%H:%M:%S')

    log = logging.getLogger(__name__)

    if options.reindex:
        from cs.licreport.utils import reindex
        reindex()

    versionstr = params['version']
    if versionstr:
        assert '.' in versionstr
        assert versionstr.startswith('1') or versionstr.startswith('9')

    TABLES = params['tables']
    log.debug("Checking table configuration")
    for tk in ('lstatistics', 'cdbfls_license_site', 'angestellter'):
        val = TABLES.get(tk)
        if val is None:
            raise errors.InvalidTablesError("No table given for key '%s'", tk)

        from cdb.util import tables as ti
        if val not in ti:
            raise errors.InvalidTablesError("Table does not exist '%s'", val)

    if options.out:
        params['reportfile'] = options.out

    if options.step:
        do_extract = options.step in ('all', 'extract')
        do_report = options.step in ('all', 'report')
    else:
        if params['step'] not in ('all', 'extract', 'report'):
            do_extract = True
            do_report = True
        else:
            do_extract = params['step'] in ('all', 'extract')
            do_report = params['step'] in ('all', 'report')

    from cs.licreport.lreport import generate_report
    generate_report(
        versionstr=versionstr,
        customer=params['customer'],
        mode='session',
        start_time=params['start_time'],
        end_time=params['end_time'],
        tables=TABLES,
        reportfile=params.get('reportfile'),
        pseudonymize=bool(int(params.get('pseudonymize', '1'))),
        do_extract=do_extract,
        do_report=do_report
    )
    return 0


def main(args=None):
    """
    console script entry point for the licreport
    """
    from cdb import rte
    from cs.licreport import errors
    parser = rte.make_argument_parser()
    setup_options(parser)
    if args is None:
        args = sys.argv[1:]
    options = parser.parse_args(args)
    try:
        with rte.Runtime(options=options, prog='Licreport'):
            return run_report(options)
    except errors.NoDataError as exc:
        logging.getLogger(__name__).error(
            "Table '%s' contained no data. No report generated.",
            exc.table)
        return 3
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Aborted by User.")
        return 1
    except Exception:
        raise
        logging.getLogger(__name__).exception("Exception from run_report.")
        return 99


# Guard importing as main module
if __name__ == "__main__":
    sys.exit(main())
