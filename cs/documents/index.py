# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module contains functions to create an index.
"""

# pylint: disable=bad-continuation


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = ["createDocIndex"]


def createDocIndex(  # pylint: disable=too-many-arguments
    znum,
    zidx,
    zidx_new="",
    tidx_new="",
    ziel_pool="",
    create_tidx=0,
    cdb_ta_z="",
    cdb_taa_z="",
    cdb_ta_t="",
    cdb_taa_t="",
    mode=-1,
    check_part_existence=0,
    t_index_max_on=0,
):
    """
    Indizieren eines Dokuments/Modells.

    znum/zidx identifizieren das zu indizierende Dokument. Ein neuer
    Dokumentenindex kann in zidx_new vorgegeben werden, sonst wird der
    neue Index berechnet. Falls create_tidx verschieden von Null ist, wird fuer
    das dem Dokument assoziierte Teil ebenfalls ein Index
    angelegt. Dieser Index kann in tidx_new vorgegeben werden, oder
    wird andernfalls berechnet. Der Schalter mode bestimmt, ob der
    neue Index geprueft werden soll [nein (0), auf Existenz (1), auf
    Maximum (2), lt. Konfig. (-1)], siehe auch Property 'idxe'.
    Falls check_part_existence verschieden von Null ist, wird
    geprueft, ob der assoziierte Teileindex existiert.
    Falls t_max_index_on verschieden von Null ist, wird die neue
    Version des Dokumentes dem hoechsten Teileindex zugeordnet.
    DEPRECATED:
    - cdb_ta_z/cdb_taa_z bzw. cdb_ta_t/cdb_taa_t: Technische Aenderungen
    - ziel_pool

    Zurueckgegeben wird der neue Dokumentenindex.
    """
    import warnings

    warnings.warn(
        "createDocIndex is deprecated. Use Document.CreateIndex instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _createDocIndex(
        znum,
        zidx,
        zidx_new,
        tidx_new,
        ziel_pool,
        create_tidx,
        cdb_ta_z,
        cdb_taa_z,
        cdb_ta_t,
        cdb_taa_t,
        mode,
        check_part_existence,
        t_index_max_on,
    )


def _createDocIndex(  # pylint: disable=too-many-arguments,too-many-locals
    znum,
    zidx,
    zidx_new="",
    tidx_new="",
    ziel_pool="",
    create_tidx=0,
    cdb_ta_z="",
    cdb_taa_z="",
    cdb_ta_t="",
    cdb_taa_t="",
    mode=-1,
    check_part_existence=0,
    t_index_max_on=0,
):
    """
    See `createDocIndex`.
    """
    import cdbwrapc
    from cdb.platform import mom
    from cdb.platform.mom import entities

    cldef = entities.CDBClassDef("document")
    doc = mom.getObjectHandle(cldef, z_nummer=znum, z_index=zidx)
    args = []
    if zidx_new:
        args.append(mom.SimpleArgument("cdb::argument.z_index_neu", zidx_new))

    if tidx_new:
        args.append(mom.SimpleArgument("cdb::argument.t_index_neu", tidx_new))

    # Deprecated - might be handled in UE
    if ziel_pool:
        args.append(mom.SimpleArgument("cdb::argument.zielpool", ziel_pool))

    args.append(mom.SimpleArgument("cdb::argument.create_part_index", create_tidx))
    args.append(mom.SimpleArgument("cdb::argument.max_part_index", t_index_max_on))
    args.append(
        mom.SimpleArgument("cdb::argument.check_part_existence", check_part_existence)
    )
    if mode != -1:
        args.append(mom.SimpleArgument("cdb::argument.idxe_mode", mode))

    indexop = cdbwrapc.Operation("CDB_Index", doc, args)
    indexop.run()
    new_doc = indexop.getObjectResult()
    return new_doc["z_index"]
