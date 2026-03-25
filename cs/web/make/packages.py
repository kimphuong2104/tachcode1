#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import argparse
import io
import os
import logging

from cs.web.make.util import MakeException


_LOGGER = logging.getLogger(__name__)


def need_init_deferred(fn):
    def _with_init_deferred(self, *args, **kwargs):
        if not self._initialized:
            self.init_deferred()
        return fn(self, *args, **kwargs)

    return _with_init_deferred


class PackageConfig(object):
    @classmethod
    def from_list(cls, files):
        return [cls(fname) for fname in files]

    def __init__(self, module_string):
        self._module_string = module_string
        self._initialized = False

    def init_deferred(self):
        from importlib import import_module

        mod_tokens = self._module_string.split('.')
        mod_tokens_existing = list(mod_tokens)
        mod_tokens_create = []

        self._created = True

        while mod_tokens_existing:
            try:
                base_module = import_module('.'.join(mod_tokens_existing))
                base_path = os.path.dirname(base_module.__file__)
                break
            except ImportError:
                mod_tokens_create.insert(0, mod_tokens_existing.pop())
                self._created = False
        else:
            raise MakeException('No module in which to create \'%s\''
                                % mod_tokens)

        self._module_tokens_create = mod_tokens_create
        self._module_tokens_existing = mod_tokens_existing
        self._module_tokens = mod_tokens
        self._base_path = base_path

        self._initialized = True

    @need_init_deferred
    def check(self):
        if not self.module:
            raise MakeException('%s is not a cdb module. A web package must '
                                'be created inside of a cdb module'
                                % self.py_name)

    @need_init_deferred
    def create(self, dry_run=False):
        for token in self._module_tokens_create:
            _LOGGER.info('Creating python package %s in %s',
                         token, self._base_path)

            self._base_path = os.path.join(self._base_path, token)
            if not dry_run:
                os.mkdir(self._base_path)
                open(os.path.join(self._base_path, '__init__.py'), 'w').close()

        self._created = True

    @property
    @need_init_deferred
    def js_name(self):
        return '-'.join(self._module_tokens)

    @property
    @need_init_deferred
    def py_name(self):
        return '.'.join(self._module_tokens)

    @property
    @need_init_deferred
    def module_tokens(self):
        return self._module_tokens

    @property
    @need_init_deferred
    def namespace(self):
        return self._module_tokens[0]

    @property
    @need_init_deferred
    def short_name(self):
        return self._module_tokens[-1]

    @property
    @need_init_deferred
    def is_created(self):
        return self._created

    @property
    @need_init_deferred
    def module(self):
        """
        Returns a comparch.modules.Module
        """
        from cdb.comparch.modules import Module
        module_tokens = list(self._module_tokens)
        while module_tokens:
            module = Module.ByKeys('.'.join(module_tokens))
            if module:
                return module
            module_tokens.pop()

    @need_init_deferred
    def dir(self, *args):
        if self._created:
            return os.path.join(self._base_path, *args)

    @property
    @need_init_deferred
    def base_dir(self):
        # TODO should be os.path.join-style function like pkgtools.path_join()
        return self.module.Package.getDistribution().location

    @property
    @need_init_deferred
    def apps(self):
        import json

        if self.module.Package.getDistribution().has_metadata("apps.json"):
            return json.loads(
                self.module.Package.getDistribution().get_metadata("apps.json"),
            )
        return []


class PackageAction(argparse.Action):
    """a python package identifying and containing the app"""
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(PackageAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace,
                self.dest, PackageConfig.from_list(values)
                if self.nargs else PackageConfig(values))
