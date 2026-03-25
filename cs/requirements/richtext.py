# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import collections
import json
import logging
import re

from cdb import i18n, sig
from cdb.lru_cache import lru_cache
from cdb.objects.core import ClassRegistry
from cs.platform.web.rest.support import rest_name

from cs.requirements import exceptions, rqm_utils

LOG = logging.getLogger(__name__)
VARIABLES_REGEX = "^[a-zA-Z0-9:_/]+$"
VARIABLES_MATCHER = re.compile(VARIABLES_REGEX)
XHTML_NAMESPACE_URI = "http://www.w3.org/1999/xhtml"
XHTML_NAMESPACES_DICT = {'xhtml': XHTML_NAMESPACE_URI}


class RichTextVariables(object):

    @classmethod
    def is_allowed_variable_id(cls, variable_id):
        return True if VARIABLES_MATCHER.match(variable_id) else False

    @classmethod
    def get_variable_xhtml(cls, variable_id):
        if not cls.is_allowed_variable_id(variable_id):
            raise ValueError('Invalid variable_id, must match to %s' % VARIABLES_REGEX)
        v = "<xhtml:object type=\"text/plain\"><xhtml:param name=\"variable_id\" value=\"{variable_id}\"></xhtml:param></xhtml:object>"
        return v.format(variable_id=variable_id)


class RichTextModifications(object):
    EMPTY_DIV = '<xhtml:div></xhtml:div>'
    DEFAULT_SERIALIZATION = "c14n2"

    @classmethod
    def get_root(cls, use_nswrapper_container, xhtml_text):
        from lxml import etree
        text_root = None
        if use_nswrapper_container:
            dummy_xhtml_div_with_xmlns = u'<xhtml:div xmlns:xhtml="{x}">{c}</xhtml:div>'
            # use dummy xhtml div around to ensure lxml understand the namespace prefix
            content = dummy_xhtml_div_with_xmlns.format(
                x=XHTML_NAMESPACE_URI,
                c=xhtml_text
            )
            # go back to the first and only child element of the tree root
            root = etree.fromstring(content)
            if not root:
                # text is no valid xhtml content
                return xhtml_text, False
            text_root = root[0]
        else:
            text_root = etree.fromstring(xhtml_text)
        return text_root, True

    @classmethod
    def change_partial_xhtml(cls, xhtml_text, change_cbs, serialization_method=None):
        if not isinstance(xhtml_text, str):
            xhtml_text = xhtml_text.decode('utf-8')
        if serialization_method is None:
            serialization_method = cls.DEFAULT_SERIALIZATION
        serialization_args = {
            'method': cls.DEFAULT_SERIALIZATION
        }
        if serialization_method != cls.DEFAULT_SERIALIZATION:
            serialization_args['encoding'] = "utf-8"
            serialization_args['method'] = serialization_method
        if not xhtml_text:
            return xhtml_text
        from lxml import etree
        use_nswrapper_container = True
        xhtml_xmlns = ' xmlns:xhtml="{}"'.format(XHTML_NAMESPACE_URI)
        if xhtml_xmlns in xhtml_text:
            use_nswrapper_container = False
        text_root = None
        valid_tree = False
        try:
            text_root, valid_tree = cls.get_root(
                use_nswrapper_container=use_nswrapper_container,
                xhtml_text=xhtml_text
            )
        except etree.XMLSyntaxError as e:
            if (
                not use_nswrapper_container and
                "namespace prefix xhtml" in str(e).lower()
            ):
                # retry with wrapper container - see E076171, it can happen that
                # the namespace is defined within some lower element but not on the root
                # element therefore retry using the wrapper container in such cases
                use_nswrapper_container = True
                text_root, valid_tree = cls.get_root(
                    use_nswrapper_container=use_nswrapper_container,
                    xhtml_text=xhtml_text
                )
            else:
                raise
        if not valid_tree:
            # change of non valid xhtml leads to unchanged text at all
            return xhtml_text
        if text_root is None:
            raise ValueError("Invalid xhtml")
        for cb in change_cbs:
            cb(text_root)
        # serialize back to string
        etree.register_namespace('xhtml', XHTML_NAMESPACE_URI)

        new_text = etree.tostring(text_root, **serialization_args)
        if use_nswrapper_container:
            new_text = new_text.replace(
                xhtml_xmlns.encode('utf-8'), b''
            )
        return new_text.decode('utf-8')

    @classmethod
    def _get_object_data_cb(cls, object_data_replacements):
        """ Replaces xhtml:object data attribute values inside richtext
        takes a dictionary of old_data_attribute_value -> new_data_attribute_value """

        def change_cb(tree):
            for obj in tree.xpath(
                '//xhtml:object',
                namespaces=XHTML_NAMESPACES_DICT
            ):
                if obj.xpath(
                    './xhtml:param[@name="variable_id"]',
                    namespaces=XHTML_NAMESPACES_DICT
                ):
                    continue  # skip variables
                if obj.attrib['data'] in object_data_replacements:
                    obj.attrib['data'] = object_data_replacements.get(obj.attrib['data'])

        return change_cb

    @classmethod
    def force_serializations(cls, attribute_values, serialization_method=None):
        richtext_attribute_values = {
            k: cls.change_partial_xhtml(
                xhtml_text=attribute_values[k],
                change_cbs=[],
                serialization_method=serialization_method
            ) for (k) in attribute_values
        }
        return richtext_attribute_values

    @classmethod
    def remove_variables(cls, xhtml_text, remove_only_values=False):
        if 'xhtml:object' in xhtml_text and 'variable_id' in xhtml_text:
            xhtml_text = cls.set_variables(
                xhtml_text=xhtml_text,
                replace_variable_nodes_with_values=not remove_only_values
            )
        return xhtml_text

    @classmethod
    def replace_filled_variables_with_text_nodes(cls, xhtml_text, ns_prefix=None):
        if ns_prefix is None:
            ns_prefix = 'xhtml'

        span = '{%s}span' % XHTML_NAMESPACES_DICT[ns_prefix] if ns_prefix else 'span'

        def transform_variables(root):
            for param in root.xpath(
                '//{ns_prefix}{sep}object/{ns_prefix}{sep}param[@name="variable_id"]'.format(
                    ns_prefix=ns_prefix, sep=':' if ns_prefix else ''
                ),
                namespaces=XHTML_NAMESPACES_DICT
            ):
                variable_id = None
                obj = param.getparent()
                if 'name' in param.attrib and param.attrib['name'] == 'variable_id':
                    variable_id = param.attrib.get('value')
                    text = param.tail
                    obj.remove(param)
                obj.tag = span
                obj.attrib['title'] = variable_id if variable_id is not None else ''
                if text:
                    obj.attrib['class'] = 'variables'
                    obj.text = text
                else:
                    obj.attrib['class'] = 'variables variables-without-value'
                    obj.text = text
                if 'data' in obj.attrib:
                    del obj.attrib['data']
                if 'type' in obj.attrib:
                    del obj.attrib['type']

        return cls.change_partial_xhtml(
            xhtml_text, change_cbs=[transform_variables]
        )

    @classmethod
    def replace_nodes_with_text(cls, node, text_value=None):
        if text_value is None:
            text_value = ''
        text = text_value + (node.tail or '')
        parent_node = node.getparent()
        if parent_node is not None:
            previous_node = node.getprevious()
            if previous_node is not None:
                previous_node.tail = (previous_node.tail or '') + text
            else:
                parent_node.text = (parent_node.text or '') + text
            parent_node.remove(node)

    @classmethod
    def _get_variable_data_cb(
        cls,
        variable_values=None,
        language=None,
        raise_for_empty_value=False,
        replace_variable_nodes_with_values=False
    ):
        """ Set variable values inside richtext
        takes a dictionary of variable_id->variable_value
        if no variable_values dict is given set all variables to ''
        """
        if variable_values is None:
            variable_values = {
                '*': ''
            }

        def change_cb(tree):
            for node in tree.xpath(
                '//xhtml:object/xhtml:param[@name="variable_id"]/..',
                namespaces=XHTML_NAMESPACES_DICT
            ):
                skip = False
                variable_value = None
                for elem in node:
                    if (
                        elem.get('name') != 'variable_id' or
                        (
                            elem.get('value') not in variable_values and
                            '*' not in variable_values
                        )
                    ):
                        skip = True
                        if raise_for_empty_value:
                            raise exceptions.MissingVariableValueError(variable_id=elem.get('value'))
                        continue  # skip if it is not the right variable_id or right param tag
                    variable_id = elem.get('value')
                    variable_value = variable_values.get(variable_id, variable_values.get('*'))
                    if isinstance(variable_value, list):
                        variable_value = ",".join(
                            [str(rqm_utils.get_classification_val(x, language)) for x in variable_value]
                        )
                    if isinstance(variable_value, bytes):
                        raise exceptions.InvalidVariableValueTypeError(
                            variable_id=variable_id, variable_value=variable_value
                        )
                    elem.tail = variable_value
                if replace_variable_nodes_with_values:
                    cls.replace_nodes_with_text(node, variable_value)
                if skip:
                    continue
                if 'data' in node.attrib:
                    del node.attrib['data']

        return change_cb

    @classmethod
    def get_richtext_object_data_replacements_filenames_to_external_links(
        cls, obj, attribute_values, file_cache=None, file_link_rest_replacement=True,
    ):
        # for all languages/richtexts
        object_data_replacements = {}
        data_ref_exist = False
        for value in attribute_values.values():
            if 'data=' in value:
                data_ref_exist = True
                break
        if data_ref_exist and hasattr(obj, 'Files'):
            if file_cache is None:
                files = obj.Files.Execute()
            else:
                files = file_cache.get(obj.cdb_object_id, [])
            for file_obj in files:
                if file_link_rest_replacement:
                    uri = "/api/v1/collection/{rest_name}/{obj_id}/files/{f_obj_id}?inline=1".format(
                        rest_name=rest_name(obj),
                        obj_id=obj.cdb_object_id,
                        f_obj_id=file_obj.cdb_object_id
                    )
                    object_data_replacements[file_obj.cdbf_name] = uri
                elif hasattr(obj, 'reqif_id') and obj.reqif_id != '':
                    object_data_replacements[file_obj.cdbf_name] = '/'.join((obj.reqif_id, file_obj.cdbf_name))
                else:
                    object_data_replacements[file_obj.cdbf_name] = '/'.join((obj.cdb_object_id, file_obj.cdbf_name))
        return object_data_replacements

    @classmethod
    def get_richtext_object_data_replacements_external_links_to_filenames(
        cls, obj, attribute_values, file_cache=None, file_link_rest_replacement=True
    ):
        # for all languages/richtexts
        object_data_replacements = {}
        data_ref_exist = False
        for value in attribute_values.values():
            if 'data=' in value:
                data_ref_exist = True
                break
        if data_ref_exist and hasattr(obj, 'Files'):
            if file_cache is None:
                files = obj.Files.Execute()
            else:
                files = file_cache.get(obj.cdb_object_id, [])
            for file_obj in files:
                if file_link_rest_replacement:
                    uri = "/api/v1/collection/{rest_name}/{obj_id}/files/{f_obj_id}?inline=1".format(
                        rest_name=rest_name(obj),
                        obj_id=obj.cdb_object_id,
                        f_obj_id=file_obj.cdb_object_id
                    )
                    object_data_replacements[uri] = file_obj.cdbf_name
                else:
                    object_data_replacements['/'.join((obj.reqif_id, file_obj.cdbf_name))] = file_obj.cdbf_name
                    object_data_replacements['/'.join((obj.cdb_object_id, file_obj.cdbf_name))] = file_obj.cdbf_name

        return object_data_replacements

    @classmethod
    def get_variable_values_by_id(cls, object_ids, specification_object_id=None, from_db=True):
        if not from_db:
            # we do only need variable values
            # for the direction from db -> presentation/etc.
            # in the other direction variable values will be stripped
            # anyway therefore we skip collecting any variable values
            return {}
        from cs.requirements import RQMSpecification
        variable_values_by_id = collections.defaultdict(dict)
        sig.emit(
            RQMSpecification, "requirements", "collect_variable_values"
        )(specification_object_id, object_ids, variable_values_by_id)
        if not variable_values_by_id:
            variable_values_by_id = cls.get_classification_variable_values_by_id(
                specification_object_id, object_ids
            )
        return variable_values_by_id

    @classmethod
    def get_variable_and_file_link_modified_attribute_values(
        cls, objs, attribute_values, from_db=True, serialization_method=None,
        file_cache=None, variable_values_by_id=None, file_link_rest_replacement=True, raise_for_empty_value=False
    ):
        args = dict(
            attribute_values=attribute_values,
            from_db=from_db,
            serialization_method=serialization_method,
            file_cache=file_cache,
            raise_for_empty_value=raise_for_empty_value,
            file_link_rest_replacement=file_link_rest_replacement,
        )
        if isinstance(objs, list):
            result = []
            if len(objs) > 0:
                if variable_values_by_id is None:
                    variable_reference_ids = list(set([x.cdb_object_id for x in objs]))
                    variable_values_by_id = cls.get_variable_values_by_id(
                        variable_reference_ids,
                        objs[0].specification_object_id
                        if hasattr(objs[0], 'specification_object_id') else None,
                        from_db=from_db,
                    )
                for obj in objs:
                    args['attribute_values'] = attribute_values[obj.cdb_object_id]
                    args['variable_values_by_id'] = variable_values_by_id
                    result.append(
                        cls.get_variable_and_file_link_modified_attribute_values_single(
                            obj=obj, **args
                        )
                    )
            return result
        else:
            args.update(dict(obj=objs))
            if variable_values_by_id is None:
                variable_values_by_id = cls.get_variable_values_by_id(
                    [objs.cdb_object_id],
                    objs.specification_object_id
                    if hasattr(objs, 'specification_object_id') else None,
                    from_db=from_db,
                )
            args['variable_values_by_id'] = variable_values_by_id
            return cls.get_variable_and_file_link_modified_attribute_values_single(**args)

    @classmethod
    def get_variable_modified_attribute_values(
        cls, objs, attribute_values, from_db=True, serialization_method=None,
        variable_values_by_id=None, raise_for_empty_value=False
    ):
        args = dict(
            attribute_values=attribute_values,
            from_db=from_db,
            serialization_method=serialization_method,
            variable_values_by_id=variable_values_by_id,
            raise_for_empty_value=raise_for_empty_value
        )
        if isinstance(objs, list):
            result = []
            for obj in objs:
                args['attribute_values'] = attribute_values[obj.cdb_object_id]
                result.append(
                    cls.get_variable_modified_attribute_values_single(
                        obj=obj, **args
                    )
                )
            return result
        else:
            args.update(dict(obj=objs))
            return cls.get_variable_modified_attribute_values_single(**args)

    @classmethod
    def get_empty_richtexts_by_iso_codes(cls, obj):
        richtext = {}
        if (
            hasattr(obj, '__description_attrname_format__') and
            obj.__description_attrname_format__
        ):

            richtext = {
                iso_lang: cls.EMPTY_DIV for iso_lang in i18n.Languages()
                if obj.__description_attrname_format__.format(iso=iso_lang) in
                cls.get_richtext_fields(obj.GetClassname())
            }
        return richtext

    @classmethod
    def get_short_title_attribute_values(cls, obj, richtext_attribute_values):
        if (
            not hasattr(obj, '__short_description_attrname_format__') or
            not hasattr(obj, '__description_attrname_format__')
        ):
            return {}
        short_title_attribute_values = {}
        for desc_attr_name in list(richtext_attribute_values):
            iso_code = desc_attr_name.split('_')[-1]
            short_description_attr_name = obj.__short_description_attrname_format__.format(
                iso=iso_code
            )
            if hasattr(obj.__class__, short_description_attr_name):
                short_title_attribute_values[short_description_attr_name] = (
                    rqm_utils.get_short_title_from_richtext(
                        field_length=getattr(obj.__class__, short_description_attr_name).length,
                        richtext=richtext_attribute_values.get(desc_attr_name)
                    )
                )
            else:
                LOG.warning(
                    "Richtext long text %s does exist but corresponding short description field %s does not exist",
                    desc_attr_name, short_description_attr_name
                )
        return short_title_attribute_values

    @classmethod
    def get_richtexts_by_iso_code(cls, obj, patched_attribute_values=None, as_json=False):
        richtexts = cls.get_empty_richtexts_by_iso_codes(obj)
        if (
            patched_attribute_values is None and
            hasattr(obj, '__description_attrname_format__') and
            obj.__description_attrname_format__
        ):
                richtext_attribute_values = cls.get_richtext_attribute_values(obj)
                for iso_lang in list(richtexts):
                    attrname = obj.__description_attrname_format__.format(iso=iso_lang)
                    if attrname in richtext_attribute_values and richtext_attribute_values[attrname]:
                        richtexts[iso_lang] = richtext_attribute_values[attrname]
                patched_fields = cls.get_variable_and_file_link_modified_attribute_values(
                    obj, richtext_attribute_values, from_db=True
                )
                patched_attribute_values = patched_fields

        for field, value in patched_attribute_values.items():
            richtexts[
                field.replace(
                    obj.__description_attrname_format__.format(iso=''), '')
            ] = value
        if as_json:
            return json.dumps(richtexts, ensure_ascii=False)
        else:
            return richtexts

    @classmethod
    def get_richtext_attribute_values(cls, obj, long_text_cache=None):
        richtext_fields = cls.get_richtext_fields(obj.GetClassname())
        if long_text_cache is None or list(richtext_fields) != list(long_text_cache):
            # should NOT be used in a loop -> that could be done more efficient
            richtext_attribute_values = {
                k: obj.GetText(k) for (k) in
                richtext_fields
            }
        else:
            richtext_attribute_values = {
                k: long_text_cache[k][obj.cdb_object_id] for (k) in
                richtext_fields
            }
        return richtext_attribute_values

    @classmethod
    @lru_cache()
    def get_richtext_fields(cls, classname):
        entity = ClassRegistry().findByClassname(classname)
        long_text_fields = entity.GetTextFieldNames()
        content_types = rqm_utils.get_content_types_by_classname(classname)
        richtext_fields = set([f for f in long_text_fields if content_types.get(f) == "XHTML"])
        return richtext_fields

    @classmethod
    def get_classification_variable_values_by_id(cls, specification_object_id, object_ids):
        # get a dictionary of variable values
        # each object has the UC property values of the specification + their own ones
        # the more specific ones from the object itself are used on name collisions.
        cdb_object_ids = (object_ids) + [specification_object_id]
        classification_value_cache = rqm_utils.load_classification_cache_by_id(cdb_object_ids)
        variable_values_by_id = collections.defaultdict(dict)
        for cdb_object_id in object_ids:
            variable_values_by_id[cdb_object_id].update(
                classification_value_cache.get(specification_object_id)
            )
            variable_values_by_id[cdb_object_id].update(
                classification_value_cache.get(cdb_object_id)
            )
        return variable_values_by_id

    @classmethod
    def get_variable_modified_attribute_values_single(
            cls, obj, attribute_values, from_db=True, serialization_method=None,
            variable_values_by_id=None, raise_for_empty_value=False,
            replace_variable_nodes_with_values=False
    ):
        """ Get all modified richtext attribute values for a single object regarding variables
        attribute_values (attr_name->attr_value)
        from_db: controls the direction of modification if True:
            - variables in richtext will be filled with their current value
        if False:
            - variable values in richtext will be removed again to ensure stable comparisons
        """
        # filter attribute_values to richtext fields which contains
        richtext_attribute_values = {}
        if hasattr(obj, 'GetClassname'):
            richtext_fields = cls.get_richtext_fields(obj.GetClassname())
            for richtext_field in richtext_fields:
                if richtext_field in attribute_values:
                    attribute_value = attribute_values[richtext_field]
                    if isinstance(attribute_value, bytes):
                        raise exceptions.InvalidRichTextAttributeValueType(
                            attribute_name=richtext_field,
                            attribute_value=attribute_value
                        )
                    elif 'xhtml:object' in attribute_value:
                        richtext_attribute_values[richtext_field] = attribute_value
                    else:
                        pass # filter out as it does not contain a variable
        else:
            richtext_attribute_values = attribute_values
        if not richtext_attribute_values:
            # skip here for all requirements/attribute_values which do not contain variables
            return {}
        if variable_values_by_id is None:
            variable_values_by_id = cls.get_classification_variable_values_by_id(
                obj.specification_object_id,
                [obj.cdb_object_id]
            )
        if from_db:  # set variable values when loading from db where no values are stored in variables
            variable_values = variable_values_by_id.get(obj.cdb_object_id)
        else:
            variable_values = None  # just clean up when going back into db direction
            # do not raise regarding empty values as this is the usecase in this direction
            raise_for_empty_value = False
        result = {}
        for attribute_name, attribute_value in richtext_attribute_values.items():
            if attribute_value:
                args = dict(
                    xhtml_text=attribute_value,
                    variable_values=variable_values,
                    raise_for_empty_value=raise_for_empty_value,
                    serialization_method=serialization_method,
                    language=attribute_name.split('_')[-1] if '_' in attribute_name else None,
                    replace_variable_nodes_with_values=replace_variable_nodes_with_values
                )
                result[attribute_name] = cls.set_variables(**args)
        return result

    @classmethod
    def get_variable_and_file_link_modified_attribute_values_single(
        cls, obj, attribute_values, from_db=True, serialization_method=None,
        file_cache=None, variable_values_by_id=None, raise_for_empty_value=False, file_link_rest_replacement=True
    ):
        """ Get all modified richtext attribute values for a single object regarding variables and file links
        attribute_values (attr_name->attr_value)
        from_db: controls the direction of modification if True:
            - filenames referenced in XHTML object data will be converted to REST API inplace file links
            - variables in richtext will be filled with their current value
        if False:
            - REST API inplace file links referenced in XHTML object data will be converted (back) to filenames
            - variable values in richtext will be removed again to ensure stable comparisons
        """
        # filter attribute_values to richtext fields which contains
        richtext_attribute_values = {}
        richtext_fields = cls.get_richtext_fields(obj.GetClassname())
        for richtext_field in richtext_fields:
            if richtext_field in attribute_values:
                attribute_value = attribute_values[richtext_field]
                if isinstance(attribute_value, bytes):
                    raise exceptions.InvalidRichTextAttributeValueType(
                        attribute_name=richtext_field,
                        attribute_value=attribute_value
                    )
                elif 'xhtml:object' in attribute_value:
                    richtext_attribute_values[richtext_field] = attribute_value
                else:
                    pass # filter out as it does not contain a variable

        if not richtext_attribute_values:
            # skip here for all requirements/attribute_values which do not contain variables or files
            return {}
        obj_data_replacement_func = (
            cls.get_richtext_object_data_replacements_filenames_to_external_links if from_db else
            cls.get_richtext_object_data_replacements_external_links_to_filenames
        )

        object_data_replacements = obj_data_replacement_func(obj, richtext_attribute_values, file_cache, file_link_rest_replacement)
        if variable_values_by_id is None:
            variable_values_by_id = cls.get_classification_variable_values_by_id(
                obj.specification_object_id,
                [obj.cdb_object_id]
            )
        if from_db:  # set variable values when loading from db where no values are stored in variables
            variable_values = variable_values_by_id.get(obj.cdb_object_id)
        else:
            variable_values = None  # just clean up when going back into db direction
        result = {}
        for attribute_name, attribute_value in richtext_attribute_values.items():
            if attribute_value:
                args = dict(
                    xhtml_text=attribute_value,
                    object_data_replacements=object_data_replacements,
                    variable_values=variable_values,
                    serialization_method=serialization_method,
                    raise_for_empty_value=raise_for_empty_value,
                    language=attribute_name.split('_')[-1] if '_' in attribute_name else None
                )
                result[attribute_name] = cls.set_variables_and_file_links(**args)
        return result

    @classmethod
    def set_variables_and_file_links(
        cls, xhtml_text, object_data_replacements,
        variable_values=None, serialization_method=None,
        raise_for_empty_value=False, language=None, replace_variable_nodes_with_values=False
    ):
        if not xhtml_text:
            return xhtml_text
        object_data_replacer = cls._get_object_data_cb(
            object_data_replacements=object_data_replacements
        )
        variable_data_setter = cls._get_variable_data_cb(
            variable_values=variable_values,
            raise_for_empty_value=raise_for_empty_value,
            language=language,
            replace_variable_nodes_with_values=replace_variable_nodes_with_values
        )
        return cls.change_partial_xhtml(
            xhtml_text=xhtml_text,
            change_cbs=[object_data_replacer, variable_data_setter],
            serialization_method=serialization_method
        )

    @classmethod
    def set_file_links(
            cls, xhtml_text, object_data_replacements, serialization_method=None
    ):
        if not xhtml_text:
            return xhtml_text
        object_data_replacer = cls._get_object_data_cb(
            object_data_replacements=object_data_replacements
        )
        return cls.change_partial_xhtml(
            xhtml_text=xhtml_text,
            change_cbs=[object_data_replacer],
            serialization_method=serialization_method
        )

    @classmethod
    def set_variables(
        cls, xhtml_text, variable_values=None, serialization_method=None,
        language=None, raise_for_empty_value=False, replace_variable_nodes_with_values=False
    ):
        if not xhtml_text:
            return xhtml_text
        variable_data_setter = cls._get_variable_data_cb(
            variable_values=variable_values,
            raise_for_empty_value=raise_for_empty_value,
            language=language,
            replace_variable_nodes_with_values=replace_variable_nodes_with_values
        )
        return cls.change_partial_xhtml(
            xhtml_text=xhtml_text,
            change_cbs=[variable_data_setter],
            serialization_method=serialization_method
        )
