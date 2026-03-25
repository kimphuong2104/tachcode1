# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import argparse
import datetime
import io

from lxml import etree

from cdb import sqlapi
from cdb.platform import PropertyValue

from cs.classification import catalog, classes
from cs.classification.solr import SOLR_FIELD_TYPE_MAPPING_IGNORE_CASE, SOLR_FIELD_TYPE_MAPPING
from cs.classification.tools import get_active_classification_languages

XML_ENCODING = "unicode"


def add_solr_fields(solr_fields, outfile, parent):
    print("    Adding Solr fields ...")
    for _, solr_field in solr_fields.items():
        field = etree.SubElement(parent, 'field', attrib=solr_field)
        outfile.write('  ' + etree.tostring(field, encoding=XML_ENCODING, pretty_print=True))
        field.clear()


def tag_to_string(event, element):
    tag_attrs = ''
    if 'start' == event:
        for name, value in element.items():
            tag_attrs += ' {name}="{value}"'.format(name=name, value=value)
    tag = '<{tag_open}{tag_name}{tag_attrs}>{line_sep}'.format(
        tag_open='/' if 'end' == event else '',
        tag_name=element.tag,
        tag_attrs=tag_attrs,
        line_sep='\n'
    )
    return tag


def update_xml(xmlfile, output_file):

    solr_fields = get_solr_fields()

    start = datetime.datetime.utcnow()
    print("--- Creating new managed schema file ...")
    print("    Reading managed schema from " + xmlfile)

    doc = etree.iterparse(xmlfile, events=('start', 'end'))
    event, root = next(doc)

    with io.open(output_file, 'w', encoding='utf8') as outfile:
        outfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        outfile.write(tag_to_string(event, root))
        add_fields = True
        start_tag = None
        for event, element in doc:
            if event == 'start' and start_tag is None:
                start_tag = element.tag
            if event == 'end' and element.tag == start_tag:
                if 'field' == element.tag:
                    if add_fields:
                        add_solr_fields(solr_fields, outfile, root)
                        add_fields = False
                    if element.attrib['name'] not in solr_fields:
                        outfile.write(etree.tostring(element, encoding=XML_ENCODING))
                else:
                    outfile.write(etree.tostring(element, encoding=XML_ENCODING))
                start_tag = None
                root.clear()
        outfile.write(tag_to_string('end', root))

    end = datetime.datetime.utcnow()
    print("    Wrote managed schema to " + output_file)
    print("    Processing took: {}s".format((end - start).total_seconds()))


def get_solr_fields():
    start = datetime.datetime.utcnow()
    properties_to_sync = {}
    print("--- Querying classification properties ...")
    rset = sqlapi.RecordSet2(sql="SELECT cdb_classname, code from cs_property")
    for r in rset:
        properties_to_sync[r.code] = catalog.classname_type_map[r.cdb_classname]
    rset = sqlapi.RecordSet2(sql="SELECT cdb_classname, code from cs_class_property")
    for r in rset:
        properties_to_sync[r.code] = classes.classname_type_map[r.cdb_classname]
    print("    Found {} classification properties.".format(len(properties_to_sync)))

    qcla = PropertyValue.ByKeys("qcla", "Common Role", "public")
    if qcla and "0" == qcla.value:
        solr_type_mapping = SOLR_FIELD_TYPE_MAPPING_IGNORE_CASE
    else:
        solr_type_mapping = SOLR_FIELD_TYPE_MAPPING

    languages = get_active_classification_languages()
    solr_fields = {}
    for code, prop_type in properties_to_sync.items():
        solr_field_type = solr_type_mapping.get(prop_type, None)
        if solr_field_type is not None:
            if "multilang" == prop_type:
                for iso_code in languages:
                    solr_field_name = "{}_{}".format(code, iso_code)
                    solr_fields[solr_field_name] = dict(name=solr_field_name, type=solr_field_type)
            else:
                solr_fields[code] = dict(name=code, type=solr_field_type)

    print("    Lead to {} Solr fields".format(len(solr_fields)))

    end = datetime.datetime.utcnow()
    print("    Processing took: {}s".format((end - start).total_seconds()))

    return solr_fields


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Utiliy to update the managed schema file.')
    parser.add_argument("input", help="Path to existing managed schema file")
    parser.add_argument("output", help="Path to existing managed schema file")
    args = parser.parse_args()

    print ("Creating updated managed schema file")
    start = datetime.datetime.utcnow()
    input_file = args.input
    output_file = args.output
    update_xml(input_file, output_file)
    print ("Processing took: {}s".format((datetime.datetime.utcnow() - start).total_seconds()))
