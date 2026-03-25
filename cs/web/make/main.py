""" A collection of CLI helpers and tools to automate and simplify the creation and
    maintenance of web applications for CONTACT Elements.
"""

import argparse
import logging
from cdb import rte
import subprocess
import sys

_LOGGER = logging.getLogger(__name__)

_DESCRIPTION = """webmake builds the web in cs.web
- This utility allows to create and build web bundles and their documentation
"""

def _setup_logging(args):
    """ Setup a root logger, used when running as a script, loglevel is determined
        from --verbose option switch
    """
    rootlogger = logging.getLogger()
    rootlogger.setLevel(logging.DEBUG if args.vverbose else logging.INFO if args.verbose else logging.WARNING)
    rootlogger.addHandler(logging.StreamHandler(sys.stderr))


def _make_argument_parser():
    """Argument parser, for running as a cmdline script"""
    from cs.web.make import build
    from cs.web.make import create
    from cs.web.make import run_tests
    from cs.web.make import styles

    argument_parser = argparse.ArgumentParser(description=_DESCRIPTION)
    argument_parser.add_argument('--vverbose',
                                 default=False,
                                 action='store_true',
                                 help='Print very verbose output.')
    argument_parser.add_argument('--dry-run',
                                 default=False,
                                 dest='dry_run',
                                 action='store_true',
                                 help='If set, do not modify filesystem/database')

    subparsers = argument_parser.add_subparsers(help='The action to be execute')
    create.add_parameters(subparsers)
    build.add_parameters(subparsers)
    styles.add_parameters(subparsers)
    run_tests.RunTests.add_parser(subparsers)

    return argument_parser


def main_internal(args=None, namespace=None):
    from cs.web.make import util
    try:
        make_options = _make_argument_parser().parse_args(
            args=args,
            namespace=namespace,
        )
        _setup_logging(make_options)
        make_options.func(make_options)
    except util.MakeException as exc:
        _LOGGER.error(exc)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        _LOGGER.error(exc)
        sys.exit(exc.returncode)


def main():
    """
    Main Entry point for wrapper script
    """
    params = {
        'description': _DESCRIPTION,
        'run_level': rte.INSTANCE_ATTACHED,
    }

    rte_options, make_args = rte.make_argument_parser(**params).parse_known_args()
    with rte.Runtime(rte_options):
        main_internal(make_args, rte_options)
