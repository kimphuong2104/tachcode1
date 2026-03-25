# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import datetime
import os
import sys

import cdbwrapc
from cdb import util
from cdb.constants import kArgumentPrefix, kOperationNew
from cdb.objects.cdb_file import CDB_File
from cdb.objects.org import CommonRoleSubject, User
from cdb.validationkit import operation
from cs.documents import Document
from cs.platform.org.user import UserSubstitute

from cs.pcs.projects import Project, ProjectCategory, Role, SubjectAssignment

PROJECT_ID = "SUBSTITUTE_UNITTEST"
SUBJECT_TYPE = User.__subject_type__


# functions for setting up test data
def create_project(cdb_project_id, *members, **kwargs):
    if "ce_baseline_id" not in kwargs:
        kwargs.update(ce_baseline_id="")
    kwargs.update({"cdb_project_id": cdb_project_id, "project_name": "test proj"})
    project = operation(kOperationNew, Project, kwargs)
    for member in members:
        project.assignTeamMember(member)
    return project


def create_project_ex(presets_custom=None, user_input_custom=None):
    project_category = ProjectCategory.Query()
    project_category_id = project_category[0].name if project_category else ""
    preset = {"category": project_category_id}
    if presets_custom:
        preset.update(presets_custom)
    user_input = {"project_name": "test project", "template": 0}
    if user_input_custom:
        user_input.update(user_input_custom)
    return operation(kOperationNew, Project, user_input=user_input, preset=preset)


def create_user(persno):
    # needs login, personalnummer
    user = User.Create(personalnummer=persno, login=persno, id=persno)
    return user


def create_ongoing_time_window():
    fromDate = None
    # set toDate to tomorrow to have an ongoing substitution
    toDate = datetime.date.today() + datetime.timedelta(days=1)
    return fromDate, toDate


def create_userSubstitution(user, substitute, fromDate, toDate):
    userSub = UserSubstitute.Create(
        period_start=fromDate,
        period_end=toDate,
        personalnummer=user.personalnummer,
        substitute=substitute.personalnummer,
    )
    # clear cache, which elsewise would give back the
    # old state without the new data entry
    cdbwrapc.clearUserSubstituteCache()
    return userSub


def assign_user_role_public(user):
    # assign the global/common role "public" to user
    assign_global_role(user, "public")


def assign_global_role(user, role_id):
    # assign the global/common role to user
    CommonRoleSubject.Create(
        role_id=role_id,
        subject_id=user.personalnummer,
        subject_type="Person",
        cdb_classname="cdb_global_subject",
    )
    # clear cache, which elsewise would give back the
    # old state without the new data entry
    util.reload_cache(util.kCGRoleCaches, util.kLocalReload)


def create_project_role(project, role_id):
    # create role "Projektmitglied" for the project
    Role.Create(
        role_id=role_id,
        cdb_project_id=project.cdb_project_id,
        team_assigned=0,
        team_needed=0,
    )


def assign_user_project_role(user, project, role_id):
    # assign project role "Projektmitglied" to the user
    SubjectAssignment.Create(
        role_id=role_id,
        subject_id2="",
        subject_id=user.personalnummer,
        subject_type="Person",
        cdb_project_id=project.cdb_project_id,
        cdb_classname="cdbpcs_subject_per",
    )
    # clear cache to allow role assignment
    util.reload_cache(util.kCGRoleCaches, util.kLocalReload)


def assign_user_project_role_with_wrong_classname(user, project, role_id):
    # assign project role "Projektmitglied" to the user
    # but use the wrong class name "cdbpcs_prj_role"
    SubjectAssignment.Create(
        role_id=role_id,
        subject_id2="",
        subject_id=user.personalnummer,
        subject_type="Person",
        cdb_project_id=project.cdb_project_id,
        cdb_classname="cdbpcs_prj_role",
    )
    # clear cache to allow role assignment
    util.reload_cache(util.kCGRoleCaches, util.kLocalReload)


def expand_test_data_filename(filename):
    if os.path.isfile(filename):
        file_path = filename
    else:
        files_dir = os.path.join(
            os.path.dirname(__file__.decode(sys.getfilesystemencoding())), "test_data"
        )
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


def change_project_msp_doc_by_base_fname(proj, base_fname):
    doc = create_document_from_base_fname(base_fname)
    doc.cdb_project_id = proj.cdb_project_id
    proj.msp_z_nummer = doc.z_nummer
    return doc


def setup_whole_data(userId, substituteId, roleId):
    # setup a test project with two users, both with the common
    # role "public" and the project role "Projektmitglied".
    # One substitutes the other in an ongoing substitution.
    # setup users and project
    user = create_user(userId)
    substitute = create_user(substituteId)
    project = create_project(PROJECT_ID, user, substitute)
    # setup users' roles
    create_project_role(project, role_id=roleId)
    assign_user_role_public(user)
    assign_user_project_role(user, project, role_id=roleId)
    assign_user_role_public(substitute)
    assign_user_project_role(substitute, project, role_id=roleId)
    # setup substitution
    fromDate, toDate = create_ongoing_time_window()
    substitutionEntry = create_userSubstitution(
        user=user, substitute=substitute, fromDate=fromDate, toDate=toDate
    )

    return {
        "user": user,
        "substitute": substitute,
        "project": project,
        "substitutionEntry": substitutionEntry,
    }


class MspXmlImportTestBase:
    """Class for common methods used by unit test modules but also by some benchmark classes."""

    @staticmethod
    def add_testdata(obj, base_fname):
        obj.log.info("Adding test data..")
        obj.project = create_project_ex()
        obj.xml_doc = create_document_from_base_fname(base_fname)
        obj.xml_doc.cdb_project_id = obj.project.cdb_project_id
        # Set MSP (resp. the document) as the primary project editor (resp. plan)
        obj.project.msp_active = 1
        obj.project.msp_z_nummer = obj.xml_doc.z_nummer

    @staticmethod
    def reset_testdata(obj):
        obj.log.info("Clearing project structure..")
        obj.project.AllTasks.Delete()
        obj.project.TaskRelations.Delete()

    @staticmethod
    def replace_xml_file(obj, filename):
        obj.log.info(f"Replacing XML file with '{filename}'..")
        file_path = expand_test_data_filename(filename)
        fobj = obj.xml_doc.Files.KeywordQuery(cdbf_type="XML")[0]
        fobj.checkin_file(file_path)

    @staticmethod
    def remove_testdata(obj):
        obj.log.info("Removing test data..")
        obj.project.msp_z_nummer = ""
        operation("CDB_Delete", obj.xml_doc)
        operation("CDB_Delete", obj.project)

    @staticmethod
    def call_import_from_xml(obj, proj, z_nummer, z_index):
        obj.log.info("Calling operation 'import_from_xml'..")
        start_time = datetime.datetime.now()
        # Passing following args simulates calling the operation from OfficeLink
        args = {
            "z_nummer": z_nummer,
            "z_index": z_index,
            "active_integration": "OfficeLink",
        }
        args = {".".join([kArgumentPrefix, k]): v for (k, v) in args.items()}
        result = operation("import_from_xml", proj, preset=args, interactive=False)
        seconds = (datetime.datetime.now() - start_time).seconds
        obj.log.info(f"The operation call returned after {seconds} seconds(s)")
        return result
