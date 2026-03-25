# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module __init__

This is the documentation for the __init__ module.
"""
import importlib
import json
import os
import pkg_resources
import sys
import traceback
import shutil
import six

from cdb import misc
from cdb import mq
from cdb import sqlapi
from cdb import CADDOK
from cdb import util
from cdb import rte
from cdb.fls import LicenseError, allocate_license, allocate_server_license
from cs.cadbase import cadcommands

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []

__cadJobExecs = dict()


class NoCadSystemException(Exception):
    """
    This Exception signals a not complete job_runner without a given cad_system
    """
    def __init__(self):
        Exception.__init__(self, "No cad_system")


class ProcessingException(Exception):
    """
    This Exception signals a failure during job processing
    """
    def __init__(self, msg):
        Exception.__init__(self, msg)


class JobCallBack(object):
    """
    Abstract base class for job callback
    """

    def pre(self, job):
        """
        This method is called before the cad jobs are running. The main purpose
        is to prepare (checkout, copy) the files in the workspace. It is also
        possible to use the pre callback for creating jobs via jobrunner
        functions and store the generated jobs description with
        job.saveCadJobs(job_runner).

        Parameters from create_cad_job can be accessed with job.get_parameter().

        In WS4 environment a temporary teamspace will be build after pre and
        this teamspace  will be transferred to the cadconvertion queue machine.

        This method has access to the PDM ecosystem.

        This method should throw a ProcessingException if an unhandleable error occurred.

        :param: job: CadQueueJob

        :returns: serialized python structure in JSON format. This result can be
                  accessed by job.preResult in post, done calls.
        """
        ret = []
        return ret

    def post(self, job, job_runner):
        """
        This method is called after successfully running the job in the CAD system.
        Its purpose is cleaning up the workspace, for example if all changed
        files should be committed by a sandbox that was constructed in pre.

        It's possible to call additional converters or other external tools.

        For future use in WS4 environments: This message must not access any PDM functions like
        cs.documents. It's only allowed to access local files, job parameters and the pre result.
        In WS4 this method runs on the CAD machine which might be differnt from the job
        executing machine with access to PDM data.

        Should throw a ProcessingException if an unhandleable error occurred.

        :param: job: CadQueueJob

        :returns: post_job result. May be any type. The result can accessed by
                  job.postResult in done

        """
        # Running a second job
        # =====================
        #
        # If we like to call additonal jobs we can use our
        # own cadcommand.JobExcution and execute the jobs directly in post.
        # The cad system is  (and should be in the future) reserved for us until
        # post has finished.
        #
        # In the future: if post is running on a differnt machine all code for
        # cadcommands must be available on that machine
        post_result = []
        return post_result

    def done(self, job):
        """
        This method is called after a successful post. Parameters from post
        are accessible by job.postResult. This method has access to the pdm
        serever. The purpose is to check in the changes from the cad jobs to
        the PDM system or to any other destination.

        If done throws an exception, the fail method will be called

        :param job: CadQueueJob
        """
        pass

    def fail(self, job):
        """
        Will be called if an exception occurred in pre, post or done, or a
        cad job execution in CAD failed.

        :param job: CadQueueJob
        """
        pass


def loaded_job_execs():
    global __cadJobExecs
    if not __cadJobExecs:
        __cadJobExecs = _import_plugins()
    return __cadJobExecs


PLUGIN_ENTRY_POINT_GROUP = "cs.jobexec.plugins"


def _import_plugins():
    _plgs = {}
    for ep in pkg_resources.iter_entry_points(group=PLUGIN_ENTRY_POINT_GROUP):
        try:
            _plgs[ep.name] = ep.load()
        except Exception:
            misc.log_traceback("warning plugin '%s' at '%s' is not a valid plugin!"
                               % (ep.name, ep.module_name))
    return _plgs


class CadQueueJob(mq.Job):
    """
    This class holds information for a single job
    """

    def __init__(self, myid, queue, duplicate=None):
        mq.Job.__init__(self, myid, queue)
        self._log = util.text_read("mq_cad_job_server_log", ["cdbmq_id"], ["%s" % myid])
        # _failed = 0: everything OK
        #         = 1: error in HandleJob
        #         = 2: error in callback
        #         = 3: no license
        #         = 4: error cad job executiton
        self._failed = 0
        w_dir = os.path.join(CADDOK.TEMP, "cadjobserver", "%s" % os.getpid(), "%s" % self.id())
        w_dir = os.path.normpath(w_dir)
        self._workdir = w_dir
        self.callBackObject = None
        self.preResult = None  # Result of pre call. Can be used in post and done calls

        # Result of the post process call. Can be used in the done call.
        # Normally a list of filenames.
        self.postResult = None

    def add_long_text_fields(self, parameter, command):
        """
        Add the string into long text fields parameter and command
        """
        util.text_write("mq_cad_job_server_param", ["cdbmq_id"], ["%s" % self.id()], parameter)
        util.text_write("mq_cad_job_server_cmd", ["cdbmq_id"], ["%s" % self.id()], command)

    def save_cad_jobs(self, job_runner):
        """
        Store the jobs from job_runner. May be used if a job is defined in the pre callback
        of a job
        """
        if not job_runner.cad_system:
            raise NoCadSystemException()
        self.set("system", job_runner.cad_system)
        util.text_write("mq_cad_job_server_cmd", ["cdbmq_id"],
                        ["%s" % self.id()], job_runner.serialize_jobs())

    def get_parameter(self):
        """
        :returns: All parameters as a dict (or given structure form JSON)
        """
        ret = dict()
        parameters_json = util.text_read("mq_cad_job_server_param", ["cdbmq_id"],
                                         ["%s" % self.id()])
        if parameters_json:
            ret = json.loads(parameters_json)
        return ret

    def _get_json_commands(self):
        """
        :return: string (utf-8 encoded)
        """
        return util.text_read("mq_cad_job_server_cmd", ["cdbmq_id"], ["%s" % self.id()])

    def get_workspace(self):
        return self._workdir

    def call_pre_function(self):
        """
        Will be called before jobs are executed.
        May fill or overwrite the job attribute in the database.
        """
        ret = self.callBackObject.pre(self)
        return ret

    def call_post_function(self, job_runner):
        """
        :param job_runner: contains all jobs and the commands, for query the result
        """
        self.log("Before calling POST")
        return self.callBackObject.post(self, job_runner)

    def log(self, msg):
        if isinstance(msg, str):
            msg = msg.decode(errors='replace')
        self._log = self._log + msg + "\n"
        util.text_append("mq_cad_job_server_log", ["cdbmq_id"], ["%s" % self.id()], msg + "\n")
        misc.log(0, msg)

    def get_current_log(self):
        """
        :returns: The cumulated log messages for this job as a single string.
        """
        return self._log

    def done(self):
        """
        Will be called after running the post-callback without error.
        """
        try:
            self.callBackObject.done(self)
        except Exception as exc:
            self._failed = 2
            msg = "".join(traceback.format_exception(*sys.exc_info()))
            self.log("caught an exception (%s) while running callback:\n%s" % (exc, msg))

        if 2 == self._failed:
            self.fail(0, "PowerScript exception while running callback")
        else:
            self._delete_text_records()
            mq.Job.done(self)

    def _delete_text_records(self):
        """
        Delete all entries in LONGTEXT relations for this job.
        """
        text_relations = ["mq_cad_job_server_log", "mq_cad_job_server_cmd",
                          "mq_cad_job_server_param"]
        for t in text_relations:
            sqlapi.SQLdelete("FROM %s WHERE cdbmq_id=%s" % (t, self.id()))

    def fail(self, code, reason):
        """
        Will be called on failed, exception or directly from code
        """
        mq.Job.fail(self, code, reason)
        try:
            self.callBackObject.fail(self)
        except Exception as exc:
            msg = "".join(traceback.format_exception(*sys.exc_info()))
            self.log("caught an exception (%s) while running failPolicy:\n%s" % (exc, msg))

    def run(self):
        """
        Run the cad job
        """
        self._failed = 0
        # Running a Job needs a license!
        try:
            allocate_license("CADBASE_002")
        except LicenseError as ex:
            self.log("License allocation failed: %s" % ex.message)
            self._failed = 3
            self.fail(0, ex.message)
            return

        try:
            if not os.path.exists(self._workdir):
                os.makedirs(self._workdir)
            os.chdir(self._workdir)
            self._run_jobs()
            if not self._failed:
                self.done()
            else:
                if self._failed != 2:
                    self.fail(self._failed, "---")
        except Exception as exc:
            self._failed = 1
            msg = "".join(traceback.format_exception(*sys.exc_info()))
            self.log("Plugin failed with exception %s:\n%s" % (exc, msg))
            self.fail(0, "PowerScript exception")

        # if self._failed and self.queue.cliSettings.failpolicy:
        #    self.queue.cliSettings.failpolicy(self)

        # Hier kann das _workdir auch abgeraeumt werden.
        os.chdir(CADDOK.HOME)
        keep_workspace = False
        cls_to_keep_str = rte.environ.get("CADDOK_CADJOBS_KEEP_WORKDIR")
        if cls_to_keep_str:
            cls_to_keep = cls_to_keep_str.split(",")
            keep_workspace = "ALL" in cls_to_keep or self.__class__.__name__ in cls_to_keep
        if not (self._failed or keep_workspace):
            try:
                shutil.rmtree(self._workdir)
            except Exception as exc:
                self.log("Warning: could not remove workspace directory %s (%s)\n" % (self._workdir,
                                                                                      exc))

    def _run_jobs(self):
        """
        Run the pre/post callbacks and the cad job.
        """
        self.callBackObject = None
        try:
            module = importlib.import_module(self.pa_mod)
            cls = getattr(module, self.pa_cb_class)
            self.callBackObject = cls()
        except Exception as e:
            self.log("Callback failed %s" % e)
            pass
        if self.callBackObject:
            try:
                self.preResult = self.call_pre_function()
            except ProcessingException as e:
                self._failed = 2
                self.log("Pre callback failed with ProcessingEexception: %s" % e)
                self.fail(2, "Preprocessing failed: %s" % e)
            except Exception as e:
                self._failed = 2
                msg = "".join(traceback.format_exception(*sys.exc_info()))
                self.log("Pre callback failed with exception %s:\n%s" % (e, msg))
                self.fail(2, "Preprocessing failure: %s, %s" % (e, msg))
            if not self._failed:
                job_directory = os.path.join(self.get_workspace(), "__jobs")
                if os.path.isdir(job_directory):
                    shutil.rmtree(job_directory)
                os.makedirs(job_directory)
                # think about: Allow empty commands?
                # or is this an error?
                cmds = self._get_json_commands()
                has_cmds = False
                if cmds:
                    job_exec = loaded_job_execs()[self.system]
                    job_runner = cadcommands.JobRunner(self.system, job_exec(), job_directory)
                    job_runner.create_jobs_from_string(cmds, self.get_workspace())
                    for job in job_runner.jobs:
                        has_cmds = has_cmds or bool(job.cmds)
                        result = job.execute(job_runner._project_env)
                        if result.hasError():
                            self._failed = 4
                            self.log("Executing jobs failed ! %s" % result)
                            break
                    self.log("Failed status after Jobs %s" % self._failed)
                if not self._failed and has_cmds:
                    try:
                        self.postResult = self.call_post_function(job_runner)
                    except ProcessingException as e:
                        self._failed = 2
                        self.log("Post callback failed with ProcessingException %s:\n%s" % (e, msg))
                        self.fail(2, "Postprocssing failed: %s" % e)
                    except Exception as e:
                        self._failed = 2
                        msg = "".join(traceback.format_exception(*sys.exc_info()))
                        self.log("Post callback failed with exception %s:\n%s" % (e, msg))
                        self.fail(2, "Postprocessing failure: %s, %s" % (e, msg))


class _CadQueue(mq.Queue):
    cCLIOptions = ("""
'cadjobqueue' is the frontend command to control the cadjobque

--site <site to run on>    Site to run this queue
--condition <sql>          Sql condition without where to filter jobs i.e. by cad system
""" + mq.Queue.cCLIOptions)

    def cli(self, args):
        """
        Handle additional command line parameters
        """
        try:
            allocate_server_license("CADBASE_003")
        except LicenseError as ex:
            misc.log_error("License allocation failed: %s" % ex.message)
            return 3
        parameters = ["--condition", "condition", "--site"]
        p_values = {}
        argv = []
        i = 0
        while i < len(args):
            arg = args[i]
            for p in parameters:
                pequal = "%s=" % p
                if arg.startswith(pequal):
                    pval = arg[len(pequal):]
                    if pval:
                        p_values[p] = pval
                    break
                elif arg == p:
                    if i + 1 < len(args):
                        i += 1
                        p_values[p] = args[i]
                    break
            else:
                argv.append(arg)
            i += 1
        self.condition = p_values.get("--condition", p_values.get("condition"))
        if self.condition == "":
            self.condition = None
        site = p_values.get("--site")
        if site:
            self.queue_site = site
            self.attend_site = 1
        rc = mq.Queue.cli(self, argv)
        return rc


theCadQueue = _CadQueue("cad_job_server", CadQueueJob)


def get_cad_convert_queue():
    return theCadQueue


def create_cad_job(job_parameters, job_runner, callback_module, callback_class, site=None):
    """
    :param job_parameters: dict with job parameters
    :param job_runner: cadcommands.jobrunner with add cad jobs or None if job is
                       defined in pre_callback
    :param callback_module: module i.e. customer.cad.foo previously imported or name of the module
    :param callback_class: class from callback_module i.e.: customer.cad.foo.MyClass or
                           name of the class
    :param site: string, site name to run this job on.

    Defining CadJobs:
      - Derive a callback_class from JobCallBack
      - Use pre() to checkout all data given that are needed and normally defined by job_parameters
      - Use post() to cleanup all not need data and checkin the data back into CIM DATABASE
      - Use done() for further actions
      - create cad jobs using job_runner

    .. code-block:: python

        jobRunner = cadcommands.JobRunner("catia")
        job = jobRunner.create_job()
        # add the commands to the job
        # cadcommands.CadCommand.CAD_ROOT_DIR will be replaced by the job working directory
        cadFile = os.path.join(cadcommands.CadCommand.CAD_ROOT_DIR,"filename.CATPart")
        cadP = {"abc": "123",   # Parameters to update in CAD
                xyz": "789"}
        jsonStruct = [{"type": "string",
                       "name": k, "value": unicode(v)} for k, v in cadP.iteritems()]
        cmdSetParameter = cadcommands.CmdSetParameter(
            cadFile,
            [],
            parameterjson=jsonStruct,
            parameterhash=None,
            regenerate=True,
            [cadcommands.processingFlags.SaveWorkFileAfterAction,
             cadcommands.processingFlags.StopOnError]
            )
        job.append(cmdSetParameter)
        flags = [cadcommands.processingFlags.CloseWorkFileAfterAction,
                 cadcommands.processingFlags.StopOnError]
        cmdSaveAppinfo = cadcommands.CmdSaveAppInfo(cadFile,[],"SINGLE",flags=flags)
        job.append(cmdSaveAppinfo)
        # call createJob with the jobRunnner
        createCadJob({"z_nummer": "00123-2",
                      "z_index": "a",
                      "destination_file": "filename.CATPart"},
                     jobRunner,
                     callback_module,
                     callback_class)
    """
    allocate_license("CADBASE_001")
    modname = callback_module if (isinstance(callback_module,
                                             six.string_types)) else callback_module.__name__
    classname = callback_class if (isinstance(callback_class,
                                              six.string_types)) else callback_class.__name__
    parameter = {"pa_mod": modname,
                 "pa_cb_class": classname}
    if job_runner is not None:
        if not job_runner.cad_system:
            raise NoCadSystemException
        parameter["system"] = job_runner.cad_system
    if site:
        parameter["cdbmq_site"] = site

    job = theCadQueue.new(**parameter)
    job.add_long_text_fields(json.dumps(job_parameters),
                             job_runner.serialize_jobs() if job_runner is not None else "")
    job.start()
    return job
