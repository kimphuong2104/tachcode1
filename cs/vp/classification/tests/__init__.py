import cdbwrapc

from cdb import constants
from cdb.objects import operations

from cs.vp import items
from cs.vp import classification

from cs.vp.items.tests import *


def generateProperty(**kwargs):
    args = {
        "prop_id": "test",
        "din4001_mm_mk": "test",
        "din4001_mm_dt": "T",
        "din4001_mm_v1": 1,
        "din4001_mm_n1": 0
    }
    args.update(kwargs)

    return operations.operation(
        constants.kOperationNew,
        classification.Property,
        **args
    )


def generatePropertySet(**kwargs):
    N = len(classification.PropertySet.Query())
    args = {"pset_id": "Test%s" % N}
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        classification.PropertySet,
        **args
    )


def assignPropertyToSet(prop, propset, **kwargs):
    args = {
        "pset_id": propset.pset_id,
        "prop_id": prop.prop_id,
        "prop_mk": prop.din4001_mm_mk
    }
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        classification.PropertyReference,
        **args
    )


def setProperty(part, pset_id, prop, value=3.14):
    cldef = cdbwrapc.CDBClassDef("part")
    facet = cdbwrapc.CDBClassDef(pset_id)
    facet_attr = cldef.getAttributeDefinition("sachgruppe")
    facet_prop_id = cldef.getFacetAttrIdentifier(facet_attr, facet.getAttributeDefinition("test"))

    args = {
        facet_prop_id: value
    }

    return operations.operation(
        constants.kOperationModify,
        part,
        operations.form_input(part, **args)
    )
