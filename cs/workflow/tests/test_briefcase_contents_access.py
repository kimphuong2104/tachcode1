#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module test_briefcase_contents

Tests if access rights for assigning objects as briefcase contents are checked
correctly.
"""

import unittest
from cdb import auth
from cdb import constants
from cdb import testcase
from cdb import util

from cdb.objects.org import CommonRoleSubject
from cdb.objects.org import Person
from cdb.objects import operations
from cdb.platform.acs import AccessControlDomain
from cdb.platform.acs import AccessDefinition
from cdb.platform.acs import DomainPredicateAssignment
from cdb.platform.acs import Grant
from cdb.platform.acs import RelshipAccessProfile
from cdb.platform.acs import RelshipAccessProfileMapping
from cdb.platform.mom import Predicate
from cdb.platform.mom import Term
from cdb.platform.mom.relships import Relship

from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import BriefcaseLink
from cs.workflow.briefcases import FolderContent
from cs.workflow.briefcases import IOType
from cs.workflow.processes import Process
from cs.workflow.tasks import ExecutionTask

RS_ACC_PROF = "custom_wf_assign_rights"


def setup_module():
    testcase.run_level_setup()


def CDB_Create(cls, **vals):
    return operations.operation(
        constants.kOperationNew, cls, operations.form_input(cls, **vals))


def CDB_Modify(obj, **vals):
    return operations.operation(
        constants.kOperationModify, obj, operations.form_input(obj, **vals))


class TestTaskActivateTask(testcase.RollbackTestCase):
    """
    no_info: cdbwf_obj_info not granted
    no_edit: cdbwf_obj_edit not granted
    caddok: both (implicitely) granted
    """
    __rs_acc_prof__ = RS_ACC_PROF
    __no_info__ = "no_info"
    __no_edit__ = "no_edit"
    __info__ = "cdbwf_obj_info"
    __edit__ = "cdbwf_obj_edit"

    def setUp(self):
        super(TestTaskActivateTask, self).setUp()
        self.setupAccess()
        self.createProcess()

    def setupAccess(self):
        self._create_rs_acc_prof()
        self._create_relship_def()
        self._create_test_persons()
        self._create_acds()
        self._verify_access()

    def createProcess(self):
        self.process = CDB_Create(
            Process,
            cdb_process_id=Process.new_process_id(),
            title="Test",
            is_template="0",
            subject_id=auth.persno,
            subject_type="Person",
            cdb_objektart="cdbwf_process",
            status=0,
        )
        self.task = CDB_Create(
            ExecutionTask,
            task_id=ExecutionTask.new_task_id(),
            cdb_process_id=self.process.cdb_process_id,
            uses_global_maps=0,
            parent_id="",
            cdb_project_id="",
            position=0,
            title="Test",
            status=0,
            cdb_objektart="cdbwf_task",
            subject_id=auth.persno,
            subject_type="Person",
            cdb_classname=ExecutionTask.__classname__,
        )
        self.briefcase = CDB_Create(
            Briefcase,
            briefcase_id=0,
            cdb_process_id=self.process.cdb_process_id,
            name="Test",
        )

    def linkBriefcase(self, iotype, force=False):
        if isinstance(iotype, str):
            iotype = IOType[iotype].value

        vals = {
            "briefcase_id": self.briefcase.briefcase_id,
            "cdb_process_id": self.briefcase.cdb_process_id,
            "task_id": self.task.task_id,
            "iotype": iotype,
            "extends_rights": 0,
        }

        if force:
            self.link = BriefcaseLink.Create(**vals)
            self.link.Reload()
        else:
            self.link = CDB_Create(BriefcaseLink, **vals)

    def changeLinkType(self, iotype):
        if isinstance(iotype, str):
            iotype = IOType[iotype].value

        assert self.link.iotype != iotype
        CDB_Modify(self.link, iotype=iotype)

    def addContent(self, person):
        CDB_Create(
            FolderContent,
            cdb_folder_id=self.briefcase.cdb_object_id,
            cdb_content_id=person.cdb_object_id,
            position=0,
        )

    def startProcess(self):
        self.process.activate_process()
        self.process.Reload()

    def startTask(self):
        self.task.activate_task()
        self.task.Reload()

    def noAccessProtocol(self, old_count, obj, protocols):
        new_count = len(protocols)
        msg = util.ErrorMessage(
            "cdbwf_no_briefcase_rights",
            self.briefcase.GetDescription(),
            obj.GetDescription(),
        )
        msg = ''.join(str(x) for x in msg.errp[0])
        self.assertEqual(self.link.extends_rights, 0)
        self.assertGreater(new_count, old_count)
        self.assertEqual(msg, protocols[-2].description)

    def _create_rs_acc_prof(self):
        common_vals = {
            "rs_acc_prof": self.__rs_acc_prof__,
            "cdb_module_id": "cs.workflow",
        }
        rs_vals = {
            "mandatory": 1,
            "descr": "TEST ONLY - MUST BE DELETED",
        }
        rs_vals.update(common_vals)
        CDB_Create(RelshipAccessProfile, **rs_vals)

        for access in [self.__info__, self.__edit__]:
            acc_vals = {
                "referer_allow": access,
                "reference_allow": access,
            }
            acc_vals.update(common_vals)
            CDB_Create(RelshipAccessProfileMapping, **acc_vals)

    def _create_relship_def(self):
        vals = {
            "name": "cdbwf_briefcase2cdb_person",
            "referer": "cdbwf_briefcase",
            "reference": "cdb_person",
            "reference_kmap": "",
            "rs_profile": "cdb_aggregation_1_N",
            "rolename": "BriefcasePerson",
            "rs_acc_prof": self.__rs_acc_prof__,
            "cdb_module_id": "cs.workflow"
        }
        CDB_Create(Relship, **vals)

    def _create_test_persons(self):
        def _new_person(persno):
            person = CDB_Create(
                Person,
                personalnummer=persno,
                name=persno,
            )
            CommonRoleSubject.Create(
                role_id="public",
                subject_id=persno,
                subject_type="Person",
                exception_id="",
                cdb_classname="cdb_global_subject",
                cdb_module_id="cs.workflow",
            )
            return person

        self.no_info = _new_person(self.__no_info__)
        self.no_edit = _new_person(self.__no_edit__)
        self.caddok = Person.ByKeys("caddok")

    def _create_acds(self):
        both = "both_info_and_edit"
        CDB_Create(
            AccessControlDomain,
            acd_id=both,
            cdb_module_id="cs.workflow",
            common_flag=1,
        )
        CDB_Create(
            Predicate,
            predicate_name=both,
            table_name="angestellter",
            cdb_module_id="cs.workflow",
        )
        CDB_Create(
            DomainPredicateAssignment,
            acd_id=both,
            predicate_name=both,
            table_name="angestellter",
            cdb_module_id="cs.workflow",
        )
        for access in [self.__info__, self.__edit__]:
            # class is a keyword
            CDB_Create(
                AccessDefinition,
                **{
                    "acd_id": both,
                    "class": "angestellter",
                    "allow": access,
                    "mandatory": 0,
                    "error_label": "",
                    "cdb_module_id": "cs.workflow",
                }
            )
            CDB_Create(
                Grant, **{
                    "acd_id": both,
                    "class": "angestellter",
                    "allow": access,
                    "subject_id": "public",
                    "subject_type": "Common Role",
                    "cdb_module_id": "cs.workflow",
                }
            )

        for persno, access in [(self.__no_info__, self.__info__),
                               (self.__no_edit__, self.__edit__)]:
            CDB_Create(
                AccessControlDomain,
                acd_id=persno,
                cdb_module_id="cs.workflow",
                common_flag=1,
            )
            CDB_Create(
                Predicate,
                predicate_name=persno,
                table_name="angestellter",
                cdb_module_id="cs.workflow",
            )
            CDB_Create(
                Term,
                predicate_name=persno,
                table_name="angestellter",
                attribute="personalnummer",
                operator="=",
                expression=persno,
                data_type="char",
                cdb_module_id="cs.workflow",
            )
            CDB_Create(
                DomainPredicateAssignment,
                acd_id=persno,
                predicate_name=persno,
                table_name="angestellter",
                cdb_module_id="cs.workflow",
            )
            CDB_Create(
                AccessDefinition,
                **{
                    "acd_id": persno,
                    "class": "angestellter",
                    "allow": access,
                    "mandatory": 1,
                    "error_label": "authorization_fail",
                    "cdb_module_id": "cs.workflow",
                }
            )

    def _verify_access(self):
        util.reload_cache(util.kCGRoleCaches, util.kLocalReload)
        util.reload_cache(util.kCGAccessSystem, util.kLocalReload)

        def _assert(condition):
            if not condition:
                raise RuntimeError("access broken")

        _assert(self.caddok.CheckAccess(self.__info__))
        _assert(self.caddok.CheckAccess(self.__edit__))

        _assert(not self.no_info.CheckAccess(self.__info__))
        _assert(self.no_info.CheckAccess(self.__edit__))

        _assert(self.no_edit.CheckAccess(self.__info__))
        _assert(not self.no_edit.CheckAccess(self.__edit__))

    def test_link_granted_info(self):
        self.addContent(self.no_edit)
        self.linkBriefcase("info")
        self.assertEqual(len(self.task.Briefcases), 1)

    def test_link_granted_edit(self):
        self.addContent(self.no_info)
        self.linkBriefcase("edit")
        self.assertEqual(len(self.task.Briefcases), 1)

    def test_link_not_granted_info(self):
        self.addContent(self.no_info)
        with self.assertRaises(RuntimeError):
            self.linkBriefcase("info")
        self.assertEqual(len(self.task.Briefcases), 0)

    def test_link_not_granted_edit(self):
        self.addContent(self.no_edit)
        with self.assertRaises(RuntimeError):
            self.linkBriefcase("edit")
        self.assertEqual(len(self.task.Briefcases), 0)

    def test_add_content_granted_info(self):
        self.linkBriefcase("info")
        self.addContent(self.no_edit)
        self.addContent(self.caddok)
        self.assertEqual(len(self.briefcase.Content), 2)

    def test_add_content_granted_edit(self):
        self.linkBriefcase("edit")
        self.addContent(self.no_info)
        self.addContent(self.caddok)
        self.assertEqual(len(self.briefcase.Content), 2)

    def test_add_content_not_granted_info(self):
        self.linkBriefcase("info")
        with self.assertRaises(RuntimeError):
            self.addContent(self.no_info)
        self.assertEqual(len(self.briefcase.Content), 0)

    def test_add_content_not_granted_edit(self):
        self.linkBriefcase("edit")
        with self.assertRaises(RuntimeError):
            self.addContent(self.no_edit)
        self.assertEqual(len(self.briefcase.Content), 0)

    def test_change_iotype_granted_info(self):
        self.linkBriefcase("info")
        self.addContent(self.caddok)
        self.changeLinkType("edit")
        self.assertEqual(IOType(self.link.iotype).name, "edit")

    def test_change_iotype_granted_edit(self):
        self.linkBriefcase("edit")
        self.addContent(self.caddok)
        self.changeLinkType("info")
        self.assertEqual(IOType(self.link.iotype).name, "info")

    def test_change_iotype_not_granted_info(self):
        self.linkBriefcase("info")
        self.addContent(self.no_edit)
        with self.assertRaises(RuntimeError):
            self.changeLinkType("edit")
        self.assertEqual(IOType(self.link.iotype).name, "info")

    def test_change_iotype_not_granted_edit(self):
        self.linkBriefcase("edit")
        self.addContent(self.no_info)
        with self.assertRaises(RuntimeError):
            self.changeLinkType("info")
        self.assertEqual(IOType(self.link.iotype).name, "edit")

    def test_start_wf_granted_info(self):
        self.addContent(self.no_edit)
        self.linkBriefcase("info")
        self.startProcess()
        self.assertEqual(self.process.status, self.process.EXECUTION.status)

    def test_start_wf_granted_edit(self):
        self.addContent(self.no_info)
        self.linkBriefcase("edit")
        self.startProcess()
        self.assertEqual(self.process.status, self.process.EXECUTION.status)

    def test_start_wf_not_granted_info(self):
        self.addContent(self.no_info)
        self.linkBriefcase("info", force=True)
        old_count = len(self.process.Protocols)
        self.startProcess()
        self.noAccessProtocol(old_count, self.no_info, self.process.Protocols)
        self.assertEqual(self.process.status, self.process.READY.status)

    def test_start_wf_not_granted_edit(self):
        self.addContent(self.no_edit)
        self.linkBriefcase("edit", force=True)
        old_count = len(self.process.Protocols)
        self.startProcess()
        self.noAccessProtocol(old_count, self.no_edit, self.process.Protocols)
        self.assertEqual(self.process.status, self.process.READY.status)

    def test_start_task_granted_info(self):
        self.process.status = 10
        self.addContent(self.no_edit)
        self.linkBriefcase("info")
        self.startTask()
        self.assertEqual(self.task.status, self.task.EXECUTION.status)

    def test_start_task_granted_edit(self):
        self.process.status = 10
        self.addContent(self.no_info)
        self.linkBriefcase("edit")
        self.startTask()
        self.assertEqual(self.task.status, self.task.EXECUTION.status)

    def test_start_task_not_granted_info(self):
        self.process.status = 10
        self.addContent(self.no_info)
        self.linkBriefcase("info", force=True)
        old_count = len(self.task.Protocols)
        self.startTask()
        self.noAccessProtocol(old_count, self.no_info, self.task.Protocols)
        self.assertEqual(self.task.status, self.task.READY.status)

    def test_start_task_not_granted_edit(self):
        self.process.status = 10
        self.addContent(self.no_edit)
        self.linkBriefcase("edit", force=True)
        old_count = len(self.task.Protocols)
        self.startTask()
        self.noAccessProtocol(old_count, self.no_edit, self.task.Protocols)
        self.assertEqual(self.task.status, self.task.READY.status)
