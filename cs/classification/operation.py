# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import json
from datetime import datetime

from cdb import auth, cmsg, i18n, sig, ue, util
from cdb.objects import ByID, expressions, references
from cdb.objects.core import Object
from cdb.platform.gui import Message
from cdb.platform.gui import PythonColumnProvider
from cdb.typeconversion import to_untyped_c_api

from cs.classification import ClassificationException
from cs.classification import tools
from cs.classification.api import ConstaintsViolationException
from cs.classification.tools import get_assigned_class_codes
from cs.classification.util import date_to_iso_str

fClassificationOperation = expressions.Forward("cs.classification.operation.ClassificationOperation")


class ClassificationOperationResult(Object):
    __classname__ = "cs_classification_op_result"
    __maps_to__ = "cs_classification_op_result"


class ClassificationOperation(Object):
    __classname__ = "cs_classification_operation"
    __maps_to__ = "cs_classification_operation"

    Results = references.Reference_N(
        ClassificationOperationResult,
        ClassificationOperationResult.operation_id == fClassificationOperation.cdb_object_id
    )

    general_error_message = None
    success_message = None

    @classmethod
    def _load_messages(cls):
        if not cls.general_error_message:
            cls.general_error_message = Message.ByKeys("cs_classification_multiple_update_general_error")
        if not cls.success_message:
            cls.success_message = Message.ByKeys("cs_classification_multiple_update_successful")

    @classmethod
    def create_operation_result(
        cls, dd_classname, objs, assigned_classes, properties, errors, warnings, title_message=None
    ):
        cls._load_messages()
        operation_args = {
            "cdb_cpersno": auth.persno,
            "dd_classname": dd_classname,
            "finish_time": datetime.utcnow()
        }
        if title_message:
            operation_args.update(
                tools.get_message_for_all_languages("title", title_message)
            )
        operation = ClassificationOperation.Create(**operation_args)

        classification_data_to_store = {
            "assigned_classes": assigned_classes,
            "properties": properties
        }
        operation.SetText(
            "classification_data",
            json.dumps(classification_data_to_store, default=date_to_iso_str)
        )

        default_lang = i18n.default()
        exec_state = 3
        error_count = 0
        success_count = 0
        warning_count = 0
        for obj in objs:
            result_args = {
                "operation_id": operation.cdb_object_id,
                "ref_object_id": obj.cdb_object_id
            }
            details = ""
            exec_state = 3
            error_or_warning = errors.get(obj.cdb_object_id)
            if error_or_warning:
                exec_state = 1
                error_count += 1
            else:
                error_or_warning = warnings.get(obj.cdb_object_id, [None])[0]
                if error_or_warning:
                    exec_state = 2
                    warning_count += 1
            if error_or_warning:
                if isinstance(error_or_warning, ConstaintsViolationException):
                    result_args.update(error_or_warning.getMessage(
                        "message", "cs_classification_constraint_violation_err")
                    )
                    details = str(error_or_warning)
                elif isinstance(error_or_warning, ClassificationException):
                    result_args.update(error_or_warning.getMessage("message"))
                    details = error_or_warning.getDetails()
                elif isinstance(error_or_warning, ue.Exception):
                    result_args.update({
                        "message_" + default_lang: str(error_or_warning)
                    })
                else:
                    result_args.update(tools.get_message_for_all_languages(
                        "message", cls.general_error_message)
                    )
                    details = str(error_or_warning)
            else:
                success_count += 1
                result_args.update(
                    tools.get_message_for_all_languages("message", cls.success_message)
                )
            result_args["exec_state"] = exec_state
            result = ClassificationOperationResult.Create(**result_args)
            result.SetText("details", details)

        operation_update_args = {
            "exec_state": exec_state,
            "failures": error_count,
            "successes": success_count,
            "warnings": warning_count
        }
        operation.Update(**operation_update_args)
        return operation


@sig.connect(ClassificationOperationResult, list, "cs_classification_multiple_edit", "pre_mask")
def _multiple_edit_classification_pre_mask(_, ctx):
    if "cs_classification_op2result" == ctx.relationship_name:
        # set url parameter operation id to id of parent
        ctx.set_elink_url(
            "cdb::argument.classification_web_ctrl",
            "/byname/update_classification/cs_classification_operation?operation_id={}".format(
                ctx.parent.cdb_object_id
            )
        )


@sig.connect(ClassificationOperationResult, list, "cs_classification_multiple_edit", "now")
def _multiple_edit_classification(objs, ctx):
    from cs.classification.object_classification import ClassificationUpdater
    from cs.classification.rest import utils

    try:
        data = json.loads(ctx.sys_args.classification_web_ctrl)
    except AttributeError:
        raise ue.Exception("cs_classification_err_mask_element")
    except ValueError:
        data = {}

    objs_to_update = []
    if "cs_classification_op2result" == ctx.relationship_name:
        for result_obj in objs:
            objs_to_update.append(ByID(result_obj.ref_object_id))
        classification_operation = ClassificationOperation.ByKeys(ctx.parent.cdb_object_id)
        dd_classname = classification_operation.dd_classname
    else:
        dd_classname = ctx.classname
        objs_to_update = objs

    assigned_classes = get_assigned_class_codes(data)
    properties = data.get("values", {})
    errors, warnings = ClassificationUpdater.multiple_update(
        objs_to_update,
        {
            "assigned_classes": assigned_classes,
            "properties": properties
        },
        typeconversion=utils.convert_from_json
    )
    operation = ClassificationOperation.create_operation_result(
        dd_classname,
        objs_to_update,
        assigned_classes,
        properties,
        errors,
        warnings,
        Message.ByKeys("cs_classification_multiple_update")
    )

    # open created cs_classifcation_op object ...
    msg = cmsg.Cdbcmsg("cs_classification_operation", "CDB_ShowObject", 0)
    msg.add_item("cdb_object_id", "cs_classification_operation", operation.cdb_object_id)
    if ctx.uses_webui:
        ctx.url(msg.url(""))
    else:
        ctx.url(msg.eLink_url())


def _multiple_edit_classification_pre_mask_classcheck(objs, ctx):
    from collections import defaultdict
    from cs.classification import api, ObjectClassification

    oids = [obj.cdb_object_id for obj in objs]
    classes_by_oid = defaultdict(list)
    for classification in ObjectClassification.Query(ObjectClassification.ref_object_id.one_of(*oids)):
        classes_by_oid[classification.ref_object_id].append(classification.class_code)
    common_classes = None
    for obj in objs:
        assigned_classes = classes_by_oid.get(obj.cdb_object_id, [])
        if common_classes is not None:
            common_classes = common_classes.intersection(set(assigned_classes))
        else:
            common_classes = set(assigned_classes)
    if common_classes:
        data_json = json.dumps({'assigned_classes': list(common_classes)})
        ctx.set('cdb::argument.classification_web_ctrl', data_json)


class OperationStatusProvider(PythonColumnProvider):

    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [{
            'column_id': 'system:exec_state',
            'label': util.get_label('cs_classification_operation_status'),
            'data_type': 'text'
    }]

    @staticmethod
    def getColumnData(classname, table_data):
        result = []
        for row in table_data:
            for exec_state in row['exec_state']:
                result.append({
                    "system:exec_state": to_untyped_c_api(
                        util.get_label('cs_classification_operation_status_{}'.format(exec_state))
                    )
                })
        return result

    @staticmethod
    def getRequiredColumns(classname, available_columns):
        return ['exec_state']

