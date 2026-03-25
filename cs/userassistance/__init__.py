# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
TODO: docstring
"""
import argparse
import logging
import os
import shutil
import sys
import threading

import pkg_resources
import setuptools
from cdb import rte
from cdb.plattools import killableprocess

COMMAND_REGISTRY = {}
REMOVE_FAILURES = 0


_logger = logging.getLogger(__name__)


def subcommand(*cmd_args):
    """@subcommand() is a decorator that registers the given function
    together with the arguments to subcommand in the global variable
    `COMMAND_REGISTRY`. In `main` this registry is used to add
    sub-commands."""

    def _wrapper(func):
        """Register `func` and return (the unwrapped!) function."""
        COMMAND_REGISTRY[func.__name__] = func, cmd_args
        return func

    return _wrapper


def arg(*args, **kwargs):
    """
    `arg` is used to collect arguments for `argparse:add_argument`
    and adding those to a `@subcommand`
    """

    def _add_arg(parser):
        return parser.add_argument(*args, **kwargs)

    return _add_arg


def die(msg: str, status_code=None):
    _logger.error(msg)

    if threading.current_thread() is threading.main_thread():
        sys.exit(status_code or -1)
    else:
        # Calling sys.exit() in a multiprocessing thread results in hanging processes
        raise RuntimeError(msg)


def rmdir(args, dirs):
    # TODO: why not just some shutil.rmtree?
    def _log_cannot_remove(function, path, excinfo):
        global REMOVE_FAILURES
        REMOVE_FAILURES += 1
        _logger.error('Failed to remove: %s', path)

    # FIXME: what in the name of our lord saviour is this type comparison?
    if type(dirs) is not list:
        die('internal error')

    if dirs:
        dirs = [d if os.path.isabs(d) else os.path.join(args.prefix, d) for d in dirs]
        _logger.debug('rm -rf %s', killableprocess.list2cmdline(dirs))
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=False, onerror=_log_cannot_remove)


def shell(args, cmd, expected_rc=None, **kwargs):
    output = None
    # noinspection PyBroadException
    try:
        _logger.debug(killableprocess.list2cmdline(cmd))
        if args.quiet:
            output = killableprocess.check_output(cmd, **kwargs)
        else:
            killableprocess.check_call(cmd, **kwargs)
    except killableprocess.CalledProcessError as exception:
        if expected_rc is not None and exception.returncode == expected_rc:
            return
        msg = f'"{cmd}" failed: {sys.exc_info()[1]}: '
        if output is not None:
            msg += f'\noutput:\n{output}'
        die(msg)
    except Exception:
        msg = f'"{cmd}" failed: {sys.exc_info()[1]}: '
        if output is not None:
            msg += f'\noutput:\n{output}'
        die(msg)


def cs_cmd(args, cmd, *cmdargs, **kwargs):
    commands = [cmd]
    instancedir = (
        args.instancedir if args.instancedir else os.environ.get('CADDOK_BASE')
    )
    if instancedir is not None:
        commands.extend(['--instancedir', instancedir])
    commands.extend(list(cmdargs))
    return shell(args, commands, **kwargs)


def platform_cmd(cmd: str):
    bin_cmd = os.path.join(os.path.dirname(sys.executable), cmd)
    if os.path.exists(bin_cmd):
        return bin_cmd
    if sys.platform == 'win32' and os.path.exists(bin_cmd + '.exe'):
        return bin_cmd + '.exe'

    script_cmd = os.path.join(os.path.dirname(sys.executable), 'Scripts', cmd)
    return script_cmd


def read_setup(script: str, output: dict, may_skip=False):
    """
    Loads a setup.py file into a dictionary by monkey patching setuptools functionality.
    """
    orig_setup = setuptools.setup
    try:
        setuptools.setup = lambda **args: output.update(**args)
        if os.path.exists(script):
            with open(script, 'r', encoding='utf_8_sig') as f:
                c = compile(f.read().encode('utf-8'), script, 'exec')
                exec(c, globals(), locals())
        elif not may_skip:
            die(f'cannot read {os.path.abspath(script)}')
    finally:
        setuptools.setup = orig_setup


def sanity_check(args):
    return True


def main():
    """Main call of cs.userassistance's CLI"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-i', '--instancedir', default=None, help='instance directory (e.g. "sqlite")'
    )
    parser.add_argument(
        '-p', '--prefix', default='.', help='package location [default: .]'
    )
    parser.add_argument(
        '-s',
        '--setup',
        default='setup.py',
        help='name of the setup script [default: setup.py]',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true', dest='verbose', help='verbose output'
    )
    parser.add_argument(
        '-q', '--quiet', action='store_true', dest='quiet', help='suppress output'
    )
    parser.add_argument(
        '-C', '--directory', default='', help='Change to this directory'
    )
    subparsers = parser.add_subparsers()

    logging.basicConfig(
        format='userassistance: [%(levelname)-8s] [%(name)s] %(message)s',
        stream=sys.stderr,
        level=logging.INFO,
    )

    # FIXME: There must be a better way
    caddok_dirs = rte.caddok_default_dirs()
    rte.environ['CADDOK_INSTALLDIR'] = caddok_dirs['INSTALLDIR']
    rte.environ['CADDOK_HOME'] = caddok_dirs['HOME']

    # see cdb/python/setup.py for loading subcommands!
    # TODO: investigate whether there is a better way
    # TODO: removing not possible as it is doing something crucial apparently
    for entrypoint in pkg_resources.iter_entry_points('cs.userassistance'):
        entrypoint.load()

    # add subcommands
    for name, (func, cmd_args) in sorted(COMMAND_REGISTRY.items()):
        sub_parser = subparsers.add_parser(name, help=func.__doc__)
        for arg_maker in cmd_args:
            arg_maker(sub_parser)
        sub_parser.set_defaults(func=func)

    args, extra = parser.parse_known_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        die('Too few arguments')

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # create console handler
    if sanity_check(args):
        setup_path = os.path.join(args.prefix, args.setup)
        if hasattr(args.func, 'create_setup_dir') and not os.path.exists(args.prefix):
            _logger.info('Creating %s', args.prefix)
            os.makedirs(args.prefix)
        setup_dict = {}

        if not os.path.abspath(args.directory) == os.path.abspath(os.getcwd()):
            os.chdir(os.path.abspath(args.directory))
        read_setup(
            script=setup_path,
            output=setup_dict,
            may_skip=hasattr(args.func, 'create_setup_dir'),
        )
        return args.func(args, extra, setup_dict)
