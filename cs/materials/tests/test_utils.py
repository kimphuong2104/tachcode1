# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json

import cdbwrapc
from cdb import cdbuuid, constants, i18n
from cdb.objects.operations import operation, rship_operation
from cdb.platform.gui import Message
from cs.materials import Material, Material2Material, MaterialStates
from cs.materials.curve import Curve
from cs.materials.diagram import Diagram


def get_error_message(message_id, language=""):
    lang = language if language else i18n.default()
    message = Message.ByKeys(meldung_label=message_id)
    return message.Text[lang]


def create_curve(diagram, label, curve_data=""):
    create_args = {
        "diagram_id": diagram.cdb_object_id,
        "label_" + i18n.default(): label,
    }
    curve = operation(constants.kOperationNew, Curve, **create_args)
    if curve_data:
        try:
            curve.SetText("curve_data", Curve.format_json(json.loads(curve_data)))
        except Exception:  # pylint: disable=W0703
            curve.SetText("curve_data", curve_data)
    return curve


def create_diagram(material, title):
    create_args = {
        "material_id": material.material_id,
        "material_index": material.material_index,
        "title_" + i18n.default(): title,
    }
    diagram = operation(constants.kOperationNew, Diagram, **create_args)
    return diagram


def create_material(name, short_name="", status=MaterialStates.DRAFT):
    # Create Material in status DRAFT
    create_args = {
        "name_" + i18n.default(): name,
        "short_name": short_name if short_name else cdbuuid.create_uuid(),
    }
    material = operation(constants.kOperationNew, Material, **create_args)

    # if requested, change the material to the desired status
    if status == MaterialStates.REVIEW:
        material.ChangeState(MaterialStates.REVIEW)
    elif status == MaterialStates.RELEASED:
        material.ChangeState(MaterialStates.REVIEW)
        material.ChangeState(MaterialStates.RELEASED)
    elif status == MaterialStates.OBSOLETE:
        material.ChangeState(MaterialStates.REVIEW)
        material.ChangeState(MaterialStates.RELEASED)
        material.ChangeState(MaterialStates.OBSOLETE)

    return material


def copy_material(sourceMaterial, name, short_name):
    copy_args = {
        "name_" + i18n.default(): name,
        "short_name": short_name,
    }
    materialCopy = operation(constants.kOperationCopy, sourceMaterial, **copy_args)
    return materialCopy


def create_material_variant(material, name, short_name="", variant_type="treatment"):
    # Mask userexit is not executed in batch mode, hence need to pass the required values directly
    create_args = {
        "name_" + i18n.default(): name,
        "short_name": short_name if short_name else cdbuuid.create_uuid(),
        "variant_type": variant_type,
    }
    materialVariant = rship_operation(
        cdbwrapc.RelshipContext(material.ToObjectHandle(), "Variant"),
        constants.kOperationNew,
        Material,
        target_args=create_args,
    )

    return materialVariant


def create_material2material(parent, child):
    create_args = {
        "parent_id": parent.material_id,
        "parent_index": parent.material_index,
        "child_id": child.material_id,
        "child_index": child.material_index,
    }
    material2material = operation(
        constants.kOperationNew, Material2Material, **create_args
    )
    return material2material
