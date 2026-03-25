#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
HOOPS Converter Wrapper for Command Line Tool (csconvert)
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['Converter']

import cdbwrapc
import os
import sys
import tempfile
import threading
import numbers
import logging
import warnings
from lxml import etree

from cdb import i18n
from cdb import fls
from cdb import rte
from cdb import CADDOK
from cdb.objects import fields, ByID
from cdb.plattools import killableprocess

from cs.threed.variants import get_variant_classes, get_variability_properties_for_pdf_by_signature
from cs.threed.hoops.converter.utils import get_substituted_src_basename, SRC_BASENAME_PLACEHOLDER
import cs.threedlibs.environment as threedlibs

k3DSCJTFeatureId = "3DSC_013"
k3DSCPMIFeatureId = "3DSC_016"
k3DSCViewsFeatureId = "3DSC_017"

CONVERTER_LOG = logging.getLogger(__name__ + " CSCONVERT")

LOG_ERROR = 0
LOG_WARN = 1
LOG_INFO = 2
LOG_DEBUG = 3

wrapperLocation = os.path.dirname(__file__)
win32 = (sys.platform == "win32")



class UnsupportedFormatException (Exception):
    pass


class HoopsConverterException(Exception):
    pass


def is_true(value):
    return (
        value is True
        or value == 1 or value == "1"
        or isinstance(value, str) and value.lower() == "true"
    )


def apply_substitutions(val, substitutions, force_str=False):
    if isinstance(val, str):
        for (old, new) in substitutions.items():
            val = val.replace(old, new)
    elif isinstance(val, bool):
        val = 'true' if val else 'false'
    return str(val) if force_str else val


class Converter(object):
    execPath = threedlibs.CSCONVERT_PATH
    libPath = threedlibs.HOOPS_LIB_PATH
    runtimePath = threedlibs.RUNTIME_PATH

    def __init__(self, wsp_path=None, models=None,
                 params=None, timeout=0, log_fn=None, log_globally=None,
                 additional_attributes=None,
                 variant=None, variability_model_id=None, signature=None, force_xvfb=False,
                 service_mode=True):
        """
        Creates a converter abstraction object.

        Provides an interface to the XML-API of the 3DC Converter.

        :param wsp_path: The workspace path to a folder where the conversion is
            executed at.

        :param models: A collection of objects to extract cad attributes for pdf export.
            The order is relevant: the attributes are extracted on the first feasible object
            on the list.
        :type models: list(cdb.objects.Object)

        :param params: Parameters for the executable
        :param timeout: Timeout to wait, until the conversion is forcibly
                        terminated
        :param log_fn: The function fn(msg, log_level) to use for logging.
                       log_level can take following values:
                       - 0: error
                       - 1: warning
                       - 2: info
                       - 3: debug
        :param additional_attributes: A dictionary containing values for pdf attributes not
            coming from the models. The dictionary is used as a fallback if the attributes
            are not found in models.
        :param variant: A variant object used for filling up a table on the pdf sheet.
        :param variability_model_id: The object id of a variability_model. Specify this if you want
            to export a pdf model for a virtual variant.
        :param signature: The signature of a virtual variant. Specify this if you want
            to export a pdf model.
        :param force_xvfb: Boolean to enforce usage of ``xvfb`` if the automatic detection is not sufficient.
        """
        self.models = models
        self.params = params or []
        self.timeout = timeout
        self.log_fn = log_fn
        self.wsp_path = wsp_path or tempfile.tempdir
        self.substitutions = {}
        self.elements = []
        self.additional_attributes = additional_attributes or {}
        self.variant = variant
        self.variability_model_id = variability_model_id
        self.signature = signature
        self.service_mode = service_mode

        auto_xvfb = "DISPLAY" not in os.environ.keys() or not os.environ["DISPLAY"]
        self.use_xvfb = not win32 and (auto_xvfb or force_xvfb)

        if log_globally is not None:
            warnings.warn("The parameter 'log_globally' has been removed and is not used "
                          "any more. It will be removed in an upcoming release of cs.threed.",
                          DeprecationWarning, stacklevel=2)

    @classmethod
    def test(cls):
        """
        Checks if the paths to the conversion program is ok.
        Throws an exception if a path does not exist.

        :return: always True
        :raises: HoopsConverterException
        """
        if not os.path.exists(cls.execPath):
            raise HoopsConverterException("CSConvert path not found: %s",
                                          cls.execPath)
        if not os.path.exists(cls.libPath):
            raise HoopsConverterException(
                "Hoops library folder not found: %s",
                cls.libPath)
        return True

    def new_conversion(self, input_path=None, substitutions=None, params=None):
        """
        Instructs the converter to make a conversion entry to the xml file.
        All following calls to :func:`add_task` will create tasks in this entry
        until a new call to :func:`new_conversion`.

        :param input_path: The path to the input file. (Optional,
                           but required for tasks with input)
        :param substitutions: A dict of substitutions, which are used to replace
                              occurrences of their ``key`` with ``value`` in
                              the parameter values. This makes it possible to
                              replace e.g. $(SRC_BASENAME) with the actual
                              basename of the output.
        :param params: the parameters for the input task.
        :return: None
        :raises: cdb.fls.LicenseError
        """
        if params is None:
            params = {}

        self.substitutions = substitutions or {}
        conv_el = etree.Element("Conversion")
        if input_path:
            from cs.threed.hoops.converter.hoops import check_converter_license

            file_type = cdbwrapc.getFileTypeByFilename(input_path)
            check_converter_license(file_type.getName(), self.service_mode)

            input_el = etree.SubElement(
                conv_el, "Input",
                {key: "%s" % value for key, value in params.items()}
            )
            input_el.set("path", input_path)
        self.elements.append(conv_el)

    def add_task(self, task_format, params):
        """
        Adds a task to the last called conversion with given parameters.

        :param task_format: the output format. Must be one of
            ``jt``, ``pdf``, ``jpg``, ``prc``, ``step``, ``stl``, ``fbx``.

        :param params: the parameters for the conversion task.

        :return: None
        """
        if not self.elements:
            raise HoopsConverterException(
                "Please create a new conversion first")
        conv_el = self.elements[-1]
        conv_el.append(self._create_task(task_format, params))

    def write_to_file(self, path):
        root_el = etree.Element("CSConvert")
        for el in self.elements:
            root_el.append(el)
        root_tree = etree.ElementTree(root_el)
        root_tree.write(path,
                        pretty_print=True,
                        xml_declaration=True,
                        encoding="utf-8")
        self.log("Taskfile for HoopsConverter wrote to '%s'" % (path,), LOG_DEBUG)

    def run(self, task_filename="converter.xml",
            delete_taskfile=True):
        """
        Executes the conversion.
        :param task_filename: The name of the xml file describing the
                              converson tasks. It will be stored in the
                              workspace of the converter.
        :param delete_taskfile: If set to True, the xml file with the
                                conversion tasks will be removed after
                                conversion has finished.
        :return: None
        """
        task_file_path = os.path.join(self.wsp_path, task_filename)
        try:
            self.write_to_file(task_file_path)
            self._run_exec(task_file_path)
        finally:
            self.substitutions = {}
            self.elements = []
            if delete_taskfile:
                os.remove(task_file_path)

    def log(self, msg, log_level=LOG_INFO):
        if self.log_fn:
            self.log_fn(msg, log_level)

    def check_path(self, path):
        if not os.path.isabs(path):
            return os.path.join(self.wsp_path, path)
        return path

    def _run_exec(self, batch_file_path=None, execPath=None, params=None):

        def _execute(args):
            timer = None
            try:
                self.log("Running: %s\n" % killableprocess.list2cmdline(args))
                env = dict(rte.environ)
                if "CADDOK_DEBUG" not in env:
                    env["CADDOK_DEBUG"] = "ALL.ANY:ts:nr:log:lev=6"
                if not win32:
                    env["LD_LIBRARY_PATH"] = "%s:%s" % (
                        self.libPath,
                        env.get("LD_LIBRARY_PATH", ""))
                else:
                    # prefer system runtime libs to embedded ones, due to
                    # security considerations. (system libs can be more up-to-date)
                    env["PATH"] = "%s;%s;%s" % (
                        self.libPath, env.get("PATH", ""),
                        self.runtimePath)
                process = killableprocess.Popen(args,
                                                stdout=killableprocess.PIPE,
                                                stderr=killableprocess.PIPE,
                                                stdin=killableprocess.PIPE,
                                                env=env)

                if self.timeout > 0:
                    def terminate_proc():
                        self.log("Process timeout: forcing process to terminate\n", LOG_ERROR)
                        process.terminate()

                    timer = threading.Timer(self.timeout, terminate_proc)
                    timer.start()

                stdout, stderr = process.communicate()
                retcode = process.poll()
                if retcode:
                    raise killableprocess.CalledProcessError(
                        retcode, args, output="\n".join([stdout, stderr]))
                CONVERTER_LOG.debug(stdout)
                if stderr:
                    if SRC_BASENAME_PLACEHOLDER in self.substitutions.keys():
                        source_file_name = os.path.split(self.substitutions[SRC_BASENAME_PLACEHOLDER])[1]
                        stderr = f"{stderr} (Source file of conversion: {source_file_name})"

                    self.log(stderr)
                    CONVERTER_LOG.error(stderr)

            except Exception:
                raise

            finally:
                if timer is not None:
                    timer.cancel()

        if execPath is None:
            execPath = self.execPath

        if params is None:
            params = self.params

        params = [apply_substitutions(p, self.substitutions) for p in params]
        args = [execPath] + params

        if batch_file_path is not None:
            args.append(batch_file_path)

        if self.use_xvfb:
            xvfb_run_args = ["xvfb-run", "-a"] + args
            try:
                _execute(xvfb_run_args)
                return
            except Exception as e:
                CONVERTER_LOG.warn(f"Conversion with 'xvfb-run' failed: {e}. Trying conversion without it.")

        _execute(args)

    def _create_task(self, task_format, params):
        if task_format.upper() == "JT":
            from cs.threed.hoops.converter.hoops import check_feature_license
            check_feature_license(k3DSCJTFeatureId, self.service_mode)

        params = self.process_params(params)
        if task_format == "pdf":
            task_el = self._create_pdf_tag(params)
        else:
            task_el = self._create_format_tag(task_format, params)

        for (param_key, param_value) in params.items():
            if isinstance(param_value, (numbers.Number, str, bool)):
                # only append simple types to the task element
                # bool is a subclass of int, but keep it in for clarity
                task_el.set(param_key, str(param_value))
        return task_el

    def process_params(self, params):
        result = {}

        for (key, value) in params.items():
            if key == "output" and SRC_BASENAME_PLACEHOLDER in list(self.substitutions.keys()):
                result[key] = get_substituted_src_basename(value, self.substitutions[SRC_BASENAME_PLACEHOLDER])
            else:
                result[key] = apply_substitutions(value, self.substitutions)

        return result

    def _create_format_tag(self, task_format, params):
        # xml attributes must be unicode strings for lxml
        path = str(params.pop("output"))

        task_el = etree.Element("Format" + task_format.upper())
        output_element = etree.SubElement(task_el, "Output")
        output_element.set("path", self.check_path(path))

        return task_el

    def _create_pdf_tag(self, params):
        from cs.threed.hoops.converter.hoops import check_feature_license
        db_attribute_map = params.pop("db_attribute_map", {})
        cad_attribute_map = params.pop("cad_attribute_map", {})
        attributes_callback = params.pop("attributes_callback", None)
        lang = params.pop("pdf_lang", i18n.default())

        def read_attr(obj, attr):
            fd = obj.GetFieldByName(attr)
            if fd:
                if isinstance(fd, fields.MultiLangAttributeDescriptor):
                    return obj.GetLocalizedValue(attr, lang)
                else:
                    return getattr(obj, attr)

        def create_variant_tag(parent, variant_or_signature):
            from cs.threed.hoops import utils
            args = {}
            if isinstance(variant_or_signature, get_variant_classes()):
                variant = variant_or_signature
                args["id"] = "%s" % variant.id
                # IMPORTANT: this should match the view name in the PRC-file
                args["name"] = utils.variant_name(variant)
                props = variant.get_variability_properties_for_pdf(lang)
            else:
                args["name"] = variant_or_signature
                props = get_variability_properties_for_pdf_by_signature(
                    self.variability_model_id, variant_or_signature, lang
                )

            if props:
                variant_tag = etree.SubElement(parent, "Variant", args)
                for (name, value) in props:
                    etree.SubElement(variant_tag, "Property", {
                        "name": name,
                        "value": "%s" % value
                    })

        # allocate pdf licenses
        if "populate_pmi_fields" in params and is_true(params["populate_pmi_fields"]):
            check_feature_license(k3DSCPMIFeatureId, self.service_mode)
        if "make_view_pages" in params and is_true(params["make_view_pages"]):
            check_feature_license(k3DSCViewsFeatureId, self.service_mode)

        task_el = self._create_format_tag("pdf", params)

        # get attributes for the text fields
        attributes_el = etree.SubElement(task_el, "PDFAttributes")
        if db_attribute_map and not self.models:
            raise HoopsConverterException("Cannot set pdf attributes without "
                                          "a model.")

        db_attributes = {}
        for attr_key, attr_value in db_attribute_map.items():
            value = self.additional_attributes.get(attr_value, "")
            for model in self.models:
                if hasattr(model, attr_value):
                    value = read_attr(model, attr_value)
                    db_attributes[attr_key] = value
                    break

        # callback to modify the attributes before conversion
        if attributes_callback is not None:
            attributes_callback(self.models, db_attributes)

        db_attributes_el = etree.SubElement(attributes_el, "DBAttributes")
        for key, value in db_attributes.items():
            db_attr_el = etree.SubElement(db_attributes_el, key)
            db_attr_el.text = str(value) if value is not None else ""

        cad_attributes_el = etree.SubElement(attributes_el, "CADAttributes")
        for attr_key, attr_value in cad_attribute_map.items():
            cad_attr_el = etree.SubElement(cad_attributes_el, attr_key)
            cad_attr_el.text = attr_value

        # get variant table
        props = None
        variant_name_field = params.pop("variant_name_field", None)

        if self.variant is not None:
            if variant_name_field is not None:
                db_attr_el = etree.SubElement(db_attributes_el, variant_name_field)
                db_attr_el.text = self.variant.name

            if isinstance(self.variant, get_variant_classes()):
                create_variant_tag(task_el, self.variant)
        elif self.variability_model_id is not None and self.signature:
            create_variant_tag(task_el, self.signature)
        elif self.variability_model_id is not None:
            variability_object = ByID(self.variability_model_id)
            if variability_object is not None:
                for variant in variability_object.Variants:
                    create_variant_tag(task_el, variant)

        return task_el
