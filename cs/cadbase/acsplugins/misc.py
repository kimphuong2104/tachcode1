#!/usr/bin/env python
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import json
import os
import shutil
import six
import base64
import string
from cs.cadbase import appinfohandler
from cs.cadbase.wsutils.resultmessage import ResKind
from cs.cadbase import cadcommands

# DCS job log
LOG = None


class CadJobException(Exception):
    pass


def set_joblog(log):
    """
    init dcs job log

    :param log: dcs job log to use for logging with joblog()
    """
    global LOG
    LOG = log


def joblog(msg):
    """
    write dcs job log in functions not having job object

    :param msg: message (without newline) to log
    """
    if LOG is not None:
        LOG("%s\n" % msg)


def get_model_and_src_file(job):
    """
    get acs job model and src_file

    :param job: acs job
    :return: model and src_file (raised CadJobException for errors)
    """
    model = job.get_document()
    if model is None:
        raise CadJobException("Could not get document")

    src_file = job.get_file()
    if src_file is None:
        try:
            src_file = model.getPrimaryFile()
            job.log("Use primary file\n")
        except Exception as e:
            job.log("%s\n" % e)
    if src_file is None:
        file_name = model.getExternalFilename()
        job.log("Use file with name '%s'\n" % file_name)
        srcFilesByName = model.Files.KeywordQuery(cdbf_name=file_name)
        if srcFilesByName:
            src_file = srcFilesByName[0]
    if src_file is None:
        raise CadJobException("Could not get src file")

    return model, src_file


def get_job_parameter(job_params, param_name, wanted_type, default_value=None):
    """
    get job parameter value, option to have string instead of wanted_type in job_params

    :param job_params: job parameters
    :param param_name: name of parameter to get
    :param wanted_type: use json.loads if param value is string but wanted_type isn't string
                        (needed using testplg)
    :param default_value: value if parameter does not exist
    :return: parameter value
    """
    try:
        result = job_params[param_name]
    except (KeyError, TypeError):
        return default_value

    if not issubclass(wanted_type, six.string_types) and isinstance(result, six.string_types):
        if wanted_type is bool:
            return json.loads(result.lower())
        return json.loads(result)
    return result


def get_target_list(job, setup, job_params):
    """
    get list of targets supporting a multi_target job
    target is a dict with keys
      "dstformat": job.target or target from multi_target
      "parameter": parameter set by multi_target call
      "int_dst_files": must be added by acscadjob.create_cad_job()
      "int_cmd_flags": can be added by acscadjob.create_cad_job()

    :param job: acs job
    :param setup: acs setup
    :param job_params: job parameters

    :return: list of target dict (raised CadJobException for errors)
    """
    if job.target.lower() != "multi_target":
        return [{"dstformat": job.target}]

    if job_params is None:
        raise CadJobException("no paramDict for 'multi_target'")
    tmp_result = get_job_parameter(job_params, "MULTI_TARGET", list)
    if tmp_result is None:
        raise CadJobException("no 'MULTI_TARGET' given in job paramDict")
    if len(tmp_result) < 1:
        raise CadJobException("empty list 'MULTI_TARGET' given in job paramDict")

    result = []
    for target in tmp_result:
        try:
            target_format = target["dstformat"]
            if target_format not in setup["Conversions"][job.source]:
                raise CadJobException("'MULTI_TARGET' dstformat not supported: %s" % target_format)
            if target_format in setup["nativeTargets"]:
                result.insert(0, target)
            else:
                result.append(target)
        except (KeyError, TypeError) as e:
            raise CadJobException("'MULTI_TARGET' exception: %s" % e)

    return result


def get_file_type(job, model):
    """
    get file type

    :param job: acs job
    :param model: acs job document
    :return: file type of job or primary file
    """
    try:
        if job.get_file() is not None:
            return job.get_file().cdbf_type
        return model.getPrimaryFile().cdbf_type
    except Exception:
        raise CadJobException("Couldn't get primary file from "
                              "document. No or multiple primary"
                              " files defined in document.")


def get_appinfo_mode(work_file, exception_no_appinfo=True):
    """
    check app info mode (in work dir or in sub dir .wsm/.info)

    NOTE: Call is allowed only before calling execute_cad_job()!

    :param work_file: src filename with full path
    :param exception_no_appinfo: if True raise exception if result isn't 1 or 2

    :return app info mode (0 no appinfo, 1 = in workdir, 2 = in .wsm/.info),
            appinfo_fname (filename with path for dcs depending on mode),
            appinfo_subdir (filename with path written from integration)
    """
    retVal = 0

    work_file_dir = os.path.dirname(work_file)
    work_file_base = os.path.basename(work_file)
    appinfo_fname = work_file + ".appinfo"
    appinfo_subdir = os.path.join(work_file_dir, ".wsm", ".info",
                                  work_file_base + ".appinfo")

    if os.path.isfile(appinfo_subdir):
        appinfo_fname = appinfo_subdir
        retVal = 2
    elif os.path.isfile(appinfo_fname):
        retVal = 1
    elif exception_no_appinfo:
        raise CadJobException("Couldn't find the appinfo for the souce file: %s" % work_file)

    return retVal, appinfo_fname, appinfo_subdir


def execute_cad_job(cad_job):
    """
    execute conversion for all targets
    raised CadJobException if one command with flag StopOnError failed

    :param cad_job: cad job to be executed
    """
    res = cad_job.execute()

    if res.isOk():
        return get_job_result_msg(res, ResKind.kResInfo)

    errmsg = get_job_result_msg(res, ResKind.kResError)
    if errmsg == "":
        errmsg = "unknown error"

    raise CadJobException(errmsg)


def get_job_result_msg(result, result_kind):
    msg = ""
    for resmsg in result.getResultMsgs():
        if resmsg.getMsgType() == result_kind:
            if (msg != ""):
                msg += "\n"
            msg += resmsg.translateArgsCDB()
    return msg


def check_converted_files(targets, work_file, appinfo_fname, appinfo_subdir,
                          sandbox_dir, setup, job_result_info):
    """
    check and normalize conversion

    :param targets: list of targets to be converted
    :param work_file: src filename with full path
    :param appinfo_fname: appinfo filename with path for dcs (depending on mode)
    :param appinfo_subdir appinfo filename with path written from integration
    :param sandbox_dir: sandbox directory
    :param job_result_info: result message for commands without flag StopOnError
    :param setup: acs setup
    """

    # normilize appinfo
    if targets[0]["dstformat"] in setup["nativeTargets"]:
        if appinfo_fname != appinfo_subdir:
            shutil.copy2(appinfo_subdir, appinfo_fname)
        appinfohandler.abs_path_to_rel_path(appinfo_fname, sandbox_dir)

    # check optional conversions (commands without flag StopOnError)
    # -> one of the dst_files has to be converted
    # (catia ps and pdf not knowing the multipage CAD setting)
    for target in targets:
        try:
            flags = target["int_cmd_flags"]
            if cadcommands.processingFlags.StopOnError not in flags:
                dst_file_ok = []
                for dst_file in target["int_dst_files"]:
                    if os.path.isfile(dst_file):
                        dst_file_ok.append(dst_file)
                if len(dst_file_ok) < 1:
                    if job_result_info == "":
                        job_result_info = "unknown error converting %s" % work_file
                    raise CadJobException(job_result_info)
                target["int_dst_files"] = dst_file_ok
        except KeyError:
            break


def transfer_converted_files(targets, job, model, src_file, setup):
    """
    transfers converted files into cdb

    :param targets: list of targets to be transfered
    :param job: acs job
    :param model: acs job document
    :param src_file: acs src file object
    :param setup: acs setup
    """
    for target in targets:
        converted_files = target["int_dst_files"]
        target_format = target["dstformat"]
        if target_format in setup["nativeTargets"]:
            # for native target the appinfo must exist
            if len(converted_files) != 2:
                raise CadJobException(
                    "error in converting native or 3D, wrong number of files returned: %s"
                    % len(converted_files))

            for fname in converted_files:
                if os.path.splitext(fname)[1] == u".appinfo":
                    job.store_file(model, fname, "Appinfo", replace_original=True)
                else:
                    result_type = setup["ResultTypes"].get(target_format, target_format)
                    job.store_file(src_file, fname, result_type, replace_original=True)
        else:
            if len(converted_files) < 1:
                raise CadJobException("error, no files converted")

            result_type = setup["ResultTypes"].get(target_format, target_format)

            try:
                # suffix from SuffixMap
                suffix = setup["SuffixMap"][target_format]
            except KeyError:
                try:
                    # suffix from Format2Suffix (AutoCAD / Inventor)
                    suffix = setup["Format2Suffix"][target_format]
                except KeyError:
                    # suffix is target_format (default / CATIA V5)
                    suffix = target_format
            if not suffix.startswith("."):
                suffix = "." + suffix

            for fname in converted_files:
                convFile = os.path.splitext(fname)[0] + suffix
                if convFile != fname:
                    shutil.copy2(fname, convFile)

                if src_file.cdbf_object_id != model.cdb_object_id:
                    attach_obj = model
                else:
                    attach_obj = src_file

                job.store_file(attach_obj, convFile, result_type)


def check_duplicate_files(targets, basename_only=False):
    """
    check for duplicate target files

    :param targets: list of targets
    :param basename_only: checks duplicates with path or not
    """
    all_files = set()
    for target in targets:
        for file_name in target["int_dst_files"]:
            len1 = len(all_files)
            if basename_only is True:
                file_name = os.path.basename(file_name)
            all_files.add(file_name)
            if len(all_files) == len1:
                raise CadJobException("duplicate dst file name found: %s" % file_name)


def get_param_value(param_name,
                    target,
                    job_params, job_params_wanted_type=six.text_type,
                    setup_name=None, setup=None,
                    default_value=None):
    """
    get parameter value from target params, job params or setup
    (with type conversion getting job params, needed if not string and using testplg)

    :param param_name: name of parameter to get
    :param target: target dict (or None if not wanted)
    :param job_params: job parameter dict (or None if not wanted)
    :param job_params_wanted_type: use json.loads if param value is string but wanted type
                                   isn't string (needed using testplg)
    :param setup_name: name of parameter to get in setup
                       if None, param_name is used for name in setup
    :param setup: (env) setting setup dict (or None if not wanted)
    :param default_value: value if parameter does not exist
    :return: parameter value
    """
    # first use target parameter dict
    if target is not None:
        try:
            return target["parameter"][param_name]
        except (KeyError, TypeError):
            pass

    # use job_params dict
    if job_params is not None:
        result = get_job_parameter(job_params, param_name, job_params_wanted_type, None)
        if result is not None:
            return result

    # use setup dict
    if setup is not None:
        try:
            if setup_name is None:
                return setup[param_name]
            else:
                return setup[setup_name]
        except KeyError:
            pass

    # default
    return default_value


def get_bool(param_value, default_value=False):
    """
    get bool value of a parameter value (e.g. get with get_param_value())
    """
    if param_value is not None:
        if isinstance(param_value, bool):
            return param_value
        if isinstance(param_value, six.string_types):
            return param_value.upper() in ["TRUE", "WAHR", "YES", "JA", "ON", "AN", "1"]
    return default_value


def contains_format(targets, formats):
    """
    determine if targets contains a format

    :param targets: list of target dicts
    :param formats: list of format strings
    :return: True if targets contains one of the formats
    """
    for target in targets:
        try:
            if target["dstformat"] in formats:
                return True
        except KeyError:
            pass
    return False


def get_valid_filename(s):
    """
    replace invalid chars for a filename to "_"

    :param s: string, filename or part of a filename without path
    :return: valid string for a filename
    """
    chars_to_replace = ["\\", "/", ":", "*", "?", "<", ">", "|"]
    normalized_name = six.text_type(s)
    for r in chars_to_replace:
        normalized_name = string.replace(normalized_name, six.text_type(r), u"_")
    return normalized_name


def add_parameter(setup, setup_name, parameter, param_name, value_type="str"):
    """
    add parameter in parameter dict with value from setup

    :param setup: (env) setting setup dict
    :param setup_name: name of parameter to get in setup
    :param parameter: parameter dict
    :param param_name: name of parameter to set in parameter
    :param value_type: parameter value type
    """
    env_value = setup.get(setup_name)
    if env_value:
        if value_type == "int":
            parameter[param_name] = int(env_value)
        elif value_type == "bool":
            parameter[param_name] = env_value.upper() == "TRUE"
        else:
            parameter[param_name] = env_value


def add_parameter_config(setup, config, parameter):
    """
    add configuration file parameter in parameter dict

    :param setup: (env) setting setup dict
    :param config: { "<environment for configuration file>" : "<configuration type>" }
    :param parameter: parameter dict
    :return: bool, one configuration was set
    """
    p = {}
    for env_name, config_type in config.items():
        env_value = setup.get(env_name)
        if env_value:
            if os.path.isfile(env_value):
                with open(env_value, "rb") as f:
                    x = base64.b64encode(f.read())
                p[config_type] = x
            else:
                joblog("WARNING: not existing config file: %s" % env_value)
    if len(p) > 0:
        parameter["mainconfigfilecontent"] = p
        return True
    return False


def add_cmd_2D_visibility(cad_job, target, job_params, setup, work_file, flags):
    """
    add CmdSet2DVisibility to cad_job if CONTROL_LAYERS is set in target, job_params or setup

    :param cad_job: cad job where to add command
    :param target: target dict (or None if not wanted)
    :param job_params: job parameter dict (or None if not wanted)
    :param setup: (env) setting setup dict (or None if not wanted)
    :param work_file: src filename with full path
    :param flags: command flags
    """
    if get_bool(get_param_value("CONTROL_LAYERS", target, job_params, six.text_type,
                                "CADDOK_ACS_PARAM_CONTROL_LAYERS", setup)):
        displayed_layers = get_param_value("DISPLAYED_LAYERS", target, job_params, six.text_type,
                                           "CADDOK_ACS_PARAM_DISPLAYED_LAYERS", setup, "")
        invisible_layers = get_param_value("INVISIBLE_LAYERS", target, job_params, six.text_type,
                                           "CADDOK_ACS_PARAM_INVISIBLE_LAYERS", setup, "")
        visible_layers = get_param_value("VISIBLE_LAYERS", target, job_params, six.text_type,
                                         "CADDOK_ACS_PARAM_VISIBLE_LAYERS", setup, "")
        displayed_layers_list = None
        visible_layers_list = None
        invisible_layers_list = None
        if displayed_layers != "":
            displayed_layers_list = displayed_layers.split(",")
        if visible_layers != "":
            visible_layers_list = visible_layers.split(",")
        if invisible_layers != "":
            invisible_layers_list = invisible_layers.split(",")
        if displayed_layers_list is None \
                and visible_layers_list is None \
                and invisible_layers_list is None:
            joblog("WARNING: CONTROL_LAYERS activated but no layers defined")
        else:
            cmd_Set2DVisibility = cadcommands.CmdSet2DVisibility(
                work_file, displayed_layers_list, visible_layers_list, invisible_layers_list,
                element_filter="", flags=flags)
            cad_job.append(cmd_Set2DVisibility)
