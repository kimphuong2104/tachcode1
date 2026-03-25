#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
A registry for document reference structure resolver implementations.
"""


__all__ = ["Registry"]

import logging
import re

import pkg_resources

from cdb import rte, sig

# The global registry object. Call Registry.getStrategy(doc) to get the
# resolver object to use.
Registry = None

_Logger = logging.getLogger(__name__)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _load_registry():
    global Registry  # pylint: disable=global-statement
    Registry = _RegistryClass()


class _RegistryClass(object):
    ADAPTER_ENTRY_POINT_GROUP = "cs.docref.resolver"

    def __init__(self):
        """Load all the defined entry points for resolver implementations, and
        store them in a list of pairs. The entry point names are interpreted
        as regular expressions, and matched against a documents 'erzeug_system'
        attribute.
        Implementation classes are expected to have a class attribute
        'priority', that is used to determine which implementation to use
        if more than one regex matches (higher values take precedence over
        lower values).
        """
        self._implementations = []
        _Logger.info("Start loading document reference resolver entry points ...")
        for ep in pkg_resources.iter_entry_points(group=self.ADAPTER_ENTRY_POINT_GROUP):
            impl_cls = ep.load()
            regexp = re.compile(impl_cls.match_expression)
            _Logger.info("  Loaded '%s' with priority %d", ep, impl_cls.priority)
            self._implementations.append((regexp, impl_cls))
        # Sort implementations once here, so that we can assume sorted order
        # when finding matches.
        self._implementations.sort(key=lambda tpl: tpl[1].priority, reverse=True)

    def getStrategy(self, doc):
        """Get the strategy implementation for the document, according to the
        documents 'erzeug_system'. If more than one matching implementation
        is found, the one with the highest priority is chosen.
        """
        erzsys = doc.erzeug_system
        if not erzsys:
            # Late import cause this should never happpen (E045273)
            from cdb.objects import NULL

            if erzsys == NULL:
                erzsys = ""
        matching = [
            impl_cls
            for (regexp, impl_cls) in self._implementations
            if regexp.match(erzsys)
        ]
        if not matching:
            # Should never occur: the standard registers an implementation
            # with priority 0 and a "match-all" regexp!
            raise RuntimeError(
                "No document reference resolver found for '%s'" % doc.erzeug_system
            )
        the_class = matching[0]
        if len(matching) > 1 and matching[0].priority == matching[1].priority:
            # If more than one match is found, log an error but continue.
            _Logger.error(
                "More than one document reference resolver found"
                " for '%s' with priority %d",
                doc.erzeug_system,
                the_class.priority,
            )
        _Logger.info(
            "Document reference resolver for %s-%s (%s) is %s",
            doc.z_nummer,
            doc.z_index,
            doc.erzeug_system,
            the_class,
        )
        return the_class(doc)
