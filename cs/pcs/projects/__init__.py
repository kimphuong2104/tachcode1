#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines,protected-access

"""
This module provides the business logic of a project.
"""

__all__ = [
    "Project",
    "ProjectCategory",
    "DomainAssignment",
    "TeamMember",
    "SubjectAssignment",
    "PersonAssignment",
    "CommonRoleAssignment",
    "PCSRoleAssignment",
    "Role",
]

import datetime
import logging
from urllib.parse import urlencode

from cdb import (
    auth,
    cdbuuid,
    cmsg,
    constants,
    ddl,
    decomp,
    misc,
    sig,
    sqlapi,
    transactions,
    ue,
    util,
)
from cdb.classbody import classbody
from cdb.constants import kOperationModify
from cdb.lru_cache import lru_cache
from cdb.objects import (
    Forward,
    Object,
    Reference_1,
    Reference_Methods,
    Reference_N,
    ReferenceMapping_1,
    ReferenceMapping_N,
    org,
    unique,
)
from cdb.objects.cdb_file import FILE_EVENT, CDB_File
from cdb.objects.common import WithImage
from cdb.objects.operations import operation
from cdb.objects.org import Person
from cdb.platform.acs import WithOCRoleQuery
from cdb.platform.gui import PythonColumnProvider
from cdb.typeconversion import to_legacy_date_format, to_legacy_date_format_auto
from cdbwrapc import RelationshipDefinition
from cs.actions import Action
from cs.activitystream.objects import Subscription
from cs.audittrail import WithAuditTrail
from cs.calendar import CalendarProfile, workday
from cs.metrics.qcclasses import WithQualityCharacteristic
from cs.tools.powerreports import WithPowerReports
from cs.workflow.processes import Process
from cs.workflow.schemacomponents import SchemaComponent
from cs.workflow.systemtasks import InfoMessage

from cs.objectdashboard.dashboard_setup import WithDefaultDashboard
from cs.pcs.efforts import WithEffortReport
from cs.pcs.issues import Issue, WithFrozen, WithIssueReport
from cs.pcs.projects import calendar as Calendar
from cs.pcs.projects import tasks_efforts, utils
from cs.pcs.projects.common.sharing import WithSharingAndProjectRoles
from cs.pcs.projects.helpers import ensure_date, sort_tasks_bottom_up
from cs.pcs.projects.web.create_from_template_app import MOUNT_FROM_TEMPLATE

# Forward declarations
fProject = Forward(__name__ + ".Project")
fRole = Forward(__name__ + ".Role")
fTeamMember = Forward(__name__ + ".TeamMember")
fDomainAssignment = Forward(__name__ + ".DomainAssignment")
fSubjectAssignment = Forward(__name__ + ".SubjectAssignment")
fPCSRoleAssignment = Forward(__name__ + ".PCSRoleAssignment")

fTimeSheet = Forward("cs.pcs.efforts.TimeSheet")
fTask = Forward("cs.pcs.projects.tasks.Task")
fTaskRelation = Forward("cs.pcs.projects.tasks.TaskRelation")
fIssue = Forward("cs.pcs.issues.Issue")
fChecklist = Forward("cs.pcs.checklists.Checklist")
fChecklistItem = Forward("cs.pcs.checklists.ChecklistItem")
fCalendarProfile = Forward("cs.calendar.CalendarProfile")
fDashboardConfig = Forward("cs.objectdashboard.config.DashboardConfig")
fDocumentTemplate = Forward("cs.pcs.projects_documents.ProjectTemplateDocRef")

PCS_ROLE = "PCS Role"
kProjectManagerRole = "Projektleiter"
kProjectMemberRole = "Projektmitglied"

bAutoUpdateTimeMask = 0b00000001
bAutoUpdateEffortMask = 0b00000010

MY_PROJECTS_MAX_RECORDS = 50


def raise_keep_at_least_prj_mgr(name):
    combined_message = "\\n".join(
        [
            str(util.ErrorMessage("pcs_keep_at_least_the_project_manager_1", name)),
            str(util.ErrorMessage("pcs_keep_at_least_the_project_manager_2", name)),
        ]
    )
    raise util.ErrorMessage("just_a_replacement", combined_message)


class Project(
    Object,
    WithEffortReport,
    WithIssueReport,
    WithOCRoleQuery,
    WithPowerReports,
    WithImage,
    WithQualityCharacteristic,
    WithSharingAndProjectRoles,
    WithFrozen,
    WithDefaultDashboard,
):
    __maps_to__ = "cdbpcs_project"
    __wf_step_reject_msg__ = "pcsproj_wfstep_rej"

    __contexts__ = ["ProjectContext"]

    constDefaultCalendarProfileName = "Standard"

    """
    The folowing fields are considered to be readOnly for all projects.
    """
    class_specific_read_only_fields = ["effort_plan", "is_group"]

    default_roles = ["Projektmitglied"]
    """
    List of project roles.

    Project roles must be defined in the project role catalog.

    The values of the identifier of the project role must be entered.

    Each project role that is defined, can be used as a default role in a derived class similar
    to the following lines:

       .. code-block:: python

          from cs.pcs.projects import Project


          class MyProject(Project):
              default_roles = ["Projektmitglied", "Projektassistent"]
    """

    RolesByID = ReferenceMapping_1(
        fRole, fRole.cdb_project_id == fProject.cdb_project_id, indexed_by=fRole.role_id
    )
    Roles = Reference_N(fRole, fRole.cdb_project_id == fProject.cdb_project_id)
    TeamMembers = Reference_N(
        fTeamMember, fTeamMember.cdb_project_id == fProject.cdb_project_id
    )

    TeamMembersByPersno = ReferenceMapping_1(
        fTeamMember,
        fTeamMember.cdb_project_id == fProject.cdb_project_id,
        indexed_by=fTeamMember.cdb_person_id,
    )

    DomainAssignmentsByID = ReferenceMapping_1(
        fDomainAssignment,
        fDomainAssignment.cdb_project_id == fProject.cdb_project_id,
        indexed_by=fDomainAssignment.acd_id,
    )

    TasksByParentTask = ReferenceMapping_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
        indexed_by=fTask.parent_task,
        order_by="position",
    )
    Issues = Reference_N(fIssue, fIssue.cdb_project_id == fProject.cdb_project_id)
    TopLevelChecklists = Reference_N(
        fChecklist,
        fChecklist.cdb_project_id == fProject.cdb_project_id,
        fChecklist.task_id == "",
        fChecklist.parent_checkl_id == 0,
    )
    Checklists = Reference_N(
        fChecklist, fChecklist.cdb_project_id == fProject.cdb_project_id
    )
    ChecklistItems = Reference_N(
        fChecklistItem, fChecklistItem.cdb_project_id == fProject.cdb_project_id
    )
    TimeSheets = Reference_N(
        fTimeSheet, fTimeSheet.cdb_project_id == fProject.cdb_project_id
    )
    Tasks = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
        order_by="position",
    )
    TaskRelations = Reference_N(
        fTaskRelation,
        fTaskRelation.cdb_project_id == fProject.cdb_project_id,
        fTaskRelation.cdb_project_id2 == fProject.cdb_project_id,
    )
    TaskRelationsPre = Reference_N(
        fTaskRelation,
        fTaskRelation.cdb_project_id == fProject.cdb_project_id,
    )
    TaskRelationsSucc = Reference_N(
        fTaskRelation, fTaskRelation.cdb_project_id2 == fProject.cdb_project_id
    )
    Milestones = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
        fTask.milestone == 1,
    )

    # NOTE: baselines are not synced, thus only non-baseline projects
    # can have parents or subprojects
    OrderedSubProjects = Reference_N(
        fProject,
        fProject.parent_project == fProject.cdb_project_id,
        fProject.ce_baseline_id == fProject.ce_baseline_id,
        order_by="position",
    )

    ParentProject = Reference_1(
        fProject, fProject.parent_project, fProject.ce_baseline_id
    )

    Subprojects = Reference_N(
        fProject,
        fProject.parent_project == fProject.cdb_project_id,
        fProject.ce_baseline_id == fProject.ce_baseline_id,
    )
    SuperProject = ParentProject

    TasksAutomatic = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
        fTask.automatic == 1,
    )
    TasksManual = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
        fTask.automatic == 0,
    )

    DocumentTemplates = Reference_N(
        fDocumentTemplate, fDocumentTemplate.cdb_project_id == fProject.cdb_project_id
    )
    CalendarProfile = Reference_1(fCalendarProfile, fProject.calendar_profile_id)

    @property
    def DefaultCalendarProfileName(cls):
        """
        Returns the name of the default calendar profile to be used by creating a project.

        Can be overwritten by customizations in order to preset the name depending on location,
        project category or whatever needed.

        ``:return: string``
        """
        return cls.constDefaultCalendarProfileName

    def _AllTaskRelations(self):
        """
        Method to get all taskrelations

        :return: returns a list of taskrelation objects (1, n, none)
        """
        return unique(self.TaskRelationsPre + self.TaskRelationsSucc)

    AllTaskRelations = Reference_Methods(fTask, lambda self: self._AllTaskRelations())

    TopTasks = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
        fTask.parent_task == "",
        order_by="position",
    )
    AllTasks = Reference_N(
        fTask,
        fTask.cdb_project_id == fProject.cdb_project_id,
        fTask.ce_baseline_id == fProject.ce_baseline_id,
    )

    def _allTasksByOrder(self):
        result = []
        for task in self.TopTasks:
            result.append(task)
            result += task._allSubtasks(by_order=True)
        return result

    AllTasksByOrder = Reference_Methods(fTask, lambda self: self._allTasksByOrder())

    def GetThumbnailFile(self):
        from cdb.objects.cdb_filetype import WebImageFiletypeNames

        ftypes = WebImageFiletypeNames()

        from cdb.objects import cdb_file

        files = cdb_file.CDB_File.KeywordQuery(
            order_by="cdbf_primary desc",
            cdbf_object_id=self.cdb_object_id,
            cdbf_type=ftypes,
        ).Execute()
        if files:
            # return the first file
            return files[0]
        else:
            return None

    def resolveSubProjects(self):
        result = []
        for p in self.OrderedSubProjects:
            result.append(p)
            result += p.resolveSubProjects()
        return result

    def on_cdbpcs_project_details_now(self, ctx):
        from cs.pcs.dashboard import KosmodromTools

        ctx.url(KosmodromTools.get_detail_url(self))

    def on_cdbpcs_milestone_report_now(self, ctx):
        from cs.tools import powerreports

        urlstr = powerreports.MakeReportURL(
            self, None, "", report_name="Meilensteintrendanalyse"
        )
        url = urlstr[: urlstr.find(" cdb:texttodisplay")]
        ctx.url(url)

    def createRole(self, role_id):
        role = self.getRole(role_id=role_id)
        if not role:
            valdict = self._key_dict()
            valdict["role_id"] = role_id
            valdict["team_needed"] = 0
            valdict["team_assigned"] = 0
            role = Role.Create(**valdict)
        return role

    def getRole(self, role_id):
        return self.RolesByID[role_id]

    def assignTeamMember(self, person):
        if not person:
            return
        persno = person
        if not isinstance(persno, str):
            persno = person.personalnummer
        tm = self.TeamMembersByPersno[persno]
        if not tm:
            valdict = self._key_dict()
            valdict["cdb_person_id"] = persno
            tm = TeamMember.Create(**valdict)
            self.handleAutoSubscription([tm])
        return tm

    def assignDomain(self, acd_id, ctx=None):
        from cdb.platform import acs

        if not acs.AccessControlDomain.ByKeys(acd_id=acd_id):
            # Domain does not exist, ignore it
            return
        if not self.DomainAssignmentsByID[acd_id]:
            valdict = self._key_dict()
            valdict["acd_id"] = acd_id
            DomainAssignment.Create(**valdict)
            # wg. AEnderungen an den Schutzklassenzuordnungen den Cache explizit
            # aktualisieren (In Abhaengigkeit vom Property cmlt auch fuer andere Anwender)
            if ctx:
                ctx.refresh_caches(
                    util.kCGDomainAssignmentCache, util.kSynchronizedReload
                )

    def removeDomain(self, acd_id, ctx=None):
        d = self.DomainAssignmentsByID[acd_id]
        if d:
            d.Delete()
        if ctx:
            # wg. AEnderungen an den Schutzklassenzuordnungen den Cache explizit
            # aktualisieren (In Abhaengigkeit vom Property cmlt auch fuer andere Anwender)
            ctx.refresh_caches(util.kCGDomainAssignmentCache, util.kSynchronizedReload)

    def getParent(self):
        return self.ParentProject

    def getParentIDs(self):
        if self.ParentProject:
            return [
                self.ParentProject.cdb_project_id
            ] + self.ParentProject.getParentIDs()
        return []

    def checkParent(self, ctx):
        if self.cdb_project_id in self.getParentIDs():
            raise ue.Exception(
                "cdbpcs_project_recursion", self.ParentProject.GetDescription()
            )

    def setProjectId(self, ctx):
        self.cdb_project_id = self.cdb_project_id.strip()

        generate_nr = not self.cdb_project_id or self.cdb_project_id == "#"

        # Handle template creation
        if not generate_nr and ctx.action in ("copy", "create"):
            # We have to create a new number if we still have the templates number
            # This also affects Drag & Drop
            generate_nr = self.cdb_project_id == getattr(
                ctx.cdbtemplate, "cdb_project_id", ""
            )

        # Handle Drag & Drop
        if not generate_nr and ctx.dragdrop_action_id != "" and ctx.action == "create":
            # We have to create a new number if we still have the dropped objects
            # number
            generate_nr = self.cdb_project_id == getattr(
                ctx.dragged_obj, "cdb_project_id", ""
            )

        if generate_nr:
            self.cdb_project_id = f'P{util.nextval("PROJECT_ID_SEQ"):06d}'

    def setPosition(self, ctx):
        if self.ParentProject and not self.position:
            self.position = (len(self.ParentProject.Subprojects) + 1) * 10

    def setTemplateOID(self, ctx):
        if not ctx:
            return
        if ctx.action == "copy" and ctx.cdbtemplate["cdb_object_id"]:
            self.template_oid = ctx.cdbtemplate["cdb_object_id"]
        elif ctx.action == "delete":
            sqlapi.SQLupdate(
                f"cdbpcs_project SET template_oid = '' "
                f"WHERE template_oid = '{self.cdb_object_id}'"
            )
            for t in self.Tasks:
                t.setTemplateOID()

    def verifyProjectManager(self, ctx):
        """
        If no project manager has been set, the current user is assigned as the project manager
        to ensure that access to the project is possible.
        """
        if self.template:
            return
        if not self.project_manager:
            self.project_manager = auth.persno

    def on_cdbpcs_reinit_position_now(self, ctx):
        """
        Event handler for initializing positions of tasks
        """
        self.reinitPosition(ctx)

    def reinitPosition(self, ctx):
        """
        Initializes the positions of the task structure
        :param ctx:
        :return:
        """
        with transactions.Transaction():
            tasks = list(self.TopTasks)
            self.TopTasks.Update(position=0)
            for task in tasks:
                task.setPosition()
                task.reinitPosition()

    def checkProjectId(self, ctx):
        if self.cdb_project_id not in ["#", ""] and Project.ByKeys(
            cdb_project_id=self.cdb_project_id
        ):
            # already exists
            raise ue.Exception("pcs_err_project_id", self.cdb_project_id)

    def setDefaults(self, ctx):
        self.cdb_project_id = ""
        self.division = auth.get_department()
        if not self.template:
            self.project_manager = auth.persno
        calendar_profile = fCalendarProfile.get_by_name(self.DefaultCalendarProfileName)
        if calendar_profile:
            self.calendar_profile_id = calendar_profile.cdb_object_id
            ctx.set("mapped_calendar_profile", calendar_profile.name)

    def setWorkflow(self, ctx):
        if self.category:
            self.cdb_objektart = ProjectCategory.ByKeys(name=self.category).workflow
        else:
            self.cdb_objektart = "cdbpcs_project"

    def setBaselineIDs(self, ctx):
        if self.ce_baseline_id == "":
            self.cdb_object_id = cdbuuid.create_uuid()
            self.ce_baseline_object_id = self.cdb_object_id

    def setProjectManager(self, ctx):
        if ctx.error != 0:
            return
        # Defaultrollen anlegen
        self.createBasicRoles(ctx)
        if self.project_manager:
            pm = org.Person.ByKeys(personalnummer=self.project_manager)
            # Projektleiter als Teammitglied hinzufuegen und
            # Projektleiterrolle anlegen und mit Projektleiter besetzen
            self.assignTeamMember(pm)
            role = self.createRole(kProjectManagerRole)
            role.assignSubject(pm, ctx)
            # Defaultrollen an den Projektleiter vergeben
            self.assignDefaultRoles(pm, ctx)

    def getProjectManagerName(self):
        if self.project_manager:
            return Person.ByKeys(personalnummer=self.project_manager).name
        return ""

    def getProjectManagers(self):
        role = self.RolesByID[kProjectManagerRole]
        if role:
            return role._Owners()
        return []

    def createBasicRoles(self, ctx):
        self.createRole(kProjectManagerRole)
        for role in self.default_roles:
            self.createRole(role)

    def assignDefaultRoles(self, person, ctx=None):
        if isinstance(person, str):
            person = org.Person.ByKeys(personalnummer=person)
        # Defaultrollen anlegen und an die Person vergeben
        for role_id in self.default_roles:
            role = self.getRole(role_id=role_id)
            if role:
                role.assignSubject(person, ctx)
        self.updateTeam()

    def createFollowUp(self, ctx):
        """
        Tells `ctx` to start the follow up operation
        ``cdbpcs_project_overview``. The follow up is
        only created if there is no pending error and the
        operation is not used in the web. Because
        CDB/Win starts a follow up on its own when performing
        a copy on the toplevel structure node, this method
        skips the creation of an additional follow up in this case.
        """
        if ctx.error != 0 or ctx.cad_system == "MS-Project" or ctx.uses_webui:
            return
        if (
            ctx.action != "copy"
            or getattr(ctx.sys_args, "structurerootaction", "") != "1"
        ):
            ctx.set_followUpOperation("cdbpcs_project_overview", 1)

    def makeID(self, attr, obj, prefix="", length=0):
        """Builds a new ID for the object specified by object within the project context based
        on the attribute specified by attr.
        The specified prefix will be prepended to the generated ID.
        All key attributes, except attr, will be used as query condition
        to find the max value for attr. cdb_project_id must be part of the primary key.
        NOTE: This method is never called by a Project Object itself."""
        additional_keys = obj.KeyDict()
        del additional_keys["cdb_project_id"]
        del additional_keys[attr]
        return self.newID(
            self.cdb_project_id,
            obj.GetTableName(),
            attr,
            prefix,
            length,
            additional_keys,
        )

    @classmethod
    def newID(
        cls, cdb_project_id, relation, attr, prefix="", length=0, additional_keys=None
    ):
        # NOTE: We take baselines into account in order to rule out duplication
        # of IDs. The new ID will be unique if we always take the next unused
        # ID among the IDs used in the project and its baselines.
        # NOTE: This method is never called by a Project Object itself
        if additional_keys is None:
            additional_keys = {}
        stmt = f"max({attr}) FROM {relation} WHERE cdb_project_id = '{cdb_project_id}'"
        if prefix:
            stmt += f" AND {attr} LIKE '{prefix}%'"
        ti = util.tables[relation]
        # Add additional keys to query condition (e.g. checklist_id for checkpoints)
        for key, value in additional_keys.items():
            literal = ti.make_literal(key, f"{value}")
            stmt += f" AND {key} = {literal}"
        t = sqlapi.SQLselect(stmt)
        max_id = sqlapi.SQLstring(t, 0, 0)
        fmt = "%s%0" + f"{length}" + "d"
        if len(max_id) == 0:
            new_id = fmt % (prefix, 1)
        else:
            new_id = fmt % (prefix, (int(max_id[len(prefix) :]) + 1))
        return new_id

    def getReadOnlyFields(self, action="modify", avoid_check=False):
        # start with a copy of the list containing the class specific readOnly fields
        readonly = list(self.class_specific_read_only_fields)

        if self.status != Project.EXECUTION.status:
            readonly += ["percent_complet"]

        if self.status in [Project.NEW.status, Project.DISCARDED.status]:
            readonly += ["start_time_act", "end_time_act"]
        elif self.status == Project.EXECUTION.status:
            readonly += ["end_time_act"]

        if self.is_group:
            readonly += [
                "start_time_act",
                "end_time_act",
                "effort_act",
                "percent_complet",
            ]

        if action == "modify":
            # The template flag can only be edited when creating a new project
            readonly += ["template"]

            # A template project doesn't have a project manager
            if self.template:
                readonly += ["mapped_project_manager"]

            if self.is_group:
                if self.auto_update_time == 1:
                    readonly += ["start_time_fcast", "end_time_fcast", "days_fcast"]
                elif self.auto_update_time == 0:
                    readonly += ["start_time_plan", "end_time_plan", "days"]
                if self.auto_update_effort:
                    readonly += ["effort_fcast"]

            # If MS-Project is set as the scheduling tool or the project is
            # locked by another user the data concerning the scheduling must
            # not be edited
            if self.msp_active or self.locked_by and self.locked_by != auth.persno:
                readonly += [
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "auto_update_time",
                    "mapped_auto_update_time",
                ]

            if len(self.TimeSheets):
                readonly += ["effort_act"]

        if action == "copy":
            # It makes no sense to edit the schedule data
            # if the project start is not moved (E054945, E054946)
            readonly += [
                "start_time_fcast",
                "end_time_fcast",
                "days_fcast",
                "auto_update_time",
                "mapped_auto_update_time",
                "template",
            ]
            # A template project doesn't have a project manager
            if self.template:
                readonly += ["mapped_project_manager"]

        return unique(readonly)

    def on_copy_pre_mask(self, ctx):
        if getattr(ctx.sys_args, "create_project_from_template", "0") == "1":
            self.set_parent_project(ctx)

        self.project_manager = ""

        # Ist-Attribute werden nicht mitkopiert
        ctx.set("start_time_act", "")
        ctx.set("end_time_act", "")
        ctx.set("days_act", "")
        ctx.set("effort_act", 0)
        ctx.set("percent_complet", 0)
        ctx.set_fields_readonly(self.getReadOnlyFields(action=ctx.action))

    def on_relship_copy_post(self, ctx):
        if ctx.error != 0:
            return
        # Rollen, Rollenvergaben und Teamzuordnungen werden ueber die Beziehungen mitkopiert.
        # Falls beim Kopieren ein neuer Projektleiter festgelegt wurde, diesen
        # nun nach dem Kopieren der entsprechenden Beziehungen eintragen.
        template_project = Project.ByKeys(
            cdb_project_id=ctx.cdbtemplate["cdb_project_id"],
            ce_baseline_id=ctx.cdbtemplate["ce_baseline_id"],
        )
        prj_mgr_role = template_project.RolesByID[kProjectManagerRole]
        if not self.template and (  # pylint: disable=too-many-boolean-expressions
            template_project.template
            or not prj_mgr_role
            or (prj_mgr_role and not prj_mgr_role.SubjectAssignmentsByType)
            or (
                prj_mgr_role
                and prj_mgr_role.Persons
                and self.project_manager
                not in [x.personalnummer for x in prj_mgr_role.Persons]
            )
        ):
            if ctx.relationship_name == "cdbpcs_project_to_cdb_person":
                # Projektleiter als Teammitglied hinzufuegen
                self.assignTeamMember(
                    org.Person.ByKeys(personalnummer=self.project_manager)
                )
            elif ctx.relationship_name == "cdbpcs_project_to_subjects":
                # Projektleiterrolle ggf. anlegen und vergeben
                assigned_subj = SubjectAssignment.KeywordQuery(
                    cdb_project_id=self.cdb_project_id
                )
                for subject in assigned_subj:
                    if subject.subject_id2 == template_project.cdb_project_id:
                        subject.subject_id2 = self.cdb_project_id
                pm = org.Person.ByKeys(personalnummer=self.project_manager)
                role = self.createRole(kProjectManagerRole)
                role.assignSubject(pm, ctx)
                # Defaultrollen anlegen und fuer den Projektleiter vergeben
                for role in self.default_roles:
                    self.createRole(role).assignSubject(pm, ctx)

        # Aufgaben-, Checklisten- und ChecklistItem- status wird auf "NEW" zurückgesetzt
        if ctx.relationship_name == "cdbpcs_project2tasks":
            for ts in self.Tasks:
                ts.Reset()

        if ctx.relationship_name == "cdbpcs_project2cdbpcs_checklist":
            for cl in self.Checklists:
                cl.Reset()

        if ctx.relationship_name == "cdbpcs_project2cdbpcs_cl_item":
            for cl_it in self.ChecklistItems:
                cl_it.Reset()

        if ctx.relationship_name == "cdbpcs_prj2doctmpl":
            for doctmpl in self.DocumentTemplates:
                doctmpl.Reset()

    def on_cdbxml_excel_report_pre_mask(self, ctx):
        self.Super(Project).on_cdbxml_excel_report_pre_mask(ctx)
        if ctx.get_current_mask() != "initial":
            ctx.set("project_name", self.project_name)

    def on_copy_post(self, ctx):
        if ctx.error != 0:
            return
        # Ist-Beginndatum, Ist-Enddatum, Ist-Aufwand und fertigestellt zurücksetzen
        self.Update(
            start_time_act="",
            end_time_act="",
            days_act="",
            effort_act=0,
            percent_complet=0,
        )

        if ctx:
            ctx.refresh_caches(
                util.kCGAccessSystemRuntimeCaches, util.kSynchronizedReload
            )

        self.createFollowUp(ctx)

    def checkProjectLevel(self, ctx):
        """SampleCode below can be used in subclasses to implement
        restrictions for the project hierachie.

        # allow only first level subprojects
        if self.ParentProject and self.ParentProject.ParentProject: raise ue.Exception("pcs_err_crt_subprj")
        # dont mix suprojects and tasks
        if self.ParentProject and self.ParentProject.Tasks: raise ue.Exception("pcs_err_mod_mix")
        """
        pass

    def on_create_pre_mask(self, ctx):
        self.checkProjectLevel(ctx)
        self.setPosition(ctx)
        if self.parent_project and self.ParentProject.template == 1:
            self.template = 1

    def on_modify_post_mask(self, ctx):
        if ctx.dialog.parent_project != ctx.object.parent_project:
            # Sample code to allow one-level project hierarchy only: see also checkProjectLevel
            # if self.ParentProject and self.Subprojects:
            #    raise ue.Exception("pcs_err_mod_subprj")
            # recalculate position
            self.setPosition(ctx)

    def on_delete_pre(self, ctx):
        if self.Subprojects:
            raise ue.Exception("pcs_err_del_proj4")
        if self.TimeSheets:
            raise ue.Exception("pcs_err_del_proj1")

    def on_delete_post(self, ctx, db_relations=None):
        """
        Deletes referenced records using cdb.sqlapi.SQLDelete within a transaction
        Can be customized similar to the following lines

        class MyProject(Project):
            ...
            def on_delete_post(self, ctx):
                additional_relations = ['my_additional_relation']
                self.Super(MyProject).on_delete_post(ctx, additional_relations)
            ...

        :param db_relations: Additional relations from which referenced records are to be deleted
        """
        if ctx.error != 0:
            return

        if db_relations is None:
            db_relations = []

        relations = [
            "cdbpcs_cl_prot",
            "cdbpcs_doc2cl",
            "cdbpcs_cli_prot",
            "cdbpcs_doc2cli",
            "cdbpcs_doc2iss",
            "cdbpcs_iss_prot",
            "cdbpcs_iss_log",
            "cdbpcs_doc2task",
        ]
        where_condition = f"cdb_project_id = '{self.cdb_project_id}'"
        with transactions.Transaction():
            for relation in relations + db_relations:
                if ddl.Table(relation) and ddl.Table(relation).hasColumn(
                    "cdb_object_id"
                ):
                    sqlapi.SQLdelete(
                        (
                            "from cdb_object where id in (select cdb_object_id "
                            f"from {relation} where {where_condition})"
                        )
                    )
                sqlapi.SQLdelete(f"from {relation} where {where_condition}")

    def on_modify_pre_mask(self, ctx):
        ctx.set_fields_readonly(self.getReadOnlyFields(action=ctx.action))

    @classmethod
    def _set_template_catalog_query_args(cls, ctx):
        if ctx.catalog_invoking_op_name == "cdbpcs_create_project":
            if not ctx.catalog_requery:
                if "templatecatalogargsset" not in ctx.ue_args.get_attribute_names():
                    ctx.keep("templatecatalogargsset", "1")
                    # We might got some decomposition-attributes by on_cdb_create_doc_from_template_now
                    for attr in ctx.catalog_invoking_dialog.get_attribute_names():
                        if attr[-15:] == "_initalqueryarg":
                            ctx.set(attr[:-15], ctx.catalog_invoking_dialog[attr])

    @classmethod
    def on_cdbpcs_create_project_now(cls, ctx):
        """
        Create an project by selecting an template and copy it
        """
        # webui: Select template using dedicated app and open info page
        if ctx.uses_webui:
            url = MOUNT_FROM_TEMPLATE
            query_dict = {}
            if (
                hasattr(ctx.dialog, "parent_project")
                and ctx.dialog.parent_project
                and hasattr(ctx.dialog, "ce_baseline_id")
                and ctx.dialog.ce_baseline_id is not None  # can be empty string
            ):
                query_dict["parent_project"] = ctx.dialog.parent_project
                query_dict["ce_baseline_id"] = ctx.dialog.ce_baseline_id

            if hasattr(ctx, "relationship_name") and ctx.relationship_name:
                query_dict["relationship_name"] = RelationshipDefinition(
                    ctx.relationship_name
                ).get_rolename()

            query = urlencode(query_dict)
            url = f"{url}?{query}"
            ctx.url(url)
        # cdbpc: Legacy template selection mechanism
        else:
            # Get the project
            if not ctx.catalog_selection:
                kwargs = {}
                # If we are in a decomposition, evaluate the predefined attributes
                if "decompositionclsid" in ctx.sys_args.get_attribute_names():
                    decomposition = ctx.sys_args["decompositionclsid"]
                    if decomposition:
                        # get predefined attrs, e.g. from decompositions
                        from cdb.platform.mom import entities

                        cdef = entities.CDBClassDef(decomposition)
                        predef_args = cdef.getPredefinedOpArgs("CDB_Search", True)
                        for arg in predef_args:
                            # This one is for the catalog configuration
                            # to behave as if the attributes were in the
                            # dialog
                            kwargs[arg.name] = arg.value
                            # This one is for _set_template_catalog_query_args
                            kwargs[arg.name + "_initalqueryarg"] = arg.value
                ctx.start_selection(catalog_name="pcs_project_templates", **kwargs)
            else:
                pnumber = ctx.catalog_selection[0]["cdb_project_id"]
                baseline_id = ctx.catalog_selection[0]["ce_baseline_id"]
                template = Project.ByKeys(
                    cdb_project_id=pnumber, ce_baseline_id=baseline_id
                )
                ctx.set_followUpOperation(
                    "CDB_Copy",
                    predefined=[("cdb::argument.create_project_from_template", True)],
                    keep_rship_context=True,
                    op_object=template,
                )

    def reset_invalid_subject_ids(self):
        team = list(self.TeamMembersByPersno)
        for t in self.Tasks.KeywordQuery(subject_type="Person", ce_baseline_id=""):
            if t.subject_id not in team:
                t.subject_id = kProjectManagerRole
                t.subject_type = Role.__subject_type__

    def adopt_all_project_roles_from_template(self, task_template):
        self.adopt_project_role_from_template(task_template=task_template)
        for t in task_template.OrderedSubTasks:
            self.adopt_all_project_roles_from_template(task_template=t)

    def adopt_project_role_from_template(self, task_template):
        old_role = task_template._getResponsibleRole()
        if not old_role:
            return
        # if role not already exists: add role to project
        new_role = Role.ByKeys(
            role_id=old_role.role_id, cdb_project_id=self.cdb_project_id
        )
        if not new_role:
            Role.Create(role_id=old_role.role_id, cdb_project_id=self.cdb_project_id)

    def checkStructureLock(self, ctx=None):
        calledByOfficeLink = (
            ctx
            and hasattr(ctx, "active_integration")
            and ctx.active_integration == "OfficeLink"
        )
        if not calledByOfficeLink and not Project.structuralChangesAllowed(
            project=self, ctx=ctx
        ):
            raise ue.Exception("cdbpcs_msp_structure_lock")

    @classmethod
    def structuralChangesAllowed(cls, project, ctx=None):
        if project.msp_active and (ctx is None or ctx.cad_system != "MS-Project"):
            return False
        return True

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = self.Super(Project).GetDisplayAttributes()
        results["attrs"].update({"heading": str(self["mapped_category_name"])})
        return results

    def GetSearchSummary(self):
        obj = self.getPersistentObject()
        return f"{obj.description}\n{obj.joined_status_name}"

    def initTaskRelationOIDs(self):
        upd = f"""cdbpcs_taskrel SET
                    pred_project_oid = (SELECT cdb_object_id FROM cdbpcs_project p
                                        WHERE cdbpcs_taskrel.cdb_project_id2 = p.cdb_project_id
                                        AND p.ce_baseline_id = ''),
                    succ_project_oid = (SELECT cdb_object_id FROM cdbpcs_project p
                                        WHERE cdbpcs_taskrel.cdb_project_id = p.cdb_project_id
                                        AND p.ce_baseline_id = ''),
                    pred_task_oid = (SELECT cdb_object_id FROM cdbpcs_task t
                                     WHERE cdbpcs_taskrel.cdb_project_id2 = t.cdb_project_id
                                     AND cdbpcs_taskrel.task_id2 = t.task_id
                                     AND t.ce_baseline_id = ''),
                    succ_task_oid = (SELECT cdb_object_id FROM cdbpcs_task t
                                     WHERE cdbpcs_taskrel.cdb_project_id = t.cdb_project_id
                                     AND cdbpcs_taskrel.task_id = t.task_id
                                     AND t.ce_baseline_id = ''),
                    cross_project = (CASE WHEN cdbpcs_taskrel.cdb_project_id2 != cdbpcs_taskrel.cdb_project_id
                                         THEN 1 ELSE 0 END)
                WHERE cdbpcs_taskrel.cdb_project_id = '{self.cdb_project_id}' OR
                    cdbpcs_taskrel.cdb_project_id2 = '{self.cdb_project_id}'
              """
        return sqlapi.SQLupdate(upd)

    def adjustDependingObjects(self, adjust_tasks=False):
        """
        Diese Methode muss aufgerufen werden, nachdem das Projekt ausserhalb
        des cdb.objects-Frameworks modifiziert wurde.
        Änderungen an allen betroffenen Aufgaben werden abhängigen Objekten bekannt gemacht
        """
        from cs.pcs.projects.tasks import Task

        if adjust_tasks:
            Task.adjustDependingObjects_many(self.AllTasks)

        sig.emit(Project, "adjustDependingObjects")(self)

    def getCriticalIssues(self):
        status_list = [
            Issue.NEW.status,
            Issue.EVALUATION.status,
            Issue.EXECUTION.status,
            Issue.DEFERRED.status,
            Issue.WAITINGFOR.status,
            Issue.REVIEW.status,
        ]
        return [
            x
            for x in self.Issues
            if x.priority == "kritisch" and x.status in status_list
        ]

    def getEarnedValue(self):
        tasks = self.TopTasks
        if tasks:
            return float(sum(x.getEarnedValue() for x in tasks))
        return self.getWorkCompletion() / 100 * self.getPlanCost()

    def getWorkCompletion(self):
        if self.percent_complet:
            return float(self.percent_complet)
        return 0.0

    def getPlanCost(self):
        if self.effort_plan:
            return float(self.effort_plan)
        return 0.0

    def getForeCast(self):
        if self.effort_fcast:
            return float(self.effort_fcast)
        return 0.0

    def getActCost(self):
        if self.effort_act:
            return float(self.effort_act)
        return 0.0

    def getPlanTimeCompletion(self, myDate=None):
        if not myDate:
            myDate = datetime.date.today()
        ed = self.end_time_fcast
        if ed and ed <= myDate:
            return 1.0
        return 0.0

    def getPlanTimeCompletion2(self):
        max_workdays = self.getWorkdays()
        my_date = datetime.date.today()
        sd = self.start_time_fcast
        ed = self.end_time_fcast
        if not max_workdays or not sd or not ed or sd > my_date:
            return 0.0
        if ed <= my_date:
            return 1.0
        days_done = float(
            len(Calendar.project_workdays(self.cdb_project_id, sd, my_date))
        )
        return days_done / max_workdays

    def getWorkdays(self):
        try:
            sd = self.start_time_plan
            ed = self.end_time_plan
            return max(len(Calendar.project_workdays(self.cdb_project_id, sd, ed)), 0)
        except Exception:
            misc.log_traceback("Workdays can not been determined")
            return 0

    def getWorkhours(self):
        return workday.days_to_hours(self.getWorkdays())

    def calculateTimeFrame(self, start="", end="", days="", shift_right=True):
        return Calendar.calculateTimeFrame(
            self.calendar_profile_id, start, end, days, shift_right
        )

    def get_days_actual(self, start, end):
        days_act = None
        if start and end:
            _, _, days_act = self.calculateTimeFrame(start=start, end=end)
        return days_act

    def validate_and_update_days_act(self, ctx):
        if (
            self.start_time_act
            and self.end_time_act
            and self.start_time_act > self.end_time_act
        ):
            raise ue.Exception(1024, util.get_label("pcs_days_act_end_before_start"))
        if self.end_time_act and not self.start_time_act:
            raise ue.Exception(
                1024, util.get_label("pcs_start_act_present_when_end_act")
            )

        self.Update(
            days_act=self.get_days_actual(self.start_time_act, self.end_time_act)
        )

    # create/copy/modify: pre
    def checkEffortFields(self, ctx):
        cdb_project_id = self.cdb_project_id
        ce_baseline_id = self.ce_baseline_id
        if ctx and ctx.action == "copy":
            cdb_project_id = ctx.cdbtemplate.cdb_project_id
            ce_baseline_id = ctx.cdbtemplate.ce_baseline_id

        cld = len(
            fTask.KeywordQuery(
                cdb_project_id=cdb_project_id, ce_baseline_id=ce_baseline_id
            )
        )

        changes = {}
        if cld == 0:
            if self.effort_plan != self.effort_fcast:
                changes.update(effort_plan=self.effort_fcast)
            if self.start_time_fcast is None:
                changes.update(start_time_fcast="")
            if self.end_time_fcast is None:
                changes.update(end_time_fcast="")
        else:
            if self.auto_update_time == 1:
                changes.update(start_time_fcast=self.start_time_plan)
                changes.update(end_time_fcast=self.end_time_plan)
            if self.auto_update_effort == 1:
                changes.update(effort_fcast=self.effort_plan)

        # start/end must be filled jointly
        if (
            self.start_time_fcast
            and not self.end_time_fcast
            or not self.start_time_fcast
            and self.end_time_fcast
        ):
            raise ue.Exception("pcs_capa_err_025")

    def on_Prj_Autolock_now(self, ctx):
        if self.CheckAccess("lock") and not self.locked_by:
            myPersno = f"{auth.persno}"
            self.locked_by = myPersno

    def on_Prj_Autounlock_now(self, ctx):
        if self.CheckAccess("unlock") and self.locked_by == f"{auth.persno}":
            self.locked_by = ""

    def on_Prj_Lock_now(self, ctx):
        myPersno = f"{auth.persno}"
        if self.locked_by == myPersno:
            return
        if self.locked_by:
            raise ue.Exception("pcs_err_lock", self.mapped_locked_by_name)
        self.locked_by = myPersno
        # do not show message boxes in the web ui
        if "lock" not in ctx.dialog.get_attribute_names() and not ctx.uses_webui:
            msgbox = ctx.MessageBox(
                "pcs_locked", [], "lock", ctx.MessageBox.kMsgBoxIconInformation
            )
            msgbox.addButton(ctx.MessageBoxButton("ok", 1))
            ctx.show_message(msgbox)

    def on_Prj_Unlock_now(self, ctx):
        if not self.locked_by:
            return
        self.locked_by = ""
        # do not show message boxes in the web ui
        if "unlock" not in ctx.dialog.get_attribute_names() and not ctx.uses_webui:
            msgbox = ctx.MessageBox(
                "pcs_unlocked", [], "unlock", ctx.MessageBox.kMsgBoxIconInformation
            )
            msgbox.addButton(ctx.MessageBoxButton("ok", 1))
            ctx.show_message(msgbox)

    def isFinalized(self, ctx=None):
        if self.status in Project.endStatus(full_cls=False):
            raise ue.Exception("cdbpcs_check_proj_status")

    def checkScheduleLock(self):
        if self.locked_by and self.locked_by != f"{auth.persno}":
            raise ue.Exception("pcs_write_locked")

    def setLock(self, ctx=None, verbose=False):
        myPersno = f"{auth.persno}"
        if self.CheckAccess("lock"):
            if not self.locked_by:
                self.locked_by = myPersno
            elif ctx and verbose and self.locked_by and self.locked_by != myPersno:
                if (
                    "lock" not in ctx.dialog.get_attribute_names()
                    and not ctx.uses_webui
                ):
                    msgbox = ctx.MessageBox(
                        "pcs_write_locked",
                        [],
                        "lock",
                        ctx.MessageBox.kMsgBoxIconInformation,
                    )
                    msgbox.addButton(ctx.MessageBoxButton("ok", 1))
                    ctx.show_message(msgbox)
        return self.isLockedByMe()

    def isLockedByMe(self):
        return self.locked_by == f"{auth.persno}"

    def isPartOfTemplateProject(self, part):
        from cs.pcs.checklists import Checklist, ChecklistItem
        from cs.pcs.projects.tasks import Task

        if part and isinstance(part, Project):
            return part.template == 1
        if part and isinstance(part, (Task, Checklist, ChecklistItem)):
            return part.Project and part.Project.template == 1
        return False

    def _correctCalendarDates(self, ctx):
        """Check if the planned project start and end dates are included in
        the specified calendar profile. If not, raise an exception to the
        user to change it.
        """
        if not self.calendar_profile_id:
            return
        calendar_profile = CalendarProfile.ByKeys(
            cdb_object_id=self.calendar_profile_id
        )
        cp_start = calendar_profile.valid_from
        cp_end = calendar_profile.valid_until

        # determine earliest project start date
        start = self.start_time_fcast or self.start_time_plan
        if self.start_time_fcast and self.start_time_plan:
            start = min([self.start_time_fcast, self.start_time_plan])

        # determine latest project end date
        end = self.end_time_fcast or self.end_time_plan
        if self.end_time_fcast and self.end_time_plan:
            end = max([self.end_time_fcast, self.end_time_plan])

        # remove this block when all date fields lost their time info
        if isinstance(start, datetime.datetime):
            start = start.date()
        if isinstance(end, datetime.datetime):
            end = end.date()
        if isinstance(cp_start, datetime.datetime):
            cp_start = cp_start.date()
        if isinstance(cp_end, datetime.datetime):
            cp_end = cp_end.date()

        # 3 cases where the dates could be invalid,
        # depending on whether start and end are defined
        if (
            start
            and end
            and (start < cp_start or cp_end < start or end < cp_start or cp_end < end)
        ):
            p_sd = to_legacy_date_format(start, full=False)
            p_ed = to_legacy_date_format(end, full=False)
            cp_sd = to_legacy_date_format(cp_start, full=False)
            cp_ed = to_legacy_date_format(cp_end, full=False)
            raise ue.Exception("cdb_proj_cal_prof", p_sd, p_ed, cp_sd, cp_ed)

    def on_cdbpcs_chg_cal_profile_now(self, ctx):
        MAX_ELEMS_IN_CLAUSE = 500
        list_of_groups = []
        # Split into distinct groups.
        list_of_projno = [obj.cdb_project_id for obj in ctx.objects]
        cutoffs = list(range(0, len(list_of_projno), MAX_ELEMS_IN_CLAUSE)) + [
            len(list_of_projno)
        ]
        for n in range(len(cutoffs) - 1):
            list_of_groups.append(list_of_projno[cutoffs[n] : cutoffs[n + 1]])
        cp = CalendarProfile.ByKeys(cdb_object_id=ctx.dialog.calendar_profile_id)
        wrong_date_projects = []
        for prj_no in list_of_projno:
            p = Project.ByKeys(cdb_project_id=prj_no)
            if p.checkProjectCalendarDates(cp):
                wrong_date_projects.append(p.GetDescription())
        if len(wrong_date_projects) > 0:
            raise ue.Exception(
                "cdbpcs_invalid_calendar_profile", "\n".join(wrong_date_projects)
            )
        for proj_group in list_of_groups:
            ps = Project.ByKeys(cdb_project_id=proj_group)
            c_id = ctx.dialog.calendar_profile_id
            ps.Update(calendar_profile_id=c_id)
            cp.on_cdb_recalculate_projects_now(ctx)

    def checkProjectCalendarDates(self, cp):
        cp_start = cp.valid_from
        cp_end = cp.valid_until
        proj_start = (
            self.start_time_fcast if self.start_time_fcast else self.start_time_plan
        )
        proj_end = self.end_time_fcast if self.end_time_fcast else self.end_time_plan
        # 3 cases where the dates could be invalid, depending on whether
        # start_time_plan is defined, end_time_plan is defined or both are
        return (proj_start and (proj_start < cp_start or cp_end < proj_start)) or (
            proj_end and (proj_end < cp_start or cp_end < proj_end)
        )

    def getResponsiblePersons(self):
        # return the id of persons who own, the role "ProjectManager"
        persons = []
        for pm in self.getProjectManagers():
            persons.append(pm.personalnummer)
        return persons

    @classmethod
    def adjustCalenderChanges(cls, cdb_project_id, day_from, day_until):
        # Note: adjust calenders only for current project and not for baselines
        p = Project.ByKeys(cdb_project_id=cdb_project_id)
        p.recalculate()

    def getEffortAvailable(self):
        fcast = 0.0
        aggr = 0.0
        if self.effort_fcast:
            fcast = float(self.effort_fcast)

        if self.Tasks and self.effort_plan:
            aggr = float(self.effort_plan)

        return fcast - aggr

    def getEffortForeCast(self):
        return self.effort_fcast

    def getEffortPlan(self):
        return self.effort_plan

    def getStartTimeFcast(self):
        return self.start_time_fcast

    def getStartTimePlan(self):
        return self.start_time_plan

    def getStartTimeAct(self):
        return self.start_time_act

    def getEndTimeFcast(self):
        return self.end_time_fcast

    def getEndTimePlan(self):
        return self.end_time_plan

    def getEndTimeAct(self):
        return self.end_time_act

    def on_cdbpcs_prj_reset_start_time_pre_mask(self, ctx):
        self.checkStructureLock(ctx=ctx)
        if not self.start_time_fcast:
            raise ue.Exception("pcs_move_project_error_01")
        ctx.set("start_time_old", self.start_time_fcast)

    def on_cdbpcs_prj_reset_start_time_now(self, ctx):
        self.checkStructureLock(ctx=ctx)
        newsd = None
        try:
            newsd = ctx.dialog.start_time_new
        except Exception:
            logging.exception("start_time_new not in ctx.dialog")
        if not newsd:
            return
        self.reset_start_time(ctx, ctx.dialog["start_time_old"], newsd)

    def reset_start_time(self, ctx=None, start_time_old=None, start_time_new=None):
        """
        Die Methode verschiebt sowohl den Sollwert als auch den aggregierten Wert des aufgerufenen und
        aller untergeordneten Elemente.
        """
        if not start_time_new or not start_time_old:
            return

        old_date = ensure_date(start_time_old)
        new_date = ensure_date(start_time_new)

        if not new_date:
            return

        # new start date must be within the valid time span
        if new_date < self.CalendarProfile.valid_from:
            nsd = to_legacy_date_format_auto(new_date)
            cp_sd = to_legacy_date_format_auto(self.CalendarProfile.valid_from)
            cp_ed = to_legacy_date_format_auto(self.CalendarProfile.valid_until)
            raise ue.Exception("cdb_proj_cal_prof", nsd, "?", cp_sd, cp_ed)

        # determine distance to move
        (new_start_idx, _) = Calendar.getIndexByDate(self.calendar_profile_id, new_date)
        (old_start_idx, _) = Calendar.getIndexByDate(self.calendar_profile_id, old_date)

        if old_start_idx and new_start_idx:
            distance = new_start_idx - old_start_idx
            if distance:
                # adjust constraint dates of all tasks and start dates for all manual tasks
                for t in self.Tasks:
                    t.moveFixedDates(
                        distance=distance, calendar_profile_id=self.calendar_profile_id
                    )
                # move project and start adjustment process
                self.setStartTimeFcast(
                    start=Calendar.getDateByIndex(
                        self.calendar_profile_id, new_start_idx
                    )
                )

    def setTimeframe(self, ctx=None, start=None, end=None, days=None, **kwargs):
        with transactions.Transaction():
            start, end, days = self.calculateTimeFrame(start=start, end=end, days=days)
            operation(
                kOperationModify,
                self.getPersistentObject(),
                start_time_fcast=start,
                end_time_fcast=end,
                days_fcast=days,
                **kwargs,
            )
            self.Reload()

    def aggregateValues(self, **kwargs):
        with transactions.Transaction():
            tasks_efforts.aggregate_changes(self)

    def mark_as_changed(self):
        kwargs = Project.MakeChangeControlAttributes()
        self.Update(cdb_apersno=kwargs["cdb_mpersno"], cdb_adate=kwargs["cdb_mdate"])

    def get_delay(self):
        fcast = self.end_time_fcast
        act = self.end_time_act
        if fcast and act:
            return (act - fcast).days
        return 0

    # usage in legacy project overview ("kosmodrom")
    def get_time_completion(self, myDate=None):
        """Calculates the work days of the project:
        SD:            (Target) Start datetime of project
        ED:            (Target) End datetime of project
        myDate:        given datetime or current date
        days_done:     workdays passed
        days_total:    workdays in total
        done_percent:  workdays done in percent
        returns tuple (<SD>, <ED>, <myDate>, <days done>, <days total>
                        <done percent>)
        """
        days_total = self.days if self.days else 0
        if not myDate:
            myDate = datetime.date.today()
        start = self.start_time_fcast
        end = self.end_time_fcast
        if not start or not end:
            return (start, end, myDate, 0, 0, 0)
        if myDate < start:
            days_done = 0
        elif myDate > end:
            days_done = days_total
        else:
            days_done = len(
                Calendar.project_workdays(self.cdb_project_id, start, myDate)
            )
        done_percent = 0
        if days_total:
            done_percent = int(round(100.0 * days_done / days_total, 0))
        return (start, end, myDate, days_done, days_total, done_percent)

    def get_manual_light(self):
        """Determines value of manual light rating for project
        0: undefiend
        1: green (good)
        2: yellow (warning)
        3: red (bad)
        """
        rating = self.rating
        if rating == "gruen":
            state = 1
        elif rating == "rot":
            state = 3
        elif rating == "gelb":
            state = 2
        else:
            state = 0
        return state

    def get_ev_pv_for_project(self):
        from cs.pcs.projects.tasks import Task
        from cs.pcs.projects.calendar import getWorkdays

        discarded_status = Task.DISCARDED.status

        def relevant_task(task):
            # tasks are valid if they...
            #   - are not group tasks
            #   - are not a milestone
            #   - have initiated fcast-values
            #   - are not in status DISCARDED
            return (
                not task.is_group
                and not task.milestone
                and task.days_fcast
                and task.start_time_fcast
                and task.end_time_fcast
                and task.effort_fcast
                and task.status != discarded_status
            )

        tasks = sqlapi.RecordSet2(
            "cdbpcs_task",
            f"cdb_project_id = '{self.cdb_project_id}'",
            columns=[
                "cdb_project_id",
                "task_id",
                "parent_task",
                "status",
                "is_group",
                "milestone",
                "percent_complet",
                "effort_fcast",
                "start_time_fcast",
                "end_time_fcast",
                "days_fcast",
                "position",
            ],
        )
        sql_tasks = sort_tasks_bottom_up(tasks)
        today = datetime.date.today()
        today_datetime = datetime.datetime.today().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if len(sql_tasks):
            values = dict(earned_value=0.0, planned_value=0.0)
            for t in sql_tasks:
                # ignore irrelevant tasks
                if not relevant_task(t):
                    continue

                # determine calculation values
                percent_complete = (
                    float(t.percent_complet) if t.percent_complet else 0.0
                )
                effort_fcast = float(t.effort_fcast)
                planned_completion = 0.0
                if t.end_time_fcast <= today:
                    planned_completion = 1.0
                elif t.start_time_fcast == today:
                    planned_completion = round(1.0 / t.days_fcast, 2)
                elif t.start_time_fcast < today < t.end_time_fcast:
                    workedDays = getWorkdays(
                        self.cdb_project_id, t.start_time_fcast, today_datetime
                    )
                    planned_completion = round(float(workedDays) / t.days_fcast, 2)

                # add up earned value
                values["earned_value"] += percent_complete / 100 * effort_fcast
                # add up planned value
                values["planned_value"] += planned_completion * effort_fcast

            return (values["earned_value"], values["planned_value"])
        return (
            self.getWorkCompletion() / 100 * self.getForeCast(),
            self.getPlanTimeCompletion() * self.getForeCast(),
        )

    def get_cost_state(self, ev):
        """Calculates the cost efficiency of the project:
        EV: Earned Value
        AC: Actual Costs
        CV: Cost Variance            (EV - AC)
        CPI: Cost Performance Index  (EV / AC)
        EVC: Earned Value Completion (EV / <Scheduled Costs>)
        ACC: Actual Cost Completion  (AC / <Scheduled Costs>)
        state color: Signal color (red, green, yellow, undefiened)
        returns a tuple (<EV>, <AC>, <CV>, <CPI>, <EVC>, <ACC>,
                        <state color>)
        """
        # Bestimme die bislang angefallenen Kosten
        ac = self.getActCost()

        # Setzte aktuelle Kosten mit erbrachter Leistung Relation
        scheduled_costs = self.getPlanCost()
        cv = 0.0
        cpi = 1.0
        myState = 0
        if ac:
            cv = ev - ac
            cpi = round(ev / ac, 1)
            myState = self._getState(cpi)
        evc = 0
        acc = 0
        if scheduled_costs:
            evc = int(round(100 * ev / scheduled_costs, 0))
            acc = int(round(100 * ac / scheduled_costs, 0))
        return (ev, ac, cv, cpi, evc, acc, myState)

    def get_schedule_state(self, ev, pv):
        """Calculates the time efficiency of the project by effort:
        EV: Earned Value
        PV: Planned Value
        SV: Schedule Variance            (EV - PV)
        SPI: Schedule Performance Index  (EV / PV)
        EVC: Earned Value Completion     (EV / <Scheduled Costs>)
        PVC: Planned Value Completion    (PV / <Scheduled Costs>)
        state color: Signal color (red, green, yellow, undefiened)
        returns a tuple (<EV>, <PV>, <SV>, <SPI>, <EVC>, <PVC>,
                        <state color>)
        """
        # Setzte geplante Leistung mit erbrachter Leistung Relation
        scheduled_costs = self.getPlanCost()
        sv = 0.0
        spi = 1.0
        myState = 0
        if pv:
            sv = ev - pv
            spi = round(ev / pv, 1)
            myState = self._getState(spi)
        evc = 0
        pvc = 0
        if scheduled_costs:
            evc = int(round(100 * ev / scheduled_costs, 0))
            pvc = int(round(100 * pv / scheduled_costs, 0))
        return (ev, pv, sv, spi, evc, pvc, myState)

    def _getState(self, efficiency):
        if efficiency >= 1.0:
            return 1
        if efficiency >= 0.9:
            return 2
        return 3

    def handleAutoSubscription(self, members):
        """
        Subscribes all `members` to the project's
        activity channel, if the conditions are
        suitable.
        """
        if self.status == Project.EXECUTION.status:
            if self.GetClassDef().isActivityChannel():
                for member in members:
                    Subscription.subscribeToChannel(
                        self.cdb_object_id, member.cdb_person_id
                    )

    def _handleSubscriptions(self, ctx):
        """
        Autosubscribe all team members to the project, on the
        workflow step to EXECUTION.
        """
        if not ctx.error:
            self.handleAutoSubscription(self.TeamMembers)

    def addQCArguments(self, args, ctx=None):
        args.update(cdb_project_id=self.cdb_project_id)

    def setInitValues(self, ctx):
        ctx.set_focus("project_name")
        ctx.set_fields_readonly(self.getReadOnlyFields(action=ctx.action))
        if self.template:
            ctx.set_optional("mapped_project_manager")

    def resetValues(self, ctx):
        if ctx.action == "create":
            ctx.set("is_group", 0)
        elif ctx.action == "copy":
            ctx.set(
                "is_group",
                1
                if len(
                    fTask.KeywordQuery(
                        cdb_project_id=ctx.cdbtemplate.cdb_project_id, ce_baseline_id=""
                    )
                )
                else 0,
            )
        ctx.set("msp_z_nummer", "")
        ctx.set("taskboard_oid", "")

    def copyAllTasksWithRelations(self, ctx):
        with transactions.Transaction():
            task_id_mapping_table = {}
            persistent_object = self.getPersistentObject()
            project_template = Project.ByKeys(
                cdb_project_id=ctx.cdbtemplate.cdb_project_id,
                ce_baseline_id=ctx.cdbtemplate.ce_baseline_id,
            )
            for task_template in project_template.TopTasks:
                # Copy task structure
                mapping_table, _ = task_template._copy_task(
                    ctx, persistent_object.cdb_project_id, "", clear_msp_task_ids=False
                )
                task_id_mapping_table.update(mapping_table)
            # Copy task relations
            fTask._copy_taskrels_by_mapping(
                ctx.cdbtemplate.cdb_project_id,
                persistent_object.cdb_project_id,
                task_id_mapping_table,
            )
            # Following line is a little confusing: within the method for copying tasks and their referenced
            # objects, a call is hidden, which copies all checklists - as well as checklists without reference
            # to a task
            project_template.copyRelatedObjects(persistent_object)
            persistent_object.Reload()
            persistent_object.initTaskRelationOIDs()

    def approximate_to_forecast(self, ctx):
        if ctx and hasattr(ctx, "cdbtemplate"):
            self.reset_start_time(
                start_time_old=ctx.cdbtemplate.start_time_fcast,
                start_time_new=self.start_time_fcast,
            )

    def copyRelatedObjects(self, new_project):
        # Copy referenced checklists
        for checklist in self.TopLevelChecklists:
            new_checklist = checklist.MakeCopy(new_project)
            new_checklist.Reset()

        # Copy referenced objects (eg. resource demands)
        sig.emit(Project, "copy_project_hook")(self, new_project)

    def on_cdbpcs_new_subtask_now(self, ctx):
        create_msg = cmsg.Cdbcmsg("cdbpcs_task", constants.kOperationNew, True)
        create_msg.add_item("cdb_project_id", "cdbpcs_task", self.cdb_project_id)
        ctx.url(create_msg.eLink_url())

    def start_project_dashboard(self, ctx):
        if len(ctx.objects) > MY_PROJECTS_MAX_RECORDS:
            raise ue.Exception(
                "cdbpcs_open_dashboard_num_too_big", MY_PROJECTS_MAX_RECORDS
            )

        from cs.pcs.dashboard import ProjectOverviewApp

        project_ids = [f"project={project.cdb_project_id}" for project in ctx.objects]
        url_params = f"?{'&'.join(project_ids)}"
        return ProjectOverviewApp.OpenPageURL(
            ProjectOverviewApp.getModuleURL() + url_params
        )

    def updateTeam(self):
        """
        update team members to exactly reflect current subject assignments

        this method will be called whenever the project subjects change, but
        not if a project subject changes at a lower level (e.g. a common role
        that is part of the project members has its subjects changed)
        """
        persons = []

        for role in self.Roles:
            persons += role.getPersons()

        with transactions.Transaction():
            self.TeamMembers.Delete()
            for person in set(persons):
                self.assignTeamMember(person)

    def check_project_role_assignments(self, ctx=None):
        """Called when assignments to a project role is changed."""
        for role in self.Roles:
            if role.Owners:
                if not role.team_assigned:
                    role.Update(team_assigned=1)
            else:
                if role.team_assigned:
                    role.Update(team_assigned=0)

    def check_project_role_needed(self, ctx=None):
        """Called when status of project, task, checklist,
        checklist item or issue is changed.
        If any such object within the project has a project role as
        responsible, check if the role has been assigned to a person.
        """
        sql_list = [
            """SELECT subject_id FROM cdbpcs_task
                WHERE cdb_project_id = '{cdb_project_id}'
                AND ce_baseline_id = '{ce_baseline_id}'
                AND subject_type = 'PCS Role'
                AND status IN (20, 50)
            """,
            """SELECT subject_id FROM cdbpcs_checklst
                WHERE cdb_project_id = '{cdb_project_id}'
                AND subject_type = 'PCS Role'
                AND status = 20
            """,
            """SELECT subject_id FROM cdbpcs_cl_item
                WHERE cdb_project_id = '{cdb_project_id}'
                AND subject_type = 'PCS Role'
                AND status = 20
            """,
            """SELECT subject_id FROM cdbpcs_issue
                WHERE cdb_project_id = '{cdb_project_id}'
                AND subject_type = 'PCS Role'
                AND status IN (30, 50, 70, 100)
            """,
        ]
        sql = " UNION ".join(sql_list)
        assigned_roles = sqlapi.RecordSet2(sql=sql.format(**self))
        assigned_roles_urgent = [x.subject_id for x in assigned_roles]
        sql_list = [
            """SELECT subject_id FROM cdbpcs_task
                WHERE cdb_project_id = '{cdb_project_id}'
                AND ce_baseline_id = '{ce_baseline_id}'
                AND subject_type = 'PCS Role'
                AND status = 0
            """,
            """SELECT subject_id FROM cdbpcs_checklst
                WHERE cdb_project_id = '{cdb_project_id}'
                AND subject_type = 'PCS Role'
                AND status = 0
            """,
            """SELECT subject_id FROM cdbpcs_cl_item
                WHERE cdb_project_id = '{cdb_project_id}'
                AND subject_type = 'PCS Role'
                AND status = 0
            """,
            """SELECT subject_id FROM cdbpcs_issue
                WHERE cdb_project_id = '{cdb_project_id}'
                AND subject_type = 'PCS Role'
                AND status = 0
            """,
        ]
        sql = " UNION ".join(sql_list)
        assigned_roles = sqlapi.RecordSet2(sql=sql.format(**self))
        assigned_roles_later = [x.subject_id for x in assigned_roles]
        for role in self.Roles:
            if role.role_id in assigned_roles_urgent:
                if role.team_needed != 2:
                    role.Update(team_needed=2)
            elif role.role_id in assigned_roles_later:
                if role.team_needed != 1:
                    role.Update(team_needed=1)
            else:
                if role.team_needed != 0:
                    role.Update(team_needed=0)

    def adjust_role_assignments(self, ctx=None):
        self.check_project_role_needed(ctx)
        self.check_project_role_assignments(ctx)

    # copy: pre
    # set parent project in batch mode
    def set_parent_project_batch(self, ctx):
        if ctx.interactive == 0 and not ctx.uses_webui:
            self.set_parent_project(ctx)

    # ensure that parent project is correct
    def set_parent_project(self, ctx):
        def update(parent_pid):
            parent_prj = Project.ByKeys(cdb_project_id=parent_pid)
            self.Update(
                template=0,
                parent_project=parent_prj.cdb_project_id,
                parent_project_name=parent_prj.project_name,
            )

        parent_attr = ctx.parent.get_attribute_names()
        if "cdb_project_id" in parent_attr and self.ce_baseline_id == "":
            update(ctx.parent["cdb_project_id"])
        else:
            if (
                ctx.uses_webui
                and hasattr(ctx.dialog, "parent_project")
                and ctx.dialog.parent_project
                and self.ce_baseline_id == ""
            ):
                # in case of create from template a copy operation is fired
                # need to update with the selected parent project
                update(ctx.dialog.parent_project)
            else:
                self.Update(template=0, parent_project="", parent_project_name="")

    def ChangeState(self, new_state, **kwargs):
        try:
            utils.add_to_change_stack(self)
            super().ChangeState(new_state, **kwargs)
        finally:
            utils.unregister_from_change_stack(self)

    def init_status_change(self, ctx=None):
        utils.add_interactive_call(self)

    def end_status_change(self, ctx=None):
        changes = utils.remove_from_change_stack(self, ctx)
        if changes:
            self.do_status_updates(changes)

    def hide_search_for_roles(self, ctx):
        ctx.disable_registers(["pcs_role_assignments"])

    def check_for_discarded_tasks(self, ctx):
        """Check if there are any discarded tasks before
        changing the MSP Version from Professional to Standard"""
        if self.msp_active == 2:
            for task in self.Tasks:
                if task.status == 180:
                    raise ue.Exception(
                        "cdbpcs_msp_modify_project_standard_no_discarded_tasks"
                    )

    event_map = {
        (("create", "copy"), "pre"): (
            "checkProjectLevel",
            "checkProjectId",
            "verifyProjectManager",
            "setTemplateOID",
            "setWorkflow",
            "setProjectId",
            "setPosition",
            "setBaselineIDs",
        ),
        (("create", "copy"), "pre_mask"): (
            "setDefaults",
            "setInitValues",
            "resetValues",
        ),
        (("modify"), "pre_mask"): (
            "hide_search_for_roles",
            "setInitValues",
        ),
        (("info"), "pre_mask"): ("hide_search_for_roles"),
        (("create", "copy", "modify"), "dialogitem_change"): ("dialog_item_change"),
        (("modify"), "pre"): (
            "checkProjectLevel",
            "changeMSP",
            "recalculate_preparation",
            "checkParent",
            "validate_and_update_days_act",
        ),
        (("modify"), "post"): ("setProjectManager", "recalculate"),
        (("create"), "post"): (
            "setProjectManager",
            "recalculate",
            "createFollowUp",
            "adjust_role_assignments",
        ),
        (("create", "copy", "modify"), "pre"): (
            "checkEffortFields",
            "_correctCalendarDates",
        ),
        (("query_catalog"), ("pre_mask", "pre")): ("_set_template_catalog_query_args"),
        (("copy"), "post"): (
            "copyAllTasksWithRelations",
            "approximate_to_forecast",
            "recalculate",
            "adjust_role_assignments",
        ),
        (("copy"), "pre"): ("set_parent_project_batch"),
        (("wf_step"), "post"): ("_handleSubscriptions"),
        ("cdbpcs_launch_project_dashboard", "now"): ("start_project_dashboard"),
        ("delete", "pre"): ("setTemplateOID"),
        (("state_change"), "pre"): ("init_status_change"),
        (("state_change"), "post"): ("end_status_change"),
    }


# Deprecated since cs.pcs 15.4.1 / E039981: Use Project.default_roles directly
default_roles = Project.default_roles


class ProjectCategory(Object):
    __maps_to__ = "cdbpcs_proj_cat"

    @classmethod
    def on_CDB_GenProjectsDecomp_now(cls, ctx):
        cls.GenerateDecomposition()

    @classmethod
    def GenerateDecomposition(cls):
        sa = util.PersonalSettings().getValueOrDefaultForUser(
            "decomp_sort_attribute", "PROJECT", "caddok", "name_d"
        )
        decompsource = decomp.DecompSource(
            source_id=None,
            relation="cdbpcs_proj_cat",
            key_attr="name",
            parent_key_attr=None,
            attribute_mappings={"category": "name"},
            c_conditions={},
            s_conditions={},
            label_attribute="name_<language>",
            position_attr="",
            icon_attr="",
            leaf_attr="",
            default_icon="Folder",
            leaf_icon="Folder",
            root_id="",
            order_by=sa,
            table_attr="",
            py_generator=__name__ + ".ProjectCategory.GenerateDecomposition",
            obsolete_attr="obsolete",
        )
        # remove decompositions based on the source object
        decompsource.delete_decompositions()
        # create decomposition
        decompsource.generate_decomposition("CDBPCS_PROJECTS")


class DomainAssignment(Object):
    Project = Reference_1(fProject, fDomainAssignment.cdb_project_id)

    __maps_to__ = "cdbpcs_prj_acd"


class TeamMember(Object):
    __maps_to__ = "cdbpcs_team"

    Project = Reference_1(fProject, fTeamMember.cdb_project_id)
    Person = Reference_1(org.Person, fTeamMember.cdb_person_id)

    def setDefaultRoles(self, ctx):
        if ctx.error != 0:
            return
        for role_id in self.Project.default_roles:
            self.Project.createRole(role_id).assignSubject(self.Person, ctx)

    def checkProjectStatus(self, ctx):
        """
        if the person already has been assigned a role in the project,
        then the person will be deleted from the role.

        :Parameters:
            ``ctx``: *Context*

        """

        sql_query = f"""
        SELECT role_id, subject_id2, subject_id, subject_type, exception_id, cdb_project_id
        FROM cdbpcs_subject
        WHERE subject_id='{self.Person.personalnummer}'
        AND cdb_project_id='{self.Project.cdb_project_id}'
        """
        rec_set = sqlapi.RecordSet2(sql=sql_query)

        if rec_set:
            for pers in rec_set:
                obj_id = f"""
                role_id='{pers.role_id}' AND
                cdb_project_id='{pers.cdb_project_id}' AND
                subject_id='{pers.subject_id}' AND
                subject_id2='{pers.subject_id2}' AND
                subject_type='{pers.subject_type}' AND
                exception_id='{pers.exception_id}'
                """

                SubjectAssignment.Query(obj_id)[0].Delete()

    def checkTasks(self, _ctx):
        """
        the methode checkt the assignment between task and person.

        :Parameters:
            ``ctx``: *Context*

        :raise cdbpcs_check_tasks: Team member can not be deleted, beacause this
            team member was already added as responsible!
        """

        # # Suche Rollenzuweisung einer Person
        mylist = self.Project.Tasks.KeywordQuery(
            subject_id=self.Person.personalnummer,
            subject_type="Person",
            ce_baseline_id="",
        )
        if mylist:
            raise ue.Exception(
                "cdbpcs_check_tasks", self.Person.name, mylist[0].task_name
            )

    def _handleSubscription(self, _ctx):
        """
        Subscribe the team-member to the projects activity channel.
        """
        if self.Project:
            self.Project.handleAutoSubscription([self])

    # noinspection PyUnusedLocal
    def keep_at_least_the_project_manager(self, ctx):
        """
        Ensures that a project manager is always assigned to the project
        by preventing the deletion of the person in the project role.
        It also takes into account removing a project manager
        by removing the assignment to the project role.
        """
        if self.cdb_person_id == self.Project.project_manager:
            raise_keep_at_least_prj_mgr(self.Person.getSubjectName())

    def unsubscribeMember(self, _ctx):
        """
        unsubscribes the member from the project.
        """
        Subscription.unsubscribeFromChannel(
            self.Project.cdb_object_id, self.Person.personalnummer
        )

    event_map = {
        ("delete", "pre"): ("keep_at_least_the_project_manager", "checkTasks"),
        ("delete", "post"): ("unsubscribeMember"),
        (("create", "copy"), "post"): ("setDefaultRoles", "_handleSubscription"),
    }


class SubjectAssignment(org.WithSubject, WithAuditTrail):
    __maps_to__ = "cdbpcs_subject"

    Role1 = Reference_1(
        fRole, fSubjectAssignment.role_id, fSubjectAssignment.cdb_project_id
    )
    Role2 = Reference_1(
        fRole, fSubjectAssignment.subject_id, fSubjectAssignment.subject_id2
    )
    CommonRole2 = Reference_1(org.CommonRole, fSubjectAssignment.subject_id)
    Project = Reference_1(fProject, fSubjectAssignment.cdb_project_id)

    def referencedAuditTrailObjects(self):
        return [self, self.Role1]

    def on_create_pre(self, _ctx):
        role = self.Role1
        role2 = None
        if self.subject_type == Role.__subject_type__:
            role2 = self.Role2
        elif self.subject_type == "Common Role":
            role2 = self.CommonRole2
        if role and role2:
            myRoles = role.Roles
            myRoles2 = role2.Roles
            if role == role2 or role in myRoles2 or role2 in myRoles:
                raise ue.Exception("cdbpcs_subject_recursion")

    def updateTeam(self, ctx):
        if ctx.error:
            return
        self.Project.updateTeam()

    @classmethod
    def get_further_role_member(
        cls, cdb_project_id, subject_id, role_id=kProjectManagerRole
    ):
        return fSubjectAssignment.Query(
            f"role_id = '{sqlapi.quote(role_id)}' "
            f"AND cdb_project_id = '{sqlapi.quote(cdb_project_id)}' "
            f"AND subject_id != '{sqlapi.quote(subject_id)}'"
        )

    # noinspection PyUnusedLocal
    def keep_at_least_the_project_manager(self, ctx):
        """
        Ensures that a project manager is always assigned to the project
        by preventing the deletion of this person in the project role.
        It also takes into account removing a project manager
        by removing the assignment to the project role.
        """
        if self.role_id not in [kProjectManagerRole, kProjectMemberRole]:
            return
        if self.subject_id == self.Project.project_manager:
            raise_keep_at_least_prj_mgr(self.getSubjectName())

    def check_project_role_assignments(self, ctx):
        self.Project.check_project_role_assignments(ctx)

    event_map = {
        ("delete", "pre"): "keep_at_least_the_project_manager",
        (("create", "copy", "modify", "delete"), "post"): (
            "updateTeam",
            "check_project_role_assignments",
        ),
    }


class PersonAssignment(SubjectAssignment):
    __classname__ = "cdbpcs_subject_per"
    __match__ = SubjectAssignment.cdb_classname >= __classname__

    def _auto_complete_hidden_fields(self, ctx):
        """
        If an assignment will be created by drag & drop, hidden
        fields are initialized to prevent the input dialog from appearing.
        """
        if not ctx.dragdrop_action_id:
            return
        ctx.set("subject_id2", "")
        ctx.set("exception_id", "")

    def on_create_post(self, ctx):
        if ctx.error:
            return
        # Automatisch dem Team und Projekmitglied/Default-Rollen zuordnen
        person = org.Person.ByKeys(personalnummer=self.subject_id)

        # due to E018328 - it makes more sense to
        # assign the default roles to every person
        # if self.role_id == kProjectManagerRole:
        if self.Project:
            for dft_role_id in self.Project.default_roles:
                role = self.Project.RolesByID[dft_role_id]
                if role:
                    role.assignSubject(person)

    def on_copy_post(self, ctx):
        if ctx.error:
            return
        person = org.Person.ByKeys(personalnummer=self.subject_id)
        prj = Project.ByKeys(
            cdb_project_id=self.cdb_project_id, ce_baseline_id=self.ce_baseline_id
        )
        prj.assignTeamMember(person)

    def on_delete_pre(self, _ctx):
        if not self.Project:
            return
        self.keep_at_least_the_project_manager(_ctx)
        if self.role_id == kProjectMemberRole:
            mylist = self.Project.Tasks.KeywordQuery(
                subject_id=self.subject_id, subject_type="Person", ce_baseline_id=""
            )
            if mylist:
                raise ue.Exception(
                    "cdbpcs_check_person_task_assignment",
                    self.Subject.name,
                    mylist[0].task_name,
                )

    def on_delete_post(self, _ctx):
        person = org.Person.ByKeys(personalnummer=self.subject_id)
        if self.Project and person and self.role_id == kProjectMemberRole:
            addtl_assignments = PersonAssignment.KeywordQuery(
                subject_id=self.subject_id, cdb_project_id=self.cdb_project_id
            )
            for assignment in addtl_assignments:
                assignment.Delete()
            Subscription.unsubscribeFromChannel(
                self.Project.cdb_object_id, self.subject_id
            )

    event_map = {("create", "pre_mask"): "_auto_complete_hidden_fields"}


class CommonRoleAssignment(SubjectAssignment):
    __classname__ = "cdbpcs_subj_com_role"
    __match__ = SubjectAssignment.cdb_classname >= __classname__

    def _auto_complete_hidden_fields(self, ctx):
        """
        If an assignment will be created by drag & drop, hidden fields
        are initialized to prevent the input dialog from appearing.
        """
        if not ctx.dragdrop_action_id:
            return
        ctx.set("subject_id2", "")
        ctx.set("exception_id", "")

    event_map = {("create", "pre_mask"): "_auto_complete_hidden_fields"}


class PCSRoleAssignment(SubjectAssignment):
    __classname__ = "cdbpcs_subj_prj_role"
    __match__ = SubjectAssignment.cdb_classname >= __classname__

    Project = Reference_1(fProject, fPCSRoleAssignment.cdb_project_id)

    def _auto_complete_hidden_fields(self, ctx):
        """
        If an assignment will be created by drag & drop, hidden fields
        are initialized to prevent the input dialog from appearing.
        """
        if not ctx.dragdrop_action_id:
            return
        ctx.set("exception_id", "")

    event_map = {
        ("create", "pre_mask"): "_auto_complete_hidden_fields",
    }


class Role(org.OCRole, WithAuditTrail):
    __maps_to__ = "cdbpcs_prj_role"
    __subject_type__ = PCS_ROLE
    __subject_assign_cls__ = SubjectAssignment
    __context_attr__ = "cdb_project_id"
    __default_action__ = "CDBPCS_Role"

    __subject_type_map__ = {
        "Person": PersonAssignment,
        "Common Role": CommonRoleAssignment,
        PCS_ROLE: PCSRoleAssignment,
    }

    @classmethod
    def BySubjectReferrer(cls, referrer):
        return cls.ByKeys(
            role_id=referrer.subject_id, cdb_project_id=referrer.cdb_project_id
        )

    SubjectAssignmentsByType = ReferenceMapping_N(
        fSubjectAssignment,
        fSubjectAssignment.role_id == fRole.role_id,
        fSubjectAssignment.cdb_project_id == fRole.cdb_project_id,
        indexed_by=fSubjectAssignment.subject_type,
    )

    Tasks = Reference_N(
        fTask,
        fTask.subject_id == fRole.role_id,
        fTask.cdb_project_id == fRole.cdb_project_id,
        fTask.subject_type == PCS_ROLE,
    )

    Checklists = Reference_N(
        fChecklist,
        fChecklist.subject_id == fRole.role_id,
        fChecklist.cdb_project_id == fRole.cdb_project_id,
        fChecklist.subject_type == PCS_ROLE,
    )

    ChecklistItems = Reference_N(
        fChecklistItem,
        fChecklistItem.subject_id == fRole.role_id,
        fChecklistItem.cdb_project_id == fRole.cdb_project_id,
        fChecklistItem.subject_type == PCS_ROLE,
    )

    Issues = Reference_N(
        fIssue,
        fIssue.subject_id == fRole.role_id,
        fIssue.cdb_project_id == fRole.cdb_project_id,
        fIssue.subject_type == PCS_ROLE,
    )

    def assignSubject(self, subject, ctx=None):
        if not subject:
            return
        subj_type = subject.SubjectType()
        if subj_type not in self.__subject_type_map__:
            raise RuntimeError(f"invalid subject types {subj_type}")

        valdict = self._key_dict()
        sid = subject.SubjectID()
        valdict["subject_id"] = sid[0]
        valdict["subject_id2"] = sid[1]
        valdict["subject_type"] = subject.SubjectType()
        valdict["exception_id"] = ""

        assign_cls = self.__subject_type_map__.get(subj_type, None)
        if assign_cls:
            res = assign_cls.ByKeys(**valdict)
            if res is None or res.IsDeleted():
                res = assign_cls.Create(**valdict)
                audittrail = res.createAuditTrail("create")
                if audittrail:
                    clsname = res.GetClassname()
                    res.createAuditTrailDetail(
                        audittrail_object_id=audittrail.audittrail_object_id,
                        clsname=clsname,
                        attribute="subject_type",
                        old_value="",
                        new_value=valdict["subject_type"],
                    )
                    res.createAuditTrailDetail(
                        audittrail_object_id=audittrail.audittrail_object_id,
                        clsname=clsname,
                        attribute="subject_id",
                        old_value="",
                        new_value=valdict["subject_id"],
                    )
                    res.createAuditTrailDetail(
                        audittrail_object_id=audittrail.audittrail_object_id,
                        clsname=clsname,
                        attribute="cdb_project_id",
                        old_value="",
                        new_value=valdict["cdb_project_id"],
                    )
        # wg. AEnderungen an den Rollenzuordnungen den Rollencache explizit
        # aktualisieren (In Abhaengigkeit vom Property cmlt auch fuer andere Anwender)
        if ctx:
            ctx.refresh_caches(util.kCGRoleCaches, util.kSynchronizedReload)

    def _check_no_tasks(self, _ctx=None):
        if self.Tasks or self.Checklists or self.ChecklistItems or self.Issues:
            raise ue.Exception("cdbpcs_role_still_used")

    def remove_prj_role(self, ctx):
        """
        In a project, if the Project Manager role is deleted,
        the exception is raised that this role must not be deleted.
        Exception also says that this role must have at least one member
        who has sufficient access rights to manage the project.
        """
        if self.role_id == kProjectManagerRole:
            raise util.ErrorMessage("cdbpcs_role_del", self.mapped_name)

    def getSubjectName(self):
        return self["mapped_name"]

    def on_create_pre(self, ctx):
        self.team_needed = 0
        self.team_assigned = 0

    event_map = {
        (("delete"), "pre"): ("_check_no_tasks", "remove_prj_role"),
    }


@classbody
class SchemaComponent:
    Project = Reference_1(fProject, SchemaComponent.cdb_project_id)


@classbody
class InfoMessage:
    Project = Reference_1(Project, InfoMessage.cdb_project_id)


@classbody
class Process:
    Project = Reference_1(fProject, Process.cdb_project_id)

    @classmethod
    def getPCSRoleType(cls):
        """
        Returns pcs role subject type.
        """
        return Role.__subject_type__

    @classmethod
    def getPCSRoles(cls, cdb_project_id, role_id=None):
        """
        Returns pcs roles specified by `cdb_project_id` and, if given,
        by `role_id`. The result is always an `cdb.objects.ObjectCollection`.
        """
        cond = f"cdb_project_id='{sqlapi.quote(cdb_project_id)}'"
        if role_id:
            cond += f" and role_id='{sqlapi.quote(role_id)}'"
        return fRole.Query(cond)


@classbody
class Action:

    Project = Reference_1(fProject, Action.cdb_project_id)


@classbody
class Person:

    constDefaultCalendarProfileName = "Standard"

    constDefaultWorkdays = {
        "1": True,
        "2": True,
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
    }

    @property
    def DefaultCalendarProfileName(self):
        """
        Returns the name of the default calendar profile to be used by creating a person
        Can be overwritten by customizations in order to preset the name depending on location,
        organization or whatever needed
        :return: string
        """
        return self.constDefaultCalendarProfileName

    @property
    def default_work_days(self):
        """
        Defines the default values, which weekdays are working days
        :rtype: dict
        """
        return self.constDefaultWorkdays

    @staticmethod
    def manage_resource_input_fields(is_resource, context_object):
        """
        Input fields of resource management are tagged as optional or mandatory fields
        :param is_resource:
        :param context_object:
        :return: None
        """
        fields = [
            ".mapped_calendar_profile",
            "angestellter.capacity",
        ]
        if is_resource:
            for field in fields:
                context_object.set_mandatory(field)
        else:
            for field in fields:
                context_object.set_optional(field)

    @staticmethod
    def manage_default_calendar_profile(
        is_resource, calendar_profile_id, context_object
    ):
        """
        If the person has been tagged as resource, default calendar profile to be set
        :param is_resource:
        :param calendar_profile_id:
        :param context_object:
        :return: None
        """
        if not is_resource:
            return
        if is_resource and calendar_profile_id:
            return

        # Use the class variable `constDefaultCalendarProfileName`, because the hook is
        # also on new executed, when the person object does not exist.
        calendar_profile = fCalendarProfile.get_by_name(
            Person.constDefaultCalendarProfileName
        )
        if calendar_profile:
            context_object.set(
                "angestellter.calendar_profile_id", calendar_profile.cdb_object_id
            )
            context_object.set(".mapped_calendar_profile", calendar_profile.name)

    @sig.connect(Person, "modify", "pre_mask")
    def _modify_pre_mask(self, ctx):
        Person.manage_resource_input_fields(self.is_resource, ctx)

    @sig.connect(Person, "create", "dialogitem_change")
    @sig.connect(Person, "copy", "dialogitem_change")
    @sig.connect(Person, "modify", "dialogitem_change")
    def resource_dialog_item_change(self, ctx):
        if ctx.changed_item == "is_resource":
            Person.manage_resource_input_fields(self.is_resource, ctx)
            Person.manage_default_calendar_profile(
                self.is_resource, self.calendar_profile_id, ctx
            )

    @staticmethod
    def handle_is_resource_change_web(hook):
        Person.manage_resource_input_fields(
            hook.get_new_values()["angestellter.is_resource"], hook
        )
        Person.manage_default_calendar_profile(
            hook.get_new_values()["angestellter.is_resource"],
            hook.get_new_values()[".mapped_calendar_profile"],
            hook,
        )

    @sig.connect(Person, "create", "pre")
    @sig.connect(Person, "copy", "pre")
    @sig.connect(Person, "modify", "pre")
    def _ensureCalendarProfileForResource(self, ctx):
        if self.is_resource and not self.calendar_profile_id:
            raise ue.Exception("cdb_cal_prof_mand")

    @sig.connect(Person, "create", "pre")
    @sig.connect(Person, "copy", "pre")
    @sig.connect(Person, "modify", "pre")
    def _ensureCapacityForResource(self, ctx):
        if not self.is_resource:
            return
        if not self.capacity or self.capacity <= 0:
            raise ue.Exception("cdbpcs_resource_with_invalid_capacity")


class ProjectResponsibleProvider(PythonColumnProvider):
    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [
            {
                "column_id": "responsible_txt",
                "label": util.get_label("cdbpcs_project_responsibles"),
                "data_type": "text",
            }
        ]

    @staticmethod
    @lru_cache()
    def getProjectResponsibles(cdb_project_id):
        """
        This method should be used in other applications too.
        The caching is with web apps in mind, which would call this method
        multiple times for the same project
        """
        result = ""
        _role = Role.KeywordQuery(
            cdb_project_id=cdb_project_id, role_id=kProjectManagerRole
        )
        if len(_role):
            role = _role[0]
            result = "; ".join([pers.getSubjectName() for pers in role.Persons])
        return result

    @staticmethod
    def getColumnData(classname, table_data):
        return [
            {
                "responsible_txt": ProjectResponsibleProvider.getProjectResponsibles(
                    data["cdb_project_id"]
                ),
            }
            for data in table_data
        ]

    @staticmethod
    def getRequiredColumns(classname, available_columns):
        return ["cdb_project_id"]


@sig.connect(FILE_EVENT, Project.__maps_to__, any)
def _file_event_handler(the_file, _, ctx):
    if ctx.action == "CDB_Lock" and the_file.cdb_lock:
        CDB_File.ByKeys(the_file.cdb_object_id).Update(cdb_lock="", cdb_lock_date="")


class RiskClass(Object):
    __maps_to__ = "cdbrm_risk_class"
    __classname__ = "cdbrm_risk_class"


class ProjectExceptionalAccessRight(Object):
    __maps_to__ = "cdbpcs_role_exc"
    __classname__ = "cdbpcs_role_exc"


class ManualSignalIconEvaluation(Object):
    __maps_to__ = "cdbpcs_rat_val_lights"
    __classname__ = "cdbpcs_rat_val_lights"
