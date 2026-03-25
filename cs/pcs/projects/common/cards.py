#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import ElementsError
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.mom.relships import Relship
from cs.web.components.ui_support.display_contexts import DisplayConfiguration


def add_card(app_setup, classname, card):
    """
    Merges the serialized mask configuration into ``appSetup``:

    If a ``DisplayConfiguration`` for given ``classname`` and ``card`` exists,
    load the mask configuration of that name and put it into
    ``appSetup["applicationConfiguration"]["cards"][card][classname]``.

    :param app_setup: The application setup object.
    :type app_setup: cs.web.components.base.main.SettingDict

    :param classname: Classname to resolve ``card`` for.
    :type classname: string

    :param card: Name of the ``DisplayConfiguration`` to resolve.
    :type card: string
    """
    try:
        mask_name = DisplayConfiguration.get_mask_name(classname, card)
    except ElementsError:
        logging.exception(
            "error while requesting DisplayConfiguration for: '%s', '%s'",
            classname,
            card,
        )
        return

    # get_dialog raises ValueError when not called with a string
    if mask_name is None:
        logging.warning(
            "no display configuration found: '%s', '%s'",
            classname,
            card,
        )
        return
    cdef = CDBClassDef(classname)
    mask = cdef.get_dialog(mask_name, {})
    # The get_dialog parameter {} is a hack for the E069860 error messages.
    # Getting around this involves possibly refactoring the code.

    # get_dialog always returns dict with key "registers"
    if not mask["registers"]:
        logging.error("mask not found: '%s'", mask_name)
        return
    # get all relships with a cardinality of 1
    relships = Relship.KeywordQuery(referer=classname, rs_profile="cdb_association_1_1")
    links = {}
    for rs in relships:
        links[rs.name] = rs.rolename

    # replace mask item relship with relship rolename
    for r in mask["registers"]:
        for mi in r["maskitems"]:
            if "link_target" in mi["config"] and mi["config"]["link_target"]:
                if mi["config"]["link_target"] in links:
                    mi["config"]["link_target"] = links[mi["config"]["link_target"]]
                else:
                    mi["config"]["link_target"] = ""

    app_setup.merge_in(
        ["applicationConfiguration", "cards", card, classname],
        mask,
    )
