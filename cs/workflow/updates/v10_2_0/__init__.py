# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from cdb import tools
from cdb import sqlapi
from cdb import util
from cdb import ddl
from cdb import objects
from cdb import transactions

from cdb.platform import FolderContent
from cdb.comparch import modules
from cdb.comparch import protocol

from cs.workflow.processes import Process

from cs.workflow import constraints
from cs.workflow import systemtasks
from cs.workflow import tasks
from cs.workflow import taskgroups
from cs.workflow import schemacomponents

DESCRIPTION = "Automatically created for the migration of '%s'"
TASK_TITLE = "%s - state change"


class InstallOptionalChanges(object):
    def run(self):
        mod = modules.Module.ByKeys('cs.workflow')
        prot_id = protocol.ProtocolContext.current_protocol_id()
        mod.install_optional_changes(prot_id)

        # Install cdb_prop manually (because its update policy is 'Never Updated')
        rs = sqlapi.RecordSet2(table="cdb_prop", columns=["count(*) as n"],
                               condition="attr='wffo' AND subject_id='public' and subject_type='Common Role'")
        if not rs or not rs[0].n:
            sqlapi.SQLinsert("INTO cdb_prop (attr, value, subject_id, subject_type, cdb_module_id) "
                             "VALUES ('wffo', 'false', 'public', 'Common Role', 'cs.workflow')")

        # Install cdb_global_subj manually (because its update policy is 'Never Updated')
        rs = sqlapi.RecordSet2(table="cdb_global_subj", columns=["count(*) as n"],
                               condition="role_id='cdbwf: Process Library Manager' AND "
                                         "subject_id='cdbwf: Process Administrator' AND "
                                         "subject_type='Common Role' AND "
                                         "exception_id=''")
        if not rs or not rs[0].n:
            sqlapi.SQLinsert("INTO cdb_global_subj "
                             "(cdb_classname, cdb_module_id, exception_id, role_id, subject_id, subject_type) "
                             "VALUES "
                             "('cdb_gl_subj_role', 'cs.workflow', '', 'cdbwf: Process Library Manager', "
                             "'cdbwf: Process Administrator', 'Common Role')")


class MigrateWorkflows(object):
    def run(self):
        self._ensure_task("Information",
                          name_de="Information",
                          name_en="Information",
                          function_fqpyname="cs.workflow.systemtasks.generate_info_message")

        self._ensure_task("Statuswechsel",
                          name_de="Statusänderung",
                          name_en="Status Change",
                          function_fqpyname="cs.workflow.systemtasks.status_change")

        for process in Process.Query():
            self.update_workflow(process)

    def _ensure_task(self, name, **args):
        td = systemtasks.SystemTaskDefinition.ByKeys(name=name)
        if not td:
            systemtasks.SystemTaskDefinition.Create(name=name, **args)

    def update_workflow(self, process):
        with transactions.Transaction():
            if process.cdb_classname == "cdbwf_ahwf_process":
                process.cdb_classname = "cdbwf_process"

            process.ensure_process_completion()
            process.Reload()

            if not process.AllBriefcases:
                table = ddl.Table("cdbwf_orole")
                if table and table.exists():
                    self.migrate_object_roles(process)

            self.convert_information_tasks(process)
            self.migrate_manual_taskgroups(process)

    def migrate_object_roles(self, process):
        from cs.workflow import briefcases

        cdb_process_id = process.cdb_process_id
        rs = sqlapi.RecordSet2(table="cdbwf_orole",
                               condition="cdb_process_id='%s'" % cdb_process_id)

        # For every object role create a briefcase
        briefcase_id = 0

        for record in rs:
            briefcase_id = briefcases.Briefcase.new_briefcase_id()

            # Create briefcase
            briefcase = briefcases.Briefcase.Create(briefcase_id=briefcase_id,
                                                    cdb_process_id=cdb_process_id,
                                                    name=record.role_name)
            self.populate_briefcase(briefcase, record.role_id)

            bflink_args = {"briefcase_id": briefcase_id,
                           "cdb_process_id": cdb_process_id,
                           "iotype": briefcases.IOType.edit.value,  # @UndefinedVariable
                           "extends_rights": 0,
                           "task_id": ""}

            # fetch cdbwf_orule records from the datenbank
            condition = ("cdb_process_id='%s' "
                         "AND role_id='%s' " % (cdb_process_id, record.role_id))
            rs2 = sqlapi.RecordSet2('cdbwf_orule', condition=condition)

            # Create success system task
            if any([r.target_state for r in rs2]):
                if process.status in [Process.NEW.status, Process.READY.status]:
                    status = tasks.Task.NEW
                elif process.status == Process.DONE.status:
                    status = tasks.Task.DONE
                else:
                    status = tasks.Task.CANCELLED

                title = TASK_TITLE % (record.role_name + " successful")
                st_success = self._create_system_task(process,
                                                      title,
                                                      invert_constraint=0,
                                                      status=status)

                # Create briefcase link
                bflink_args["task_id"] = st_success.task_id
                briefcases.BriefcaseLink.Create(**bflink_args)

            # Create failure system task
            if any([r.failure_target_state for r in rs2]):
                if process.status in [Process.NEW.status, Process.READY.status]:
                    status = tasks.Task.NEW
                elif process.status == Process.DONE.status:
                    status = tasks.Task.CANCELLED
                else:
                    status = tasks.Task.DONE

                title = TASK_TITLE % (record.role_name + " failure")
                st_failure = self._create_system_task(process,
                                                      title,
                                                      invert_constraint=1,
                                                      status=status)

                # Create briefcase link
                bflink_args["task_id"] = st_failure.task_id
                briefcases.BriefcaseLink.Create(**bflink_args)

            # if that briefcase should be displayed as global one
            if record.display_link == "1":
                # already used as local briefcase, need a new one
                if bflink_args["task_id"] != "":
                    briefcase_id = briefcases.Briefcase.new_briefcase_id()
                    global_bc = briefcases.Briefcase.Create(briefcase_id=briefcase_id,
                                                            cdb_process_id=cdb_process_id,
                                                            name=record.role_name)
                    self.populate_briefcase(global_bc, record.role_id)
                    bflink_args["briefcase_id"] = briefcase_id

                bflink_args["iotype"] = briefcases.IOType.info.value
                bflink_args["task_id"] = ""
                # create global link
                briefcases.BriefcaseLink.Create(**bflink_args)

            # Create object filters and parameters
            for rule_record in rs2:
                rule = self._create_object_rule(rule_record.objektart,
                                                rule_record.state_constraints)

                if rule_record.target_state:
                    self._create_object_filter(process, st_success.task_id,
                                               rule, rule_record.target_state)

                if rule_record.failure_target_state:
                    self._create_object_filter(process, st_failure.task_id,
                                               rule, rule_record.failure_target_state)

    def convert_information_tasks(self, process):
        """ Convert information tasks to system tasks """
        task_definitions = systemtasks.SystemTaskDefinition.KeywordQuery(name="Information")
        if not task_definitions:
            raise RuntimeError("System task definition not found")
        task_definition = task_definitions[0]

        def set_parameter(task_id, name, value):
            # Create parameter
            tasks.FilterParameter.Create(cdb_process_id=process.cdb_process_id,
                                         task_id=task_id,
                                         name=name,
                                         rule_name='',
                                         value=value,)

        condition = "cdb_classname='%s' AND cdb_process_id='%s'" % ("cdbwf_task_information",
                                                                    process.cdb_process_id)
        rs = sqlapi.RecordSet2(table="cdbwf_task", condition=condition)
        for record in rs:
            parent_task = schemacomponents.SchemaComponent\
                .ByKeys(cdb_process_id=process.cdb_process_id, task_id=record.parent_id)
            if parent_task:
                # Create a new system task

                if record.status == tasks.Task.NEW.status:
                    status = tasks.Task.NEW
                elif record.status in [tasks.Task.READY.status,
                                       tasks.Task.DONE.status]:
                    status = tasks.Task.DONE
                else:
                    status = tasks.Task.CANCELLED
                status_txt = tasks.Task.GetStateText(status)

                # subject_id must be caddok, because the workflow service has not
                # been installed yet, therefore we can't use the method
                # SystemTask.set_service_user
                st = tasks.SystemTask.Create(cdb_process_id=process.cdb_process_id,
                                             task_id=tasks.Task.new_task_id(),
                                             parent_id=record.parent_id,
                                             cdb_project_id=record.cdb_project_id,
                                             position=record.position,
                                             finish_option=0,
                                             task_definition_id=task_definition.cdb_object_id,
                                             title=record.title,
                                             description=record.description,
                                             uses_global_maps=0,
                                             subject_id="caddok",
                                             subject_type="Person",
                                             status=status.status,
                                             cdb_status_txt=status_txt)

                # Set parameters
                set_parameter(st.task_id, "title", record.title)
                set_parameter(st.task_id, "description", record.description)
                set_parameter(st.task_id, "subject_id", record.subject_id)
                set_parameter(st.task_id, "subject_type", record.subject_type)

                # Create Info messages
                if record.status in [tasks.Task.READY.status, tasks.Task.DONE.status]:
                    title_fd = systemtasks.InfoMessage.GetFieldByName("title")
                    title = record.title[:title_fd.length]

                    description_fd = systemtasks.InfoMessage.GetFieldByName("description")
                    description = record.description[:description_fd.length]

                    systemtasks.generate_info_message(
                        st,
                        content=None,
                        cdb_project_id=process.cdb_project_id,
                        title=title,
                        description=description,
                        subject_id=record.subject_id,
                        subject_type=record.subject_type,
                        is_active=0,
                    )

                # Delete the old task
                record.delete()

        process.Reload()

    def migrate_manual_taskgroups(self, process):
        # Find all manual task groups
        condition = "cdb_process_id='%s' AND "\
            "cdb_classname='cdbwf_aggregate_manual'" % process.cdb_process_id
        rs = sqlapi.RecordSet2(table="cdbwf_task", condition=condition)

        t_condition = "cdb_process_id='{cdb_process_id}' "\
            "AND parent_id='%s'".format(cdb_process_id=process.cdb_process_id)
        for record in rs:
            task_rs = sqlapi.RecordSet2(table="cdbwf_task",
                                        condition=t_condition % record.task_id)

            # Change type of the taskgroup
            record.update(cdb_classname="cdbwf_aggregate_parallel")

            for task_r in task_rs:  # @UnusedVariable
                # substitute the task with a sequential task group
                position = task_r.position
                parent_id = task_r.parent_id
                task_r.update(position=20, parent_id=sqlapi.NULL)

                if task_r.status == tasks.Task.NEW.status:
                    tg_status = record.status
                    t_status = record.status
                else:
                    tg_status = task_r.status
                    t_status = tasks.Task.DONE.status

                taskgroup = self._create_task_group(process, "sequential",
                                                    position, parent_id,
                                                    status=tasks.Task.GetState(tg_status))

                # Set the new task group as parent
                task_r.update(parent_id=taskgroup.task_id)

                # insert a new execution task before the task
                self._create_task(process,
                                  mode="execution",
                                  title='Activate manual task "%s"' % task_r.title,
                                  position=10,
                                  parent_id=taskgroup.task_id,
                                  status=tasks.Task.GetState(t_status),
                                  subject_id=process.subject_id,
                                  subject_type=process.subject_type)

    def populate_briefcase(self, briefcase, role_id):
        links = [('cdbwf_p2doc', 'cs.documents.Document'),
                 ('cdbwf_p2ec', 'cs.ec.EngineeringChange'),
                 ('cdbwf_p2mod', 'cs.documents.Document'),
                 ('cdbwf_p2part', 'cs.vp.items.Item'),
                 ('cdbwf_p2task', 'cs.pcs.projects.tasks.Task')]

        cdb_process_id = briefcase.cdb_process_id
        condition = ("cdb_process_id='%s' "
                     "AND role_id='%s'" % (cdb_process_id, role_id))

        for relation, pyname in links:
            try:
                pyclass = tools.getObjectByName(pyname)
                pkeys = [fd.name for fd in pyclass.GetTablePKeys()]

                rs = sqlapi.RecordSet2(table=relation,
                                       condition=condition)

                for record in rs:
                    args = {pkey: record.get(pkey) for pkey in pkeys}
                    for obj in pyclass.KeywordQuery(**args):
                        self._add_object_to_briefcase(briefcase,
                                                      obj.cdb_object_id)
            except ImportError:
                pass

        table = ddl.Table("cdbwf_p2obj")
        if table and table.exists():
            rs = sqlapi.RecordSet2(table='cdbwf_p2obj',
                                   condition=condition)
            for record in rs:
                self._add_object_to_briefcase(briefcase, record.cdbf_object_id)

    # Help methods

    def _add_object_to_briefcase(self, briefcase, object_id):
        FolderContent.Create(cdb_folder_id=briefcase.cdb_object_id,
                             cdb_content_id=object_id)

    def _create_object_rule(self, objektart, state_constraints):
        from cdb.objects import Rule
        from cdb.objects import Predicate

        states = []
        for st in state_constraints.split(";"):
            try:
                states.append(int(st))
            except ValueError:
                continue
        states.sort()

        if states:
            rule_name = "cs.workflow_%s_%s" % (objektart, "_".join(map(str, states)))
        else:
            rule_name = "cs.workflow_%s" % objektart
        rule = Rule.ByKeys(rule_name)

        if not rule:
            # find classname(s)
            from cdb.platform import olc
            from cdb.platform.mom import entities

            olc_wflow = olc.Workflow.ByKeys(objektart)
            classes = entities.Class.KeywordQuery(cdb_wflow_cls=olc_wflow.objclass)

            # Create rule
            rule = Rule.Create(name=rule_name,
                               description=(DESCRIPTION % "cdbwf_orules"))
            # Create predicates
            for cls in classes:
                if cls.fqpyname:
                    Predicate.Create(name=rule_name,
                                     fqpyname=cls.fqpyname,
                                     predicate_name=cls.classname)

                    # Create terms

                    # objektart
                    pyclass = tools.getObjectByName(cls.fqpyname)
                    olc_attr = pyclass.__olc_attr__

                    if pyclass.HasField(olc_attr):
                        self._create_term(name=rule_name,
                                          fqpyname=cls.fqpyname,
                                          predicate_name=cls.classname,
                                          attribute=olc_attr,
                                          operator="=",
                                          expression=objektart)

                    if states:
                        # status
                        self._create_term(name=rule_name,
                                          fqpyname=cls.fqpyname,
                                          predicate_name=cls.classname,
                                          attribute="status",
                                          operator="IN",
                                          expression=",".join(map(str, states)))

        return rule

    def _create_term(self, name, fqpyname, predicate_name, attribute,
                     operator, expression):
        condition = ("name = '%s' and fqpyname = '%s' "
            "and predicate_name = '%s'" % (name, fqpyname, predicate_name))
        rs = sqlapi.RecordSet2(table="cdb_pyterm",
                               condition=condition,
                               columns=["max(id) as term_id"])
        if rs and rs[0].term_id:
            term_id = rs[0].term_id
        else:
            term_id = 0
        term_id += 1

        args = {"name": name,
                "fqpyname": fqpyname,
                "predicate_name": predicate_name,
                "attribute": attribute,
                "operator": operator,
                "expression": expression,
                "id": term_id}
        return objects.Term.Create(**args)

    def _create_task_group(self, process, mode, position, parent_id, status,
                           **args):
        if mode == "sequential":
            cls = taskgroups.SequentialTaskGroup
            title = "sequential taskgroup"
        else:
            cls = taskgroups.ParallelTaskGroup
            title = "parallel taskgroup"

        status_txt = cls.GetStateText(status, "de")

        d = {"cdb_process_id": process.cdb_process_id,
             "cdb_project_id": process.cdb_project_id,
             "task_id": taskgroups.TaskGroup.new_aggregate_number(),
             "position": position,
             "parent_id": parent_id,
             "title": title,
             "status": status.status,
             "cdb_status_txt": status_txt,
             "cdb_classname": cls.__classname__,
        }
        d.update(**args)
        taskgroup = cls.Create(**d)
        taskgroup.setObjectLifeCycle(None)

        return taskgroup

    def _create_task(self, process, mode, title, position, parent_id, status, **args):
        if mode == 'execution':
            cls = tasks.ExecutionTask
        elif mode == 'approval':
            cls = tasks.ApprovalTask
        elif mode == 'examination':
            cls = tasks.ExaminationTask
        else:
            cls = tasks.SystemTask

        status_txt = cls.GetStateText(status, "de")

        task = cls.Create(cdb_classname=cls.__classname__,
                          cdb_process_id=process.cdb_process_id,
                          cdb_project_id=process.cdb_project_id,
                          task_id=tasks.Task.new_task_id(),
                          title=title,
                          parent_id=parent_id,
                          position=position,
                          status=status.status,
                          cdb_status_txt=status_txt,
                          **args)
        task.subject_name = task.getSubjectName()
        task.setObjectLifeCycle(None)

        return task

    def _create_system_task(self, process, title, invert_constraint, status):
        tdfs = systemtasks.SystemTaskDefinition.KeywordQuery(name="Statuswechsel")
        if not tdfs:
            raise RuntimeError("System task definition not found")
        task_definition = tdfs[0]

        # Create system task

        # subject_id must be caddok, because the workflow service has not
        # been installed yet, therefore we can't use the method
        # SystemTask.set_service_user
        components = schemacomponents.SchemaComponent\
            .KeywordQuery(cdb_process_id=process.cdb_process_id,
                          parent_id=process.ProcessCompletion.task_id)

        position = max(components.position + [0]) + 10
        status_txt = tasks.Task.GetStateText(status)
        st = tasks.SystemTask.Create(cdb_process_id=process.cdb_process_id,
                                     task_id=tasks.Task.new_task_id(),
                                     parent_id=process.ProcessCompletion.task_id,
                                     cdb_project_id=getattr(process, "cdb_project_id", ""),
                                     position=position,
                                     finish_option=0,
                                     task_definition_id=task_definition.cdb_object_id,
                                     title=title,
                                     uses_global_maps=0,
                                     subject_id="caddok",
                                     subject_type="Person",
                                     status=status.status,
                                     cdb_status_txt=status_txt)

        # Create constraint
        constraints.Constraint.Create(cdb_process_id=process.cdb_process_id,
                                      rule_name="wf-designer: process completing successfully",
                                      task_id=st.task_id,
                                      invert_rule=invert_constraint)

        return st

    def _create_object_filter(self, process, task_id, filter_rule, target_state):
        if filter_rule:
            rule_name = filter_rule.name
        else:
            rule_name = ""

        # Create parameter
        tasks.FilterParameter.Create(cdb_process_id=process.cdb_process_id,
                                     task_id=task_id,
                                     name="target_state",
                                     rule_name=rule_name,
                                     value=target_state,)


pre = []
post = [InstallOptionalChanges, MigrateWorkflows]

if __name__ == "__main__":
    MigrateWorkflows().run()
