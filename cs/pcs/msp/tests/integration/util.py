# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import os

from cdb.constants import kOperationNew
from cdb.objects.cdb_file import CDB_File
from cdb.validationkit import operation
from cs.documents import Document
from cs.workflow.processes import Process

from cs.pcs.projects import Project, ProjectCategory
from cs.pcs.projects.tests.common import generate_baseline_of_project


def create_project_ex(presets_custom=None, user_input_custom=None):
    project_category = ProjectCategory.Query()
    project_category_id = project_category[0].name if project_category else ""
    preset = {"category": project_category_id}
    if presets_custom:
        preset.update(presets_custom)
    user_input = {"project_name": "test project", "template": 0}
    if user_input_custom:
        user_input.update(user_input_custom)
    prj = operation(kOperationNew, Project, user_input=user_input, preset=preset)
    generate_baseline_of_project(prj)
    return prj


def create_workflow(user_input_custom=None):
    user_input = {"title": "WF 002", "template": 1}
    if user_input_custom:
        user_input.update(user_input_custom)
    return operation(kOperationNew, Process, user_input=user_input)


def expand_test_data_filename(filename):
    if os.path.isfile(filename):
        file_path = filename
    else:
        files_dir = os.path.join(os.path.dirname(__file__), "test_data")
        file_path = os.path.join(files_dir, filename)
    return file_path


def create_document_from_base_fname(base_fname):
    # create file names for mpp and xml from file name base and
    # get path to corresponding existing test data files
    mpp_filename = base_fname + ".mpp"
    xml_filename = base_fname + ".xml"
    mpp_file_path = expand_test_data_filename(mpp_filename)
    xml_file_path = expand_test_data_filename(xml_filename)
    # create document
    doc = operation(
        kOperationNew,
        Document,
        user_input={"titel": f"{os.path.basename(base_fname)}"},
        preset={
            "cdb_obsolete": "0",
            "z_categ1": "145",  # Projektdokumentation
            "z_categ2": "181",  # Projektplan
            "z_art": "doc_standard",
            "vorlagen_kz": "0",
        },
    )
    # create files on document
    # exactly one primary MS-Project File
    additional_args = {"cdbf_type": "MS-Project"}
    mpp_file = CDB_File.NewFromFile(
        doc.cdb_object_id, mpp_file_path, primary=True, additional_args=additional_args
    )
    # and exactly one non primary XML File derived from the MS-Project File
    additional_args = {"cdbf_type": "XML", "cdbf_derived_from": mpp_file.cdb_object_id}
    CDB_File.NewFromFile(
        doc.cdb_object_id, xml_file_path, primary=False, additional_args=additional_args
    )
    return doc
