#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=W0212,C1801

import datetime

from cdb import ElementsError, misc, sig, ue
from cdb.classbody import classbody
from cdb.objects import (
    ByID,
    Forward,
    Reference,
    Reference_1,
    Reference_Methods,
    Reference_N,
    operations,
)
from cdb.objects.org import Person
from cdb.platform.gui import CDBCatalog
from cs.pcs.resources.helpers import date_from_legacy_str, to_legacy_str
from cs.pcs.resources.pools.assignments import Resource, ResourcePoolAssignment

# Forward declarations
fPerson = Forward("cdb.objects.org.Person")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourcePoolAssignment = Forward(
    "cs.pcs.resources.pools.assignments.ResourcePoolAssignment"
)
fResourcePoolAssignmentPerson = Forward(
    "cs.pcs.resources.pools.assignments.person.ResourcePoolAssignmentPerson"
)
fResourceSchedule = Forward("cs.pcs.resources.resourceschedule.ResourceSchedule")
fResourceScheduleObject = Forward(
    "cs.pcs.resources.resourceschedule.ResourceScheduleObject"
)
fCAPACITY_CALCULATOR = Forward("cs.pcs.resources.capacity.CAPACITY_CALCULATOR")


@classbody
class Person(object):
    """
    Objects of classes Person and Resource are to be synchronized
    """

    Resource = Reference_1(fResource, fResource.referenced_oid == fPerson.cdb_object_id)
    ResourceMember = Reference_N(
        fResourcePoolAssignmentPerson,
        fResourcePoolAssignmentPerson.person_id == fPerson.personalnummer,
        order_by="start_date",
    )

    def _getResourceMember(self):
        rms = list(self.ResourceMember)
        pool = self.Organization.ResourcePool if self.Organization else None
        if pool:
            rms = [x for x in rms if x.pool_oid == pool.cdb_object_id]
        if len(rms):
            open_rmss = [x for x in rms if not x.end_date]
            if len(open_rmss):
                return open_rmss[-1]
            else:
                rms.sort(key=lambda x: x.end_date)
                return rms[-1]
        return None

    ActiveResourceMember = Reference_Methods(
        fResourcePoolAssignmentPerson, lambda self: self._getResourceMember()
    )

    """
    attribute mapping between person und resource
    keys: mapping will be used by creation or deletion only
    attributes will be used by modifying too
    attributes of the source class Person covered by key values
    attributes of the target class Resource covered by values of the keys
    """
    c_resource_attribute_map = {
        "map_keys": {"cdb_object_id": "referenced_oid"},
        "attributes": {
            "name": "name",
            "capacity": "capacity",
            "calendar_profile_id": "calendar_profile_id",
        },
    }

    @property
    def resource_keys_map(self):
        """
        :return: key-value pairs of the unchangeable attributes for use in resource class
        """
        return {
            v: getattr(self, k)
            for k, v in self.c_resource_attribute_map["map_keys"].items()
        }

    @property
    def resource_attribute_map(self):
        """
        :return: key-value pairs of the changeable attributes for use in resource class
        """
        return {
            v: getattr(self, k)
            for k, v in self.c_resource_attribute_map["attributes"].items()
        }

    def create_resource(self, **kwargs):
        """
        Calls the kernel operation CDB_Create of the class Resource
        If something goes wrong, an ue.Exception is raised
        :param kwargs: used as operations.form_input parameter
        :return: cs.pcs.resources.pools.Resource
        """
        args = dict(self.resource_keys_map)
        args.update(**kwargs)
        try:
            return operations.operation(
                "CDB_Create", Resource, operations.form_input(Resource, **args)
            )
        except ElementsError as error:
            raise ue.Exception("cdbpcs_person_resource_sync_err", str(error))

    def delete_resource(self):
        """
        Calls the kernel operation CDB_Delete of the assigned resource object
        If something goes wrong, an ue.Exception is raised
        """
        try:
            operations.operation("CDB_Delete", self.Resource)
        except ElementsError as error:
            raise ue.Exception("cdbpcs_person_resource_sync_err", str(error))

    @sig.connect(Person, "create", "post")
    @sig.connect(Person, "copy", "post")
    def _on_create_resource_post(self, ctx):
        """
        If the person has been created as resource, the resource object is created
        """
        if ctx.error:
            return
        if not self.is_resource:
            return
        self.create_resource()

    @sig.connect(Person, "modify", "post")
    def _on_modify_resource_post(self, ctx):
        """
        If any attribute of a resource has been updated, the resource object will be updated too
        If the person has been tagged as a resource, the resource object will be created
        If the person has been untagged as a resource, the resource object will be deleted
        """
        if ctx.error:
            return
        if self.is_resource:
            if not self.Resource:
                self.create_resource()
                self.Reload()
            else:
                # former Resource modify post
                resource = Resource.ByKeys(referenced_oid=self.cdb_object_id)
                resource.createSchedules()
        elif not self.is_resource and self.Resource:
            self.delete_resource()

    @sig.connect(Person, "delete", "post")
    def _on_delete_resource_post(self, ctx):
        if self.Resource:
            self.delete_resource()

    @sig.connect(Person, "delete", "pre")
    def _on_delete_resource_pre(self, ctx):
        if not self.is_resource:
            return
        if self.ResourceMember:
            raise ue.Exception(
                "cdbpcs_person_resource_delete_err_1", len(self.ResourceMember)
            )

    @classmethod
    def on_pcs_resource_assign_to_pool_pre_mask(cls, ctx):
        """
        Assigns a resource pool to one or more persons.
        """
        ctx.set("start_date", to_legacy_str(datetime.date.today()))

    @classmethod
    def on_pcs_resource_assign_to_pool_now(cls, ctx):
        """
        Assigns a resource pool to one or more persons.
        """
        assignment_errors = {}
        selected_persons = [
            Person.ByKeys(item["personalnummer"]) for item in ctx.objects
        ]

        for person in selected_persons:
            args = {
                "pool_oid": ctx.dialog["pool_oid"],
                "person_id": person.personalnummer,
                "resource_oid": person.Resource.cdb_object_id,
                "start_date": date_from_legacy_str(ctx.dialog.start_date),
                "end_date": (
                    date_from_legacy_str(ctx.dialog.end_date)
                    if ctx.dialog.end_date
                    else None
                ),
            }
            try:
                operations.operation("CDB_Create", ResourcePoolAssignmentPerson, **args)
            except ElementsError as e:
                assignment_errors[person.GetDescription()] = str(e)

        if not assignment_errors:
            misc.log_error(
                "All selected persons have been assigned to the selected resource pool."
            )
            return
        misc.log_error(
            "Not all selected persons could be assigned to the resource pool:"
        )
        error_message_replacement = ""
        for k, v in assignment_errors.items():
            error_message_replacement += "- {}: {}\n".format(k, v.split("\n")[0])
            misc.log_error("{}: {}".format(k, v))
        raise ue.Exception(
            "cdbpcs_person_resource_assign_err_2", error_message_replacement
        )


class ResourcePoolAssignmentPerson(ResourcePoolAssignment):

    __classname__ = "cdbpcs_pool_person_assign"
    __match__ = ResourcePoolAssignment.cdb_classname >= __classname__

    ResourceScheduleOccurrences = Reference_N(
        fResourceScheduleObject,
        fResourceScheduleObject.content_oid
        == fResourcePoolAssignmentPerson.cdb_object_id,
    )
    Person = Reference(1, fPerson, fResourcePoolAssignmentPerson.person_id)

    def on_create_set_resource_oid(self, ctx):
        """
        Used for Drag&Drop of a person to resource pool mambership and for each new membership
        call time 'pre_mask' needed to fill the mandatory fields of the input form
        call time 'pre' needed, if the operation is performed in batch mode
        """
        if not self.person_id:
            return
        if not self.Person.is_resource:
            raise ue.Exception("cdbpcs_person_resource_assign_err_1")
        resource = fResource.KeywordQuery(referenced_oid=self.Person.cdb_object_id)
        if not resource or len(resource) > 1:
            raise ue.Exception("cdbpcs_person_resource_ident_err")
        self.Update(
            resource_oid=resource[0].cdb_object_id, capacity=self.Person.capacity
        )
        # This line avoids the input dialog (E041988)
        ctx.set("mapped_person", self.Person.name)

    def on_create_set_person_data(self, ctx):
        """
        Used for Drag&Drop of a resource to resource pool mambership and for each new membership
        call time 'pre_mask' needed to fill the mandatory fields of the input form
        call time 'pre' needed, if the operation is performed in batch mode
        """
        if not ctx.dragged_obj:
            return
        dragged_object = ByID(ctx.dragged_obj["cdb_object_id"])
        if not isinstance(dragged_object, Resource):
            return
        person = ByID(dragged_object.referenced_oid)
        if not isinstance(person, Person):
            return
        self.Update(
            person_id=person.personalnummer,
            capacity=dragged_object.capacity,
            calendar_profile_id=dragged_object.calendar_profile_id,
        )
        # This line avoids the input dialog (E041988)
        ctx.set("mapped_person", person.name)

    event_map = {
        (("create", "copy"), ("pre_mask", "pre")): (
            "on_create_set_resource_oid",
            "on_create_set_person_data",
        )
    }


class PersonPoolAssignmentCatalog(CDBCatalog):
    """
    Used, when a person is assigned to a resource pool
    Determines and sets the UUID of the resource object
    It is avoided to use a join on the class cdb_person
    """

    def handleSelection(self, selected_objects):
        if not selected_objects:
            return
        if len(selected_objects) > 1:
            return

        selected_object = selected_objects[0]
        resource = fResource.KeywordQuery(
            referenced_oid=selected_object.getValue("cdb_object_id", False)
        )

        if not resource or len(resource) > 1:
            raise ue.Exception("cdbpcs_person_resource_ident_err")

        self.setValue("resource_oid", resource[0].cdb_object_id)
