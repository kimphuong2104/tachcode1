# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import datetime
import json
import logging
import re

from collections import defaultdict

import cdbwrapc
from cdb import i18n
from cdb import misc
from cdb import sqlapi
from cdb import util as cdb_util
from cdb.objects import ClassRegistry
from cdb.objects import DataDictionary
from cdb.objects import ByID

from cs.platform.web.uisupport import get_ui_link

LOG = logging.getLogger(__name__)


# A regular expression to parse clss_descr_tag strings.
RE_DESCRTAG_TOKENS = re.compile("(?P<format>\([^\)]+\)?\s*\))|"
                                "(?P<identifier>[a-zA-Z0-9_]+)|"  # $ is used as marker for unit
                                "(?P<whitespace>[ \\t]+)|"
                                "(?P<literal>\"[^\"]*\")|"
                                "(?P<operator>[+])")


def parse_tag(data):

    """Parses a message tag as used by icons and item
    name definitions. The syntax looks like:

    tag: <expr> '+' <expr>
    expr: <fieldname> | '"' <literal> '"'

    This functions returns a list of tokens, where each token is a
    pair of token name and token value. Token names are 'identifier',
    'whitespace', 'literal', 'operator'.
    """

    end = 0
    result = []
    while 1:
        mo = RE_DESCRTAG_TOKENS.match(data[end:])
        if not mo:
            break
        for k, v in mo.groupdict().items():
            if v:
                result.append((k, v))
        if mo.end() == 0:
            raise Exception("Parse error")
        end += mo.end()
    return result


def parse_formats(pattern):
    result = {}
    last_identifier = ""
    for k, v in parse_tag(pattern):
        if v:
            if k == 'identifier':
                last_identifier = v
            elif k == 'format' and last_identifier:
                value_format = v[1:-1].strip()
                if ";" in value_format:
                    number_formats = value_format.split(";")
                    number_format = number_formats[0]
                    with_unit = "$(unit)" in number_formats[1]
                else:
                    with_unit = "$(unit)" in value_format
                    number_format = value_format if not with_unit else ""
                result[last_identifier] = {
                    'format_string': number_format,
                    'with_unit': with_unit
                }
    return result


def parse_raw(pattern):
    result = ""
    for k, v in parse_tag(pattern):
        if v:
            if k == 'identifier':
                result += "%%(%s)s" % v
            elif k == 'literal':
                # Duplicate % (E017625)
                result += v[1:-1].replace("%", "%%")
    return result


def get_label(multilang_base_name, rec, languages=None):
    langs = languages if languages else get_languages()
    for lang in langs:
        attr_name = multilang_base_name + '_' + lang
        if attr_name in rec:
            label = rec[attr_name]
            if label:
                return label
    return ""


def get_message_for_all_languages(attr_name, message, args=None):
    message_dict = {}
    for lang_key in message.Text.keys():
        message_text = message.Text[lang_key] if message.Text[lang_key] else ""
        if message_text and args:
            message_dict[attr_name + "_" + lang_key] = message_text % args
        else:
            message_dict[attr_name + "_" + lang_key] = message_text
    return message_dict


class _ValueAccessor(object):

    def __init__(self, accessor):
        self.accessor = accessor

    def __getitem__(self, name):
        try:
            v = self.accessor.__getitem__(name)
        except (KeyError, AttributeError):
            v = u"<attribute %s not found>" % name
        if v is None:
            v = u""
        return v


def fill_pattern(rec, pattern):
    return parse_raw(pattern) % _ValueAccessor(rec)


def get_active_classification_languages():
    """ returns the active classification language codes
    used for data language (not user interface) of multi language properties.

    The language list 'Application Data Languages' is used by default.
    """
    r = sqlapi.RecordSet2("cdb_isolang_list",
                          "cdb_object_id='1eca06cf-3033-11e5-89a4-f0def133d0a6'",
                          ['iso_languages'])
    active_languages_str = "de,en"
    if r and r[0]:
        active_languages_str = r[0].get('iso_languages', active_languages_str)
    else:
        LOG.warning("Missing default language list, using {als} as fallback".format(active_languages_str))
    return active_languages_str.split(',')


_classification_languages = None


def get_languages():
    global _classification_languages
    if _classification_languages is None:
        _classification_languages = [i18n.default()] + i18n.FallbackLanguages()
    return _classification_languages


def get_obj_link(request, obj):
    ui_link = get_ui_link(request, obj)
    if ui_link and re.match(r"^cdbcmsg:/[^/]", ui_link):
        ui_link = ui_link.replace("cdbcmsg:/", "cdbcmsg://", 1)
    return ui_link


def get_addtl_objref_value(objref_value, request):
    ui_link = ""
    ui_text = ""
    if objref_value:
        obj = ByID(objref_value)
        if obj:
            ui_text = obj.GetDescription()
            ui_link = get_obj_link(request, obj)
        else:
            ui_text = "** Object not found: %s **" % objref_value
    return {
        "ui_link": ui_link,
        "ui_text": ui_text
    }


def join_error_messages(error_messages):
    import cdbwrapc
    if error_messages:
        error_message = "\n".join(error_messages)
        if not error_message:
            error_message = cdbwrapc.get_label("web.cs-classification-component.error_constraints_fallback")
        return error_message
    else:
        return ""


def load_objects(object_ids):
    CDBObject = ClassRegistry().find('cdb_object', generate=True)
    cdb_object_objs = CDBObject.Query(CDBObject.id.one_of(*object_ids))

    # sort them by relation
    oids_by_rel = defaultdict(list)
    for o in cdb_object_objs:
        oids_by_rel[o.relation].append(o.id)

    # load by relation
    result = {}
    for relation, oids in oids_by_rel.items():
        pycls = ClassRegistry().find(relation)
        if pycls:
            objects = pycls.Query(pycls.cdb_object_id.one_of(*oids))
            for obj in objects:
                result[obj.cdb_object_id] = obj
        else:
            misc.cdblogv(misc.kLogErr, 0, "Cannot load python object(s) for relation '%s'. "
                                          "No python class could be found." % relation)
    return result


def get_dd_classnames(object_ids):
    dd_classnames = []
    if not object_ids:
        return dd_classnames

    cdbobject_cls = ClassRegistry().find("cdb_object", generate=True)
    rset = sqlapi.RecordSet2(sql="select distinct relation from cdb_object where %s" %
                                 cdbobject_cls.id.one_of(*object_ids))
    for r in rset:
        sw_rec = DataDictionary().getRootClassRecord(r.relation)
        if sw_rec:
            dd_classnames.append(sw_rec.classname)
    return dd_classnames


def replace_all_identifier(identifier_mapping, expression):
    replaced_expression = expression
    if expression:
        for old_identifier, new_identifier in identifier_mapping.items():
            replaced_expression = replace_identifier(old_identifier, new_identifier, replaced_expression)
    return replaced_expression


def replace_identifier(old_identifier, new_identifier, expression):
    pattern = r'(?P<identifier>{})|(?P<literal>\"[^\"]*\")|(?P<literal_2>\'[^\']*\')'.format(old_identifier)
    replaced_expression = ""
    if expression:
        for expression_part in re.split(pattern, expression):
            if expression_part == old_identifier:
                replaced_expression = replaced_expression + new_identifier
            elif expression_part:
                replaced_expression = replaced_expression + expression_part
    return replaced_expression

CHUNK_SIZE_IN_STATEMENTS = 10000
DELETE_ROW_MAX = 10000
INSERT_ROW_MAX = 1000
NUM_IN_CONDITION_MAX_VALUES = 1000
SELECT_ROW_MAX = 10000


def chunk(list, number_of_elements):
    for i in range(0, len(list), number_of_elements):
        yield list[i:i + number_of_elements]


def exists_query(sql_stmt):
    from_str = "FROM dual" if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE else ""
    exists_qry = "SELECT 1 AS cnt {from_str} WHERE EXISTS ({sql_stmt})".format(from_str=from_str,
                                                                               sql_stmt=sql_stmt)
    exists = len(sqlapi.RecordSet2(sql=exists_qry)) > 0
    return exists


def copy_rows(table_name, where_condition, value_callback, insert_chunk_size=INSERT_ROW_MAX):
    """
     :param table_name:
        Name of the table to copy the rows.
    :param where_condition:
        Where condition to identify the rows to be copied
    :param value_callback:
        Function to change values for the copied row, e.g. make the pri key for the copy unique or change
        creation or modification dates

    """
    columns = [col.name() for col in cdb_util.tables[table_name]]
    table_info = cdb_util.TableInfo(table_name)

    column_types = {}
    for column in columns:
        column_types[column] = table_info.column(column).type()

    rows = []
    for row in sqlapi.RecordSet2(table_name, where_condition):
        copy_values = []
        for column_name in columns:
            copy_value = value_callback(column_name, row)
            # make_literals is  not used by intention here because it is faster to determine the column type
            # via table info instead of using isinstance
            if copy_value is None:
                copy_value = "NULL"
            elif sqlapi.SQL_CHAR == column_types[column_name]:
                copy_value = "'{}'".format(copy_value.replace("'", "''"))
            elif sqlapi.SQL_DATE == column_types[column_name]:
                copy_value = cdbwrapc.SQLdate_literal(copy_value)
            else:
                copy_value = str(copy_value)
            copy_values.append(copy_value)
        rows.append(copy_values)

    return insert_rows(table_name, columns, rows, insert_chunk_size=insert_chunk_size)


def format_in_condition(column, values):
    """
    Safely formats a list of values for a column into an IN condition. If values exceeds
    NUM_IN_CONDITION_MAX_VALUES, the list of values is split into multiple IN conditions concatenated with OR
    to ensure compatibility with various databases.

    For example, assuming NUM_IN_CONDITION_MAX_VALUES=1000 and a list of values [0, ..., 9999], the formatted
    in condition would be "column IN (0, 1, ..., 999) OR ... OR column IN (9000, 9001, ..., 9999)".

    :param column: Name of the column for the IN condition.
    :param values: List of values for the IN condition.
    :return: A formatted IN condition that splits NUM_IN_CONDITION_MAX_VALUES values into separate IN
             conditions concatenated with OR.
    """

    def _make_date_literals(literals):
        result = []
        for literal in literals:
            if literal is None:
                result.append("NULL")
            else:
                result.append(sqlapi.SQLdate_literal(literal))
        return ", ".join(result)

    def _make_string_literals(literals):
        result = []
        for literal in literals:
            if literal is None:
                result.append("NULL")
            else:
                result.append(u"'%s'" % literal.replace("'", "''"))
        return ", ".join(result)

    def _make_literals(literals):
        result = []
        for literal in literals:
            if literal is None:
                result.append("NULL")
            else:
                result.append(str(literal))
        return ", ".join(result)

    if not values:
        return ""

    literal_func = None
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            literal_func = _make_string_literals
        elif isinstance(value, datetime.date):
            literal_func = _make_date_literals
        else:
            literal_func = _make_literals
        break;

    if not literal_func:
        return f"{column} IS NULL"

    if len(values) <= NUM_IN_CONDITION_MAX_VALUES:
        return f"{column} IN ({literal_func(values)})"

    in_condition = ""
    num_formatted_values = 0
    for values_chunk in chunk(values, NUM_IN_CONDITION_MAX_VALUES):
        in_condition += f"{column} IN ({literal_func(values_chunk)})"

        # If we are not in last iteration (chunk), append OR for next IN condition.
        num_formatted_values += len(values_chunk)
        if num_formatted_values < len(values):
            in_condition += " OR "

    return in_condition


def format_recursive():
    if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
        return "RECURSIVE"
    else:
        return ""


def insert_rows(table_name, columns, rows, insert_chunk_size=INSERT_ROW_MAX):
    """
    Insert multiple rows in a table.

    :param table_name:
        Name of the table to insert the rows.
    :param columns:
        List of column names. The column names must match to the given rows
    :param rows:
        List of rows to be inserted. Each row has to be a list of values that matches to the given
        column names and each value has to be a valid sql literal
    """

    if not rows:
        return

    column_names = ",".join(columns)
    rows_inserted = 0
    for rows_chunk in chunk(rows, insert_chunk_size):
        # Build the statement for inserting the row values into the columns. The statement depends on the used
        # DBMS.
        match sqlapi.SQLdbms(): # pylint: disable=syntax-error
            case sqlapi.DBMS_ORACLE:
                insert_statements = [
                    f"INTO {table_name} ({column_names}) VALUES ({','.join(row)})"
                    for row in rows_chunk
                ]
                stmt = "INSERT ALL\n{}\nSELECT 1 from dual".format('\n'.join(insert_statements))
            case sqlapi.DBMS_MSSQL:
                joined_rows = ",\n".join([f"({','.join(row)})" for row in rows_chunk])
                stmt = f"""
                    INSERT INTO {table_name} ({column_names})
                    SELECT {column_names} FROM ( VALUES {joined_rows} )
                    AS vals ({column_names})
                """
            case _:
                # Default (SQLite).
                joined_rows = ",\n".join([f"({','.join(row)})" for row in rows_chunk])
                stmt = f"INSERT INTO {table_name} ({column_names}) VALUES {joined_rows}"

        # Actual insertion of the rows in the current chunk.
        rows_inserted = rows_inserted + sqlapi.SQL(stmt)
    LOG.debug("Inserted %d rows in %s", rows_inserted, table_name)
    return rows_inserted


def get_assigned_class_codes(data):
    if "metadata" in data:
        return data["metadata"].get("assigned_classes", [])
    else:
        return data.get("assigned_classes", [])


def get_deleted_class_codes(data):
    if "metadata" in data:
        return data["metadata"].get("deleted_classes", [])
    else:
        return data.get("deleted_classes", [])

def get_deleted_property_codes(data):
    if "metadata" in data:
        return data["metadata"].get("deleted_properties", [])
    else:
        return data.get("deleted_properties", [])

def preset_mask_data(classification_data, ctx=None):
    from cs.classification.rest.utils import ensure_json_serialiability
    mask_data = {
        "assigned_classes": classification_data["assigned_classes"],
        "values": classification_data["properties"]
    }
    mask_data_str = json.dumps(ensure_json_serialiability(mask_data))
    if ctx:
        ctx.set('cdb::argument.classification_web_ctrl', mask_data_str)
    return mask_data_str
