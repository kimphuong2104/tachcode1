# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module solidworksshowvariant

Register "Show in CAD" in varianteditor
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging


use_cs_variants = False

try:
    from cs.variants.cad_integration import register_open_in_cad_plugin
    from cs.wsm.variantmanagement.showvariant import show_in_wsm_cs_variants
    logging.info("Show_in_wsm variantmanger using cs.variants 15.8")
    use_cs_variants = True
except ImportError as exc:
    from cs.vp.variants.apps.generatorui import register_plugin
    logging.info("Show_in_wsm variantmanger using cs.variants pre 15.8 %s", exc)
try:
    from cs.wsm.variantmanagement.showvariant import show_in_wsm
except ImportError as exc:
    logging.info("Show_in_wsm from cs.wsm not available. cs.workspaces may be too old %", exc)
    show_in_wsm = None


# Exported objects
__all__ = []


def show_solidworks_in_wsm(state_id, selected_row, selected_maxbom_oid=None):
    """
    Dieses muss in jedem Plugin einzeln erfolgen und wir haben dann pro CAD
    einen Eintrag, da sonst die Filterung der MAXBOM auf die cadsource nicht
    funktioniert. Wir bekommen dann alle Zeilen fuer alle CAD zurueck, was dann
    beim HIDE_COMPONENT Problemen macht.
    """
    return show_in_wsm("SolidWorks:asm", state_id, selected_row, selected_maxbom_oid)


def show_solidworks_in_wsm_cs_variants(erzeug_system, walk_generator, ctx):
    """
    callback called from cs.variants during the 'now' hook from operation 'open in cad'

    :param erzeug_system: string like 'SolidWorks:asm'
    :param walk_generator: a instance of
        cs.variants.api.occurrence_walk_generator.OccurrenceWalkGenerator
    :param ctx: the operation context (now)
    :return:
    """
    show_in_wsm_cs_variants(erzeug_system, walk_generator, ctx)


if show_in_wsm is not None:
    if use_cs_variants:
        register_open_in_cad_plugin(
            "SolidWorks:asm",
            show_solidworks_in_wsm_cs_variants,
            label="solidworks_show_variant_wsm",
        )
    else:
        register_plugin(
            {
                "icon": "solidworks_show_variant_wsm",
                "label": "solidworks_show_variant_wsm",
                "json_name": "show_solidworks_in_wsm",
                "open_new_window": False,
                "json": show_solidworks_in_wsm,
                "position": 200,
            }
        )
