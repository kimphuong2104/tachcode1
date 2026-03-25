#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import os
import sys
import traceback
import logging
import cProfile
import datetime
import pstats
import base64
import six
from six.moves import StringIO

from cdb import misc, rte
from cdb import ue
from cs.wsm.pkgserrors import KnownException


WS_PROFILE = "ws_profile"


def setupImportPath(wsmVersion):
    """
    Sets import path for wsm version specific server components.

    WARNING: This is a dangerous operation, potentially opening the door to
             remote code execution. Make sure paths to set are always sanitized!
    """
    base = misc.getConfigValue("CADDOK_BASE")
    if base:
        wsmPath = misc.jail_filename(base, "pkgs", "wsm", wsmVersion)
        if os.path.isdir(wsmPath):
            if wsmPath not in sys.path:
                sys.path.insert(0, wsmPath)
            logging.info("wsm import path set to '%s'", wsmPath)
        else:
            logging.error("wsm import path '%s' does not exist", wsmPath)
    else:
        logging.error("CADDOK_BASE not set")


def version_greater_equal(version1, version2):
    """
    Return True if version1 is considered greater or equal compared to version2.

    :Parameters":
        version1, version2: String
            version strings like "3.14", "15.4.0"
    """
    version1_tuple = tuple([int(v) for v in version1.split(".")])
    version2_tuple = tuple([int(v) for v in version2.split(".")])
    return version1_tuple >= version2_tuple


def processCommand(inputLines, wsVersion, request=None):
    """
    Process 'inputLines' with the WsmCommandProcessor.

    :param wsVersion: str. Version of WSM doing a request/ue call
    :param inputLines: The lines contain the command to be executed.
    :type inputLines: list(str)
    :param request: The request from the web call.
    :type request: webob.Request
    :return: The error code and the base64 encoded response.
    :rtype: tuple(str, str)
    """
    try:
        if version_greater_equal(wsVersion, "15.4.0"):
            # hope WSM will be able to manage version mismatch
            # properly for combinations like cs.workspaces 3.15 + WSM 3.16
            from cs.wsm.pkgs.wsmcommandprocessor import (
                WsmCommandProcessor,
                CompressStream,
            )
            from cs.wsm.pkgs.cmdprocessorbase import WsmCmdErrCodes
        else:
            # SUPPORT FOR WSM < 3.15 where pkgs are located in the instance dir
            setupImportPath(wsVersion)
            from wsmcommandprocessor import WsmCommandProcessor, CompressStream
            from cmdprocessorbase import WsmCmdErrCodes
    except ImportError as e:
        logging.error("importing wsm module failed: %s", e)
        logging.error(traceback.format_exc())
        returnCode = None

        resultLines = ["WSM_IMPORT_ERROR"]
    else:
        returnCode = WsmCmdErrCodes.unknownProcessingError
        try:
            # check if client activated profiling
            profile = False
            if inputLines and inputLines[0] == WS_PROFILE:
                inputLines[:] = inputLines[1:]
                profile = True

            cmdProcessor = WsmCommandProcessor(inputLines)
            if request is not None:
                logging.info(
                    "cdbwsmcommands.processCommand: "
                    "Process command with WsmCommandProcessor "
                    "with web request"
                )
            else:
                logging.info(
                    "cdbwsmcommands.processCommand: "
                    "Process command with WsmCommandProcessor "
                    "without web request"
                )

            if profile:
                logging.info("Performance profiling active")
                prof = cProfile.Profile()
                returnCode, resultLines = prof.runcall(cmdProcessor.process, request)

                timeStamp = datetime.datetime.now().strftime("%y.%m.%d_%H.%M.%S.%f")
                statsStr = StringIO()
                stats = pstats.Stats(prof, stream=statsStr).sort_stats(
                    "cumulative", "time", "calls"
                )
                stats.print_stats(75)
                # client needs marker to distinguish return values from profiling results.
                # return timestamp for logging too
                if six.PY3:
                    encodedStats = base64.standard_b64encode(
                        statsStr.getvalue().encode("utf-8")
                    )
                else:
                    encodedStats = base64.standard_b64encode(statsStr.getvalue())
                resultLines.append(WS_PROFILE + timeStamp + "@" + encodedStats)
            else:
                if request is not None:
                    returnCode, resultLines = cmdProcessor.process(request)
                else:
                    # keep this call for compatibility
                    returnCode, resultLines = cmdProcessor.process()

        except KnownException as e:
            logging.error("An exception occurred calling UE cdbwsmcommands")
            logging.error(six.text_type(e))
            logging.error(traceback.format_exc())
            resultStream = CompressStream()
            resultStream.write(six.text_type(e))
            resultLines = resultStream.lines()
        except Exception as e:
            logging.error("An exception occurred calling UE cdbwsmcommands")
            logging.error(six.text_type(e))
            logging.error(traceback.format_exc())
            resultStream = CompressStream()
            if six.PY2:
                resultStream.write(traceback.format_exc())
            else:
                resultStream.write(traceback.format_exc().encode("utf-8"))
            resultLines = resultStream.lines()
    return returnCode, resultLines


class cdbwsmcommandsadapter:
    """
    Operation to handle XML communication between WSM and CDB server.
    """

    context_name = "cadtalkstdinout"

    def impl(self, ctx):
        logging.info("-----start cdbwsmcommandsadapter.impl(...)")
        wsVersion = rte.environ.get("WS_VERSION")
        returnCode, resultLines = processCommand(ctx.stdin, wsVersion)
        if returnCode is not None:
            ctx.writeln(six.text_type(returnCode))
        for line in resultLines:
            ctx.writeln(line)

        logging.info("-----end cdbwsmcommandsadapter.impl(...)")


if "__main__" == __name__:
    ue.run(cdbwsmcommandsadapter)
