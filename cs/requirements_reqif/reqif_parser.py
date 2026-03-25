# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function
import collections
import datetime
import gc
import hashlib
import json
import logging
import os
import shutil
import tempfile
import zipfile

from lxml import etree
from lxml.etree import DocumentInvalid, XMLSyntaxError

from cdb import ElementsError
from cs.classification.util import convert_datestr_to_datetime
from cs.requirements.rqm_utils import multireplace
from cs.requirements_reqif.exceptions import ReqIFValidationError
from cs.requirements_reqif.reqif_validator import ReqIFValidator
from cs.requirements_reqif.reqif_export_ng import ReqIFNodes
from cs.requirements.richtext import RichTextModifications

LOG = logging.getLogger(__name__)


class ReqIFStopProcessingException(BaseException):
    pass


class ReqIFParser(object):

    def __init__(
            self,
            reqif_files,
            metadata_callback=None,
            max_in_memory_validation_size=10 * 1024 * 1024,
            progress_callback=None,
            convert_types=True  # whether to convert "1" to 1, "1.0" to 1.0 or a date string to a datetime object
    ):
        self.data_types = {}
        self.data_type_enum_values = {}
        self.data_type_usages = collections.defaultdict(list)
        self.specifications = collections.OrderedDict()
        self.specification_types = {}
        self.spec_objects = collections.OrderedDict()
        self.spec_object_types = {}
        self.spec_relations = {}
        self.spec_relation_types = {}
        self.relation_group_types = {}
        self.spec_hierarchies = {}
        self.spec_hierarchy_tree = collections.defaultdict(list)
        self.relation_groups = {}
        self.reqif_file_names = reqif_files
        self.all_tag_types = set()
        self.spec_attributes = collections.defaultdict(dict)
        self.current_enum_values = collections.OrderedDict()
        self.current_data_type = None
        self.current_specification_type = None
        self.current_spec_object_type = None
        self.current_spec_object_ref = []
        self.current_spec_relation_type = None
        self.current_spec_relation_ref = None
        self.current_relation_group_type = None
        self.current_spec_hierarchy = None
        self.parent_spec_hierarchies_stack = []
        self.current_attribute_definition_type = None
        self.current_attribute_value = None
        self.current_attribute_values = None
        self.current_spec_relations = None
        self.current_the_value = None
        self.current_xhtml_content = None
        self.current_xhtml_content_level = 0
        self.current_type = None
        self.current_default_value = None
        self.current_specification = None
        self.current_spec_object = None
        self.current_spec_relation = None
        self.current_spec_relation_source_object_ref = None
        self.current_spec_relation_target_object_ref = None
        self.current_relation_group_type = None
        self.current_spec_relation_source_object_ref = None
        self.current_spec_relation_target_object_ref = None
        self.current_xhtml_object_content_level = 0
        self.object_references = collections.defaultdict(list)
        self.metadata_callback = metadata_callback
        self._processing_time = None
        self.is_default_value = False
        self.tool_extension_active = False
        self.max_in_memory_validation_size = max_in_memory_validation_size
        self.schema = ReqIFValidator().schema
        self.current_processing_line = 0
        self.lines_per_file = {'__all__': 0}
        self.convert_types = convert_types
        self.progress_callback = progress_callback
        ReqIFNodes.register_namespaces()

    def __enter__(self):
        self.process([self.all])
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        gc.collect()

    @classmethod
    def get_value(cls, value, data_type):
        convert_map = {
            'boolean': lambda x: True if x else False,
            'integer': lambda x: int(x),
            'real': lambda x: float(x),
            'date': lambda x: convert_datestr_to_datetime(x)
        }
        if data_type in convert_map:
            value['THE-VALUE'] = convert_map[data_type](value['THE-VALUE'])
        return value

    @staticmethod
    def count_lines(f):
        cnt = 0
        with open(f, "rb") as f2:
            for _line in f2:
                cnt += 1
        return cnt

    def process(self, handlers):
        # do sax processing of the file
        start = datetime.datetime.now()
        for reqif_file in self.reqif_file_names:
            self.lines_per_file[reqif_file] = self.count_lines(reqif_file)
            self.lines_per_file['__all__'] += self.lines_per_file[reqif_file]
        for reqif_file in self.reqif_file_names:
            LOG.debug('process: %s', reqif_file)
            try:
                for event, element in etree.iterparse(
                    source=reqif_file,
                    events=('start', 'end'),
                    schema=self.schema,
                    remove_blank_text=True,
                    no_network=True
                ):
                    try:
                        if self.progress_callback:
                            self.current_processing_line = element.sourceline
                        for handler in handlers:
                            handler(self, event, element)
                        if self.progress_callback:
                            self.progress_callback(
                                reqif_file,
                                (
                                    float(self.current_processing_line) / self.lines_per_file[reqif_file]
                                ) * 100.0,
                                (
                                    float(self.current_processing_line) / self.lines_per_file['__all__']
                                ) * 100.0,
                            )
                    except ReqIFStopProcessingException:
                        LOG.debug('stop after meta model')
                        break
            except (DocumentInvalid, XMLSyntaxError) as e:
                if isinstance(reqif_file, str) and os.stat(reqif_file).st_size < self.max_in_memory_validation_size:
                    with open(reqif_file) as f:
                        ReqIFValidator().is_valid(f, incremental=False)
                raise ReqIFValidationError("{} - {}".format(e, reqif_file))
        end = datetime.datetime.now()
        processing_time = (end - start).total_seconds()
        LOG.debug('processing took: %ss', processing_time)
        self._processing_time = processing_time

    @classmethod
    def handle_specification_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}specification":
            obj.current_specification = {name: value for (name, value) in element.items()}
            obj.current_attribute_values = []

    @classmethod
    def handle_specification_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}specification":
            spec = obj.current_specification
            spec.update({
                'type': obj.current_specification_type,
                'values': obj.current_attribute_values
            })
            obj.specifications[spec.get('IDENTIFIER')] = spec
            obj.current_specification_type = None
            obj.current_specification = None
            obj.current_attribute_values = None
            element.clear()

    @classmethod
    def handle_spec_types(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-types":
            element.clear()
            if obj.metadata_callback and callable(obj.metadata_callback):
                obj.metadata_callback(obj)

    @classmethod
    def handle_specification_types(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}specification-type":
            obj.specification_types[element.attrib.get('IDENTIFIER')] = dict(element.attrib)
            obj.current_specification_type = element.attrib.get('IDENTIFIER')
            obj.current_type = element.attrib.get('IDENTIFIER')

    @classmethod
    def handle_specification_type_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}specification-type-ref":
            obj.current_specification_type = element.text
            element.clear()

    @classmethod
    def handle_spec_object_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-object":
            obj.current_spec_object = {name: value for (name, value) in element.items()}
            obj.current_attribute_values = []

    @classmethod
    def handle_spec_object_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-object":
            spec_object = obj.current_spec_object
            spec_object.update({
                'type': obj.current_spec_object_type,
                'values': obj.current_attribute_values
            })
            obj.spec_objects[spec_object.get('IDENTIFIER')] = spec_object
            obj.current_spec_object_type = None
            obj.current_spec_object = None
            obj.current_attribute_values = None
            element.clear()

    @classmethod
    def handle_spec_object_types(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-object-type":
            obj.spec_object_types[element.attrib.get('IDENTIFIER')] = dict(element.attrib)
            obj.current_spec_object_type = element.attrib.get('IDENTIFIER')
            obj.current_type = element.attrib.get('IDENTIFIER')

    @classmethod
    def handle_spec_object_type_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-object-type-ref":
            obj.current_spec_object_type = element.text
            element.clear()

    @classmethod
    def handle_spec_object_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-object-ref":
            obj.current_spec_object_ref.append(element.text)
            element.clear()

    @classmethod
    def handle_source(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}source":
            obj.current_spec_relation_source_object_ref = obj.current_spec_object_ref.pop()
            element.clear()

    @classmethod
    def handle_target(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}target":
            obj.current_spec_relation_target_object_ref = obj.current_spec_object_ref.pop()
            element.clear()

    @classmethod
    def handle_spec_relation_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-relation":
            obj.current_spec_relation = {name: value for (name, value) in element.items()}
            obj.current_attribute_values = []

    @classmethod
    def handle_spec_relation_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-relation":
            spec_relation = obj.current_spec_relation
            spec_relation.update({
                'type': obj.current_spec_relation_type,
                'source': obj.current_spec_relation_source_object_ref,
                'target': obj.current_spec_relation_target_object_ref,
                'values': obj.current_attribute_values
            })
            obj.spec_relations[spec_relation.get('IDENTIFIER')] = spec_relation
            obj.current_spec_relation_type = None
            obj.current_spec_relation = None
            obj.current_attribute_values = None
            obj.current_spec_relation_source_object_ref = None
            obj.current_spec_relation_target_object_ref = None
            element.clear()

    @classmethod
    def handle_spec_relation_types(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-relation-type":
            obj.spec_relation_types[element.attrib.get('IDENTIFIER')] = dict(element.attrib)
            obj.current_spec_relation_type = element.attrib.get('IDENTIFIER')
            obj.current_type = element.attrib.get('IDENTIFIER')

    @classmethod
    def handle_spec_relation_type_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-relation-type-ref":
            obj.current_spec_relation_type = element.text
            element.clear()

    @classmethod
    def handle_spec_relation_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-relation-ref":
            obj.current_spec_relation_ref = element.text
            obj.current_spec_relations.append(element.text)
            element.clear()

    @classmethod
    def handle_relation_group_types(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}relation-group-type":
            obj.relation_group_types[element.attrib.get('IDENTIFIER')] = dict(element.attrib)
            obj.current_type = element.attrib.get('IDENTIFIER')
            element.clear()

    @classmethod
    def handle_relation_group_type_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}relation-group-type-ref":
            obj.current_relation_group_type = element.text
            element.clear()

    @classmethod
    def handle_relation_group_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}relation-group":
            obj.current_relation_group = {name: value for (name, value) in element.items()}
            obj.current_spec_relations = []

    @classmethod
    def handle_relation_group_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}relation-group":
            relation_group = obj.current_relation_group
            relation_group.update({
                'type': obj.current_spec_relation_type,
                'source-specification': obj.current_relation_group_source_ref,
                'target-specification': obj.current_relation_group_target_ref,
                'spec-relations': obj.current_spec_relations
            })
            obj.relation_groups[relation_group.get('IDENTIFIER')] = relation_group
            obj.current_relation_group_type = None
            obj.current_relation_group = None
            obj.current_spec_relations = None
            obj.current_spec_relation_source_object_ref = None
            obj.current_spec_relation_target_object_ref = None
            element.clear()

    @classmethod
    def handle_source_specification(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}source-specification":
            obj.current_relation_group_source_ref = element.text
            element.clear()

    @classmethod
    def handle_target_specification(cls, obj, event, element):
        if event == 'end' and element.tag.lower() == "{http://www.omg.org/spec/reqif/20110401/reqif.xsd}target-specification":
            obj.current_relation_group_target_ref = element.text
            element.clear()

    @classmethod
    def handle_attribute_definition_type_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}attribute-definition-") and not element.tag.lower().endswith('-ref'):
            attribute_definition_type = {name: value for (name, value) in element.items()}
            obj.current_attribute_definition_type = attribute_definition_type
            obj.spec_attributes[obj.current_type][attribute_definition_type.get('IDENTIFIER')] = attribute_definition_type

    @classmethod
    def handle_default_value_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}default-value"):
            obj.is_default_value = True

    @classmethod
    def handle_attribute_value_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}attribute-value-"):
            attribute_value = {name: value for (name, value) in element.items()}
            obj.current_attribute_value = attribute_value

    @classmethod
    def handle_object_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.w3.org/1999/xhtml}object"):
            obj.current_xhtml_object_content_level += 1

    @classmethod
    def handle_object_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.w3.org/1999/xhtml}object"):
            obj.current_xhtml_object_content_level -= 1
            element_attributes = element.attrib
            if 'data' in element_attributes:
                # variables do not have data attribute/a valid url
                obj.object_references[element_attributes.get('data')].append({
                    'spec_object_id': obj.current_spec_object.get('IDENTIFIER'),
                    'type': element_attributes.get('type')
                })

    @classmethod
    def handle_div_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.w3.org/1999/xhtml}div"):
            obj.current_xhtml_content_level += 1

    @classmethod
    def handle_div_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.w3.org/1999/xhtml}div"):
            obj.current_xhtml_content_level -= 1
            cls.handle_most_outer_xhtml_element(obj, event, element)

    @classmethod
    def handle_most_outer_xhtml_element(cls, obj, event, element):
        # check if most outer div
        if obj.current_xhtml_content_level == 0:
            xhtml_content = (
                etree.tostring(
                    element, method=RichTextModifications.DEFAULT_SERIALIZATION
                )
            )
            replacements = {}
            # remove xmlns attributes and force xhtml namespace id to be 'xhtml'
            xhtml_ns_ids = []
            for ns_id, ns_uri in element.nsmap.items():
                if ns_uri == 'http://www.w3.org/1999/xhtml':
                    xhtml_ns_ids.append(ns_id)
                replacements[
                    ' {xmlns}="{ns_uri}"'.format(
                        xmlns='xmlns:{}'.format(ns_id) if ns_id is not None else 'xmlns',
                        ns_uri=ns_uri
                    )
                ] = ''
            for xhtml_ns_id in xhtml_ns_ids:
                if xhtml_ns_id != 'xhtml':
                    replacements['<{}:'.format(xhtml_ns_id)] = '<xhtml:'
                    replacements['</{}:'.format(xhtml_ns_id)] = '</xhtml:'

            obj.current_xhtml_content = multireplace(xhtml_content.decode(), replacements=replacements)
            element.clear()

    @classmethod
    def handle_p_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.w3.org/1999/xhtml}p"):
            obj.current_xhtml_content_level += 1

    @classmethod
    def handle_p_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.w3.org/1999/xhtml}p"):
            obj.current_xhtml_content_level -= 1
            cls.handle_most_outer_xhtml_element(obj, event, element)

    @classmethod
    def handle_the_value_end(cls, obj, event, element):
        # ReqIF defines THE-VALUE to have a child element of XHTML-CONTENT which refers to xhtml.BlkStruct.class.
        # as of w3.org/TR/xhtml11/xhtml11_schema.html xhtml.BlkStruct.class can be a div or p element
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}the-value"):
            if obj.current_attribute_value is not None and obj.current_xhtml_content is not None:
                obj.current_attribute_value['THE-VALUE'] = obj.current_xhtml_content

            obj.current_xhtml_content = None
            element.clear()

    @classmethod
    def handle_the_original_value_end(cls, obj, event, element):
        # ReqIF defines THE-VALUE to have a child element of XHTML-CONTENT which refers to xhtml.BlkStruct.class.
        # as of w3.org/TR/xhtml11/xhtml11_schema.html xhtml.BlkStruct.class can be a div or p element
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}the-original-value"):
            if obj.current_attribute_value is not None and 'the-original-value' not in obj.current_attribute_value and obj.current_xhtml_content is not None:
                obj.current_attribute_value['the-original-value'] = obj.current_xhtml_content
            obj.current_xhtml_content = None
            element.clear()

    @classmethod
    def handle_attribute_value_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}attribute-value-"):
            data_type = element.tag.lower().replace('{http://www.omg.org/spec/reqif/20110401/reqif.xsd}attribute-value-', '')
            if (
                data_type == "enumeration" and 
                obj.current_attribute_value is not None and 
                "values" not in obj.current_attribute_value
            ): # in case of empty values ensure that the key is there and contains an empty list - see E075261
                obj.current_attribute_value["values"] = []
            # convert strings to integers, floats, ...
            if obj.convert_types:
                value = cls.get_value(obj.current_attribute_value, data_type)
            else:
                value = obj.current_attribute_value
            if obj.current_attribute_definition_type and obj.is_default_value:
                obj.spec_attributes[obj.current_type][obj.current_attribute_definition_type['IDENTIFIER']]['default'] = value
            elif obj.current_spec_object or obj.current_specification or obj.current_spec_relation:
                obj.current_attribute_values.append(value)
            else:
                raise ValueError('invalid reqif: %s %s %s' % (etree.tostring(element), obj.is_default_value, obj.current_attribute_definition_type))
            obj.current_attribute_value = None
            element.clear()

    @classmethod
    def handle_default_value_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}default-value"):
            obj.is_default_value = False
            element.clear()

    @classmethod
    def handle_attribute_definition_type_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}attribute-definition-") and element.tag.lower().endswith('-ref'):
            if obj.current_attribute_value is not None:
                obj.current_attribute_value['definition'] = element.text
            element.clear()

    @classmethod
    def handle_attribute_definition_type_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}attribute-definition-") and not element.tag.lower().endswith('-ref'):
            obj.current_attribute_definition_type = None
            element.clear()

    @classmethod
    def handle_datatype_definition_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}datatype-definition-") and element.tag.lower().endswith('-ref'):
            try:
                obj.spec_attributes[obj.current_type][obj.current_attribute_definition_type['IDENTIFIER']]['type'] = element.text
                obj.data_type_usages[element.text].append(obj.current_attribute_definition_type['IDENTIFIER'])
            except TypeError:
                if obj.tool_extension_active:
                    LOG.warn('failed datatype_definition_ref in tool extensions: %s %s %s', obj.current_type, obj.current_attribute_definition_type, element.text)
                else:
                    LOG.error('failed datatype_definition_ref: %s %s %s', obj.current_type, obj.current_attribute_definition_type, element.text)
                    raise
            element.clear()

    @classmethod
    def handle_req_if_tool_extension_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}req-if-tool-extension"):
            obj.tool_extension_active = True

    @classmethod
    def handle_req_if_tool_extension_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}req-if-tool-extension"):
            obj.tool_extension_active = False
            element.clear()

    @classmethod
    def handle_datatype_definition_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}datatype-definition-") and not element.tag.lower().endswith('-ref'):
            obj.current_data_type = element
            obj.current_enum_values = collections.OrderedDict()

    @classmethod
    def handle_enum_value_ref(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}enum-value-ref"):
            if obj.current_attribute_value is not None and 'values' not in obj.current_attribute_value:
                obj.current_attribute_value['values'] = [element.text]
            elif obj.current_attribute_value is not None and 'values' in obj.current_attribute_value:
                obj.current_attribute_value['values'].append(element.text)
            elif obj.tool_extension_active:
                LOG.warn('failed enum_value_ref in tool extensions: %s %s', obj.current_attribute_value, element.attrib)
            else:
                raise ValueError('failed enum_value_ref in tool extensions: %s %s', obj.current_attribute_value, element.attrib)
            element.clear()

    @classmethod
    def handle_enum_value(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}enum-value") and not element.tag.lower().endswith('-ref'):
            enum = {name: value for (name, value) in element.items()}
            obj.current_enum_values[enum.get('IDENTIFIER')] = enum
            element.clear()

    @classmethod
    def handle_datatype_definition_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}datatype-definition-") and not element.tag.lower().endswith('-ref'):
            data_type = {name: value for (name, value) in obj.current_data_type.items()}
            data_type['type'] = element.tag.lower().replace('{http://www.omg.org/spec/reqif/20110401/reqif.xsd}datatype-definition-', '')
            obj.data_types[data_type.get('IDENTIFIER')] = data_type
            if 'enumeration' in element.tag.lower():
                obj.data_type_enum_values[data_type.get('IDENTIFIER')] = obj.current_enum_values
            element.clear()

    @classmethod
    def handle_spec_hierarchy_start(cls, obj, event, element):
        if event == 'start' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-hierarchy"):
            obj.current_spec_hierarchy = {name: value for (name, value) in element.items()}
            obj.parent_spec_hierarchies_stack.append(obj.current_spec_hierarchy)

    @classmethod
    def handle_spec_hierarchy_end(cls, obj, event, element):
        if event == 'end' and element.tag.lower().startswith("{http://www.omg.org/spec/reqif/20110401/reqif.xsd}spec-hierarchy"):
            if len(obj.parent_spec_hierarchies_stack) > 0:
                current = obj.parent_spec_hierarchies_stack.pop()
                current['object'] = obj.current_spec_object_ref.pop()
                current_identifier = current.get('IDENTIFIER')
                obj.spec_hierarchies[current_identifier] = current
                if len(obj.parent_spec_hierarchies_stack) > 0:
                    obj.spec_hierarchy_tree[obj.parent_spec_hierarchies_stack[-1].get('IDENTIFIER')].append(current_identifier)
                else:
                    obj.spec_hierarchy_tree[obj.current_specification.get('IDENTIFIER')].append(current_identifier)
                obj.current_spec_hierarchy = None
            element.clear()

    @classmethod
    def all_tags(cls, obj, event, element):
        obj.all_tag_types.add(element.tag.lower())

    @classmethod
    def all(cls, obj, event, element):
        # cls.all_tags(obj, event, element)
        # data types
        cls.handle_datatype_definition_start(obj, event, element)
        cls.handle_enum_value(obj, event, element)
        cls.handle_datatype_definition_end(obj, event, element)
        # entity types
        cls.handle_specification_types(obj, event, element)
        cls.handle_specification_type_ref(obj, event, element)
        cls.handle_spec_object_types(obj, event, element)
        cls.handle_spec_object_type_ref(obj, event, element)
        cls.handle_spec_relation_types(obj, event, element)
        cls.handle_spec_relation_type_ref(obj, event, element)
        cls.handle_relation_group_types(obj, event, element)
        # attribute definitions
        cls.handle_attribute_definition_type_start(obj, event, element)
        cls.handle_datatype_definition_ref(obj, event, element)
        cls.handle_default_value_start(obj, event, element)
        cls.handle_default_value_end(obj, event, element)
        cls.handle_enum_value_ref(obj, event, element)
        cls.handle_attribute_definition_type_end(obj, event, element)
        # attribute values
        cls.handle_attribute_value_start(obj, event, element)
        cls.handle_attribute_definition_type_ref(obj, event, element)
        cls.handle_div_start(obj, event, element)
        cls.handle_object_start(obj, event, element)
        cls.handle_object_end(obj, event, element)
        cls.handle_div_end(obj, event, element)
        cls.handle_p_start(obj, event, element)
        cls.handle_p_end(obj, event, element)
        cls.handle_the_value_end(obj, event, element)
        cls.handle_the_original_value_end(obj, event, element)
        cls.handle_attribute_value_end(obj, event, element)
        cls.handle_spec_types(obj, event, element)
        # spec objects
        cls.handle_spec_object_start(obj, event, element)
        cls.handle_spec_object_end(obj, event, element)
        # spec relations
        cls.handle_spec_relation_start(obj, event, element)
        cls.handle_source(obj, event, element)
        cls.handle_target(obj, event, element)
        cls.handle_spec_relation_end(obj, event, element)
        # specifications
        cls.handle_specification_start(obj, event, element)
        cls.handle_spec_hierarchy_start(obj, event, element)
        cls.handle_spec_object_ref(obj, event, element)
        cls.handle_spec_hierarchy_end(obj, event, element)
        cls.handle_specification_end(obj, event, element)
        # relation groups
        cls.handle_relation_group_start(obj, event, element)
        cls.handle_relation_group_type_ref(obj, event, element)
        cls.handle_source_specification(obj, event, element)
        cls.handle_target_specification(obj, event, element)
        cls.handle_spec_relation_ref(obj, event, element)
        cls.handle_relation_group_end(obj, event, element)
        # tool extensions
        cls.handle_req_if_tool_extension_start(obj, event, element)
        cls.handle_req_if_tool_extension_end(obj, event, element)

    @classmethod
    def to_dict(cls, obj):
        return {
            "data_types": obj.data_types,
            "data_type_enum_values": obj.data_type_enum_values,
            "data_type_usages": obj.data_type_usages,
            "specifications": obj.specifications,
            "specification_types": obj.specification_types,
            "spec_objects": obj.spec_objects,
            "spec_object_types": obj.spec_object_types,
            "spec_relations": obj.spec_relations,
            "spec_relation_types": obj.spec_relation_types,
            "relation_groups": obj.relation_groups,
            "relation_group_types": obj.relation_group_types,
            "reqif_file_names": obj.reqif_file_names,
            "_all_tag_types_": list(obj.all_tag_types),
            "spec_attributes": obj.spec_attributes,
            "spec_hierarchies": obj.spec_hierarchies,
            "spec_hierarchy_tree": obj.spec_hierarchy_tree,
            "object_references": obj.object_references,
            "_processing_time_": obj._processing_time,
            "__count_of_specifications__": len(obj.specifications),
            "__count_of_spec_objects__": len(obj.spec_objects),
        }

    @classmethod
    def get_enum_value(cls, obj, attribute_identifier, enum_identifier):
        for possible_enum_val in obj.data_type_enum_values.get(attribute_identifier, []):
            if possible_enum_val.get('IDENTIFIER') == enum_identifier:
                return possible_enum_val


class ReqIFzHandler(object):

    def __init__(self, filepath, remove_tempdir=True, hashes=None):
        """
        ReqIFzHandler works as a context manager to ensure that an underlying parser or importer
        can directly use the files contained in a possible .reqifz file as follows:

        with ReqIFzHandler(filepath) as (
            reqif_files, binary_files, extraction_time
        ):
            print(
                '%s contain reqif files: %s and binary files: %s - extraction took %s s' % (
                    filepath, reqif_files, binary_files, extraction_time
                )
            )

        If remove_tempdir is set (which it is by default) the temporary directory is removed
         at the end.
        hashes can be set to a list of hash names e.g. ['md5', 'sha256'] then each binary file in
        binary_files contain a hash key of hashes for the binary_file
        """
        self.filepath = filepath
        self.reqif_files = []
        self.binary_blobs = {}
        self.tempdir = tempfile.mkdtemp()
        self.remove_tempdir = remove_tempdir
        self.extraction_time = None
        self.hashes = hashes

    def _calculate_hashes(self, file_name, file_path):
        if self.hashes:
            hashes_to_update = {}
            for hash_name in self.hashes:
                hasher = getattr(hashlib, hash_name)()
                hashes_to_update[hash_name] = hasher
            size = 0
            with open(file_path, 'rb') as f:
                while True:
                    content = f.read(16 * 1024 * 1024)  # 16 MB chunks should fast enough
                    if not content:
                        break
                    for hash_name, hasher in hashes_to_update.items():
                        hasher.update(content)
                    size += len(content)
            self.binary_blobs[file_name]['hashes'] = {
                k: v.hexdigest() for (k, v) in hashes_to_update.items()
            }
            self.binary_blobs[file_name]['size'] = size

    def __enter__(self):
        zfile = None
        start = datetime.datetime.now()
        try:
            LOG.info('extracting %s to %s', self.filepath, self.tempdir)
            zfile = zipfile.ZipFile(self.filepath, allowZip64=True)
            for name in zfile.namelist():
                zfile.extract(name, self.tempdir)
                basename = os.path.basename(name)
                fs_name = os.path.join(self.tempdir, name)
                if os.path.isfile(fs_name):  # in zip archives names in namelist can be folders
                    if basename.endswith(str('.reqif')):
                        self.reqif_files.append(fs_name)
                    else:
                        self.binary_blobs[name] = {
                            'path': fs_name
                        }
                        self._calculate_hashes(name, fs_name)
        except (RuntimeError, zipfile.error):
            # fall back when input file is not a zip archive
            self.reqif_files.append(self.filepath)
        finally:
            if zfile is not None:
                zfile.close()
        end = datetime.datetime.now()
        self.extraction_time = (end - start).total_seconds()
        return self.reqif_files, self.binary_blobs, self.extraction_time

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.remove_tempdir:
            LOG.info('Try to remove %s', self.tempdir)
            shutil.rmtree(self.tempdir, ignore_errors=True)
            if os.path.isdir(self.tempdir):
                LOG.warn('Failed to remove %s', self.tempdir)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        last_percentage = 0.0
        last_progress_modification = None
        start = datetime.datetime.now()

        def metadata_callback(parser_result):
            print('metadata finished, count of specification types: {}, count of spec object types: {}'.format(len(parser_result.specification_types), len(parser_result.spec_object_types)))

        def progress_callback(_filepath, _file_percentage, overall_percentage):
            global last_percentage
            global last_progress_modification
            if overall_percentage - last_percentage > 0.5:
                now = datetime.datetime.now()
                if last_progress_modification is not None:
                    duration = (now - last_progress_modification).total_seconds()
                    eta = (100.0 - overall_percentage) * 2 * duration
                    done_date = now + datetime.timedelta(seconds=eta)
                    print('progress: %4.1f, ETA: %s' % (overall_percentage, done_date.isoformat()))
                else:
                    print('progress: %4.1f' % (overall_percentage))
                last_progress_modification = now
                last_percentage = overall_percentage

        hashes = ['md5', 'sha256']

        with ReqIFzHandler(sys.argv[1], hashes=hashes) as (
            reqif_files, binary_files, extraction_time
        ):
            print(
                '%s contain reqif files: %s and binary files: %s - extraction took %s s' % (
                    sys.argv[1], reqif_files, binary_files, extraction_time
                )
            )
            if len(reqif_files) > 1:
                raise ElementsError('currently only one .reqif file is supported per .reqifz archive')
            with ReqIFParser(
                reqif_files=reqif_files,
                metadata_callback=metadata_callback,
                progress_callback=progress_callback,
                convert_types=False  # otherwise datetime objects must be reconverted to string again afterwards
            ) as parser_result:
                end = datetime.datetime.now()
                print('finished parsing, count of specifications: {}, count of spec objects: {}, count of spec relations: {}, took {}s'.format(
                    len(parser_result.specifications),
                    len(parser_result.spec_objects),
                    len(parser_result.spec_relations),
                    (end - start).total_seconds()
                ))
                with open('result.json', 'w+') as f:
                    parser_result = parser_result.to_dict(parser_result)
                    parser_result['__binary_files__'] = binary_files
                    json.dump(fp=f, obj=parser_result)
