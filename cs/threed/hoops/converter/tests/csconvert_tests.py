#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the converter tool
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id: converter_tests.py 168423 2017-11-14 13:35:45Z gda $"

from collections import namedtuple

from cdb import cdbuuid
from cs.threed.hoops.converter import csconvert

DocumentMock = namedtuple("DocumentMock", "titel z_nummer z_index")

input_params = [
    "read_geom_tess_mode", "root_dir_recursive", "use_root_dir",
    "read_only_active_filter", "read_attributes", "read_construction_and_references",
    "import_hidden_objects", "read_pmi", "read_solids", "read_surfaces",
    "read_wireframes", "default_unit", "always_substitute_font",
    "always_use_default_color", "default_pmi_unit", "number_of_digits_after_dot",
    "substitution_font", "default_pmi_color", "configuration",
    "accurate_tessellation", "skip_normals_in_accurate_tessellation",
    "keep_uv_points", "tessellation_lod"
]

task_params = [
    ("fbx", "ascii"),
    ("jt", "write_hidden"),
    ("jt", "write_pmi"),
    ("jt", "jt_version"),
    ("pdf", "model_field"),
    ("pdf", "author"),
    ("pdf", "creator"),
    ("pdf", "subject"),
    ("pdf", "title"),
    ("pdf", "pmi_color"),
    ("pdf", "disable_interactivity"),
    ("pdf", "open_model_tree"),
    ("pdf", "show_toolbar"),
    ("pdf", "transparent_background"),
    ("pdf", "activate_when"),
    ("pdf", "deactivate_when"),
    ("pdf", "lighting"),
    ("pdf", "rendering_style"),
    ("pdf", "border"),
    ("pdf", "background_color"),
    ("pdf", "template_file"),
    ("prc", "compress_brep"),
    ("prc", "compress_brep_type"),
    ("prc", "compress_tessellation"),
    ("prc", "remove_attributes"),
    ("prc", "remove_brep"),
    ("step", "format"),
    ("step", "short_names"),
    ("step", "write_attributes"),
    ("step", "write_pmi"),
    ("step", "write_pmi_as_tessellated"),
    ("step", "write_pmi_with_semantic"),
    ("step", "write_validation_properties"),
    ("step", "configuration"),
    ("stl", "accurate_tessellation"),
    ("stl", "export_to_binary"),
    ("stl", "keep_current_tessellation"),
    ("stl", "tessellation_level"),
]


def test_task_params():
    "Check that tool.HoopsConverter passes the parameters to the format tags"

    for format, param in task_params:
        yield (check_task_param, format, param)


def check_task_param(format, param):
    converter = csconvert.Converter(models=[DocumentMock("", "", "")], service_mode=False)
    input_path = "%s.%s" % (cdbuuid.create_uuid(), format)
    converter.new_conversion(input_path)

    value = cdbuuid.create_uuid()
    converter.add_task(format, {
        param: value,
        "output": ""
    })

    for conversion in converter.elements:
        for task in conversion.iter("Format%s" % format.upper()):
            assert param in task.keys(), \
                "%s doesn't have the attribute %s" % (
                    task.tag, param)
            assert task.get(param) == value, \
                "Wrong value for %s on tag %s. Expected %s, found %s" % (
                    param,
                    task.tag,
                    value,
                    task.get(param)
                )


def test_input_params():
    "Check that tool.HoopsConverter passes the parameters to the input tag"

    for param in input_params:
        yield (check_input_param, param)


def check_input_param(param):
    converter = csconvert.Converter(models=[DocumentMock("", "", "")], service_mode=False)
    input_path = "%s.%s" % (cdbuuid.create_uuid(), format)

    value = cdbuuid.create_uuid()
    converter.new_conversion(input_path, params={param: value})

    for conversion in converter.elements:
        for input_tag in conversion.iter("Input"):
            assert param in input_tag.keys(), \
                "%s doesn't have the attribute %s" % (
                    input_tag.tag, param)
            assert input_tag.get(param) == value, \
                "Wrong value for %s on tag %s. Expected %s, found %s" % (
                    param,
                    input_tag.tag,
                    value,
                    input_tag.get(param)
                )
