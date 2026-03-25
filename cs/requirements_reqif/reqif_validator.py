# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals, print_function
from io import BytesIO
import os
import logging
from lxml import etree
from lxml.etree import XMLSchema, DocumentInvalid, XMLSyntaxError
from cs.requirements_reqif.exceptions import ReqIFValidationError

LOG = logging.getLogger(__name__)


class ReferenceResolver(etree.Resolver):
    """
    Resolver for external entities
    """

    # well known namespaces we can resolve without network access
    URNS = {
        "http://www.w3.org/2001/xml.xsd": u"xml.xsd",
        "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd": "reqif.xsd",
        "http://www.w3.org/XML/1998/namespace": "xml.xsd",
        "http://www.omg.org/spec/ReqIF/20110402/driver.xsd": "driver.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-table-1.xsd": "xhtml-table-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-inlstyle-1.xsd": "xhtml-inlstyle-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-hypertext-1.xsd": "xhtml-hypertext-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-framework-1.xsd": "xhtml-framework-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-pres-1.xsd": "xhtml-pres-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-edit-1.xsd": "xhtml-edit-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-text-1.xsd": "xhtml-text-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-object-1.xsd": "xhtml-object-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-list-1.xsd": "xhtml-list-1.xsd",
        "http://www.w3.org/TR/xhtml-modularization/SCHEMA/xhtml-datatypes-1.xsd": "xhtml-datatypes-1.xsd"
    }

    def __init__(self, *args, **kwargs):
        self.resolve_external_uris = kwargs.pop('resolve_external_uris')
        self.schemas_path = kwargs.pop('schemas_path')
        super(ReferenceResolver, self).__init__(*args, **kwargs)

    def resolve(self, url, id, context):
        shortname = self.URNS.get(url)
        if shortname:
            path = os.path.join(self.schemas_path, shortname)
            if os.path.exists(path):
                LOG.debug("Resolving: %s [ID=%s] to %s", url, id, path)
                return self.resolve_filename(path, context)
            else:
                LOG.warn("XML Schema: %s [ID=%s] cannot be resolved to %s", url, id, path)
        if not self.resolve_external_uris and not url.startswith('file:/') and not url.startswith('/'):
            LOG.error("Should not resolve: %s [ID=%s]", url, id)
            raise ValueError("Should not resolve: %s [ID=%s]" % (url, id))


class ReqIFValidator(object):
    """Validate an ReqIF file against the strict ReqIF Schema"""

    dummy_reqif = '''<?xml version="1.0" encoding="utf-8"?> <REQIF:REQ-IF xmlns:REQIF="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd" xmlns:xhtml="http://www.w3.org/1999/xhtml"> <REQIF:THE-HEADER> <REQIF:REQ-IF-HEADER IDENTIFIER="header"> <REQIF:COMMENT></REQIF:COMMENT> <REQIF:CREATION-TIME>2017-11-22T12:49:20</REQIF:CREATION-TIME> <REQIF:REPOSITORY-ID></REQIF:REPOSITORY-ID> <REQIF:REQ-IF-TOOL-ID></REQIF:REQ-IF-TOOL-ID> <REQIF:REQ-IF-VERSION>1.0</REQIF:REQ-IF-VERSION> <REQIF:SOURCE-TOOL-ID></REQIF:SOURCE-TOOL-ID> <REQIF:TITLE></REQIF:TITLE> </REQIF:REQ-IF-HEADER> </REQIF:THE-HEADER> <REQIF:CORE-CONTENT> <REQIF:REQ-IF-CONTENT> <REQIF:DATATYPES> <REQIF:DATATYPE-DEFINITION-XHTML DESC="XHTML Data Type" IDENTIFIER="dt-richtext" LAST-CHANGE="2017-11-22T12:49:20" LONG-NAME="XHTML"/> </REQIF:DATATYPES> <REQIF:SPEC-TYPES> <REQIF:SPEC-OBJECT-TYPE DESC="" IDENTIFIER="req-type" LAST-CHANGE="2017-11-22T12:49:20" LONG-NAME=""> <REQIF:SPEC-ATTRIBUTES> <REQIF:ATTRIBUTE-DEFINITION-XHTML DESC="" IDENTIFIER="richtext" LAST-CHANGE="2017-11-22T12:49:20" LONG-NAME=""> <REQIF:TYPE> <REQIF:DATATYPE-DEFINITION-XHTML-REF>dt-richtext</REQIF:DATATYPE-DEFINITION-XHTML-REF> </REQIF:TYPE> </REQIF:ATTRIBUTE-DEFINITION-XHTML> </REQIF:SPEC-ATTRIBUTES> </REQIF:SPEC-OBJECT-TYPE> </REQIF:SPEC-TYPES> <REQIF:SPEC-OBJECTS> <REQIF:SPEC-OBJECT DESC="" IDENTIFIER="specobject" LAST-CHANGE="2017-11-22T12:49:05" LONG-NAME=""> <REQIF:VALUES> <REQIF:ATTRIBUTE-VALUE-XHTML> <REQIF:THE-VALUE>{}</REQIF:THE-VALUE> <REQIF:DEFINITION> <REQIF:ATTRIBUTE-DEFINITION-XHTML-REF>richtext</REQIF:ATTRIBUTE-DEFINITION-XHTML-REF> </REQIF:DEFINITION> </REQIF:ATTRIBUTE-VALUE-XHTML> </REQIF:VALUES> <REQIF:TYPE> <REQIF:SPEC-OBJECT-TYPE-REF>req-type</REQIF:SPEC-OBJECT-TYPE-REF> </REQIF:TYPE> </REQIF:SPEC-OBJECT> </REQIF:SPEC-OBJECTS> <REQIF:SPEC-RELATIONS/> <REQIF:SPECIFICATIONS/> <REQIF:SPEC-RELATION-GROUPS/> </REQIF:REQ-IF-CONTENT> </REQIF:CORE-CONTENT> </REQIF:REQ-IF>'''

    def __init__(self, resolve_external_uris=False):
        self.schemas_path = os.path.join(os.path.dirname(__file__), 'api', 'reqif', 'schemas')
        self.parser = etree.XMLParser(
            remove_comments=True,
            remove_pis=True,
            load_dtd=False,
            attribute_defaults=True,
            resolve_entities=True)
        resolver = ReferenceResolver(
            schemas_path=self.schemas_path,
            resolve_external_uris=resolve_external_uris
        )
        self.parser.resolvers.add(resolver)
        schema_root = etree.parse("http://www.omg.org/spec/ReqIF/20110401/reqif.xsd",
                                  parser=self.parser)
        self.schema = XMLSchema(schema_root)

    def validate(self, filename):
        # incremental validation, errors lacks correct line numbers
        for _ in etree.iterparse(filename, schema=self.schema, events=('end',)):
            pass

    def validate_in_memory(self, filename):
        # load everything into memory before processing it, errors have correct line numbers
        tree = etree.parse(filename, parser=self.parser)
        self.schema.assertValid(tree)
        return tree

    def has_valid_xhtml_field_content(self, content):
        reqif = self.dummy_reqif.format(content)
        content = BytesIO(reqif.encode('utf-8'))
        return self.is_valid(content)

    def is_valid(self, filename, incremental=True):
        try:
            if incremental:
                self.validate(filename)
            else:
                self.validate_in_memory(filename)
            return True
        except (DocumentInvalid, XMLSyntaxError) as e:
            raise ReqIFValidationError(e)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        if os.path.splitext(filename)[1].lower() == '.reqif':
            with open(filename, 'rb') as f:
                try:
                    if ReqIFValidator().is_valid(f):
                        print('valid ReqIF')
                except ReqIFValidationError as e:
                    if os.stat(filename).st_size < 10 * 1024 * 1024:  # 100 MB
                        try:
                            f.seek(0)
                            ReqIFValidator().is_valid(f, incremental=False)
                        except ReqIFValidationError as e2:
                            print('invalid: %s' % e2)
                    else:
                        print('invalid: %s' % e)
        else:
            print('unsupported file, currently only previously extracted reqif files')
