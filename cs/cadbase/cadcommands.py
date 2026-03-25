#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


"""
Module cadcommands

API for creating standard commands for manipulation of CAD models and drawings.

This is a wrapper for Workspaces CAD Link and DCS modules
"""

import sys
import copy
import json
import logging
from cdb.plattools import killableprocess

from .appjobs.appcommand import AppCommand
from .appjobs.appcommandresult import AppCommandResult
from .appjobs.appjob import AppJob
from .appjobs.appjobitem import processingFlags, appCommParams
from .wsutils.resultmessage import Result, ResKind
from .wsutils.collectionutils import removeDuplicatesOrdered


def convert_matrix(position):
    """
    Converts the specified 4x4 position matrix in CDB format
    into a positions list.
    """
    p = []
    for r in range(position.getRows()):
        for c in range(position.getCols()):
            p.append("%s" % position.getElement(c, r))
    return p


class AppCommandExecute(AppCommand):
    def __init__(
        self,
        name,
        fname,
        contextFiles,
        parameters,
        flags,
        operation,
        successActions=None,
        failActions=None,
        preActions=None,
    ):
        """
        Initializes self

        :Parameters:
            name : unicode
                The name of this command. Is evaluated by the integrated
                applications
            fname : unicode or None
                The main file this command operates on
            contextFiles : list or None
                This command should operate in context of these files
            parameters : list or None
                Parameters of this command.
            flags : list of processingFlags or None
            operation : AppOperation
                The operations which is to associate with this AppCommand
                instance
            successActions : list or None
                Actions to execute when this command has been processed
                successfully
            failActions : list or None
                Actions to execute when this command has been processed
                erroneously
            preActions : list or None
                Actions to execute before this command is going to be processed
        """
        AppCommand.__init__(
            self,
            name,
            fname,
            contextFiles,
            parameters,
            flags,
            operation,
            successActions,
            failActions,
            preActions,
        )
        self.return_code = None
        self.err_msg = None

    def execute_local(self):
        """
        excutes_given_process and returns AppCommandResult() w/o. data
        """
        appCommRes = AppCommandResult()
        proc_parameters = []
        program = None
        res_type = (
            ResKind.kResError
            if processingFlags.StopOnError in self.flags
            else ResKind.kResInfo
        )
        timeout = -1
        for (p, val) in self.parameters:
            if p == "program":
                program = val
            elif p == "parameter":
                if val:
                    proc_parameters = json.loads(val)
            elif p == "timeout":
                if val and val.isdigit():
                    timeout = int(val)
                    if timeout == 0:
                        timeout = -1
        if program:
            args = [program]
            args.extend(proc_parameters)
            try:
                logging.debug("AppCommandExecute: Call: %s", args)
                return_code = killableprocess.call(args, timeout=timeout)
                if return_code != 0:
                    logging.error(
                        "AppCommandExecute: Command '%s' exitcode : %s",
                        program,
                        return_code,
                    )
                    msg = "{} failed with exit code {}".format(program, return_code)
                    appCommRes.append(res_type, ("appjobs", msg))
            except EnvironmentError as ex:
                logging.error(
                    "AppCommandExecute: Command '%s' execution failed: %s", program, ex
                )
                msg = "Command '{}' not executed ({})".format(program, str(ex))
                appCommRes.append(res_type, ("appjobs", msg))
        else:
            logging.error("AppCommandExecute: No program to run given")
            appCommRes.append(res_type, ("appjobs", "No program name"))
        return appCommRes


class CadCommand(object):
    """
    Base Command Wrapper

    Actual wrappers must be derived from this class.
    A command wrapper ist responsible for generating an AppCommand,
    parsing its result and offering helper methods for result queries.
    """

    DEFAULT_FLAGS = [processingFlags.StopOnError]

    CAD_ROOT_DIR = "[\\\\:__ROOT]"

    def __init__(self, app_command):
        """
        Base constructor, must be overloaded by real generator implementations

        :param app_command: AppCommand instance
        """
        self.job = None
        self.cmd_index = None
        self.app_command = app_command

    def bind_to_job(self, job, cmd_index):
        # FIXME: this method is probably not needed
        self.job = job
        self.cmd_index = cmd_index

    def execute(
        self,
        cad_system=None,
        job_exec=None,
        job_dir=None,
        project_env=None,
        test_env=None,
    ):
        """
        Execute CAD command

        :param cad_system:  Name of the CAD system as String. If None, value
                            from test_env is used.
        :param job_exec:    Callable, which receives an AppJob instance as
                            parameter. If None, value from test_env is used.
        :param job_dir:     Existing directory where the job is created as String.
        :param project_env: CAD project environment for jobs
        :param test_env:    Reference to a CADIntegrationTest instance or its
                            derivative or None. If None, cad_system, job_exec,
                            job_dir must be set.
        """
        runner = JobRunner(cad_system, job_exec, job_dir, project_env, test_env)
        job = runner.create_job()
        job.append(self)
        return job.execute()

    def serialize(self):
        """
        serailize this job to a json compatible python structure
        :returns: python dict
        """
        r = {
            "operation": self.app_command.name,
            "fname": self.app_command.file,
            "parameter": self.app_command.parameters,
            "flags": self.app_command.flags,
            "context_files": self.app_command.contextFiles,
            "classname": self.__class__.__module__ + "." + self.__class__.__name__,
        }
        return r

    def result(self):
        """
        Retrieves the result of the unterlying CAD command.

        :returns: Result object with status of command
        """
        return self.app_command.getResult()


class CmdLoad(CadCommand):
    """
    LOAD Command Wrapper
    """

    def __init__(
        self, fname, load_mode="NORM", flags=CadCommand.DEFAULT_FLAGS, variant_id=""
    ):
        """
        Construct a LOAD command

        :param fname: Name of file to be loaded
        :param load_mode: Load mode
        :param flags: Command execution flags
        """
        params = [
            (appCommParams.loadmode, load_mode),
            (appCommParams.variantid, variant_id),
        ]
        context_files = None
        app_cmd = AppCommand("LOAD", fname, context_files, params, flags, None)
        CadCommand.__init__(self, app_cmd)


class CmdClose(CadCommand):
    """
    CLOSE Command Wrapper
    """

    def __init__(self, fname, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a CLOSE command

        :param fname: Name of file to be closed
        :param flags: Command execution flags
        """
        params = None
        app_cmd = AppCommand("CLOSE", fname, None, params, flags, None)
        CadCommand.__init__(self, app_cmd)


class CmdCloseAll(CadCommand):
    """
    CLOSE_ALL Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a CLOSE_ALL command

        :param flags: Command execution flags
        """
        params = None
        cmd = AppCommand("CLOSE_ALL", "", None, params, flags, None)
        CadCommand.__init__(self, cmd)


class CmdEnsureNotLoaded(CadCommand):
    """
    ENSURE_NOT_LOADED Command Wrapper
    """

    def __init__(self, files_to_close, force_mode, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a ENSURE_NOT_LOADED command

        Command to close assemblies that use the specified files

        :param files_to_close: json list of filenames (full path)
        :param force_mode: string, "NO" (close only if there are no modified files)
                                   "SAVE" (save all files before closing)
                                   "DISCARD" (discard all changes before closing)
        """
        params = [("files_to_close", files_to_close), ("force_mode", force_mode)]
        app_cmd = AppCommand("ENSURE_NOT_LOADED", "", None, params, flags, None)
        CadCommand.__init__(self, app_cmd)

    def get_results(self):
        """
        :returns list of modified and closed files
        """
        modified = None
        closed = None
        cmd_result = self.app_command.getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                # result without empty string list items
                ml = data.get("modified")
                if ml:
                    modified = list(filter(None, ml))
                cl = data.get("closed")
                if cl:
                    closed = list(filter(None, cl))
        return modified, closed


class CmdRename(CadCommand):
    """
    RENAME Command Wrapper
    """

    def __init__(
        self, fname, new_filename, context_files=None, flags=CadCommand.DEFAULT_FLAGS
    ):
        """
        Construct a RENAME command

        :param fname: Name of file to be renamed
        :param new_filename: New file name
        :param context_files: Context files
        :param flags: Command execution flags
        """
        params = [(appCommParams.new_filename, new_filename)]
        app_cmd = AppCommand("RENAME", fname, context_files, params, flags, None)
        CadCommand.__init__(self, app_cmd)


class CmdGetWindowTitle(CadCommand):
    """
    GET_WINDOW_TITLE Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a GET_WINDOW_TITLE command

        :param flags: Command execution flags
        """
        params = None
        context_files = None
        app_cmd = AppCommand("GET_WINDOW_TITLE", "", context_files, params, flags, None)
        CadCommand.__init__(self, app_cmd)

    def get_window_title(self):
        """
        :returns CAD system window title or None on failure
        """
        ret = None
        cmd_result = self.app_command.getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                vl = data.get("window_title")
                if vl:
                    ret = vl[0]
        return ret


class CmdShutdown(CadCommand):
    """
    SHUTDOWN Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a SHUTDOWN command

        :param flags: Command execution flags
        """
        params = None
        app_cmd = AppCommand("SHUTDOWN", "", None, params, flags, None)
        CadCommand.__init__(self, app_cmd)


class CmdGetProjectEnvironment(CadCommand):
    """
    GET_PROJECT_ENVIRONMENT Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a GET_PROJECT_ENVIRONMENT command

        :param flags: Command execution flags
        """
        params = None
        app_cmd = AppCommand("GET_PROJECT_ENVIRONMENT", "", None, params, flags, None)
        CadCommand.__init__(self, app_cmd)

    def get_project_environment(self):
        """
        :returns: Project environment or None
        """
        ret = None
        cmd_result = self.job.cmds[self.cmd_index].getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                rval = data.get("project_env")
                if rval:
                    ret = rval[0]
        return ret


class FileListParser(object):
    """
    Helper class for commands which retrieve file lists
    """

    @staticmethod
    def parse_file_list(data, list_name, parse_lock_states=True):
        """
        Extract list of files loaded in CAD with their corresponding
        modification and lock states. If reading lock state is not supported by
        the CAD system, it's set to None

        :param data: Dictionary as returned by the AppCommand
        :param list_name: Name of the file list to be parsed
        :param parse_lock_states: Parse lock states if true

        :returns: Dictionary containing
                    {filepath: (modification state, lock state)}
        """
        # lockstates: list of boolean strings (and trailing empty string),
        # e.g. ["TRUE", "FALSE", "TRUE", ""]
        if parse_lock_states:
            lock_states = data.get("loadedfiles_lockstates", None)
        else:
            lock_states = None
        loaded_files = data.get(list_name, None)
        result = {}
        if loaded_files is not None:
            # FileList = Filename 0, ModificationState 0,
            #            Filename 1, ModificationState 1, ...
            number_of_files = len(loaded_files) // 2
            lock_state_available = False
            if lock_states is not None:
                if number_of_files <= len(lock_states):
                    lock_state_available = True
                else:
                    raise Exception(
                        "Parsing lock states failed: number of lock states "
                        "does not match the number of files"
                    )

            for i in range(number_of_files):
                fname = loaded_files[2 * i]
                if fname:
                    modified_state = loaded_files[2 * i + 1] == "TRUE"
                    lock_state = None
                    if lock_state_available:
                        lock_state = lock_states[i] == "TRUE"
                    result[fname] = (modified_state, lock_state)
        return result


class CmdTopFiles(CadCommand):
    """
    TOPFILES Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a TOPFILES command.

        :param flags: Command execution flags
        """
        params = None
        cmd = AppCommand("TOPFILES", "", None, params, flags, None)
        CadCommand.__init__(self, cmd)

    def get_top_files(self):
        """
        Get list of top level files using FileListParser.parse_file_list()

        :returns: Dictionary containing
                    {filepath: (modification state, None)}
        """
        top_files = None
        cmd_result = self.app_command.getResult()
        if cmd_result.isOk() and cmd_result.data() is not None:
            top_files = FileListParser.parse_file_list(
                cmd_result.data(), "topfiles", False
            )
        return top_files


class CmdListOfFiles(CmdTopFiles):
    """
    LISTOFFILES Command Wrapper
    """

    def __init__(self, top_files=False, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a LISTOFFILES command.

        :param top_files: Retrieve list of Top file if True
        :param flags: Command execution flags
        """
        params = [("topfiles", "TRUE" if top_files else "FALSE")]
        cmd = AppCommand("LISTOFFILES", "", None, params, flags, None)
        CadCommand.__init__(self, cmd)

    def get_loaded_files(self):
        """
        Get list of files using parse_file_list()

        :returns: Dictionary containing
                    {filepath: (modification state, lock state)}
        """
        loaded_files = None
        cmd_result = self.app_command.getResult()
        if cmd_result.isOk() and cmd_result.data() is not None:
            loaded_files = FileListParser.parse_file_list(
                cmd_result.data(), "loadedfiles"
            )
        return loaded_files


class CmdCD(CadCommand):
    """
    CD Command Wrapper
    """

    def __init__(self, path, flags=CadCommand.DEFAULT_FLAGS, additional_args=None):
        """
        Construct a CD command

        :param path: string, Absolute path to the working directory
        :param flags: Command execution flags
        :param additional_args: list of arg tuples or None
        """
        params = [("path", path)]
        if additional_args is not None:
            params.extend(additional_args)
        cmd = AppCommand("CD", "", None, params, flags, None)
        CadCommand.__init__(self, cmd)


class CmdPWD(CadCommand):
    """
    PWD Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a PWD command

        :param flags: Command execution flags
        """
        params = None
        cmd = AppCommand("PWD", "", None, params, flags, None)
        CadCommand.__init__(self, cmd)

    def get_working_directory(self):
        """
        :returns Current working directory or None
        """
        ret = None
        cmd_result = self.app_command.getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                rval = data.get("workingdirectory")
                if rval:
                    ret = rval[0]
        return ret


class CmdSaveAppInfo(CadCommand):
    """
    SAVEAPPINFO Command Wrapper
    """

    def __init__(
        self,
        fname,
        context_files,
        extend,
        force=False,
        dont_save_workfile=False,
        regenerate=False,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a SAVEAPPINFO command

        :param fname: string, Name of file to be saved
        :param context_files: list of strings, Context files
        :param extend: string of SINGLE | SUBCOMPONENTS | ALL
        :param force: boolean, Ignore timestamp and force app info writing
        :param dont_save_workfile: boolean, Do not save work file if True
        :param regenerate: boolean, Regenerate (e.g. update views) before saving
        :param flags: Command execution flags
        """
        params = [
            ("extend", extend),
            ("force", str(force).upper()),
            ("dontSaveWorkfile", str(dont_save_workfile).upper()),
            ("regenerate", str(regenerate).upper()),
        ]
        app_cmd = AppCommand("SAVEAPPINFO", fname, context_files, params, flags, None)
        CadCommand.__init__(self, app_cmd)


class CmdFillFrame(CadCommand):
    """
    FILL_FRAME Command Wrapper
    """

    def __init__(
        self,
        fname,
        context_files,
        frame_data_json=None,
        frame_hash=None,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a FILL_FRAME command

        :param fname: string, File name
        :param context_files: list of strings, Context files
        :param frame_data_json: python dict, result from PdmInfoHelper.getFrameDataForJson()
        :param frame_hash: string, Frame hash value
        :param flags: Command execution flags
        """
        param = []
        if frame_data_json is not None:
            param.append(("framedatajson", json.dumps(frame_data_json)))
        if frame_hash is not None:
            param.append(("framehash", frame_hash))
        cmd = AppCommand("FILL_FRAME", fname, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdSetParameter(CadCommand):
    """
    SET_PARAMETER Command Wrapper
    """

    def __init__(
        self,
        fname,
        context_files,
        parameter_json=None,
        parameter_hash=None,
        regenerate=False,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a SET_PARAMETER command

        :param fname: string, File name
        :param context_files: List of strings, Context files
        :param parameter_json: List of dicts with value type, value, name.
                               result from PdmInfoHelper.getCadParameterForJson()
        :param parameter_hash: string
        :param regenerate: boolean. Regenerate model after setting of parameter
        :param flags: Command execution flags
        """
        param = []
        if parameter_json is not None:
            param.append(("parameterjson", json.dumps(parameter_json)))
        if parameter_hash is not None:
            param.append(("parameterhash", parameter_hash))
        param.append(("regenerate", "TRUE" if regenerate else "FALSE"))
        cmd = AppCommand("SET_PARAMETER", fname, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdReplace(CadCommand):
    """
    REPLACE Command Wrapper
    """

    def __init__(
        self,
        fname,
        context_files,
        new_filename,
        replace_all_instances,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a REPLACE command

        :param fname: string, Name of the file to be replaced
        :param context_files: List of strings, Context files
        :param new_filename: string with absolute pathname of the new file
        :param replace_all_instances: boolean
        :param flags: Command execution flags
        """
        param = [
            ("newfile", new_filename),
            ("replaceAllInstances", "TRUE" if replace_all_instances else "FALSE"),
        ]
        cmd = AppCommand("REPLACE", fname, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdReplace2(CadCommand):
    """
    REPLACE Command Wrapper with extended parameters
    """

    def __init__(
        self,
        fname,
        context_files,
        new_filename,
        replace_all_instances,
        replace_occurrence=None,
        current_variant_id=None,
        new_variant_id=None,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a REPLACE command

        :param fname: string, Name of the file to be replaced
        :param context_files: List of strings, Context files
        :param new_filename: string with absolute pathname of the new file
        :param replace_all_instances: boolean
        :param replace_occurrence: string with the occurrence id
        :param current_variant_id: String with a variant id. Only occurrences with
            this variant id should replace
        :param new_variant_id: String with the variant id of the replacing file
        :param flags: Command execution flags
        """
        param = [
            ("newfile", new_filename),
            ("replaceAllInstances", "TRUE" if replace_all_instances else "FALSE"),
        ]
        if replace_occurrence is not None:
            param.append(("replaceOccurrence", str(replace_occurrence)))
        if current_variant_id is not None:
            param.append(("currentvariantid", str(current_variant_id)))
        if new_variant_id is not None:
            param.append(("newvariantid", str(new_variant_id)))
        cmd = AppCommand("REPLACE", fname, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdSaveSecondary(CadCommand):
    """
    SAVE_SECONDARY Command Wrapper
    """

    def __init__(
        self,
        fname,
        format,
        dst_filename,
        sheet_id=None,
        sheet_number=None,
        parameter=None,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a SAVE_SECONDARY command

        :param fname: string, source file name
        :param format: string, destination format
        :param dst_filename: string, destination file name
        :param sheet_id: string, id of the sheet to print
        :param sheet_number: int, sheet number to print
        :param parameter: dict with name/value pairs
        :param flags: Command execution flags
        """
        param = [("format", format), ("dstfilename", dst_filename)]
        if sheet_number is not None:
            param.append(("sheetnumber", str(sheet_number)))
        if sheet_id is not None:
            param.append(("sheetid", sheet_id))
        if parameter is not None:
            param.append(("parameter", json.dumps(parameter)))
        context_files = []
        cmd = AppCommand("SAVE_SECONDARY", fname, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdNewFrom(CadCommand):
    """
    NEW_FROM Command Wrapper
    """

    def __init__(self, file_list, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a NEW_FROM command

        :param file_list: List of tuples of (src, dst, isTopFile (Boolean))
        :param flags: Command execution flags
        """
        f_temp_list = []
        for t in file_list:
            val = "%s@%s@%s" % (t[0], t[1], "TRUE" if t[2] else "FALSE")
            f_temp_list.append(val)
        f_list_val = "@".join(f_temp_list)
        param = [("filelist", f_list_val)]
        cmd = AppCommand("NEW_FROM", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdAddComponent(CadCommand):
    """
    ADD_COMPONENT Command Wrapper
    """

    def __init__(
        self,
        fname,
        component_file,
        position,
        cad_id=None,
        variant_name=None,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct an ADD_COMPONENT command

        :param fname: string, file name of the assembly
        :param component_file: string, file name of the file to be inserted into the component
        :param position: cs.cadbase.wsutils.matrix.Matrix(4x4), Transformation matrix
        :param cad_id: string, Id/Name of Instance in CAD
        :param variant_name: string, optional Id of the variant
        :param flags: Command execution flags
        """
        pos_info = ";".join(convert_matrix(position))
        param = [("referencedfile", component_file), ("position", pos_info)]
        if cad_id is not None:
            param.append(("cadid", cad_id))
        if variant_name is not None:
            param.append(("variantname", variant_name))
        cmd = AppCommand("ADD_COMPONENT", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdPositionComponent(CadCommand):
    """
    POSITION_COMPONENT Command Wrapper
    """

    def __init__(self, fname, position, cad_id, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct an POSITION_COMPONENT command

        :param fname: string, file name of the assembly
        :param position: cs.cadbase.wsutils.matrix.Matrix(4x4), Transformation matrix
        :param cad_id: string, Id/Name of Instance in CAD
        :param flags: Command execution flags
        """
        pos_info = ";".join(convert_matrix(position))
        param = [("cadid", cad_id), ("position", pos_info)]
        cmd = AppCommand("POSITION_COMPONENT", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdDeleteComponent(CadCommand):
    """
    DELETE_COMPONENT Command Wrapper
    :param parent_file: string. Assembly filename
    :param occurrence_id: string: Occurrence to delete
    """

    def __init__(self, parent_file, occurrence_id, flags=CadCommand.DEFAULT_FLAGS):
        """
        Constructs a DELETE_COMPONENT command

        :param parent_file: string. Assembly filename
        :param occurrence_id: string: Occurrence to delete
        """
        param = [("cadid", occurrence_id)]
        cmd = AppCommand("DELETE_COMPONENT", parent_file, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdHideComponents(CadCommand):
    """
    HIDE_COMPONENTS Command Wrapper
    """

    def __init__(self, assembly_fname, hide_infos, flags=CadCommand.DEFAULT_FLAGS):
        """
        Constructs a HIDE_COMPONENTS command

        :param assembly_fname: string, filename of root assembly
        :param hide_infos: list of two element tuples.
            Element 1: list of occurrence_ids to address the component to hide or show.
            Element 2: Boolean: True: Show component, False: Hide component
        """
        json_hide = []
        for hi in hide_infos:
            json_hide.append({"path": hi[0], "mode": "SHOW" if hi[1] else "HIDE"})
        param = [("occurrences", json.dumps(json_hide))]
        cmd = AppCommand("HIDE_COMPONENTS", assembly_fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdRefresh(CadCommand):
    """
    REFRESH Command Wrapper
    """

    def __init__(self, file_list, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a REFRESH command

        :param file_list: List of unicode strings with absolute path names
        :param flags: Command execution flags
        """
        f_list = "|".join(file_list)
        param = [("filelist", f_list)]
        cmd = AppCommand("REFRESH", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdLoadFrame(CadCommand):
    """
    LOAD_FRAME Command Wrapper
    """

    def __init__(
        self,
        fname,
        sheet_id,
        frame_file,
        pdm_frame_id,
        frame_layer,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a LOAD_FRAME command

        :param fname: string, File name
        :param sheet_id: string, Id of the sheet where the frame has to be loaded
        :param frame_file: string, Frame file name
        :param pdm_frame_id: string, Id of the frame in the PDM system
        :param frame_layer: Name or number of drawing layer where the
                            frame should be inserted. Depends on CAD system.
        :param flags: Command execution flags
        """

        param = [
            ("sheetid", sheet_id),
            ("framefile", frame_file),
            ("pdmframeid", pdm_frame_id),
            ("framelayer", frame_layer),
        ]
        cmd = AppCommand("LOAD_FRAME", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdNOOP(CadCommand):
    """
    NOOP Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a NOOP command

        :param flags: Command execution flags
        """
        param = None
        cmd = AppCommand("NOOP", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdCreateFile(CadCommand):
    """
    CREATE_FILE Command Wrapper
    """

    def __init__(self, filename, filetype, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a CREATE_FILE command

        :param filename: string, Name of file to create
        :param filetype: string, "ASSEMBLY", "PART", "DRAWING" or CAD specific
        :param flags: Command execution flags
        """
        param = [("filename", filename), ("filetype", filetype)]
        cmd = AppCommand("CREATE_FILE", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdCreateFrom(CadCommand):
    """
    CREATE_FROM Command Wrapper
    """

    def __init__(
        self,
        srcfilename,
        srcfiletype,
        dstfilename=None,
        dstfiletype=None,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a CREATE_FROM command

        Command to create native file(s) including appinfo(s) from a third-party format

        :param srcfilename: string, file (full path) of the third-party format
        :param srcfiletype: string, type of the third-party format (e.g. "STEP")
        :param dstfilename: string, file (full path) of the CAD file to be created. If None,
                            filename results from srcfilename and the extension for dstfiletype.
        :param dstfiletype: string, type of the CAD file to be created
                            ("ASSEMBLY", "PART", "DRAWING" or CAD specific).
                            If None (supporting None is CAD specific), the type is determined
                            automatically. In this case dstfilename should also be None.
        :param flags: Command execution flags
        """
        param = [("srcfilename", srcfilename), ("srcfiletype", srcfiletype)]
        if dstfilename is not None:
            param.append(("dstfilename", dstfilename))
        if dstfiletype is not None:
            param.append(("dstfiletype", dstfiletype))
        cmd = AppCommand("CREATE_FROM", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)

    def get_created_filename(self):
        """
        :returns filename (full path) of created CAD file
        """
        ret = None
        cmd_result = self.app_command.getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                vl = data.get("created_file")
                if vl:
                    ret = vl[0]
        return ret


class CmdSaveState(CadCommand):
    """
    SAVE_STATE Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a SAVE_STATE command

        :param flags: Command execution flags
        """
        param = None
        cmd = AppCommand("SAVE_STATE", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdRestoreState(CadCommand):
    """
    RESTORE_STATE Command Wrapper
    """

    def __init__(self, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a RESTORE_STATE command

        :param flags: Command execution flags
        """
        param = None
        cmd = AppCommand("RESTORE_STATE", "", None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdSetParametric(CadCommand):
    # TODO: implementation must be reviewed, perhaps removed
    def __init__(self, fname, sml_info, dest_file, flags=None):
        """
        :Parameter:
            smlinfo: list of tuple(name, value, unit)
            destfile: unicode string
                      name of file to create or None if information should only
                      modify current file
        """
        smlinfo_list = []
        for s in sml_info:
            smlinfo_list.append("@".join(s))
        param = [("smlinfo", fname), ("variantfile", "@".join(smlinfo_list))]
        cmd = AppCommand("SET_PARAMETRIC", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdUpdateVariantTable(CadCommand):
    """
    UPDATE_CADVARIANT_TABLE Command Wrapper
    """

    def __init__(
        self, fname, variant_information, keep_local_new, flags=CadCommand.DEFAULT_FLAGS
    ):
        """
        Construct an UPDATE_CADVARIANT_TABLE command

        :param fname: File name
        :param variant_information: dict {rowid: dict {columid, value}}
                                    for new rows: rowid = __new__<number>
        :param keep_local_new: bool, do not delete local Entries if True
        :param flags: Command execution flags
        """
        param = [
            ("variants", json.dumps(variant_information)),
            ("keep_local_new", "True" if keep_local_new else "False"),
        ]
        cmd = AppCommand("UPDATE_CADVARIANT_TABLE", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)

    def get_update_result(self):
        """
        Retrieve update result

        :returns: result dict

        .. code-block:: python

            <given_id>: {"newid": <new id from cad>, for new records
                         "parameter": <dict with key/values for parameter>,
                         "errors": list(), list of errormessages
                        }

                        For deleted elements "parameter" does not exist.
                        newid exists only for new elements (with id __new__).
                        Not changed rows are not listed in the result
        """
        ret = None
        cmd_result = self.job.cmds[self.cmd_index].getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                vl = data.get("result")
                if vl:
                    ret = vl[0]
        return ret


class CmdRenameVariant(CadCommand):
    """
    RENAME_VARIANT Command Wrapper
    """

    def __init__(
        self,
        filename,
        context_files,
        current_variant_id,
        new_variant_id,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Generate the RENAME_VARIANT command

        :param filename: string, File name for variant
        :param context_files: List of context files that references files
        :param current_variant_id: string, Current name to change
        :param new_variant_id: string, new id/name for current name
        :param flags: Command execution flags
        """
        param = [("currentid", current_variant_id), ("newid", new_variant_id)]
        cmd = AppCommand("RENAME_VARIANT", filename, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdSetCadVariantTableDefinition(CadCommand):
    """
    SET_CADVARIANT_TABLE_DEF Command Wrapper
    """

    def __init__(self, filename, variant_table, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a SET_CADVARIANT_TABLE_DEF command

        :param filename: string, File name for variant
        :param variant_table: json compatible python structure

        .. code-block:: python

                             [{"id": <id>,
                               "name": <name>,
                               "type": <typ>,
                               "datatype": <Data type>
                               "defaultval": <default value> (Optional)}
                             ]

        :param flags: Command execution flags
        """
        param = [("varianttable", json.dumps(variant_table))]
        context_files = []
        cmd = AppCommand(
            "SET_CADVARIANT_TABLE_DEF", filename, context_files, param, flags, None
        )
        CadCommand.__init__(self, cmd)


class CmdGetCadVariantTableDefinition(CadCommand):
    """
    GET_CADVARIANT_TABLE_DEF Command Wrapper
    """

    def __init__(self, filename, flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a GET_CADVARIANT_TABLE_DEF command

        :param filename: string, File name for variant
        :param flags: Command execution flags
        """
        param = []
        context_files = []
        cmd = AppCommand(
            "GET_CADVARIANT_TABLE_DEF", filename, context_files, param, flags, None
        )
        CadCommand.__init__(self, cmd)

    def get_table_definition(self):
        """
        Retrieve the table definition

        :returns result list:

        .. code-block:: python

                             [{"id": <id>,
                               "name": <name>,
                               "type": <typ>,
                               "datatype": <Data type>
                               "defaultval": <default value> (Optional)}
                             ]

        """
        ret = None
        cmd_result = self.job.cmds[self.cmd_index].getResult()
        if cmd_result.isOk():
            data = cmd_result.data()
            if data is not None:
                vl = data.get("json")
                if vl:
                    ret = vl[0]
        return ret


class CmdFillBomPos(CadCommand):
    """
    FILL_BOMPOS Command Wrapper
    """

    def __init__(self, fname, bomposlist="", flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a FILL_BOMPOS command

        :param fname: string, File name
        :param bomposlist: string, with format described in D079872.
                                   like the pdminfo string
        :param flags: Command execution flags
        """
        param = [(appCommParams.bomposlist, bomposlist)]
        cmd = AppCommand("FILL_BOMPOS", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdChainedUpdateCommand(CadCommand):
    # TODO: must be fixed!
    def __init__(self, fname, flags, contextfiles):
        cmd = AppCommand("CHAINED_UPDATE_COMMAND", fname, contextfiles, [], flags, None)
        CadCommand.__init__(self, cmd)


class CmdSaveAppinfoModifiedInTransaction(CadCommand):
    # TODO: must be fixed!
    def __init__(self, flags, contextfiles):
        cmd = AppCommand(
            "SAVEAPPINFO_MODIFIED_IN_TRANSACTION", "", None, [], flags, None
        )
        CadCommand.__init__(self, cmd)


class CmdSet2DVisibility(CadCommand):
    """
    SET_2D_VISIBILITY Command Wrapper
    """

    def __init__(
        self,
        fname,
        displayed_layers,
        visible_layers,
        invisible_layers,
        element_filter,
        flags=CadCommand.DEFAULT_FLAGS,
    ):
        """
        Construct a SET_2D_VISIBILITY command

        :param fname: string, File name
        :param displayed_layers: list of strings. All layers are made visible if required.
                                                  All others layers will be explicitly suppressed.
                                                  This parameter has priority over visible_layers
                                                  and invisible_layers.
        :param visible_layers: list of strings.   All layers are made visible if required.
        :param invisible_layers: list of strings. All layers to be suppressed if necessary.
        :param element_filter: string    .        The parameter contains a filter name.
        :param flags: Command execution flags
        """

        param = []
        if displayed_layers is not None and (len(displayed_layers) > 0):
            param.append(("displayed_layers", json.dumps(displayed_layers)))
        if visible_layers is not None and (len(visible_layers) > 0):
            param.append(("visible_layers", json.dumps(visible_layers)))
        if invisible_layers is not None and (len(invisible_layers) > 0):
            param.append(("invisible_layers", json.dumps(invisible_layers)))
        if element_filter is not None and (not element_filter.isspace()):
            param.append(("element_filter", element_filter))

        cmd = AppCommand("SET_2D_VISIBILITY", fname, None, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdSetGeometryParameter(CadCommand):
    """
    SET_GEO_PARAMETER Command Wrapper
    """

    def __init__(
        self, fname, parameter_json, regenerate=False, flags=CadCommand.DEFAULT_FLAGS
    ):
        """
        Construct a SET_GEO_PARAMETER command

        :param fname: string, File name
        :param parameter_json: List of dicts with value type, value, name
        :param regenerate: boolean. Regenerate model after setting of variables
        :param flags: Command execution flags
        """
        param = []
        if parameter_json is not None:
            param.append(("parameterjson", json.dumps(parameter_json)))
        param.append(("regenerate", "TRUE" if regenerate else "FALSE"))
        context_files = []
        cmd = AppCommand("SET_GEO_PARAMETER", fname, context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CmdCallProgram(CadCommand):
    """
    CALL_PROGRAM Command Wrapper
    """

    def __init__(self,
                 program,
                 parameter_list,
                 timeout=None,
                 flags=CadCommand.DEFAULT_FLAGS):
        """
        Construct a CALL_PROGRAM command.

        CALL_PROGRAM commands at the beginning or at the end of a job sequence
        are excuted directly from the CadJob server. Commands between
        Cmds that are handeld by the CAD system are executed by the CAD system.
        If the exit_code of the called program is unequal 0 the command returns
        with an error.

        :param program: string path to executable file
        :param parameter_list: List of string parameters
        :param timeout: int > 0 timeout in seconds. Program will fail if timeout elapsed
        :param flags: Command execution flags
        """

        param = []
        param.append(("program", program))
        param.append(("parameter", json.dumps(parameter_list)))
        if timeout is not None:
            param.append(("timeout", str(timeout)))
        context_files = []
        cmd = AppCommandExecute("CALL_PROGRAM", "", context_files, param, flags, None)
        CadCommand.__init__(self, cmd)


class CadJob(object):
    """
    CAD Job implementation. Used to send one or multiple CAD commands to the
    CAD integration. Usually, this class is used seamlessly by JobRunner.
    An instance can be retrieved by JobRunner(...).create_job()
    """

    def __init__(self, job_runner):
        """
        :param job_runner: JobRunner used to execute the job
        """
        self.job_runner = job_runner
        self.cmds = []
        self.cad_cmds = []

    def append(self, *commands):
        """
        Append one or more commands to the job

        :param commands: Instance(s) of CadCommand
        """
        index = len(self.cmds)
        for command in commands:
            command.bind_to_job(self, index)
            index += 1
            self.cmds.append(command.app_command)
        self.cad_cmds.extend(commands)

    def execute(self, project_environment=None):
        """
        Execute all CAD commands from the job sequentially

        :returns result: Result
        """
        result = self.job_runner.execute_commands(self.cmds, project_environment)
        if result.isOk():
            job = result.getResultValue("job")
            job.getCommands()
        return result

    def serialize(self):
        """
        serializes all commands to a json compatible python structure (list of commands)
        :returns: list
        """
        return [cmd.serialize() for cmd in self.cad_cmds]

    def get_last_save_file(self, fname):
        """
        Get the real filename on disk for a given name of current JobExec-System

        :param fname: Str filename without version number
        :returns: Str or None. Standard implemention just returns fname
        """
        current_filename = None
        if self.job_runner and self.job_runner.job_exec:
            current_filename = self.job_runner.job_exec.get_last_save_file(fname)
        return current_filename


class JobRunner(object):
    """
    High level Job Runner interface for server side cad jobs and test environments.
    Instances of this class are to be used by the application to create and
    execute CAD jobs.
    Usually, a new job is instantiated by calling the create_job() method,
    and then instances of CadCommand are appended to the job. Afterwards,
    the job is executed and results can be retrieved.

    Usage example:

    .. code-block:: python

        from cs.catia.jobexec.catiajobexec import CatiaJobExec
        job = JobRunner("catiav5",
                        CatiaJobExec(),
                        r"c:\\temp\\jobs").create_job()
        cmd_close = CmdCloseAll()
        cmd_load = CmdLoad(r"c:\\tmp\\MyPart.CATPart")
        cmd_list = CmdListOfFiles()
        job.append(cmd_close, cmd_load, cmd_list)
        result = job.execute()
        if result.isOk():
            for fname in cmd_list.get_loaded_files().keys():
                print fname

    """

    def __init__(
        self,
        cad_system=None,
        job_exec=None,
        job_dir=None,
        project_env=None,
        test_env=None,
    ):
        """

        :param cad_system:  Name of the CAD system as String. If None, value
                            from test_env is used.
        :param job_exec:    Callable derived from JobExecBase, which receives an AppJob instance as
                            parameter. If None, value from test_env is used.
                            This class is provided by the cs.<cad> module for the CAD system.
                            Direct import from cs.<cad>.jobexec.<Classname> or by
                            retrieving the class by the entry point "cs.jobexec.plugins".
        :param job_dir:     Existing directory where the job is created as String.
                            If None, value from test_env is used.
        :param project_env: CAD project environment for jobs
        :param test_env:    Reference to a CADIntegrationTest instance or its
                            derivative or None. If None, cad_system, job_exec,
                            job_dir must be set.
        """
        if test_env is not None:
            self.cad_system = test_env.CAD_SYSTEM
            self.job_exec = test_env.JOB_EXEC
            self.cad_job_dir = test_env.get_job_dir()
        if cad_system is not None:
            self.cad_system = cad_system
        if job_exec is not None:
            self.job_exec = job_exec
        if job_dir is not None:
            self.cad_job_dir = job_dir
        self._project_env = project_env
        self.jobs = []
        self.encoding = "utf-8"

    def create_job(self):
        """
        Create a new CadJob

        :return: New instance of CadJob
        """
        job = CadJob(self)
        self.jobs.append(job)
        return job

    def set_encoding(self, encoding):
        """
        Set encoding for CAD communication

        :param encoding: Encoding as String
        """
        self.encoding = encoding

    def set_job_dir(self, job_dir):
        """
        Set job directory

        :param job_dir: Job directory as String
        """
        self.cad_job_dir = job_dir

    def serialize_jobs(self):
        """
        Serialize jobs in JSON format. Only allowed for test_env=None

        :return: string with serialized jobs
        """
        job_list = [job.serialize() for job in self.jobs]
        return json.dumps(
            {"project_env": self._project_env, "job_list": job_list, "version": "1.0"}
        )

    @staticmethod
    def _replace_path(s, cad_input_directory):
        if s is not None:
            return s.replace(CadCommand.CAD_ROOT_DIR, cad_input_directory)
        else:
            return s

    def _replace_path_in_list(self, in_list, cad_input_directory):
        if in_list:
            return [self._replace_path(p, cad_input_directory) for p in in_list]
        else:
            return in_list

    def _replace_path_in_parameters(self, in_list, cad_input_directory):
        if in_list:
            return [
                (p[0], self._replace_path(p[1], cad_input_directory)) for p in in_list
            ]
        else:
            return in_list

    def create_jobs_from_string(self, job_str, cad_input_directory):
        """
        Create jobs form a string containing serialized jobs in JSON format.
        Insert correct filename paths form cadInputDirectory (replaces the
        given cadcaommds.CAD_ROOTDIR directory by cad_input_directory)

        :param job_str: sring, serialized jobs in JSON format
        :param cad_input_directory: string, CAD input directory

        """
        p_struct = json.loads(job_str)
        if isinstance(p_struct, dict):
            version = p_struct.get("version")
            python_jobs = p_struct.get("job_list")
            if version in ["1.0"]:
                self._project_env = p_struct.get("project_env")
            self.jobs = []
            mymod = sys.modules.get("cs.cadbase.cadcommands")
            for job in python_jobs:
                cad_job = self.create_job()
                for cmd in job:
                    cname = cmd["classname"]
                    splittedName = cname.split(".")
                    mymod = sys.modules.get(".".join(splittedName[0:-1]))
                    cls = getattr(mymod, splittedName[-1])
                    app_cmd = AppCommand(
                        cmd["operation"],
                        self._replace_path(cmd["fname"], cad_input_directory),
                        self._replace_path_in_list(
                            cmd["context_files"], cad_input_directory
                        ),
                        self._replace_path_in_parameters(
                            cmd["parameter"], cad_input_directory
                        ),
                        cmd["flags"],
                        None,
                    )
                    cad_cmd = CadCommand(app_cmd)
                    cad_cmd.__class__ = cls
                    cad_job.append(cad_cmd)

    def execute_commands(self, cmds, project_env=None):
        """
        Execute CAD commands

        :param cmds: List of CadCommand instances
        :param project_env: Project environment (used to initialize an AppJob)
                            if not specified use job_runner value

        :return: Result
        """
        result = Result()
        if project_env is None:
            project_env = self._project_env

        command_names = []
        app_job = AppJob(project_env)
        pre_programs = []
        post_programs = []
        direct_cad = []
        for cmd in cmds:
            if isinstance(cmd, AppCommandExecute):
                pre_programs.append(cmd)
            else:
                break
        rev_cmds = copy.copy(cmds)
        rev_cmds.reverse()
        for cmd in rev_cmds:
            if isinstance(cmd, AppCommandExecute) and cmd not in pre_programs:
                post_programs.append(cmd)
            else:
                break
        post_programs.reverse()
        if post_programs:
            direct_cad = cmds[len(pre_programs):-len(post_programs)]
        else:
            direct_cad = cmds[len(pre_programs):]
        for cmd in direct_cad:
            app_job.append(cmd)
            command_names.append(cmd.name)
        command_names = removeDuplicatesOrdered(command_names)
        main_job_name = ", ".join(command_names)
        app_job.name = main_job_name
        for pre in pre_programs:
            result.extend(pre.execute_local())
        if direct_cad:
            result.extend(self.write_app_job(app_job))
            if result.isOk():
                result.extend(self.run_app_job(app_job))
        if result.isOk():
            result.setResultValue("job", app_job)
            for post in post_programs:
                result.extend(post.execute_local())
        return result

    def write_app_job(self, app_job):
        """
        Write an AppJob to file system

        :param app_job: AppJob
        :returns: Result
        """
        result = Result()
        app_job.writeToFs(
            self.cad_job_dir,
            self.cad_system,
            encoding=self.encoding,
            notificationPath=self.job_exec.get_notification_dir(),
        )
        return result

    def run_app_job(self, app_job):
        """
        Run an AppJob

        :param app_job: AppJob
        :returns: Result
        """
        rc = self.job_exec.call(app_job)
        if rc == 0:
            result = app_job.wait(None)
        else:
            result = Result(
                ResKind.kResError, ("cadcommands", "Starting CAD failed: %s" % str(rc))
            )
        return result
