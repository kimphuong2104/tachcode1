#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2002 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Stuecklistenvergleich
"""

import sys
import copy
import time

import cdbwrapc

from cdb import dberrors
from cdb import ue
from cdb import misc
from cdb import sqlapi
from cdb import util
from cdb import cmsg
from cdb import classbody
from cdb import typeconversion

from cs.vp.items import Item


kStlcompareTypeEqual = 99
kStlcompareTypeLeft = 10
kStlcompareTypeRight = 20
kStlcompareTypePart = 30
kStlcompareTypeDifference = 60
kStlcompareTypeVersion = 40
kStlcompareTypePosition = 50


@classbody.classbody
class Item(object):
    pass

    @classmethod
    def on_cdb_parts_list_comparison_pre_mask(cls, ctx):
        if len(ctx.objects) > 2:
            raise ue.Exception("cdbvp_stlcompare_only_two")
        if len(ctx.objects) > 0:
            ctx.set("baugruppe1", ctx.objects[0].dbkeys["teilenummer"])
            ctx.set("b_index1", ctx.objects[0].dbkeys["t_index"])
        if len(ctx.objects) > 1:
            ctx.set("baugruppe2", ctx.objects[1].dbkeys["teilenummer"])
            ctx.set("b_index2", ctx.objects[1].dbkeys["t_index"])

    @classmethod
    def on_cdb_parts_list_comparison_now(cls, ctx):
        compare_parts_lists(ctx)


def safe_convert(value):
    # util.DBInserter will convert float values to strings in exponential notation (E049735)
    # therefore we're making the type conversion on our own

    try:
        return typeconversion.to_untyped_c_api(value)
    except NotImplementedError:
        # to_untyped_c_api will raise a NotImplementedError for unknown types
        return value


def safe_insert(table, values):
    # insert a record in a table, if it's not already there
    # works by catching unique constraint errors
    # and reraising any other error

    # useful for assemblies, which have multiple occurrences inside
    # a product structure

    inserter = util.DBInserter(table)
    for k in values.keys():
        inserter.add(k, values[k])

    try:
        inserter.insert()
    except RuntimeError:
        ti = util.tables[table]
        keynames = ti.keyname_list().split(', ')
        keys = ["%s" % values.get(keyname) for keyname in keynames]
        stmt = "1 from %s where %s" % (table, ti.key_condition(keys))

        t = sqlapi.SQLselect(stmt)
        if sqlapi.SQLrows(t) == 0:
            # not a unique constraint error
            raise


def compare_parts_lists(ctx):
    # Relationsnamen
    tname = 'einzelteile_v'           # Daten Quelle
    comptable1 = 'cdb_partslist_comp'  # Strukturdaten
    comptable2 = 'cdb_partslist_cval'  # Vergleichsergebnisse

    # Session ID und Timestamp
    session_id = util.nextval("cdb_parts_list_comp_session")
    session_timestamp = int(time.time())

    # cleanup old Sessions
    # Anzahl Tage nach denen alte Session gelöscht werden
    max_session_age = 1
    deprecation_time = session_timestamp - max_session_age * 60 * 60 * 24
    sqlapi.SQLdelete("from %s where session_timestamp<%s" % (
        comptable1, deprecation_time))
    sqlapi.SQLdelete("from %s where session_timestamp<%s" % (
        comptable2, deprecation_time))

    # Operationsparameter
    max_comp_depth = 99
    if ctx.dialog["depth"] == "":
        depth = max_comp_depth
    else:
        depth = int(ctx.dialog["depth"])
    compdepth = depth
    showsame = int(ctx.dialog["kumuliert"])

    # zu vergleichende Baugruppen
    assembly_number1 = ctx.dialog["baugruppe1"]
    assembly_index1 = ctx.dialog["b_index1"]
    assembly_number2 = ctx.dialog["baugruppe2"]
    assembly_index2 = ctx.dialog["b_index2"]

    cdef = cdbwrapc.CDBClassDef("bom_item")

    # zuvergleichende Attr. der Stücklistenpositionen
    comp_atts = ["menge", "netto_laenge"]
    comp_atts_name = {
        attr: cdef.getAttributeDefinition(attr).getLabel()
        for attr in comp_atts
    }

    # Schluesselattribute fuer Vergleich
    resultkey = 'position'
    keyatts = ['teilenummer', 't_index']

    # Wurzelobjekt einfuegen
    rootvalues = {
        "baugruppe1": '',
        "b_index1": '',
        "baugruppe2": '',
        "b_index2": '',
        "teilenummer1": assembly_number1,
        "t_index1": assembly_index1,
        "teilenummer2": assembly_number2,
        "t_index2": assembly_index2,
        "position": 0,
        "typ": 0,
        "tiefe": depth,
        "kumuliert": showsame,
        "session_id": session_id,
        "session_timestamp": session_timestamp
    }
    inserter = util.DBInserter(comptable1)
    for k in rootvalues.keys():
        inserter.add(k, rootvalues[k])
    inserter.insert()

    # Suche & Vergleiche
    assembly1 = {"baugruppe": assembly_number1, "b_index": assembly_index1}
    assembly2 = {"baugruppe": assembly_number2, "b_index": assembly_index2}
    tosearch = [(assembly1, assembly2)]
    while compdepth > 0:
        nextsearch = []
        for (current_assembly1, current_assembly2) in tosearch:
            # Vergleichsanfang: Datensortierung
            compresults = compare_attributes(
                tname, current_assembly1, current_assembly2, resultkey, keyatts, comp_atts)
            for pos in compresults.keys():
                c = compresults[pos]
                component_number1 = c.get("teilenummer1", '')
                component_index1 = c.get("t_index1", '')
                component_number2 = c.get("teilenummer2", '')
                component_index2 = c.get("t_index2", '')
                v1 = c.get("value1", {})
                v2 = c.get("value2", {})
                # Typen!
                diff_type = kStlcompareTypeEqual  # Die Pos. ist in beiden BG. gleich.
                pve = True
                if component_number1 and component_number2:
                    # Vergleichswerte nur eintragen, wenn es die Position
                    # in beiden Baugruppen gibt
                    for anatt in comp_atts:
                        value1 = v1.get(anatt, '')
                        value2 = v2.get(anatt, '')
                        if value1 != value2:
                            pve = False
                            # Vergleichsergebnisse in Relation "stlvergleich2" einfuegen
                            ovalue2 = {"attr_name": anatt,
                                       "attr_benennung": comp_atts_name.get(anatt, anatt),
                                       "wert1": safe_convert(value1),
                                       "wert2": safe_convert(value2),
                                       "position": pos,
                                       "baugruppe1": current_assembly1['baugruppe'],
                                       "b_index1": current_assembly1["b_index"],
                                       "baugruppe2": current_assembly2['baugruppe'],
                                       "b_index2": current_assembly2["b_index"],
                                       "session_id": session_id,
                                       "session_timestamp": session_timestamp}
                            safe_insert(comptable2, ovalue2)
                if not component_number2:
                    diff_type = kStlcompareTypeLeft  # Die Pos. nur in A vorhanden
                elif not component_number1:
                    diff_type = kStlcompareTypeRight  # Die Pos. nur in B vorhanden
                elif component_number1 != component_number2:
                    diff_type = kStlcompareTypePart  # Die Pos. unterscheidet sich durch einen anderen Artikel
                    if not pve:
                        diff_type = kStlcompareTypeDifference  # Die Pos. unterscheidet sich insgesamt
                elif component_index1 != component_index2:
                    diff_type = kStlcompareTypeVersion  # Die Pos. unterscheidet sich durch eine andere Version des Artikels
                elif not pve:
                    diff_type = kStlcompareTypePosition  # Die Pos. unterscheidet sich in den Werten der Positionsattribute

                if not showsame and diff_type == kStlcompareTypeEqual:
                    continue

                # Strukturdaten in Relation "stlvergleich" einfuegen
                ovalue1 = {"baugruppe1": current_assembly1['baugruppe'],
                           "b_index1": current_assembly1["b_index"],
                           "baugruppe2": current_assembly2['baugruppe'],
                           "b_index2": current_assembly2["b_index"],
                           "teilenummer1": component_number1,
                           "t_index1": component_index1,
                           "teilenummer2": component_number2,
                           "t_index2": component_index2,
                           "position": pos,
                           "typ": diff_type,
                           "tiefe": depth,
                           "kumuliert": showsame,
                           "session_id": session_id,
                           "session_timestamp": session_timestamp}
                safe_insert(comptable1, ovalue1)

                newg1 = {"baugruppe": component_number1,
                         "b_index": component_index1}
                newg2 = {"baugruppe": component_number2,
                         "b_index": component_index2}
                nextsearch.append((newg1, newg2))
        tosearch = copy.copy(nextsearch)
        compdepth -= 1
        pass

    # Strukturdarstellung aufrufen
    interactive = 1
    classname = "cdb_partslist_comp"
    nextact = "CDB_PartsListComparison"
    search_cond = {"baugruppe1": '',
                   "b_index1": '',
                   "baugruppe2": '',
                   "b_index2": '',
                   "teilenummer1": assembly_number1,
                   "teilenummer2": assembly_number2,
                   "t_index1": assembly_index1,
                   "t_index2": assembly_index2,
                   "position": '0',
                   "session_id": "%d" % session_id}
    query = cmsg.Cdbcmsg(classname, nextact, interactive)
    for key in search_cond.keys():
        query.add_item(key, comptable1, search_cond[key])
    ctx.url("cdbcmsg:" + query.read().decode())


def compare_attributes(table, o1, o2, resultkey, keyatts, comp_atts):
    """
    2 Objekte vergleichen
    """

    # fix E053026
    def get_components(object_keys):
        is_defined = lambda value: value is not None and value != ""
        if not is_defined(object_keys.get("baugruppe")) and not is_defined(object_keys.get("b_index")):
            return []
        else:
            return sqlapi.RecordSet2(
                table, util.tables[table].condition(list(object_keys), list(object_keys.values())))

    components_left = get_components(o1)
    components_right = get_components(o2)

    results = {}
    for comp in components_left:
        m = {}
        m = results.setdefault(comp[resultkey], m)
        for k in keyatts:
            m[k + '1'] = comp[k]
        for anatt in comp_atts:
            if not "value1" in m:
                m["value1"] = {}
            m["value1"][anatt] = comp.get(anatt, '')
    for comp in components_right:
        m = {}
        m = results.setdefault(comp[resultkey], m)
        for k in keyatts:
            m[k + '2'] = comp[k]
        for anatt in comp_atts:
            if not "value2" in m:
                m["value2"] = {}
            m["value2"][anatt] = comp.get(anatt, '')
    return results
