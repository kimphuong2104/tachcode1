#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Common interface of |cs.taskboard|
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig
from cdb import rte
from cs.taskboard.interfaces.board_adapter import BoardAdapter


REGISTER_BOARD_ADAPTER = sig.signal()


def register_sub_classes(cls):
    for subcls in cls.__subclasses__():
        for reg in sig.emit(REGISTER_BOARD_ADAPTER, subcls)():
            subcls.__CARD_ADAPTERS__ = dict(
                subcls.__CARD_ADAPTERS__, **reg["card_adapters"])
            subcls.__ALLOWED_CONTEXT_CLASSES__ = dict(
                subcls.__ALLOWED_CONTEXT_CLASSES__, **reg["context_adapters"])
            register_sub_classes(subcls)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def notificate_adapter_registrations():
    register_sub_classes(BoardAdapter)
