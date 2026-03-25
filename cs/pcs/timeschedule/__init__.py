#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,too-many-lines

import datetime
from calendar import timegm
from collections import defaultdict

from cdb import CADDOK, ElementsError, auth, cmsg, elink, sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.constants import (
    kOperationDelete,
    kOperationModify,
    kOperationNew,
    kOperationSearch,
)
from cdb.elink.engines.chameleon.engine import _OpHelper
from cdb.objects import (
    ByID,
    Forward,
    IconCache,
    Object,
    Reference_1,
    Reference_Methods,
    Reference_N,
    _LabelValueAccessor,
)
from cdb.objects.operations import operation, system_args
from cdb.objects.org import WithSubject
from cdb.platform.mom.fields import DDField
from cdb.platform.olc import StateDefinition
from cdb.util import ErrorMessage, SkipAccessCheck, get_label, nextval
from cdbwrapc import CDBClassDef
from cs.platform.web.uisupport import get_webui_link
from cs.tools.powerreports import MakeReportURL, WithPowerReports
from cs.web.components.ui_support.dialog_hooks import DialogHook

from cs.pcs.projects import Project
from cs.pcs.projects.auto_update_time import AutoUpdateTime
from cs.pcs.projects.chart import ChartConfig
from cs.pcs.projects.common import assert_valid_project_resp, partition
from cs.pcs.projects.common.sharing import WithSharingAndProjectRoles
from cs.pcs.projects.tasks import Task, TaskConstraint, TaskRelation, TaskRelationType
from cs.pcs.helpers import get_dbms_split_count
from cs.pcs.timeschedule.web.models.helpers import get_oid_query_str
from cs.pcs.timeschedule.web.plugins import GET_TABLE_DATA_PLUGINS
from cs.pcs.timeschedule.web.rest_objects import relships2json

fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")
fTimeSchedule = Forward(__name__ + ".TimeSchedule")
fTimeScheduleObject = Forward(__name__ + ".TimeScheduleObject")
fProject2TimeSchedule = Forward(__name__ + ".Project2TimeSchedule")
fColumnDefinition = Forward(__name__ + ".ColumnDefinition")
fColumnFormat = Forward(__name__ + ".ColumnFormat")


class TimeSchedule(WithSubject, WithPowerReports, WithSharingAndProjectRoles):
    __maps_to__ = "cdbpcs_time_schedule"

    # attributes for web models
    schedule_column_group = "gantt"
    schedule_content_table = "cdbpcs_ts_content"
    schedule_content_classname = "cdbpcs_ts_content"
    schedule_setting_id1 = "cs-pcs-timeschedule-web"
    schedule_first_page_size = 100
    schedule_with_baselines = True
    # signal cannot be bound directly to the class

    @property
    def schedule_plugin_signal(self):
        return GET_TABLE_DATA_PLUGINS

    TimeScheduleContents = Reference_N(
        fTimeScheduleObject,
        fTimeScheduleObject.view_oid == fTimeSchedule.cdb_object_id,
        order_by="position",
    )
    Project = Reference_1(fProject, fTimeSchedule.cdb_project_id)
    ReferencedProjects = Reference_N(
        fProject2TimeSchedule,
        fProject2TimeSchedule.time_schedule_oid == fTimeSchedule.cdb_object_id,
    )

    def getLegacyProjectPlanURL(self):
        return f"/powerscript/cs.pcs.timeschedule.new_time_chart/index/{self.cdb_object_id}"

    def getProjectPlanURL(self):
        return get_webui_link(None, self)

    def on_CDBPCS_ProjectPlan_now(self, ctx):
        ctx.url(self.getProjectPlanURL())

    def on_cdbpcs_delete_settings_now(self, ctx):
        self.delete_chart_setting(ctx, persno=auth.persno)

    def _get_selection(self, ctx, catalog_name):
        result = []
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name=catalog_name)
        else:
            result = ctx.catalog_selection
        return result

    def on_cdbpcs_add_project_now(self, ctx):
        for obj in self._get_selection(ctx, "pcs_projects_list_by_id"):
            self._insertObject(fProject.ByKeys(obj.cdb_project_id, obj.ce_baseline_id))

    def on_cdbpcs_add_task_now(self, ctx):
        for obj in self._get_selection(ctx, "pcs_tasks_list_by_uuid"):
            self._insertObject(
                fTask.ByKeys(obj.cdb_project_id, obj.task_id, obj.ce_baseline_id)
            )

    def getNextPosition(self):
        positions = [x.position for x in self.TimeScheduleContents]
        positions.append(0)
        return max(positions) + 1

    def setOrderBy(self, attr):
        def key_func(x):
            return x.getContentObject().getAttributeValue(attr)

        objs = list(self.TimeScheduleContents)
        objs.sort(key=key_func)
        for i, obj in enumerate(objs):
            obj.position = i + 1

    def insertObjects(self, objs):
        for obj in objs:
            self._insertObject(obj)

    def _insertObject(self, obj, unremovable=False):
        if TimeScheduleObject.KeywordQuery(
            view_oid=self.cdb_object_id, content_oid=obj.cdb_object_id
        ):
            return
        kwargs = {}
        kwargs["view_oid"] = self.cdb_object_id
        kwargs["content_oid"] = obj.cdb_object_id
        kwargs["cdb_content_classname"] = obj.GetClassname()
        kwargs["unremovable"] = 1 if unremovable else 0
        TimeScheduleObject.createObject(**kwargs)

    def insertProject(self, ctx):
        if ctx.error:
            return
        if self.Project:
            self.Project.insertIntoTimeSchedule(
                schedule_oid=self.cdb_object_id, unremovable=True
            )
        kwargs = {
            "cdb_project_id": self.cdb_project_id,
            "time_schedule_oid": self.cdb_object_id,
        }
        if ctx.relationship_name == "cdbpcs_project2time_schedule":
            # When the time schedule is created using context of a project,
            # relation ship between project and time schedule will be created by kernel operation
            return
        if not Project2TimeSchedule.ByKeys(**kwargs):
            Project2TimeSchedule.Create(**kwargs)

    def setSubject(self, ctx):
        if not self.subject_id:
            self.subject_id = auth.persno
            self.subject_type = "Person"

    def setProjectID(self, ctx):
        if (
            ctx
            and ctx.parent
            and hasattr(ctx.parent, "cdb_project_id")
            and hasattr(ctx.parent, "ce_baseline_id")
        ):
            self.cdb_project_id = ctx.parent["cdb_project_id"]
            ce_baseline_id = ctx.parent["ce_baseline_id"]
            p = Project.ByKeys(
                cdb_project_id=self.cdb_project_id, ce_baseline_id=ce_baseline_id
            )
            if p:
                ctx.set("project_name", p.project_name)

    def cdbpcs_timeschedule_ganttexport(self, ctx):
        urlstr = MakeReportURL(self, None, "", report_name="ExportGantt")
        url = urlstr[: urlstr.find(" cdb:texttodisplay")]
        ctx.url(url)

    @classmethod
    def createObject(cls, skip_access_check=True, **kwargs):
        return operation(
            kOperationNew,
            TimeSchedule,
            system_args(skip_access_check=skip_access_check),
            **kwargs,
        )

    def checkResponsible(self, ctx):
        if self.cdb_project_id:
            if (
                "skip_access_check" not in ctx.sys_args.get_attribute_names()
                or not ctx.sys_args["skip_access_check"]
            ):
                assert_valid_project_resp(ctx)
        elif self.subject_type == "PCS Role":
            raise ue.Exception("cdbpcs_project_id_needed")

    def delete_chart_setting(self, ctx=None, persno=None):
        chart_configs = None
        if persno:
            chart_configs = ChartConfig.KeywordQuery(
                chart_oid=self.cdb_object_id, persno=persno
            )
        else:
            chart_configs = ChartConfig.KeywordQuery(chart_oid=self.cdb_object_id)
        for config in chart_configs:
            operation(kOperationDelete, config)

    def reveal_tso_in_schedule(self, obj, keep_old_expanded_ids):
        expanded_ids = ChartConfig.getSetting(
            auth.persno, self.cdb_object_id, setting_name="#expandedId#"
        )
        lvl0_tsos_ids = [tso.content_oid for tso in self.TimeScheduleContents]
        expanded_ids_2_add = []
        obj = obj.getParentObject()
        while obj:
            if obj.cdb_object_id not in expanded_ids:
                expanded_ids_2_add.append(obj.cdb_object_id)
            if obj.cdb_object_id in lvl0_tsos_ids:
                break
            if keep_old_expanded_ids and obj.cdb_object_id in expanded_ids:
                break
            new_obj = obj.getParentObject()
            if not new_obj:
                # add obj to ts-objects
                kwargs = {
                    "view_oid": self.cdb_object_id,
                    "content_oid": obj.cdb_object_id,
                    "cdb_content_classname": obj.GetClassname(),
                    "cdb_project_id": obj.cdb_project_id,
                }
                try:
                    operation(kOperationNew, TimeScheduleObject, **kwargs)
                except (ValueError, ElementsError) as e:
                    return {"error": str(ErrorMessage("just_a_replacement", f"{e}"))}
            obj = new_obj
        new_expanded_ids = expanded_ids_2_add
        if keep_old_expanded_ids:
            new_expanded_ids += expanded_ids
        ChartConfig.setSetting(
            auth.persno,
            self.cdb_object_id,
            new_expanded_ids,
            setting_name="#expandedId#",
        )

    def _fully_expand_tso_in_schedule(self, obj, expanded_ids):
        children = obj.getChildrenObjects()
        if children:
            if obj.cdb_object_id not in expanded_ids:
                expanded_ids.append(obj.cdb_object_id)
            for child in children:
                expanded_ids = self._fully_expand_tso_in_schedule(child, expanded_ids)
        return expanded_ids

    def fully_expand_tso_in_schedule(self, obj):
        expanded_ids = ChartConfig.getSetting(
            auth.persno, self.cdb_object_id, setting_name="#expandedId#"
        )
        expanded_ids = self._fully_expand_tso_in_schedule(obj, expanded_ids)
        ChartConfig.setSetting(
            auth.persno, self.cdb_object_id, expanded_ids, setting_name="#expandedId#"
        )

    event_map = {
        (("create"), "pre_mask"): ("setSubject", "setProjectID"),
        (("create", "copy", "modify"), "pre"): ("checkResponsible"),
        (("create"), "post"): ("insertProject"),
        (("cdbpcs_timeschedule_ganttexport"), "now"): (
            "cdbpcs_timeschedule_ganttexport"
        ),
        (("delete"), "post"): ("delete_chart_setting"),
    }

    # methods for web models

    def schedule_get_data(self, result, _):
        # time schedule extensions to generic data

        if "relships" not in result:
            return {"relships": []}

        return {
            "constraintTypes": self._schedule_get_constraint_types(),
            "ratingIDMapping": self._schedule_get_rating_names(),
            "daytimeMapping": self._schedule_get_daytime_names(),
        }

    def schedule_get_full_data(self, oids, request):
        return {
            "relships": self._schedule_resolve_relships(oids),
            "auto_update_time": AutoUpdateTime.GetMapping(),
        }

    def _schedule_get_rating_names(self):
        """
        :returns: rating names in login language (fallback english)
            indexed by IDs.
        :rtype: dict
        """
        rating_id = f"rating_value_{CADDOK.ISOLANG}"

        def get_name(rating):
            return getattr(rating, rating_id) or rating.rating_value_en

        return {
            x.rating_id: get_name(x)
            for x in sqlapi.RecordSet2(
                "cdbpcs_rat_val_lights",
                access="read",
            )
        }

    def _schedule_get_daytime_names(self):
        """
        :returns: daytime names in login language (fallback english)
            indexed by IDs.
        :rtype: dict
        """
        daytime_id = f"daytime_value_{CADDOK.ISOLANG}"

        def get_name(daytime):
            return getattr(daytime, daytime_id) or daytime.daytime_value_en

        return {
            x.daytime_id: get_name(x)
            for x in sqlapi.RecordSet2(
                "cdbpcs_daytime_options",
                access="read",
            )
        }

    def _schedule_get_constraint_types(self):
        """
        :returns: Constraint type names in login language (fallback english)
            indexed by IDs.
        :rtype: dict
        """
        name = f"name_{CADDOK.ISOLANG}"

        def get_name(constraint):
            return getattr(constraint, name) or constraint.name_en

        return {
            x.constraint_id: get_name(x)
            for x in sqlapi.RecordSet2(
                "cdbpcs_task_constraint",
                access="read",
            )
        }

    def _schedule_resolve_relships(self, oids):
        """
        :param oids: cdb_object_ids to query relationships with.
        :type oids: list of str

        :returns: all relationship values where given ``oids`` overlap with
            either the predecessor or successor task cdb_object_ids. Values
            only contain a subset of the database fields used in the frontend.
        :rtype: list of dict
        """
        rset = sqlapi.RecordSet2(
            "cdbpcs_taskrel",
            f"{get_oid_query_str(oids, 'pred_task_oid')} OR "
            f"{get_oid_query_str(oids, 'succ_task_oid')}",
            access="read",
        )
        return relships2json(rset)


class TimeScheduleObject(Object):
    __maps_to__ = "cdbpcs_ts_content"

    TimeSchedule = Reference_1(fTimeSchedule, fTimeScheduleObject.view_oid)

    def getContentObject(self):
        return ByID(self.content_oid)

    def initPosition(self):
        self.position = self.TimeSchedule.getNextPosition()

    def resetPosition(self):
        pos = self.position
        to_change = [
            x
            for x in self.TimeSchedule.TimeScheduleContents
            if x.content_oid != self.content_oid
        ]
        to_change = [x for x in to_change if x.position >= pos]
        for obj in to_change:
            pos = pos + 1
            obj.position = pos

    def onCreatePreMask(self, ctx):
        self.initPosition()

    def onCreatePre(self, ctx):
        if not self.position:
            self.initPosition()
        if isinstance(ctx.dragdrop_op_count, int) and ctx.dragdrop_op_count > 0:
            if hasattr(ctx.dragged_obj, "succ_task_oid"):
                self.insertTasksByTaskRelation(ctx)

    def insertTasksByTaskRelation(self, ctx):
        pred_task_oid = ctx.dragged_obj["pred_task_oid"]
        succ_task_oid = ctx.dragged_obj["succ_task_oid"]
        view_oid = ctx.parent["cdb_object_id"]

        if (
            len(
                TimeScheduleObject.KeywordQuery(
                    view_oid=view_oid, content_oid=succ_task_oid
                )
            )
            == 0
        ):
            if len(
                TimeScheduleObject.KeywordQuery(
                    view_oid=view_oid, content_oid=pred_task_oid
                )
            ):
                self.content_oid = succ_task_oid
            else:
                kwargs = {}
                kwargs["view_oid"] = view_oid
                kwargs["content_oid"] = succ_task_oid
                kwargs["cdb_content_classname"] = ctx.dialog["cdb_content_classname"]
                kwargs["position"] = self.position + 1
                TimeScheduleObject.createObject(**kwargs)

    @classmethod
    def createObject(cls, **kwargs):
        operation(kOperationNew, TimeScheduleObject, **kwargs)

    def setProjectID(self):
        content_obj = self.getContentObject()
        if hasattr(content_obj, "getAttributeValue"):
            content_project_id = content_obj.getAttributeValue("cdb_project_id")
        else:
            content_project_id = getattr(content_obj, "cdb_project_id", "")

        self.getPersistentObject().cdb_project_id = content_project_id

    def onModifyPost(self, ctx):
        self.resetPosition()
        self.setProjectID()

    def onCreatePost(self, ctx):
        self.setProjectID()

    def onCopyPost(self, ctx):
        self.setProjectID()

    event_map = {
        (("modify"), "post"): "onModifyPost",
        (("create"), "pre"): "onCreatePre",
        (("create"), "pre_mask"): "onCreatePreMask",
        (("create"), "post"): "onCreatePost",
        (("copy"), "post"): "onCopyPost",
    }


class Project2TimeSchedule(Object):
    __maps_to__ = "cdbpcs_project2time_schedule"

    Project = Reference_1(fProject, fProject2TimeSchedule.cdb_project_id)
    TimeSchedule = Reference_1(fTimeSchedule, fProject2TimeSchedule.time_schedule_oid)


class WithTimeScheduleContent:
    def _getTimeScheduleObjects(self):
        return TimeScheduleObject.KeywordQuery(content_oid=self.cdb_object_id)

    TimeScheduleObjects = Reference_Methods(
        TimeScheduleObject, lambda self: self._getTimeScheduleObjects()
    )

    def _getTimeSchedules(self):
        return [x.TimeSchedule for x in self._getTimeScheduleObjects()]

    TimeSchedules = Reference_Methods(
        TimeSchedule, lambda self: self._getTimeSchedules()
    )

    def _id_list_to_id_string(self, ids):
        if not ids:
            return ""
        if not isinstance(ids, list):
            ids = [ids]
        return ", ".join([f"'{x}'" for x in ids])

    def _getPersonOIDs(self, persno=None):
        ids = self._id_list_to_id_string(persno)
        if not ids:
            return []
        sql = f"SELECT cdb_object_id FROM angestellter WHERE personalnummer IN ({ids})"
        result = sqlapi.RecordSet2(sql=sql)
        return [x["cdb_object_id"] for x in result]

    def _getOrgOIDs(self, org_ids=None):
        ids = self._id_list_to_id_string(org_ids)
        if not ids:
            return []
        sql = f"SELECT cdb_object_id FROM cdb_org WHERE org_id IN ({ids})"
        result = sqlapi.RecordSet2(sql=sql)
        return [x["cdb_object_id"] for x in result]

    def getRelationURL(self, search_predecessors=True):
        clsdef = CDBClassDef(TaskRelation._getClassname())
        clsname = clsdef.getClassname()
        msg = cmsg.Cdbcmsg(clsname, kOperationSearch, False)
        args = {}
        if hasattr(self, "cdb_project_id") and hasattr(self, "task_id"):
            if search_predecessors:
                args["cdb_project_id"] = self.cdb_project_id
                args["task_id"] = self.task_id
            else:
                args["cdb_project_id2"] = self.cdb_project_id
                args["task_id2"] = self.task_id
        for k, v in args.items():
            msg.add_item(f"{k}", clsdef.getPrimaryTable(), f"{v}")
        return msg.eLink_url(0)

    def on_cdbpcs_ts_add_obj_pre_mask(self, ctx):
        if not TimeSchedule.Query():
            name = (
                "CDBPCS_VIEW_"
                + auth.persno
                + "_"
                + f"{nextval('CDBPCS_VIEW_' + auth.persno)}"
            )
            operation(kOperationNew, TimeSchedule, name=name)

    def on_cdbpcs_ts_add_obj_now(self, ctx):
        if "time_schedule" in ctx.dialog.get_attribute_names():
            self.insertIntoTimeSchedule(ctx.dialog["time_schedule"])

    def getAllTimeScheduleObjects(self):
        return [self]

    def insertCompleteIntoSchedule(self, schedule_oid):
        ts = TimeSchedule.ByKeys(cdb_object_id=schedule_oid)
        if ts:
            ts.insertObjects(self.getAllTimeScheduleObjects())
            ts.setOrderBy("psp_code")

    def insertIntoTimeSchedule(self, schedule_oid, unremovable=False):
        ts = TimeSchedule.ByKeys(cdb_object_id=schedule_oid)
        if ts:
            ts._insertObject(obj=self, unremovable=unremovable)

    def delete_chart_setting(self, ctx=None):
        chart_configs = ChartConfig.KeywordQuery(attr=self.cdb_object_id)
        for config in chart_configs:
            operation(kOperationDelete, config)

    def hasChildren(self):
        return False

    # getter functions
    def getAttributeValue(self, attr_name, default=""):
        try:
            return self._getValue(self[attr_name], default=default)
        except AttributeError:
            return default

    def _getValue(self, val, default=""):
        if isinstance(val, (str, float, datetime.date, datetime.datetime, int)):
            return val
        return default

    def getObjectPermission(self):
        return self.CheckAccess("save", auth.persno)

    def getFieldAccess(self, has_licence=False, permission=False):
        if not has_licence:
            return defaultdict(lambda: False)
        d = defaultdict(lambda: permission)
        if hasattr(self, "getReadOnlyFields"):
            for f in self.getReadOnlyFields(avoid_check=True):
                d[f] = False
        return d

    def getProject(self):
        prj_id = self.getProjectID()
        baseline_id = self.getBaselineID()
        if prj_id and baseline_id:
            return Project.ByKeys(cdb_project_id=prj_id, ce_baseline_id=baseline_id)
        return None

    def getPredecessorRelations(self):
        return []

    def getSuccessorRelations(self):
        return []

    def getResponsibleIDs(self):
        "Returns the id (personalnummer) of all persons that are responsible"
        return []

    def getResponsibleNames(self):
        "Returns the names of all persons that are responsible"
        ids = self.getResponsibleIDs()
        if not ids:
            return []
        id_str = ", ".join(f"'{x}'" for x in ids)
        sql = f"""SELECT name FROM angestellter WHERE personalnummer IN ({id_str}) ORDER BY name"""
        result = sqlapi.RecordSet2(sql=sql)
        return [r["name"] for r in result]

    def getStateColor(self):
        color = self._getObjectStateColor()
        if color:
            return color
        return (255, 255, 255)

    def _getSignal(self, icon_id):
        return IconCache.getIcon(icon_id, None, _LabelValueAccessor(self, True))

    def getEffortSignalIcon(self):
        if not self.getAttributeValue("status_effort_fcast"):
            return None
        return self._getSignal("cdbpcs_status_effort_fcast")

    def getEffortSignalDescription(self):
        return ""

    def getTimeSignalIcon(self):
        if not self.getAttributeValue("status_time_fcast"):
            return None
        return self._getSignal("cdbpcs_status_time_fcast")

    def getOverdueIcon(self):
        return None

    def getTimeSignalDescription(self):
        return ""

    def getOverdueDescription(self):
        return ""

    def getTotalSignalIcon(self):
        if not self.getAttributeValue("rating"):
            return None
        return self._getSignal("cdbpcs_man_rating")

    def getTotalSignalDescription(self):
        return self.getAttributeValue("rating_descr")

    def getBarDescription(self):
        return self.GetDescription()

    @classmethod
    def getDoubleClickOperation(cls):
        return "CDB_Modify"

    def getDoubleClickURL(self, base_url):
        """
        :param base_url: Base URL for legacy links (unused if the request
            comes from a web client)
        :type base_url: basestring

        :returns: A URL linking to ``self``. If the request comes from a cdbpc
            client, a legacy URL based on ``base_url`` is returned. Else, the
            cs.web URL pointing the ``self``'s object page is returned.
        :rtype: basestring
        """
        if elink.isCDBPC():
            classname = self._getClassname()
            url_suffix = TSHelper._get_url_suffix(
                self, classname
            )  # pylint: disable=W0212
            return base_url + url_suffix
        else:
            return get_webui_link(None, self)

    def getChildrenObjects(self):
        return []

    def getParentObject(self):
        return None

    def getEarlyStart(self):
        return ""

    def getEarlyFinish(self):
        return ""

    def getLateStart(self):
        return ""

    def getLateFinish(self):
        return ""

    def isMilestone(self):
        return False

    def getName(self):
        return self.GetDescription()

    def getSubjectTooltip(self):
        return self.getSubject()

    def getSubject(self):
        return self.getAttributeValue("subject_id")

    def getResourceOIDs(self):
        # resources that shall be inserted into the resource chart
        # because they might handle the realization of the TS-object
        return self.getAssignedOIDs()

    def getAssignedOIDs(self):
        # return id of resources that are scheduled for realization of the TS-object
        # overwritten within resource module
        return []

    def getRealizationBy(self):
        return ""

    def getPosition(self):
        return self.getAttributeValue("position")

    def getProjectID(self):
        return self.getAttributeValue("cdb_project_id")

    def getBaselineID(self):
        return self.getAttributeValue("ce_baseline_id")

    def getProjectName(self):
        return self.getAttributeValue("project_name")

    def getCompletion(self):
        return self.getAttributeValue("percent_complet", 0)

    def getStartTimeFcast(self):
        return self.getAttributeValue("start_time_fcast")

    def getEndTimeFcast(self):
        return self.getAttributeValue("end_time_fcast")

    def getDaysFcast(self):
        days = self.getAttributeValue("days_fcast")
        return days if days else 0

    def getStartTimePlan(self):
        return self.getAttributeValue("start_time_plan")

    def getEndTimePlan(self):
        return self.getAttributeValue("end_time_plan")

    def getDays(self):
        return self.getAttributeValue("days")

    def getStartTimeAct(self):
        return self.getAttributeValue("start_time_act")

    def getEndTimeAct(self):
        return self.getAttributeValue("end_time_act")

    def getEffortFcast(self):
        return self.getAttributeValue("effort_fcast")

    def getEffortPlan(self):
        return self.getAttributeValue("effort_plan")

    def getEffortAct(self):
        return self.getAttributeValue("effort_act")

    def getEffortDemand(self):
        return self.getAttributeValue("effort_fcast_d")

    def getEffortAssignment(self):
        return self.getAttributeValue("effort_fcast_a")

    def getPlanningStatus(self):
        return self.getAttributeValue("planning_status")

    # setter functions
    def prepare_change_control_attributes(self, ctx, **kwargs):
        change_args = self.MakeChangeControlAttributes()
        # in the context of a hook, only set cdb_adate, cdb_apersno if
        # they're present on the mask
        if isinstance(ctx, DialogHook):
            hook_values = ctx.get_new_values()
            classname = self.GetClassname()
            enhanced_apersno_key = ".".join([classname, "cdb_apersno"])
            enhanced_adate_key = ".".join([classname, "cdb_adate"])
            if enhanced_apersno_key in hook_values:
                kwargs["cdb_apersno"] = change_args["cdb_mpersno"]
            if enhanced_adate_key in hook_values:
                kwargs["cdb_adate"] = change_args["cdb_mdate"]
        # in the context of an object, only set cdb_adate, cdb_apersno if
        # the object has these attributes
        else:
            if hasattr(self, "cdb_apersno"):
                kwargs["cdb_apersno"] = change_args["cdb_mpersno"]
            if hasattr(self, "cdb_adate"):
                kwargs["cdb_adate"] = change_args["cdb_mdate"]
        return kwargs

    def updateObject(self, ctx=None, **kwargs):
        self.Update(**self.prepare_change_control_attributes(ctx, **kwargs))

    def update_object_web(self, hook, **kwargs):
        constraint_name = ""
        if "constraint_type" in kwargs:
            constraint_name = TaskConstraint.ByKeys(
                constraint_id=kwargs["constraint_type"]
            ).name
        enhanced_kwargs = self.prepare_change_control_attributes(hook, **kwargs)
        for k, v in enhanced_kwargs.items():
            key = f"{self.__maps_to__}.{k}"
            if k == "constraint_type":
                hook.set(
                    f".mapped_constraint_type_name_{CADDOK.ISOLANG}", constraint_name
                )
            hook.set(key, v)

    def setAttributeValues(self, ctx=None, **kwargs):
        if (
            not self.__class__.ByKeys(**self.KeyDict())
            or ctx
            and (isinstance(ctx, DialogHook) or ctx.mode in ["dialogitem_change"])
        ):
            if isinstance(ctx, DialogHook):
                self.update_object_web(ctx, **kwargs)
            else:
                self.updateObject(ctx, **kwargs)
        else:
            with SkipAccessCheck():
                operation(kOperationModify, self.getPersistentObject(), **kwargs)
            self.Reload()

    def setName(self, name):
        pass

    def setNewPosition(self, pos):
        pass

    def setEarlyPosition(self, pos):
        pass

    def setDaysFcast(self, ctx=None, days=None):
        """
        Adjusts the duration of the period. The start date is retained
        and the end date is adjusted. If no duration value is given,
        the start and end date are also cleared.

        :param ctx: context
        :param days: workdays as integer
        """
        if not (days is None or days == ""):
            days = TSHelper.positive_int(val=days)
            self.setTimeframe(ctx=ctx, start=self.getStartTimeFcast(), days=days)
        else:
            self.setTimeframe(ctx=ctx)

    def setStartTimeFcastByBar(self, ctx=None, start=None):
        """
        Adjusts the start date. This method keeps the end date and adjusts
        the duration of the period instead.

        :param ctx: context
        :param start: datetime
        """
        constraints = self._determineConstraints(start=start)
        if start:
            self.setTimeframe(
                ctx=ctx, start=start, end=self.getEndTimeFcast(), **constraints
            )
        else:
            self.setTimeframe(ctx=ctx, **constraints)

    def setStartTimeFcast(self, ctx=None, start=None):
        """
        Adjusts the start date. In this method, the duration is adjusted
        if the constraint type limits the end date.
        If the end date is not restricted, the duration is retained and the
        end date is adjusted.

        :param ctx: context
        :param start: datetime
        """
        # table set start
        constraints = self._determineConstraints(start=start)
        if hasattr(self, "constraint_type") and int(self.constraint_type) in [3, 6, 7]:
            end = self.getEndTimeFcast()
            self.setTimeframe(ctx=ctx, start=start, end=end, **constraints)
        else:
            days = self.getDaysFcast()
            if start and not days:
                days = 1
            self.setTimeframe(ctx=ctx, start=start, days=days, **constraints)

    def setEndTimeFcastByBar(self, ctx=None, end=None):
        """
        Adjusts the end date. This method keeps the start date and adjusts
        the duration of the period instead.

        :param ctx: context
        :param end: datetime
        """
        constraints = self._determineConstraints(end=end)
        if end:
            self.setTimeframe(
                ctx=ctx, start=self.getStartTimeFcast(), end=end, **constraints
            )
        else:
            self.setTimeframe(ctx=ctx)

    def setEndTimeFcast(self, ctx=None, end=None):
        """
        Adjusts the end date. In this method, the duration is adjusted
        if a start date already exists. If the start date does not exist,
        the duration is retained and the start date is set instead.

        :param ctx: context
        :param end: datetime
        """
        # table set end
        if self.isMilestone():
            constraints = self._determineConstraints(constraint_date=end)
            self.setTimeframe(ctx=ctx, start=end, end=end, days=0, **constraints)
        else:
            start = self.getStartTimeFcast()
            if not start or not end:
                start = end
            if end:
                constraints = self._determineConstraints(end=end)
                self.setTimeframe(ctx=ctx, start=start, end=end, **constraints)
            else:
                constraints = self._determineConstraints(constraint_date=end)
                days = self.getDaysFcast()
                self.setTimeframe(ctx=ctx, end=end, days=days, **constraints)

    def moveTimeframePlan(self, start=None, end=None):
        pass

    def moveTimeframe(self, ctx=None, start=None, end=None):
        """
        Moves the period of the object as a whole.
        If it is a task, the system assesses whether the start date
        or the end date is used for the calculation,
        depending on the constraint type.

        :param ctx: context
        :param start: datetime.date
        :param end: datetime.date
        """
        if self.isMilestone():
            constraints = self._determineConstraints(constraint_date=end)
            self.setTimeframe(ctx=ctx, start=end, end=end, days=0, **constraints)
        else:
            constraints = self._determineConstraints(start=start, end=end)
            days = self.getDaysFcast()
            if not hasattr(self, "constraint_type"):
                self.setTimeframe(ctx=ctx, start=start, days=days)
            elif int(self.constraint_type) in [0, 2, 4, 5]:
                self.setTimeframe(ctx=ctx, start=start, days=days, **constraints)
            elif int(self.constraint_type) in [1, 3, 6, 7]:
                self.setTimeframe(ctx=ctx, end=end, days=days, **constraints)

    def setEffortFcast(self, effort):
        pass

    def setEffortAct(self, effort):
        pass

    def setEffortDemand(self, effort):
        pass

    def setEffortAssignment(self, effort):
        pass

    def setAutomatic(self, auto):
        pass

    def setAutoUpdateTime(self, auto):
        pass

    def setConstraint(self, constraint_date=None):
        pass

    def _determineConstraints(
        self, constraint_date=None, start=None, end=None, forced=False
    ):
        return {}

    def getCustomBarClass(self):
        return ""

    def isDiscarded(self):
        return False

    def get_grafic_types(self):
        return {
            "class_name": self.GetClassname(),
            "displayPlanBar": False,
            "drawBold": False,
            "hasRelations": False,
        }

    def get_psp_code(self):
        return self.getPSPCode() if hasattr(self, "getPSPCode") else ""

    @classmethod
    def _getTSPredRelsPerClass(cls, objs):
        return [[] for x in range(len(objs))]

    @classmethod
    def _getTSSuccRelsPerClass(cls, objs):
        return [[] for x in range(len(objs))]

    @classmethod
    def _getPlanningStatusPerClass(cls, objs):
        return [obj.getPlanningStatus() for obj in objs]

    @classmethod
    def getTSFieldsPerClass(cls, objs):
        classname = cls._getClassname()
        base_dblclck_url = _OpHelper.get_class_operations(
            [cls.getDoubleClickOperation()], classname
        )[0]["url"]
        pred_rels = cls._getTSPredRelsPerClass(objs)
        succ_rels = cls._getTSSuccRelsPerClass(objs)
        planning_statuses = cls._getPlanningStatusPerClass(objs)
        result = []
        for index, obj in enumerate(objs):
            mo_url = obj.getDoubleClickURL(base_dblclck_url)
            result.append(
                {
                    "modifyOperationUrl": mo_url,
                    "predecessors_relations": pred_rels[index],
                    "successors_relations": succ_rels[index],
                    "planning_status": planning_statuses[index],
                }
            )
        return result

    def getTSFieldsPerObject(self, has_licence, asynchronous):
        data = self.getTSFieldsSync()
        if asynchronous:
            # load defaults and load the rest async later
            data.update(self.getTSFieldsAsyncDefaults())
        else:
            data.update(self.getTSFieldsAsync(has_licence))
        return data

    def getTSFieldsSync(self):
        pcs_hours_label = get_label("pcs_hour")
        result = {
            "is_group": self.getAttributeValue("is_group"),
            "hasChildren": self.hasChildren(),
            "objCdbObjectId": self.cdb_object_id,
            "isMilestone": self.isMilestone(),
            # compute start and end dates in the table from timestamp dates below (SSOT + computed properties)
            # chart
            "customBarClass": self.getCustomBarClass(),
            "early_start": TSHelper.date2utc(self.getEarlyStart()),
            "late_finish": TSHelper.date2utc(self.getLateFinish()),
            "percentComplete": self.getCompletion(),
            # tooltip
            "valueDemand": f"{self.getEffortDemand()} {pcs_hours_label}",
            "valueAssignment": f"{self.getEffortAssignment()}" + " " + pcs_hours_label,
            "isDiscarded": self.isDiscarded(),
            "barDescription": self.getBarDescription(),
        }
        result.update(self.get_grafic_types())
        if hasattr(self, "task_id"):
            result["task_id"] = self.task_id
        return result

    def getTSFieldsAsyncDefaults(self):
        editable_keys = [
            "isTitleEditable",
            "isPositionEditable",
            "isDurationEditable",
            "isEffortEditable",
            "isEffortActEditable",
            "isEffortDemandEditable",
            "isEffortAssignmentEditable",
            "isStartEditable",
            "isEndEditable",
            "dragableFcast",
            "dragablePlan",
            "resizableFcast",
            "isEarlyPositionVisible",
            "isEarlyPositionEditable",
            "isAutomaticVisible",
            "isAutomaticEditable",
            "isConstraintDateEditable",
            "isStartHidden",
            "isEndHidden",
            "end_plan_fix",
            "objPermission",
            "isAutoUpdateTimeVisible",
            "isAutoUpdateTimeEditable",
        ]
        data = dict.fromkeys(editable_keys, False)
        return data

    def getTSFieldsAsync(self, has_licence):
        # per class implementation
        return {}

    # timeschedule columns getters
    @classmethod
    def get_ts_col_val_status_color(cls, objs, obj_id_2_tso):
        # optimized self.getStateColor
        olcs = list({obj.GetObjectKind() for obj in objs})
        colors_for_state_dict = {}
        desc_for_sdfs_dict = {}
        for olc in olcs:
            colors_for_state_dict[olc] = {}
            colors_for_state = sqlapi.RecordSet2(
                sql="SELECT o.statusnummer, f.* "
                "FROM objektstati o "
                "INNER JOIN farben f "
                "ON o.statusfarbe=f.bezeichnung "
                f"WHERE  o.objektart='{olc}'"
            )
            for cs in colors_for_state:
                colors_for_state_dict[olc][cs.statusnummer] = (
                    cs.rot_anteil,
                    cs.gruen_anteil,
                    cs.blau_anteil,
                )
            state_defs = StateDefinition.Query(f"objektart='{olc}'")
            desc_for_sdfs_dict[olc] = {}
            for sd in state_defs:
                desc_for_sdfs_dict[olc][sd.statusnummer] = sd.StateText[""]
        classname = cls._getClassname()
        base_url = None
        if elink.isCDBPC():
            op = _OpHelper.get_class_operations(["CDB_Workflow"], classname)
            base_url = op[0]["url"] if len(op) else None
        result = []
        for obj in objs:
            olc = obj.GetObjectKind()
            if len(colors_for_state_dict[olc]) and len(desc_for_sdfs_dict[olc]):
                url = ""
                if base_url:
                    url = base_url + TSHelper._get_url_suffix(obj, classname)
                result.append(
                    {
                        # pylint: disable-next=consider-using-f-string
                        "style": "background-color: #%02X%02X%02X;"
                        % (colors_for_state_dict[olc][obj.status]),
                        "url": url,
                        "description": desc_for_sdfs_dict[olc][obj.status],
                    }
                )
            else:
                result.append({"style": "", "url": "", "description": ""})
        return result

    @classmethod
    def get_ts_col_val_operations(cls, objs, obj_id_2_tso):
        not_web_context = elink.isCDBPC()
        classname = cls._getClassname()
        ops = _OpHelper.get_class_operations_for_context(
            classname, "pcs_timeschedule_items"
        )
        result = []
        for obj in objs:
            ops_arr = []
            url_suffix = TSHelper._get_url_suffix(obj, classname)
            for op in ops:
                if not_web_context and "CE_ShowObjectPage" not in op["url"]:
                    ops_arr.append(TSHelper.get_op_info(op, url_suffix))
            result.append(ops_arr)
        return result

    def deleteTimeScheduleObjects(self, ctx=None):
        for tso in self.TimeScheduleObjects:
            tso.Delete()

    def get_object_description(self):
        return ""

    event_map = {
        (("delete"), "post"): ("delete_chart_setting", "deleteTimeScheduleObjects")
    }


@classbody
class Project(WithTimeScheduleContent):

    PrimaryTimeSchedule = Reference_N(
        fTimeSchedule, fTimeSchedule.cdb_project_id == fProject.cdb_project_id
    )

    def on_CDBPCS_ProjectPlan_now(self, ctx):
        if not ctx.uses_webui:
            ts = self.getPrimaryTimeSchedule(ctx=ctx)
            if ts:
                if ts.CheckAccess("read", auth.persno):
                    ctx.url(ts.getProjectPlanURL())
                else:
                    raise ue.Exception("cdbpcs_operation_access")

    def getPrimaryTimeSchedule(self, ctx=None):
        if len(self.PrimaryTimeSchedule) == 1:
            return self.PrimaryTimeSchedule[0]
        if ctx:
            if not ctx.catalog_selection:
                kwargs = {"cdb_project_id": self.cdb_project_id}
                ctx.start_selection(catalog_name="cdbpcs_ts_catalog2", **kwargs)
            else:
                return ByID(ctx.catalog_selection[0]["cdb_object_id"])
        return None

    def createTimeSchedule(self, ctx, skip_access_check=True):
        """
        Creates a time schedule for the current project using kernel operation.
        Usually, the method is only used if the time schedule is created in the
        context of the creation of a new project. Therefore, we can deactivate the
        access check by default. If the method is used in a different context,
        the access check can be activated.

        .. warning ::

            If this project's roles and team are not set up yet
            (e.g. the logged-in user is not part of the team),
            `cs.pcs.projects.common.assert_valid_project_resp` will fail.

        :param ctx: unused
        :param skip_access_check: controls the access check
                                  Default: Access check is skipped because
                                  the call from the event map
                                  can not be parameterized (E041003)
        :return: cs.pcs.timeschedule.Timeschedule
        """
        kwargs = {
            "cdb_project_id": self.cdb_project_id,
            "name": self.project_name,
            "subject_id": self.project_manager,
            "subject_type": "Person",
            "cdb_objektart": TimeSchedule._getClassname(),
        }
        if skip_access_check:
            with SkipAccessCheck():
                return TimeSchedule.createObject(skip_access_check, **kwargs)
        return TimeSchedule.createObject(**kwargs)

    def createTimeScheduleConnection(self, ctx):
        for ps in self.PrimaryTimeSchedule:
            kwargs = {
                "cdb_project_id": self.cdb_project_id,
                "time_schedule_oid": ps.cdb_object_id,
            }
            if not Project2TimeSchedule.ByKeys(**kwargs):
                Project2TimeSchedule.Create(**kwargs)

    def getAllTimeScheduleObjects(self):
        return [self] + list(self.AllTasksByOrder)

    def hasChildren(self):
        return self.is_group or len(self.Subprojects) > 0

    @classmethod
    def _getPlanningStatusPerClass(cls, objs):
        return TSHelper.get_virtual_attr_for_objs(cls, objs, "planning_status")

    # getter functions
    def getName(self):
        return self.project_name

    def getSubject(self):
        return self.getProjectManagerName()

    def getResponsibleIDs(self):
        return self.getResponsiblePersons()

    def getProject(self):
        # otherwise this won't work in a "create" UE
        return self

    def setAutoUpdateTime(self, auto):
        self.setAttributeValues(auto_update_time=auto)

    def getChildrenObjects(self):
        return self.OrderedSubProjects + self.TopTasks

    def getParentObject(self):
        return self.getParent()

    # editable functions
    def getTSFieldsAsync(self, has_licence):
        obj_permission = self.getObjectPermission()
        field_access = self.getFieldAccess(
            has_licence=has_licence, permission=obj_permission
        )
        isStartEditable = field_access["start_time_fcast"]
        isEndEditable = field_access["end_time_fcast"]
        # editable stuff
        data = {
            "isTitleEditable": field_access["project_name"],
            "isPositionEditable": field_access["position"],
            "isDurationEditable": (isEndEditable and field_access["days_fcast"]),
            "isEffortEditable": field_access["effort_fcast"],
            "isEffortActEditable": field_access["effort_act"],
            "isAutoUpdateTimeVisible": True,
            "isAutoUpdateTimeEditable": field_access["auto_update_time"],
            "isStartEditable": isStartEditable,
            "isEndEditable": isEndEditable,
            "dragableFcast": isStartEditable and isEndEditable,
            "dragablePlan": isStartEditable or isEndEditable,
            "resizableFcast": isStartEditable or isEndEditable,
            "end_plan_fix": 0,
            "objPermission": obj_permission,
        }
        # other expensive fields
        data.update({"responsible_oids": self.getResourceOIDs()})
        return data

    def isDiscarded(self):
        return self.status == 180

    def get_grafic_types(self):
        return {
            "class_name": "cdbpcs_project",
            "displayPlanBar": self.hasChildren(),
            "drawBold": True,
            "hasRelations": False,
        }

    def get_object_description(self):
        if self.parent_project:
            return get_label("pcs_subproject")
        return get_label("cdbpcs_project")

    # setter functions
    def setName(self, name):
        self.updateObject(project_name=name)

    def setNewPosition(self, pos):
        self.updateObject(position=pos)

    def setEffortFcast(self, effort):
        effort = TSHelper.positive_float(val=effort)
        if not self.is_group:
            self.setAttributeValues(effort_fcast=effort, effort_plan=effort)
        elif not self.auto_update_effort:
            self.setAttributeValues(effort_fcast=effort)

    def setEffortAct(self, effort):
        effort = TSHelper.positive_float(val=effort)
        self.setAttributeValues(effort_act=effort)

    def setEffortDemand(self, effort):
        effort = TSHelper.positive_float(val=effort)
        sig.emit(Project, "adjust_effort_fcast_d")(self, effort=effort)

    def setEffortAssignment(self, effort):
        effort = TSHelper.positive_float(val=effort)
        sig.emit(Project, "adjust_effort_fcast_a")(self, effort=effort)

    def getCustomBarClass(self):
        return "thick-bar"

    def deleteTimeScheduleObjects(self, ctx=None):
        # first remove the own id from all primary time schedules
        for ts in self.PrimaryTimeSchedule:
            ts.cdb_project_id = ""
        # removing all tasks from time schedules
        if "_all_task_ids_" in ctx.ue_args.get_attribute_names():
            all_tasks_tsos = fTimeScheduleObject.KeywordQuery(
                content_oid=ctx.ue_args._all_task_ids_.split(";")
            )
            all_tasks_tsos.Delete()
        self.TimeScheduleObjects.Delete()

    def keepTaskIds(self, ctx):
        ctx.keep("_all_task_ids_", ";".join(self.AllTasks.cdb_object_id))

    event_map = {
        (("create", "copy"), "post"): (
            "createTimeSchedule",
            "createTimeScheduleConnection",
        ),
        (("delete"), "pre"): ("keepTaskIds"),
    }


@classbody
class Task(WithTimeScheduleContent):
    def on_CDBPCS_ProjectPlan_now(self, ctx):
        if not ctx.uses_webui:
            ts = None
            if len(self.Project.PrimaryTimeSchedule) == 1:
                ts = self.Project.PrimaryTimeSchedule[0]
            elif not ctx.catalog_selection:
                targs = {"cdb_project_id": self.cdb_project_id}
                ctx.start_selection(catalog_name="cdbpcs_ts_catalog2", **targs)
            else:
                ts = ByID(ctx.catalog_selection[0]["cdb_object_id"])
            if ts:
                if ts.CheckAccess("read", auth.persno):
                    if ctx.uses_webui:
                        ctx.url(ts.getProjectPlanURL())
                    else:
                        ctx.set_followUpOperation(
                            opname="CDBPCS_ProjectPlan", use_result=1, op_object=ts
                        )
                else:
                    raise ue.Exception("cdbpcs_operation_access")

    def hasChildren(self):
        return self.is_group

    @classmethod
    def _getPlanningStatusPerClass(cls, objs):
        return TSHelper.get_virtual_attr_for_objs(cls, objs, "planning_status")

    # getter functions
    def getName(self):
        return self.task_name

    def getSubject(self):
        return self.mapped_subject_name

    def getResponsibleIDs(self):
        return self.getResponsiblePersons()

    def getPosition(self):
        return self.position

    def getChildrenObjects(self):
        return self.OrderedSubTasks

    def getParentObject(self):
        return self.getParent()

    def getEarlyStart(self):
        return self.early_start

    def getEarlyFinish(self):
        return self.early_finish

    def getLateStart(self):
        return self.late_start

    def getLateFinish(self):
        return self.late_finish

    def isMilestone(self):
        return self.milestone

    def getPredecessorRelations(self):
        return self.PredecessorTaskRelations

    def getSuccessorRelations(self):
        return self.SuccessorTaskRelations

    def getOverdueIcon(self):
        if self.getAttributeValue("status") in self.endStatus(full_cls=False):
            return None
        end = self.getAttributeValue("end_time_fcast")
        if not end or datetime.date.today() <= end:
            return None
        return self._getSignal("cdbpcs_overdue_fixed")

    # editable functions
    def getTSFieldsAsync(self, has_licence):
        obj_permission = self.getObjectPermission()
        field_access = self.getFieldAccess(
            has_licence=has_licence, permission=obj_permission
        )
        isMilestone = self.isMilestone()
        hiddenStartTimeFcast = isMilestone and not self.start_is_early
        hiddenEndTimeFcast = isMilestone and self.start_is_early
        isStartEditable = not hiddenStartTimeFcast and field_access["start_time_fcast"]
        isEndEditable = not hiddenEndTimeFcast and field_access["end_time_fcast"]
        # editable stuff
        data = {
            "isTitleEditable": field_access["task_name"],
            "isPositionEditable": field_access["position"],
            "isDurationEditable": field_access["days_fcast"],
            "isEffortEditable": field_access["effort_fcast"],
            "isEffortActEditable": field_access["effort_act"],
            "isStartEditable": isStartEditable,
            "isEndEditable": isEndEditable,
            "dragableFcast": (isStartEditable or isEndEditable)
            if isMilestone
            else (isStartEditable and isEndEditable),
            "dragablePlan": isStartEditable or isEndEditable,
            "resizableFcast": False
            if isMilestone
            else (isStartEditable or isEndEditable),
            "isAutoUpdateTimeVisible": True,
            "isAutoUpdateTimeEditable": field_access["auto_update_time"],
            "isEarlyPositionVisible": True,
            "isEarlyPositionEditable": isMilestone and field_access["start_is_early"],
            "isAutomaticVisible": True,
            "isAutomaticEditable": field_access["automatic"],
            "isConstraintDateEditable": field_access["constraint_date"],
            "isStartHidden": hiddenStartTimeFcast,
            "isEndHidden": hiddenEndTimeFcast,
            "end_plan_fix": 0,
            "objPermission": obj_permission,
        }
        # other expensive fields
        data.update({"responsible_oids": self.getResourceOIDs()})
        return data

    def isDiscarded(self):
        return self.status == 180

    def get_grafic_types(self):
        return {
            "class_name": "cdbpcs_task",
            "displayPlanBar": self.hasChildren(),
            "drawBold": self.hasChildren(),
            "hasRelations": True,
        }

    def get_object_description(self):
        if self.isMilestone():
            return get_label("pcs_milestone")
        elif self.hasChildren():
            return get_label("pcs_supertask")
        return get_label("cdbpcs_task")

    # setter functions
    def setName(self, name):
        self.updateObject(task_name=name)

    def setNewPosition(self, pos):
        self.updateObject(position=pos)

    def setEarlyPosition(self, pos):
        self.setAttributeValues(start_is_early=pos)

    def setAutomatic(self, auto):
        if auto and not self.days_fcast:
            self.days_fcast = int(not self.milestone)
        self.setAttributeValues(automatic=auto, auto_update_time=auto)

    def setAutoUpdateTime(self, auto):
        if self.automatic:
            self.setAttributeValues(auto_update_time=auto)
        else:
            self.setAttributeValues(automatic=auto, auto_update_time=auto)

    def setConstraint(self, constraint_date=None):
        constraints = self._determineConstraints(
            constraint_date=constraint_date, forced=True
        )
        if constraints:
            self.setAttributeValues(**constraints)

    def _determineConstraints(
        self, constraint_date=None, start=None, end=None, forced=False
    ):
        result = {}
        if not self.constraint_type or not self.automatic and not forced:
            return result
        ct = int(self.constraint_type)
        if not start and not end:
            if self.constraint_date != constraint_date:
                result["constraint_date"] = constraint_date
                if not constraint_date:
                    result["constraint_type"] = "0"
                elif ct in [0, 1]:
                    result["constraint_type"] = "4"
        elif start and ct in [2, 4, 5]:
            result["constraint_date"] = start
        elif end and ct in [3, 6, 7]:
            result["constraint_date"] = end
        elif start and ct in [0, 1]:
            result["constraint_date"] = start
            result["constraint_type"] = "4"
        return result

    def setEffortFcast(self, effort):
        effort = TSHelper.positive_float(val=effort)
        if not self.is_group:
            self.setAttributeValues(effort_fcast=effort, effort_plan=effort)
        elif not self.auto_update_effort:
            self.setAttributeValues(effort_fcast=effort)

    def setEffortAct(self, effort):
        effort = TSHelper.positive_float(val=effort)
        self.setAttributeValues(effort_act=effort)

    def setEffortDemand(self, effort):
        effort = TSHelper.positive_float(val=effort)
        sig.emit(Task, "adjust_effort_fcast_d")(self, effort=effort)

    def setEffortAssignment(self, effort):
        effort = TSHelper.positive_float(val=effort)
        sig.emit(Task, "adjust_effort_fcast_a")(self, effort=effort)

    def getCustomBarClass(self):
        cb_class = "thin-bar"
        if self.isMilestone():
            cb_class = "due-date-bar"
            if self.percent_complet == 100:
                cb_class = cb_class + " finished"
        return cb_class

    # pylint: disable=too-many-locals
    @classmethod
    def _getTSRelsPerClass(cls, objs, proj_field, task_field):
        # 1 SQL for every project, so split them up
        proj_ids = [task.cdb_project_id for task in objs]
        uniq_proj_ids = list(set(proj_ids))
        proj2task = {pid: [] for pid in uniq_proj_ids}
        for task in objs:
            proj2task[task.cdb_project_id].append(task)
        # get all relations for the tasks we need from this project
        tablename = TaskRelation.GetTableName()
        relations = []
        for pid, all_tasks in proj2task.items():
            for tasks in partition(all_tasks, get_dbms_split_count()):
                tasks_ids_str = ", ".join(["'" + task.task_id + "'" for task in tasks])
                sqlstr = (
                    f"SELECT * FROM {tablename} WHERE {proj_field}='{pid}'"
                    f" AND {task_field} IN ({tasks_ids_str})"
                )
                relations += TaskRelation.SQL(sqlstr)
        # to generate result in correct order and avoiding O(n^2)
        # we create a dictionary of pid,tid to obj index
        pid_tid2index = {}
        for index, task in enumerate(objs):
            pid_tid2index[(task.cdb_project_id, task.task_id)] = index
        # finally generate result
        result = [[] for x in range(len(objs))]
        for rel in relations:
            obj_index = pid_tid2index[
                (getattr(rel, proj_field), getattr(rel, task_field))
            ]
            result[obj_index].append(TSHelper.get_relation_data(rel))
        return result

    @classmethod
    def _getTSPredRelsPerClass(cls, objs):
        return cls._getTSRelsPerClass(objs, "cdb_project_id", "task_id")

    @classmethod
    def _getTSSuccRelsPerClass(cls, objs):
        return cls._getTSRelsPerClass(objs, "cdb_project_id2", "task_id2")


class TSHelper:
    type_labels = None

    @staticmethod
    def positive_int(val):
        if val:
            return max(0, int(val))
        return 0

    @staticmethod
    def positive_float(val):
        if val:
            return max(0.0, float(val))
        return 0.0

    @staticmethod
    def _get_url_suffix(obj, classname):
        primary_keys = obj._record.keydict()
        res = "?"
        for k, v in primary_keys.items():
            res = res + classname + "." + str(k) + "=" + str(v) + "&"
        return res[:-1]

    @staticmethod
    def getTypeLabel(rel_type):
        if not TSHelper.type_labels:
            TSHelper.type_labels = TaskRelationType.getTypeLabels()
        return TSHelper.type_labels.get(rel_type, rel_type)

    @staticmethod
    def date2utc(dt):
        # datetime or date => utc timestamp
        result = None
        if dt:
            if isinstance(dt, datetime.date):
                dt = datetime.datetime.combine(dt, datetime.datetime.min.time())
            if isinstance(dt, datetime.datetime):
                result = timegm(dt.utctimetuple()) * 1000
        return result

    @staticmethod
    def utc2date(timestamp):
        # utc timestamp => date
        if not timestamp:
            return None
        d = datetime.datetime.utcfromtimestamp(int(timestamp) / 1000)
        return datetime.date(d.year, d.month, d.day)

    @staticmethod
    def get_relation_data(task_rel):
        return {
            "successorID": task_rel.succ_task_oid,
            "predecessorID": task_rel.pred_task_oid,
            "conflict": task_rel.isViolated(),
            "minimal_gap": int(task_rel.minimal_gap) if task_rel.minimal_gap else 0,
            "type": task_rel.rel_type,
            "type_label": TSHelper.getTypeLabel(task_rel.rel_type),
            "icon_url": task_rel.GetObjectIcon(),
            "primary_keys": {
                "cdb_project_id": task_rel.cdb_project_id,
                "task_id": task_rel.task_id,
                "cdb_project_id2": task_rel.cdb_project_id2,
                "task_id2": task_rel.task_id2,
                "rel_type": task_rel.rel_type,
            },
        }

    @staticmethod
    def get_attr_from_recset(ids, recs, attr_name):
        attr_dict = {rec.cdb_object_id: rec.get(attr_name) for rec in recs}
        return [attr_dict.get(id) for id in ids]

    @staticmethod
    def get_virtual_attr_for_objs(clazz, objs, attr_name):
        ids = [obj.cdb_object_id for obj in objs]
        if not ids:
            return []
        stmts = []
        for split_ids in partition(list(set(ids)), get_dbms_split_count()):
            in_clause = "', '".join(split_ids)
            stmts.append(f"cdb_object_id IN ('{in_clause}')")
        field = DDField.KeywordQuery(
            classname=clazz._getClassname(), field_name=attr_name
        )
        if len(field):
            f_sql = field[0].sqlExpr()
            recs = sqlapi.RecordSet2(
                sql=(
                    f"SELECT cdb_object_id, {f_sql} FROM"
                    f" {clazz.GetTableName()} WHERE {' OR '.join(stmts)}"
                )
            )
            return TSHelper.get_attr_from_recset(ids, recs, attr_name)
        else:
            return ["" for id in ids]

    @staticmethod
    def get_op_info(op, url_suffix=""):
        return {
            "url": op["url"] + url_suffix,
            "title": op["fullpath_label"],
            "tooltip": op["tooltip"],
            "iconUrl": op["icon"],
            "iconLabel": op["label"],
        }


class ColumnDefinition(Object):
    """
    definition of table column class
    """

    __maps_to__ = "cdbpcs_ts_column"
    __classname__ = "cdbpcs_ts_column"

    Format = Reference_1(fColumnFormat, fColumnDefinition.format_name)

    def on_reset_position_now(self, ctx):
        pos = 0
        for c in ColumnDefinition.Query(
            f"chart = '{self.chart}'", order_by=["chart", "position"]
        ):
            pos += 10
            c.position = pos

    def get_column_value(self, obj, ts_obj=None):
        if self.attribute[:2] == "${" and self.attribute[-1] == "}":
            attr_name = self.attribute[2:-1]
        else:
            # old style ( <15.3.0 ) custom attribute support
            attr_name = self.attribute
        method = getattr(self, "get_" + attr_name, None)
        return (
            method(obj, ts_obj)
            if method
            else self._format(obj.getAttributeValue(attr_name))
        )

    def _format(self, value):
        if self.Format and self.Format.name == "date":
            if value:
                return TSHelper.date2utc(value)
            return None
        return value

    def get_obj_icon(self, obj, ts_obj=None):
        return {
            "icon": obj.GetObjectIcon(),
            "description": obj.get_object_description(),
        }

    def get_status_color(self, obj, ts_obj=None):
        url = ""
        if elink.isCDBPC():
            url = _OpHelper.get_object_operation("CDB_Workflow", obj)["url"]
        return {
            "style": f"background-color: rgb{obj.getStateColor()};",
            "url": url,
            "description": StateDefinition.ByKeys(
                statusnummer=obj.status, objektart=obj.GetObjectKind()
            ).StateText[""],
        }

    def get_title(self, obj, ts_obj=None):
        return obj.getName()

    def get_total_rating_icon(self, obj, ts_obj=None):
        return {
            "icon": obj.getTotalSignalIcon(),
            "description": obj.getTotalSignalDescription(),
        }

    def get_psp_code(self, obj, ts_obj=None):
        return obj.get_psp_code()

    def get_delete(self, obj, ts_obj=None):
        return {
            "inSchedule": bool(ts_obj),
            "unremovable": ts_obj.unremovable if ts_obj else False,
        }

    def get_time_signal_icon(self, obj, ts_obj=None):
        return {
            "icon": obj.getTimeSignalIcon(),
            "description": obj.getTimeSignalDescription(),
        }

    def get_overdue(self, obj, ts_obj=None):
        return {
            "icon": obj.getOverdueIcon(),
            "description": obj.getOverdueDescription(),
        }

    def get_status_effort_fcast(self, obj, ts_obj=None):
        return {
            "icon": obj.getEffortSignalIcon(),
            "description": obj.getEffortSignalDescription(),
        }

    def get_cdb_project_id(self, obj, ts_obj=None):
        return obj.getProjectID()

    def get_project_name(self, obj, ts_obj=None):
        return obj.getProjectName()

    def get_responsible(self, obj, ts_obj=None):
        return obj.getSubject()

    def get_position(self, obj, ts_obj=None):
        return obj.getPosition()

    def get_start_time_fcast(self, obj, ts_obj=None):
        return self._format(obj.getStartTimeFcast())

    def get_end_time_fcast(self, obj, ts_obj=None):
        return self._format(obj.getEndTimeFcast())

    def get_days_fcast(self, obj, ts_obj=None):
        return obj.getDaysFcast()

    def get_start_time_plan(self, obj, ts_obj=None):
        return self._format(obj.getStartTimePlan())

    def get_end_time_plan(self, obj, ts_obj=None):
        return self._format(obj.getEndTimePlan())

    def get_days(self, obj, ts_obj=None):
        return obj.getDays()

    def get_start_time_act(self, obj, ts_obj=None):
        return self._format(obj.getStartTimeAct())

    def get_end_time_act(self, obj, ts_obj=None):
        return self._format(obj.getEndTimeAct())

    def get_effort_fcast(self, obj, ts_obj=None):
        return obj.getEffortFcast()

    def get_effort_plan(self, obj, ts_obj=None):
        return obj.getEffortPlan()

    def get_effort_act(self, obj, ts_obj=None):
        return obj.getEffortAct()

    def get_effort_fcast_d(self, obj, ts_obj=None):
        return obj.getEffortDemand()

    def get_effort_fcast_a(self, obj, ts_obj=None):
        return obj.getEffortAssignment()

    def get_percent_complet(self, obj, ts_obj=None):
        return obj.getCompletion()

    def get_realization(self, obj, ts_obj=None):
        # TODO: massive performance issues, at least for Oracle DBs
        # return obj.getRealizationBy()
        return ""

    def get_constraint_type(self, obj, ts_obj=None):
        return obj.getAttributeValue("mapped_constraint_type_name")

    def get_constraint_date(self, obj, ts_obj=None):
        return self._format(obj.getAttributeValue("constraint_date"))


class ColumnFormat(Object):
    """
    The formatting of column.
    """

    __maps_to__ = "cdbpcs_ts_format"
    __classname__ = "cdbpcs_ts_format"
    Columns = Reference_N(
        fColumnDefinition, fColumnDefinition.format_name == fColumnFormat.name
    )

    def check_on_delete(self, ctx):
        """
        If formatting is deleted, then also need to be
        deleted from the referencing columns to the formatting.
        :Parameters:
            ``ctx`` : *Context*
        """
        for column in self.Columns:
            column.format_name = ""

    event_map = {(("delete"), "post"): ("check_on_delete")}
