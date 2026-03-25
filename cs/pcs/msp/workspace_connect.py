#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import ElementsError, sig, ue
from cdb.comparch.packages import Package
from cdb.fls import get_license
from cdb.objects.cdb_file import CDB_File
from cs.documents import Document

from cs.pcs.helpers import get_and_check_object
from cs.pcs.msp.exports import XmlExport
from cs.pcs.msp.imports import XmlMergeImport
from cs.pcs.projects import Project

LICENSE_FEATURE_ID = "PROJECTS_030"

ACTIVE_PROJECTLINK_BUTTONS = "ACTIVE_PROJECTLINK_BUTTONS"
TASK_GUIDS_STARTED = "TASK_GUIDS_STARTED"
TASK_GUIDS_DISCARDED = "TASK_GUIDS_DISCARDED"
TASK_WERE_ADDED = "TASK_WERE_ADDED"
TASK_GUIDS_ALL = "TASK_GUIDS_ALL"
BUTTON_IDS = {
    "PUBLISH": ["PUBLISH_PROJECT"],
    "UPDATE": ["UPDATE_PROJECT", "UPDATE_ATTRIBUTES"],
}


def _check_wsm_installed():
    wsm_pkg = Package.ByKeys(name="cs.workspaces")
    if wsm_pkg:
        return True
    return False


def _get_project_and_xml_doc(parameters):
    """
    Identifies MSP-Document and corresponding project by keys in parameters.
    May return WSD specific error response if identification fails or identified
    MSP-Document is not the latest primary of its project.

    :param parameters: Key value mapping of Document keys. Must contain z_nummer and Z_index
    :type parameters: dict

    :returns: tuple of the identified project, the identified document and a WSD specific error respones
                project and doc are None if an error is encountered
                the error repsonse is None if no error is encountered
                Errors handled this way are:
                    - Document does not exist or is not readable
                    - Document is not attached to an existing project
                    - Document is not the latest primary MSP-Document of the project
    :rtype: tuple

    :raises: ValueError if given parameters lack the required keys `z_nummer` and `z_index`.
    """
    try:
        untrusted_z_nummer = parameters["z_nummer"]
        untrusted_z_index = parameters["z_index"]
    except KeyError as exc:
        raise ValueError from exc  # necessary keys z_nummer and z_index not in parameters

    kwargs = {"z_nummer": untrusted_z_nummer, "z_index": untrusted_z_index}
    xml_doc = get_and_check_object(Document, "read", **kwargs)
    if xml_doc is None:
        # Document does not exist or is not readable...
        return None, None, ([(1, "cdbpcs_msp_no_mpp_files", [])], {}, [])

    cdb_project_id = xml_doc.cdb_project_id
    projects = Project.KeywordQuery(cdb_project_id=cdb_project_id, ce_baseline_id="")
    if projects is None:
        # No project found
        return (
            None,
            None,
            ([(1, "cdbpcs_projects_not_found", [cdb_project_id])], {}, []),
        )
    project = projects[0]
    # Verify that given z_nummer and z_index belong to the latest MSP document of the identified project
    latest_xml_doc = project.getLastPrimaryMSPDocument()
    if latest_xml_doc is None:
        # Project has no primary MSP document
        return (
            None,
            None,
            ([(1, "cdbpcs_msp_no_primary_mpp", [cdb_project_id])], {}, []),
        )
    if (
        latest_xml_doc.z_nummer != xml_doc.z_nummer
        or latest_xml_doc.z_index != xml_doc.z_index
    ):
        # asked for xml_doc to write/read change to/from, but it is not the latest one, so not allowed
        return (
            None,
            None,
            ([(1, "cdbpcs_msp_xml_not_from_latest_mpp", [cdb_project_id])], {}, []),
        )
    return project, xml_doc, None


def _save_xml_file_to_xml_doc(xml_doc, path_to_import_file):
    # Get only XML file of latest primary MSP file of given document
    all_files = xml_doc.Files
    # Get Primary MSP file from Document
    primary_mpp_files_iterator = filter(
        lambda f: (f.cdbf_type == "MS-Project" and f.cdbf_primary == "1"), all_files
    )
    primary_mpp_files = list(primary_mpp_files_iterator)
    if len(primary_mpp_files) != 1:
        return (
            [
                (
                    1,
                    "cdbpcs_not_exactly_one_primary_msp_file_in_document",
                    [xml_doc.cdb_project_id],
                )
            ],
            {},
            [],
        )
    primary_mpp_fobj = primary_mpp_files[0]

    # Get non primary files of type xml derived from found mpp
    derived_xml_files_iterator = filter(
        lambda f: (
            f.cdbf_type == "XML"
            and f.cdbf_primary == "0"
            and f.cdbf_derived_from == primary_mpp_fobj.cdb_object_id
        ),
        all_files,
    )
    derived_xml_files = list(derived_xml_files_iterator)
    if len(derived_xml_files) > 1:
        return (
            [(1, "cdbpcs_multiple_xml_files_in_document", [xml_doc.GetDescription()])],
            {},
            [],
        )

    if not derived_xml_files:
        # Create new XML file on xml_doc and mark as derived from primary .mpp
        CDB_File.NewFromFile(
            xml_doc.cdb_object_id,
            path_to_import_file,
            False,
            additional_args={"cdbf_derived_from": primary_mpp_fobj.cdb_object_id},
        )

    if len(derived_xml_files) == 1:
        # Write the content of the new XML file into the XML file attached to the xml_doc
        derived_xml_files[0].checkin_file(path_to_import_file)

    return None


def _check_for_licence():
    if not get_license(LICENSE_FEATURE_ID):
        return (
            None,
            None,
            ([(1, "cdbfls_nolicforfeature", [LICENSE_FEATURE_ID])], {}, []),
        )
    return None


def _get_active_projectlink_buttons(project, xml_doc, msp_edition):
    """
    Calls 'check'-methods with given parameters and returns list of buttons to
    be activated in Project Link Plugin.

    The 'check'-methods are:
        - cs.pcs.msp.imports.XmlMergeImport.check_msp_edition
        - cs.pcs.msp.imports.XmlMergeImport.check_import_right
        - cs.pcs.msp.exports.XmlExport.check_export_right

    If msp_edition is not correct, no buttons are active
    If importing is allowed, publish buttons are active
    If exporting is allowed, update buttons are active
    """
    active_projectlink_buttons = []
    try:
        # only if no error occurs, the msp_edition is valid
        XmlMergeImport.check_msp_edition(project, msp_edition)
        is_correct_msp_edition = True
    except ue.Exception:
        is_correct_msp_edition = False

    if not is_correct_msp_edition:
        # no buttons are active
        return active_projectlink_buttons

    try:
        can_publish = XmlMergeImport.check_import_right(project, xml_doc, True)
    except ue.Exception:  # PO-specific exception
        can_publish = False

    if can_publish:
        active_projectlink_buttons += BUTTON_IDS["PUBLISH"]

    can_update = XmlExport.check_export_right(project, xml_doc, True)

    if can_update:
        active_projectlink_buttons += BUTTON_IDS["UPDATE"]

    return active_projectlink_buttons


def _get_list_of_synced_project_tasks(project):
    task_guids_all = []
    task_guids_started = []
    task_guids_discarded = []
    task_were_added = False
    for t in project.Tasks:
        if t.msp_guid not in ["", None]:
            task_guids_all.append(t.msp_guid)
            if t.percent_complet != 0 and t.percent_complet is not None:
                task_guids_started.append(t.msp_guid)
            if t.status == 180:
                task_guids_discarded.append(t.msp_guid)
        else:
            task_were_added = True
    return task_guids_all, task_guids_started, task_guids_discarded, task_were_added


@sig.connect("ws_appl_function", "cs_pcs_xml_to_ce")
def cs_pcs_xml_to_ce(parameters, files):
    """
    Connected to signal of the WSD Plugin 'Project Link' of the MSP-Integration for importing
    XML from WSD into CE.
    Ensures, that MSP-Document to be updated (identified by keys in parameters)
    is the latest primary MSP and if so hands back url to be called for the
    MSP Import Preview.

    :param parameters: Key value mapping of Document keys. Must contain z_nummer and Z_index
    :type parameters: dict

    :param file: List of RemoteFile Objects.
                 Must have exactly one element, that represents the XML doc
                 to import from.
    :type parameters: list of dict

    :returns: WSD-required response: tuple consisting of
                - list of tuples representing errors (only non-empty if an error occurs)
                    each error tuple has three values:
                        - error type (always 1)
                        - ID of CE error message
                        - list of parameters of above error message
                - dictionary of values
                    needs to be present, but is always empty
                - list of dicts representing files
                    needs to be present, but is always empty
    :rtype: tuple (list, dict, list)

    Internal helper method `_get_project_and_xml_doc` raises a ValueError if
    given parameters lack the required keys `z_nummer` and `z_index`.
    """
    # check licence
    licence_error = _check_for_licence()
    if licence_error:
        return licence_error

    _, xml_doc, error = _get_project_and_xml_doc(parameters)
    if error:
        # return Error to WSD in specific format
        return error
    if len(files) != 1:
        raise Exception(
            f"Not exactly one file given {files}"
        )  # files has to have exactly one element

    import_remote_file_obj = files[0]
    path_to_import_file = import_remote_file_obj.local_fname
    error = _save_xml_file_to_xml_doc(xml_doc, path_to_import_file)
    if error:
        return error

    return (
        [],  # errors
        {},  # values
        [],  # files
    )


@sig.connect("ws_appl_function", "cs_pcs_xml_from_ce")
def cs_pcs_xml_from_ce(parameters, files):
    """
    Connected to signal of the WSD Plugin 'Project Link' of the MSP-Integration for exporting
    XML from CE to WSD.
    Generates temporary XML file for the MSP document identified by the given keys
    in parameters and returns it location to the MSP-integration, so it can be
    downloaded.

    :param parameters: Key value mapping of Document keys. Must contain z_nummer and z_index.
    :type parameters: dict

    :param file: Unused - List of dictionaries with file information.
    :type parameters: list of dict

    :returns: WSD-required response: tuple consisting of
                - list of tuples representing errors (only non-empty if an error occurs)
                    each error tuple has three values:
                        - error type (always 1)
                        - ID of CE error message
                        - list of parameters of above error message
                - dictionary of values
                    if no error occurs, contains
                        - the file_id of the to be exported xml under the key `file`
                        - list of attributes configured at `project.XML_EXPORT_CLASS.TASK_UPDATABLE_MSP_ATTRS`
                          under the key 'TASK_UPDATABLE_MSP_ATTRS' - needed for 'Update Attributes'
                          function in the Project Link plugin.
                - list of RemoteFile Objects
                    if no error occurs, contains a single entry representing the
                    to be exported xml with  'local_fname' containing the
                    file's location on the server
    :rtype: tuple (list, dict, list)

    Internal helper method `_get_project_and_xml_doc` raises a ValueError if
    given parameters lack the required keys `z_nummer` and `z_index`.
    """
    if not _check_wsm_installed():
        raise ElementsError("Package cs.workspaces not installed - Signal call invalid")
    from cs.wsm.pkgs.applrpcutils import RemoteFile

    # check licence
    licence_error = _check_for_licence()
    if licence_error:
        return licence_error

    # get project to export xml for
    project, _, error = _get_project_and_xml_doc(parameters)
    if error:
        return error

    try:
        reset_ids = parameters["reset_ids"] == "True"
    except KeyError:
        reset_ids = False

    if reset_ids:
        # For safe (re-)importing tasks with matching UIDs between MSP and CDB afterwards:
        # Remove all GUIDs in the DB, because MSP always generates a new GUID when
        # importing a task or when copying it from another plan
        project.Tasks.Update(msp_guid="")
        project.Reload()

    # Export XML to local tmp dir and get file name
    filename = project.get_temp_export_xml_file()
    return (
        [],  # errors
        {  # params
            "file": "update_xml",
            "TASK_UPDATABLE_MSP_ATTRS": project.XML_EXPORT_CLASS.TASK_UPDATABLE_MSP_ATTRS,
        },
        [RemoteFile("update_xml", filename, "XML")],  # files
    )


@sig.connect("ws_appl_function", "cs_pcs_get_active_buttons")
def cs_pcs_get_active_buttons(parameters, files):
    """
    Connected to signal of the WSD Plugin 'Project Link' of the MSP-Integration for determining
    which Buttons (Update/Publish) in the Plugin are active/enabled.

    Calls internal 'check' functions with the project and MSP document identified
    by the given keys in `parameters` as well as with the currently used msp edition
    also given in `parameters`.

    :param parameters: Key value mapping. Must contain z_nummer, z_index and msp_edition
    :type parameters: dict

    :param file: Unused - List of dictionaries with file information.
    :type parameters: list of dict

    :returns: WSD-required response: tuple consisting of
                - list of tuples representing errors (only non-empty if an error occurs)
                    each error tuple has three values:
                        - error type (always 1)
                        - ID of CE error message
                        - list of parameters of above error message
                - dictionary of values
                    if no error occurs, contains
                        - list of active buttons under key 'ACTIVE_PROJECTLINK_BUTTONS'.
                          Each button is represented by a string constant
                - list of dicts representing files
                    needs to be present, but is always empty
    :rtype: tuple (list, dict, list)

    Internal helper method `_get_project_and_xml_doc` raises a ValueError if
    given parameters lack the required keys `z_nummer` and `z_index`.
    """
    # check licence
    licence_error = _check_for_licence()
    if licence_error:
        return licence_error

    try:
        msp_edition = parameters["msp_edition"]
    except KeyError as exc:
        raise ValueError from exc  # necessary key 'msp_edition' not in parameters

    # get project to export xml for
    project, xml_doc, error = _get_project_and_xml_doc(parameters)
    if error:
        return error
    # get list of to be active/enabled buttons in porject link plugin
    active_projectlink_buttons = _get_active_projectlink_buttons(
        project, xml_doc, msp_edition
    )

    return (
        [],  # errors
        {ACTIVE_PROJECTLINK_BUTTONS: active_projectlink_buttons},  # params
        [],  # files
    )


@sig.connect("ws_appl_function", "cs_pcs_get_sync_status")
def cs_pcs_get_sync_status(parameters, files):
    """
    Connected to signal of the WSD Plugin 'Project Link' of the MSP-Integration for determining
    if all Tasks in the opened Project are in sync between PO and MSP.

    :param parameters: Key value mapping. Must contain z_nummer and z_index
    :type parameters: dict

    :param file: Unused - List of dictionaries with file information.
    :type parameters: list of dict

    :returns: WSD-required response: tuple consisting of
                - list of tuples representing errors (only non-empty if an error occurs)
                    each error tuple has three values:
                        - error type (always 1)
                        - ID of CE error message
                        - list of parameters of above error message
                - dictionary of values
                    if no error occurs, contains
                        - list of guids of msp-synced tasks unde key 'TASK_GUIDS_ALL'
                        - list of guids of msp-synced started tasks under key 'TASK_GUIDS_STARTED'.
                        - list of guids of msp-synced discarded tasks under key 'TASK_GUIDS_DISCARDED'
                        - bool whether any tasks were added to the project and are thus not synced with msp
                          under the key 'TASK_WERE_ADDED'
                - list of dicts representing files
                    needs to be present, but is always empty
    :rtype: tuple (list, dict, list)

    Internal helper method `_get_project_and_xml_doc` raises a ValueError if
    given parameters lack the required keys `z_nummer` and `z_index`.
    """
    # check licence
    licence_error = _check_for_licence()
    if licence_error:
        return licence_error

    # get project to export xml for
    project, _, error = _get_project_and_xml_doc(parameters)
    if error:
        return error
    # get lists of synced msp tasks
    (
        task_guids_all,
        task_guids_started,
        task_guids_discarded,
        task_were_added,
    ) = _get_list_of_synced_project_tasks(project)

    return (
        [],  # errors
        {
            TASK_GUIDS_ALL: task_guids_all,
            TASK_GUIDS_STARTED: task_guids_started,
            TASK_GUIDS_DISCARDED: task_guids_discarded,
            TASK_WERE_ADDED: task_were_added,
        },  # params
        [],  # files
    )
