# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module applicationrpc

This is the documentation for the applicationrpc module.
"""

from __future__ import absolute_import

import json
import os
import logging

from lxml import etree as ElementTree
from cdb import ue
from cdb import sig
from cs.wsm.pkgs.pkgsutils import createErrorElement, createInfoElement
from cs.wsm.pkgs.applrpcutils import RemoteFile, ApplRemoteRpc
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes

__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []


class ApplRpcProcesssor(CmdProcessorBase):
    """
    Handle WSD RPCs for packages
    """

    name = u"application_rpc"

    ERROR_NONE = 0
    ERROR_MESSAGE = 3001
    ERROR_NO_UNIQUE_CONNECTION = 3010
    ERROR_NO_CONNECTION = 3011
    ERROR_OTHER = 3012
    ERROR_INVALID_REPLY = 3013
    ERROR_INVALID_REQUEST = 3014

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
        # <WSCOMMANDS cmd="application_rpc">
        #  <RPCDATA function="<function>">
        #   text=json(server)
        #  </RPCDATA>
        # </WSCOMMANDS>
        # returns:
        # <RPCDATARESULT errocode="<errocode>">
        #   [<ERROR>]
        #   <ERROR>
        #   [<INFO>]
        #   ..
        #   text  = jsonrepcdata
        # <RPCDATARESULT>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
        # <RPCDATARESULT errocode="<errocode>">
        #   [<ERROR>]
        #   <ERROR>
        #   [<INFO>}
        #   ..
        #   text  = jsonrepcdata
        # <RPCDATARESULT>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("RPCDATARESULT")
        errorlist = root
        error_code = self.ERROR_INVALID_REQUEST
        for child in self._rootElement.etreeElem:
            if child.tag == "RPCDATA":
                function_to_call = child.attrib["function"]
                server_data = json.loads(child.text)
                logging.debug(
                    "ApplRpcProcessor: Called for function %s", function_to_call
                )
                if function_to_call and server_data:
                    error_code = self.ERROR_NONE
                    parameter, files = ApplRemoteRpc.from_json(server_data)
                    try:
                        sigresult = sig.emit("ws_appl_function", function_to_call)(
                            parameter, files
                        )
                        if sigresult:
                            if len(sigresult) == 1:
                                result_values = sigresult[0]
                                if len(result_values) == 3:
                                    # res_files: list of cs.wsm.pkgs.apprpcutils.RemoteFile
                                    # errors is a list of tuples, (mesg_id, list of args)
                                    errors, res_values, res_files = result_values
                                    has_error = False
                                    for error in errors:
                                        if error[0] == 1:
                                            errorlist.append(
                                                createErrorElement(error[1], error[2])
                                            )
                                            has_error = True
                                        else:
                                            errorlist.append(
                                                createInfoElement(error[1], error[2])
                                            )
                                    if has_error:
                                        error_code = self.ERROR_MESSAGE
                                    else:
                                        res_data = ApplRemoteRpc.to_json(
                                            res_values, res_files
                                        )
                                        if res_data is not None:
                                            root.text = json.dumps(res_data)
                                        else:
                                            errorlist.append(
                                                createErrorElement(
                                                    "wsm_rpc_data_invalid"
                                                )
                                            )
                                else:
                                    logging.error(
                                        "application_rpc: invalid return values"
                                    )
                                    error_code = self.ERROR_NO_UNIQUE_CONNECTION
                                    errorlist.append(
                                        createErrorElement(
                                            "wsm_rpc_return_invalid",
                                            [str(len(result_values))],
                                        )
                                    )
                            else:
                                logging.error(
                                    "application_rpc: No unique connection(%s)",
                                    len(sigresult),
                                )
                                error_code = self.ERROR_NO_UNIQUE_CONNECTION
                                errorlist.append(
                                    createErrorElement(
                                        "wsm_rpc_connect_error", [str(len(sigresult))]
                                    )
                                )

                        else:
                            logging.error("application_rpc: No connected function")
                            error_code = self.ERROR_NO_CONNECTION
                            errorlist.append(
                                createErrorElement("wsm_rpc_connect_error", ["0"])
                            )
                    except Exception as ex:
                        logging.exception(
                            "application_rpc: Exception in connected method"
                        )
                        error_code = self.ERROR_OTHER
                        errorlist.append(
                            createErrorElement("wsm_rpc_exception", [str(ex)])
                        )
                    finally:
                        # try to cleanup files
                        if files:
                            for f in files:
                                if f.local_fname and os.path.isfile(f.local_fname):
                                    try:
                                        os.unlink(f.local_fname)
                                    except EnvironmentError:
                                        pass
                else:
                    errorlist.append(createErrorElement("wsm_rpc_invalid_input"))
        root.attrib["errorcode"] = str(error_code)
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk
