#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
import logging
import cdbwrapc

from datetime import datetime

from cdb import cdbuuid
from cdb import i18n
from cdb import sqlapi
from cdb import sig
from cdb import rte
from cdb import kernel
from cdb import transactions
from cdb import ue
from cdb import util as cdb_util
from cdb.dberrors import DBConstraintViolation
from cdb.objects import ByID
from cdb.objects import expressions
from cdb.objects import references
from cdb.objects.core import Object, object_from_handle
from cdb.objects.core import ClassRegistry
from cdb.platform.acs import GEN_CDB_ACC_RIGHTS_V_EVENT
from cdb.platform.mom import SimpleArguments

from cdb.platform.gui import CDBCatalog, Message

from cs.classification import classes
from cs.classification import computations
from cs.classification import tools
from cs.classification import util

LOG = logging.getLogger(__name__)

fObjectClassification = expressions.Forward("cs.classification.ObjectClassification")
fObjectPropertyValue = expressions.Forward("cs.classification.ObjectPropertyValue")
fEnumObjectPropertyValue = expressions.Forward("cs.classification.EnumObjectPropertyValue")

fBlockProperty = expressions.Forward("cs.classification.catalog.BlockProperty")
fBlockClassProperty = expressions.Forward("cs.classification.classes.BlockClassProperty")


classification_elink_urls_by_operation = {
    'copy': "/byname/copy_classification/{cdb_object_id}",
    'create': "/byname/create_classification/{cdb_classname}",
    'modify': "/byname/object_classification/{cdb_object_id}",
    'info': "/byname/object_classification/{cdb_object_id}?readonly=true",
    'query': "/byname/search_classification/{cdb_classname}",
    'query_catalog': "/byname/search_classification/{cdb_classname}",
    'requery': "/byname/search_classification/{cdb_classname}"
}


class ClassificationConstants(object):
    """
    Constants for cs.classification.
    """
    ASSIGNED_CLASSES = "assigned_classes"
    BLOCK_CHILD_PROPS = "child_props"
    BLOCK_PATH_SEP = "/"
    FLOAT_VALUE = "float_value"
    FLOAT_VALUE_NORMALIZED = "float_value_normalized"
    FLOAT_VALUE_UNIT_OID = "unit_object_id"
    METADATA = "metadata"
    MULTILANG_VALUE = "text_value"
    PERSISTENT_VALUES_CHECKSUM = "persistent_values_checksum"
    PROPERTIES = "properties"
    UE_ARGS = "ue_args"
    VALUE = "value"


class ClassificationException(ue.Exception):

    _message = None

    def __init__(self, message_id, *args):
        super(ClassificationException, self).__init__(message_id, *args)
        self.message_id = message_id
        self.args = args

    def getDetails(self):
        return ""

    def getMessageId(self):
        return self.message_id

    def getMessage(self, attr_name, message_id=None, args=None):
        if message_id:
            message = Message.ByKeys(message_id)
            return tools.get_message_for_all_languages(attr_name, message, args)
        else:
            message = Message.ByKeys(self.message_id)
            return tools.get_message_for_all_languages(attr_name, message, self.args)


class ClassificationChecksum(Object):
    __classname__ = "cs_classification_checksum"
    __maps_to__ = "cs_classification_checksum"


class ClassificationContext(Object):
    __classname__ = "cs_classification_context"
    __maps_to__ = "cs_classification_context"


class ObjectClassification(Object):
    __classname__ = "cs_object_classification"
    __maps_to__ = "cs_object_classification"

    Class = references.Reference_1(
        classes.ClassificationClass,
        classes.ClassificationClass.code == fObjectClassification.class_code
    )

    def copy_for_ref_object(self, ref_object, ctx=None):
        """
        Is called during batch copy or index of an classified object. Can be used to implement a special copy
        function for ObjectClassification
        `ref_object` is the object to be classified, `ctx` is the optional context of the operation.
        """

    def _get_object(self):
        return ByID(self.ref_object_id)

    Object = references.Reference_Methods(Object, lambda self: self._get_object())

class ObjectClassificationLog(Object):
    __classname__ = "cs_object_classification_log"
    __maps_to__ = "cs_object_classification_log"

    @classmethod
    def clear_index_dates(cls):
        stmt = "cs_object_classification_log set cdb_index_date = NULL"
        sqlapi.SQLupdate(stmt)

    @classmethod
    def get_dates(cls, ref_object_id):
        try:
            stmt = """
                SELECT cdb_mdate, cdb_index_date 
                FROM cs_object_classification_log
                WHERE ref_object_id = '{}'
            """.format(ref_object_id)
            rset = sqlapi.RecordSet2(sql=stmt)
            r = rset[0]
            return r.cdb_mdate, r.cdb_index_date
        except Exception:
            return None, None

    @classmethod
    def get_ref_object_ids_for_reindex(cls, modified_from=None):
        if modified_from:
            where_condition = """
                cs_object_classification_log.cdb_mdate IS NOT NULL
                AND cs_object_classification_log.cdb_mdate >= {}
            """.format(
                cdbwrapc.SQLdate_literal(modified_from)
            )
        else:
            where_condition = """
                cs_object_classification_log.cdb_index_date IS NULL
                OR cs_object_classification_log.cdb_mdate > cs_object_classification_log.cdb_index_date
            """
        stmt = """
            SELECT cs_object_classification.ref_object_id 
            FROM cs_object_classification 
            LEFT JOIN cs_object_classification_log
            ON cs_object_classification.ref_object_id = cs_object_classification_log.ref_object_id
            WHERE {where_condition}
            UNION
            SELECT cs_object_property_value.ref_object_id
            FROM cs_object_property_value 
            LEFT JOIN cs_object_classification_log 
            ON cs_object_property_value.ref_object_id = cs_object_classification_log.ref_object_id
            WHERE {where_condition}
        """.format(where_condition=where_condition)
        rset = sqlapi.RecordSet2(sql=stmt)
        obj_ids = [r.ref_object_id for r in rset]
        return obj_ids

    @classmethod
    def update_log(cls, ref_object_id, cdb_mdate=None, cdb_index_date=None):
        if not cdb_mdate and not cdb_index_date:
            # no update needed
            return

        set_mdate = "cdb_mdate = {}".format(cdbwrapc.SQLdate_literal(cdb_mdate)) \
            if cdb_mdate else ""
        set_index_date = "cdb_index_date = {}".format(cdbwrapc.SQLdate_literal(cdb_index_date)) \
            if cdb_index_date else ""
        stmt = "cs_object_classification_log set {} {} {} where ref_object_id = '{}'".format(
                set_mdate,
                "," if set_mdate and set_index_date else "",
                set_index_date,
                sqlapi.quote(ref_object_id)
        )
        if not sqlapi.SQLupdate(stmt):
            ins = cdb_util.DBInserter("cs_object_classification_log")
            ins.add("ref_object_id", ref_object_id)
            ins.add("cdb_mdate", cdb_mdate)
            ins.add("cdb_index_date", cdb_index_date)
            ins.insert()

    @classmethod
    def update_logs(cls, ref_object_ids, cdb_index_date=None, cdb_mdate=None):
        if not ref_object_ids:
            return

        cols = ["ref_object_id"]
        if cdb_index_date:
            index_date = cdbwrapc.SQLdate_literal(cdb_index_date)
            set_index_date = "cdb_index_date = {}".format(index_date)
            cols.append("cdb_index_date")
        else:
            index_date = None
            set_index_date = ""

        if cdb_mdate:
            m_date = cdbwrapc.SQLdate_literal(cdb_mdate)
            set_mdate = "cdb_mdate = {}".format(m_date)
            cols.append("cdb_mdate")
        else:
            m_date = None
            set_mdate = ""

        for ref_object_ids_chunk in tools.chunk(ref_object_ids, tools.SELECT_ROW_MAX):
            stmt = "cs_object_classification_log set {} {} {} where {}".format(
                set_index_date,
                "," if set_mdate and set_index_date else "",
                set_mdate,
                tools.format_in_condition("ref_object_id", ref_object_ids_chunk)
            )
            rows_affected = sqlapi.SQLupdate(stmt)
            if rows_affected != len(ref_object_ids_chunk):
                # insert missing rows
                sql_stmt = "select ref_object_id from cs_object_classification_log where {}".format(
                    tools.format_in_condition("ref_object_id", ref_object_ids_chunk)
                )
                updated_ref_object_ids = set([r.ref_object_id for r in sqlapi.RecordSet2(sql=sql_stmt)])
                rows = []
                for ref_object_id in set(ref_object_ids_chunk) - updated_ref_object_ids:
                    row = [f"'{ref_object_id}'"]
                    if index_date:
                        row.append(index_date)
                    if m_date:
                        row.append(m_date)
                    rows.append(row)
                tools.insert_rows(
                    "cs_object_classification_log", cols, rows
                )


class ObjectPropertyValue(Object):
    __classname__ = "cs_object_property_value"
    __maps_to__ = "cs_object_property_value"

    def _get_object(self):
        return ByID(self.ref_object_id)

    Object = references.Reference_Methods(Object, lambda self: self._get_object())

    @classmethod
    def build_value_dict(cls, values):
        """ Builds a dictionary for insert or update purposes
        on cs_object_property_value"""
        attr = cls.get_value_attr()
        if isinstance(attr, list):
            if isinstance(values, dict):
                return {key: values[key] for key in attr}
            else:
                return {key: None for key in attr}
        else:
            return {attr: values}

    @classmethod
    def get_value_from_record(cls, val):
        property_type = val.property_type
        if "boolean" == property_type:
            boolean_value = val.boolean_value
            if boolean_value == 1:
                return True
            elif boolean_value == 0:
                return False
            else:
                return None
        else:
            attr = type_map[property_type]._value_attr
            if isinstance(attr, list):
                return {key: getattr(val, key) for key in attr}
            else:
                return getattr(val, attr)

    @classmethod
    def get_empty_value(cls):
        """ Builds an empty value for the given value class for client communication
        purposes. For complex value types, e.g. float properties, a dictionary
        with specific keys is returned. For basic value types, e.g. string or int, None is returned.
        """
        attr = cls.get_value_attr()
        if isinstance(attr, list):
            return {key: None for key in attr}
        else:
            return None

    @classmethod
    def get_value_attr(cls):
        return cls._value_attr

    def _value(self):
        attr = self.get_value_attr()
        if isinstance(attr, list):
            return {key: getattr(self, key) for key in attr}
        else:
            return getattr(self, attr)

    @property
    def value(self):
        return self._value()

    @classmethod
    def value_exists_for_ref_obj(cls, ref_object_id):
        sql_stmt = "SELECT * FROM cs_object_property_value where ref_object_id = '{ref_object_id}'".format(
            ref_object_id=ref_object_id
        )
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            from_str = "FROM dual"
        else:
            from_str = ""
        exists_qry = "SELECT 1 AS cnt {from_str} WHERE EXISTS ({sql_stmt})".format(from_str=from_str, sql_stmt=sql_stmt)
        return len(sqlapi.RecordSet2(sql=exists_qry)) > 0

    @classmethod
    def value_exists(cls, prop_code):
        sql_stmt = "SELECT * FROM cs_object_property_value where property_code = '{prop_code}'".format(
            prop_code=prop_code
        )
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            from_str = "FROM dual"
        else:
            from_str = ""
        exists_qry = "SELECT 1 AS cnt {from_str} WHERE EXISTS ({sql_stmt})".format(from_str=from_str, sql_stmt=sql_stmt)
        return len(sqlapi.RecordSet2(sql=exists_qry)) > 0

    @classmethod
    def value_exists_in(cls, prop_codes):
        if not prop_codes:
            return False
        sql_stmt = "SELECT * FROM cs_object_property_value where {}".format(
            tools.format_in_condition("property_code", prop_codes)
        )
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            from_str = "FROM dual"
        else:
            from_str = ""
        exists_qry = "SELECT 1 AS cnt {from_str} WHERE EXISTS ({sql_stmt})".format(from_str=from_str, sql_stmt=sql_stmt)
        return len(sqlapi.RecordSet2(sql=exists_qry)) > 0


class TextObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'text'

    _value_attr = "text_value"


class BooleanObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'boolean'

    _value_attr = "boolean_value"

    def _value(self):
        if super(BooleanObjectPropertyValue, self)._value() == 1:
            return True
        elif super(BooleanObjectPropertyValue, self)._value() == 0:
            return False
        else:
            return None


class DatetimeObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'datetime'

    _value_attr = "datetime_value"


class IntegerObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'integer'

    _value_attr = "integer_value"


class FloatObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'float'

    _value_attr = ["float_value", "unit_object_id", "float_value_normalized"]


class FloatRangeObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'float_range'

    _value_attr = ["range_identifier", "float_value", "unit_object_id", "float_value_normalized"]

    RANGE_IDENTIFIER = ["min", "max"]

    @classmethod
    def get_empty_value(cls):
        value = {}
        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            value[range_identifier] = {
                "id": None,
                "float_value": None,
                "float_value_normalized": None,
                "range_identifier": range_identifier,
                "unit_object_id": None
            }
        return value


class MultilangObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'multilang'

    _value_attr = ["text_value", "iso_language_code"]

    @classmethod
    def get_empty_value(cls):
        value = {}
        for language in tools.get_active_classification_languages():
            value[language] = {
                "id": None,
                "iso_language_code": language,
                "text_value": None
            }
        return value


class ObjectReferenceObjectPropertyValue(ObjectPropertyValue):
    __match__ = ObjectPropertyValue.property_type == 'objectref'

    _value_attr = "object_reference_value"


type_map = {
    "text": TextObjectPropertyValue,
    "boolean": BooleanObjectPropertyValue,
    "datetime": DatetimeObjectPropertyValue,
    "integer": IntegerObjectPropertyValue,
    "float": FloatObjectPropertyValue,
    "float_range": FloatRangeObjectPropertyValue,
    "multilang": MultilangObjectPropertyValue,
    "objectref": ObjectReferenceObjectPropertyValue
}

block_prop_descriptions = None


def get_block_prop_description_pattern(block_property_code):
    global block_prop_descriptions
    if block_prop_descriptions:
        return block_prop_descriptions.get(block_property_code)
    else:
        block_prop_descriptions = {}
        languages = [i18n.default()] + i18n.FallbackLanguages()

        i18n_block_description_fields = [field.name for field in fBlockProperty.description.getLanguageFields().values()]
        where_condition = "("
        sub_where_conditions = []
        for description_field in i18n_block_description_fields:
            sub_where_conditions.append("({} IS NOT NULL AND {} != '')".format(description_field, description_field))
        where_condition += " OR ".join(sub_where_conditions) + ")"

        block_props_with_description = fBlockProperty.Query(where_condition)

        i18n_block_description_fields = [field.name for field in fBlockClassProperty.description.getLanguageFields().values()]
        sub_where_conditions = []
        for description_field in i18n_block_description_fields:
            sub_where_conditions.append("({} IS NOT NULL AND {} != '')".format(description_field, description_field))
        where_condition = " OR ".join(sub_where_conditions)

        block_class_props_with_description = fBlockClassProperty.Query(where_condition)

        for block_prop in block_props_with_description + block_class_props_with_description:
            for lang_iso_code in languages:
                attr_name = 'description_' + lang_iso_code
                if hasattr(block_prop, attr_name):
                    val = getattr(block_prop, attr_name)
                    if val:
                        block_prop_descriptions[block_prop.code] = val
                        break
        return block_prop_descriptions.get(block_property_code)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _connect():
    from cs.classification import operation

    rset = sqlapi.RecordSet2(sql="select distinct dd_classname from cs_classification_applicabilit")
    tables = set([kernel.getPrimaryTableForClass(r["dd_classname"]) for r in rset])
    for table in tables:
        # connect classification methods for modifying usecases
        if table:
            pycls = ClassRegistry().find(table)
            if pycls:
                sig.connect(pycls, "copy", "pre")(_check_classification)
                sig.connect(pycls, "copy", "post")(_copy_classification)
                sig.connect(pycls, "create", "pre")(_check_classification)
                sig.connect(pycls, "create", "post")(_create_classification)
                sig.connect(pycls, "delete", "post")(_delete_classification)
                sig.connect(
                    pycls, list, "cs_classification_multiple_edit", "now"
                )(operation._multiple_edit_classification)

                if table in ["zeichnung", "teile_stamm"]:
                    sig.connect(pycls, "index", "post")(_copy_classification)
            else:
                LOG.error(
                    "Cannot connect classification events (copy, index, delete) for table '%s'. No cdb.objects class could be found." % table
                )

    stmt = """
        select distinct classname from cdb_operations
            where name in ('cs_classification_multiple_edit', 'cs_classification_object_plan')
            and not classname = 'cs_classification_op_result'
    """
    rset = sqlapi.RecordSet2(sql=stmt)
    tables.update(set([kernel.getPrimaryTableForClass(r["classname"]) for r in rset]))
    for table in tables:
        if table:
            pycls = ClassRegistry().find(table)
            if pycls:
                sig.connect(pycls, "copy", "pre_mask")(_modify_classification_web_registers)
                sig.connect(pycls, "create", "pre_mask")(_modify_classification_web_registers)
                sig.connect(pycls, "info", "pre_mask")(_modify_classification_web_registers)
                sig.connect(pycls, "modify", "pre_mask")(_modify_classification_web_registers)
                sig.connect(pycls, "query", "pre_mask")(_modify_classification_web_registers)
                sig.connect(pycls, "query_catalog", "pre_mask")(_modify_classification_web_registers)
                sig.connect(pycls, "requery", "pre_mask")(_modify_classification_web_registers)
                sig.connect(
                    pycls, list, "cs_classification_multiple_edit", "pre_mask"
                )(operation._multiple_edit_classification_pre_mask_classcheck)
                setattr(pycls, 'on_cs_classification_object_plan_now', classmethod(_show_object_plan))
            else:
                LOG.error(
                    "Cannot connect classification events (copy, index, delete) for table '%s'. No cdb.objects class could be found." % table
                )


@sig.connect(GEN_CDB_ACC_RIGHTS_V_EVENT)
def _add_write_access_obj():
    return ("cs_classification_applicabilit", "write_access_obj", "'Universial Classification'")


@sig.connect(GEN_CDB_ACC_RIGHTS_V_EVENT)
def _add_write_access_objclassification():
    return ("cs_classification_applicabilit", "write_access_objclassification", "'Universial Classification'")


def _show_object_plan(cls, ctx):
    prepare_oplan(cls._getClassname())
    ctx.url("/classification-objectplan?classname=" + cls._getClassname())


def _modify_classification_web_registers(obj, ctx):

    if "classification_web_ctrl" not in ctx.dialog.get_attribute_names():
        # disable all register if no classification mask is configured
        ctx.disable_registers([
            'cs_classification',
            'cs_classification_tab',
            'cs_classification_tab_c',
            'cs_classification_tab_copy',
            'cs_classification_tab_info',
            'cs_classification_tab_s',
            'cs_classification_web',
            'cs_classification_tab_web',
            'cs_classification_tab_c_web',
            'cs_classification_tab_copy_web',
            'cs_classification_tab_s_web'
        ])
        return

    if ctx.uses_webui:
        registers_to_disable = [
            'cs_classification',
            'cs_classification_tab',
            'cs_classification_tab_c',
            'cs_classification_tab_copy',
            'cs_classification_tab_info',
            'cs_classification_tab_s'
        ]
        if "info" == ctx.action:
            registers_to_disable.append('cs_classification_web')
        ctx.disable_registers(registers_to_disable)
    else:
        ctx.disable_registers([
            'cs_classification_web',
            'cs_classification_tab_web',
            'cs_classification_tab_c_web',
            'cs_classification_tab_copy_web',
            'cs_classification_tab_s_web'
        ])
        url = classification_elink_urls_by_operation.get(ctx.action, '')
        template_id = getattr(ctx.cdbtemplate, "cdb_object_id", None)
        if template_id:
            url = classification_elink_urls_by_operation.get('copy', '').format(cdb_object_id=template_id)

        if url:
            if "_____is_generic_classification_tab_____" in ctx.dialog.get_attribute_names():
                ctx.set_elink_url(
                    "cdb::argument.classification_web_ctrl", url.format(
                        cdb_classname=ctx.classname, cdb_object_id=obj.cdb_object_id
                    )
                )
            if "query" == ctx.action and "classification_web_ctrl" in ctx.sys_args.get_attribute_names():
                # activate classification tab if classified search data is preset
                data = ctx.sys_args.classification_web_ctrl
                if data:
                    d = json.loads(data)
                    if tools.get_assigned_class_codes(d) or d.get("values", {}):
                        if "_____is_generic_classification_tab_____" in ctx.dialog.get_attribute_names():
                            ctx.set_active_register('cs_classification')
                        else:
                            ctx.set_active_register('cs_classification_tab_s')


def _copy_classification(obj, ctx):
    if ctx.error:
        return

    if "classification_web_ctrl" in ctx.sys_args.get_attribute_names():
        _create_classification(obj, ctx)
    else:
        if util.check_arg(ctx, "cs.classification.prevent_copy", "1"):
            return
        copy_classification(ctx.cdbtemplate.cdb_object_id, obj, ctx)


def copy_classification(source, target, ctx=None):
    """
    Copies the classification data from source to target
    `source` and contains the ``cdb_object_id`` of the template and
    `target` is a `cdb.objects.Object`.
    """

    from cs.classification import api
    from cs.classification.classes import ClassificationClass
    from cs.classification.classification_data import ClassificationData
    from cs.classification.object_classification import ClassificationUpdater

    object_classifications_to_copy = []
    with transactions.Transaction():
        # copy assigned classes
        object_classifications = ObjectClassification.KeywordQuery(ref_object_id=source)
        assigned_class_codes = [
            object_classification.class_code for object_classification in object_classifications
        ]

        copy_infos = ClassificationClass.get_copy_info(
            dd_classname=target.GetClassname(), class_codes=assigned_class_codes
        )
        for object_classification in object_classifications:
            if copy_infos.get(object_classification.class_code):
                object_classifications_to_copy.append(object_classification)
                object_classification.copy_for_ref_object(target, ctx)

        if not object_classifications_to_copy and not ObjectPropertyValue.value_exists_for_ref_obj(source):
            # no data to copy
            return

        update_index = True
        if util.check_arg(ctx, "cs.classification.prevent_index_update", "1"):
            update_index = False

        class_codes = [obj.class_code for obj in object_classifications_to_copy]
        classification = ClassificationData(
            obj=source, class_codes=class_codes, narrowed=True,
            check_rights=True, filter_write_access=True
        )
        properties = classification.get_classification_data()
        classification.pad_values(properties, active_props_only=True)
        cdata = {
            "properties": properties,
            "assigned_classes": classification.get_assigned_classes(include_bases=False)
        }
        sig.emit(target.__class__, "classification_copy", "pre")(target, cdata)
        updater = ClassificationUpdater(target, full_update_mode=True)
        update_data = updater.update(data=cdata, check_access=False, update_index=update_index)
        sig.emit(target.__class__, "classification_copy", "post")(target, update_data)



def copy_classifications(ref_object_ids_to_copy, update_index=True):
    """
    Low level copy of classifications for given ref_object_ids. The copied objects are not allowed to be
    classified, otherwise this method will cuase pri key violations. If you are not sure you should call
    delete_classifiations before.

    :param: ref_object_ids:
        Must be a dict of cdb_object_id of source object as key and cdb_object_id of copied object as value.
    :param: update_index:
        If True, the search index is updated. If False, the search index is not updated
        (search index must be updated later manually).
    """

    from cs.classification.solr import index_object_ids

    def _copy_classification_checksums(ref_object_ids):
        def get_value(column_name, row):
            if "ref_object_id" == column_name:
                return ref_object_ids[row["ref_object_id"]]
            else:
                return row[column_name]

        for ref_object_ids_chunk in tools.chunk(list(ref_object_ids.keys()), tools.SELECT_ROW_MAX):
            in_condition = tools.format_in_condition("ref_object_id", ref_object_ids_chunk)
            tools.copy_rows("cs_classification_checksum", in_condition, get_value)

    def _copy_object_classification(table_name, ref_object_ids):
        def get_value(column_name, row):
            if "id" == column_name:
                return cdbuuid.create_uuid()
            elif "ref_object_id" == column_name:
                ref_obj_id = ref_object_ids[row[column_name]]
                ref_object_ids_with_copied_classification.add(ref_obj_id)
                return ref_obj_id
            elif "status" == column_name:
                return 0
            elif "cdb_status_txt" == column_name:
                if row["cdb_objektart"]:
                    try:
                        return cdbwrapc.StatusInfo(row["cdb_objektart"], 0).getStatusTxt()
                    except Exception:  # pylint: disable=W0703
                        pass
                return ''
            else:
                return row[column_name]

        for ref_object_ids_chunk in tools.chunk(list(ref_object_ids.keys()), tools.SELECT_ROW_MAX):
            in_condition = tools.format_in_condition("ref_object_id", ref_object_ids_chunk)
            tools.copy_rows(table_name, in_condition, get_value)

    with transactions.Transaction():
        ref_object_ids_with_copied_classification = set()
        _copy_object_classification("cs_object_classification", ref_object_ids_to_copy)
        _copy_object_classification("cs_object_property_value", ref_object_ids_to_copy)
        _copy_classification_checksums(ref_object_ids_to_copy)

        ref_object_ids_with_copied_classification_list = list(ref_object_ids_with_copied_classification)
        modification_date = datetime.utcnow()
        if update_index:
            try:
                index_object_ids(
                    list(ref_object_ids_with_copied_classification_list), cdb_mdate=modification_date
                )
            except Exception:  # pylint: disable=W0703
                # THINK ABOUT: what to do if index service fails?
                pass
        else:
            ObjectClassificationLog.update_logs(
                ref_object_ids_with_copied_classification_list, cdb_mdate=modification_date
            )

        return ref_object_ids_with_copied_classification_list


def delete_classifications(ref_object_ids):
    with transactions.Transaction():
        classification_tables = [
            "cs_object_classification",
            "cs_object_classification_log",
            "cs_object_property_value",
            "cs_classification_checksum"
        ]
        deleted_rows_by_table = {}
        for ref_object_ids_chunk in tools.chunk(ref_object_ids, tools.DELETE_ROW_MAX):
            for table_name in classification_tables:
                stmt = """FROM {} WHERE {}""".format(
                    table_name,
                    tools.format_in_condition("ref_object_id", ref_object_ids_chunk)
                )
                deleted_rows_by_table[table_name] = \
                    deleted_rows_by_table.get(table_name, 0) + sqlapi.SQLdelete(stmt)

        for table_name in classification_tables:
            LOG.info(
                "Deleted %d rows from %s",
                deleted_rows_by_table.get(table_name, 0), table_name
            )


def _delete_classification(obj, ctx):
    if ctx.error:
        return

    with transactions.Transaction():
        deleted_class_assignments = sqlapi.SQLdelete(
            "from cs_object_classification where ref_object_id='%s'" % ctx.object.cdb_object_id
        )
        sqlapi.SQLdelete(
            "from cs_object_classification_log where ref_object_id='%s'" % ctx.object.cdb_object_id
        )
        deleted_props = sqlapi.SQLdelete(
            "from cs_object_property_value where ref_object_id='%s'" % ctx.object.cdb_object_id
        )
        sqlapi.SQLdelete(
            "from cs_classification_checksum where ref_object_id='%s'" % ctx.object.cdb_object_id
        )

    if deleted_class_assignments or deleted_props:
        from cs.classification import solr
        solr.remove_from_index(obj.cdb_object_id)


def _check_classification(obj, ctx):
    from cs.classification.object_classification import ClassificationUpdater

    if not ctx.uses_webui and "classification_web_ctrl" in ctx.sys_args.get_attribute_names():
        data = ctx.sys_args.classification_web_ctrl
        if data:
            d = json.loads(data)
            classification = {
                "assigned_classes": tools.get_assigned_class_codes(d),
                "properties": d.get("values", {})
            }
            error_messages = ClassificationUpdater.check_classification(classification, check_rights=True)

            if classification['error_messages']:
                error_messages.extend(classification["error_messages"])

            if error_messages:
                error_message = "{}:\n{}".format(
                    cdb_util.get_label("web.cs-classification-component.error_constraints"),
                    "\n".join(error_messages)
                )
                raise ue.Exception(
                    "cs_classification_constraint_violation", error_message
                )


def _create_classification(obj, ctx):
    """
    """
    if ctx.error:
        return

    from cs.classification.api import update_classification

    if "classification_web_ctrl" in ctx.sys_args.get_attribute_names():
        data = ctx.sys_args.classification_web_ctrl
        if data:
            # classification_web_ctrl contains a json string: {"classes":[],"values":"{}"}
            d = json.loads(data)
            if "values" in d:
                upd_data = {
                    "assigned_classes": tools.get_assigned_class_codes(d),
                    "properties": d["values"]
                }
                try:
                    update_classification(obj, upd_data, full_update_mode=True, check_access=False)
                except Exception: # pylint: disable=W0703
                    LOG.exception("Error saving classification data:")
                    raise ue.Exception("cs_classification_err_save_data")
            return
    template_id = getattr(ctx.cdbtemplate, "cdb_object_id", None)
    if template_id:
        try:
            copy_classification(ctx.cdbtemplate.cdb_object_id, obj, ctx)
        except DBConstraintViolation:
            # classification has already been copied
            pass


def pre_submit_hook(hook):
    # server side validation and update of classification data.
    from cs.classification.api import update_classification
    from cs.classification.object_classification import ClassificationUpdater

    data = hook.get_new_value("cdb::argument.classification_web_ctrl")
    if data:
        d = json.loads(data)
        if "values" in d:
            upd_data = {
                "assigned_classes": tools.get_assigned_class_codes(d),
                "properties": d["values"]
            }
            try:
                error_messages = ClassificationUpdater.check_classification(upd_data, check_rights=True)
                if upd_data['error_messages'] or error_messages:
                    combined_error_messages = upd_data.get('error_messages', [])
                    if error_messages:
                        combined_error_messages.extend(error_messages)
                    title = cdb_util.CDBMsg(
                        cdb_util.CDBMsg.kFatal, "cs_classification_err_save_data_title"
                    )
                    hook.set_error(
                        title.getText(i18n.default(), True),
                        "\n".join(upd_data['error_messages'])
                    )
                else:
                    op_state_info = hook.get_operation_state_info()
                    if "CDB_Modify" == op_state_info.get_operation_name():
                        obj_handles = op_state_info.get_objects()
                        if obj_handles:
                            obj = object_from_handle(obj_handles[0])
                            upd_data = {
                                "assigned_classes": tools.get_assigned_class_codes(d),
                                "deleted_classes": tools.get_deleted_class_codes(d),
                                "deleted_properties": tools.get_deleted_property_codes(d),
                                "properties": d["values"]
                            }
                            update_classification(obj, upd_data, full_update_mode=False)
                            hook._from_cdb_classification_hook = True
            except (ue.Exception, ClassificationException) as classification_exception:
                LOG.exception("Error saving classification data:")
                title = cdb_util.CDBMsg(cdb_util.CDBMsg.kFatal, "cs_classification_err_save_data_title")
                hook.set_error(title.getText(i18n.default(), True), str(classification_exception))
            except Exception: # pylint: disable=W0703
                LOG.exception("Error saving classification data:")
                msg = cdb_util.CDBMsg(cdb_util.CDBMsg.kFatal, "cs_classification_err_save_data")
                title = cdb_util.CDBMsg(cdb_util.CDBMsg.kFatal, "cs_classification_err_save_data_title")
                hook.set_error(title.getText(i18n.default(), True), msg.getText(i18n.default(), True))


def _prepare(classname, mode):
    cdbwrapc.prepare_feature_call_by_args(SimpleArguments(cdb_classname='cdb_lic_feature_assign_cl',
                                                          classification_datadict_class=classname,
                                                          classification_access_type=mode))


def prepare_read(classname):
    _prepare(classname, 'read')


def prepare_write(classname):
    _prepare(classname, 'write')


def prepare_oplan(classname):
    from cdb import version
    version.verstring(True)
    sl = 0
    try:
        sl = int(version.verstring(True).split(".")[-1])
    except ValueError:
        pass
    if sl >= 17:
        _prepare(classname, 'oplan')


class AccessModeCatalog(CDBCatalog):

    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        return ["read", "write", "oplan"]


def collect_index_attributes(updater):
    logging.info("Collect ClassificationProperties: %s", updater._cdb_object_id)
    sql_stmt = """
        select text_value from cs_object_property_value where ref_object_id = '{ref_obj_id}' and (property_type = 'text' or property_type = 'multilang')
    """.format(ref_obj_id=updater._cdb_object_id)
    property_values = sqlapi.RecordSet2(sql=sql_stmt)
    for property_value in property_values:
        updater._add_field("descriptive", property_value["text_value"])
