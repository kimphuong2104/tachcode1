#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=W0212,C1801

from cdb import sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.constants import kOperationModify
from cdb.objects import Forward, Reference_Methods, Reference_N, ReferenceMethods_N
from cdb.objects.core import ByID
from cdb.objects.org import Organization, Person

fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")
fOrganization = Forward("cdb.objects.org.Organization")
fResourceDemand = Forward("cs.pcs.resources.RessourceDemand")
fResourceAssignment = Forward("cs.pcs.resources.RessourceAssignment")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fOrganization2ResourcePool = Forward("cs.pcs.resources.pools.Organization2ResourcePool")
fResourcePool2Schedule = Forward("cs.pcs.resources.pools.ResourcePool2Schedule")
fResourcePoolAssignmentPerson = Forward(
    "cs.pcs.resources.pools.assignments.person.ResourcePoolAssignmentPerson"
)
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourceMember = Forward("cs.pcs.resources.pools.ResourcePoolAssignment")
fResourceSchedule = Forward("cs.pcs.resources.resourceschedule.ResourceSchedule")


def get_int_value(value):
    if not value:
        return 0
    return int(value)


@classbody
class Organization(object):

    Resources = Reference_N(
        Person,
        Person.org_id == Organization.org_id,
        Person.is_resource == 1,
        order_by="name",
    )

    ResourcePoolLinks = Reference_N(
        fOrganization2ResourcePool,
        fOrganization2ResourcePool.org_oid == Organization.cdb_object_id,
    )

    def _getResourcePools(self):
        return [o2rs.RessourcePool for o2rs in self.ResourcePoolLinks]

    ResourcePools = ReferenceMethods_N(fResourcePool, _getResourcePools)

    ResourcePoolSchedules = Reference_N(
        fResourcePool2Schedule,
        fResourcePool2Schedule.pool_oid == fOrganization.cdb_object_id,
    )

    def _allResourcePoolSchedules(self):
        result = set()
        for p in self.ResourcePoolSchedules:
            result.add(p.Schedule)
        return list(result)

    PrimaryResourceSchedules = Reference_Methods(
        fResourceSchedule, lambda self: self._allResourcePoolSchedules()
    )

    def _getSinglePool(self):
        if self.ResourcePools:
            return self.ResourcePools[0]
        return None

    ResourcePool = Reference_Methods(fResourcePool, lambda self: self._getSinglePool())

    @sig.connect(Organization, "CDBPCS_ResourceChart", "now")
    def CDBPCS_ResourceChart_now(self, ctx):
        self.show_resource_chart(ctx=ctx)

    def getPrimaryResourceSchedule(self):
        prs = self.PrimaryResourceSchedules
        if not prs:
            schedule = self.createResourceSchedule()
            self.createOrgToResourceSchedule(pool=self, schedule=schedule)
            prs = self.PrimaryResourceSchedules
            prs[0].insertObjects([self], unremovable=True)
        return prs[0]

    def createOrgToResourceSchedule(self, pool, schedule):
        kwargs = {}
        kwargs["pool_oid"] = pool.cdb_object_id
        kwargs["resource_schedule_oid"] = schedule.cdb_object_id
        return fResourcePool2Schedule.createObject(**kwargs)

    def createResourceSchedule(self):
        kwargs = {"name": self.name}
        return fResourceSchedule.createObject(**kwargs)

    def show_resource_chart(self, ctx):
        chart = self.getPrimaryResourceSchedule()
        if chart:
            chart.show_resource_chart(ctx=ctx, context=self)

    def getDemands(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getDemands(**kwargs)
        return []

    def getAssignments(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getAssignments(**kwargs)
        return []

    def getTotalDemandInPeriod(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getTotalDemandInPeriod(**kwargs)
        return 0.0

    def getTotalAssignmentInPeriod(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getTotalAssignmentInPeriod(**kwargs)
        return 0.0

    def getTotalCapacityInPeriod(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getTotalCapacityInPeriod(**kwargs)
        return 0.0

    def getCapacityPerDay(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getCapacityPerDay(**kwargs)
        return 0.0

    def getFreeCapacityInPeriod(self, **kwargs):
        mypool = self.ResourcePool
        if mypool:
            kwargs["include_sub_pools"] = kwargs["include_sub_orgs"]
            return mypool.getFreeCapacityInPeriod(**kwargs)
        return 0.0

    @classmethod
    def _getOrgBreakdownRecursive(cls, org_id):
        """
        Recursive search through the organization tree. Take an org_id and
        return the underlying organizations and their employees marked as
        resources. The result format is a triple made up of:
        - a dictionary with org_id : (set of employee ids, set of sub-org_id's)
        - a set of all the employees under the top org_id (including sub-orgs)
        - a flattened set of all the org_id's under the top org_id
        """
        # 2 SQL statements for each org_id node
        resources = sqlapi.RecordSet2(
            sql="SELECT personalnummer "
            "FROM   angestellter "
            "WHERE  org_id = '%s' "
            "  AND  is_resource = 1" % sqlapi.quote(org_id)
        )
        sub_orgs = sqlapi.RecordSet2(
            sql="SELECT org_id "
            "FROM   cdb_org "
            "WHERE  org_id_head = '%s'" % sqlapi.quote(org_id)
        )
        # First save the information from the current organization.
        org_dict = {}
        org_dict[org_id] = (
            {r.personalnummer for r in resources},
            {o.org_id for o in sub_orgs},
        )
        set_of_pers = {r.personalnummer for r in resources}
        set_of_orgs = set([org_id])
        # Then merge the information with the results from recursive calls on
        # each sub-organization
        for sub_org in org_dict[org_id][1]:
            (
                sub_orgs_dict,
                sub_set_of_pers,
                sub_set_of_orgs,
            ) = Organization._getOrgBreakdownRecursive(sub_org)
            org_dict = dict(list(org_dict.items()) + list(sub_orgs_dict.items()))
            set_of_pers |= sub_set_of_pers
            set_of_orgs |= sub_set_of_orgs
        return org_dict, set_of_pers, set_of_orgs

    @classmethod
    def getOrgBreakdown(cls, org_id):
        """
        Take an org_id and return the underlying organizations and their
        employees marked as resources. Obtain the information with
        hierarchical/recursive queries for improved efficiency under
        ORACLE/MSSQL or do a simple recursive lookup for otehr DB systems.
        The result format is a triple made up of:
        - a dictionary with org_id : (set of employee ids, set of sub-org_id's)
        - a set of all the employees under the top org_id (including sub-orgs)
        - a flattened set of all the org_id's under the top org_id
        """
        OptimizedQuery = {
            sqlapi.DBMS_ORACLE: (
                "SELECT a.personalnummer, o.org_id, o.org_id_head, o.path "
                "FROM "
                "    (SELECT org_id, org_id_head, "
                "            SYS_CONNECT_BY_PATH(org_id, '/') path "
                "     FROM   cdb_org "
                "     START WITH org_id = '%s' "
                "     CONNECT BY PRIOR org_id = org_id_head) o "
                "LEFT JOIN "
                "    (SELECT personalnummer, org_id "
                "     FROM   angestellter "
                "     WHERE  is_resource = 1) a "
                "ON  a.org_id = o.org_id " % sqlapi.quote(org_id)
            ),
            sqlapi.DBMS_MSSQL: (
                "WITH OrgTree (org_id, org_id_head, path) "
                "AS (SELECT o.org_id, o.org_id_head, "
                "           Cast('/' as varchar(8000)) + o.org_id as path "
                "    FROM   cdb_org AS o "
                "    WHERE  o.org_id = '%s' "
                "    UNION ALL "
                "    SELECT o.org_id, o.org_id_head, h.path + "
                "           Cast('/' as varchar(8000)) + o.org_id as path "
                "    FROM   cdb_org AS o "
                "    INNER JOIN OrgTree AS h "
                "    ON     o.org_id_head = h.org_id) "
                "SELECT a.personalnummer, o.org_id, o.org_id_head, o.path "
                "FROM   OrgTree as o "
                "LEFT JOIN "
                "    (SELECT personalnummer, org_id "
                "     FROM   angestellter "
                "     WHERE  is_resource = 1) as a "
                "ON  a.org_id = o.org_id " % sqlapi.quote(org_id)
            ),
        }
        DBType = sqlapi.SQLdbms()
        if DBType in OptimizedQuery:
            # Each record has an org_id, a parent org_id, the path which
            # contains information about its ancestor orgs and an employee id.
            # Some records might have a blank employee id for orgs without
            # resources. Iterate through the results and fill up the result set.
            records = sqlapi.RecordSet2(sql=OptimizedQuery[DBType])
            set_of_pers = set()
            set_of_orgs = set()
            org_dict = {}
            for record in records:
                # if personalnummer is '' or NULL, then it doesn't exist
                if record.personalnummer:
                    set_of_pers.add(record.personalnummer)
                set_of_orgs.add(record.org_id)
                if record.org_id not in org_dict:
                    org_dict[record.org_id] = (set(), set())
                    if record.personalnummer:
                        org_dict[record.org_id][0].add(record.personalnummer)
                    # if there is no parent org, then the path info is useless
                    if record.org_id_head == "":
                        continue
                    org_path = record.path.split("/")[1:]
                    # Go through the path and update the hierarchy information
                    for idx in range(len(org_path) - 1):
                        if org_path[idx] not in org_dict:
                            org_dict[org_path[idx]] = (set(), set())
                        org_dict[org_path[idx]][1].add(org_path[idx + 1])
                elif record.personalnummer:
                    org_dict[record.org_id][0].add(record.personalnummer)
            return org_dict, set_of_pers, set_of_orgs
        else:
            top_org = Organization.ByKeys(org_id)
            if top_org is not None:
                return Organization._getOrgBreakdownRecursive(org_id)
            else:
                return {}, set(), set()

    @classmethod
    def getMatchingIDsToOIDs(cls, org_ids, person_ids):
        id_match = {}
        if org_ids:
            ids = ", ".join(["'%s'" % x for x in org_ids])
            sql = "SELECT cdb_object_id, org_id FROM cdb_org WHERE org_id IN (%s)" % ids
            for rec in sqlapi.RecordSet2(sql=sql):
                id_match[rec.org_id] = rec.cdb_object_id
        if person_ids:
            ids = ", ".join(["'%s'" % x for x in person_ids])
            sql = (
                "SELECT DISTINCT cdb_object_id, personalnummer FROM angestellter WHERE personalnummer IN (%s)"
                % ids
            )
            for rec in sqlapi.RecordSet2(sql=sql):
                id_match[rec.personalnummer] = rec.cdb_object_id
        return id_match

    @classmethod
    def getOrgBreakdownByOID(cls, org_oid=None, org_id=None):
        org_dict = {}
        person_list = set()
        organization_list = set()
        myorg = ByID(org_oid) if org_oid else cls.ByKeys(org_id)
        if not myorg or not isinstance(myorg, cls):
            return org_dict, person_list, organization_list
        odict, plist, olist = cls.getOrgBreakdown(org_id=myorg.org_id)
        id_match = cls.getMatchingIDsToOIDs(org_ids=olist, person_ids=plist)
        for p in plist:
            person_list.add(id_match.get(p, p))
        for o in olist:
            organization_list.add(id_match.get(o, o))
        for key, val in odict.items():
            pl = {id_match.get(x, x) for x in val[0]}
            ol = {id_match.get(x, x) for x in val[1]}
            org_dict[id_match.get(key, key)] = (pl, ol)
        return org_dict, person_list, organization_list

    @sig.connect(Organization, "query", "pre_mask")
    @sig.connect(Organization, "requery", "pre_mask")
    @sig.connect(Organization, "create", "pre_mask")
    @sig.connect(Organization, "copy", "pre_mask")
    @sig.connect(Organization, "modify", "pre_mask")
    def _disable_resource_management(self, ctx):
        """
        The properties Resource and Resource Selection are no longer supported from version 15.3.0.
        Owner of these properties is cs.platform.org.
        Earlier versions also work with teh same version of cs.platform.org and require these properties.
        This is why the properties can not be removed yet, but we make them unusable.
        """
        ctx.set_fields_readonly(["is_resource", "is_resource_browsable"])


@classbody
class Person(object):

    Resources = Reference_N(fResource, fResource.referenced_oid == Person.cdb_object_id)

    def _getSingleResource(self):
        if self.Resources:
            return self.Resources[0]
        return None

    Resource = Reference_Methods(fResourcePool, lambda self: self._getSingleResource())

    def getDemands(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getDemands(**kwargs)
        return []

    def getAssignments(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getAssignments(**kwargs)
        return []

    def getTotalDemandInPeriod(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getTotalDemandInPeriod(**kwargs)
        return 0.0

    def getTotalAssignmentInPeriod(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getTotalAssignmentInPeriod(**kwargs)
        return 0.0

    def getTotalCapacityInPeriod(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getTotalCapacityInPeriod(**kwargs)
        return 0.0

    def getCapacityPerDay(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getCapacityPerDay(**kwargs)
        return 0.0

    def getFreeCapacityInPeriod(self, **kwargs):
        myres = self.Resource
        if myres:
            return myres.getFreeCapacityInPeriod(**kwargs)
        return 0.0

    @staticmethod
    def _check_resource(is_resource, personalnummer):
        from cs.pcs.projects.tasks import Task

        if not is_resource:
            sql = """
            SELECT cdb_demand_id AS myid FROM cdbpcs_prj_demand_v WHERE subject_id = '%s'
            AND subject_type = 'Person' AND task_status <= %s
            UNION
            SELECT cdb_alloc_id AS myid FROM cdbpcs_prj_alloc_v WHERE persno = '%s' AND status <= %s
            """ % (
                personalnummer,
                Task.EXECUTION.status,
                personalnummer,
                Task.EXECUTION.status,
            )
            result = sqlapi.RecordSet2(sql=sql)
            if len(result):
                raise ue.Exception("pcs_err_resource_flag")

    @sig.connect(Person, "copy", "post_mask")
    @sig.connect(Person, "modify", "post_mask")
    def _check_resource_field(self, ctx):
        Person._check_resource(self.is_resource, self.personalnummer)

    @staticmethod
    def _check_resource_field_for_web(hook):
        # Execute this hook only for CDB_Modify
        if not hook.get_operation_name() == kOperationModify:
            return
        vals = hook.get_new_values()
        Person._check_resource(
            vals["angestellter.is_resource"], vals["angestellter.personalnummer"]
        )

    @sig.connect(Person, "modify", "post_mask")
    def _sync_pers_on_change(self, ctx):
        Person._sync_pers(
            ctx.object["personalnummer"],
            get_int_value(ctx.dialog["is_resource"]),
        )

    @staticmethod
    def _sync_pers_on_change_for_web(hook):
        # Execute this hook only for CDB_Modify
        if not hook.get_operation_name() == kOperationModify:
            return
        vals = hook.get_new_values()
        Person._sync_pers(
            vals["angestellter.personalnummer"],
            get_int_value(vals["angestellter.is_resource"]),
        )

    @staticmethod
    def _sync_pers(personalnummer, is_resource):
        person = Person.ByKeys(personalnummer=personalnummer)
        obj = person.getPersistentObject()
        if not obj.Resource:
            return
        if person.is_resource and not is_resource and person.ActiveResourceMember:
            raise ue.Exception("cdbpcs_person_resource_assign_remove_err")
