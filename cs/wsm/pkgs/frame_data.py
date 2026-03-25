# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module frame_data

This is the documentation for the frame_data module.
"""

from __future__ import absolute_import

import collections
import datetime
import logging

from cdb import cad
from cdb import constants
from cs.platform.web import root
from cs.platform.cad import FrameGroup
from cs.platform.cad import TitleBlock
from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


# Server code for delivering frame information on connection


def to_key_val(obj):
    ret = {}
    for k in obj.keys():
        v = obj[k]
        if v and isinstance(v, datetime.datetime):
            v = v.isoformat()
        ret[k] = v
    return ret


def load_frame_configuration(cad_systems, request=None):
    """
    We do not allow different number of ranks for the same attribute with different att_index.
    This should not happen because the integration will fail if the number doesn't match.

    Expects that "ZVS Schriftfeld komplett" is set for the the system in the framegroup or a fallback name
    for cad conf switch of this system.

    loads the current frame configuration from CDB
    :returns json compatible structure:
            {"frame_groupname": {"group_info": {key, val pairs},
                                 "tables: [{key, val pairs}], including aenderung*
                                 "frames": [[key, val pairs}],
                                 "title_block": {"<relation>": {"attributes: {{"<attr>": {<ranknr> : "Wert"},..},
                                                               {"cadnames": {<CADNAME>: <attribute>}
                                                }
                                 "complete_tables":  Boolean
                                }
    """
    frame_config = {}
    requested_systems = set([system.lower().split(":")[0] for system in cad_systems])
    logging.debug("Starting load_frame_configuration: (request: %s)", request)
    for f_g in FrameGroup.Query():
        if hasattr(f_g, "cdb_obsolete"):
            if f_g.cdb_obsolete == 1:
                continue
        if not f_g.CheckAccess(constants.kAccessRead):
            continue
        if f_g["cad_system"].lower().split(":")[0] not in requested_systems:
            continue
        complete_table = cad.isTrue(
            cad.getCADConfValue("ZVS Schriftfeld komplett", f_g["cad_system"])
        )
        frames = []
        use_direct_blob = GetCdbVersionProcessor.checkPresignedBlobConfig() == 0
        for f in f_g.Frames:
            if hasattr(f, "cdb_obsolete"):
                if f.cdb_obsolete == 1:
                    continue
            if not f.CheckAccess(constants.kAccessRead):
                continue
            frame_attrs = to_key_val(f)

            if use_direct_blob:
                frame_files = []
                for ff in f.Files:
                    vals = to_key_val(ff)
                    if hasattr(ff, "presigned_blob_url"):
                        vals["blob_url"] = ff.presigned_blob_url(
                            check_access=False, emit_read_signal=False
                        )
                    frame_files.append(vals)
            elif request is not None:
                collection_app = root.get_v1(request).child("collection")
                frame_files = []
                for ff in f.Files:
                    vals = to_key_val(ff)
                    vals["@id"] = request.link(ff, app=collection_app)
                    logging.debug("FrameLink: %s ", vals["@id"])
                    frame_files.append(vals)
            else:
                frame_files = [to_key_val(ff) for ff in f.Files]
            frame_attrs["files"] = frame_files
            frames.append(frame_attrs)

        aenderungs_relations = []
        last_relation = ""
        title_blocks = dict()
        rel_data = {"attributes": dict(), "cadnames": dict()}
        attrs = rel_data["attributes"]
        last_attr = ""
        attr_info = collections.defaultdict(dict)
        for tb in TitleBlock.KeywordQuery(
            order_by="relation, attribut, rang", gruppe=f_g.rahmen_gruppe
        ):
            # Rank 0 wird nicht an das CAD-System weiter gegeben
            if tb.rang == 0:
                continue
            rel = tb.relation
            if rel.upper().startswith("AENDERUNG"):
                aenderungs_relations.append(rel)
            if rel != last_relation:
                if last_relation != "":
                    attrs[last_attr] = attr_info
                    title_blocks[last_relation] = rel_data
                    rel_data = {"attributes": dict(), "cadnames": dict()}
                    last_attr = ""
                    attr_info = collections.defaultdict(dict)
                    attrs = rel_data["attributes"]
                last_relation = rel
            if tb.attribut != last_attr:
                if last_attr != "":
                    attrs[last_attr] = attr_info
                    attr_info = collections.defaultdict(dict)
                last_attr = tb.attribut
            attr_info[tb.rang] = tb.wert
            if tb.rang == 4:
                rel_data["cadnames"][tb.wert] = tb.attribut
        # insert last data
        if last_relation != "":
            if last_attr != "":
                attrs[last_attr] = attr_info
            title_blocks[last_relation] = rel_data
        tables = {}
        for t in f_g.FrameTables:
            tables[t.db_relation] = to_key_val(t)
        g_attrs = to_key_val(f_g)
        for aend in aenderungs_relations:
            if aend not in tables:
                tables[aend] = g_attrs
        if frames:
            group = {
                "group_info": g_attrs,
                "complete_tables": complete_table,
                "frame_layer": cad.getCADConfValue("ZVS Rahmen Layer", f_g.cad_system),
                "text_layer": cad.getCADConfValue(
                    "ZVS Schriftfeld Layer", f_g.cad_system
                ),
                "tables": tables,
                "frames": frames,
                "title_block": title_blocks,
            }
            frame_config[f_g.rahmen_gruppe] = group
    return frame_config
