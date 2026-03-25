#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import logging

import pkg_resources
from cdb import rte, sig

__docformat__ = "restructuredtext en"

log = logging.getLogger(__name__)

# The global registry object.
Registry = None


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _load_registry():
    global Registry  # pylint: disable=global-statement
    Registry = _RegistryClass()


def get_registry():
    return Registry


class _RegistryClass(object):
    ADAPTER_ENTRY_POINT_GROUP = "cs.activitystream.subscription_category"

    def __init__(self):
        """Load all the defined entry points for implementations of
        subscription categories. Implementation classes are expected to
        have a class attribute 'priority', that is used to determine
        the order of displaying.
        """
        self._implementations = []
        log.info(
            "Start loading activity stream subscription category entry " "points ..."
        )
        for ep in pkg_resources.iter_entry_points(group=self.ADAPTER_ENTRY_POINT_GROUP):
            impl_cls = ep.load()
            log.info("  Loaded '%s' with priority %d", ep, impl_cls.priority)
            self._implementations.append(impl_cls)
        # Sort implementations once here
        self._implementations.sort(key=lambda categ: categ.priority, reverse=True)

    def get_categories(self):
        return self._implementations
