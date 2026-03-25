#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=W0212,C1801,C0200,W0703,E1136,C0121,W0211,too-many-lines

import datetime
import logging
import math
from collections import defaultdict

from webob.exc import HTTPForbidden

from cdb import auth, sig, sqlapi, ue, util
from cdb.classbody import classbody
from cdb.constants import (
    kOperationDelete,
    kOperationModify,
    kOperationNew,
    kOperationShowObject,
)
from cdb.elink.engines.chameleon.engine import _OpHelper
from cdb.objects import (
    ByID,
    Class,
    Forward,
    Object,
    Reference_1,
    Reference_Methods,
    Reference_N,
    Rule,
)
from cdb.objects.operations import operation
from cdb.objects.org import Organization, Person, User, WithSubject
from cdb.util import get_label
from cs.pcs.projects import Project  # noqa
from cs.pcs.projects.chart import ChartConfig
from cs.pcs.resources import RessourceAssignment, RessourceDemand, db_tools
from cs.pcs.resources.helpers import to_iso_date
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments import ResourcePoolAssignment  # noqa
from cs.pcs.resources.pools.assignments.person import ResourcePoolAssignmentPerson
from cs.pcs.resources.structure.plugins import GET_SCHEDULE_PLUGINS
from cs.pcs.timeschedule import ColumnDefinition, TSHelper
from cs.platform.web.uisupport import get_webui_link

fProject = Forward("cs.pcs.projects.Project")
fResourceSchedule = Forward(__name__ + ".ResourceSchedule")
fResourceScheduleObject = Forward(__name__ + ".ResourceScheduleObject")
fProject2ResourceSchedule = Forward(__name__ + ".Project2ResourceSchedule")
fResourcePool2Schedule = Forward("cs.pcs.resources.pools.ResourcePool2Schedule")
fTimeSchedule = Forward("cs.pcs.timeschedule.TimeSchedule")
fCombinedResourceSchedule = Forward(__name__ + ".CombinedResourceSchedule")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourcePoolAssignment = Forward(
    "cs.pcs.resources.pools.assignments.ResourcePoolAssignment"
)
fResourceEvaluation = Forward(
    "cs.pcs.resources.resourceschedule.resourceevaluation.ResourceEvaluation"
)
fOrganization = Forward("cdb.objects.org.Organization")
fPerson = Forward("cdb.objects.org.Person")
fResourceDemand = Forward("cs.pcs.resources.RessourceDemand")
fResourceAssignment = Forward("cs.pcs.resources.RessourceAssignment")


class ResourceSchedule(WithSubject):
    __maps_to__ = "cdbpcs_resource_schedule"

    # attributes for web models
    schedule_column_group = "resource_standalone"
    schedule_content_table = "cdbpcs_rs_content"
    schedule_setting_id1 = "cs-pcs-resources-web"
    schedule_first_page_size = 100
    schedule_with_baselines = False

    # signal cannot be bound directly to the class
    @property
    def schedule_plugin_signal(self):
        return GET_SCHEDULE_PLUGINS

    def schedule_get_data(self, data, request):
        from cs.pcs.resources.web.models.data import ResourceScheduleDataModel
        model = ResourceScheduleDataModel(self.cdb_object_id)
        oids = [x["cdb_object_id"] for x in data.get("objects", [])]
        return model.get_resource_schedule_data(oids, request)

    def schedule_get_full_data(self, oids, request):
        from cs.pcs.resources.web.models.data import ResourceScheduleDataModel
        model = ResourceScheduleDataModel(self.cdb_object_id)
        return model.get_resource_schedule_data(oids, request)

    CombinedResourceSchedules = Reference_N(
        fCombinedResourceSchedule,
        fCombinedResourceSchedule.resource_schedule_oid
        == fResourceSchedule.cdb_object_id,
    )
    ResourceScheduleContents = Reference_N(
        fResourceScheduleObject,
        fResourceScheduleObject.view_oid == fResourceSchedule.cdb_object_id,
        order_by="position",
    )
    Project = Reference_1(fProject, fResourceSchedule.cdb_project_id)
    ReferencedProjects = Reference_N(
        fProject2ResourceSchedule,
        fProject2ResourceSchedule.resource_schedule_oid
        == fResourceSchedule.cdb_object_id,
    )
    ReferencedPools = Reference_N(
        fResourcePool2Schedule,
        fResourcePool2Schedule.resource_schedule_oid == fResourceSchedule.cdb_object_id,
    )

    @classmethod
    def createObject(cls, **kwargs):
        args = {
            "cdb_objektart": "cdbpcs_res_schedule",
            "subject_id": auth.persno,
            "subject_type": "Person",
            "cdb_project_id": "",
            "name": "",
        }
        args.update(**kwargs)
        return operation(kOperationNew, ResourceSchedule, **args)

    def on_CDBPCS_ResourceChart_now(self, ctx):
        self.show_resource_chart(ctx=ctx)

    def show_resource_chart(self, ctx, context=None):
        if context:  # pin context if not pinned
            self.insertObjects([context], unremovable=True)
        url = get_webui_link(None, self)
        ctx.url(url)

    def on_cdbpcs_refresh_resource_schedule_now(self, ctx):
        if self.Project:
            self.Project.insertIntoResourceSchedule(schedule_oid=self.cdb_object_id)

    def on_cdbpcs_delete_settings_now(self, ctx):
        self.delete_chart_setting(ctx, persno=auth.persno)

    def _get_selection(self, ctx, catalog_name):
        result = []
        if not ctx.catalog_selection:
            ctx.start_selection(catalog_name=catalog_name)
        else:
            result = ctx.catalog_selection
        return result

    def on_cdbpcs_add_resourcepool_now(self, ctx):
        for obj in self._get_selection(ctx, "cdbpcs_resource_pool3"):
            self._insertObject(fResourcePool.ByKeys(obj.cdb_object_id))

    def on_cdbpcs_add_resource_now(self, ctx):
        for obj in self._get_selection(ctx, "cdbpcs_resource_assignment2"):
            self._insertObject(fResourcePoolAssignment.ByKeys(obj.cdb_object_id))

    def on_cdbpcs_add_organization_now(self, ctx):
        for obj in self._get_selection(ctx, "cdbpcs_organization"):
            self._insertObject(fOrganization.ByKeys(obj.org_id))

    def on_cdbpcs_add_person_now(self, ctx):
        for obj in self._get_selection(ctx, "cdbpcs_person4"):
            self._insertObject(fPerson.ByKeys(obj.personalnummer))

    def on_cdbpcs_add_demand_now(self, ctx):
        for obj in self._get_selection(ctx, "cdbpcs_demand3"):
            self._insertObject(
                fResourceDemand.ByKeys(
                    cdb_project_id=obj.cdb_project_id, cdb_demand_id=obj.cdb_demand_id
                )
            )

    def on_cdbpcs_add_alloc_now(self, ctx):
        for obj in self._get_selection(ctx, "cdbpcs_alloc"):
            self._insertObject(
                fResourceAssignment.ByKeys(
                    cdb_project_id=obj.cdb_project_id, cdb_alloc_id=obj.cdb_alloc_id
                )
            )

    def insertAllPools(self):
        self.insertObjects(objs=fResourcePool.KeywordQuery(browser_root=1))

    def insertObjectsByOID(self, oids):
        if not oids:
            return
        s = "SELECT content_oid FROM %s WHERE view_oid='%s'" % (
            ResourceScheduleObject._getClassname(),
            self.cdb_object_id,
        )
        existing_content_oids = [x["content_oid"] for x in sqlapi.RecordSet2(sql=s)]
        oids = list(set(oids) - set(existing_content_oids))
        objs = []
        title_col_l = ResourceColumnDefinition.KeywordQuery(attribute="${title}")
        title_col = title_col_l[0] if len(title_col_l) else None

        def sort_func(x):
            if title_col:
                return title_col.get_column_value(x)
            else:
                return x.getName()

        # oder them by type and alphabetically
        ordered_objs = []
        for oid in oids:
            obj = ByID(oid)
            if obj:
                objs.append(obj)
            tmp_objs = [o for o in objs if isinstance(o, ResourcePool)]
            if len(tmp_objs):
                tmp_objs.sort(key=sort_func)
                ordered_objs += tmp_objs
            tmp_objs = [o for o in objs if not isinstance(o, ResourcePool)]
            if len(tmp_objs):
                tmp_objs.sort(key=sort_func)
                ordered_objs += tmp_objs
        self.insertObjects(ordered_objs)

    def getNextPosition(self):
        positions = [x.position for x in self.ResourceScheduleContents]
        positions.append(0)
        return max(positions) + 1

    def setOrderBy(self, attr=None):
        def sort_func(x):
            return x.getContentObject().getOrderValue(attr=attr)

        objs = []
        for obj in self.ResourceScheduleContents:
            if hasattr(obj.getContentObject(), "getOrderValue"):
                objs.append(obj)
            else:
                logging.error("deleting invalid resource schedule object: %s", dict(obj))
                obj.Delete()

        if objs:
            objs.sort(key=sort_func)
            for i in range(len(objs)):
                objs[i].position = i + 1

    def insertObjects(self, objs, unremovable=False):
        position = self.getNextPosition()
        for obj in objs:
            self._insertObject(obj, position=position, unremovable=unremovable)
            position += 1
        self.setOrderBy()

    def _insertObject(self, obj, position=0, unremovable=False):
        if ResourceScheduleObject.KeywordQuery(
            view_oid=self.cdb_object_id, content_oid=obj.cdb_object_id
        ):
            return
        kwargs = {}
        kwargs["view_oid"] = self.cdb_object_id
        kwargs["content_oid"] = obj.cdb_object_id
        kwargs["cdb_content_classname"] = obj.GetClassname()
        kwargs["position"] = position if position else self.getNextPosition()
        kwargs["unremovable"] = 1 if unremovable else 0
        ResourceScheduleObject.createObject(**kwargs)

    def insertProject(self, ctx):
        if ctx.error:
            return
        if self.Project:
            self.Project.insertIntoResourceSchedule(schedule_oid=self.cdb_object_id)
            kwargs = {
                "cdb_project_id": self.cdb_project_id,
                "resource_schedule_oid": self.cdb_object_id,
            }
            if ctx.relationship_name == "cdbpcs_project2res_schedule":
                # When the resource schedule is created using context a project,
                # relation ship between project and resource schedule will be created by kernel operation
                return
            if not Project2ResourceSchedule.ByKeys(**kwargs):
                Project2ResourceSchedule.Create(**kwargs)

    def checkResponsible(self, ctx):
        if self.subject_type == "PCS Role" and not self.cdb_project_id:
            raise ue.Exception("cdbpcs_project_id_needed")

    def getData(self, **kwargs):
        myargs = {
            "start": kwargs.get("start"),
            "order_by": "",
            "context": "project",
            "end": kwargs.get("end"),
            "interval": kwargs.get("scale"),
            "init": "True",
            "filter_list": "['cdbpcs: Active Project']",
            "cdb_project_ids": kwargs.get("evaluate_project_ids", []),
        }
        resources = self._getRessources(kwargs.get("ids"), myargs["start"], myargs["end"])
        resources = list(set(resources))
        myargs["resources"] = resources
        return self.calculatePlan(**myargs)

    def _getRessources(self, oids, start_date, end_date):  # pylint: disable=too-many-locals
        if not oids:
            return []

        date_condition = db_tools.get_time_frame_overlap_condition(
            "start_date", "end_date", start_date, end_date)
        target_date_condition = db_tools.get_time_frame_overlap_condition(
            "start_time_fcast", "end_time_fcast", start_date, end_date)

        my_orgs = fOrganization.KeywordQuery(cdb_object_id=oids)
        my_pers = fPerson.KeywordQuery(cdb_object_id=oids)

        oid_str_assign = db_tools.OneOfReduced('cdbpcs_pool_assignment').get_expression(
            'cdb_object_id', oids)
        my_assign = fResourcePoolAssignment.Query(
            f"{oid_str_assign} AND {date_condition}"
        )

        oid_str_demand = db_tools.OneOfReduced('cdbpcs_prj_demand_v').get_expression(
            'cdb_object_id', oids)
        demands = sqlapi.RecordSet2(
            "cdbpcs_prj_demand_v",
            f"{oid_str_demand} AND {target_date_condition}",
        )

        oid_str_alloc = db_tools.OneOfReduced('cdbpcs_prj_alloc_v').get_expression(
            'cdb_object_id', oids)
        allocs = sqlapi.RecordSet2(
            "cdbpcs_prj_alloc_v",
            f"{oid_str_alloc} AND {target_date_condition}",
        )

        pool_oor = db_tools.OneOfReduced('cdbpcs_resource_pool')
        oids_str_pool = pool_oor.get_expression('cdb_object_id', oids)
        pools_by_demand = pool_oor.get_expression(
            'cdb_object_id',
            [x["pool_oid"] for x in demands]
        )
        pools_by_alloc = pool_oor.get_expression(
            'cdb_object_id',
            [x["pool_oid"] for x in allocs]
        )
        my_pools = fResourcePool.Query(
            f"{oids_str_pool} OR {pools_by_demand} OR {pools_by_alloc}"
        )

        res_oor = db_tools.OneOfReduced('cdbpcs_resource')
        oids_str_res = res_oor.get_expression('cdb_object_id', oids)
        oids_str_res2 = res_oor.get_expression('referenced_oid', oids)
        res_by_demand = res_oor.get_expression(
            "cdb_object_id", [x["resource_oid"] for x in demands])
        res_by_alloc = res_oor.get_expression(
            "cdb_object_id", [x["resource_oid"] for x in allocs])
        oids_assign = res_oor.get_expression(
            "cdb_object_id", my_assign.cdb_object_id)
        my_res = fResource.Query(
            f"""{oids_str_res}
            OR {oids_str_res2}
            OR {res_by_demand}
            OR {res_by_alloc}
            OR {oids_assign}"""
        )
        resources = (
            list(my_pools)
            + list(my_orgs)
            + list(my_assign)
            + list(my_res)
            + list(my_pers)
        )
        return resources

    def calculatePlan(self, **kwargs):
        cr = None
        out = {}
        try:
            # initialize report
            cr = fResourceEvaluation(**kwargs)

            # evaluate all projects
            total_entries = {}
            cr.evaluateAll()
            details = cr.getAllocationDetails()
            matrix = cr.getCalculationDetails(include_capacity=True)
            total_entries.update(details)
            total_entries.update(matrix)

            # evaluate special projects
            project_entries = {}
            if cr.cdb_project_ids:
                cr.evaluatePrj(with_prj_ids=cr.cdb_project_ids)
                matrix = cr.getCalculationDetails(include_capacity=True)
                project_entries.update(matrix)
            project_entries.update(details)

            out["total_entries"] = total_entries
            out["project_entries"] = project_entries
            out["start_date"] = cr.start_date
            out["end_date"] = cr.end_date
        except Exception:
            logging.exception(
                "ResourceSchedule.calculatePlan: %s (kwargs: %s)",
                self.cdb_object_id,
                kwargs,
            )
            return "Exception in ResourceSchedule.calculatePlan"
        return out

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

    def reveal_rso_in_schedule(self, obj, keep_old_expanded_ids):
        expanded_ids = ChartConfig.getSetting(
            auth.persno, self.cdb_object_id, setting_name="#expandedId#"
        )
        lvl0_rsos_ids = [rso.content_oid for rso in self.ResourceScheduleContents]
        expanded_ids_2_add = []
        obj = obj.getParentObject()
        while obj:
            if not obj.cdb_object_id in expanded_ids:  # noqa
                expanded_ids_2_add.append(obj.cdb_object_id)
            if obj.cdb_object_id in lvl0_rsos_ids:
                break
            if keep_old_expanded_ids and obj.cdb_object_id in expanded_ids:
                break
            new_obj = obj.getParentObject()
            if not new_obj:
                # add object to resource schedule objects
                kwargs = {
                    "view_oid": self.cdb_object_id,
                    "content_oid": obj.cdb_object_id,
                    "cdb_content_classname": obj.GetClassname(),
                    "cdb_project_id": "",
                }
                try:
                    operation(kOperationNew, ResourceScheduleObject, **kwargs)
                except Exception as e:
                    return {
                        "error": str(
                            util.ErrorMessage("just_a_replacement", "%s" % (e))
                        )
                    }
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

    def _fully_expand_rso_in_schedule(self, obj, expanded_ids):
        children = obj.getChildrenObjects()
        if children:
            if not obj.cdb_object_id in expanded_ids:  # noqa
                expanded_ids.append(obj.cdb_object_id)
            for child in children:
                expanded_ids = self._fully_expand_rso_in_schedule(child, expanded_ids)
        return expanded_ids

    def fully_expand_rso_in_schedule(self, obj):
        expanded_ids = ChartConfig.getSetting(
            auth.persno, self.cdb_object_id, setting_name="#expandedId#"
        )
        expanded_ids = self._fully_expand_rso_in_schedule(obj, expanded_ids)
        ChartConfig.setSetting(
            auth.persno, self.cdb_object_id, expanded_ids, setting_name="#expandedId#"
        )

    def preset_project(self, ctx):
        if self.cdb_project_id:
            return
        if ctx and ctx.parent and hasattr(ctx.parent, "cdb_project_id"):
            self.cdb_project_id = ctx.parent["cdb_project_id"]

    def preset_subject(self, ctx):
        if self.subject_id:
            return
        self.subject_id = auth.persno
        self.subject_type = "Person"

    def deleteResourceScheduleContents(self, ctx=None):
        for rsc in self.ResourceScheduleContents:
            rsc.Delete()

    event_map = {
        (("create", "copy"), "pre_mask"): ("preset_subject", "preset_project"),
        (("create", "copy", "modify"), "post_mask"): ("checkResponsible"),
        (("create", "copy"), "post"): ("insertProject"),
        (("cdbpcs_timeschedule_ganttexport"), "now"): (
            "cdbpcs_timeschedule_ganttexport"
        ),
        (("delete"), "post"): (
            "delete_chart_setting",
            "deleteResourceScheduleContents",
        ),
    }


class ResourceScheduleTime(ResourceSchedule):
    __classname__ = "cdbpcs_resource_schedule_time"
    __match__ = ResourceSchedule.cdb_classname >= __classname__

    # column definition and mapping for RS in combined schedule
    schedule_column_group = "resource"

    @classmethod
    def createObject(cls, **kwargs):
        args = {
            "cdb_objektart": "cdbpcs_res_schedule",
            "subject_id": auth.persno,
            "subject_type": "Person",
            "cdb_project_id": "",
            "name": "",
        }
        args.update(**kwargs)
        return operation(kOperationNew, ResourceScheduleTime, **args)


class ResourceScheduleObject(Object):
    __maps_to__ = "cdbpcs_rs_content"

    ResourceSchedule = Reference_1(
        fResourceSchedule,
        fResourceSchedule.cdb_object_id == fResourceScheduleObject.view_oid,
    )

    def getContentObject(self):
        return ByID(self.content_oid)

    def initPosition(self):
        self.position = self.ResourceSchedule.getNextPosition()

    def resetPosition(self):
        pos = self.position
        to_change = [
            x
            for x in self.ResourceSchedule.ResourceScheduleContents
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

    @classmethod
    def createObject(cls, **kwargs):
        operation(kOperationNew, ResourceScheduleObject, **kwargs)

    def setProjectID(self):
        # self.getPersistentObject().cdb_project_id = self.getContentObject().getAttributeValue("cdb_project_id")
        pass

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


class CombinedResourceSchedule(Object):
    __maps_to__ = "cdbpcs_time2res_schedule"

    TimeSchedule = Reference_1(
        fTimeSchedule, fCombinedResourceSchedule.time_schedule_oid
    )
    ResourceSchedule = Reference_1(
        fResourceSchedule, fCombinedResourceSchedule.resource_schedule_oid
    )


class Project2ResourceSchedule(Object):
    __maps_to__ = "cdbpcs_project2res_schedule"

    Project = Reference_1(fProject, fProject2ResourceSchedule.cdb_project_id)
    ResourceSchedule = Reference_1(
        fResourceSchedule, fProject2ResourceSchedule.resource_schedule_oid
    )


class WithResourceScheduleContent(object):
    _operation_context_ = "res_resourceschedule_items"

    def _getResourceScheduleObjects(self):
        return ResourceScheduleObject.KeywordQuery(content_oid=self.cdb_object_id)

    ResourceScheduleObjects = Reference_Methods(
        ResourceScheduleObject, lambda self: self._getResourceScheduleObjects()
    )

    def _getResourceSchedules(self):
        return [x.ResourceSchedule for x in self._getResourceScheduleObjects()]

    ResourceSchedules = Reference_Methods(
        ResourceSchedule, lambda self: self._getResourceSchedules()
    )

    def getOrderValue(self, attr=None):
        if attr:
            return "%s-%s" % (self.getOrderType(), self.getAttributeValue(attr))
        return "%s-%s" % (self.getOrderType(), self.getName())

    def getOrderType(self):
        """overwrite method to sort objects by their type value"""
        return 0

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

    def getProjectID(self):
        return self.getAttributeValue("cdb_project_id")

    def getProjectName(self):
        return self.getAttributeValue("project_name")

    def getSubjectTooltip(self):
        return self.getSubject()

    def getResource(self):
        return ""

    def getSubject(self):
        return ""

    def get_psp_code(self):
        return ""

    def getResponsibleIDs(self):
        return []

    def getResponsibleNames(self):
        "Returns the names of all persons that are responsible"
        ids = self.getResponsibleIDs()
        if not ids:
            return []
        id_str = ", ".join("'%s'" % x for x in ids)
        sql = (
            "SELECT name FROM angestellter WHERE personalnummer IN (%s) ORDER BY name"
            % id_str
        )
        result = sqlapi.RecordSet2(sql=sql)
        return [r["name"] for r in result]

    def getAttributeValue(self, attr_name):
        if hasattr(self, attr_name):
            return self._getValue(self[attr_name])
        return ""

    def _getValue(self, val):
        if type(val) in [str, str, int, float]:
            return val
        return ""

    @staticmethod
    def getDoubleClickOperation():
        return kOperationModify

    @staticmethod
    def getFallbackOperation():
        return kOperationShowObject

    def getObjectForOperation(self):
        return self

    def setAttributeValues(self, **kwargs):
        operation(kOperationModify, self, **kwargs)
        # reload from DB
        self.Reload()

    def getDemand(self):
        return ""

    def getRSDemands(self, start=None, end=None, prj_ids=None):
        return []

    def hasRSDemands(self):
        return False

    def setDemand(self, hours=0.0):
        pass

    def getOpenDemand(self):
        return ""

    def getAssignment(self):
        return ""

    def getRSAssignments(self, start=None, end=None, prj_ids=None):
        return []

    def hasRSAssignments(self, start=None, end=None):
        return False

    def setAssignment(self, hours=0.0):
        pass

    def getName(self):
        if isinstance(self, Person) and hasattr(self, "name"):
            return self.name
        return self.GetDescription()

    def editableName(self):
        return False

    def setName(self, name):
        pass

    def getChildrenObjects(self, start=None, end=None):
        return []

    def hasChildrenObjects(self):
        return len(self.getChildrenObjects()) > 0

    def getParentObject(self):
        return None

    def getAllResourceScheduleObjects(self):
        return [self]

    def insertCompleteIntoSchedule(self, schedule_oid):
        rs = ResourceSchedule.ByKeys(schedule_oid)
        if rs:
            rs.insertObjects(self.getAllResourceScheduleObjects())

    def insertIntoResourceSchedule(self, schedule_oid):
        rs = ResourceSchedule.ByKeys(schedule_oid)
        if rs:
            rs._insertObject(obj=self)

    def getDemandCreateURL(self):
        demand_URI = Class.MakeCdbcmsg(RessourceDemand, action="CDB_Create")
        return demand_URI.eLink_url()

    def getAssignmentCreateURL(self):
        assignment_URI = Class.MakeCdbcmsg(RessourceAssignment, action="CDB_Create")
        return assignment_URI.eLink_url()

    def delete_chart_setting(self, ctx=None):
        chart_configs = ChartConfig.KeywordQuery(attr=self.cdb_object_id)
        for config in chart_configs:
            operation(kOperationDelete, config)

    # editable functions
    def _isEditable(self, attr, field_access_dict=None):
        if field_access_dict == None:  # noqa
            field_access_dict = self.getFieldAccess()
        return field_access_dict[attr]

    def deleteResourceScheduleObjects(self, ctx=None):
        for rso in self.ResourceScheduleObjects:
            rso.Delete()

    @staticmethod
    @sig.connect("plugins.validate_schedule")
    def validate_schedule(schedule_oid):
        rs = ResourceSchedule.ByKeys(schedule_oid)
        if rs:
            combined = CombinedResourceSchedule.KeywordQuery(resource_schedule_oid=schedule_oid)
            if not combined:
                logging.exception(f"{get_label('unpinnable_plugin')} Schedule: '%s'", schedule_oid)
                raise HTTPForbidden(get_label("unpinnable_plugin"))

    @staticmethod
    def getTSFieldsPerClass(cls, objs):
        classname = cls._getClassname()

        # Find out what happens when you double-click the row:
        # 1. double-click operation according to the return value of getDoubleClickOperation of
        #    the business object class
        # 2. fallback operation  according to the return value of getFallbackOperation of
        #    the business object class
        # 3. nothing
        operations = _OpHelper.get_class_operations(
            [cls.getDoubleClickOperation()], classname
        )
        if not operations:
            operations = _OpHelper.get_class_operations(
                [cls.getFallbackOperation()], classname
            )
        base_dblclck_url = operations[0]["url"] if operations else ""

        result = []
        for index, obj in enumerate(objs):
            if not base_dblclck_url:
                # An empty URL allows a double-click,
                # shows a prohibition symbol for a short time
                # and displays the current page without refresh.
                result.append({"modifyOperationUrl": ""})
            else:
                url_suffix = RSHelper._get_url_suffix(obj, classname)
                result.append({"modifyOperationUrl": base_dblclck_url + url_suffix})
        if "task_id" in [tf.name for tf in cls.GetTableKeys()]:
            task_names = RSHelper.get_attr_from_relation(
                objs, "task_name", "cdbpcs_task", "task_id"
            )
            task_oids = RSHelper.get_attr_from_relation(
                objs, "cdb_object_id", "cdbpcs_task", "task_id"
            )
            for index, obj in enumerate(objs):
                result[index].update(
                    {
                        "task_name": task_names[index],
                        "task_object_id": task_oids[index],
                    }
                )
        return result

    def getTSFieldsPerObject(self, has_licence, a_sync):  # noqa
        data = self.getTSFieldsSync()
        if a_sync:  # noqa
            # load defaults and load the rest async later
            data.update(self.getTSFieldsAsyncDefaults())
        else:
            data.update(self.getTSFieldsAsync(has_licence))
        return data

    def _getTSFieldsSync(self):
        result = {
            "demandURL": self.getDemandCreateURL(),
            "assignmentURL": self.getAssignmentCreateURL(),
            "class_name": self.GetClassname(),
            "hasDemands": self.hasRSDemands(),
            "hasAssignments": self.hasRSAssignments(),
            "hasChildren": self.hasChildrenObjects(),
            "objCdbObjectId": self.cdb_object_id,
        }
        return result

    def getTSFieldsAsyncDefaults(self):
        editable_keys = ["isDemandEditable", "isAssignmentEditable"]
        data = dict.fromkeys(editable_keys, False)
        # expensive fields that will be loaded async
        data.update(
            {
                #
            }
        )
        return data

    def getTSFieldsAsync(self, has_licence):
        # per class implementation
        return {
            #
        }

    # resourceschedule columns getters
    @classmethod
    def get_ts_col_val_start_date(cls, objs, obj_id_2_tso):
        return RSHelper.default_get_ts_col_val(cls, objs, obj_id_2_tso)

    @classmethod
    def get_ts_col_val_end_date(cls, objs, obj_id_2_tso):
        return RSHelper.default_get_ts_col_val(cls, objs, obj_id_2_tso)

    @classmethod
    def get_ts_col_val_duration(cls, objs, obj_id_2_tso):
        return RSHelper.default_get_ts_col_val(cls, objs, obj_id_2_tso)

    @classmethod
    def get_ts_col_val_start_time_act(cls, objs, obj_id_2_tso):
        return RSHelper.default_get_ts_col_val(cls, objs, obj_id_2_tso)

    @classmethod
    def get_ts_col_val_end_time_act(cls, objs, obj_id_2_tso):
        return RSHelper.default_get_ts_col_val(cls, objs, obj_id_2_tso)

    @classmethod
    def get_ts_col_val_operations(cls, objs, obj_id_2_tso):
        classname = cls._getClassname()
        ops = _OpHelper.get_class_operations_for_context(
            classname, cls._operation_context_
        )
        result = []
        for index, obj in enumerate(objs):  # pylint: disable=W0612
            ops_arr = []
            url_suffix = TSHelper._get_url_suffix(obj, classname)
            for op in ops:
                ops_arr.append(TSHelper.get_op_info(op, url_suffix))
            result.append(ops_arr)
        return result

    event_map = {
        (("delete"), "post"): ("delete_chart_setting", "deleteResourceScheduleObjects"),
    }


@classbody
class RessourceDemand(WithResourceScheduleContent):
    _operation_context_ = "res_resourceschedule_assign"

    def getOrderType(self):
        return 3

    def setDemand(self, hours=0.0):
        hours = max(hours, 0.0)
        hours_per_day = self.getHoursPerDay(hours)
        self.setAttributeValues(hours=hours, hours_per_day=hours_per_day)

    def getResource(self):
        return self.getParentObject().getName()

    def getPlanningStatus(self):
        entries = self.Task.getPlanningStatus().split(" ")
        entries = [x for x in entries if x.startswith("demand")]
        return " ".join(entries)

    def getSubject(self):
        return self.Task.getSubject()

    def getResponsibleIDs(self):
        return self.Task.getResponsibleIDs()

    def get_psp_code(self):
        return self.Task.get_psp_code()

    def getDemand(self):
        return self.getAttributeValue("hours")

    def getOpenDemand(self):
        return max(0.0, self.getDemand() - self.getAttributeValue("hours_assigned"))

    def getAssignment(self):
        return self.getAttributeValue("hours_assigned")

    def getParentObject(self):
        if self.ResourcePoolAssignment:
            return self.ResourcePoolAssignment
        return self.ResourcePool

    def getName(self):
        return (
            "("
            + self.Project.getAttributeValue("cdb_project_id")
            + ") "
            + self.Task.getAttributeValue("task_name")
        )

    def getTSFieldsSync(self):
        result = self._getTSFieldsSync()
        result.update(
            {
                "prj_name": self.project_name if self.project_name else "",
                "prj_id": self.cdb_project_id,
                "task_id": self.task_id,
                "demand_id": self.cdb_demand_id,
                "planning_status": self.getPlanningStatus(),
                "hours_per_day": self.hours_per_day if self.hours_per_day else "",
            }
        )
        return result

    def getTSFieldsAsync(self, has_licence):
        obj_permission = self.getObjectPermission()
        field_access = self.getFieldAccess(
            has_licence=has_licence, permission=obj_permission
        )
        # editable stuff
        data = {
            "objPermission": obj_permission,
            "isDemandEditable": self._isEditable(
                "hours", field_access_dict=field_access
            ),
            "isAssignmentEditable": False,
        }
        # other expensive fields
        data.update(
            {
                #
            }
        )
        return data

    # resourceschedule columns getters
    @classmethod
    def get_ts_col_val_start_date(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "start_time_fcast", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_end_date(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "end_time_fcast", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_duration(cls, objs, obj_id_2_tso):
        return RSHelper.get_attr_from_relation(
            objs, "days_fcast", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_start_time_act(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "start_time_act", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_end_time_act(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "end_time_act", "cdbpcs_task", "task_id"
        )


@classbody
class RessourceAssignment(WithResourceScheduleContent):
    _operation_context_ = "res_resourceschedule_assign"

    def getOrderType(self):
        return 4

    def setAssignment(self, hours=0.0):
        hours = max(hours, 0.0)
        hours_per_day = self.getHoursPerDay(hours)
        if not hours_per_day:
            hours_per_day = 0.0
        self.setAttributeValues(hours=hours, hours_per_day=hours_per_day)

    def getResource(self):
        return self.getParentObject().getName()

    def getPlanningStatus(self):
        entries = self.Task.getPlanningStatus().split(" ")
        entries = [x for x in entries if x.startswith("assignment")]
        return " ".join(entries)

    def getSubject(self):
        return self.Task.getSubject()

    def getResponsibleIDs(self):
        return self.Task.getResponsibleIDs()

    def get_psp_code(self):
        return self.Task.get_psp_code()

    def getDemand(self):
        return self.Demand.getDemand()

    def getOpenDemand(self):
        return self.Demand.getOpenDemand()

    def getAssignment(self):
        return self.getAttributeValue("hours")

    def getParentObject(self):
        if self.ResourcePoolAssignment:
            return self.ResourcePoolAssignment
        return self.ResourcePool

    def getName(self):
        return (
            "("
            + self.Project.getAttributeValue("cdb_project_id")
            + ") "
            + self.Task.getAttributeValue("task_name")
        )

    def getTSFieldsSync(self):
        result = self._getTSFieldsSync()
        result.update(
            {
                "prj_name": self.project_name if self.project_name else "",
                "prj_id": self.cdb_project_id,
                "task_id": self.task_id,
                "demand_id": self.cdb_demand_id,
                "planning_status": self.getPlanningStatus(),
                "hours_per_day": self.hours_per_day if self.hours_per_day else "",
            }
        )
        return result

    def getTSFieldsAsync(self, has_licence):
        obj_permission = self.getObjectPermission()
        field_access = self.getFieldAccess(
            has_licence=has_licence, permission=obj_permission
        )
        # editable stuff
        data = {
            "objPermission": obj_permission,
            "isDemandEditable": False,
            "isAssignmentEditable": self._isEditable(
                "hours", field_access_dict=field_access
            ),
        }
        # other expensive fields
        data.update(
            {
                #
            }
        )
        return data

    # resourceschedule columns getters
    @classmethod
    def get_ts_col_val_start_date(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "start_time_fcast", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_end_date(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "end_time_fcast", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_duration(cls, objs, obj_id_2_tso):
        return RSHelper.get_attr_from_relation(
            objs, "days_fcast", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_start_time_act(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "start_time_act", "cdbpcs_task", "task_id"
        )

    @classmethod
    def get_ts_col_val_end_time_act(cls, objs, obj_id_2_tso):
        return RSHelper.get_date_attr_from_relation(
            objs, "end_time_act", "cdbpcs_task", "task_id"
        )


def _remove_duplicates_in_hierarchy(resource_pools):
    # If there are multiple pools in the same pool hierarchy,
    # we only want to add the highest pool of the combined hierarchy
    new_pools = []
    for pool_oid in set(resource_pools):
        parent = ResourcePool.KeywordQuery(cdb_object_id=pool_oid)[0].parent_oid
        while parent:
            if parent in resource_pools:
                break
            parent = ResourcePool.KeywordQuery(cdb_object_id=parent)[0].parent_oid
        if not parent:
            new_pools.append(pool_oid)
    return new_pools


def _get_current_quarter(curr_date):
    return math.ceil((curr_date.month - 1) // 3) + 1


def _get_start_date(curr_date):
    quarter = _get_current_quarter(curr_date) - 1
    year = curr_date.year
    if quarter == 0:
        quarter = 4
        year -= 1
    month = quarter * 3 - 2
    return datetime.date(year, month, 1)


def _get_end_date(curr_date):
    quarter = _get_current_quarter(curr_date) + 2
    year = curr_date.year
    if quarter == 5:
        quarter = 1
        year += 1
    if quarter == 6:
        quarter = 2
        year += 1
    month = quarter * 3 - 1
    return datetime.date(year, month, 1) - datetime.timedelta(days=1)


def _get_valid_pools(all_memberships):
    # Default time frame is
    #   - Start: The quarter before the current quarter
    #   - End: The second quarter after the current quarter
    today = datetime.date.today()
    std_start = _get_start_date(today)
    std_end = _get_end_date(today)
    valid_pools = []
    for m in all_memberships:
        if (
            (not m.start_date or m.start_date <= std_end)
            and (not m.end_date or m.end_date >= std_start)
        ):
            valid_pools.append(m.pool_oid)
    return valid_pools


@classbody
class Project(object):
    def insertIntoResourceSchedule(self, schedule_oid):
        rs = ResourceSchedule.ByKeys(schedule_oid)
        if rs:
            all_memberships = ResourcePoolAssignment.KeywordQuery(person_id=self.TeamMembers.cdb_person_id)
            valid_pools = _get_valid_pools(all_memberships)
            if len(valid_pools) > 0:
                rs.insertObjectsByOID(_remove_duplicates_in_hierarchy(valid_pools))


@classbody
class ResourcePool(WithResourceScheduleContent):
    def getOrderType(self):
        return 1

    def hasRSDemands(self):
        return True

    def hasRSAssignments(self, start=None, end=None):
        return True

    def getRSDemands(self, start=None, end=None, prj_ids=None):
        prj_rule = Rule.ByKeys("cdbpcs: Active Project")
        if prj_ids is not None and prj_ids:
            prj_rule = None
        all_demands = list(
            self.getDemands(
                start_date=start,
                end_date=end,
                prj_rule=prj_rule,
                include_covered=True,
                include_resources=False,
                include_sub_pools=False,
                with_prj_ids=prj_ids,
                all_status=True,
            )
        )
        return [x for x in all_demands if not x.resource_oid]

    def getRSAssignments(self, start=None, end=None, prj_ids=None):
        prj_rule = Rule.ByKeys("cdbpcs: Active Project")
        if prj_ids is not None and prj_ids:
            prj_rule = None
        all_assignments = list(
            self.getAssignments(
                start_date=start,
                end_date=end,
                prj_rule=prj_rule,
                include_resources=False,
                include_sub_orgs=False,
                with_prj_ids=prj_ids,
                all_status=True,
            )
        )
        return [x for x in all_assignments if not x.resource_oid]

    def getChildrenObjects(self, start=None, end=None):
        objs_o = list(self.SubPools)
        objs_o.sort(key=lambda x: x.name)
        objs_r = []
        if start and end:
            objs_r = list(self.getPoolAssignments(start=start, end=end))
        else:
            objs_r = list(self.PoolAssignments)
        objs_r.sort(key=lambda x: x.pool_name + x.resource_name)
        return objs_o + objs_r

    def hasChildrenObjects(self):
        return True

    def getParentObject(self):
        return self.ParentPool

    def getDemandCreateURL(self):
        demand_URI = Class.MakeCdbcmsg(
            RessourceDemand, action="CDB_Create", pool_oid=self.cdb_object_id
        )
        return demand_URI.eLink_url()

    def getAssignmentCreateURL(self):
        assignment_URI = Class.MakeCdbcmsg(
            RessourceAssignment, action="CDB_Create", pool_oid=self.cdb_object_id
        )
        return assignment_URI.eLink_url()

    def deleteResourceScheduleObjects(self, ctx=None):
        # removing all assignments from resource schedules
        if "_all_assignment_ids_" in ctx.ue_args.get_attribute_names():
            all_ass_rsos = fResourceScheduleObject.Query(
                "content_oid IN ({0})".format(ctx.ue_args["_all_assignment_ids_"])
            )
            for rso in all_ass_rsos:
                rso.Delete()
        for rso in self.ResourceScheduleObjects:
            rso.Delete()

    def keepAssignmentsIds(self, ctx):
        ctx.keep(
            "_all_assignment_ids_",
            "'" + "', '".join([a.cdb_object_id for a in self.PoolAssignments]) + "'",
        )

    def getTSFieldsSync(self):
        result = self._getTSFieldsSync()
        parent_pool = self.ParentPool
        result.update(
            {
                "head_pool": parent_pool.name if parent_pool else "",
                "objPermission": True,
            }
        )
        return result

    event_map = {
        (("delete"), "pre"): ("keepAssignmentsIds"),
    }


@classbody
class ResourcePoolAssignmentPerson(WithResourceScheduleContent):
    def getOrderValue(self, attr=None):
        if attr:
            return "%s-%s-%s" % (
                self.getOrderType(),
                self.getAttributeValue(attr),
                to_iso_date(self.real_start_date),
            )
        return "%s-%s-%s" % (
            self.getOrderType(),
            self.getName(),
            to_iso_date(self.real_start_date),
        )

    def getOrderType(self):
        return 2

    def hasRSDemands(self):
        return True

    def hasRSAssignments(self, start=None, end=None):
        return True

    def getRSDemands(self, start=None, end=None, prj_ids=None):
        prj_rule = Rule.ByKeys("cdbpcs: Active Project")
        if prj_ids is not None and prj_ids:
            prj_rule = None
        return list(
            self.getDemands(
                start_date=start,
                end_date=end,
                prj_rule=prj_rule,
                include_covered=True,
                with_prj_ids=prj_ids,
                all_status=True,
            )
        )

    def getRSAssignments(self, start=None, end=None, prj_ids=None):
        prj_rule = Rule.ByKeys("cdbpcs: Active Project")
        if prj_ids is not None and prj_ids:
            prj_rule = None
        return list(
            self.getAssignments(
                start_date=start,
                end_date=end,
                prj_rule=prj_rule,
                with_prj_ids=prj_ids,
                all_status=True,
            )
        )

    def getObjectForOperation(self):
        return self.Person

    def getName(self):
        return self.resource_name

    def getParentObject(self):
        return self.ResourcePool

    def getDemandCreateURL(self):
        demand_URI = Class.MakeCdbcmsg(
            RessourceDemand,
            action="CDB_Create",
            pool_oid=self.pool_oid,
            resource_oid=self.resource_oid,
            assignment_oid=self.cdb_object_id,
            original_resource_oid=self.Resource.referenced_oid,
        )
        return demand_URI.eLink_url()

    def getAssignmentCreateURL(self):
        assignment_URI = Class.MakeCdbcmsg(
            RessourceAssignment,
            action="CDB_Create",
            pool_oid=self.pool_oid,
            resource_oid=self.resource_oid,
            assignment_oid=self.cdb_object_id,
            original_resource_oid=self.Resource.referenced_oid,
        )
        return assignment_URI.eLink_url()

    def getResource(self):
        return self.getParentObject().getName()

    def getTSFieldsSync(self):
        result = self._getTSFieldsSync()
        resource_pool = self.ResourcePool
        result.update(
            {
                "pool_name": resource_pool.name if resource_pool else "",
                "objPermission": True,
            }
        )
        return result

    @classmethod
    def get_ts_col_val_start_date(cls, objs, obj_id_2_tso):
        return RSHelper.get_attr_for_objs(cls, objs, "start_date")

    @classmethod
    def get_ts_col_val_end_date(cls, objs, obj_id_2_tso):
        return RSHelper.get_attr_for_objs(cls, objs, "end_date")


@classbody
class Organization(WithResourceScheduleContent):
    def getName(self):
        return "{0} ({1})".format(self.name, self.org_type_name)

    def getOrderType(self):
        return 3

    def getChildrenObjects(self, start=None, end=None):
        objs_o = list(self.SubOrganizations)
        objs_o.sort(key=lambda x: x.name)
        objs_r = list(self.Resources)
        objs_r.sort(key=lambda x: x.Organization.name + x.name)
        return objs_o + objs_r

    def hasChildrenObjects(self):
        return True

    def getParentObject(self):
        return self.HeadOrganization

    def getDemandCreateURL(self):
        return ""

    def getAssignmentCreateURL(self):
        return ""

    def getTSFieldsSync(self):
        result = self._getTSFieldsSync()
        result.update(
            {
                "org_id": self.org_id,
                "head_org": self.head_name if self.head_name else "",
                "objPermission": True,
            }
        )
        return result


@classbody
class Person(WithResourceScheduleContent):
    def getOrderType(self):
        return 4

    def hasRSDemands(self):
        return True

    def hasRSAssignments(self, start=None, end=None):
        return True

    def getRSDemands(self, start=None, end=None, prj_ids=None):
        prj_rule = Rule.ByKeys("cdbpcs: Active Project")
        if prj_ids is not None and prj_ids:
            prj_rule = None
        return list(
            self.getDemands(
                start_date=start,
                end_date=end,
                prj_rule=prj_rule,
                include_covered=True,
                with_prj_ids=prj_ids,
                all_status=True,
            )
        )

    def getRSAssignments(self, start=None, end=None, prj_ids=None):
        prj_rule = Rule.ByKeys("cdbpcs: Active Project")
        if prj_ids is not None and prj_ids:
            prj_rule = None
        return list(
            self.getAssignments(
                start_date=start,
                end_date=end,
                prj_rule=prj_rule,
                with_prj_ids=prj_ids,
                all_status=True,
            )
        )

    def getParentObject(self):
        return self.Organization

    def getResource(self):
        return self.getParentObject().getName()

    def getTSFieldsSync(self):
        result = self._getTSFieldsSync()
        result.update(
            {
                "personalnummer": self.personalnummer,
                "orgname": self.orgname if self.orgname else "",
                "objPermission": True,
            }
        )
        return result


class RSHelper(TSHelper):
    @staticmethod
    def default_get_ts_col_val(cls, objs, obj_id_2_tso):
        return [""] * len(objs)

    @staticmethod
    def get_attr_for_objs(cls, objs, attr_name):
        ids = [obj.cdb_object_id for obj in objs]
        recs = sqlapi.RecordSet2(
            sql="SELECT cdb_object_id, {0} FROM {1} WHERE cdb_object_id IN ('{2}')".format(
                attr_name, cls.GetTableName(), "', '".join(ids)
            )
        )
        return TSHelper.get_attr_from_recset(ids, recs, attr_name)

    @staticmethod
    def _get_attr_from_relation(objs, attr2get, tablename, attr4rel):
        rel_ids = [getattr(obj, attr4rel) for obj in objs]
        uniq_rids = list({rid for rid in rel_ids if rid})
        recs = sqlapi.RecordSet2(
            sql="SELECT {0}, {1} FROM {2} WHERE {0} IN ('{3}')".format(
                attr4rel, attr2get, tablename, "', '".join(uniq_rids)
            )
        )
        return {rec.get(attr4rel): rec.get(attr2get) for rec in recs}

    @staticmethod
    def get_attr_from_relation(objs, attr2get, tablename, attr4rel):
        rel_ids = [getattr(obj, attr4rel) for obj in objs]
        attr_dict = RSHelper._get_attr_from_relation(
            objs, attr2get, tablename, attr4rel
        )
        return [attr_dict.get(rid) for rid in rel_ids]

    @staticmethod
    def get_date_attr_from_relation(objs, attr2get, tablename, attr4rel):
        rel_ids = [getattr(obj, attr4rel) for obj in objs]
        attr_dict = RSHelper._get_attr_from_relation(
            objs, attr2get, tablename, attr4rel
        )
        date_dict = {k: RSHelper.date2utc(v) for k, v in attr_dict.items()}
        return [date_dict.get(rid) for rid in rel_ids]


class ResourceColumnDefinition(ColumnDefinition):
    def get_obj_resource(self, obj):
        if obj.Resource:
            return obj.Resource
        else:
            from cs.pcs.resources.pools.assignments import Resource

            args = {
                "referenced_oid": obj.cdb_object_id,
                "calendar_profile_id": obj.calendar_profile_id,
                "capacity": obj.capacity,
                "name": obj.name,
            }
            return operation(kOperationNew, Resource, **args)

    def get_obj_icon(self, obj, rs_obj=None):
        if (
            obj.GetClassname() == User._getClassname()
            or obj.GetClassname() == ResourcePoolAssignmentPerson._getClassname()
        ):
            icon = self.get_obj_resource(obj).GetObjectIcon()
            description = get_label("resources_ressource")
        else:
            icon = obj.GetObjectIcon()
            description = ""
            if obj.GetClassname() == Organization._getClassname():
                description = get_label("cdb_organisation")
            elif obj.GetClassname() == RessourceDemand._getClassname():
                if obj.coverage == 1:
                    description = get_label("cdbpcs_demand_covered")
                elif obj.coverage == 0:
                    description = get_label("cdbpcs_demand_uncovered")
            elif obj.GetClassname() == RessourceAssignment._getClassname():
                description = get_label("pcs_assignment")
        return {"icon": icon, "description": description}

    def get_demand(self, obj, rs_obj=None):
        if hasattr(obj, "getDemand") and callable(getattr(obj, "getDemand")):
            return self._format(obj.getDemand())
        return ""

    def get_open_demand(self, obj, rs_obj=None):
        if hasattr(obj, "getOpenDemand") and callable(getattr(obj, "getOpenDemand")):
            return self._format(obj.getOpenDemand())
        return ""

    def get_assignment(self, obj, rs_obj=None):
        if hasattr(obj, "getAssignment") and callable(getattr(obj, "getAssignment")):
            return self._format(obj.getAssignment())
        return ""

    def get_resource(self, obj, rs_obj=None):
        return obj.getResource()
