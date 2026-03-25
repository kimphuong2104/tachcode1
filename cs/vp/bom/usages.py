# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Efficiently compute the usages of some items inside a product structure.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb import sqlapi
from cdb import dberrors
from cdb import misc
import collections


# Exported objects
__all__ = [
    "get_all_usages", "get_usages"
]


def _fp(value):  # Format a Parameter for an sql query
    if value in [None, sqlapi.NULL]:
        return ''
    return sqlapi.quote(value)


def get_all_usages(*roots):
    """ compute usages for all the parts under the bom.

    IMPORTANT NOTE: This method should not be used anymore. It will be deprecated once there is an
    alternative API available, see E075249. In particular, this function
    * Does not work with PostgreSQL
    * Does not support Imprecise BOMs
    * Does not work reliably if the product structure contains cycles

        :param roots: The boms under which the usages are searched for.
            Can be instances of ``cs.vp.items.Items``, ``cs.vp.bom.AssemblyComponent``
            or ``cdb.sqlapi.Record``.

        :returns: a map (teilenummer, t_index) -> [(teilenummer, t_index)]
    """

    Q = """
        WITH bom (baugruppe, b_index, teilenummer, t_index)
        AS (
            SELECT baugruppe, b_index, teilenummer, t_index
            FROM einzelteile
            WHERE {condition}
            UNION ALL
            SELECT e.baugruppe, e.b_index, e.teilenummer, e.t_index
            FROM einzelteile e
            INNER JOIN bom b
            ON e.baugruppe=b.teilenummer AND e.b_index=b.t_index
        ),
        usages (nr, idx, baugruppe, b_index, teilenummer, t_index)
        AS (
            SELECT teilenummer, t_index, baugruppe, b_index, teilenummer, t_index
            FROM (SELECT DISTINCT * FROM bom) bom
            UNION ALL
            SELECT u.nr, u.idx, e.baugruppe, e.b_index, e.teilenummer, e.t_index
            FROM einzelteile e
            INNER JOIN usages u
            ON e.teilenummer=u.baugruppe AND e.t_index=u.b_index
        )
        SELECT DISTINCT * FROM usages
    """
    condition = " OR ".join([
        "(baugruppe='%s' AND b_index='%s')" % (root.teilenummer, root.t_index)
        for root in roots
    ])

    rs = sqlapi.RecordSet2(sql=Q.format(condition=condition))
    result = collections.defaultdict(list)
    for r in rs:
        result[(r.nr, r.idx)].append((r.baugruppe, r.b_index))
    return result


def get_usages(items, *boms):
    """ Compute a list of those items, which use the given items in their
        product structure and are contained in the product structure of
        some given boms. Return their object ids

        IMPORTANT NOTE: This method should not be used anymore. It will be deprecated once there is an
        alternative API available, see E075249. In particular, this function
        * Does not work with PostgreSQL
        * Does not support Imprecise BOMs
        * Does not work reliably if the product structure contains cycles

        :param items: a list the items, of which the usages are searched for
        :type items: a list of instances of ``cs.vp.items.Item``

        :param boms: a list of boms, under which the usages are searched for
        :type boms: instances of ``cs.vp.items.Item``

        :return: a list of strings
    """
    if items:
        # consider also engineering and manufacturing views
        _items = set(items)
        for item in items:
            if item.IsDerived() and item.EngineeringView:
                _items.add(item.EngineeringView)
            elif item.ManufacturingViews:
                _items.update(item.ManufacturingViews)

        items_condition = " OR ".join([
            "(teilenummer='{teilenummer}' AND t_index='{t_index}')"
            .format(teilenummer=_fp(item.teilenummer),
                    t_index=_fp(item.t_index))
            for item in _items
        ])

        boms_condition = " OR ".join([
            "(baugruppe='{teilenummer}' AND b_index='{t_index}')"
            .format(teilenummer=_fp(bom.teilenummer),
                    t_index=_fp(bom.t_index))
            for bom in boms
        ])

        try:
            QUERYSTR = """
                WITH usages (baugruppe, b_index, teilenummer, t_index)
                AS (
                    SELECT baugruppe, b_index, teilenummer, t_index
                    FROM einzelteile
                    WHERE {items_condition}
                    UNION ALL
                    SELECT e.baugruppe, e.b_index, e.teilenummer, e.t_index
                    FROM einzelteile e
                    INNER JOIN usages u
                    ON e.teilenummer=u.baugruppe AND e.t_index=u.b_index
                ),
                bom (baugruppe, b_index, teilenummer, t_index)
                AS (
                    SELECT baugruppe, b_index, teilenummer, t_index
                    FROM einzelteile
                    WHERE {boms_condition}
                    UNION ALL
                    SELECT e.baugruppe, e.b_index, e.teilenummer, e.t_index
                    FROM einzelteile e
                    INNER JOIN bom b
                    ON e.baugruppe=b.teilenummer AND e.b_index=b.t_index
                )
                SELECT teile_stamm.cdb_object_id item_object_id
                FROM teile_stamm, (
                    SELECT * FROM usages
                    INTERSECT
                    SELECT * FROM bom
                ) bomusages
                WHERE
                teile_stamm.teilenummer=bomusages.baugruppe AND
                teile_stamm.t_index=bomusages.b_index
            """.format(
                items_condition=items_condition,
                boms_condition=boms_condition
            )

            rs = sqlapi.RecordSet2(sql=QUERYSTR)
        except dberrors.DBError:
            misc.log(
                0,
                "cs.vp.bom: cyclic product structure detected, "
                "using fallback recursive query implementation"
            )

            # This query is (10x) slower than the other one, but runs without errors
            # even if an element of 'items' is contained in a recursive
            # product structure. Provided the elements of 'boms' are in
            # no such structure. In case of a recursion error, this query
            # is used as fallback
            QUERYSTR = """
                WITH
                bom (baugruppe, b_index, teilenummer, t_index)
                AS (
                    SELECT baugruppe, b_index, teilenummer, t_index
                    FROM einzelteile
                    WHERE {boms_condition}
                    UNION ALL
                    SELECT e.baugruppe, e.b_index, e.teilenummer, e.t_index
                    FROM einzelteile e
                    INNER JOIN bom b
                    ON e.baugruppe=b.teilenummer AND e.b_index=b.t_index
                ),
                usages (baugruppe, b_index, teilenummer, t_index)
                AS (
                    SELECT baugruppe, b_index, teilenummer, t_index
                    FROM bom
                    WHERE {items_condition}
                    UNION ALL
                    SELECT e.baugruppe, e.b_index, e.teilenummer, e.t_index
                    FROM bom e
                    INNER JOIN usages u
                    ON e.teilenummer=u.baugruppe AND e.t_index=u.b_index
                )
                SELECT DISTINCT teile_stamm.cdb_object_id item_object_id
                FROM teile_stamm, usages
                WHERE
                teile_stamm.teilenummer=usages.baugruppe AND
                teile_stamm.t_index=usages.b_index
            """.format(
                items_condition=items_condition,
                boms_condition=boms_condition
            )

            rs = sqlapi.RecordSet2(sql=QUERYSTR)

        return [r["item_object_id"] for r in rs]
    else:
        return []
