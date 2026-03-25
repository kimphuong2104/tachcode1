#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
HOOPS Converter plug-in for the ACS/DCS
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import shutil
import sys
import time

from cdb import util
from cdb import sig
from cdb.acs import acslib, cadacsutils
from cdb.mq import Job

from cdb.objects import Rule
from cdb.objects.cdb_file import CDB_File
from cdb.objects.pdd.Files import DuplicateFilenameError, Sandbox

from cs.threed.hoops import markup
from cs.threed.hoops.utils import chunks, MONOLITHIC_FILETYPES
from cs.threed.hoops.converter import CSCONVERT_NAME, JSON_FILE_FORMAT, PRC_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT, PDF_FILE_FORMAT
from cs.threed.hoops.converter import configurations
from cs.threed.hoops.converter import csconvert
from cs.threed.hoops.converter import create_dependent_jobs
from cs.threed.hoops.converter import hoops
from cs.threed.hoops.converter import utils
from cs.threed.hoops.converter.proe import generate_xas_and_xpr_files, is_proe
STRUCTURE_CHECKED_OUT = sig.signal()

# these are valid parameters for the HOOPS converter
# but don't expect an output path as the value
# so no file must be checked in for these params
HOOPS_OUTPUT_PARAMS_BLACKLIST = ["output_png_resolution"]

# These parameters are mainly needed for the mapping in the cockpit
# and are therefore obsolete for the monolthic formats.
# Skipping these can increase performance depending on the model size.
HOOPS_PARAMS_MONOLITHIC_BLACKLIST = ["export_exchange_ids", "output_xml_assemblytree"]

class MissingResultException(Exception):
    pass

class UnsupportedFiletypeException(Exception):
    pass

log = acslib.log

cPlgInRevision = "$Revision$"[11:-2]
cPlgInLocation = os.path.dirname(__file__)
cPlgInName = "hoops"
cSetup = None
Conversions = {}

BLACKLIST_NOT_INITIALIZED = -1
BLACKLIST_RULE = "3DConnect: Blacklist"
blacklist = BLACKLIST_NOT_INITIALIZED


def initPlgIn():
    global cSetup, Conversions
    log("Initializing plug-in %s\n" % cPlgInName)
    cSetup = acslib.getPluginsSetup(cPlgInName)
    Conversions = cSetup["Conversions"]

    return True


def testPlgIn():
    log("Testing configuration of plug-in %s\n" % cPlgInName)
    try:
        hoops.Converter.test()
        log("Hoops converter found: %s\n" % hoops.Converter.execPath)
        csconvert.Converter.test()
        log("CSConvert found: %s\n" % csconvert.Converter.execPath)
    except Exception as e:
        log(str(e))

    return True


def get_identical_jobs(new_job, fobjs):
    from cdb import acs
    acsqueue = acs.getQueue()

    jobs = []
    for chunked_fobjs in chunks(fobjs):
        jobs.extend(job for job in acsqueue.query_jobs(
            "src_object_id IN (%s)" % (", ".join(["'%s'" % fobj.cdb_object_id for fobj in chunked_fobjs])),
            "cdbmq_state='%s'" % Job.Processing,
            "plugin='%s'" % new_job.plugin if hasattr(new_job, 'plugin') else None,
            "source='%s'" % new_job.source if hasattr(new_job, 'source') else None,
            "target='%s'" % new_job.target if hasattr(new_job, 'target') else None,
        ))
    return jobs


def HandleJob(job):
    global log, cSetup, blacklist
    log = job.log
    testPlgIn()

    if blacklist == BLACKLIST_NOT_INITIALIZED:
        blacklist = Rule.ByKeys(BLACKLIST_RULE)

    if not Conversions.get(job.source, None):
        raise Exception(
            "No implementation for source format '%s'" % job.source)

    model = job.get_document()

    if model is None:
        job.log("No model found.\n")
        return 1

    if blacklist is not None and blacklist.match(model):
        # If the blacklist matches the job should be terminated without failing
        return 0

    all_configs = configurations.get_configurations()

    if job.target == "threed_batch":
        return create_dependent_jobs(job, all_configs)

    if len(get_identical_jobs(job, model.Files)) > 1:
        time.sleep(cSetup.get("IdenticalJobRetryDelay", 5))
        _retry_job(job)
        return 0

    params = utils.get_job_params(job.id())

    filetypes = params["filetypes"] if params and "filetypes" in params.keys() else []

    if filetypes:
        configs_to_use = [conf for conf in all_configs if conf.ft_name in filetypes]
    else:
        configs_to_use = [conf for conf in all_configs if conf.auto_convert]

    invalidate_markup = "skip_markup_inval" not in params.keys() or not params["skip_markup_inval"] if params else True

    return run_document_conversion(job, model, configs_to_use, log, invalidate_markup)


def run_document_conversion(job, model, configs, log, invalidate_markup=True):
    """
    Converts a document with the converter set by the configuration.

    :param job: The ACS job
    :param model: The source CAD-document
    :param configs: The list of configurations for the conversion to be run with
    :param log: The log function
    """
    wsp = job.getWorkspace()
    log("Conversion workspace: %s\n" % wsp)

    src_fobj = model.getPrimaryFile()

    # delete existing files for 3d viewing format prior to conversion
    if SCZ_FILE_FORMAT in [conf.ft_name for conf in configs]:
        del_ftypes = [JSON_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT]
        for f in model.Files.KeywordQuery(cdbf_type=del_ftypes, cdbf_derived_from=src_fobj.cdb_object_id):
            f.delete_file()

    if wsp:
        _empty_dir(wsp)

    with Sandbox(wsp) as sb:
        src_fname = sb.pathname(src_fobj)
        src_ftype_monolithic = False
        all_filenames = []

        # only checkout a single file for monolithic formats
        if src_fobj.cdbf_type in MONOLITHIC_FILETYPES:
            src_ftype_monolithic = True
            try:
                src_fname = sb.checkout(src_fobj)[0]
            except DuplicateFilenameError as ex:
                log(f"Duplicate filename: {ex}")
                raise
        else:
            try:
                accept_duplicates = cSetup.get("ACCEPT_DUPLICATE_FILENAMES", False)
                filenames_by_doc = cadacsutils.checkoutStructure(sb, model, ignoreDuplicates=accept_duplicates)
                for filenames in filenames_by_doc.values():
                    all_filenames.extend(filenames)
            except DuplicateFilenameError as ex:
                log(f"Duplicate filename in model structure: {ex}")
                raise

        # generate Creo xpr and xas files, if the corresponding parameter is set.
        if is_proe(src_fobj) and cSetup.get("ProeGenerateAcceleratorFiles", False):
            proe_job_result = generate_xas_and_xpr_files(wsp, src_fname, all_filenames, log)
            if not proe_job_result and cSetup.get("ProeAcceleratorFilesMandatory", True):
                return 1

        ret = 0
        hoops_configs = []
        csconvert_configs = []

        for conf in configs:
            if conf.converter == CSCONVERT_NAME:
                csconvert_configs.append(conf)
            else:
                hoops_configs.append(conf)

        if hoops_configs:
            ret = run_hoops_conversion(model, hoops_configs, src_fname, invalidate_markup, src_ftype_monolithic)
            if ret != 0:
                return ret

        if csconvert_configs:
            sig.emit(STRUCTURE_CHECKED_OUT)(sb.location, src_fobj, job, cSetup)
            ret = run_csconvert_conversion(model, csconvert_configs, src_fname, wsp, invalidate_markup)
            if ret != 0:
                return ret

        # remove params if job succeeds
        util.text_write("threed_hoops_job_params", ['job_id'], [job.id()], "")
        return ret


def run_hoops_conversion(model, configs, src_fname, invalidate_markup, src_ftype_monolithic=False, service_mode=True):

    source_filepath = os.path.abspath(src_fname)
    src_basename = os.path.splitext(source_filepath)[0]

    def log_fn(msg, log_level):
        if log_level == hoops.LOG_ERROR:
            log("ERROR: %s" % (msg,))
        elif log_level == hoops.LOG_WARN:
            log("WARNING: %s" % (msg,))
        elif log_level == hoops.LOG_INFO:
            log("%s" % (msg,))

    for conf in configs:
        params = [(param.name, param.param_value) for param in conf.Parameters if param.converter == conf.converter]

        final_params = []
        conversion_results = []
        xml_path = None
        sc_full_path = None

        # substitute the basename for all occurences and get the updated path and filetype
        for p in params:

            param_name = p[0]
            new_val = p[1]

            if src_ftype_monolithic and param_name in HOOPS_PARAMS_MONOLITHIC_BLACKLIST:
                continue

            # this should only target converter params that expect an output path as the value
            if "output" in param_name and param_name not in HOOPS_OUTPUT_PARAMS_BLACKLIST:
                new_val, suffix = _apply_basename_substitution(p[1], src_basename)
                basename = os.path.splitext(new_val)[0]

                if param_name == "output_xml_assemblytree":
                    xml_path = new_val
                    conversion_results.append({"basename": basename, "suffix": suffix, "filetype": XML_FILE_FORMAT})

                else:

                    # drop suffix for stream cache output param value
                    # as it is automatically added by the conversion
                    # also trim whitespaces and add back later
                    if param_name == "output_sc":
                        sc_full_path = new_val
                        new_val = os.path.splitext(new_val)[0].strip()
                        basename = new_val

                    conversion_results.append({"basename": basename, "suffix": suffix, "filetype": conf.ft_name})

            final_params.append((param_name, new_val))

        converter = hoops.Converter(
            input_path=source_filepath,
            params=final_params,
            timeout=cSetup.get("Timeout", 0),
            log_fn=log_fn,
            force_xvfb=cSetup.get("ForceXvfb", False),
            service_mode=service_mode
        )

        converter.execute()

        hidden_result = False

        if conf.ft_name == SCZ_FILE_FORMAT:

            if xml_path is not None:
                json_path = utils.convert_xml_to_json(xml_path)
                json_basename, json_suffix = os.path.splitext(json_path)
                conversion_results.append({"basename": json_basename, "suffix": json_suffix, "filetype": JSON_FILE_FORMAT})

            if invalidate_markup:
                markup.invalidate_markup_views(model)
                markup.invalidate_measurements(model)

            hidden_result = True

        for conv_res in conversion_results:
            converted_path = "%s%s" % (conv_res["basename"], conv_res["suffix"])

            if conv_res["filetype"] == SCZ_FILE_FORMAT:

                if not sc_full_path:
                    log("Exception while renaming: SC path is not defined.")
                    return 1

                try:
                    os.rename(converted_path, sc_full_path)
                except OSError as err:
                    log("Exception while renaming %s: %s" % (converted_path, err))
                    return 1

                converted_path = sc_full_path

            _checkin_conversion_result(model, converted_path, conv_res["filetype"], hidden=hidden_result)

    return 0


def run_csconvert_conversion(model, configs, src_fname, wsp, invalidate_markup, service_mode=True):

    src_basename = os.path.splitext(src_fname)[0]

    def log_fn(msg, log_level):
        if log_level == csconvert.LOG_ERROR:
            log("ERROR: %s" % (msg,))
        elif log_level == csconvert.LOG_WARN:
            log("WARNING: %s" % (msg,))
        elif log_level == csconvert.LOG_INFO:
            log("%s" % (msg,))

    converter = csconvert.Converter(
        wsp_path=wsp,
        models=[model],
        timeout=cSetup.get("Timeout", 0),
        log_fn=log_fn,
        force_xvfb=cSetup.get("ForceXvfb", False),
        service_mode=service_mode
    )

    converter.new_conversion(
        src_fname,
        substitutions=_make_substitutions(wsp, src_basename),
        params=cSetup.get("ConverterImportParams", {})
    )

    configs_by_ft_name = {conf.ft_name: conf for conf in configs}
    scz_config = configs_by_ft_name[SCZ_FILE_FORMAT] if SCZ_FILE_FORMAT in configs_by_ft_name.keys() else None
    temp_prc_fname = None
    prc_checkin_name = None

    if scz_config:
        prc_params = {}

        # use global prc config params if they exist
        all_configs = configurations.get_configurations()
        prc_configs = [conf for conf in all_configs if conf.ft_name == PRC_FILE_FORMAT]
        if prc_configs:
            prc_params = configurations.get_csconvert_config_params(prc_configs[0])

        # force basic filename to prevent interference
        # with substitution in hoops conversion later
        temp_prc_fname = "%s%s" % (src_basename, ".prc")
        prc_params["output"] = temp_prc_fname

        converter.add_task("prc", prc_params)

    conversion_results = []

    for conf in configs:
        params = configurations.get_csconvert_config_params(conf)
        if conf.ft_name == PDF_FILE_FORMAT:
            params["attributes_callback"] = cSetup.get("pdf_additional_attributes", None)

        for key, val in params.items():
            if key == "output":
                new_val, suffix = _apply_basename_substitution(val, src_basename)
                conversion_results.append({"basename": os.path.splitext(new_val)[0], "suffix": suffix, "filetype": conf.ft_name})

                # only add prc task if not already done
                if conf.ft_name == PRC_FILE_FORMAT and scz_config:
                    prc_checkin_name = new_val
                    continue

                target_format_from_suffix = suffix.replace(".", "")

                converter.add_task(target_format_from_suffix, params)

    converter.run(delete_taskfile=False)

    if scz_config:
        if not temp_prc_fname or not os.path.exists(temp_prc_fname):
            log("PRC file does not exist: %s" % temp_prc_fname)
            return 1

        ret = run_hoops_conversion(model, [scz_config], temp_prc_fname, invalidate_markup)
        if ret != 0:
            return ret

        # rename temp prc to checkin as regular prc result
        if prc_checkin_name:
            try:
                os.rename(temp_prc_fname, prc_checkin_name)
            except OSError as err:
                log("Exception while renaming %s: %s" % (temp_prc_fname, err))
                return 1

    for conv_res in conversion_results:
        converted_path = "%s%s" % (conv_res["basename"], conv_res["suffix"])
        _checkin_conversion_result(model, converted_path, conv_res["filetype"])

    return 0


def _apply_basename_substitution(val, filepath):
    suffix = ""

    if isinstance(val, str):
        suffix = os.path.splitext(val)[1]
        val = utils.get_substituted_src_basename(val, filepath)

    return val, suffix


def _checkin_conversion_result(model, file_path, cdbf_type, hidden=False):

    if not os.path.exists(file_path):
        raise MissingResultException(
            "Missing result of conversion: %s\n" % file_path)

    log("Checking in conversion result: %s\n" % file_path)

    additional_args = {
        "cdbf_hidden": 1 if hidden else 0,
        "cdbf_type": cdbf_type,
        "cdbf_derived_from": model.getPrimaryFile().cdb_object_id
    }
    existing_file = False

    primary_file_ids = set()
    for f in model.Files:
        if f.cdbf_primary == "1":
            primary_file_ids.add(f.cdb_object_id)

    fname = os.path.basename(file_path)
    for f in model.Files.KeywordQuery(cdbf_type=cdbf_type, cdbf_derived_from=primary_file_ids, cdbf_name=fname):
        f.checkin_file(file_path, additional_args=additional_args)
        existing_file = True

    if not existing_file:
        CDB_File.NewFromFile(
            model.cdb_object_id,
            file_path,
            primary=False,
            additional_args=additional_args
        )


def _make_substitutions(wsp, src_basename):
    if not sys.platform == "win32":
        # Workaround: On linux the converter gets executed with its own
        # working directory set, so we have to use full output paths
        src_basename = os.path.join(wsp, src_basename)
    return {
        "$(WORKSPACE)": wsp,
        "$(SRC_BASENAME)": src_basename,
    }


def _retry_job(job):
    current_retries = _get_no_of_retries(job)
    job.record.copy(
        cdbmq_id=util.nextval("acs"),
        cdbmq_state=Job.Waiting,
        cdbmq_ftext=_get_job_retry_ftext(job, current_retries + 1)
    )


def _get_job_retry_ftext(job, retries):
    return "Retried from job %d. Number of retries: %d" % (job.cdbmq_id, retries)


def _get_no_of_retries(job):
    """
    Parses the error message of a job and tries to extract the number of retries from it.
    If any error happens during parsed, this function always returns 0, so that the job will retried.
    """
    if job.cdbmq_ftext is None or job.cdbmq_ftext == "":
        return 0
    split = job.cdbmq_ftext.split(": ")
    if len(split) != 2:
        return 0
    try:
        return int(split[1])
    except ValueError:
        return 0

def _empty_dir(dirname):

    def _remove_path(p, retries=10):

        def _remove_file_or_dir(fod):
            if os.path.isdir(fod):
                shutil.rmtree(fod)
            else:
                os.remove(fod)

        try:
            _remove_file_or_dir(p)
        except OSError as e:
            if retries == 0:
                log("Error while cleaning up workspace directory: %s\n" % e)

        if os.path.exists(os.path.abspath(p)) and retries > 0:
            time.sleep(0.1)
            _remove_path(p, retries - 1)

    for p in os.listdir(dirname):
        _remove_path(p)
