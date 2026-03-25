#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import cdbuuid, sqlapi, transactions
from cdb.comparch import protocol

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

CREATE_ORG_POOLS = True


class CheckConsistencyOfPersonsData(object):
    def run(self):

        detail = ""
        inconsistent_data = sqlapi.RecordSet2(
            "angestellter", "is_resource=1 AND (capacity=0 OR capacity IS NULL)"
        )
        for record in inconsistent_data:
            record.update(capacity=0.01)
            detail = (
                "{} The capacity of user {} ({}) has been automatically set to 0.01 hr."
                " because it was marked as a resource.\n".format(
                    detail, record.name, record.personalnummer
                )
            )

        if detail:
            message = (
                "The capacity of some persons has been automatically set to the value 0.01."
                "Please check the master data of the corresponding persons."
                "For more information refer to field Details."
            )
            protocol.logWarning(message, details_longtext=detail)


class CreateResourceObjects(object):
    def run(self):
        res_to_be_migrated = sqlapi.RecordSet2("angestellter", "is_resource=1")
        tbm = len(sqlapi.RecordSet2("angestellter", "is_resource=1"))
        self.create_resources(res_to_be_migrated)
        tbi = len(sqlapi.RecordSet2("cdbpcs_resource"))

        status = "Ok" if tbm == tbi else "TO BE CHECKED"
        details = (
            "%s users to be migrated\n"
            "%s resources exist\n"
            "...%s." % (tbm, tbi, status)
        )
        if status == "Ok":
            protocol.logMessage(
                "Migration from user to resources", details_longtext=details
            )
        else:
            protocol.logWarning(
                "Migration from user to resources", details_longtext=details
            )

    def create_resources(self, records):
        with transactions.Transaction():
            for record in records:
                exists = len(
                    sqlapi.RecordSet2(
                        "cdbpcs_resource",
                        "referenced_oid = '{}'".format(record.cdb_object_id),
                    )
                )
                if exists:
                    continue
                args = {
                    "cdb_object_id": cdbuuid.create_uuid(),
                    "relation": "cdbpcs_resource",
                    "name": sqlapi.quote(record.name) if record.name else "",
                    "capacity": record.capacity if record.capacity else 0,
                    "referenced_oid": record.cdb_object_id,
                    "calendar_profile_id": record.calendar_profile_id,
                }
                self._create(**args)

    def _create(self, relation, **args):
        oid = args["cdb_object_id"]
        keys = ", ".join(list(args))
        values = ", ".join(
            [
                "'%(" + x + ")s'"
                if isinstance(args[x], (str, str))
                else "%(" + x + ")s"
                for x in list(args)
            ]
        )
        sqlapi.SQLinsert("INTO %s (%s) VALUES (%s)" % (relation, keys, values) % args)
        sqlapi.SQLinsert(
            "INTO cdb_object (id, relation) VALUES ('%s', '%s')" % (oid, relation)
        )


class CreatePoolStructureByOrgStructure(object):
    """
    Set cdbpcs_resource_pools according to structure of organizations marked as resources.
    Set cdbpcs_resource according to persons/users marked as resources.
    """

    def run(self):
        # Previous data basis
        prev_resource_pools = len(sqlapi.RecordSet2("cdbpcs_resource_pool"))
        prev_pool_assignments = len(sqlapi.RecordSet2("cdbpcs_pool_assignment"))
        # Data to be migrated
        orgs_to_be_migrated = len(
            sqlapi.RecordSet2("cdb_org", "is_resource=1 OR is_resource_browsable=1")
        )
        res_to_be_migrated = len(sqlapi.RecordSet2("angestellter", "is_resource=1"))
        sql = """SELECT 1 FROM angestellter
                 JOIN cdb_org ON cdb_org.org_id = angestellter.org_id
                  WHERE angestellter. is_resource=1
                  AND (cdb_org.is_resource=1 or cdb_org.is_resource_browsable=1)"""
        res_assg_to_be_migrated = len(sqlapi.RecordSet2(sql=sql))
        # running migration
        with transactions.Transaction():
            orgs = sqlapi.RecordSet2(sql="SELECT * FROM cdb_org where org_id_head = ''")
            for myorg in orgs:
                self._createPoolByOrg(myorg)
        # Current data
        curr_resource_pools = len(sqlapi.RecordSet2("cdbpcs_resource_pool"))
        curr_resources = len(sqlapi.RecordSet2("cdbpcs_resource"))
        curr_pool_assignments = len(sqlapi.RecordSet2("cdbpcs_pool_assignment"))

        # Summary
        status = (
            "Ok"
            if curr_resource_pools - prev_resource_pools == orgs_to_be_migrated
            else "TO BE CHECKED"
        )
        details = (
            "%s organizations to be migrated\n"
            "%s resource pools have been found before migration\n"
            "%s resource pools added\n"
            "...%s."
            % (
                orgs_to_be_migrated,
                prev_resource_pools,
                curr_resource_pools - prev_resource_pools,
                status,
            )
        )
        if status == "Ok":
            protocol.logMessage(
                "Migration from organization to resource pools",
                details_longtext=details,
            )
        else:
            protocol.logWarning(
                "Migration from organization to resource pools",
                details_longtext=details,
            )

        status = "Ok" if curr_resources == res_to_be_migrated else "TO BE CHECKED"
        details = (
            "%s users to be migrated\n"
            "%s resources exist\n"
            "...%s." % (res_to_be_migrated, curr_resources, status)
        )
        if status == "Ok":
            protocol.logMessage(
                "Migration from user to resources", details_longtext=details
            )
        else:
            protocol.logWarning(
                "Migration from user to resources", details_longtext=details
            )

        status = (
            "Ok"
            if curr_pool_assignments - prev_pool_assignments == res_assg_to_be_migrated
            else "TO BE CHECKED"
        )
        details = (
            "%s users to be migrated\n"
            "%s pool assignemnts have been found before migration\n"
            "%s pool assignemnts added\n"
            "...%s."
            % (
                res_assg_to_be_migrated,
                prev_pool_assignments,
                curr_pool_assignments - prev_pool_assignments,
                status,
            )
        )
        if status == "Ok":
            protocol.logMessage(
                "Migration from user to pool assignment", details_longtext=details
            )
        else:
            protocol.logWarning(
                "Migration from user to pool assignment", details_longtext=details
            )

    def _createPoolByOrg(self, obj, parent_pool_oid=None):
        oid = ""
        args = {}
        args["relation"] = "cdbpcs_resource_pool"
        args["parent_oid"] = parent_pool_oid if parent_pool_oid else ""
        args["cdb_object_id"] = oid
        args["name"] = sqlapi.quote(obj.name) if obj.name else ""
        args["bookable"] = 1 if obj.is_resource else 0
        args["browser_root"] = 1 if obj.is_resource_browsable else 0
        if CREATE_ORG_POOLS and (obj.is_resource or obj.is_resource_browsable):
            oid = cdbuuid.create_uuid()
            args["cdb_object_id"] = oid
            self._create(**args)
        # loop over sub organizations
        for o in sqlapi.RecordSet2(
            sql="SELECT * FROM cdb_org WHERE org_id_head = '%s'"
            % sqlapi.quote(obj.org_id)
        ):
            self._createPoolByOrg(o, args["cdb_object_id"])
        # All persons, whether the organization is marked as a resource or not
        for r in sqlapi.RecordSet2(
            sql="SELECT * FROM angestellter WHERE org_id = '%s' AND is_resource = 1"
            % sqlapi.quote(obj.org_id)
        ):
            self._createResourceByPerson(r, args["cdb_object_id"])
        # Set the mandatory field start date of pool assignemnts with the value of the calendar start
        sql = """update cdbpcs_pool_assignment
                    set start_date =
                    (select valid_from from cdb_calendar_profile
                    join angestellter
                    on angestellter.calendar_profile_id = cdb_calendar_profile.cdb_object_id
                    where cdbpcs_pool_assignment.person_id = angestellter.personalnummer)
                  where cdbpcs_pool_assignment.start_date is NULL
        """
        sqlapi.SQL(sql)

    def _createResourceByPerson(self, obj, parent_pool_oid):
        res = sqlapi.RecordSet2(
            sql="SELECT * FROM cdbpcs_resource WHERE referenced_oid = '%s'"
            % sqlapi.quote(obj.cdb_object_id)
        )
        oid = ""
        if res:
            oid = res[0].cdb_object_id
        else:
            oid = cdbuuid.create_uuid()
            args = {}
            args["relation"] = "cdbpcs_resource"
            args["cdb_object_id"] = oid
            args["name"] = sqlapi.quote(obj.name) if obj.name else ""
            args["capacity"] = obj.capacity if obj.capacity else 0
            args["referenced_oid"] = obj.cdb_object_id
            args["calendar_profile_id"] = obj.calendar_profile_id
            self._create(**args)

        if CREATE_ORG_POOLS and parent_pool_oid:
            args = {}
            args["relation"] = "cdbpcs_pool_assignment"
            args["cdb_object_id"] = cdbuuid.create_uuid()
            args["pool_oid"] = parent_pool_oid
            args["resource_oid"] = oid
            args["capacity"] = obj.capacity
            args["person_id"] = obj.personalnummer
            args["cdb_classname"] = "cdbpcs_pool_person_assign"
            self._create(**args)

    def _create(self, relation, **args):
        oid = args["cdb_object_id"]
        keys = ", ".join(list(args))
        values = ", ".join(
            [
                "'%(" + x + ")s'"
                if isinstance(args[x], (str, str))
                else "%(" + x + ")s"
                for x in list(args)
            ]
        )
        sqlapi.SQLinsert("INTO %s (%s) VALUES (%s)" % (relation, keys, values) % args)
        sqlapi.SQLinsert(
            "INTO cdb_object (id, relation) VALUES ('%s', '%s')" % (oid, relation)
        )


class AdjustDemands(object):
    """Set pool_oids for cdbpcs_prj_demand."""

    def run(self):
        sqlapi.SQLupdate(
            """cdbpcs_prj_demand SET pool_oid =
                (SELECT cdbpcs_resource_pool.cdb_object_id FROM cdb_org, cdbpcs_resource_pool
                 WHERE cdb_org.name = cdbpcs_resource_pool.name
                 AND cdbpcs_prj_demand.org_id = cdb_org.org_id)
                 WHERE cdbpcs_prj_demand.org_id != ''
                 AND cdbpcs_prj_demand.org_id IS NOT NULL"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_prj_demand SET resource_oid =
                (SELECT resource_oid FROM cdbpcs_pool_assignment
                 WHERE cdbpcs_prj_demand.subject_id = cdbpcs_pool_assignment.person_id)
                 WHERE cdbpcs_prj_demand.subject_id != ''
                 AND cdbpcs_prj_demand.subject_id IS NOT NULL"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_prj_demand SET assignment_oid =
                (SELECT cdb_object_id FROM cdbpcs_pool_assignment
                 WHERE cdbpcs_prj_demand.subject_id = cdbpcs_pool_assignment.person_id)
                 WHERE cdbpcs_prj_demand.subject_id != ''
                 AND cdbpcs_prj_demand.subject_id IS NOT NULL"""
        )


class AdjustAssignments(object):
    """Set pool_oids for cdbpcs_prj_alloc."""

    def run(self):
        sqlapi.SQLupdate(
            """cdbpcs_prj_alloc SET pool_oid =
                (SELECT cdbpcs_resource_pool.cdb_object_id FROM cdb_org, cdbpcs_resource_pool
                 WHERE cdb_org.name = cdbpcs_resource_pool.name
                 AND cdbpcs_prj_alloc.org_id = cdb_org.org_id)
                 WHERE cdbpcs_prj_alloc.org_id != ''
                 AND cdbpcs_prj_alloc.org_id IS NOT NULL"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_prj_alloc SET resource_oid =
                (SELECT resource_oid FROM cdbpcs_pool_assignment
                 WHERE cdbpcs_prj_alloc.persno = cdbpcs_pool_assignment.person_id)
                 WHERE cdbpcs_prj_alloc.persno != ''
                 AND cdbpcs_prj_alloc.persno IS NOT NULL"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_prj_alloc SET assignment_oid =
                (SELECT cdb_object_id FROM cdbpcs_pool_assignment
                 WHERE cdbpcs_prj_alloc.persno = cdbpcs_pool_assignment.person_id)
                 WHERE cdbpcs_prj_alloc.persno != ''
                 AND cdbpcs_prj_alloc.persno IS NOT NULL"""
        )


class AdjustBackendRelations(object):
    """Set pool_oids for assisting relations."""

    def run(self):
        for table in [
            "cdbpcs_res_schedule",
            "cdbpcs_res_sched_pw",
            "cdbpcs_res_sched_pm",
            "cdbpcs_res_sched_pq",
            "cdbpcs_res_sched_ph",
        ]:
            sqlapi.SQLupdate(
                """{table} SET pool_oid =
                    (SELECT cdbpcs_resource_pool.cdb_object_id FROM cdb_org, cdbpcs_resource_pool
                     WHERE cdb_org.name = cdbpcs_resource_pool.name
                     AND {table}.org_id = cdb_org.org_id)
                     WHERE {table}.org_id != ''
                     AND {table}.org_id IS NOT NULL""".format(
                    table=table
                )
            )
            sqlapi.SQLupdate(
                """{table} SET resource_oid =
                    (SELECT resource_oid FROM cdbpcs_pool_assignment
                     WHERE {table}.personalnummer = cdbpcs_pool_assignment.person_id)
                     WHERE {table}.personalnummer != ''
                     AND {table}.personalnummer IS NOT NULL""".format(
                    table=table
                )
            )
            sqlapi.SQLupdate(
                """{table} SET assignment_oid =
                    (SELECT cdb_object_id FROM cdbpcs_pool_assignment
                     WHERE {table}.personalnummer = cdbpcs_pool_assignment.person_id)
                     WHERE {table}.personalnummer != ''
                     AND {table}.personalnummer IS NOT NULL""".format(
                    table=table
                )
            )


class FillCapacityTables(object):
    """Fill the for assisting relations with capacity values."""

    def run(self):
        from cs.pcs.resources.capacity import CAPACITY_CALCULATOR

        oids = [
            x.resource_oid
            for x in sqlapi.RecordSet2(
                sql="SELECT resource_oid FROM cdbpcs_pool_assignment"
            )
        ]
        CAPACITY_CALCULATOR.createSchedules(resource_oids=oids)


pre = []
post = [
    CheckConsistencyOfPersonsData,
    CreateResourceObjects
    # CreatePoolStructureByOrgStructure,
    # AdjustDemands, AdjustAssignments, AdjustBackendRelations,
    # FillCapacityTables,
]
