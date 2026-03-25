# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


import datetime
import logging
import requests

from cdb import sig
from cdb import sqlapi
from cdb.platform import PropertyValue

from cs.classification import catalog
from cs.classification import classes
from cs.classification import solr
from cs.classification.tools import get_active_classification_languages
from cs.classification.units import UnitCache


LOG = logging.getLogger(__name__)


def get_solr_field_names(solr_connection):

    import lxml
    import os
    import tempfile

    field_names = set()
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as temp:
        url = "{}/schema/fields/?indent=on&wt=xml".format(solr_connection.endpoint)
        response = solr_connection.execute("get", "get solr fields: {}", url, stream=True)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=4096, decode_unicode=False):
            if chunk:  # filter out keep-alive new chunks
                temp.write(chunk)
        temp.close()
        for _, element in lxml.etree.iterparse(temp.name, tag="str"):
            if "name" in element.attrib and "name" == element.attrib["name"]:
                field_names.add(element.text)
        os.unlink(temp.name)
        return field_names


def send_solr_commands(solr_connection, output_func, new_solr_fields, update_solr_fields):
    import json

    send_solr_commands.solr_commands_last = 0
    send_solr_commands.solr_commands_send = 0

    def get_solr_command(operation, sep, field):
        if operation == "delete-field":
            field_data = '{"name": %s}' % field["name"]
        else:
            field_data = json.dumps(field, ensure_ascii=False)
        cmd = """{sep}"{operation}": {field_data}""".format(
            sep=sep,
            operation=operation,
            field_data=field_data
        )
        LOG.debug(cmd)
        send_solr_commands.solr_commands_send += 1
        if send_solr_commands.solr_commands_send >= send_solr_commands.solr_commands_last + 10000:
            if output_func:
                output_func("    Sent {} Solr commands ...".format(send_solr_commands.solr_commands_send))
            send_solr_commands.solr_commands_last = send_solr_commands.solr_commands_send
        return cmd.encode('utf-8')

    def get_solr_commands():
        yield b"{"
        operation = "add-field"
        sep = ""
        for field in new_solr_fields:
            yield get_solr_command(operation, sep, field)
            sep = ","
        operation = "replace-field"
        for field in update_solr_fields:
            yield get_solr_command(operation, sep, field)
            sep = ","
        yield b"}"

    url = "%s/%s" % (solr_connection.endpoint, "schema")
    response = solr_connection.execute("post", "", url, data=get_solr_commands())
    if send_solr_commands.solr_commands_send > send_solr_commands.solr_commands_last and output_func:
        output_func("    Sent {} Solr commands ...".format(send_solr_commands.solr_commands_send))

    try:
        response.raise_for_status()
        result = response.json()
        if 'errors' in result:
            msgs = []
            for errorMessage in result.get('errors'):
                msgs.append("".join(errorMessage.get('errorMessages', [])))
            raise solr.SolrCommandException("\n".join(msgs))
    except requests.exceptions.HTTPError:
        LOG.error('request error: %s', response.status_code)
        LOG.error('request details: %s\n%s\n', response.request.headers, url)


def process_fields(catalog_prop_query, class_prop_query, output_func=None, chunk_size=1000):
    if output_func:
        output_func("Resyncing schema to solr...")

    start = datetime.datetime.utcnow()
    properties_to_sync = {}

    if output_func:
        output_func("--- Querying classification properties ...")

    if catalog_prop_query:
        rset = sqlapi.RecordSet2(sql=catalog_prop_query)
        for r in rset:
            properties_to_sync[r.code] = catalog.classname_type_map[r.cdb_classname]
    if class_prop_query:
        rset = sqlapi.RecordSet2(sql=class_prop_query)
        for r in rset:
            properties_to_sync[r.code] = classes.classname_type_map[r.cdb_classname]

    if output_func:
        output_func("    Found {} classification properties.".format(len(properties_to_sync)))

    qcla = PropertyValue.ByKeys("qcla", "Common Role", "public")
    if qcla and "0" == qcla.value:
        solr_type_mapping = solr.SOLR_FIELD_TYPE_MAPPING_IGNORE_CASE
    else:
        solr_type_mapping = solr.SOLR_FIELD_TYPE_MAPPING

    if output_func:
        output_func("--- Retrieving existing solr fields ...")

    sc = solr._get_solr_connection()
    try:
        existing_solr_fields = get_solr_field_names(sc)
        if output_func:
            output_func("    Found {} existing solr fields.".format(len(existing_solr_fields)))
    except requests.exceptions.HTTPError as e:
        if output_func:
            output_func("    ERROR: Unable to get Solr field names! Make sure that Solr is available and run the script again.")
        LOG.exception(e)
        return

    new_solr_fields = []
    update_solr_fields = []

    languages = get_active_classification_languages()
    for code, prop_type in properties_to_sync.items():
        solr_field_type = solr_type_mapping.get(prop_type, None)
        if solr_field_type is not None:
            if "multilang" == prop_type:
                for iso_code in languages:
                    solr_field_name = "{}_{}".format(code, iso_code)
                    if solr_field_name in existing_solr_fields:
                        update_solr_fields.append(dict(name=solr_field_name, type=solr_field_type))
                    else:
                        new_solr_fields.append(dict(name=solr_field_name, type=solr_field_type))
            else:
                if code in existing_solr_fields:
                    update_solr_fields.append(dict(name=code, type=solr_field_type))
                else:
                    new_solr_fields.append(dict(name=code, type=solr_field_type))
        field_count = len(new_solr_fields) + len(update_solr_fields)
        if chunk_size != -1 and field_count > chunk_size:
            start_chunk = datetime.datetime.utcnow()
            if output_func:
                output_func("--- Processing {field_count} solr fields ({start_time})...".format(field_count=field_count, start_time=start_chunk))
            send_solr_commands(sc, output_func, new_solr_fields, update_solr_fields)
            progress_info = "    Processing took: {}m".format((datetime.datetime.utcnow() - start_chunk).total_seconds() / 60)
            if output_func:
                output_func(progress_info)
            new_solr_fields = []
            update_solr_fields = []

    field_count = len(new_solr_fields) + len(update_solr_fields)
    if field_count > 0:
        start_chunk = datetime.datetime.utcnow()
        if output_func:
            output_func("--- Processing {field_count} solr fields ({start_time})...".format(field_count=field_count, start_time=start_chunk))
        send_solr_commands(sc, output_func, new_solr_fields, update_solr_fields)
        progress_info = "    Processing took: {}m".format((datetime.datetime.utcnow() - start_chunk).total_seconds() / 60)
        if output_func:
            output_func(progress_info)

    end = datetime.datetime.utcnow()
    progress_final_info = "Processing took: {}s".format((end - start).total_seconds())
    if output_func:
        output_func(progress_final_info)


def process_single_field(code, prop_type, solr_field_type):
    sc = solr._get_solr_connection()
    new_solr_fields = [dict(name=code, type=solr_field_type)]
    try:
        sc.add_fields(new_solr_fields, log_level=logging.DEBUG)
        LOG.info("solr added field for property: '{}' with type: '{}' and solr field type: '{}'".format(code, prop_type, solr_field_type))
    except solr.SolrCommandException:
        # field does already exist, update existing ...
        sc.update_fields(new_solr_fields)
        LOG.info("solr updated field for property: '{}' with type: '{}' and solr field type: '{}'".format(code, prop_type, solr_field_type))


@sig.connect(catalog.FloatProperty, "modify", "post")
def process_currency_field(prop, ctx=None):
    if UnitCache.is_currency(prop.unit_object_id):
        sc = solr._get_solr_connection()
        solr_field_name = solr.SOLR_CURRENCY_KEY + prop.code
        solr_field_type = solr.SOLR_FIELD_TYPE_MAPPING.get("text")
        new_solr_fields = [dict(name=solr_field_name, type=solr_field_type)]
        try:
            sc.add_fields(new_solr_fields, log_level=logging.DEBUG)
            LOG.info(
                "solr added field for property: '{}' with type: '{}' and solr field type: '{}'".format(
                    solr_field_name, "float", solr_field_type
                )
            )
        except solr.SolrCommandException:
            # field does already exist ...
            pass


@sig.connect(catalog.Property, "create", "post")
@sig.connect(catalog.Property, "copy", "post")
@sig.connect(classes.ClassProperty, "create", "post")
@sig.connect(classes.ClassProperty, "copy", "post")
def add_field(prop, ctx=None, qcla=None):
    import requests
    from cdb.storage.index.errors import InvalidService
    from cs.classification import ClassificationException
    try:
        prop_type = prop.getType()
        solr_field_type = solr.SOLR_FIELD_TYPE_MAPPING.get(prop_type)
        if not qcla:
            qcla = PropertyValue.ByKeys("qcla", "Common Role", "public")
        if qcla and "0" == qcla.value:
            solr_field_type = solr.SOLR_FIELD_TYPE_MAPPING_IGNORE_CASE.get(prop_type)
        if solr_field_type is not None:
            if not isinstance(prop, catalog.MultilangProperty) and not isinstance(prop, classes.MultilangClassProperty):
                process_single_field(prop.code, prop_type, solr_field_type)
                process_currency_field(prop)
            else:
                for iso_code in get_active_classification_languages():
                    process_single_field("{}_{}".format(prop.code, iso_code), prop_type, solr_field_type)
        elif prop_type not in ['block', 'float_range']:
            raise ValueError('unknown property type {}'.format(prop_type))
    except (requests.exceptions.HTTPError, InvalidService) as ex:
        LOG.exception(ex)
        raise ClassificationException("cs_classification_search_index_field_error", prop.code)
