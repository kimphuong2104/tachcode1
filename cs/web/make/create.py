#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import absolute_import, print_function
from __future__ import absolute_import
import datetime
import getpass
import io
import logging
import os
import six

import importlib

from cdb.comparch import pkgtools
from cs.web.make.util import MakeException, jsonread
from cs.web.make.packages import PackageAction


_LOGGER = logging.getLogger(__name__)


def task_add_import(module='main'):
    def _run_add_import(args):
        if os.path.exists(args.package.dir('%s.py' % module.replace('.', os.sep))):
            import_line = 'import %s' % args.package.py_name if module == "__init__" \
                else u'import %s.%s\n' % (args.package.py_name, module)

            # Read default.conf and check if import is already added
            line_set = set()
            last_line = ''
            default_conf = os.path.join(args.package.module.module_dir, 'default.conf')
            if os.path.exists(default_conf):
                with io.open(default_conf, 'r', encoding='utf-8') as fstream:
                    for line in fstream:
                        line_set.add(line)
                        last_line = line

            if import_line not in line_set:
                with io.open(default_conf, 'a', encoding='utf-8') as fstream:
                    if not last_line.endswith('\n'):
                        fstream.write(u'\n')
                    fstream.write(import_line)
    return _run_add_import


def _customize_default(args, template):
    repl = {u'WEB_BASE_DIR': pkgtools.path_join('cs.web'),
            u'NOW_YEAR': six.text_type(datetime.datetime.utcnow().year),
            u'NOW_MONTH': six.text_type(datetime.datetime.utcnow().month),
            u'NOW_DAY': six.text_type(datetime.datetime.utcnow().day),
            u'USER': getpass.getuser()}

    if hasattr(args, 'package'):
        repl.update({u'PACKAGE_JS': args.package.js_name,
                     u'PACKAGE_PY': args.package.py_name,
                     u'NAME_LC': args.package.module_tokens[-1].lower(),
                     u'NAME_UC':
                         args.package.module_tokens[-1][0].upper() +
                         args.package.module_tokens[-1][1:].lower()})

    return template % repl


def _run_tasks(args, template_root):
    conf_path = str(template_root) + '.json'
    if os.path.exists(conf_path):
        conf = jsonread(conf_path)
        for task in conf['tasks']:
            params = task.get('param', {})
            _LOGGER.info('Running task %s with args %s',
                         task['fqpn'], params)
            mod_name, fn_name = _process_fqpn(task['fqpn'])
            task_fn = getattr(importlib.import_module(mod_name), fn_name)
            task_fn(**params)(args)


def _copy_template(args, template_dir, package_dir, fname, include_header=True):
    _LOGGER.info('  creating %s\n      from %s',
                 os.path.join(package_dir, fname),
                 os.path.join(template_dir, '%s.template' % fname))
    if args.dry_run:
        return

    package_path = os.path.join(package_dir, fname)
    with io.open(package_path, 'w', encoding='utf-8') as package_file:
        # Insert header if namespace is cs and header for filetype
        # exists
        # TODO custom headers in packages?
        if include_header:
            header_path = pkgtools.path_join('cs.web', 'templates', 'headers',
                                             ('%s.header' % os.path.splitext(fname)[1][1:]))
            if os.path.exists(header_path):
                with io.open(header_path, 'r', encoding="utf-8") as header_file:
                    package_file.write(_customize_default(args, header_file.read()))
                    package_file.write(u'\n')

        # Write template
        with io.open(os.path.join(template_dir, '%s.template' % fname), 'r', encoding='utf-8') as template_file:
            package_file.write(_customize_default(args, template_file.read()))


def _get_existing_template_files(args, template_roots):
    existing_files = []

    for template_root in template_roots:
        for root, _, files in os.walk(template_root):
            relative_dir = os.path.relpath(root, template_root)
            package_dir = args.package.dir(relative_dir)

            if not package_dir or not os.path.exists(package_dir):
                continue

            for fname in [f for f in files if f.endswith('.template')]:
                real_name = fname[:-9]  # Remove .template suffix
                real_path = os.path.join(package_dir, real_name)
                if os.path.exists(real_path):
                    existing_files.append(real_path)

    return existing_files


def _copy_templates(args, template_root):
    for root, _, files in os.walk(template_root):
        relative_dir = os.path.relpath(root, template_root)
        template_dir = os.path.join(template_root, relative_dir)
        package_dir = args.package.dir(relative_dir)

        if relative_dir != '.':
            _LOGGER.info('mkdir %s', package_dir)
            if not args.dry_run and not os.path.exists(package_dir):
                os.mkdir(package_dir)

        for fname in [f for f in files if f.endswith('.template')]:
            # Insert header if namespace is cs and header for filetype
            # exists
            _copy_template(args, template_dir, package_dir, fname[:-9],
                           include_header=(args.package.namespace == 'cs'))


def _process_fqpn(fqpn):
    tokens = fqpn.split('.')
    return '.'.join(tokens[:-1]), tokens[-1]


def _cmd_create_app(args):
    args.package.check()

    # Generate template roots (folders under <cdb_package>/templates/app)
    # Templates for application files may be overridden by specifying
    # [ <cdb_package> ]:template_name
    # Default cdb_package is cs.web (if no package is provided)
    def _generate_template_path(template_name):
        template_name_splitted = (['cs.web', template_name]
                                  if template_name.find(':') == -1
                                  else template_name.split(':', 1))
        template_path = importlib.resources.files(template_name_splitted[0]) \
            / 'resources' / 'templates' / 'app' / template_name_splitted[1]
        if not os.path.exists(template_path):
            raise MakeException('Template %s resolving to path %s does not exist'
                                % (template_name, template_path))
        return template_path
    template_roots = [_generate_template_path(template_name)
                      for template_name in args.templates]

    # Check if all required template_roots are valid
    for template_root in template_roots:
        if not os.path.isdir(template_root):
            raise MakeException('Requested template root %s does not exist' % template_root)

    app_path = None
    apps_list = args.package.apps
    js_dir = args.package.dir('js')
    # args.package.dir('js') usually is None when the App doesn't exist yet.
    # In that case resolving 'app_path' is only possible after calling
    # '_run_tasks' below
    if js_dir:
        app_path = os.path.relpath(js_dir, args.package.base_dir).replace('\\', '/')
        if app_path in apps_list:
            raise MakeException('A package already exists in %s.' % js_dir)

    # check if existing files would be overwritten
    existing_files = _get_existing_template_files(args, template_roots)
    if existing_files:
        _LOGGER.error('The following files would be overwritten by this action:')
        for f in existing_files:
            _LOGGER.error('\t%s', f)
        raise MakeException('Can not create app if existing files would be overwritten.')

    # Create Bundle
    if not args.package.is_created:
        args.package.create(dry_run=args.dry_run)

    for template_root in template_roots:
        _copy_templates(args, template_root)
        _run_tasks(args, template_root)

    # add the app to the bundle
    if not app_path:
        app_path = os.path.relpath(
            args.package.dir('js'),
            args.package.base_dir,
        ).replace('\\', '/')
    print(
        "IMPORTANT: Please add '%s' to the list of apps in setup.py / setup.cfg "
        "and re-generate the egg-info data." % app_path,
    )


def add_parameters(subparsers):
    parser_create = subparsers.add_parser('create', help='create an app skeleton')
    parser_create.add_argument('package',
                               action=PackageAction,
                               help='a python package identifying and containing the app')
    parser_create.add_argument('--templates',
                               default=['base_impl'],
                               dest='templates',
                               metavar='TEMPLATE',
                               nargs='+',
                               help='list of templates to install. '
                                    'templates may specify cdb package from which template is taken.')
    parser_create.set_defaults(func=_cmd_create_app)
