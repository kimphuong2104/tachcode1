# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import logging

from cdb.objects import expressions, references
from cdb.objects.core import Object

fCurve = expressions.Forward("cs.materials.curve.Curve")
fDiagram = expressions.Forward("cs.materials.diagram.Diagram")
fMaterial = expressions.Forward("cs.materials.Material")

LOG = logging.getLogger(__name__)


class Diagram(Object):
    __maps_to__ = "csmat_diagram"
    __classname__ = "csmat_diagram"

    EXPORT_ATTRIBUTES = [
        "diagram_type",
        "mapped_abscissa",
        "mapped_ordinate",
        "mapped_curve_attribute",
        "title",
        "x_label",
        "x_type",
        "y_label",
        "y_type",
    ]

    Curves = references.Reference_N(fCurve, fCurve.diagram_id == fDiagram.cdb_object_id)

    Material = references.Reference_1(
        fMaterial, fDiagram.material_id, fDiagram.material_index
    )

    def to_json(self):
        curves = []
        for curve in self.Curves:
            curves.append(curve.to_json())
        json_data = {"curves": curves}
        for attr in Diagram.EXPORT_ATTRIBUTES:
            json_data[attr] = self[attr]
        return json_data

    def set_title(self, ctx):
        def get_lang_field(field_name, lang):
            localized_field_name = field_name + "_" + lang
            return getattr(ctx.dialog, localized_field_name, "")

        if ctx.changed_item == "diagram_type":
            # set title from curve type
            for lang, field in Diagram.title.getLanguageFields().items():
                if field.name in ctx.dialog.get_attribute_names():
                    title = "{} - {}".format(
                        get_lang_field("mapped_abscissa", lang),
                        get_lang_field("mapped_ordinate", lang),
                    )
                    ctx.set(field.name, title)

    event_map = {(("create", "modify", "copy"), "dialogitem_change"): "set_title"}


class DiagramType(Object):
    __maps_to__ = "csmat_diagram_type"
    __classname__ = "csmat_diagram_type"
