#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
This module defines the streaming cache publishing service which encapsules
the HOOPS Communicator streaming cache broker server.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import argparse
import io
import json
import logging
import multiprocessing
import os
import sys

from collections import deque

from cdb import fls
from cdb.uberserver import usutil
from cdb.uberserver import secure

try:
    usutil.pick_platform_reactor()
except:
    pass

# import AFTER pick_platform_reactor
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import threads
import twisted.internet.error
from twisted.web import resource
from twisted.web import server
from twisted.web import client
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet import task
from twisted.python.components import registerAdapter
from twisted.internet.protocol import Factory
from zope.interface import classImplements
from zope import interface as zope_interface
from twisted.web.server import Session

from cdb import misc
from cdb import rte

from cs.threed.services.hoops_config_gen import HOOPSConfigGenerator
from cs.threed.services import cache

from cs.threed.services.installation_fix import fix_installation
from cs.threed.services.broker.check_resource import CheckResource
from cs.threed.services.broker import util as brokerUtil
from cs.threed.services.broker import ws_transport
from cs.threed.services.broker import authentication
from cs.threed.services.broker import proxy
import cs.threedlibs.environment as threedlibs

# Exported objects
__all__ = ['BrokerService']

LOG = logging.getLogger(__name__)

# Interval in seconds between status file updates
STATUS_CHECK_INTERVAL = 10
# Url fragment to trigger an xml text result on registration
XML_ARG = "with_xml"
# Indicates, if the model should be rendered client-side ("csr_session") or
# server-side ("ssr_session")
SESSION_ARG = "session"
# Indicates, if the state notification should be streamed ("stream"),
# bound to session and polled for updates ("session") or skipped
# (anything else or left out).
RESPONSE_ARG = "response"

# Maximum amount of retires, until worker or server executables stops being
# respawned
MAX_RETRIES = 3

# hoops server status file constants
HOOPS_CSR_SUBCLASS = "techsoft3d.communicator.serviceinterface.processmanager.sccsr"
HOOPS_SSR_SUBCLASS = "techsoft3d.communicator.serviceinterface.processmanager.scssr"

# default maximum broker service worker count
DEFAULT_MAX_WORKER_COUNT = 16

win32 = (sys.platform == "win32")

def u_to_str(text):
    import unicodedata
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')


class BrokerService(protocol.ProcessProtocol):

    def __init__(self, sid, server_port=None, max_spawn_count=10, spawn_start_port=0,
                 csr_enabled=False, ssr_enabled=False):
        self.sid = sid
        self.hostname = "localhost"
        config_dir = cache.get_config_dir()
        log_dir = cache.get_log_dir()
        tmp_dir = cache.get_tmp_dir()
        cache_dir = cache.get_cache_dir()
        self.config = HOOPSConfigGenerator(
            sid=sid,
            config_dir=config_dir,
            log_dir=log_dir,
            cache_dir=cache_dir,
            tmp_dir=tmp_dir,
            base_port=server_port,
            max_spawn_count=max_spawn_count,
            spawn_start_port=spawn_start_port,
            csr_enabled=csr_enabled,
            ssr_enabled=ssr_enabled
        )
        self.port = self.config.broker_port
        self.retries = 0
        self.has_ssr = ssr_enabled
        self.has_csr = csr_enabled
        self.logger = logging.getLogger("Hoops Broker Server")

    def connectionMade(self):
        self.logger.info("Connected")
        self.deferred.callback(self)

    def outReceived(self, data):
        # reset retry count, as the server seems to run
        self.retries = 0
        if isinstance(data, str):
            data = data.strip()
        self.logger.info("%s", data)

    def errReceived(self, data):
        if isinstance(data, str):
            data = data.strip()
        self.logger.error("%s", data)

    def inConnectionLost(self):
        pass

    def processEnded(self, reason):
        self.logger.info("Process ended: %r", reason.value)
        if isinstance(reason.value, twisted.internet.error.ProcessDone) or \
                reason.value.signal < 4:
            if not self.deferred.called:
                self.deferred.callback(None)
        else:
            if not self.deferred.called:
                self.deferred.errback(reason.value.status)
            self.logger.info("Connection lost, restarting...")
            if self.retries < MAX_RETRIES:
                self.retries += 1
                reactor.callLater(2 ** self.retries, self.spawn)

    def is_alive(self):
        return self.transport is not None and self.transport.pid is not None

    def get_url(self, *url_parts):
        """returns the endpoint of the hoops broker service"""
        additional_path = ""
        if url_parts:
            additional_path = "/" + "/".join(url_parts)
        return "http://%s:%s%s" % ("localhost", self.port, additional_path)

    def stop(self):
        if self.is_alive():
            self.logger.info("Stopped")
            self.transport.signalProcess('TERM')

    def spawn(self):
        """
        Spawns the hoops server
        :return: a Deferred with a callback on successful connection,
                 and errback on process terminating with error. The result of
                 the callback is the transport object itself if it is alive,
                 or None if it is not.

        """
        self.deferred = defer.Deferred(self.stop)
        args = [
            threedlibs.NODE_EXECUTABLE_NAME,
            "--expose-gc",
            threedlibs.SERVICE_STARTUP_SCRIPT_PATH,
            "--config-file",
            self.config.server_path
        ]
        env = dict(rte.environ)
        if win32:
            env["PATH"] = ";".join([env["PATH"], threedlibs.RUNTIME_PATH])
        else:
            server_dir = os.path.dirname(threedlibs.NODE_EXECUTABLE_PATH)
            if server_dir not in env.get("LD_LIBRARY_PATH", ""):
                path_items = [env.get("LD_LIBRARY_PATH"), server_dir]
                env["LD_LIBRARY_PATH"] = ":".join(item for item in path_items if item)
        reactor.spawnProcess(
            self, threedlibs.NODE_EXECUTABLE_PATH, args=args, env=env,
            path=self.config.log_dir
        )

        return self.deferred


class WorkerService(protocol.ProcessProtocol):

    def __init__(self, name, wid, work_queue, only_checks=False):
        self.name = name
        self.counter = 0
        self.wid = wid
        self.is_ready = False
        self.active_deferred = None
        self.tasks = work_queue
        self.deferred = None
        self.only_checks = only_checks
        self.retries = 0

    def task_len(self):
        return len(self.tasks) + (1 if self.active_deferred else 0)

    def run_task(self):
        # run new task, if there is not another one running
        if not self.is_ready or self.active_deferred is not None:
            return

        try:
            if self.only_checks and self.tasks:
                pot_task = self.tasks[0]
                if not pot_task[1][0:5] == "check":
                    return

            wrk_task = self.tasks.popleft()
            self.active_deferred = wrk_task[0]
        except IndexError:
            pass  # no tasks
        else:
            try:
                self.transport.writeToChild(0, (f"{wrk_task[1]}\n".encode(encoding = "utf-8")))
            except AttributeError:
                LOG.error("Connection to broker worker terminated "
                          "unexpectedly: %s", self.name)

    def connectionMade(self):
        LOG.info("ThreeD Broker: Worker connected (%s)", self.name)
        self.is_ready = True
        self.run_task()

    def outReceived(self, msg):
        # reset retry count, as an output could be received from the worker
        self.retries = 0

        lines = msg.decode().rstrip().split("\n")
        for line in lines:
            d = self.active_deferred
            if d and line[0:7] == "RESULT:":
                self.active_deferred = None
                d.callback(line[7:])
                # take next task
                self.run_task()
            elif line == "READY":
                LOG.info("3D Broker Worker is ready: %s", self.name)
            else:
                LOG.warning("3D Broker Worker output: %s", msg)

    def errReceived(self, msg):
        lines = msg.decode().rstrip().split("\n")
        for line in lines:
            d = self.active_deferred
            if d and line[0:7] == "RESULT:":
                self.active_deferred = None
                d.errback(ValueError(line[7:]))
                LOG.warning("3D Broker Worker Error: %s", line[8:])
                # take next task
                self.run_task()
            elif line == "READY":
                LOG.info("3D Broker Worker communicates ready "
                         "state on an error channel: %s", self.name)
            else:
                LOG.warning("3D Broker Worker Error: %s", msg)

    def inConnectionLost(self):
        self.is_ready = False
        d = self.active_deferred
        if d:
            self.active_deferred = None
            d.errback(RuntimeError("crashed"))

    def processEnded(self, reason):
        d = self.active_deferred
        if d:
            self.active_deferred = None
            d.errback(RuntimeError("shutdown"))
        LOG.info("HOOPS broker worker died with error message: %s",
                 reason.value)

        if self.retries < MAX_RETRIES and not isinstance(
                reason.value, twisted.internet.error.ProcessDone) \
                and (reason.value.signal is None or reason.value.signal > 3):
            LOG.info("HOOPS broker worker died, restarting...")
            self.retries += 1
            reactor.callLater(2 ** self.retries, self.spawn)

    def is_alive(self):
        return self.transport.pid is not None

    def stop(self):
        if self.is_alive():
            self.transport.signalProcess('TERM')
            LOG.info("ThreeD Broker: Worker stopped (%s)", self.name)

    def spawn(self):
        """
         Spawns a worker, which is responsible for operations on model files
         and database records.
        :return: a Deferred with a callback on successful connection,
                 and errback on process terminating with error. The result of
                 the callback is the transport object itself if it is alive,
                 or None if it is not.

        """
        self.deferred = defer.Deferred(self.stop)
        environ = rte.environ
        parent_log = os.path.join(environ["CADDOK_BASE"], "etc",
                                  "%s.conf" % environ["CADDOK_TOOL"])
        args = [
            "powerscript" + (".exe" if win32 else ""),
            "--program-name", "threed_broker_worker_%d" % (self.wid, ),
            "--nologin"
        ]
        if os.path.exists(parent_log):
            args.extend(["--conf", parent_log])
        args.extend([
            "-m", "cs.threed.services.broker_worker",
            "-q"
        ])
        reactor.spawnProcess(self, rte.runtime_tool("powerscript"),
                             args=args, env=rte.environ)
        return self.deferred


class JsonParamProducer(object):
    classImplements(IBodyProducer)

    def __init__(self, params):
        self.data = bytes(json.dumps(params), "utf-8")
        self.length = len(self.data)

    def startProducing(self, consumer):
        consumer.write(self.data)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class ReadJsonBodyProtocol(protocol.Protocol):

    def __init__(self, finished):
        self.finished = finished
        self.buffer = b""

    def dataReceived(self, data):
        self.buffer += data

    def connectionLost(self, reason=None):
        if isinstance(reason.value, client.ResponseDone):
            self.finished.callback(json.loads(self.buffer))
        else:
            self.finished.errback(reason)


class StateProtocol(object):

    def __init__(self, request, state_manager, document_id, make_endpoint, scope):
        self.request = request
        self.sm = state_manager
        self.document_id = document_id
        self.make_endpoint = make_endpoint
        self.scope = scope

    def response(self):
        raise NotImplementedError("response")


class BlockingHandler(StateProtocol):
    """
    Doesn't implement a model request state notification at all. The request
    will be held open until the model is ready and the endpoint is available.
    Only then the response will be transmitted to the client.

    FIXME: this handler is not used directly any more. It can be merged with the StreamingHandler
    """

    def __init__(self, request, state_manager, document_id, make_endpoint, scope):
        super(BlockingHandler, self).__init__(request, state_manager,
                                              document_id, make_endpoint, scope)
        self.isTLS = secure.get_ssl_mode() == secure.USESSL

    def _process_endpoints(self, endpoints):
        result = {}
        for epk, epv in endpoints.items():
            prot = epk.lower()
            if not prot.startswith("ws"):
                continue
            ws_url = epv

            epv_comps = epv.split(":")
            if len(epv_comps) == 3:
                forward_port = epv_comps[2]
                url_base = proxy.get_ws_scheme_and_host(request=self.request)
                ws_url = "%s/ws/%s" % (url_base, forward_port)
                self.sm.add_endpoint_scope(forward_port, self.scope)
            else:
                LOG.error("Invalid WebSocket URL received from Broker Server: %s", ws_url)

            LOG.debug("WebSocket URL: %s", ws_url)
            result[prot] = ws_url
        return result

    def _format_hoops_result(self, result):
        LOG.debug("hoops server response %s", result)
        if result.get('reason'):
            raise ValueError(result.get('reason'))
        response = {}
        response["endpoints"] = self._process_endpoints(
            result.get("endpoints", {}))
        response["result"] = result.get("result", "error")
        response["renderer"] = result.get("renderer", "client")
        return response

    @staticmethod
    def _format_cache_result(result):
        response = {}
        cache_response = result.get("model_result", "Error\t")
        cache_state, cache_name = cache_response.split("\t")
        response["cache_name"] = cache_name
        if cache_state == "Registered":
            response["cache_hit"] = False
        elif cache_state == "Unchanged":
            response["cache_hit"] = True
        else:
            response["cache_hit"] = "Error"
        if result.get("xml"):
            response["xml"] = result.get("xml")
        return response

    @staticmethod
    def make_response_json(is_successful, result=None, state=None, value=None, states=None,
                           message_id=None, message_text=None, detailed_message=None,
                           session_id=None, done=None):
        out = dict(success=is_successful)
        if is_successful:
            if result:
                out["result"] = result
            if states:
                out["states"] = states
            if state is not None:
                out["state"] = state
            if value is not None:
                out["value"] = value
        else:
            out["msgId"] = message_id if message_id else "error_broker_connection"
            out["reason"] = message_text if message_text \
                else "Broker Service failed to process the request"
            out["detail"] = detailed_message if detailed_message else ""
        if session_id is not None:
            out["session"] = "%s" % (session_id)
        if done is not None:
            out["done"] = done

        return bytes(json.dumps(out), "utf-8")

    def _success(self, results):
        try:
            result = {}
            hoops_result = results[0]
            cache_result = results[1]
            if hoops_result:
                result = self._format_hoops_result(hoops_result)
            result["obj_info"] = self._format_cache_result(cache_result)
        except Exception as e:
            self._error(e)
        else:
            self.request.write(self.make_response_json(
                is_successful=True,
                result=result
            ))
            self.request.finish()

        return results

    def _error(self, error):
        try:
            exc = error.value
            detail = f"{type(exc).__name__}: {str(exc)}"
        except AttributeError:
            detail = f"{type(error).__name__}: {error}"
        self.request.write(self.make_response_json(
            is_successful=False,
            detailed_message=detail,
        ))
        self.request.finish()
        LOG.warning("Registration failed with: %s", detail)
        return error

    @staticmethod
    def _response_failed(err, call):
        call.cancel()

    def response(self):
        session_type = self.request.args.get(SESSION_ARG, ['csr_session'])[0]
        with_xml = self.request.args.get(XML_ARG, ['false'])[0] in ["1", "true"]

        @defer.inlineCallbacks
        def deferred_call():
            check_result = yield self.sm.check_model(self.document_id.decode("utf-8"))
            cache_result = yield self.sm.register_model(
                check_result, document_id=self.document_id.decode("utf-8"), with_xml=with_xml)
            if self.make_endpoint:
                hoops_result = yield self.sm.request_endpoint(session_type)
            else:
                hoops_result = None
            defer.returnValue((hoops_result, cache_result))

        call = deferred_call()
        call.addCallbacks(self._success, self._error)
        # cancel the initial requests and all chained requests, if the
        # request object has closed.
        self.request.notifyFinish().addErrback(self._response_failed, call)
        return server.NOT_DONE_YET


class IRequestState(zope_interface.Interface):
    response = zope_interface.Attribute("A dict containing the partially built "
                                        "result.")
    done = zope_interface.Attribute("A flag indicating, whether the response "
                                    "is complete.")
    states = zope_interface.Attribute("List of all completed states.")
    error = zope_interface.Attribute("Error object in case of an exception")
    request = zope_interface.Attribute("Request object to write response to")
    update = zope_interface.Attribute("A flag indicating, whether there are "
                                      "unsent state updates")


@zope_interface.implementer(IRequestState)
class RequestState(object):
    def __init__(self, session):
        self.response = {}
        self.done = False
        self.states = []
        self.error = None
        self.request = None
        self.update = False


registerAdapter(RequestState, Session, IRequestState)


class StreamingHandler(BlockingHandler):
    """
    Implements a model request state notification with the Stream API. The
    state changes will be streamed to the client, while the connection is
    held open.
    """

    def response(self):
        session_type = self.request.args.get(SESSION_ARG, ['csr_session'])[0]
        with_xml = self.request.args.get(XML_ARG, ['false'])[0] in ["1", "true"]

        @defer.inlineCallbacks
        def model_call():
            check_result = yield self.sm.check_model(self.document_id.decode("utf-8"))
            check_state, _ = check_result.split("\t")
            self.request.write(self.make_response_json(
                is_successful=True,
                state="model_change",
                value=(check_state == "Changed")
            ))
            self.request.write(b"\n")
            cache_result = yield self.sm.register_model(
                check_result, document_id=self.document_id.decode("utf-8"), with_xml=with_xml)
            self.request.write(self.make_response_json(
                is_successful=True,
                state="model_assembly",
                value=self._format_cache_result(cache_result)
            ))
            self.request.write(b"\n")
            defer.returnValue(cache_result)

        @defer.inlineCallbacks
        def hoops_call():
            if self.make_endpoint:
                hoops_result = yield self.sm.request_endpoint(session_type)
            else:
                hoops_result = None
            hoops_data = self._format_hoops_result(hoops_result) if hoops_result else {}
            self.request.write(self.make_response_json(
                is_successful=True,
                state="endpoint",
                value=hoops_data
            ))
            self.request.write(b"\n")
            defer.returnValue(hoops_result)

        @defer.inlineCallbacks
        def deferred_call():
            # parallel call
            # result = yield defer.DeferredList([hoops_call(), model_call()])
            # defer.returnValue((result[0][1], result[1][1]))
            # sequential call
            cache_result = yield model_call()
            hoops_result = yield hoops_call()
            defer.returnValue((hoops_result, cache_result))

        self.request.write(self.make_response_json(
            is_successful=True,
            state="connection"
        ))
        self.request.write(b"\n")
        call = deferred_call()
        call.addCallbacks(self._success, self._error)
        # cancel the initial requests and all chained requests, if the
        # request object has closed.
        self.request.notifyFinish().addErrback(self._response_failed, call)
        return server.NOT_DONE_YET

    def _success(self, results):
        self.request.finish()
        return results


class BrokerStateManager(object):

    def __init__(self, broker, max_worker_count):
        agentTimeout = max(10, brokerUtil.read_env_param(
            "THREED_HTTP_COMMUNICATOR_TIMEOUT", 120.0))
        LOG.info("Communicator agent timeout set to: %s", agentTimeout)
        self.agent = client.Agent(reactor, connectTimeout=agentTimeout)
        self.broker = broker
        self.workers = []
        self.work_queue = deque()
        self.task_deferreds = dict()
        self.endpoint_scopes = dict()
        logical_cpu_count = min(multiprocessing.cpu_count(), max_worker_count)
        for i in range(0, logical_cpu_count):
            # start workers and dedicate the last one on a multiprocess
            # system for check operations only (so that registration doesn't
            # block cache checks completely)
            worker = WorkerService("StreamCache Worker #%s" % (i,),
                                   i,
                                   self.work_queue,
                                   (i > 0 and i == logical_cpu_count - 1))
            worker.spawn()
            self.workers.append(worker)

    def add_endpoint_scope(self, ws_port, model_scope):
        if ws_port in self.endpoint_scopes:
            LOG.info("Overwriting untidy port/scope mapping: %s -> %s",
                     ws_port, self.endpoint_scopes.get(ws_port))
        self.endpoint_scopes[ws_port] = model_scope

    def pop_endpoint_scope(self, ws_port):
        key = str(ws_port)
        try:
            return self.endpoint_scopes.pop(key)
        except KeyError:
            return None

    def stop(self):
        for wrk in self.workers:
            wrk.stop()

    def worker_count(self):
        return len([w for w in self.workers if w.is_alive()])

    def _procd_success(self, result, task_key):
        defs = self.task_deferreds.pop(task_key)
        if defs:
            for d in defs[1]:
                d.callback(result)

    def _procd_error(self, error, task_key):
        defs = self.task_deferreds.pop(task_key)
        if defs:
            for d in defs[1]:
                d.errback(error)

    def schedule_task(self, task_cmd, task_params=None):
        task_list = [task_cmd]
        if task_params:
            task_list.extend((str(p) if p else "none" for p in task_params))
        task_str = "\t".join(task_list)
        task_d = self.task_deferreds.get(task_str)

        def deferred_cancel(deferred):
            td = self.task_deferreds.get(task_str)
            if td:
                td[1].remove(deferred)

        d = defer.Deferred(deferred_cancel)

        if not task_d:
            task_d = (defer.Deferred(), [d])
            self.task_deferreds[task_str] = task_d
            task_d[0].addCallbacks(self._procd_success, self._procd_error,
                                   callbackArgs=[task_str],
                                   errbackArgs=[task_str])
            self.work_queue.append((task_d[0], task_str))
            for wrk in self.workers:
                wrk.run_task()
        else:
            task_d[1].append(d)

        return d

    @staticmethod
    def _process_client_response(resp):
        d = defer.Deferred()
        resp.deliverBody(ReadJsonBodyProtocol(d))
        return d

    @defer.inlineCallbacks
    def request_endpoint(self, session_type):
        if session_type == "ssr_session" and not self.broker.has_ssr:
            session_type = "csr_session"
        if not self.broker.has_csr:
            session_type = "ssr_session"
        if not self.broker.has_csr and not self.broker.has_ssr:
            defer.returnValue({
                "renderer": "none",
                "endpoints": {},
                "result": "error",
                "reason": "No CSR or SSR endpoints configured"
            })
            return

        broker_endpoint = self.broker.get_url("api", "spawn")
        LOG.debug("hoops server request: url=%s, class=%s",
                  broker_endpoint, session_type)
        response = yield self.agent.request(
            b"POST", broker_endpoint.encode("utf-8"),
            Headers({'Content-Type': ['application/json']}),
            JsonParamProducer({"class": session_type}))
        json_result = yield self._process_client_response(response)

        if session_type == "ssr_session" and self.broker.has_ssr:
            json_result['renderer'] = "server"
        elif self.broker.has_csr:
            json_result['renderer'] = "client"
        else:
            json_result['renderer'] = "none"
        defer.returnValue(json_result)

    @defer.inlineCallbacks
    def get_hoops_server_status(self):
        response = yield self.agent.request(
            'GET', self.broker.get_url("api", "status"),
            Headers({'Content-Type': ['application/json']}))
        json_result = yield self._process_client_response(response)
        if "status" in json_result:
            result = {"instancesDead": json_result["dead"]}
            defer.returnValue(result)
        else:
            defer.returnValue({"error": "Invalid response from hoops server"})

    def check_model(self, document_id):
        return self.schedule_task("check", [document_id])

    @defer.inlineCallbacks
    def register_model(self, change_response, document_id, with_xml=False):
        cache_state, _ = change_response.split("\t")
        if cache_state == "Changed":
            deferred_result = yield self.schedule_task("register", [document_id])
        else:
            deferred_result = change_response
        result = {"model_result": deferred_result}
        if with_xml:
            _, cache_name = deferred_result.split("\t")
            xml_result = yield self.fetch_xml(model_hash=cache_name)
            result["xml"] = xml_result
        defer.returnValue(result)

    def fetch_xml(self, model_hash):
        return threads.deferToThread(self._thr_fetch_xml, model_hash)

    @staticmethod
    def _thr_fetch_xml(model_hash):
        cache_dir = cache.get_cache_dir()
        xml_path = os.path.join(cache_dir, model_hash + '.xml')
        if os.path.exists(xml_path):
            with io.open(xml_path) as xml_file:
                xml_text = xml_file.read()
        else:
            xml_text = None
        return xml_text


class RegistrationResource(resource.Resource):
    isLeaf = True

    def __init__(self, broker_state_manager, request_endpoints=True):
        resource.Resource.__init__(self)
        self.request_endpoints = request_endpoints
        self.sm = broker_state_manager

    def render_HEAD(self, request):
        return brokerUtil.default_head_response(request)

    def render_OPTIONS(self, request):
        return brokerUtil.default_options_response(request, ["POST", "HEAD", "OPTIONS"])

    def render_POST(self, request):
        brokerUtil.default_head_response(request)

        if request.postpath:
            document_id = request.postpath[0]
        else:
            return '{"success": false, "message": "This resource requires a model id"}'.encode(encoding="utf-8")

        scope = f"threed/broker/{document_id.decode('utf-8')}"
        if not authentication.validate_request(request, scope):
            return b""

        handler = StreamingHandler(request, self.sm, document_id, self.request_endpoints, scope)
        return handler.response()


class TwistedService(object):
    # based on cs.dsig twisted service
    def __init__(self, port, broker, status_file, max_worker_count, iface):
        # set the Twisted factories to silent, so they don't drown our own logging
        Factory.noisy = False
        self.reactor = None
        self.listeners = None

        self.port = port
        self.broker = broker
        self.broker_subprocess = None
        self.iface = iface
        if max_worker_count > 0:
            self.max_worker_count = max_worker_count
        else:
            self.max_worker_count = DEFAULT_MAX_WORKER_COUNT
        self.sm = BrokerStateManager(self.broker, self.max_worker_count)
        self.disable_http2 = False
        if status_file:
            self.status_file = status_file
        else:
            self.status_file = None
        self.quiet = False
        self.openHandshakeTimeout = brokerUtil.read_env_param(
            "THREED_WS_OPEN_CLIENT_TIMEOUT", 60.0)
        self.closeHandshakeTimeout = brokerUtil.read_env_param(
            "THREED_WS_CLOSE_CLIENT_TIMEOUT", 60.0)
        LOG.info("Initializing ThreeD Broker Service")

    def activate_logging(self):
        from twisted.python import log
        # twisted log to cdblog...
        log.startLogging(misc.FileLikeCdblog(loglevel=6), setStdout=self.quiet)

    def setup_root(self):
        register_resource = RegistrationResource(self.sm)
        switch_resource = RegistrationResource(self.sm, request_endpoints=False)
        check_resource = CheckResource(self.sm, self.openHandshakeTimeout,
                                       self.closeHandshakeTimeout)
        self.root = resource.ForbiddenResource()
        self.site = server.Site(self.root)
        if self.disable_http2:
            self.site.acceptableProtocols = lambda: [b"http/1.1"]
        self.root.putChild(b"register", register_resource)
        self.root.putChild(b"registerSwitch", switch_resource)
        self.root.putChild(b"check", check_resource)
        ws_factory = ws_transport.WebSocketTransportServerFactory(self.sm)
        ws_factory.protocol = ws_transport.WebsocketTransportProtocol
        ws_factory.setProtocolOptions(
            webStatus=False,
            openHandshakeTimeout=self.openHandshakeTimeout,
            closeHandshakeTimeout=self.closeHandshakeTimeout)
        self.root.putChild(b"ws", ws_transport.WebSocketTransportResource(ws_factory))

    def activate_tasks(self):
        # Twisted Janitor Task, which removes freed stream cache models
        def clean_streaming_cache():
            self.sm.schedule_task("cleanup")

        # This process will block a worker, so it should be called regularly
        # to avoid long blocking cleaning procedures.
        if self.broker.sid == 1:
            LOG.info("Scheduling hourly reoccurring cache cleanup task")
            clean_task = task.LoopingCall(clean_streaming_cache)
            clean_task.start(3600, now=False)  # call every hour

    def set_quiet(self, quiet):
        self.quiet = quiet

    def _update_status(self, result):
        with open(self.status_file, "wb") as f:
            f.write(str(self.port).encode("utf-8"))
        return result

    def start(self):
        self.reactor = reactor

        self.setup_root()
        self.activate_logging()
        self.activate_tasks()
        from cs.threed.services.broker.network import ServiceNetwork

        self.network = ServiceNetwork(no_http2=self.disable_http2, iface=self.iface)
        deferred = self.network.attach_site(self.site, self.reactor, self.port)
        deferred.addCallback(self._run_reactor)

    def _run_reactor(self, listeners):
        LOG.info("Network listener created %s", [l.getHost() for l in listeners])
        if not listeners:
            self.stop()
            return False
        self.listeners = listeners
        self.broker_subprocess = self.broker.spawn()
        if self.status_file:
            self.broker_subprocess.addCallback(self._update_status)
        try:
            LOG.info("Twisted reactor running")
            ok = self.reactor.run(installSignalHandlers=1)
            LOG.info("Twisted reactor stopped")
            return ok
        except Exception:
            LOG.exception("Twisted reactor exited")
            return False

    def stop(self):
        self.broker.stop()
        self.sm.stop()
        if self.listeners:
            for listener in self.listeners:
                listener.loseConnection()
        if self.reactor and self.reactor.running:
            self.reactor.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Service for Hoops '
                                                 'Communicator Broker Server')
    parser.add_argument('--id', type=int, default=1,
                        help='The ID of the broker service. This ID will be '
                             'added to the configuration files.')
    parser.add_argument('--port', type=int, default=11179,
                        help='port of the registration server (default: 11179)')
    parser.add_argument('--hostname', default="localhost",
                        help='hostname of the broker service and all '
                             'its streaming services')
    parser.add_argument('--max_spawn_count', type=int, default=200,
                        help='Number of streaming instances. Must be bigger than 0 (default: 200)')
    parser.add_argument('--spawn_start_port', default=11200, type=int,
                        help='Port of the first rendering instance. (default 11200)')
    parser.add_argument('--statusfile', default="",
                        help='Path where to write a status file for service '
                             'monitoring.')
    parser.add_argument('--logfile', default="",
                        help='Path to logfile where the output of the service '
                             'is redirected to.')
    parser.add_argument('--max_worker_count', type=int,
                        default=DEFAULT_MAX_WORKER_COUNT,
                        help='Number of the maximun broker service workers. '
                             'If 0, default value will be used. '
                             '(default %d)' % DEFAULT_MAX_WORKER_COUNT)
    parser.add_argument('--interface', default='',
                        help='Make the service bind to specific network interface '
                             'only. If not set or empty, default interface will be used.')
    parser.add_argument('--disable_http2', action='store_true',
                        help='Disallow the service to use HTTP/2 connection '
                             'protocol and stick to HTTP/1.1.')
    parser.add_argument('--csr_enabled', type=int, default=1,
                        help='Enable Client Site rendering')
    parser.add_argument('--ssr_enabled', type=int, default=0,
                        help='Enable Server Site rendering')
    parser.add_argument('-q', action='store_true', help='quiet output')
    args = parser.parse_args()

    # workaround for E048622
    fix_installation()

    if fls.get_server_license("3DSC_001") is True:
        bs = BrokerService(
            sid=args.id,
            server_port=args.port,
            max_spawn_count=args.max_spawn_count,
            csr_enabled=args.csr_enabled == 1,
            ssr_enabled=args.ssr_enabled == 1,
            spawn_start_port=args.spawn_start_port
        )
        svc = TwistedService(args.port, bs, args.statusfile, args.max_worker_count,
                             iface=args.interface)
        svc.set_quiet(args.q)
        svc.disable_http2 = args.disable_http2
        try:
            svc.start()
        finally:
            svc.stop()
    else:
        LOG.critical("License not available. Aborting.")
