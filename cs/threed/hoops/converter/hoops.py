#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
HOOPS Converter API
###################

|cs.threed| provides a low level API to convert models into several neutral
formats by using the HOOPS Converter Command Line Tool.

This converter should be preferred over the converter found in module
`cs.threed.hoops.converter.csconvert`, if possible.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['Converter', 'check_converter_license', 'check_feature_license']


import cdbwrapc
import itertools
import logging
import os
import sys
import threading

from cdb import fls
from cdb import rte
from cdb import sqlapi
from cdb.plattools import killableprocess

import cs.threedlibs.environment as threedlibs

kSingleCADFeatureId = "3DSC_011"
kMultiCADFeatureId = "3DSC_012"

CONVERTER_LOG = logging.getLogger(__name__ + " CONVERTER")

LOG_ERROR = 0
LOG_WARN = 1
LOG_INFO = 2
LOG_DEBUG = 3

wrapperLocation = os.path.dirname(__file__)
win32 = (sys.platform == "win32")

class HoopsConverterException(Exception):
    pass


def check_feature_license(feat_id, svc_mode):
    if svc_mode:
        fls.allocate_server_license(feat_id)
    else:
        from cdb.platform.lic import FeatureID
        from cdb.platform.gui import Message

        lic_info = fls.get_licsystem_info()
        if not lic_info.get("soed_active", False) and not fls.is_licensed(feat_id):
            feature_obj = FeatureID.ByKeys(id=feat_id)
            label = feat_id
            if feature_obj:
                label = feature_obj.name
            err_msg = Message.GetMessage("cdbfls_nolicforfeature", label)
            raise fls.LicenseError(err_msg, feat_id)


def check_converter_license(file_type, svc_mode):
    def _cad(source):
        return source.split(":")[0]
    try:
        check_feature_license(kMultiCADFeatureId, svc_mode)
    except fls.LicenseError:
        sources = sqlapi.RecordSet2(
            "acs_plg_conv",
            condition="plugin='hoops'",
            columns=["source"]
        )
        cads = set([_cad(source.source) for source in sources])
        if len(cads) == 1 and _cad(file_type) in cads:
            check_feature_license(kSingleCADFeatureId, svc_mode)
        else:
            raise


class Converter(object):
    execPath = threedlibs.HOOPS_CONVERTER_PATH

    def __init__(
        self,
        input_path=None,
        params=None,
        timeout=43200,
        log_fn=None,
        force_xvfb=False,
        service_mode=True
    ):
        """
        Provides an interface for the HOOPS Converter.

        :param input_path:  The path to the input file.

        :param params:  Parameters for the executable as a list of tuples
                        in the following form: (``OPTION``, ``VALUE``).
                        A full list of accepted command line options
                        can be found here:
                        https://docs.techsoft3d.com/communicator/latest/build/api_ref/data_import/converter-command-line-options.html

        :param timeout: Timeout in seconds to wait, until the conversion is forcibly
                        terminated, defaults to 12 hours

        :param log_fn:  The function fn(msg, log_level) to use for logging.
                        log_level can take following values:
                        - 0: error
                        - 1: warning
                        - 2: info
                        - 3: debug

        :param force_xvfb: Boolean to enforce usage of ``xvfb`` if the automatic detection is not sufficient.


        You can generate multiple formats from the same source model with
        one converter call by providing multiple output parameters.

        **Usage**

        .. code-block:: python

            import os
            from cs.threed.hoops.converter import hoops

            source_filepath = os.path.abspath("TopAssembly.CATProduct")

            params = [
                ("output_png", os.path.abspath("TopAssembly.png")),
                ("background_color", "0.75,0.86,0.97"),
                ("output_step": os.path.abspath("TopAssembly.step")
            ]

            converter = hoops.Converter(
                input_path=source_filepath,
                params=params
            )

            converter.execute()

        """

        if input_path and params:
            file_type = cdbwrapc.getFileTypeByFilename(input_path)
            check_converter_license(file_type.getName(), service_mode)

            fixed_params = [
                ("--input", input_path),
                ("--license", threedlibs.SERVER_LICENSE)
            ]

            all_params = params
            all_params.extend(fixed_params)

            self.params = self.format_params(all_params)
            self.timeout = timeout
            self.log_fn = log_fn

            auto_xvfb = "DISPLAY" not in os.environ.keys() or not os.environ["DISPLAY"]
            self.use_xvfb = not win32 and (auto_xvfb or force_xvfb)

        else:
            self.params = []


    @classmethod
    def test(cls):
        """
        Checks if the paths to the conversion program is ok.
        Throws an exception if a path does not exist.

        :return: always True
        :raises: HoopsConverterException
        """
        if not os.path.exists(cls.execPath):
            raise HoopsConverterException("Hoops converter not found: %s", cls.execPath)

        return True

    def format_params(self, params):
        formatted_params = []
        arg_prefix = "--"

        for key, value in params:
            if not key.startswith(arg_prefix):
                key = arg_prefix + key

            formatted_params.append((key, value))

        return formatted_params

    def log(self, msg, log_level=LOG_INFO):
        if self.log_fn:
            self.log_fn(msg, log_level)

    def execute(self):
        """
        Instructs the converter to run the conversion.
        """

        def _execute(args):
            timer = None
            try:
                env = dict(rte.environ)
                process = killableprocess.Popen(args,
                                                stdout=killableprocess.PIPE,
                                                stderr=killableprocess.PIPE,
                                                stdin=killableprocess.PIPE,
                                                env=env)

                if self.timeout > 0:
                    def terminate_proc():
                        CONVERTER_LOG.error("Process timeout: forcing process to terminate\n")
                        process.terminate()

                    timer = threading.Timer(self.timeout, terminate_proc)
                    timer.start()

                stdout, stderr = [msg.decode(encoding='unicode_escape', errors='replace') for msg in process.communicate()]

                CONVERTER_LOG.debug(stdout)
                self.log(stdout)
                if stderr:
                    self.log(stderr)
                    CONVERTER_LOG.error(stderr)

            except Exception:
                raise

            finally:
                if timer is not None:
                    timer.cancel()

        if self.params:
            params = self.params

            if self.use_xvfb:
                args = ["xvfb-run", "-a", self.execPath] + list(itertools.chain(*params))
                try:
                    _execute(args)
                    return
                except Exception as e:
                    CONVERTER_LOG.warn(f"Conversion with 'xvfb-run' failed: {e}. Trying conversion without it.")

            args = [self.execPath] + list(itertools.chain(*params))
            _execute(args)

        else:
            CONVERTER_LOG.error("Either no input path or no parameters specified. No conversion will be run.")
