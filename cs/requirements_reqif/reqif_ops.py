# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import datetime
import logging
import os
import tempfile
import xml

from cdb import CADDOK, constants, sig, ue, util
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cdb.platform.mom import increase_eviction_queue_limit
from cdb.wsgi.util import jail_filename
from cdbwrapc import getFileTypeByFilename
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.classes import (RQMExportProcessRun, RQMImportProcessRun,
                                     RQMProtocol, RQMProtocolLogging)
from cs.requirements.document_export import DocumentExportTools
from cs.requirements.rqm_utils import statement_count
from cs.requirements_reqif import ReqIFProfile
from cs.requirements_reqif.exceptions import ReqIFInterfaceError

LOG = logging.getLogger(__name__)


@sig.connect(RQMSpecification, "cdbrqm_reqif_export", "pre_mask")
def cdbrqm_reqif_export_prepare_mask(_, ctx):
    profile = None
    user_last_profile = util.PersonalSettings().getValueOrDefault("cs.requirements_reqif",
                                                                  "reqif_profile",
                                                                  None)
    user_last_exportpath = util.PersonalSettings().getValueOrDefault("cs.requirements_reqif",
                                                                     "export_path",
                                                                     None)
    if user_last_profile is not None:
        profile = user_last_profile
    elif ReqIFProfile.get_default() is not None:
        profile = ReqIFProfile.get_default().cdb_object_id
    if profile is not None:
        ctx.set("reqif_profile", profile)

    if user_last_exportpath is not None:
        ctx.set("export_path", user_last_exportpath)


@sig.connect(RQMSpecification, "cdbrqm_reqif_export", "now")
def cdbrqm_reqif_export(specification, ctx):
    if "reqif_exported" not in ctx.dialog.get_attribute_names():
        from cs.requirements_reqif.reqif_export_ng import ReqIFExportNG
        start_sql_cnt = statement_count()
        start = datetime.datetime.now()
        if ctx.dialog.reqif_profile != '':
            profile = ctx.dialog.reqif_profile
        profile = ReqIFProfile.ByKeys(cdb_object_id=profile)
        if not profile or profile.obsolete:
            LOG.error('Invalid or obsolete profile')
            raise ue.Exception("cdbrqm_reqif_err_no_export_profile")
        if ctx.dialog.export_path != '':
            export_path = ctx.dialog.export_path
            util.PersonalSettings().setValue("cs.requirements_reqif",
                                             "export_path", export_path)
        else:
            raise ue.Exception("cdbrqm_reqif_err_no_export_directory")
        util.PersonalSettings().setValue(
            "cs.requirements_reqif",
            "reqif_profile",
            profile.cdb_object_id
        )
        process_run = operation(
            constants.kOperationNew, RQMExportProcessRun,
            specification_object_id=specification.cdb_object_id,
            export_type="ReqIF Export ({})".format(profile.GetDescription()),
            export_status=RQMExportProcessRun.CREATED,
            profile_object_id=profile.cdb_object_id
        )
        protocol = operation(
            constants.kOperationNew, RQMProtocol,
            cdbf_object_id=process_run.cdb_object_id,
            protocol_id=1,
            action="Execution"
        )
        logger_extra_args = dict(
            tags=['rqm_protocol'],
            specification_object_id=specification.cdb_object_id
        )
        result_file = None
        with RQMProtocolLogging(protocol) as logger:
            try:
                replace_variables = (
                    ctx.dialog.replace_variables == "1"
                    if ('replace_variables') in ctx.dialog.get_attribute_names() else False
                )
                if replace_variables:
                    logger.info('Variable replacement has been activated by user.')
                export_target_values = (
                    ctx.dialog.export_target_values == "1"
                    if('export_target_values') in ctx.dialog.get_attribute_names() else False
                )
                if export_target_values:
                    logger.info('Export of acceptance criteria has been activated by user')
                with increase_eviction_queue_limit(len(specification.Requirements) * 2):
                    reqif_export = ReqIFExportNG(
                        profile,
                        specification,
                        logger=logger,
                        logger_extra_args=logger_extra_args,
                        replace_variables=replace_variables,
                        export_target_values=export_target_values,
                        process_run=process_run
                    )
                    tmp_dir_path = tempfile.mkdtemp(dir=CADDOK.TMPDIR)
                    logger.info('Created temporary working directory: %s', tmp_dir_path, extra=logger_extra_args)
                    export_file = "%s.reqifz" % specification.spec_id
                    export_file = jail_filename(tmp_dir_path, export_file)
                    server_file_name = reqif_export.export(export_file)
                    result_file = DocumentExportTools.save_result_file(
                        export_run=process_run,
                        tmp_dir_path=tmp_dir_path,
                        result_file_name=server_file_name
                    )
                    process_run.export_status = RQMExportProcessRun.FINISHED
                    end = datetime.datetime.now()
                    logger.info(
                        'Export to %s finished (total: %s seconds)',
                        result_file.GetDescription(), (end - start).total_seconds(),
                        extra=logger_extra_args
                    )
            except BaseException as e:
                logger.exception(e, extra=logger_extra_args)
                process_run.export_status = RQMExportProcessRun.FAILED
                end = datetime.datetime.now()
        stop_sql_cnt = statement_count()
        LOG.debug('took %s seconds and %d statements', (
            (end - start).total_seconds()), stop_sql_cnt - start_sql_cnt
        )
        ctx.keep('reqif_exported', '1')
        if result_file is None:
            msg = 'Failed to export %s with profile %s, look into export run for details.' % (
                specification.GetDescription(), profile.GetDescription()
            )
            if ctx.interactive or ctx.uses_webui:
                raise ue.Exception('just_a_replacement', msg)
            else:
                raise ReqIFInterfaceError(msg)
        if ctx.uses_webui:
            ctx.url(
                "/api/v1/collection/rqm_export_run/%s/files/%s" % (
                    process_run.cdb_object_id,
                    result_file.cdb_object_id
                )
            )
        elif ctx.interactive:
            ctx.upload_cdbfile_to_client(
                cdb_file_id=result_file.cdb_object_id,
                client_filename=export_path
            )
        else:
            ctx.set_object_result(result_file)
        DocumentExportTools.cleanup_folder(tmp_dir_path)


@sig.connect(RQMSpecification, "cdbrqm_reqif_import", "pre_mask")
def cdbrqm_reqif_import_prepare_mask(_, ctx):
    profile = None
    user_last_profile = util.PersonalSettings().getValueOrDefault("cs.requirements_reqif",
                                                                  "reqif_profile",
                                                                  None)
    user_last_file = util.PersonalSettings().getValueOrDefault("cs.requirements_reqif",
                                                               "import_file",
                                                               None)
    if user_last_profile is not None:
        profile = user_last_profile
    elif ReqIFProfile.get_default() is not None:
        profile = ReqIFProfile.get_default().cdb_object_id
    if profile is not None:
        ctx.set("reqif_profile", profile)

    if user_last_file is not None:
        ctx.set("import_file", user_last_file)


@sig.connect(RQMSpecification, "cdbrqm_reqif_import", "post_mask")
def cdbrqm_reqif_import_checks(_, ctx):
    if (ctx.dialog.reqif_profile != '' and
            ReqIFProfile.ByKeys(ctx.dialog.reqif_profile) is not None):
        util.PersonalSettings().setValue("cs.requirements_reqif",
                                         "reqif_profile", ctx.dialog.reqif_profile)
    else:
        raise ue.Exception("cdbrqm_reqif_err_no_import_profile")

    if ctx.dialog.import_file != '':
        util.PersonalSettings().setValue("cs.requirements_reqif",
                                         "import_file",
                                         ctx.dialog.import_file)
    else:
        raise ue.Exception("cdbrqm_reqif_err_no_import_file")


@sig.connect(RQMSpecification, "cdbrqm_reqif_import", "now")
def cdbrqm_reqif_import_transfer(specification, ctx, process_run_id=None):
    client_path = ctx.dialog.import_file
    _, extension = os.path.splitext(client_path)
    if extension.lower() not in ['.reqif', '.reqifz']:
        raise ue.Exception("cdbrqm_reqif_err_invalid_file_extension")
    source_filename = os.path.basename(client_path)
    if process_run_id is not None:
        process_run = RQMImportProcessRun.ByKeys(cdb_object_id=process_run_id)
    else:
        process_run = operation("CDB_Create", RQMImportProcessRun,
                                specification_object_id=specification.cdb_object_id,
                                import_type="ReqIF Import",
                                source=source_filename)
        process_run_id = process_run.cdb_object_id
    protocol = operation("CDB_Create", RQMProtocol,
                         cdbf_object_id=process_run.cdb_object_id,
                         protocol_id=1,
                         action="Preparation")
    logger_extra_args = dict(tags=['rqm_protocol'],
                             specification_object_id=specification.cdb_object_id)
    with RQMProtocolLogging(protocol) as logger:
        # ensure valid path/profile
        cdbrqm_reqif_import_checks(specification, ctx)
        f_temp = tempfile.NamedTemporaryFile(
            prefix='reqif_import_f',
            delete=False
        )
        logger.info('Downloading file from client to server: %s to %s', client_path, f_temp.name, extra=logger_extra_args)
        ctx.download_from_client(client_path, f_temp.name,
                                 delete_file_after_download=0)
        logger.info('Finished downloading', extra=logger_extra_args)
        ctx.keep('importpath', f_temp.name)
    ctx.keep('process_run_id', process_run_id)
    ctx.keep('source_filename', source_filename)


@sig.connect(RQMSpecification, "cdbrqm_reqif_import", "post")
def cdbrqm_reqif_import(specification, ctx, process_run_id=None):
    from os import path, remove
    from cs.requirements_reqif.reqif_import_ng import ReqIFImportNG
    # from cs.requirements_reqif.reqif_import import ReqIFImport as ReqIFImportNG
    create_baseline = (ctx.dialog['create_baseline'] == u'1')
    if "import_errors" not in ctx.dialog.get_attribute_names():
        if ('importpath' not in ctx.ue_args.get_attribute_names() or
                not path.isfile(ctx.ue_args['importpath'])):
            raise ue.Exception("cdbrqm_reqif_err_no_tempfile")
        process_run_id = ctx.ue_args['process_run_id'] if 'process_run_id' in ctx.ue_args.get_attribute_names() else process_run_id
        if process_run_id is not None:
            process_run = RQMImportProcessRun.ByKeys(cdb_object_id=process_run_id)
        else:
            raise ue.Exception("cdbrqm_reqif_err_missing_import_process")
        protocol = operation("CDB_Create", RQMProtocol,
                             cdbf_object_id=process_run.cdb_object_id,
                             protocol_id=2,
                             action="Execution")
        logger_extra_args = dict(tags=['rqm_protocol'],
                                 specification_object_id=specification.cdb_object_id)
        with RQMProtocolLogging(protocol) as logger:
            importPath = ctx.ue_args['importpath']
            source_filename = ctx.ue_args['source_filename']
            ftype = getFileTypeByFilename(source_filename)
            CDB_File.NewFromFile(process_run_id,
                                 importPath,
                                 primary=True,
                                 additional_args=dict(cdbf_name=source_filename,
                                                      cdbf_type=ftype.getName()))
            logger.info('Attached file %s to import run', source_filename, extra=logger_extra_args)
            profile = ctx.dialog.reqif_profile
            meldung = ""
            success = False
            has_error = False
            has_warning = False
            try:
                reqif_import = ReqIFImportNG(
                    specification_mappings={
                        specification.reqif_id: specification,
                        ReqIFImportNG.DEFAULT_MAPPING_KEY: specification
                    },
                    profile=profile,
                    import_file=importPath,
                    logger=logger,
                    logger_extra_args=logger_extra_args,
                    create_baseline=create_baseline
                )
                results = reqif_import.imp()
                for res in results:
                    if res.get('level').lower() == 'warning':
                        has_warning = True
                    if res.get('level').lower() == 'error':
                        has_error = True
                    meldung += "\n\n%s: %s" % (
                        res["level"].upper(),
                        res["message"]
                    )
                process_run.import_status = RQMImportProcessRun.FINISHED
                success = True
            except ue.Exception as e:
                logger.exception(e, extra=logger_extra_args)
                raise e
            except ValueError as e:
                logger.exception(e, extra=logger_extra_args)
                meldung += e.message
                raise ue.Exception("just_a_replacement", e.message)
            except ReqIFInterfaceError as e:
                logger.exception(e, extra=logger_extra_args)
                raise ue.Exception("just_a_replacement", e.message)
            except BaseException as e:
                logger.exception(e, extra=logger_extra_args)
                raise
            finally:
                if not success:
                    process_run.import_status = RQMImportProcessRun.FAILED
            try:
                remove(ctx.ue_args['importpath'])
            except IOError as e:
                logger.exception(e, extra=logger_extra_args)
                meldung += e.message
            ctx.keep('results', meldung)
            ctx.keep('result_level', 'error' if has_error else ('warning' if has_warning else 'info'))
    else:
        ctx.keep('suppress_result_information', 1)


@sig.connect(RQMSpecification, "cdbrqm_reqif_import", "final")
def cdbrqm_reqif_import_results(_, ctx):
    if "suppress_result_information" not in ctx.ue_args.get_attribute_names():
        if (
            'results' in ctx.ue_args.get_attribute_names() and
            'result_level' in ctx.ue_args.get_attribute_names()
        ):
            # hard errors should be communicated using exceptions and will automatically get another message box then
            if ctx.ue_args['result_level'] in ['error', 'warning']:
                icon = ctx.MessageBox.kMsgBoxIconAlert
            else:
                icon = ctx.MessageBox.kMsgBoxIconInformation
            msgbox = ctx.MessageBox("cdbrqm_reqif_import_message",
                                    [ctx.ue_args['results']],
                                    "import_errors",
                                    icon)
            msgbox.addButton(ctx.MessageBoxButton("button_cad_bind",
                                                  ctx.MessageBox.kMsgBoxResultYes,
                                                  is_dflt=1))
            ctx.refresh_tables([RQMSpecification.GetTableName(),
                                RQMSpecObject.GetTableName(),
                                TargetValue.GetTableName()])
            if not ctx.uses_webui:
                ctx.show_message(msgbox)
