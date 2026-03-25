#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import datetime
import logging
import uuid

from cdb import auth, sqlapi, transactions, util
from cdb.objects.core import Object
from cs.baselining import Baseline

LOG = logging.getLogger(__name__)


class BaseliningNotSupportedError(ValueError):
    pass


class BaselineTools(object):
    @classmethod
    def generate_baseline_id(cls):
        return uuid.uuid4()

    @classmethod
    def check_baseline_support(cls, obj, readonly=False):
        if not isinstance(obj, Object):
            LOG.error("%s is not a cdb.objects.core.Object", type(obj))
            raise BaseliningNotSupportedError(
                "%s is not a cdb.objects.core.Object" % type(obj)
            )
        if not hasattr(obj, "ce_baseline_id"):
            LOG.error("%s has no ce_baseline_id attribute", obj.GetClassname())
            raise BaseliningNotSupportedError(
                "%s has no ce_baseline_id attribute" % obj.GetClassname()
            )
        if "cdb_object_id" in obj.KeyDict() and not hasattr(
            obj, "ce_baseline_object_id"
        ):
            LOG.error("%s has no ce_baseline_object_id attribute", obj.GetClassname())
            raise BaseliningNotSupportedError(
                "%s has no ce_baseline_object_id attribute" % obj.GetClassname()
            )
        if (
            "cdb_object_id" in obj.KeyDict()
            and hasattr(obj, "ce_baseline_object_id")
            and obj.cdb_object_id
            and not obj.ce_baseline_object_id
        ):
            # condition obj.cdb_object_id to ensure it only reacts to valid objects
            raise BaseliningNotSupportedError(
                "%s has a invalid ce_baseline_object_id" % obj
            )
        if (
            "cdb_object_id" not in obj.KeyDict()
            and "ce_baseline_id" not in obj.KeyDict()
        ):
            LOG.error(
                "%s does not contain ce_baseline_id in primary keys", obj.GetClassname()
            )
            raise BaseliningNotSupportedError(
                "%s does not contain ce_baseline_id in primary keys"
                % obj.GetClassname()
            )
        if not readonly and (
            not hasattr(obj, "copy_baseline_elements")
            or not callable(obj.copy_baseline_elements)
        ):
            LOG.error("%s has no copy_baseline_elements method", type(obj))
            raise BaseliningNotSupportedError(
                "%s has no copy_baseline_elements method" % type(obj)
            )
        if not readonly and (
            not hasattr(obj, "remove_all_baseline_elements")
            or not callable(obj.remove_all_baseline_elements)
        ):
            LOG.error("%s has no remove_all_baseline_elements method", type(obj))
            raise BaseliningNotSupportedError(
                "%s has no remove_all_baseline_elements method" % type(obj)
            )
        return True

    @classmethod
    def fix_baseline_object_ids(cls, relation):
        cnts = []
        ti = util.tables[relation]
        attr_list = ti.attrname_list()
        if "cdb_object_id" in attr_list:
            if "ce_baseline_id" in attr_list:
                cnts.append(
                    sqlapi.SQLupdate(
                        """
                        {table} SET
                            ce_baseline_id=''
                        WHERE (
                            ce_baseline_id IS NULL
                        )""".format(
                            table=ti.name()
                        )
                    )
                )
            cnts.append(
                sqlapi.SQLupdate(
                    """
                    {table} SET
                        ce_baseline_object_id=cdb_object_id
                    WHERE (
                        ce_baseline_object_id IS NULL OR ce_baseline_id=''
                    )""".format(
                        table=ti.name()
                    )
                )
            )
            cnts.append(
                sqlapi.SQLupdate(
                    """
                    {table} SET
                        ce_baseline_origin_id=cdb_object_id
                    WHERE (
                        ce_baseline_origin_id IS NULL OR ce_baseline_id=''
                    )""".format(
                        table=ti.name()
                    )
                )
            )
        return cnts

    @classmethod
    def get_baselines(cls, obj):
        """get all baseline elements but itself"""
        if cls.check_baseline_support(obj, readonly=True):
            if hasattr(obj, "ce_baseline_object_id"):
                # if we have it --> use it
                condition = obj.__table_info__.condition(
                    ["ce_baseline_object_id"], [obj.ce_baseline_object_id]
                )
                keydict = obj.KeyDict()
                keycondition = obj.__table_info__.condition(
                    list(keydict),
                    list(keydict.values()),
                )
                for k in list(keydict):
                    keycondition = keycondition.replace("%s=" % k, "entity.%s=" % k)
                qry = """
                    SELECT entity.* FROM %s entity, %s baseline
                    WHERE
                        %s
                        AND NOT (%s)
                        AND entity.ce_baseline_id=baseline.cdb_object_id
                    ORDER BY baseline.ce_baseline_cdate DESC"""
                stmt = qry % (
                    obj.GetTableName(),
                    Baseline.GetTableName(),
                    condition,
                    keycondition,
                )
            else:
                keydict = obj.KeyDict()
                condition = obj.__table_info__.condition(
                    [x for x in list(keydict) if x != "ce_baseline_id"],
                    [v for (k, v) in keydict.items() if k != "ce_baseline_id"],
                )
                keycondition = obj.__table_info__.condition(
                    list(keydict),
                    list(keydict.values()),
                )
                for k in list(keydict):
                    keycondition = keycondition.replace("%s=" % k, "entity.%s=" % k)
                qry = """
                    SELECT entity.* FROM %s entity, %s baseline
                    WHERE
                        %s
                        AND NOT (%s) AND entity.ce_baseline_id=baseline.cdb_object_id
                    ORDER BY baseline.ce_baseline_cdate DESC"""
                stmt = qry % (
                    obj.GetTableName(),
                    Baseline.GetTableName(),
                    condition,
                    keycondition,
                )
            return obj.SQL(stmt)
        else:
            return []

    @classmethod
    def enhance_search_condition(cls, obj, ctx):
        if cls.check_baseline_support(obj, readonly=True):
            ce_baselines = (
                int(ctx.dialog.ce_baselines)
                if "ce_baselines" in ctx.dialog.get_attribute_names()
                and ctx.dialog.ce_baselines
                else None
            )
        if ce_baselines == 0:
            ctx.set("ce_baseline_id", '=""')
        elif ce_baselines == 1:
            ctx.set("ce_baseline_id", '!=""')
        elif "ce_baselines" in ctx.dialog.get_attribute_names():
            ctx.set("ce_baseline_id", "*")

    @classmethod
    def is_baseline(cls, obj, readonly=True):
        cls.check_baseline_support(obj, readonly=readonly)
        return obj.ce_baseline_id != ""

    @classmethod
    def get_current_obj(cls, baseline_obj):
        """returns only the current object within the same index as baseline_obj"""
        if cls.check_baseline_support(baseline_obj, readonly=True):
            if hasattr(baseline_obj, "ce_baseline_object_id"):
                # if we have it --> use it
                condition = baseline_obj.__table_info__.condition(
                    ["ce_baseline_object_id"], [baseline_obj.ce_baseline_object_id]
                )
                qry = "SELECT entity.* FROM %s entity WHERE %s AND entity.ce_baseline_id=''"
                stmt = qry % (baseline_obj.GetTableName(), condition)
            else:
                keydict = baseline_obj.KeyDict()
                condition = baseline_obj.__table_info__.condition(
                    [x for x in list(keydict) if x != "ce_baseline_id"],
                    [v for (k, v) in keydict.items() if k != "ce_baseline_id"],
                )
                qry = "SELECT entity.* FROM %s entity WHERE %s AND entity.ce_baseline_id=''"
                stmt = qry % (baseline_obj.GetTableName(), condition)
            res = baseline_obj.SQL(stmt)
            if not len(res) == 1:
                raise ValueError("%s %s" % (stmt, res))
            return res[0]
        return None  # no current object

    @classmethod
    def create_baseline_check(cls, obj):
        if cls.is_baseline(obj, readonly=False):
            raise ValueError(
                "Cannot baseline a baseline: '{}'".format(obj.ce_baseline_id)
            )

    @classmethod
    def create_baseline(cls, obj, name=None, comment=None, system=False):
        cls.create_baseline_check(obj)
        with transactions.Transaction():
            LOG.info("Create baseline for %s", obj)
            creator = auth.persno
            now = datetime.datetime.utcnow()
            info_tag = "[{}] ".format(
                name[: min(27, len(name))] if name else now.isoformat().split(".")[0]
            )
            baseline_head_args = dict(
                ce_baseline_creator=creator,
                ce_baseline_name=name,
                ce_baseline_comment=comment,
                ce_baseline_cdate=now,
                ce_baseline_info_tag=info_tag,
                ce_baseline_creation_type=1 if system else 0,
            )
            if hasattr(obj, "cdb_object_id"):
                baseline_head_args["ce_baselined_object_id"] = obj.cdb_object_id
            new_baseline_obj = Baseline.Create(**baseline_head_args)
            new_baseline_head_obj = obj.copy_baseline_elements(
                ce_baseline_id=new_baseline_obj.cdb_object_id,
            )
            return new_baseline_obj, new_baseline_head_obj

    @classmethod
    def restore_baseline(cls, baseline_obj):
        cls.check_baseline_support(baseline_obj)
        if not baseline_obj.ce_baseline_id:
            raise ValueError("Not a baseline")
        current_obj = cls.get_current_obj(baseline_obj)
        if current_obj is None:
            raise ValueError("No current object exist, Baseline cannot be restored")
        with transactions.Transaction():
            LOG.info("Restore baseline  %s", baseline_obj)
            cls.create_baseline(current_obj, system=True)
            # delete current state
            current_obj.remove_all_baseline_elements(ce_baseline_id="")
            # restore baseline state
            new_current_head_obj = baseline_obj.copy_baseline_elements(
                ce_baseline_id="", restore=True
            )
            return new_current_head_obj
