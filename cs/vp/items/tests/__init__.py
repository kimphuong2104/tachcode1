# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module __init__

This is the documentation for the __init__ module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import cdbwrapc

from cdb import constants
from cdb import util
from cdb.objects import operations

from cs import documents
from cs.vp import items
from cs.vp.items import batchoperations


def generateItem(**kwargs):
    args = {
        "benennung": "Blech",
        "t_kategorie": "Baukasten",
        "t_bereich": "Engineering",
        "mengeneinheit": "qm"
    }
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        items.Item,
        **args
    )


def generateCADDocument(item, **kwargs):
    args = {
        "teilenummer": item.teilenummer,
        "t_index": item.t_index,
        "z_categ1": "144",  # Produkt/Teil
        "z_categ2": "177"  # CAD-Zeichnung
    }
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        "model",
        **args
    )


def generateStateChangeBatchOperation(parts, **kwargs):
    args = {
        "id": "%s" % util.nextval("cdb_bfolder"),
        "type_id": "teile_stamm",
        "operation": "PartStateChange",
        "param1": "100",
        "param2": "Review",
    }
    args.update(kwargs)

    batch_op = operations.operation(
        constants.kOperationNew,
        batchoperations.PartStateChangeImpl,
        **args
    )

    for part in parts:
        operations.operation(
            constants.kOperationNew,
            batchoperations.BatchOperationItemAssignment,
            id=batch_op.id,
            teilenummer=part.teilenummer,
            t_index=part.t_index,
            exec_state=0,
        )

    return batch_op
