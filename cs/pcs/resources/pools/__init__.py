# !/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com/
# pylint: disable=W0212,R0913,R0914

from cdb import cdbuuid, sqlapi, transactions, ue
from cdb.objects import Forward, Object, Reference_1, Reference_Methods, Reference_N
from cdb.objects.core import ByID
from cdb.objects.operations import operation
from cdb.objects.org import Organization
from cs.calendar import workday
from cs.tools.powerreports import WithPowerReports

# Forward declarations
fTask = Forward("cs.pcs.projects.tasks.Task")
fPerson = Forward("cdb.objects.org.Person")
fOrganization = Forward("cdb.objects.org.Organization")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fOrganization2ResourcePool = Forward("cs.pcs.resources.pools.Organization2ResourcePool")
fResourcePool2Schedule = Forward("cs.pcs.resources.pools.ResourcePool2Schedule")
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourcePoolAssignment = Forward(
    "cs.pcs.resources.pools.assignments.ResourcePoolAssignment"
)
fResourcePoolAssignmentPerson = Forward(
    "cs.pcs.resources.pools.assignments.person.ResourcePoolAssignmentPerson"
)
fResourceDemand = Forward("cs.pcs.resources.RessourceDemand")
fResourceAssignment = Forward("cs.pcs.resources.RessourceAssignment")
fResourceSchedule = Forward("cs.pcs.resources.resourceschedule.ResourceSchedule")
fResourceScheduleObject = Forward(
    "cs.pcs.resources.resourceschedule.ResourceScheduleObject"
)


class ResourcePool(Object, WithPowerReports):
    __classname__ = "cdbpcs_resource_pool"
    __maps_to__ = "cdbpcs_resource_pool"

    ResourcePoolSchedules = Reference_N(
        fResourcePool2Schedule,
        fResourcePool2Schedule.pool_oid == fResourcePool.cdb_object_id,
    )
    ResourceScheduleOccurrences = Reference_N(
        fResourceScheduleObject,
        fResourceScheduleObject.content_oid == fResourcePool.cdb_object_id,
    )
    ParentPool = Reference_1(fResourcePool, fResourcePool.parent_oid)
    SubPools = Reference_N(
        fResourcePool, fResourcePool.parent_oid == fResourcePool.cdb_object_id
    )
    PoolAssignments = Reference_N(
        fResourcePoolAssignment,
        fResourcePoolAssignment.pool_oid == fResourcePool.cdb_object_id,
    )
    # Demands = Reference_N(fResourceDemand, fResourceDemand.pool_oid == fResourcePool.cdb_object_id)
    # Assignments = Reference_N(fResourceAssignment, fResourceAssignment.pool_oid == fResourcePool.cdb_object_id)

    def getPoolAssignments(self, start=None, end=None):
        start_sql = sqlapi.SQLdbms_date(start)
        end_sql = sqlapi.SQLdbms_date(end)
        return fResourcePoolAssignment.Query(
            "pool_oid = '{oid}'"
            " AND (start_date IS NULL OR start_date <= {end} OR assign_start_date <= {end})"
            " AND (end_date IS NULL OR end_date >= {start} OR assign_end_date >= {start})".format(
                oid=self.cdb_object_id, start=start_sql, end=end_sql
            ),
            order_by=["start_date"],
        )

    def _allResourcePoolSchedules(self):
        result = set()
        for p in self.ResourcePoolSchedules:
            result.add(p.Schedule)
        return list(result)

    PrimaryResourceSchedules = Reference_Methods(
        fResourceSchedule, lambda self: self._allResourcePoolSchedules()
    )

    def _allResourcePools(self):
        result = [self]
        for p in self.SubPools:
            result += p._allResourcePools()
        return result

    AllResourcePools = Reference_Methods(
        fResourcePool, lambda self: self._allResourcePools()
    )

    def _allParentPools(self):
        result = [self]
        if self.ParentPool:
            result += self.ParentPool._allParentPools()
        return result

    AllParentPools = Reference_Methods(
        fResourcePool, lambda self: self._allParentPools()
    )

    def _getResources(self):
        result = set()
        for a in self.PoolAssignments:
            result.add(a.Resource)
        return list(result)

    Resources = Reference_Methods(fResource, lambda self: self._getResources())

    def _allResources(self):
        result = set()
        for p in self.AllResourcePools:
            for a in p.PoolAssignments:
                result.add(a.Resource)
        return list(result)

    AllResources = Reference_Methods(fResource, lambda self: self._allResources())

    def _getReferencedObject(self):
        if self.referenced_oid:
            return ByID(self.referenced_oid)
        return None

    ReferencedObject = Reference_Methods(
        Object, lambda self: self._getReferencedObject()
    )

    @classmethod
    def on_create_basic_pools_now(cls, ctx):
        Organization.on_create_basic_pools_now(ctx=ctx)

    def createPoolToResourceSchedule(self, pool, schedule):
        kwargs = {}
        kwargs["pool_oid"] = pool.cdb_object_id
        kwargs["resource_schedule_oid"] = schedule.cdb_object_id
        return fResourcePool2Schedule.createObject(**kwargs)

    def createResourceSchedule(self):
        kwargs = {"name": self.name}
        return fResourceSchedule.createObject(**kwargs)

    def getPrimaryResourceSchedule(self):
        prs = self.PrimaryResourceSchedules
        if not prs:
            schedule = self.createResourceSchedule()
            self.createPoolToResourceSchedule(pool=self, schedule=schedule)
            prs = self.PrimaryResourceSchedules
            prs[0].insertObjects([self], unremovable=True)
        return prs[0]

    def on_CDBPCS_ResourceChart_now(self, ctx):
        self.show_resource_chart(ctx=ctx)

    def show_resource_chart(self, ctx):
        chart = self.getPrimaryResourceSchedule()
        if chart:
            chart.show_resource_chart(ctx=ctx, context=self)

    def containsResource(self, res):
        if isinstance(res, str):
            res = fResource.ByKeys(res)
        if res in self.AllResources:
            return True
        return False

    def on_create_post(self, ctx):
        if ctx.dragdrop_op_count > 0:
            oid = ctx.dragged_obj["cdb_object_id"]
            with transactions.Transaction():
                template = fResourcePool.ByKeys(oid)
                for pool in template.SubPools:
                    pool._copy_pool(ctx, parent_oid=self.cdb_object_id)
                self.Reload()

    def _copy_pool(self, ctx, parent_oid=""):
        new_pool_check = ResourcePool(**self._record)
        new_pool_check.parent_oid = parent_oid

        # Create a new UUID for the copied task object
        new_pool_check.cdb_object_id = cdbuuid.create_uuid()

        # Create a new pool object and write it into database
        new_pool_check.Update(**ResourcePool.MakeChangeControlAttributes())
        new_pool = ResourcePool.Create(**new_pool_check)

        # Copy sub-pools recursively
        for pool in self.SubPools:
            pool._copy_pool(ctx, parent_oid=new_pool.cdb_object_id)
        new_pool.Reload()

    @classmethod
    def createObject(cls, **kwargs):
        return operation("CDB_Create", cls, **kwargs)

    def modifyObject(self, **kwargs):
        return operation("CDB_Modify", self, **kwargs)

    def deleteObject(self):
        operation("CDB_Delete", self)

    def getDemands(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_covered=False,
        include_resources=True,
        include_sub_pools=True,
        all_status=False,
        **kargs
    ):
        """
        liefert alle Bedarfe, die den Aufrufparametern entsprechen:

        start_date und end_date (vom Typ datetime) begrenzen, falls angegeben den Auswertungszeitraum
        prj_rule  beinhaltet eine (Projekt-)Regel, nach der die auszuwertenden Projekte bestimmt werden.
        with_prj_ids beinhaltet die cdb_project_id von allen Projekten die manuell in die Berechnung mit einbezogen
        werden sollen (selbst wenn sie nicht der übergebenen Regel entsprechen)
        without_prj_ids beinhaltet die cdb_project_id von allen Projekten die manuell von der Berechnung
        ausgeschlossen werden sollen (selbst wenn sie der übergebenen Regel entsprechen würden)
        include_covered:
         - Sollen auch Bedarfe einbezogen werden, die bereits komplett durch Zuweisungen abgedeckt sind?
         - True: liefere alle Bedarfe (inklusive all derjenigen, die durch Zuweisungen komplett abgedeckt wurden)
         - False: liefere nur die ungedeckten Bedarfe
         (diejenigen, die durch Zuweisungen nicht komplett abgedeckt wurden)
        include_resources:
         - Schließe in die Auswertung auch alle zugeordneten Ressourcen ein?
        include_sub_pools:
         - Führe die Auswertung rekursiv auf allen untergeordneten Ressourcenpools aus?
        """
        if not prj_rule and not with_prj_ids:
            return []
        pool_dict, res_list, pool_list = ResourcePool.getPoolBreakdown(
            self.cdb_object_id, start=start_date, end=end_date
        )
        if not res_list and not pool_list:
            return []

        # basic statement
        sqlSelect = "SELECT cdbpcs_prj_demand.*, cdbpcs_task.position"
        sqlFrom = " FROM cdbpcs_prj_demand, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_task.milestone != 1"
            " AND cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
        )
        if not all_status:
            sqlWhere += " AND {}".format(
                fTask.get_condition_of_StatusForResourceEvaluation()
            )

        if not include_covered:
            sqlWhere += " AND cdbpcs_prj_demand.coverage = 0"

        # evaluate time frame
        if start_date and end_date:
            sd = sqlapi.SQLdbms_date(start_date)
            ed = sqlapi.SQLdbms_date(end_date)
            sqlWhere += (
                " AND (%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "cdbpcs_task.%s <= %s AND %s <= cdbpcs_task.%s)"
                % (
                    sd,
                    fTask.getDemandStartTimeFieldName(),
                    fTask.getDemandStartTimeFieldName(),
                    ed,
                    sd,
                    fTask.getDemandEndTimeFieldName(),
                    fTask.getDemandEndTimeFieldName(),
                    ed,
                    fTask.getDemandStartTimeFieldName(),
                    sd,
                    ed,
                    fTask.getDemandEndTimeFieldName(),
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_demand.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, prj_rule.expr(cls))
            )
        if with_prj_ids:
            sqlWithPrj = "cdbpcs_prj_demand.cdb_project_id IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in with_prj_ids]
            )
        if without_prj_ids:
            sqlWithoutPrj = "cdbpcs_prj_demand.cdb_project_id NOT IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in without_prj_ids]
            )
        sqlWhere += " AND (%s OR %s) AND %s" % (sqlPrjRule, sqlWithPrj, sqlWithoutPrj)

        # evaluate pool and resource parameters
        if not include_sub_pools:
            pool_list = [self.cdb_object_id]
            res_list = pool_dict[self.cdb_object_id][0]
        sqlPool = "cdbpcs_prj_demand.pool_oid IN (%s)" % ",".join(
            ["'%s'" % sqlapi.quote(x) for x in pool_list]
        )
        sqlRes = "1=0"
        if include_resources and res_list:
            sqlRes = "(cdbpcs_prj_demand.resource_oid IN (%s))" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in res_list]
            )
        sqlWhere += " AND (%s OR %s)" % (sqlPool, sqlRes)
        sqlOrder = " ORDER BY cdbpcs_prj_demand.coverage, cdbpcs_prj_demand.cdb_project_id, cdbpcs_task.position"

        # send statement
        return fResourceDemand.SQL(sqlSelect + sqlFrom + sqlWhere + sqlOrder)

    def getAssignments(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_resources=True,
        include_sub_pools=True,
        all_status=False,
        **kargs
    ):
        if not prj_rule and not with_prj_ids:
            return []
        pool_dict, res_list, pool_list = ResourcePool.getPoolBreakdown(
            self.cdb_object_id, start=start_date, end=end_date
        )
        if not res_list and not pool_list:
            return []

        # basic statement
        sqlSelect = "SELECT cdbpcs_prj_alloc.*, cdbpcs_task.position"
        sqlFrom = " FROM cdbpcs_prj_alloc, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_task.milestone != 1"
            " AND cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
        )
        if not all_status:
            sqlWhere += " AND {}".format(
                fTask.get_condition_of_StatusForResourceEvaluation()
            )

        # evaluate time frame
        if start_date and end_date:
            sd = sqlapi.SQLdbms_date(start_date)
            ed = sqlapi.SQLdbms_date(end_date)
            sqlWhere += (
                " AND (%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "cdbpcs_task.%s <= %s AND %s <= cdbpcs_task.%s)"
                % (
                    sd,
                    fTask.getAssignmentStartTimeFieldName(),
                    fTask.getAssignmentStartTimeFieldName(),
                    ed,
                    sd,
                    fTask.getAssignmentEndTimeFieldName(),
                    fTask.getAssignmentEndTimeFieldName(),
                    ed,
                    fTask.getAssignmentStartTimeFieldName(),
                    sd,
                    ed,
                    fTask.getAssignmentEndTimeFieldName(),
                )
            )

        # evaluate parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_alloc.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, prj_rule.expr(cls))
            )
        if with_prj_ids:
            sqlWithPrj = "cdbpcs_prj_alloc.cdb_project_id IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in with_prj_ids]
            )
        if without_prj_ids:
            sqlWithoutPrj = "cdbpcs_prj_alloc.cdb_project_id NOT IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in without_prj_ids]
            )
        sqlWhere += " AND (%s OR %s) AND %s" % (sqlPrjRule, sqlWithPrj, sqlWithoutPrj)

        # evaluate pool and resource parameters
        if not include_sub_pools:
            pool_list = [self.cdb_object_id]
            res_list = pool_dict[self.cdb_object_id][0]
        sqlOrg = "cdbpcs_prj_alloc.pool_oid IN (%s)" % ",".join(
            ["'%s'" % sqlapi.quote(x) for x in pool_list]
        )
        sqlRes = "1=0"
        if include_resources and res_list:
            sqlRes = "cdbpcs_prj_alloc.resource_oid IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in res_list]
            )
        sqlWhere += " AND (%s OR %s)" % (sqlOrg, sqlRes)
        sqlOrder = " ORDER BY cdbpcs_prj_alloc.cdb_project_id, cdbpcs_task.position"

        # send statement
        return fResourceAssignment.SQL(sqlSelect + sqlFrom + sqlWhere + sqlOrder)

    def getTotalDemandInPeriod(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_covered=False,
        include_resources=True,
        include_sub_pools=True,
        **kargs
    ):
        load = 0.0
        for demand in self.getDemands(
            start_date=start_date,
            end_date=end_date,
            prj_rule=prj_rule,
            with_prj_ids=with_prj_ids,
            without_prj_ids=without_prj_ids,
            include_covered=include_covered,
            include_resources=include_resources,
            include_sub_pools=include_sub_pools,
        ):
            hours = demand.hours
            if not include_covered and hours:
                hours = demand.demandRemainderInHours()
            task = demand.Task
            duration_total = task.getWorkdays()
            duration_period = task.getWorkdaysInPeriod(start_date, end_date)
            if duration_total and duration_period and hours:
                load += float(duration_period) / duration_total * hours
        return load

    def getTotalAssignmentInPeriod(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_resources=True,
        include_sub_pools=True,
        **kargs
    ):
        load = 0.0
        for assign in self.getAssignments(
            start_date=start_date,
            end_date=end_date,
            prj_rule=prj_rule,
            with_prj_ids=with_prj_ids,
            without_prj_ids=without_prj_ids,
            include_resources=include_resources,
            include_sub_pools=include_sub_pools,
        ):
            task = assign.Task
            duration_total = task.getWorkdays()
            duration_period = task.getWorkdaysInPeriod(start_date, end_date)
            if duration_total and duration_period and assign.hours:
                load += float(duration_period) / duration_total * assign.hours
        return load

    def getTotalCapacityInPeriod(
        self, start_date, end_date, include_resources=True, include_sub_pools=True
    ):
        return self.getCapacityPerDay(
            include_resources=include_resources, include_sub_pools=include_sub_pools
        ) * len(workday.workdays(start_date, end_date))

    def getCapacityPerDay(
        self, include_resources=True, include_sub_pools=True, **kargs
    ):
        capa = 0.0
        if include_resources:
            for res in self.Resources:
                capa += res.getCapacityPerDay()
        if include_sub_pools:
            for sub in self.SubOrganizations:
                capa += sub.getCapacityPerDay()
        return capa

    def getFreeCapacityInPeriod(
        self,
        start_date,
        end_date,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_resources=True,
        include_sub_pools=True,
        **kargs
    ):
        return (
            self.getTotalCapacityInPeriod(
                start_date=start_date,
                end_date=end_date,
                include_resources=include_resources,
                include_sub_pools=include_sub_pools,
            )
            - self.getTotalDemandInPeriod(
                start_date=start_date,
                end_date=end_date,
                prj_rule=prj_rule,
                with_prj_ids=with_prj_ids,
                without_prj_ids=without_prj_ids,
                include_resources=include_resources,
                include_sub_pools=include_sub_pools,
            )
            - self.getTotalAssignmentInPeriod(
                start_date=start_date,
                end_date=end_date,
                prj_rule=prj_rule,
                with_prj_ids=with_prj_ids,
                without_prj_ids=without_prj_ids,
                include_resources=include_resources,
                include_sub_pools=include_sub_pools,
            )
        )

    @classmethod
    def _getPoolBreakdownRecursive(cls, pool_oid, start=None, end=None):
        """
        Recursive search through the resource pool tree. Take an pool_oid and
        return the underlying pools and their resources.
        The result format is a triple made up of:
        - a dictionary with pool_oid : (set of resource_oids, set of sub-pool_oids)
        - a set of all the resources under the top pool_oid (including sub-pools)
        - a flattened set of all the pool_oid's under the top pool_oid
        """
        # 2 SQL statements for each pool_oid node
        sql = (
            "SELECT cdb_object_id AS assignment_oid FROM cdbpcs_pool_assignment "
            "WHERE pool_oid = '%s'" % sqlapi.quote(pool_oid)
        )
        if start and end:
            sql += (
                " AND (start_date IS NULL OR start_date <= {end} OR assign_start_date <= {end})"
                " AND (end_date IS NULL OR end_date >= {start} OR assign_end_date >= {start})".format(
                    start=start, end=end
                )
            )

        resources = sqlapi.RecordSet2(sql=sql)
        sql = (
            "SELECT cdb_object_id FROM cdbpcs_resource_pool "
            "WHERE parent_oid = '%s'" % sqlapi.quote(pool_oid)
        )
        sub_pools = sqlapi.RecordSet2(sql=sql)
        # First save the information from the current organization.
        pool_dict = {}
        pool_dict[pool_oid] = (
            {r.assignment_oid for r in resources},
            {o.cdb_object_id for o in sub_pools},
        )
        set_of_res = {r.assignment_oid for r in resources}
        set_of_pools = set([pool_oid])
        # Then merge the information with the results from recursive calls on
        # each sub-organization
        for sub_pool in pool_dict[pool_oid][1]:
            (
                sub_pool_dict,
                sub_set_of_res,
                sub_set_of_orgs,
            ) = ResourcePool._getPoolBreakdownRecursive(sub_pool, start=start, end=end)
            pool_dict = dict(list(pool_dict.items()) + list(sub_pool_dict.items()))
            set_of_res |= sub_set_of_res
            set_of_pools |= sub_set_of_orgs
        return pool_dict, set_of_res, set_of_pools

    @classmethod
    def getPoolBreakdown(cls, pool_oid, start=None, end=None):
        """
        Take an pool_oid and return the underlying pools and their
        resources. Obtain the information with
        hierarchical/recursive queries for improved efficiency under
        ORACLE/MSSQL or do a simple recursive lookup for other DB systems.
        The result format is a triple made up of:
        - a dictionary with pool_oid : (set of resource_oids, set of sub-pool_oids)
        - a set of all the resources under the top pool_oid (including sub-pools)
        - a flattened set of all the pool_oids under the top pool_oid
        """
        # first check, if given pool_oid matches to an organization
        pool_dict, set_of_res, set_of_pools = Organization.getOrgBreakdownByOID(
            org_oid=pool_oid
        )
        if pool_dict:
            return pool_dict, set_of_res, set_of_pools

        timeframe = ""
        if start and end:
            start = sqlapi.SQLdbms_date(start)
            end = sqlapi.SQLdbms_date(end)
            timeframe = (
                "WHERE (start_date IS NULL OR start_date <= {end} OR assign_start_date <= {end})"
                "AND (end_date IS NULL OR end_date >= {start} OR assign_end_date >= {start})".format(
                    start=start, end=end
                )
            )

        # continue with search for regular pool
        OptimizedQuery = {
            sqlapi.DBMS_ORACLE: (
                """
                 SELECT a.resource_oid, a.assignment_oid, o.pool_oid, o.parent_oid, o.path
                 FROM
                     (SELECT cdb_object_id AS pool_oid, parent_oid,
                             SYS_CONNECT_BY_PATH(cdb_object_id, '/') path
                      FROM   cdbpcs_resource_pool
                      START WITH cdb_object_id = '%s'
                      CONNECT BY PRIOR cdb_object_id = parent_oid) o
                 LEFT JOIN
                     (SELECT resource_oid, cdb_object_id AS assignment_oid, pool_oid
                      FROM   cdbpcs_pool_assignment %s) a
                 ON  a.pool_oid = o.pool_oid """
                % (sqlapi.quote(pool_oid), timeframe)
            ),
            sqlapi.DBMS_MSSQL: (
                """
                 WITH PoolTree (pool_oid, parent_oid, path)
                 AS (SELECT o.cdb_object_id AS pool_oid, o.parent_oid,
                            Cast('/' as VARCHAR(8000)) + o.cdb_object_id AS path
                     FROM   cdbpcs_resource_pool AS o
                     WHERE  o.cdb_object_id = '%s'
                     UNION ALL
                     SELECT o.cdb_object_id AS pool_oid, o.parent_oid, h.path +
                            Cast('/' as VARCHAR(8000)) + o.cdb_object_id AS path
                     FROM   cdbpcs_resource_pool AS o
                     INNER JOIN PoolTree AS h
                     ON     o.parent_oid = h.pool_oid)
                 SELECT a.resource_oid, a.assignment_oid, o.pool_oid, o.parent_oid, o.path
                 FROM   PoolTree AS o
                 LEFT JOIN
                     (SELECT resource_oid, cdb_object_id AS assignment_oid, pool_oid
                      FROM   cdbpcs_pool_assignment %s) AS a
                 ON  a.pool_oid = o.pool_oid """
                % (sqlapi.quote(pool_oid), timeframe)
            ),
        }
        DBType = sqlapi.SQLdbms()
        if DBType in OptimizedQuery:
            # Each record has a pool_oid, a parent_oid, the path which
            # contains information about its ancestor pools and a resource_oid.
            # Some records might have a blank resource_oid for pools without
            # resources. Iterate through the results and fill up the result set.
            records = sqlapi.RecordSet2(sql=OptimizedQuery[DBType])
            set_of_res = set()
            set_of_pools = set()
            pool_dict = {}
            for r in records:
                # if assignment_oid is '' or NULL, then it doesn't exist
                if r.assignment_oid:
                    set_of_res.add(r.assignment_oid)
                set_of_pools.add(r.pool_oid)
                if r.pool_oid not in pool_dict:
                    pool_dict[r.pool_oid] = (set(), set())
                    if r.assignment_oid:
                        pool_dict[r.pool_oid][0].add(r.assignment_oid)
                    # if there is no parent pool, then the path info is useless
                    if r.parent_oid == "":
                        continue
                    pool_path = r.path.split("/")[1:]
                    # Go through the path and update the hierarchy information
                    for idx in range(len(pool_path) - 1):
                        if pool_path[idx] not in pool_dict:
                            pool_dict[pool_path[idx]] = (set(), set())
                        pool_dict[pool_path[idx]][1].add(pool_path[idx + 1])
                elif r.assignment_oid:
                    pool_dict[r.pool_oid][0].add(r.assignment_oid)
            return pool_dict, set_of_res, set_of_pools
        else:
            top_pool = ResourcePool.ByKeys(pool_oid)
            if top_pool:
                return ResourcePool._getPoolBreakdownRecursive(pool_oid, start, end)
            return {}, set(), set()

    def manage_browser_root(self, ctx):
        if not self.parent_oid and not self.browser_root:
            self.browser_root = True
        elif self.parent_oid and self.browser_root:
            self.browser_root = False

    def preset_values(self, ctx):
        if self.parent_oid:
            ctx.set("browser_root", False)
            ctx.set("bookable", True)

    def _delete_confirmation(self, ctx, message_box_argument_name):
        """
        If more than one sub resource pools exists or more than one member exists,
        The user must confirm that sub resource pools and resource members are also deleted (recursive deletion)
        """
        sub_pools = len(self.SubPools)
        pool_members = len(self.PoolAssignments)
        if not sub_pools and not pool_members:
            return
        message_box = ctx.MessageBox(
            "cdbpcs_resourcepool_delete_confirmation",
            [sub_pools, pool_members],
            message_box_argument_name,
            ctx.MessageBox.kMsgBoxIconQuestion,
        )
        message_box.addButton(
            ctx.MessageBoxButton(
                "ok",  # E041570
                ctx.MessageBox.kMsgBoxResultYes,
                ctx.MessageBoxButton.kButtonActionCallServer,
                is_dflt=0,
            )
        )
        message_box.addCancelButton(is_dflt=1)
        ctx.show_message(message_box)

    def manage_deletion(self, ctx):
        """
        Todo: Resource Pool can not be deleted if members are used as resource demands or resource allocations
        The user must confirm that sub resource pools and resource members are also deleted (recursive deletion)
        """
        message_box_argument_name = "delete_confirmation"
        if message_box_argument_name not in ctx.dialog.get_attribute_names():
            self._delete_confirmation(ctx, message_box_argument_name)

    def validate_parent_pool(self, ctx):
        # Chosen parent pool is not allowed to be part of new pool's substructure
        # or to be the pool itself
        parent_oid = ctx.dialog["parent_oid"]
        if parent_oid:
            subpool_oids = [sp.cdb_object_id for sp in self.AllResourcePools]
            if parent_oid in subpool_oids:
                raise ue.Exception("cdbpcs_resource_pool_recursive")

    event_map = {
        (("create", "copy"), "pre_mask"): "preset_values",
        (("create", "copy", "modify"), "pre"): "manage_browser_root",
        (("copy", "modify"), "pre"): "validate_parent_pool",
        ("delete", "pre"): "manage_deletion",
    }


class ResourcePool2Schedule(Object):
    __maps_to__ = "cdbpcs_pool2res_schedule"

    ResourcePool = Reference_1(fResourcePool, fResourcePool2Schedule.pool_oid)
    OrganizationPool = Reference_1(fResourcePool, fOrganization.cdb_object_id)
    Schedule = Reference_1(
        fResourceSchedule, fResourcePool2Schedule.resource_schedule_oid
    )

    def getPool(self):
        return self.ResourcePool if self.ResourcePool else self.OrganizationPool

    @classmethod
    def createObject(cls, **kwargs):
        return operation("CDB_Create", cls, **kwargs)


class Organization2ResourcePool(Object):
    __maps_to__ = "cdbpcs_org2resource_pool"

    Organization = Reference_1(
        fOrganization, fOrganization.cdb_object_id == fOrganization2ResourcePool.org_oid
    )
    RessourcePool = Reference_1(fResourcePool, fOrganization2ResourcePool.pool_oid)

    def check_unique_org(self, ctx):
        if len(  # pylint: disable=C1801
            Organization2ResourcePool.KeywordQuery(org_oid=ctx.dialog.org_oid)
        ):
            raise ue.Exception("cdbpcs_org2pool_uniq")

    event_map = {(("create", "copy"), "post_mask"): "check_unique_org"}
