# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Shared utils for cs.vp.bom nosetests

"""
from cdb import constants
from cdb.objects import operations

from cs.vp import items
from cs.vp import bom
from cs.vp.bom import AssemblyComponent

__all__ = [
    "generateComponent",
    "generateMBomComponent",
    "generateItem",
    "generateAssemblyComponent",
    "generateAssemblyComponentOccurrence"
]


def generateComponent(**kwargs):
    args = {
        "benennung": "Blech",
        "b_index": "",
        "t_index": "",
        "position": 1000,
        "variante": "",
        "auswahlmenge": 0.0
    }
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        AssemblyComponent,
        **args
    )


def generateMBomComponent(**kwargs):
    # This is the component that we want to generate the mBOM from.
    lbom = items.Item.ByKeys(teilenummer=kwargs.get("teilenummer"))

    # The newly generated mBOM.
    mbom = lbom.generate_mbom(question_copy_stl_relship_1st_level=1)

    # Put generated mBOM into specified assembly as a new position.
    args = {
        "baugruppe": kwargs.get("baugruppe"),
        "b_index": kwargs.get("b_index"),
        "teilenummer": mbom.teilenummer
    }

    return generateComponent(**args)


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


def generateAssemblyComponent(assembly, item=None, **kwargs):
    if item is None:
        item = generateItem()

    assembly.Reload()

    args = {"teilenummer": item.teilenummer,
            "t_index": item.t_index,
            "baugruppe": assembly.teilenummer,
            "b_index": assembly.t_index,
            "position": len(assembly.Components) * 10,
            "variante": "0",
            "auswahlmenge": 0.0,
            "is_imprecise": 0}
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        bom.AssemblyComponent,
        **args
    )


def generateAssemblyComponentOccurrence(assembly_component, **kwargs):
    from cs.vp.bom import AssemblyComponentOccurrence

    args = {
        "bompos_object_id": assembly_component.cdb_object_id,
        "occurrence_id": "some assembly component occurrence",
        "reference_path": "reference_path.prt",
        "assembly_path": "assembly_path.asm",
    }

    args.update(kwargs)

    return operations.operation(
        constants.kOperationNew,
        AssemblyComponentOccurrence,
        **args
    )


def generateDocument(**kwargs):
    args = {
        "z_categ1": "142",  # General
        "z_categ2": "154"   # Meeting Notes
    }
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        "document",
        **args
    )


def generateDocumentStructure(parent, child, **kwargs):
    args = {
        "reltype": "WSM",
        "logischer_name": "",
        "z_nummer": parent.z_nummer,
        "z_index": parent.z_index,
        "z_nummer2": child.z_nummer,
        "z_index2": child.z_index,
        "t_nummer2": "",
        "t_index2": "",
    }
    args.update(kwargs)
    return operations.operation(
        constants.kOperationNew,
        "cdb_doc_rel",
        **args
    )
