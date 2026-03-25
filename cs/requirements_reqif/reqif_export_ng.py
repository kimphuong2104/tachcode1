# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import collections
import datetime
import logging
import os
import sys
import time
import zipfile
from xml.sax import saxutils

from lxml import etree

from io import BytesIO
from cdb import CADDOK, cdbuuid, profiling, rte, sqlapi, ue, util, objects
from cdb.lru_cache import lru_cache
from cdb.objects.core import ClassRegistry
from cdb.wsgi.util import jail_filename
from cs.classification.classes import (ClassProperty,
                                       ClassPropertyValuesView, ClassificationClass)
from cs.requirements.rqm_utils import (RQMHierarchicals,
                                       createUniqueIdentifier, strip_tags)
from cs.requirements_reqif import createXsdDateTime, prefixID
from cs.requirements_reqif.exceptions import ReqIFValidationError
from cs.requirements_reqif.reqif_utils import ReqIFBase
from cs.requirements_reqif.reqif_validator import ReqIFValidator
from cs.requirements import exceptions, rqm_utils
from cs.requirements.richtext import RichTextModifications

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
LOG = logging.getLogger(__name__)

ReqIFIDTuple = collections.namedtuple('ReqIFIDTuple', 'specification_object_id reqif_id')


class ReqIFNodes(object):
    NAMESPACES = {
        "reqif": "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd",
        "xhtml": "http://www.w3.org/1999/xhtml"
    }

    @classmethod
    def register_namespaces(cls):
        etree.register_namespace('reqif', cls.NAMESPACES['reqif'])
        etree.register_namespace('xhtml', cls.NAMESPACES['xhtml'])

    @classmethod
    def ReqIF(cls, tag):
        return etree.QName(cls.NAMESPACES['reqif'], tag)

    @classmethod
    def XHTML(cls, tag):
        return etree.QName(cls.NAMESPACES['xhtml'], tag)

    @classmethod
    def e(cls, tag, children=None, attrib=None, text=None, nsmap=None):
        if children is None:
            children = []
        if attrib is None:
            attrib = {}
        _attrib = {k: v for (k, v) in attrib.items() if v is not None}
        out = etree.Element(cls.ReqIF(tag), _attrib, nsmap=nsmap)
        out.text = text
        for node in children:
            out.append(node)
        return out

    @classmethod
    def check_required_attributes(cls, attributes, required_attributes=None):
        if required_attributes is None:
            required_attributes = ['IDENTIFIER', 'LAST-CHANGE']
        for attribute_name in required_attributes:
            if attribute_name not in attributes or not attributes.get(attribute_name):
                raise ValueError('Missing required value: %s' % attribute_name)

    @classmethod
    @lru_cache()
    def _get_versions(cls):
        from cdb.comparch.packages import Package
        package_version = Package.ByKeys("cs.requirements").version
        platform_version = Package.ByKeys("cs.platform").version
        return {"platform": u"cs.platform %s" % platform_version,
                "package": u"cs.requirements %s" % package_version}

    @classmethod
    @lru_cache()
    def get_tool_id(cls):
        versions = cls._get_versions()
        return ";".join([
            versions['platform'],
            versions['package']]
        )

    @classmethod
    def reqif_tool_extension(cls, children, attrib):
        return cls.e("REQ-IF-TOOL-EXTENSION", children=children, attrib=attrib)

    @classmethod
    def reqif_reqif(cls, the_header, core_content, tool_extensions=None):
        return cls.e("REQ-IF", children=[x for x in [
            the_header,
            core_content,
            tool_extensions
        ] if x is not None], nsmap=cls.NAMESPACES)

    @classmethod
    def reqif_the_header(
        cls,
        reqif_header_id,
        title,
        creation_time=None,
        reqif_version="1.0",
        comment=None,
        repository_id=None,
        reqif_tool_id=None,
        source_tool_id=None
    ):
        if creation_time is None:
            creation_time = createXsdDateTime()
        if reqif_tool_id is None:
            reqif_tool_id = cls.get_tool_id()
        if source_tool_id is None:
            source_tool_id = cls.get_tool_id()
        return cls.e(
            "THE-HEADER", [
                cls.e(
                    "REQ-IF-HEADER", [
                        cls.e("COMMENT", text=comment),
                        cls.e("CREATION-TIME", text=creation_time),
                        cls.e("REPOSITORY-ID", text=repository_id),
                        cls.e("REQ-IF-TOOL-ID", text=reqif_tool_id),
                        cls.e("REQ-IF-VERSION", text=reqif_version),
                        cls.e("SOURCE-TOOL-ID", text=source_tool_id),
                        cls.e("TITLE", text=title)
                    ],
                    attrib={'IDENTIFIER': reqif_header_id}
                )
            ]
        )

    @classmethod
    def reqif_core_content(
        cls,
        data_types=None,
        spec_types=None,
        spec_objects=None,
        spec_relations=None,
        specifications=None,
        spec_relation_groups=None
    ):
        return cls.e(
            "CORE-CONTENT", [
                cls.e(
                    "REQ-IF-CONTENT", [
                        x for x in [
                            data_types,
                            spec_types,
                            spec_objects,
                            spec_relations,
                            specifications,
                            spec_relation_groups
                        ] if x is not None
                    ]
                )
            ]
        )

    @classmethod
    def _merge_sublists(cls, lists):
        children = []
        for definition_list in lists:
            if definition_list is not None:
                if isinstance(definition_list, list):
                    for definition in definition_list:
                        children.append(definition)
                else:
                    children.append(definition_list)
        return children

    @classmethod
    def reqif_datatypes(
        cls,
        boolean_definitions=None,
        date_definitions=None,
        enumeration_definitions=None,
        integer_definitions=None,
        real_definitions=None,
        string_definitions=None,
        xhtml_definitions=None
    ):
        children = cls._merge_sublists([
            boolean_definitions,
            date_definitions,
            enumeration_definitions,
            integer_definitions,
            real_definitions,
            string_definitions,
            xhtml_definitions
        ])
        return cls.e(
            "DATATYPES",
            children=children
        )

    @classmethod
    def reqif_datatype_definition_boolean(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        return cls.e(
            "DATATYPE-DEFINITION-BOOLEAN",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_datatype_definition_date(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        return cls.e(
            "DATATYPE-DEFINITION-DATE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_datatype_definition_enumeration(cls, enum_values, **kwargs):
        cls.check_required_attributes(kwargs)
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        children.append(cls.e("SPECIFIED-VALUES", children=enum_values))
        return cls.e(
            "DATATYPE-DEFINITION-ENUMERATION",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_datatype_definition_integer(cls, **kwargs):
        cls.check_required_attributes(
            kwargs,
            required_attributes=[
                'IDENTIFIER',
                'LAST-CHANGE',
                'MAX',
                'MIN'
            ]
        )
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        return cls.e(
            "DATATYPE-DEFINITION-INTEGER",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_datatype_definition_real(cls, **kwargs):
        cls.check_required_attributes(
            kwargs,
            required_attributes=[
                'IDENTIFIER',
                'LAST-CHANGE',
                'ACCURACY',
                'MAX',
                'MIN'
            ]
        )
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        return cls.e(
            "DATATYPE-DEFINITION-REAL",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_datatype_definition_string(cls, **kwargs):
        cls.check_required_attributes(
            kwargs,
            required_attributes=[
                'IDENTIFIER',
                'LAST-CHANGE',
                'MAX-LENGTH'
            ]
        )
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        return cls.e(
            "DATATYPE-DEFINITION-STRING",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_datatype_definition_xhtml(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        children = []
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        return cls.e(
            "DATATYPE-DEFINITION-XHTML",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_spec_types(
        cls,
        relation_group_types,
        spec_object_types,
        spec_relation_types,
        specification_types
    ):
        children = cls._merge_sublists([
            relation_group_types,
            spec_object_types,
            spec_relation_types,
            specification_types
        ])
        return cls.e("SPEC-TYPES", children=children)

    @classmethod
    def reqif_relation_group_type(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        spec_attributes = kwargs.pop('SPEC-ATTRIBUTES') if 'SPEC-ATTRIBUTES' in kwargs else None
        if spec_attributes is not None:
            children.append(cls.e("SPEC-ATTRIBUTES", spec_attributes))
        return cls.e(
            "RELATION-GROUP-TYPE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_spec_object_type(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        spec_attributes = kwargs.pop('SPEC-ATTRIBUTES') if 'SPEC-ATTRIBUTES' in kwargs else None
        if spec_attributes is not None:
            children.append(cls.e("SPEC-ATTRIBUTES", spec_attributes))
        return cls.e(
            "SPEC-OBJECT-TYPE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_spec_relation_type(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        spec_attributes = kwargs.pop('SPEC-ATTRIBUTES') if 'SPEC-ATTRIBUTES' in kwargs else None
        if spec_attributes is not None:
            children.append(cls.e("SPEC-ATTRIBUTES", spec_attributes))
        return cls.e(
            "SPEC-RELATION-TYPE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_specification_type(cls, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        spec_attributes = kwargs.pop('SPEC-ATTRIBUTES') if 'SPEC-ATTRIBUTES' in kwargs else None
        if spec_attributes is not None:
            children.append(cls.e("SPEC-ATTRIBUTES", spec_attributes))
        return cls.e(
            "SPECIFICATION-TYPE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_boolean(cls, typeref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-BOOLEAN-REF", text=typeref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-BOOLEAN",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_date(cls, typeref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-DATE-REF", text=typeref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-DATE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_enumeration(cls, typeref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-ENUMERATION-REF", text=typeref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-ENUMERATION",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_integer(cls, typeref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-INTEGER-REF", text=typeref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-INTEGER",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_real(cls, typeref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-REAL-REF", text=typeref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-REAL",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_string(cls, datatype_definition_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-STRING-REF", text=datatype_definition_ref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-STRING",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_definition_xhtml(cls, datatype_definition_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        default_value = kwargs.pop('DEFAULT-VALUE') if 'DEFAULT-VALUE' in kwargs else None
        if default_value is not None:
            children.append(cls.e("DEFAULT-VALUE", children=[default_value]))
        children.append(
            cls.e("TYPE", [
                cls.e("DATATYPE-DEFINITION-XHTML-REF", text=datatype_definition_ref)
            ])
        )
        return cls.e(
            "ATTRIBUTE-DEFINITION-XHTML",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_enum_value(cls, key, other_content, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        children.append(
            cls.e("PROPERTIES", [
                cls.e("EMBEDDED-VALUE", attrib={'KEY': key, 'OTHER-CONTENT': other_content})
            ])
        )
        return cls.e(
            "ENUM-VALUE",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_spec_objects(cls, spec_objects):
        return cls.e("SPEC-OBJECTS", spec_objects)

    @classmethod
    def reqif_spec_relations(cls, spec_relations):
        return cls.e("SPEC-RELATIONS", spec_relations)

    @classmethod
    def reqif_spec_relation(cls, source_ref, target_ref, spec_relation_type_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        values = kwargs.pop('VALUES') if 'VALUES' in kwargs else None
        if values is not None:
            children.append(cls.e("VALUES", children=values))
        children.append(
            cls.e("SOURCE", [
                cls.e("SPEC-OBJECT-REF", text=source_ref)
            ])
        )
        children.append(
            cls.e("TARGET", [
                cls.e("SPEC-OBJECT-REF", text=target_ref)
            ])
        )
        children.append(
            cls.e("TYPE", [
                cls.e("SPEC-RELATION-TYPE-REF", text=spec_relation_type_ref)
            ])
        )
        return cls.e(
            "SPEC-RELATION",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_specifications(cls, specifications):
        return cls.e("SPECIFICATIONS", specifications)

    @classmethod
    def reqif_spec_relation_groups(cls, spec_relation_groups):
        return cls.e("SPEC-RELATION-GROUPS", spec_relation_groups)

    @classmethod
    def reqif_relation_group(cls, relation_group_type_ref, source_specification_ref, target_specification_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        children.append(
            cls.e("SOURCE-SPECIFICATION", [
                cls.e("SPECIFICATION-REF", text=source_specification_ref)
            ])
        )
        spec_relations = kwargs.pop('SPEC-RELATIONS') if 'SPEC-RELATIONS' in kwargs else None
        if spec_relations is not None:
            children.append(
                cls.e(
                    "SPEC-RELATIONS", [
                        cls.e("SPEC-RELATION-REF", text=x)
                        for x in spec_relations
                    ]
                )
            )
        children.append(
            cls.e("TARGET-SPECIFICATION", [
                cls.e("SPECIFICATION-REF", text=target_specification_ref)
            ])
        )
        children.append(
            cls.e("TYPE", [
                cls.e("RELATION-GROUP-TYPE-REF", text=relation_group_type_ref)
            ])
        )
        return cls.e(
            "RELATION-GROUP",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_spec_object(cls, spec_object_type_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        values = kwargs.pop('VALUES') if 'VALUES' in kwargs else None
        if values is not None:
            children.append(cls.e("VALUES", children=values))
        children.append(
            cls.e("TYPE", [
                cls.e("SPEC-OBJECT-TYPE-REF", text=spec_object_type_ref)
            ])
        )
        return cls.e(
            "SPEC-OBJECT",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_specification(cls, specification_type_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        values = kwargs.pop('VALUES') if 'VALUES' in kwargs else None
        if values is not None:
            children.append(cls.e("VALUES", children=values))
        CHILDREN = kwargs.pop('CHILDREN') if 'CHILDREN' in kwargs else None
        if CHILDREN is not None:
            children.append(cls.e("CHILDREN", children=CHILDREN))
        children.append(
            cls.e("TYPE", [
                cls.e("SPECIFICATION-TYPE-REF", text=specification_type_ref)
            ])
        )
        return cls.e(
            "SPECIFICATION",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_spec_hierarchy(cls, object_ref, **kwargs):
        cls.check_required_attributes(kwargs)
        children = []
        alternative_id = kwargs.pop('ALTERNATIVE-ID') if 'ALTERNATIVE-ID' in kwargs else None
        if alternative_id is not None:
            children.append(cls.e("ALTERNATIVE-ID", attrib={'IDENTIFIER': alternative_id}))
        CHILDREN = kwargs.pop('CHILDREN') if 'CHILDREN' in kwargs else None
        if CHILDREN is not None:
            children.append(cls.e("CHILDREN", children=CHILDREN))
        editable_attrs = kwargs.pop('EDITABLE-ATTS') if 'EDITABLE-ATTS' in kwargs else None
        if editable_attrs is not None:
            children.append(cls.e("EDITABLE-ATTS", children=editable_attrs))
        children.append(
            cls.e("OBJECT", [
                cls.e("SPEC-OBJECT-REF", text=object_ref)
            ])
        )
        return cls.e(
            "SPEC-HIERARCHY",
            children=children,
            attrib=kwargs
        )

    @classmethod
    def reqif_attribute_value_boolean(cls, attribute_ref, value):
        return cls.e(
            "ATTRIBUTE-VALUE-BOOLEAN", [
                cls.e("DEFINITION", [
                    cls.e("ATTRIBUTE-DEFINITION-BOOLEAN-REF", text=attribute_ref)
                ])
            ],
            attrib={"THE-VALUE": str(value)}
        )

    @classmethod
    def reqif_attribute_value_date(cls, attribute_ref, value):
        return cls.e(
            "ATTRIBUTE-VALUE-DATE", [
                cls.e("DEFINITION", [
                    cls.e("ATTRIBUTE-DEFINITION-DATE-REF", text=attribute_ref)
                ])
            ],
            attrib={"THE-VALUE": str(value)}
        )

    @classmethod
    def reqif_attribute_value_enumeration(cls, attribute_ref, value=None):
        if value is None:
            values = []
        elif isinstance(value, list):
            values = value
        else:
            values = [value]
        return cls.e(
            "ATTRIBUTE-VALUE-ENUMERATION", [
                cls.e("DEFINITION", [
                    cls.e("ATTRIBUTE-DEFINITION-ENUMERATION-REF", text=attribute_ref)
                ]),
                cls.e("VALUES", [
                    cls.e("ENUM-VALUE-REF", text=x) for x in values
                ])
            ]
        )

    @classmethod
    def reqif_attribute_value_integer(cls, attribute_ref, value):
        return cls.e(
            "ATTRIBUTE-VALUE-INTEGER", [
                cls.e("DEFINITION", [
                    cls.e("ATTRIBUTE-DEFINITION-INTEGER-REF", text=attribute_ref)
                ])
            ],
            attrib={"THE-VALUE": str(value)}
        )

    @classmethod
    def reqif_attribute_value_real(cls, attribute_ref, value):
        return cls.e(
            "ATTRIBUTE-VALUE-REAL", [
                cls.e("DEFINITION", [
                    cls.e("ATTRIBUTE-DEFINITION-REAL-REF", text=attribute_ref)
                ])
            ],
            attrib={"THE-VALUE": str(value)}
        )

    @classmethod
    def reqif_attribute_value_string(cls, attribute_ref, value):
        return cls.e(
            "ATTRIBUTE-VALUE-STRING", [
                cls.e("DEFINITION", [
                    cls.e("ATTRIBUTE-DEFINITION-STRING-REF", text=attribute_ref)
                ])
            ],
            attrib={"THE-VALUE": value}
        )

    @classmethod
    def reqif_attribute_value_xhtml(cls, attribute_ref, value):
        return cls.e(
            "ATTRIBUTE-VALUE-XHTML", [
                cls.e(
                    "THE-VALUE", [
                        etree.fromstring(
                            '<xhtml:div xmlns:xhtml="http://www.w3.org/1999/xhtml">{}</xhtml:div>'.format(
                                value
                            )
                        ).getchildren()[0]
                    ]
                ),
                cls.e(
                    "DEFINITION", [
                        cls.e(
                            "ATTRIBUTE-DEFINITION-XHTML-REF", text=attribute_ref
                        )
                    ]
                )
            ]
        )


class ReqIFExportNG(ReqIFBase):
    """
    ReqIF-Export
    """

    def __init__(
        self,
        profile,
        specifications,
        logger=None,
        logger_extra_args=None,
        replace_variables=False,
        export_target_values=True,
        process_run=None
    ):
        start = datetime.datetime.now()
        self.logger = logger if logger is not None else LOG
        self.logger_extra = logger_extra_args
        # initialize variables
        self.content_types = {}
        self.specifications = specifications if isinstance(specifications, list) else [specifications]
        self.new_reqif_id_mapping = collections.defaultdict(dict)  # Classname -> cdb_object_id -> reqif_id
        self.reqif_id_mapping = {}  # cdb_object_id -> ReqIFIDTuple
        self.reqif_validator = ReqIFValidator()
        self.referenced_attachments = []
        self.profile = None
        self.replace_variables = replace_variables
        self.export_target_values = export_target_values
        self.process_run = process_run
        with profiling.profile():
            ReqIFNodes.register_namespaces()
            self._load_mapping_information(profile)
            self._load_content_types()
            self.logger.info(
                u"Start ReqIF-Export for '%s' with Profile: '%s'", ",".join(
                    [x.spec_id for x in self.specifications]),
                self.profile.profile_name
            )
            stop = datetime.datetime.now()
            self.logger.debug('initialization took: %s', (stop - start).total_seconds())

    def _get_datatype_xhtml(self):
        identifier = createUniqueIdentifier()
        return identifier, ReqIFNodes.reqif_datatype_definition_xhtml(
            **{
                'LONG-NAME': u"XHTML",
                'LAST-CHANGE': createXsdDateTime(),
                'IDENTIFIER': identifier,
                'DESC': 'XHTML Data Type'
            }
        )

    def _get_datatype_string(self):
        identifier = createUniqueIdentifier()
        return identifier, ReqIFNodes.reqif_datatype_definition_string(
            **{
                'LONG-NAME': u"String",
                'LAST-CHANGE': createXsdDateTime(),
                'IDENTIFIER': identifier,
                'DESC': 'String Data Type',
                'MAX-LENGTH': str(32000)
            }
        )

    def _get_datatype_integer(self):
        identifier = createUniqueIdentifier()
        return identifier, ReqIFNodes.reqif_datatype_definition_integer(
            **{
                'LONG-NAME': u"Integer",
                'LAST-CHANGE': createXsdDateTime(),
                'IDENTIFIER': identifier,
                'DESC': 'Integer Data Type',
                'MAX': str(sys.maxsize),
                'MIN': str(-sys.maxsize - 1)
            }
        )

    def _get_datatype_real(self):
        identifier = createUniqueIdentifier()
        return identifier, ReqIFNodes.reqif_datatype_definition_real(
            **{
                'LONG-NAME': u"Float",
                'LAST-CHANGE': createXsdDateTime(),
                'IDENTIFIER': identifier,
                'DESC': 'Float Data Type',
                'MAX': str(sys.float_info.max),
                'MIN': str(-sys.float_info.max),  # https://stackoverflow.com/questions/25493580/pythons-negative-threshold-the-lowest-non-infinity-negative-number - as we do not need the smallest positive (greater zero) float value,
                'ACCURACY': '2'
            }
        )

    def _get_datatype_date(self):
        identifier = createUniqueIdentifier()
        return identifier, ReqIFNodes.reqif_datatype_definition_date(
            **{
                'LONG-NAME': u"Date",
                'LAST-CHANGE': createXsdDateTime(),
                'IDENTIFIER': identifier,
                'DESC': 'Date Data Type',
            }
        )

    def _get_datatype_enumeration(self):
        # enum attributes are different when internal_field_name is different
        attribute_mappings = self.profile.AllAttributes.KeywordQuery(
            data_type='enumeration'
        )
        prop_codes = [
            attribute_mapping.internal_field_name for
            attribute_mapping in attribute_mappings
        ]
        props = {prop.code: prop for prop in ClassProperty.KeywordQuery(code=prop_codes)}
        classification_class_ids = [prop.classification_class_id for prop in props.values()]
        classification_class_codes = ClassificationClass.oids_to_code(classification_class_ids)
        enumeration_definitions = []
        enumerations_by_attribute = {}
        enum_value_ids_by_attribute = collections.defaultdict(dict)
        enum_default_ids_by_attribute = {}
        # the same classification class property may occur in different reqif entities
        # with different enum mappings
        for attribute_mapping in attribute_mappings:
            if (
                attribute_mapping.is_mapped_enumeration or
                attribute_mapping.internal_field_name not in enumerations_by_attribute
            ):
                prop = props.get(attribute_mapping.internal_field_name)
                default_enum_value_id = None
                enum_value_objects = ClassPropertyValuesView.get_catalog_value_objects(
                    classification_class_codes[prop.classification_class_id],
                    prop.code,
                    True
                )
                if attribute_mapping.is_mapped_enumeration:
                    enum_dt_long_name = attribute_mapping.external_field_name
                    enum_dt_identifier = attribute_mapping.cdb_object_id
                    enum_mapping = attribute_mapping.get_internal_to_external_map()
                else:
                    enum_dt_long_name = prop.code
                    enum_dt_identifier = prop.cdb_object_id
                enum_values = []
                key = 0
                for enum_val in enum_value_objects:
                    classification_val = rqm_utils.get_classification_val(enum_val, language="en")
                    if attribute_mapping.is_mapped_enumeration:
                        val_id, val = enum_mapping.get(
                            enum_val.cdb_object_id,
                            (
                                enum_val.value_oid,  # fallback to default
                                classification_val
                            )
                        )
                        val_id = prefixID(val_id)
                    else:
                        val = classification_val
                        val_id = prefixID(enum_val.value_oid)
                    # get default enum value of prop if it has some
                    if prop.default_value_oid and enum_val.value_oid == prop.default_value_oid:
                        default_enum_value_id = val_id # use prefixed val id and also mapped if it is mapped
                    str_val = self._convert_enum_value_to_str(val)
                    enum_values.append(
                        ReqIFNodes.reqif_enum_value(
                            key=str(key),
                            other_content=str_val,
                            **{
                                'IDENTIFIER': val_id,
                                'LAST-CHANGE': createXsdDateTime(),
                                'LONG-NAME': str_val
                            }
                        )
                    )
                    if (
                        not attribute_mapping.is_mapped_enumeration and
                        attribute_mapping.internal_field_name not in enum_value_ids_by_attribute or
                        val not in enum_value_ids_by_attribute[attribute_mapping.internal_field_name]
                    ):
                        enum_value_ids_by_attribute[
                            attribute_mapping.internal_field_name
                        ][classification_val] = val_id
                    else:
                        enum_value_ids_by_attribute[attribute_mapping.cdb_object_id][classification_val] = val_id
                    key += 1
                if default_enum_value_id is not None and attribute_mapping.is_mapped_enumeration:
                    enum_default_ids_by_attribute[attribute_mapping.cdb_object_id] = default_enum_value_id
                elif default_enum_value_id is not None and not attribute_mapping.is_mapped_enumeration:
                    enum_default_ids_by_attribute[attribute_mapping.internal_field_name] = default_enum_value_id
                enumeration_id = prefixID(enum_dt_identifier)
                enumeration_definition = ReqIFNodes.reqif_datatype_definition_enumeration(
                    enum_values, **{
                        'LONG-NAME': enum_dt_long_name,
                        'LAST-CHANGE': createXsdDateTime(),
                        'IDENTIFIER': enumeration_id,
                        'DESC': "Enumeration Data Type for {}".format(prop.code)
                    }
                )
                enumeration_definitions.append(enumeration_definition)
                if (
                    not attribute_mapping.is_mapped_enumeration and
                    attribute_mapping.internal_field_name not in enumerations_by_attribute
                ):
                    enumerations_by_attribute[
                        attribute_mapping.internal_field_name
                    ] = enumeration_id
                else:
                    enumerations_by_attribute[
                        attribute_mapping.cdb_object_id
                    ] = enumeration_id
        return enumeration_definitions, enumerations_by_attribute, enum_value_ids_by_attribute, enum_default_ids_by_attribute

    def _get_datatype_definitions(self):
        data_types_used = set(self.profile.AllAttributes.data_type)
        data_type_generators = {
            'xhtml': self._get_datatype_xhtml,
            'char': self._get_datatype_string,
            'long text': self._get_datatype_string,
            'integer': self._get_datatype_integer,
            'float': self._get_datatype_real,
            'date': self._get_datatype_date,
        }
        generators_used = set()
        data_type_definitions = []
        enum_value_ids_by_attribute = {}
        enum_default_ids_by_attribute = {}
        data_type_definitions_by_type = collections.defaultdict(dict)
        for data_type in data_types_used:
            if data_type == 'enumeration':
                continue  # skip for now as it is specially handled
            generator = data_type_generators.get(data_type)
            if not generator:
                raise NotImplementedError('%s is not supported actually', data_type)
            if generator not in generators_used:
                identifier, definition = generator()
                data_type_definitions_by_type[data_type] = identifier
                data_type_definitions.append(definition)
                generators_used.add(generator)
            else:
                # ensure str data type is referenced for booth types
                if data_type == 'long text':
                    data_type_definitions_by_type['long text'] = data_type_definitions_by_type['char']
                elif data_type == 'char':
                    data_type_definitions_by_type['char'] = data_type_definitions_by_type['long text']

        if 'enumeration' in data_types_used:
            (
                enumeration_definitions,
                enumerations_by_attribute,
                enum_value_ids_by_attribute,
                enum_default_ids_by_attribute
            ) = self._get_datatype_enumeration()
            data_type_definitions_by_type['enumeration'] = enumerations_by_attribute
            data_type_definitions.extend(enumeration_definitions)
        return (
            data_type_definitions,
            data_type_definitions_by_type,
            enum_value_ids_by_attribute,
            enum_default_ids_by_attribute
        )

    def _get_semantic_link_relation_group_type(self):
        """
        """
        spec_relation_group_type = ReqIFNodes.reqif_relation_group_type(
            **{
                'IDENTIFIER': 'cdb_semantic_link',
                'LAST-CHANGE': createXsdDateTime()
            }
        )
        return spec_relation_group_type

    def export(self, export_file):
        """
        Exports the internal structure into ReqIF file.

        @param export_file: can be a file-like object or a path to an file

        """
        with profiling.profile():
            return self._export(export_file)

    def _export(self, export_file):
        """
        Exports the internal structure into ReqIF file.

        @param export_file: can be a file-like object or a path to an file

        """
        start = datetime.datetime.now()
        if isinstance(export_file, str):
            server_file_name = jail_filename(CADDOK.TMPDIR, os.path.splitext(export_file)[0] + '.reqifz')
            reqif_name = os.path.splitext(os.path.basename(export_file))[0] + '.reqif'
            server_dir_name = os.path.dirname(server_file_name)
        else:
            # support file-like objects
            server_file_name = export_file
            reqif_name = os.path.splitext(os.path.basename(server_file_name.name))[0] + '.reqif' if hasattr(server_file_name, 'name') else 'export.reqif'
            server_dir_name = CADDOK.TMPDIR

        self.logger.debug("Write Export File '%s'..." % server_file_name)
        with zipfile.ZipFile(server_file_name, mode='w', allowZip64=True) as zf:
            info = zipfile.ZipInfo(
                reqif_name,
                date_time=time.localtime(time.time()),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            exported_doc = self.create_reqif_document()
            contentstr = etree.tostring(
                exported_doc,
                standalone=True,
                method=RichTextModifications.DEFAULT_SERIALIZATION
            )
            self.reqif_validator.validate(BytesIO(contentstr))
            zf.writestr(info, contentstr)
            for attachment in self.referenced_attachments:
                file_obj = attachment['file_obj']
                if attachment['object_reqif_id'] != '':
                    arcname = os.path.join(attachment['object_reqif_id'], file_obj.cdbf_name)
                else:
                    arcname = os.path.join(file_obj.cdbf_object_id, file_obj.cdbf_name)
                fp = jail_filename(server_dir_name, file_obj.cdbf_name)
                file_obj.checkout_file(fp)
                zf.write(fp, arcname=arcname)
                os.remove(fp)
        for specification in self.specifications:
            specification.reqif_id_locked = 1
        stop = datetime.datetime.now()
        self.logger.debug('export took: %s', (stop - start).total_seconds())
        return server_file_name

    def _get_attribute_definition(self, attribute):
        attribute_definition_generators = {
            'xhtml': ReqIFNodes.reqif_attribute_definition_xhtml,
            'char': ReqIFNodes.reqif_attribute_definition_string,
            'long text': ReqIFNodes.reqif_attribute_definition_string,
            'integer': ReqIFNodes.reqif_attribute_definition_integer,
            'float': ReqIFNodes.reqif_attribute_definition_real,
            'date': ReqIFNodes.reqif_attribute_definition_date,
            'enumeration': ReqIFNodes.reqif_attribute_definition_enumeration,
        }
        generator = attribute_definition_generators.get(attribute.data_type)
        if not generator:
            raise NotImplementedError('unsupported data type %s', attribute.data_type)
        attribute_data_type_ref_id = self.data_type_definitions_by_type[attribute.data_type]
        data = {
            "LONG-NAME": attribute.external_field_name,
            "LAST-CHANGE": createXsdDateTime(),
            "IDENTIFIER": attribute.external_identifier,
            "DESC": attribute.internal_field_name,
            "IS-EDITABLE": "true" if attribute.is_editable else "false"
        }
        if attribute.data_type == 'enumeration':
            if attribute.is_mapped_enumeration:
                attribute_data_type_ref_id = self.data_type_definitions_by_type[
                    attribute.data_type][attribute.cdb_object_id]
                if (
                    attribute.cdb_object_id in self.enum_default_ids_by_attribute and
                    self.enum_default_ids_by_attribute[attribute.cdb_object_id]
                ):
                    default_enum_value_id = self.enum_default_ids_by_attribute[attribute.cdb_object_id]
                    data['DEFAULT-VALUE'] = ReqIFNodes.reqif_attribute_value_enumeration(
                        attribute_ref=attribute.external_identifier,
                        value=[default_enum_value_id]
                    )
            else:
                attribute_data_type_ref_id = self.data_type_definitions_by_type[
                    attribute.data_type][attribute.internal_field_name]
                if (
                    attribute.internal_field_name in self.enum_default_ids_by_attribute and
                    self.enum_default_ids_by_attribute[attribute.internal_field_name]
                ):
                    default_enum_value_id = self.enum_default_ids_by_attribute[attribute.internal_field_name]
                    data['DEFAULT-VALUE'] = ReqIFNodes.reqif_attribute_value_enumeration(
                        attribute_ref=attribute.external_identifier,
                        value=[default_enum_value_id]
                    )
            data['MULTI-VALUED'] = "true" if attribute.is_multivalued else "false"

        attribute_definition = generator(
            attribute_data_type_ref_id,
            **data
        )
        return attribute_definition

    def _get_spec_types(self):
        spec_types = {
            'spec_object_types': {},
            'specification_types': {}
        }
        spec_object_type_list = []
        specification_type_list = []

        for entities in self.mapping_entities_by_external_object_type.values():
            attributes = {}
            dst_entity = None
            # Spec types with the same external_object_type ID can only be present once
            for entity in entities:
                if dst_entity is None:
                    dst_entity = entity
                # SpecAttributes with external identifier can only be present once
                attributes.update(
                    {
                        x.external_identifier: x for x in
                        self.mapping_attributes_by_entity_mapping[
                            entity.cdb_object_id
                        ].values()
                    }
                )

            spec_attributes = []
            for attribute in attributes.values():
                spec_attribute = self._get_attribute_definition(attribute)
                spec_attributes.append(spec_attribute)
            identifier = prefixID(dst_entity.external_object_type)
            if dst_entity.object_type_field_name or dst_entity.object_type_field_value:
                desc = "{} ({}/{})".format(
                    dst_entity.internal_object_type,
                    dst_entity.object_type_field_name,
                    dst_entity.object_type_field_value
                )
            else:
                desc = dst_entity.internal_object_type
            type_attributes = {
                'IDENTIFIER': identifier,
                'LAST-CHANGE': createXsdDateTime(),
                'SPEC-ATTRIBUTES': spec_attributes,
                'LONG-NAME': dst_entity.external_object_type_longname,
                'DESC': desc
            }
            if not dst_entity.is_top_level:
                # a spec object type per configured non top level dst_entity
                spec_object_type = ReqIFNodes.reqif_spec_object_type(
                    **type_attributes
                )
                spec_types['spec_object_types'][dst_entity.external_object_type] = identifier
                spec_object_type_list.append(spec_object_type)
                self.logger.debug('Created SPEC-OBJECT-TYPE for {}'.format(dst_entity.external_object_type))
            elif dst_entity.is_top_level:
                # a specification type per configured top level dst_entity
                specification_type = ReqIFNodes.reqif_specification_type(
                    **type_attributes
                )
                spec_types['specification_types'][dst_entity.external_object_type] = identifier
                specification_type_list.append(specification_type)
                self.logger.debug('Created SPECIFICATION-TYPE for {}'.format(dst_entity.external_object_type))
        return spec_object_type_list, specification_type_list, spec_types

    def _get_spec_relation_types(self):
        spec_relation_types = []
        for link_type in self.mapping_relation_types:
            data = {
                'IDENTIFIER': prefixID(link_type.external_link_type),
                'LONG-NAME': link_type.link_name,
                'LAST-CHANGE': createXsdDateTime(),
                'DESC': '%s %s %s' % (
                    link_type.subject_classname,
                    link_type.link_name,
                    link_type.object_classname
                )
            }
            spec_relation_type = ReqIFNodes.reqif_spec_relation_type(**data)
            spec_relation_types.append(spec_relation_type)
            self.logger.debug("Created SPEC-RELATION-TYPE for {}".format(link_type))
        return spec_relation_types

    def __get_char(self, maybe_string):
        value = "%s" % maybe_string if maybe_string is not None else None
        return value

    def __get_float(self, maybe_float):  # NaN won't work when we have min/max values defined in ReqMan
        value = maybe_float if maybe_float is not None else None
        return value

    def __get_date(self, maybe_date):
        value = createXsdDateTime(maybe_date) if maybe_date is not None else None
        return value

    def __get_int(self, maybe_int):
        value = maybe_int if maybe_int is not None else None
        return value

    def __get_raw_value(self, obj, attr, tree_down_context):
        if attr.is_classification_property():
            classification_cache = tree_down_context.get('classification_cache')
            obj_classification = classification_cache.get(obj.cdb_object_id)
            if obj_classification:
                values = obj_classification.get(attr.internal_field_name)
                if values:
                    return rqm_utils.get_classification_val(values[0], language="en")
        else:
            try:
                return obj[attr.internal_field_name]
            except AttributeError:
                if attr.internal_field_name in obj.GetTextFieldNames():
                    content = obj.GetText(attr.internal_field_name)
                    obj_classname = obj.GetClassname()
                    field_name = attr.internal_field_name
                    if (
                        self.content_types.get(obj_classname).get(field_name) == 'XHTML' and
                        attr.data_type == 'char'
                    ):
                        content = strip_tags(content)
                    return content
                else:
                    self.log(
                        "error",
                        "Failed to access attribute %s of %s",
                        attr.internal_field_name, obj.GetClassname()
                    )
                    raise

    def _get_xhtml_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        value = None
        if mapping_attr.is_reference_link:
            value = "<xhtml:div><xhtml:a href=\"{web_ui_link}\">{web_ui_label}</xhtml:a></xhtml:div>".format(
                web_ui_link=obj.MakeURL(plain=3),
                web_ui_label=util.get_label('cdbrqm_reqif_object_ref_link_name')
            )
        else:

            long_text_cache = tree_down_context.get('long_text_cache').get(
                obj.GetClassname()
            )
            if mapping_attr.internal_field_name in obj.GetTextFieldNames():
                value = long_text_cache.get(
                    mapping_attr.internal_field_name, {}
                ).get(obj.cdb_object_id) if long_text_cache else obj.GetText(
                    mapping_attr.internal_field_name
                )
            value = self.__get_char(value)
            self.logger.debug(
                "Export Attribute: '%s'='%s'" % (
                    mapping_attr.internal_field_name,
                    value
                )
            )
            if value:
                file_cache = tree_down_context.get('file_cache')
                language = mapping_attr.internal_field_name.split('_')[-1]
                attribute_values = {language: value}
                object_data_replacements = RichTextModifications.get_richtext_object_data_replacements_filenames_to_external_links(
                    obj=obj, file_cache=file_cache, file_link_rest_replacement=False, attribute_values=attribute_values
                )
                if self.replace_variables:
                    classification_values = (
                        tree_down_context.get('classification_cache', {}).get(obj.specification_object_id, {})
                    )
                    classification_values.update(
                        tree_down_context.get('classification_cache', {}).get(obj.cdb_object_id, {})
                    )
                    try:
                        value = RichTextModifications.set_variables_and_file_links(
                            xhtml_text=value,
                            variable_values=classification_values,
                            replace_variable_nodes_with_values=True,
                            raise_for_empty_value=True,
                            language=language,
                            object_data_replacements=object_data_replacements
                        )
                    except exceptions.MissingVariableValueError as e:
                        raise ue.Exception(
                            "just_a_replacement",
                            "Missing variable value for %s on object %s" % (
                                e.variable_id, obj.GetDescription()
                            )
                        )
                else:
                    value = RichTextModifications.set_file_links(
                        xhtml_text=value,
                        object_data_replacements=object_data_replacements
                    )
                if hasattr(obj, 'Files'):
                    for f in file_cache.get(obj.cdb_object_id, []):
                        if f.cdbf_name in value or saxutils.escape(f.cdbf_name) in value:
                            self.referenced_attachments.append({'file_obj': f, 'object_reqif_id': obj.reqif_id})
                try:
                    self.reqif_validator.has_valid_xhtml_field_content(value)
                except ReqIFValidationError as e:
                    self.logger.exception(e)
                    raise ue.Exception("just_a_replacement", "{}:\n{}".format(obj.GetDescription(), e))
                value = ReqIFNodes.reqif_attribute_value_xhtml(
                    attribute_ref=attribute_ref,
                    value=value
                )
            else:
                self.logger.debug("Found an empty XHTML (%s) -> will not be exported" % mapping_attr.internal_field_name)
            return value

    def _get_char_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        raw_value = self.__get_raw_value(obj, mapping_attr, tree_down_context)
        value = self.__get_char(raw_value)
        self.logger.debug("Export Attribute: '%s'='%s'" % (mapping_attr.internal_field_name, value))
        if value is not None:
            value = ReqIFNodes.reqif_attribute_value_string(
                attribute_ref=attribute_ref,
                value=value
            )
        else:
            self.logger.debug("Found an empty String (%s) ->  will not be exported" % mapping_attr.internal_field_name)
        return value

    def _get_int_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        raw_value = self.__get_raw_value(obj, mapping_attr, tree_down_context)
        value = self.__get_int(raw_value)
        self.logger.debug("Export Attribute: '%s'='%s'" % (mapping_attr.internal_field_name, value))
        if value is not None:
            value = ReqIFNodes.reqif_attribute_value_integer(
                attribute_ref=attribute_ref,
                value=value
            )
        else:
            self.logger.debug("Found an empty Integer (%s) -> will not be exported" % mapping_attr.internal_field_name)
        return value

    def _get_float_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        raw_value = self.__get_raw_value(obj, mapping_attr, tree_down_context)
        value = self.__get_float(raw_value)
        self.logger.debug("Export Attribute: '%s'='%s'" % (mapping_attr.internal_field_name, value))
        if value is not None:
            value = ReqIFNodes.reqif_attribute_value_real(
                attribute_ref=attribute_ref,
                value=value
            )
        else:
            self.logger.debug("Found an empty Float (%s) ->  will not be exported" % mapping_attr.internal_field_name)
        return value

    def _get_date_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        raw_value = self.__get_raw_value(obj, mapping_attr, tree_down_context)
        value = self.__get_date(raw_value)
        self.logger.debug("Export Attribute: '%s'='%s'" % (mapping_attr.internal_field_name, value))
        if value is not None:
            value = ReqIFNodes.reqif_attribute_value_date(
                attribute_ref=attribute_ref,
                value=value
            )
        else:
            self.logger.debug("Found an empty Date (%s) -> will not be exported" % mapping_attr.internal_field_name)
        return value

    def _get_longtext_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        long_text_cache = tree_down_context.get('long_text_cache').get(obj.GetClassname())
        value = None
        if mapping_attr.internal_field_name in obj.GetTextFieldNames():
            value = (
                long_text_cache.get(
                    mapping_attr.internal_field_name, {}
                ).get(obj.cdb_object_id) if long_text_cache else
                obj.GetText(mapping_attr.internal_field_name)
            )
        value = self.__get_char(value)
        self.logger.debug(
            "Export Attribute: '%s'='%s'" % (
                mapping_attr.internal_field_name,
                value
            )
        )
        if value is not None:
            value = ReqIFNodes.reqif_attribute_value_string(
                attribute_ref=attribute_ref,
                value=value
            )
        else:
            self.logger.debug("Found an empty long text (%s) -> will not be exported" % mapping_attr.internal_field_name)
        return value

    def _get_enumeration_value(self, obj, attribute_ref, mapping_attr, tree_down_context):
        classification_cache = tree_down_context.get('classification_cache')
        obj_classification = classification_cache.get(obj.cdb_object_id)
        value = None
        if obj_classification:
            xml_values = []
            values = obj_classification.get(mapping_attr.internal_field_name, [])
            for raw_value in values:
                uc_value = rqm_utils.get_classification_val(raw_value, language="en")
                self.logger.debug(
                    "Export Attribute: '%s'='%s'" % (
                        mapping_attr.internal_field_name,
                        uc_value
                    )
                )
                if uc_value is not None:
                    try:
                        xml_values.append(
                            self.enum_value_ids_by_attribute.get(
                                mapping_attr.cdb_object_id,
                                self.enum_value_ids_by_attribute.get(
                                    mapping_attr.internal_field_name
                                )
                            )[uc_value]
                        )
                    except KeyError:
                        LOG.error("%s is missing in %s", uc_value, self.enum_value_ids_by_attribute.get(
                                mapping_attr.cdb_object_id,
                                self.enum_value_ids_by_attribute.get(
                                    mapping_attr.internal_field_name
                                )
                        ))
                        raise
            if xml_values:
                value = ReqIFNodes.reqif_attribute_value_enumeration(
                    attribute_ref=attribute_ref,
                    value=xml_values
                )
            else:
                self.logger.debug("Found an emty Enumeration (%s) -> will not be exported" % mapping_attr.internal_field_name)
        return value

    def _get_values(self, entity, tree_down_context, obj):
        node_fn = {
            'xhtml': self._get_xhtml_value,
            'char': self._get_char_value,
            'long text': self._get_longtext_value,
            'integer': self._get_int_value,
            'float': self._get_float_value,
            'date': self._get_date_value,
            'enumeration': self._get_enumeration_value
        }
        values = []
        entity_mapping_attrs = self.mapping_attributes_by_entity_mapping[entity.cdb_object_id]
        for attribute_ref, mapping_attribute in entity_mapping_attrs.items():
            node_func = node_fn.get(mapping_attribute.data_type)
            if not node_func:
                raise NotImplementedError('unknown data type: %s' % mapping_attribute.data_type)
            value_node = node_func(
                obj, attribute_ref, mapping_attribute, tree_down_context
            )
            if value_node is not None:
                values.append(
                    value_node
                )
        return values

    def _get_children(self, tree_down_context, spec_ref):

        def recursive_children(tree_down_context, obj=None, level=0):
            root = tree_down_context.get('root')
            children = root._tree_depth_first_next(tree_down_context, parent=obj, with_target_values=self.export_target_values)
            spec_objects = []
            child_hierarchies = []
            for child in children:
                sub_spec_objects, sub_child_hierarchies = recursive_children(tree_down_context, child, level=level + 1)
                spec_object_id, spec_object_node = self._get_spec_object(tree_down_context, child)
                spec_objects.append(spec_object_node)
                spec_objects.extend(sub_spec_objects)
                child_hierarchy = ReqIFNodes.reqif_spec_hierarchy(
                    spec_object_id,
                    **{
                        'IDENTIFIER': createUniqueIdentifier(),
                        'LAST-CHANGE': createXsdDateTime(),
                        'LONG-NAME': child.get_reqif_long_name(),
                        'DESC': "Spec Hierarchy: %s" % child.get_reqif_description(),
                        'CHILDREN': sub_child_hierarchies
                    }
                )
                child_hierarchies.append(child_hierarchy)
            return spec_objects, child_hierarchies

        return recursive_children(tree_down_context)

    def _get_spec_object(self, tree_down_context, spec_object):
        entity = self._get_entity_mapping(obj=spec_object)
        if not entity:
            raise ue.Exception("cdbrqm_reqif_missing_entity_mapping", spec_object)
        else:
            spec_object_type_ref = self.spec_types['spec_object_types'][entity.external_object_type]
            values = self._get_values(entity, tree_down_context, spec_object)
            unique_identifier = spec_object.reqif_id
            if not unique_identifier:
                unique_identifier = createUniqueIdentifier()
                # queue for later batch updating
                self.new_reqif_id_mapping[spec_object.GetClassname()][spec_object.cdb_object_id] = unique_identifier
            self.reqif_id_mapping[spec_object.cdb_object_id] = ReqIFIDTuple(
                spec_object.specification_object_id, unique_identifier
            )

            return unique_identifier, ReqIFNodes.reqif_spec_object(
                spec_object_type_ref, **{
                    'IDENTIFIER': unique_identifier,
                    'LAST-CHANGE': createXsdDateTime(spec_object.cdb_mdate),
                    'LONG-NAME': spec_object.get_reqif_long_name(),
                    'DESC': spec_object.get_reqif_description(),
                    'VALUES': values
                }
            )

    def _get_specification(self, tree_down_context, spec):
        entity = self._get_entity_mapping(obj=spec)
        if not entity:
            raise ue.Exception("cdbrqm_reqif_missing_entity_mapping", spec)
        else:
            specification_type_ref = self.spec_types['specification_types'][entity.external_object_type]
            values = self._get_values(entity, tree_down_context, spec)
            unique_identifier = spec.reqif_id
            if not unique_identifier:
                unique_identifier = createUniqueIdentifier()
                # queue for later batch updating
                self.new_reqif_id_mapping[spec.GetClassname()][spec.cdb_object_id] = unique_identifier
            self.reqif_id_mapping[spec.cdb_object_id] = ReqIFIDTuple(
                spec.cdb_object_id, unique_identifier
            )

            spec_objects, children = self._get_children(tree_down_context, unique_identifier)
            return spec_objects, ReqIFNodes.reqif_specification(
                specification_type_ref, **{
                    'IDENTIFIER': unique_identifier,
                    'LAST-CHANGE': createXsdDateTime(spec.cdb_mdate),
                    'LONG-NAME': spec.get_reqif_long_name(),
                    'DESC': spec.get_reqif_description(),
                    'VALUES': values,
                    'CHILDREN': children
                }
            )

    def _get_spec_relations(self, semantic_link_cache):
        spec_relations = []
        spec_relation_groups_to_create = collections.defaultdict(list)
        spec_relation_groups = []
        allowed_link_types = {x.link_type_object_id: x for x in self.mapping_relation_types}
        for semantic_links in semantic_link_cache.values():
            for semantic_link in semantic_links:
                if (
                    semantic_link.link_type_object_id in allowed_link_types and
                    semantic_link.object_object_id in semantic_link_cache
                ):
                    mapping_relation_type = allowed_link_types.get(semantic_link.link_type_object_id)
                    source = self.reqif_id_mapping[semantic_link.subject_object_id]
                    target = self.reqif_id_mapping[semantic_link.object_object_id]
                    spec_relation_id = createUniqueIdentifier()
                    spec_relation = ReqIFNodes.reqif_spec_relation(
                        source_ref=source.reqif_id,
                        target_ref=target.reqif_id,
                        spec_relation_type_ref=prefixID(mapping_relation_type.external_link_type),
                        **{
                            'IDENTIFIER': spec_relation_id,
                            'LAST-CHANGE': createXsdDateTime()
                        }
                    )
                    spec_relations.append(spec_relation)
                    spec_relation_groups_to_create[
                        (source.specification_object_id, target.specification_object_id)
                    ].append(
                        spec_relation_id
                    )
        for (source_spec_id, target_spec_id), spec_relation_ids in spec_relation_groups_to_create.items():
            relation_group = ReqIFNodes.reqif_relation_group(
                'cdb_semantic_link',
                source_spec_id,
                target_spec_id,
                **{
                    'IDENTIFIER': createUniqueIdentifier(),
                    'LAST-CHANGE': createXsdDateTime(),
                    'SPEC-RELATIONS': spec_relation_ids
                }
            )
            spec_relation_groups.append(relation_group)

        return spec_relations, spec_relation_groups

    def _get_contents(self):
        spec_objects = []
        specifications = []
        semantic_link_cache = {}

        for specification in self.specifications:
            self.logger.debug(
                u"Add Specification Objects to 'Specifications' ... '%s'" % [
                    x.get_reqif_long_name() for x in self.specifications
                ]
            )
            tree_down_context = RQMHierarchicals.get_tree_down_context(
                specification, with_file_cache=True, with_semantic_link_cache=True
            )
            semantic_link_cache.update(tree_down_context.get('semantic_link_cache'))
            spec_object_nodes, specification_node = self._get_specification(
                tree_down_context, spec=specification
            )
            specifications.append(specification_node)
            spec_objects.extend(spec_object_nodes)
        spec_relations, spec_relation_groups = self._get_spec_relations(
            semantic_link_cache
        )
        self._update_new_reqif_ids()
        return (
            spec_objects,
            spec_relations,
            specifications,
            spec_relation_groups
        )

    def _get_update_new_reqif_id_statement_chunks(self, clazz, new_ids, max_chunk_size=1000):
        chunks = []
        i = 0
        when_then_condition = ""
        chunk_keys = []
        for cdb_object_id, reqif_id in new_ids.items():
            chunk_keys.append(cdb_object_id)
            when_then_condition += " WHEN cdb_object_id='{cdb_object_id}' THEN '{reqif_id}'".format(
                cdb_object_id=cdb_object_id, reqif_id=reqif_id
            )
            i += 1
            if i >= max_chunk_size:
                stmt = "{table} SET reqif_id = CASE {when_then_condition} END WHERE {condition}".format(
                    table=clazz.__maps_to__,
                    when_then_condition=when_then_condition,
                    condition=clazz.cdb_object_id.one_of(*chunk_keys)
                )
                chunks.append(stmt)
                when_then_condition = ""  # clear for next chunk
                i = 0
                chunk_keys = []
        if when_then_condition:
            stmt = "{table} SET reqif_id = CASE {when_then_condition} END WHERE {condition}".format(
                table=clazz.__maps_to__,
                when_then_condition=when_then_condition,
                condition=clazz.cdb_object_id.one_of(*chunk_keys)
            )
            chunks.append(stmt)
        return chunks

    def _update_new_reqif_ids(self):
        for class_name, new_ids in self.new_reqif_id_mapping.items():
            clazz = ClassRegistry().findByClassname(class_name)
            chunks = self._get_update_new_reqif_id_statement_chunks(clazz, new_ids)
            updated = 0
            for chunk in chunks:
                updated += sqlapi.SQLupdate(chunk)
            if updated != len(new_ids.keys()):
                msg = 'Update of reqif ids for classname %s failed, updated %d expected %d' % (
                    class_name, updated, len(new_ids.keys())
                )
                self.log(
                    "error",
                    msg
                )
                raise AssertionError(msg)

    def create_reqif_document(self):
        export_run_id = prefixID(self.process_run.cdb_object_id) if self.process_run is not None else prefixID(cdbuuid.create_uuid())

        comment = util.get_label("cdbrqm_reqif_exp_comment") % self.profile.GetDescription()
        (
            data_type_definitions,
            self.data_type_definitions_by_type,  # lut
            self.enum_value_ids_by_attribute,  # lut
            self.enum_default_ids_by_attribute # lut
        ) = self._get_datatype_definitions()
        data_types = ReqIFNodes.reqif_datatypes(
            data_type_definitions
        )
        semantic_link_relation_group_type = self._get_semantic_link_relation_group_type()
        (
            spec_object_types,
            specification_types,
            self.spec_types  # lut
        ) = self._get_spec_types()
        spec_relation_types = self._get_spec_relation_types()
        spec_types = ReqIFNodes.reqif_spec_types(
            [semantic_link_relation_group_type],  # as of now only one relation group type
            spec_object_types,
            spec_relation_types,
            specification_types
        )
        (
            _spec_objects,
            _spec_relations,
            _specifications,
            _spec_relation_groups
        ) = self._get_contents()
        spec_objects = ReqIFNodes.reqif_spec_objects(_spec_objects)
        spec_relations = ReqIFNodes.reqif_spec_relations(_spec_relations)
        specifications = ReqIFNodes.reqif_specifications(_specifications)
        spec_relation_groups = ReqIFNodes.reqif_spec_relation_groups(_spec_relation_groups)
        core_content = ReqIFNodes.reqif_core_content(
            data_types,
            spec_types,
            spec_objects,
            spec_relations,
            specifications,
            spec_relation_groups
        )
        # TODO: for multiple specs within one reqif we should find a better solution here
        export_title = util.get_label("cdbrqm_reqif_exp_title") % self.specifications[0].GetDescription()
        the_header = ReqIFNodes.reqif_the_header(
            reqif_header_id=export_run_id,
            title=export_title,
            reqif_version='1.0',
            comment=comment,
            repository_id=rte.environ.get('RQM_REQIF_REPOSITORY_ID', None)
        )
        exported_doc = ReqIFNodes.reqif_reqif(the_header, core_content)
        return exported_doc


if __name__ == "__main__":
    pass

