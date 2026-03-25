# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


import collections
import datetime
import json
import logging
import re

from urllib.request import getproxies

from cdb import i18n, sqlapi, tls, ue
from cdb.objects import ClassRegistry
from cdb.objects import DataDictionary
from cdb.storage.index.errors import InvalidService
from cs.classification import search_parser, tools
from cs.classification import util, units
from cs.classification import ObjectClassificationLog
from cs.classification.catalog import Property
from cs.classification.search_semantics import ClassificationSolrSearchWithoutIdentifiersSemantics
from cs.classification.classes import ClassificationClass
from cs.classification.units import UnitCache

LOG = logging.getLogger(__name__)
iso_date_matcher = re.compile('^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')
solr_connection = None

SOLR_CHUNK_SIZE = 100

class JSONDatetimeEncoder(json.JSONEncoder):

    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def _get_solr_connection():
    from cdb.storage.index import serviceparms
    global solr_connection
    if solr_connection is not None:
        return solr_connection
    else:
        solr_connection = SolrClassificationRestConnection(serviceparms.get(serviceparms.INDEX_SERVICE_ID))
        return solr_connection


def _close_solr_connection():
    if solr_connection:
        solr_connection.session.close()



SOLR_ASSIGNED_CLASSES_KEY = "_assigned_classes_"
SOLR_BLOCK_PATH_KEY = "_block_path"
SOLR_BLOCK_PROP_KEY = "_block_prop"
SOLR_EMPTY_VALUES_KEY = "_empty_values"
SOLR_CURRENCY_KEY = "_____currency_____"
SOLR_FLOAT_RANGE_MIN_KEY = "___float_range_min_value___"
SOLR_FLOAT_RANGE_MAX_KEY = "___float_range_max_value___"

SOLR_FIELD_TYPE_MAPPING = {
    "text": "strings",
    "boolean": "booleans",
    "datetime": "tdates",
    "integer": "tlongs",
    "float": "tdoubles",
    "multilang": "strings",
    "objectref": "strings",
}

SOLR_FIELD_TYPE_MAPPING_IGNORE_CASE = {
    "text": "strings_ignore_case",
    "boolean": "booleans",
    "datetime": "tdates",
    "integer": "tlongs",
    "float": "tdoubles",
    "multilang": "strings_ignore_case",
    "objectref": "strings",
}


class SolrCommandException(ValueError):
    pass


class SolrRESTConnection(object):
    """ generic solr rest connection class """

    # https://cwiki.apache.org/confluence/display/solr/Common+Query+Parameters
    def __init__(self, endpoint, username=None, password=None, measure_solr_times=False):
        import requests
        self.system_fields = [
            '_root_',
            '_version_',
            '_text_',
            'id',
            'type',
            SOLR_ASSIGNED_CLASSES_KEY,
            SOLR_BLOCK_PATH_KEY,
            SOLR_BLOCK_PROP_KEY,
            SOLR_EMPTY_VALUES_KEY
        ]
        self.endpoint = endpoint
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json; charset=utf-8'})
        self.path_sep = "/"
        self.measure_solr_times = measure_solr_times
        if username is not None:
            self.session.auth = requests.auth.HTTPBasicAuth(username, password if password is not None else '')

    def _log_proxy_config(self):
        # find proxy settings and log them.
        proxies = getproxies()
        if proxies:
            LOG.error("Detected proxy configuration: %s" % "\n".join("%s=%s" % kv for kv in proxies.items()))

    def handle_errors(self, request, log_level=logging.ERROR):
        import requests
        try:
            request.raise_for_status()
        except requests.exceptions.HTTPError as err:
            LOG.log(log_level, 'request error: %s', request.status_code)
            log_headers = dict(request.request.headers)
            if 'Authorization' in log_headers:
                del log_headers['Authorization']
            if request.request.method in ['get', 'GET']:
                LOG.log(log_level, 'request details: %s\n%s\n', log_headers, request.request.url)
            else:
                LOG.log(
                    log_level,
                    'request details: %s\n%s\n',
                    log_headers,
                    json.dumps(json.loads(request.request.body.decode('utf-8')), indent=4)
                )
            response_data = {}
            try:
                response_data = request.json()
                LOG.log(
                    log_level,
                    'response details: %s\n%s\n',
                    log_headers,
                    json.dumps(response_data, indent=4)
                )
            except ValueError:
                LOG.log(log_level, 'request details: %s', request.text)
            if 'error' in response_data and 'msg' in response_data.get('error'):
                raise SolrCommandException(response_data.get('error').get('msg'))
            raise err

    def _generate_update_add_block(self, doc):
        return json.dumps({"overwrite": True, "doc": doc}, ensure_ascii=False)

    def _generate_update_remove_nested_block(self, doc):
        id_pattern_str = "id:{id}%s*" % self.path_sep
        return json.dumps({"query": id_pattern_str.format(**doc)}, ensure_ascii=False)

    def execute(self, method, message, *args, **kwargs):
        try:
            kwargs['verify'] = tls.verify_path()
            if self.measure_solr_times:
                before = datetime.datetime.utcnow()
                r = getattr(self.session, method)(*args, **kwargs)
                after = datetime.datetime.utcnow()
                duration = (after - before).total_seconds()
                LOG.debug(message.format(duration))
            else:
                r = getattr(self.session, method)(*args, **kwargs)
            return r
        except Exception as ex:
            LOG.exception(ex)
            self._log_proxy_config()
            raise

    def update(self, data):
        assert isinstance(data, list)
        # Solr does NOT delete old nested documents on update even with overwrite, therefore
        # we have to force that using solr command messages when updating a document.
        # Due to crazy non standard json message format for solr commands for multiple adds/deletes
        # (https://cwiki.apache.org/confluence/display/solr/Uploading+Data+with+Index+Handlers#UploadingDatawithIndexHandlers-SendingJSONUpdateCommands)
        # we have to create it by hand otherwise only one add/delete key in a dictionary would survive.
        solr_commands = []
        for doc in data:
            doc_update = """
            "delete": {delete_block},
            "add": {add_block}""".format(add_block=self._generate_update_add_block(doc),
                                         delete_block=self._generate_update_remove_nested_block(doc))
            # strip { and }
            solr_commands.append(doc_update)
        url = "%s/%s" % (self.endpoint, "update?commit=false")
        return self.send_solr_commands(url, solr_commands, 'update')

    def commit(self):
        url = "%s/%s" % (self.endpoint, "update?commit=true")
        r = self.execute("get", "solr commit duration: {}", url)
        self.handle_errors(r)

    def delete_all(self):
        url = "%s/%s" % (self.endpoint, "update")
        payload = {'delete': {'query': '*:*'},
                   'commit': {}}
        r = self.execute("post", "solr delete_all duration: {}", url, json=payload)
        self.handle_errors(r)

    def _query_rows(self, data, start=None, rows=None):
        if start is None:
            start = 0
        if rows is None:
            rows = SOLR_CHUNK_SIZE
        url = "%s/%s" % (self.endpoint, "select?wt=json&fl=id&start={start}&rows={rows}".format(start=start, rows=rows))
        query_args = dict(query=data)
        r = self.execute("post", "solr query rows duration: {}", url, json=query_args)
        self.handle_errors(r)
        return r.json()

    def execute_query(self, data, rows_per_chunk=SOLR_CHUNK_SIZE):
        assert isinstance(data, str)

        def gen(data, rows_per_chunk):
            initial = True
            rows = rows_per_chunk
            numFound = None
            start = None
            has_more_results = False
            while initial or has_more_results:
                initial = False
                res = self._query_rows(data, start=start, rows=rows)
                rows = None
                numFound = None
                start = None
                rows = int(res.get('responseHeader').get('params').get('rows', rows_per_chunk))
                numFound = int(res.get('response').get('numFound'))
                start = int(res.get('response').get('start'))
                if rows is not None and start is not None and numFound is not None:
                    has_more_results = (numFound - start - rows) > 0
                    start = start + rows
                else:
                    has_more_results = False
                yield res

        return gen(data, rows_per_chunk)

    def get_field(self, fieldname):
        url = "{}/schema/fields/{}?indent=on&wt=json".format(self.endpoint, fieldname)
        r = self.execute("get", "solr fields duration: {}", url)
        self.handle_errors(r)
        result = r.json()
        fields = result.get('fields', [])
        return fields[0] if fields else None

    def get_fields(self, fieldnames=None):
        url = "{}/schema/fields/?indent=on&wt=json".format(self.endpoint)
        data = None if not fieldnames else {
            "fl": ",".join(fieldnames)
        }
        r = self.execute("get", "solr fields duration: {}", url, params=data)  # stream=True
        self.handle_errors(r)
        result = r.json()
        fields = result.get('fields', [])
        return fields

    def send_solr_commands(self, url, solr_commands, log_id=None, log_level=logging.ERROR):
        payload_data = "{"
        payload_data += ",".join(solr_commands)
        payload_data += "}"
        LOG.debug('solr send_solr_commands (%s) : %s', log_id if log_id else '', payload_data)
        r = self.execute("post", "solr %s duration: {}" % log_id if log_id else '', url,
                         data=payload_data.encode('utf-8'))
        self.handle_errors(r, log_level)
        result = r.json()
        if 'errors' in result:
            msgs = []
            for errorMessage in result.get('errors'):
                msgs.append("".join(errorMessage.get('errorMessages', [])))
            raise SolrCommandException("\n".join(msgs))
        return result

    def change_fields(self, fields, operation=None, log_level=logging.ERROR):
        # due to expected deprecation of the direct solr core/schema/fields api
        # we need to use post request directly to solr core/schema using the solr command syntax
        solr_commands = []
        if operation in ['add-field', 'replace-field', 'delete-field']:
            for field in fields:
                if operation == "delete-field":
                    field_data = '{"name": %s}' % field["name"]
                else:
                    field_data = json.dumps(field, ensure_ascii=False)

                cmd = """
                    "{operation}": {field_data}
                """.format(operation=operation, field_data=field_data)
                solr_commands.append(cmd)
            url = "%s/%s" % (self.endpoint, "schema")
            return self.send_solr_commands(url, solr_commands, 'add_fields', log_level)
        else:
            raise ValueError('invalid operation')

    def filter_guarded_fields(self, fields):
        filtered_fields = []
        for field in fields:
            if 'name' in field:
                if field.get('name') not in self.system_fields:
                    filtered_fields.append(field)
                else:
                    raise ValueError("field: '{}' is a system field".format(field.get('name')))
            else:
                raise ValueError("field: '{}' does not have a name, which is mandatory".format(field))
        return filtered_fields

    def add_fields(self, fields, log_level=logging.ERROR):
        return self.change_fields(fields, 'add-field', log_level)

    def delete_fields(self, fields):
        filtered_fields = self.filter_guarded_fields(fields)
        return self.change_fields(filtered_fields, 'delete-field')

    def update_fields(self, fields):
        filtered_fields = self.filter_guarded_fields(fields)
        return self.change_fields(filtered_fields, 'replace-field')


class SolrBaseProcessor(object):

    def __init__(self, obj_values, level=0):
        self.obj_values = obj_values
        self.level = level
        self.type_map = {}  # callback type map to be overridden
        self.path_sep = "/"
        self.multivalue_sep = ":"
        self._solr_dummy_class = "no_class"

    def _generate_block_infos(self, block_path_segments_str):
        """ determines block_path and block_prop from block_path_segments_str
            filters out position information as we want to find all
            multi values for a given path """

        path_segments = block_path_segments_str.split(self.path_sep)

        def filter_pos(name_and_pos):
            segments = name_and_pos.split(self.multivalue_sep)
            return segments[0]

        # the last element is the block property itself
        block_prop = path_segments[-1]
        if block_prop:
            block_prop = filter_pos(block_prop)

        # block path does not contain the leaf property only the parents
        block_path_segments = path_segments[:-1]
        block_path_segments = [filter_pos(segment) for segment in block_path_segments]
        block_path = self.path_sep.join(block_path_segments)
        block_path = "{}{}{}".format(self.path_sep, block_path, self.path_sep) if block_path else ''
        block_infos = {SOLR_BLOCK_PROP_KEY: block_prop}
        if block_path:
            block_infos.update({SOLR_BLOCK_PATH_KEY: block_path})
        return block_infos

    def get_result(self, only_solr_values=False):
        # to be overridden
        pass

    def process(self, with_classes_conditions=True):
        # to be overridden
        pass


class SolrIndexProcessor(SolrBaseProcessor):

    def __init__(self, obj_values, object_id=None, level=0, catalog_prop_codes=None):
        super(SolrIndexProcessor, self).__init__(obj_values=obj_values,
                                                 level=level)
        self.result = collections.defaultdict(list)
        self.key_mapping_result = {}
        self.type_map = {
            "text": self.process_entry,
            "boolean": self.process_entry,
            "datetime": self.process_datetime,
            "integer": self.process_entry,
            "float": self.process_float,
            "float_range": self.process_float_range,
            "multilang": self.process_multilang,
            "objectref": self.process_entry,
            "block": self.process_block,
        }
        self.object_id = object_id
        self.catalog_prop_codes = catalog_prop_codes
        self.empty_catalog_prop_codes = []

    def get_result(self, only_solr_values=False):
        self.process()
        if not only_solr_values:
            return self.result
        else:
            return {k: [x.get('solr_value') for x in v] for (k, v) in self.result.items()}

    def process_entry(self, base_code, entry):
        e = entry.copy()
        e['solr_value'] = entry.get('value')
        self.result[base_code].append(e)
        self.key_mapping_result[base_code] = base_code

    def process_multilang(self, base_code, entry):
        multilang_value = entry.get('value')
        for k, v in multilang_value.items():
            if v is None:
                continue
            code = base_code + '_' + k
            e = entry.copy()
            e['solr_value'] = v["text_value"]
            self.result[code].append(e)
            self.key_mapping_result[code] = base_code

    def process_datetime(self, base_code, entry):
        val = entry.get('value')
        e = entry.copy()
        if isinstance(val, datetime.datetime):
            date_value = val.replace(tzinfo=None)
            date_value = date_value.replace(microsecond=0)
            e['solr_value'] = date_value.isoformat() + 'Z' if val is not None else None
        elif isinstance(val, datetime.date):
            e['solr_value'] = datetime.datetime(val.year, val.month, val.day).isoformat() + 'Z' if val is not None else None
        else:
            e['solr_value'] = val if val is not None else None
        self.result[base_code].append(e)
        self.key_mapping_result[base_code] = base_code

    def process_float(self, base_code, entry):
        val = entry.get('value')
        e = entry.copy()
        if val and UnitCache.is_currency(val.get('unit_object_id')):
            e['solr_value'] = val.get('float_value')
            solr_field_name = SOLR_CURRENCY_KEY + base_code
            unit_entry = {
                'solr_value': val.get('unit_object_id')
            }
            self.result[solr_field_name].append(unit_entry)
            self.key_mapping_result[solr_field_name] = solr_field_name
        elif val is not None and val.get('float_value_normalized') is not None:
            e['solr_value'] = val.get('float_value_normalized')
        elif val is not None and val.get('float_value') is not None:
            e['solr_value'] = val.get('float_value')
        else:
            e['solr_value'] = None
        self.result[base_code].append(e)
        self.key_mapping_result[base_code] = base_code

    def process_float_range(self, base_code, entry):
        value_path = entry.get("value_path", base_code)
        new_entry = {
            "property_type": "block",
            "id": entry["id"],
            "value_path": value_path,
            "value": {"child_props": {
                SOLR_FLOAT_RANGE_MIN_KEY: [{
                    "value_path": self.path_sep.join(
                        [value_path, SOLR_FLOAT_RANGE_MIN_KEY]
                    ),
                    "property_type": "float",
                    "id": None,
                    "value": entry["value"]["min"]
                }],
                SOLR_FLOAT_RANGE_MAX_KEY: [{
                    "value_path": self.path_sep.join(
                        [value_path, SOLR_FLOAT_RANGE_MAX_KEY]
                    ),
                    "property_type": "float",
                    "id": None,
                    "value": entry["value"]["max"]
                }]
            }}
        }
        return self.process_block(base_code, new_entry)

    def process_block(self, base_code, entry):
        val = entry.get('value')
        e = entry.copy()
        # in the first level we need the object_id added in front
        # for the indexing case
        # for the other levels the id in data already contain the
        # needed parent information
        parent_path = ''
        if self.object_id is not None:
            parent_path = self.object_id
        value_processor = SolrIndexProcessor(obj_values=val.get('child_props'),
                                             object_id=self.object_id,
                                             level=self.level + 1)
        value_repr = value_processor.get_result(only_solr_values=True)
        block_id = entry.get('value_path').replace(self.multivalue_sep, self.path_sep)
        block_base_repr = {
            'id': '{parent_path}{path_sep}{block_id}'.format(parent_path=parent_path,
                                                             path_sep=self.path_sep,
                                                             block_id=block_id)
        }
        block_base_repr.update(self._generate_block_infos(entry.get('value_path')))
        block_base_repr.update(value_repr)
        e['solr_value'] = block_base_repr
        # in solr all blocks per level are stored within the _childDocuments_ key
        self.result['_childDocuments_'].append(e)
        self.key_mapping_result[base_code] = base_code

    def process(self, with_classes_conditions=True):
        empty_catalog_prop_codes = []
        for k, v in self.obj_values.items():
            for entry in v:
                # ignore empty fields as solr does not index empty fields
                if entry.get('value') == "" or entry.get('value') is None:
                    if self.catalog_prop_codes and k in self.catalog_prop_codes:
                        empty_catalog_prop_codes.append(k)
                    continue
                self.type_map[entry.get('property_type')](k, entry)
        self.empty_catalog_prop_codes = empty_catalog_prop_codes


class SolrQueryProcessor(SolrBaseProcessor):

    def __init__(
        self, obj_values, class_codes, level=0, block_prop='', block_path='', catalog_property_mapping=None,
        base_units=None
    ):
        super(SolrQueryProcessor, self).__init__(obj_values=obj_values,
                                                 level=level)
        self.query_conditions = []
        self.class_codes = class_codes
        self.catalog_property_mapping = catalog_property_mapping if catalog_property_mapping else {}
        self.block_prop = block_prop
        self.block_path = block_path
        self.base_units = base_units
        self.type_map = {
            "text": self.convert_text,
            "boolean": self.convert_value,
            "datetime": self.convert_date,
            "integer": self.convert_int,
            "float": self.convert_float,
            "float_range": self.convert_float_range,
            "multilang": self.convert_multilang,
            "objectref": self.convert_text
        }

    def _initialize_float_base_unit_cache(self):

        def _find_floats(props, is_inside_block=False):
            result = set()
            for prop_code, prop_values in props.items():
                for prop_value in prop_values:
                    if prop_value['value'] is not None:
                        prop_type = prop_value["property_type"]
                        if prop_type == "block":
                            result.update(_find_floats(prop_value["value"]["child_props"],
                                                       is_inside_block=True))
                        elif prop_type == "float":
                            float_value = prop_value["value"]["float_value"]
                            if float_value is not None and "" != float_value:
                                result.add((prop_code, is_inside_block))
                        elif prop_type == "float_range":
                            float_value = prop_value["value"]["min"]["float_value"]
                            if float_value is not None and "" != float_value:
                                result.add((prop_code, is_inside_block))
                                continue
                            float_value = prop_value["value"]["max"]["float_value"]
                            if float_value is not None and "" != float_value:
                                result.add((prop_code, is_inside_block))
            return result
        if self.base_units:
            return
        self.float_props = _find_floats(self.obj_values)
        self.base_units = util.load_base_units(self.float_props)

    def add_class_conditions(self):
        if self.class_codes:
            for class_code in self.class_codes:
                conditions = []
                for class_id in ClassificationClass.get_sub_class_ids(
                    class_codes=[class_code], include_given=True
                ):
                    conditions.append("{}:\"{}\"".format(
                        SOLR_ASSIGNED_CLASSES_KEY, class_id
                    ))
                self.query_conditions.append("({})".format(" OR ".join(conditions)))

    def get_result(self, only_solr_values=False):
        self._initialize_float_base_unit_cache()
        self.process()
        querystring = " AND ".join(self.query_conditions)
        LOG.debug('\tQUERYSTRING ({}): \n\t\'{}\'\n'.format(self.level, querystring))
        return querystring

    def semanticConversion(
        self,
        code,
        value,
        break_on_error=False,
        normalize_float_func=None,
        is_text_property=False,
        is_within_block=False,
        enum_values=None,
        unit_object_id=None,
        empty_wildcard_char=None
    ):
        """ returns None on error, a solr syntax string otherwise """
        semantic = ClassificationSolrSearchWithoutIdentifiersSemantics(
            code,
            normalize_float_func=normalize_float_func,
            is_text_property=is_text_property,
            is_within_block=is_within_block,
            is_catalog_property=code in self.catalog_property_mapping,
            enum_values=enum_values,
            unit_object_id=unit_object_id,
            empty_wildcard_char=empty_wildcard_char
        )
        import tatsu
        try:
            ast = search_parser.parse_without_identifiers_needed(value, semantic)
            parsed_value = semantic.get_result(ast)
            if parsed_value is not None:
                return parsed_value
            else:
                return None
        except tatsu.exceptions.ParseError as e:
            if break_on_error:
                raise tatsu.exceptions.ParseError(re.compile(r'.*\^', re.DOTALL).match(str(e)).group())
            else:
                search_value = '="{}"'.format(value) if is_text_property else "={}".format(value)
                return self.semanticConversion(
                    code,
                    search_value,
                    break_on_error=True,
                    normalize_float_func=normalize_float_func,
                    is_text_property=is_text_property,
                    is_within_block=is_within_block,
                    enum_values=enum_values,
                    unit_object_id=unit_object_id,
                    empty_wildcard_char=empty_wildcard_char
                )

    def create_query_condition(self, values):
        value = " AND ".join(values)
        if not self.block_prop:  # simple value
            query = '{value}'.format(
                value=value,
                assigned_classes_key=SOLR_ASSIGNED_CLASSES_KEY
            )
        else:
            if self.block_path:
                block_path = "\\\"{}\\\"".format(self.block_path) if self.block_path[0] == "/" else self.block_path
                block_path_condition = "{block_path_key}:{block_path_val}".format(
                    block_path_key=SOLR_BLOCK_PATH_KEY,
                    block_path_val=block_path
                )
            else:
                block_path_condition = "-{block_path_key}:[* TO *]".format(block_path_key=SOLR_BLOCK_PATH_KEY)
            query = '_query_:"{{!parent which={assigned_classes_key}:*}} ({value} AND {block_prop_key}:{block_prop_val} AND {block_path_condition})"'.format(
                assigned_classes_key=SOLR_ASSIGNED_CLASSES_KEY,
                value=value,
                block_prop_key=SOLR_BLOCK_PROP_KEY,
                block_prop_val=self.block_prop,
                block_path_condition=block_path_condition
            )
        self.query_conditions.append("({})".format(query))

    def convert_value(self, base_code, entry, enum_values):
        value = entry.get('value').strip() if isinstance(entry.get('value'), str) else entry.get('value')
        LOG.debug('convert_value ({}): {} -> {}'.format(self.level, base_code, value))
        return self.semanticConversion(base_code, value, is_within_block=self.level > 0)

    def convert_date(self, base_code, entry, enum_values):
        value = entry.get('value').strip() if isinstance(entry.get('value'), str) else entry.get('value')
        LOG.debug('convert_date ({}): {} -> {}'.format(self.level, base_code, value))
        return self.semanticConversion(
            base_code, value, is_within_block=self.level > 0, empty_wildcard_char='[* TO *]'
        )

    def convert_text(self, base_code, entry, enum_values):
        value = entry.get('value').strip()
        LOG.debug('convert_text ({}): {} -> {}'.format(self.level, base_code, value))
        return self.semanticConversion(
            base_code, value, is_text_property=True, is_within_block=self.level > 0, enum_values=enum_values
        )

    def convert_multilang(self, base_code, entry, enum_values):
        converted_values = []
        for k, v in entry.get('value').items():
            if v is None or not v["text_value"]:
                continue
            multilang_code = base_code + "_" + k
            multilang_value = v["text_value"].strip()
            LOG.debug('convert_multilang ({}): {} -> {}'.format(self.level, multilang_code, multilang_value))
            converted_values.append(
                self.semanticConversion(
                    multilang_code, multilang_value, is_text_property=True, is_within_block=self.level > 0
                )
            )
        return " AND ".join(converted_values)

    def convert_int(self, base_code, entry, enum_values):
        self._raise_if_wildcard(entry.get('value'))
        return self.convert_value(base_code, entry, enum_values)

    def convert_float(self, base_code, entry, enum_values):
        LOG.debug('process_float ({}): {} -> {}'.format(self.level, base_code, entry.get('value')))
        val = entry.get('value')
        unit_object_id = val.get('unit_object_id')
        if not val.get('float_value'):
            return None
        self._raise_if_wildcard(val.get('float_value'))
        value = val.get('float_value').strip() \
            if isinstance(val.get('float_value'), str) else val.get('float_value')
        if isinstance(value, float):  # python float as unicode has .  as decimal sep
            value = str(value).replace('.', i18n.get_decimal_separator())

        prop_code = entry.get("property_code", base_code)
        base_unit_id = self.base_units.get(prop_code, {}).get("unit_object_id")

        def normalize_float_func(val_to_convert, repair_dict):
            if unit_object_id and base_unit_id and not UnitCache.is_currency(unit_object_id):
                converted_float = units.normalize_value(val_to_convert, unit_object_id, base_unit_id, base_code)
                LOG.debug('converted float {} to {}'.format(val_to_convert, converted_float))
            else:
                converted_float = val_to_convert
            ret = "[{} TO {}]".format(
                converted_float - util.get_epsilon(converted_float),
                converted_float + util.get_epsilon(converted_float)
            )
            repair_dict[ret] = converted_float
            return ret

        return self.semanticConversion(
            base_code, value,
            normalize_float_func=normalize_float_func, empty_wildcard_char='[* TO *]',
            is_within_block=self.level > 0, unit_object_id=unit_object_id
        )

    @staticmethod
    def __check_float_range_value(value):
        return value is not None and "" != value and (
            not isinstance(value, str)
            or all([op not in value for op in (">", "<", "=", "*", "%")])
        )

    def convert_float_range(self, property_code, property_value, enum_values):
        LOG.debug("convert_float_range ({}): {} -> {}".format(
            self.level, property_code, property_value.get('value')
        ))
        min_value = property_value["value"]["min"]
        no_min_value = min_value["float_value"] is None or "" == min_value["float_value"]

        max_value = property_value["value"]["max"]
        no_max_value = max_value["float_value"] is None or "" == max_value["float_value"]

        if no_min_value and no_max_value:
            return None
        elif no_min_value:
            min_value["float_value"] = max_value["float_value"] if self.__check_float_range_value(max_value["float_value"]) else "*"
        elif no_max_value:
            max_value["float_value"] = min_value["float_value"] if self.__check_float_range_value(min_value["float_value"]) else "*"

        min_float = min_value["float_value"]
        min_unit_id = min_value.get("unit_object_id")
        max_float = max_value["float_value"]
        max_unit_id = max_value.get("unit_object_id")

        if self.__check_float_range_value(min_float) and self.__check_float_range_value(max_float):
            min_value["float_value"] = "<={}".format(max_float)
            min_value["float_value_normalized"] = None
            min_value["unit_object_id"] = max_unit_id
            max_value["float_value"] = ">={}".format(min_float)
            max_value["float_value_normalized"] = None
            max_value["unit_object_id"] = min_unit_id

        new_property_value = {
            "property_type": "block",
            "id": property_value["id"],
            "value": {"child_props": {
                SOLR_FLOAT_RANGE_MIN_KEY: [{
                    "property_code": property_code,  # add original prop_code for float normalization
                    "property_type": "float",
                    "id": None,
                    "value": min_value
                }],
                SOLR_FLOAT_RANGE_MAX_KEY: [{
                    "property_code": property_code,  # add original prop_code for float normalization
                    "property_type": "float",
                    "id": None,
                    "value": max_value
                }]
            }}
        }
        subqueries = []
        self.process_block(property_code, new_property_value, subqueries)
        if subqueries:
            subqueries = " OR ".join(subqueries)
            self.query_conditions.append("({})".format(subqueries))
        return None

    def process_block(self, block_prop_code, property_value, subqueries):
        if self.block_prop and self.block_path:
            block_path = "{}{}{}".format(self.block_path, self.block_prop, self.path_sep)
        elif self.block_prop:
            block_path = '{}{}{}'.format(self.path_sep, self.block_prop, self.path_sep)
        else:
            block_path = ''
        block_subquery_processor = SolrQueryProcessor(
            obj_values=property_value['value'].get('child_props'),
            class_codes=self.class_codes,
            level=self.level + 1,
            block_prop=block_prop_code,
            block_path=block_path,
            base_units=self.base_units
        )
        subquery_str = block_subquery_processor.get_result()
        if subquery_str:
            subqueries.append("({})".format(subquery_str))

    def process_class_properties(self, property_code, property_value, enum_values):
        converted_class_property_values = []

        class_property_mappings = self.catalog_property_mapping.get(property_code, {})
        for class_property_code, class_oids in class_property_mappings.items():
            converted_value = self.type_map[property_value.get('property_type')](
                class_property_code, property_value, enum_values
            )
            if converted_value:
                class_conditions = []
                for class_oid in class_oids:
                    class_conditions.append("{assigned_classes_key}:{class_oid}".format(
                        assigned_classes_key=SOLR_ASSIGNED_CLASSES_KEY,
                        class_oid=class_oid
                    ))
                converted_class_property_values.append(
                    "(({value_condition}) AND ({class_condition}))".format(
                        value_condition=converted_value,
                        class_condition=" OR ".join(class_conditions)
                    )
                )
        return converted_class_property_values

    def process(self, with_classes_conditions=True):
        if with_classes_conditions and self.level == 0:
            # class conditions are global therefore should not be added at each level
            self.add_class_conditions()
        converted_values = []
        enum_values = util.get_enum_values_with_labels(util.get_text_prop_codes(self.obj_values))

        for property_code, property_values in self.obj_values.items():
            for property_value in property_values:
                # empty conditions are not part of the search - to search empty values use =""
                if property_value.get('value') == "" or property_value.get('value') is None:
                    continue
                if 'block' == property_value.get('property_type'):
                    subqueries = []
                    self.process_block(property_code, property_value, subqueries)

                    class_property_mappings = self.catalog_property_mapping.get(property_code, None)
                    if class_property_mappings:
                        for class_property_code in class_property_mappings:
                            self.process_block(
                                class_property_code, property_value, subqueries
                            )
                    if subqueries:
                        subqueries = " OR ".join(subqueries)
                        self.query_conditions.append("({})".format(subqueries))
                else:
                    converted_value = self.type_map[property_value.get('property_type')](
                        property_code, property_value, enum_values
                    )
                    if converted_value or converted_value is False:
                        converted_property_values = []
                        if 0 == self.level:
                            converted_property_values.append(
                                "(({value}) AND {assigned_classes_key}:*)".format(
                                    value=converted_value,
                                    assigned_classes_key=SOLR_ASSIGNED_CLASSES_KEY
                                )
                            )
                            converted_property_values.extend(
                                self.process_class_properties(property_code, property_value, enum_values)
                            )
                        else:
                            converted_property_values.append("{value}".format(
                                value=converted_value,
                                assigned_classes_key=SOLR_ASSIGNED_CLASSES_KEY
                            ))

                        if converted_property_values:
                            converted_values.append("({})".format(" OR ".join(converted_property_values)))
        if converted_values:
            self.create_query_condition(converted_values)

    def _raise_if_wildcard(self, value):
        wildcards = ["*", "%", "?"]
        # Check the value for wildcards, but allow them if they are the only sign
        if isinstance(value, str) and any([w != value and w in value for w in wildcards]):
            ue_ex = ue.Exception("cs_classification_no_wildcard_support_for_numbers")
            LOG.exception(ue_ex)
            raise SolrCommandException(str(ue_ex))


class SolrClassificationRestConnection(SolrRESTConnection):
    """ solr rest connection class for classification data """

    def __init__(self, service_parameters, *args, **kwargs):
        self._solr_dummy_class = "no_class"
        self.service_parameters = service_parameters
        self.url = str(self.service_parameters.url) + '/solr/classification'
        super(SolrClassificationRestConnection, self).__init__(endpoint=self.url,
                                                               username=self.service_parameters.username,
                                                               password=self.service_parameters.password,
                                                               *args, **kwargs)

    def index_object_ids(self, object_ids, cdb_mdate=None):
        """ data should be a list of cdb_object_ids """

        def index_object_ids_chunk(object_ids_chunk, catalog_prop_codes):
            rset = sqlapi.RecordSet2(sql="select id, relation from cdb_object where %s" %
                                         cdbobject_cls.id.one_of(*object_ids_chunk))
            obj_data = []
            dd_classnames = {}
            for r in rset:
                dd_classname = dd_classnames.get(r.relation, None)
                if not dd_classname:
                    sw_rec = DataDictionary().getRootClassRecord(r.relation)
                    if sw_rec:
                        dd_classname = sw_rec.classname
                        dd_classnames[r.relation] = dd_classname
                if dd_classname:
                    obj_data.append((r.id, dd_classname))
            update_data = self.convert_update_data(obj_data, catalog_prop_codes)
            # LOG.debug('data to index: {}'.format(json.dumps(update_data, indent=4, cls=JSONDatetimeEncoder)))
            super(SolrClassificationRestConnection, self).update(update_data)
            # update cdb_index_time
            ObjectClassificationLog.update_logs(
                object_ids_chunk, cdb_index_date=datetime.datetime.utcnow(), cdb_mdate=cdb_mdate
            )

        if not object_ids:
            return
        cdbobject_cls = ClassRegistry().find("cdb_object", generate=True)
        catalog_prop_codes = Property.get_catalog_codes()
        for object_ids_chunk in tools.chunk(object_ids, SOLR_CHUNK_SIZE):
            index_object_ids_chunk(object_ids_chunk, catalog_prop_codes)

    def index_objects(self, objs, cdb_mdate=None):
        """ data should be a list of objects to be indexed """

        def index_object_chunk(chunk_objects, catalog_prop_codes):
            obj_data = []
            ref_object_ids = []
            for obj in chunk_objects:
                obj_data.append((obj.cdb_object_id, obj.GetClassname()))
                ref_object_ids.append(obj.cdb_object_id)
            update_data = self.convert_update_data(obj_data, catalog_prop_codes)
            # LOG.debug('data to index: {}'.format(json.dumps(update_data, indent=4, cls=JSONDatetimeEncoder)))
            super(SolrClassificationRestConnection, self).update(update_data)
            ObjectClassificationLog.update_logs(
                ref_object_ids, cdb_index_date=datetime.datetime.utcnow(), cdb_mdate=cdb_mdate
            )

        catalog_prop_codes = Property.get_catalog_codes()
        for chunk_objs in tools.chunk(objs, SOLR_CHUNK_SIZE):
            index_object_chunk(chunk_objs, catalog_prop_codes)

    def update_index(self, obj, classification, class_oids, catalog_prop_codes):
        sf = SolrIndexProcessor(
            obj_values=classification, object_id=obj.cdb_object_id, catalog_prop_codes=catalog_prop_codes
        )
        obj_classification = sf.get_result(only_solr_values=True)
        obj_classification['id'] = obj.cdb_object_id
        obj_classification['type'] = obj.GetClassname()
        if 0 == len(class_oids):
            class_oids.append(self._solr_dummy_class)
        obj_classification[SOLR_ASSIGNED_CLASSES_KEY] = class_oids
        if sf.empty_catalog_prop_codes:
            obj_classification[SOLR_EMPTY_VALUES_KEY] = sf.empty_catalog_prop_codes
        super(SolrClassificationRestConnection, self).update([obj_classification])

    def remove_from_index(self, cdb_object_id):
        # FIXME: empty document with the given id remains in index
        obj_classification = {'id': cdb_object_id}
        super(SolrClassificationRestConnection, self).update([obj_classification])

    def query(self, data, class_codes, catalog_property_codes, rows_per_chunk=SOLR_CHUNK_SIZE):
        catalog_prop_mapping = self.get_class_properties(catalog_property_codes)
        query_processor = SolrQueryProcessor(
            obj_values=data, class_codes=class_codes, catalog_property_mapping=catalog_prop_mapping
        )
        query_str = query_processor.get_result()
        LOG.debug('solr query: {}'.format(query_str))
        return super(SolrClassificationRestConnection, self).execute_query(
            query_str, rows_per_chunk=rows_per_chunk
        )

    def convert_update_data(self, obj_datas, catalog_prop_codes):
        from cs.classification.classification_data import ClassificationData
        assert isinstance(obj_datas, list)
        update_data = []
        for obj_data in obj_datas:
            try:
                classification = ClassificationData(obj_data[0], check_rights=False)
                obj_classification = classification.get_classification_data(
                    with_object_descriptions=False, calc_checksums=False
                )
                obj_classes = classification.get_assigned_classes(as_object_ids=True)
                sf = SolrIndexProcessor(obj_values=obj_classification,
                                        object_id=obj_data[0],
                                        catalog_prop_codes=catalog_prop_codes)
                obj_classification = sf.get_result(only_solr_values=True)
                obj_classification['id'] = obj_data[0]
                obj_classification['type'] = obj_data[1]
                if sf.empty_catalog_prop_codes:
                    obj_classification[SOLR_EMPTY_VALUES_KEY] = sf.empty_catalog_prop_codes
                if 0 == len(obj_classes):
                    obj_classes.append(self._solr_dummy_class)
                obj_classification[SOLR_ASSIGNED_CLASSES_KEY] = obj_classes
                update_data.append(obj_classification)
            except Exception as ex: # pylint: disable=W0703
                LOG.error("Error processing {}: {}".format(obj_data[1], obj_data[0]))
                LOG.exception(ex)
        return update_data

    def get_class_properties(self, catalog_prop_codes):
        catalog_props_to_class_props = {}

        # add all given catalog prop codes to dict instead of using a defaultdict
        # because catalog properties may exist that have not been imported in an class
        for catalog_prop_code in catalog_prop_codes:
            catalog_props_to_class_props[catalog_prop_code] = collections.defaultdict(set)

        if not catalog_prop_codes:
            return catalog_props_to_class_props

        catalog_prop_codes_string = ",".join(
            [sqlapi.make_literals(class_name) for class_name in catalog_prop_codes]
        )
        rset = sqlapi.RecordSet2(
            sql="""
                SELECT code, catalog_property_code, classification_class_id FROM cs_class_property
                WHERE {}
            """.format(
                tools.format_in_condition("catalog_property_code", catalog_prop_codes)
            )
        )
        for class_prop in rset:
            catalog_prop_code = class_prop["catalog_property_code"]
            class_prop_code = class_prop["code"]
            class_oid = class_prop["classification_class_id"]
            for class_id in ClassificationClass.get_sub_class_ids(class_ids=[class_oid], include_given=True):
                catalog_props_to_class_props[catalog_prop_code][class_prop_code].add(class_id)

        return catalog_props_to_class_props


def index_object(obj):
    import requests
    try:
        solr_connection = _get_solr_connection()
        solr_connection.index_objects([obj])
        solr_connection.commit()
    except (requests.ConnectionError, InvalidService) as e:
        LOG.exception(e)


def index_objects(objs, cdb_mdate=None):
    import requests
    try:
        solr_connection = _get_solr_connection()
        try:
            solr_connection.index_objects(objs, cdb_mdate)
        except Exception as ex:
            LOG.exception(ex)
        # commit to ensure that successful chunks are completely processed
        solr_connection.commit()
    except (requests.ConnectionError, InvalidService) as e:
        LOG.exception(e)


def index_object_ids(obj_ids, cdb_mdate=None):
    import requests
    try:
        solr_connection = _get_solr_connection()
        try:
            solr_connection.index_object_ids(obj_ids, cdb_mdate)
        except Exception as ex:
            LOG.exception(ex)
        # commit to ensure that successful chunks are completely processed
        solr_connection.commit()
    except (requests.ConnectionError, InvalidService) as e:
        LOG.exception(e)


def delete_index():
    import requests
    try:
        solr_connection = _get_solr_connection()
        solr_connection.delete_all()
        solr_connection.commit()
    except (requests.ConnectionError, InvalidService) as e:
        LOG.exception(e)


def update_index(obj, classification, class_oids, catalog_prop_codes, update_log=True):
    import requests
    try:
        solr_connection = _get_solr_connection()
        solr_connection.update_index(obj, classification, class_oids, catalog_prop_codes)
        solr_connection.commit()
        if update_log:
            ObjectClassificationLog.update_log(
                ref_object_id=obj.cdb_object_id,
                cdb_index_date=datetime.datetime.utcnow()
            )
    except (requests.ConnectionError, InvalidService) as e:
        LOG.exception(e)
        raise


def remove_from_index(cdb_object_id):
    import requests
    try:
        solr_connection = _get_solr_connection()
        solr_connection.remove_from_index(cdb_object_id)
        solr_connection.commit()
    except (requests.ConnectionError, InvalidService) as e:
        LOG.exception(e)


def search_solr(values=None, class_codes=None, catalog_property_codes=None, rows_per_chunk=500):
    solr_connection = _get_solr_connection()

    def gen_res(qry_vals, rows_per_chunk):
        for res in solr_connection.query(
            qry_vals, class_codes, catalog_property_codes, rows_per_chunk=rows_per_chunk
        ):
            for doc in res.get('response').get('docs'):
                yield doc.get('id')

    return gen_res(values, rows_per_chunk)
