#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Load and save data for flex generated gantt chart
"""

import traceback

# pylint: disable-msg=R0903
from io import StringIO


class WithProjectGanttHandler(object):
    def loadGanttData(self, req):
        try:
            req.write(
                '<project name="%s (%s)" id="%s" division="%s" category="%s"/>\n'
                % (
                    self.project_name,
                    self.cdb_project_id,
                    self.cdb_project_id,
                    self.division,
                    self.category,
                )
            )
            for role in self.Roles:
                req.write(
                    '<person id="%s" name="%s" subject_type="PCS Role"/>\n'
                    % (role.role_id, role.role_id)
                )
            for member in self.TeamMembersByPersno.values():
                req.write(
                    '<person id="%s" name="%s" subject_type="Person"/>\n'
                    % (member.mapped_cdb_person_id_name, member.cdb_person_id)
                )
            mylist = self.TasksByParentTask[""]
            for task in mylist:
                task.loadGanttData(req)
            for task in self.Tasks:
                task.loadGanttRelationData(req)
        except Exception as e:  # pylint: disable=W0703
            memfile = StringIO.StringIO()
            traceback.print_exc(file=memfile)
            print(memfile.getvalue())
            req.write(
                "<error>Fehler aufgetreten\n\n%s\n\n%s</error>"
                % (e, memfile.getvalue())
            )


class WithTaskGanttHandler(object):
    def loadGanttData(self, req):
        req.write("<task ")
        req.write('id="%s" ' % self.task_id)
        req.write('resourceId="%s" ' % self.task_id)
        req.write('type="plan" ')
        req.write('task_name="%s" ' % self.task_name)
        req.write('subject_id="%s" ' % self.subject_id)
        req.write('subject_type="%s" ' % self.subject_type)
        req.write('category="%s" ' % self.category)
        req.write('milestone="%s" ' % self.milestone)
        req.write('priority="%s" ' % self.priority)
        req.write('division="%s" ' % self.division)
        req.write('percent="%s" ' % self.percent_complet)
        req.write('position="%s" ' % self.position)
        if self.start_time_plan and not self.milestone:
            req.write('startTime="%s" ' % self.start_time_plan)
        if self.end_time_plan:
            if not self.milestone:
                req.write('endTime="%s" ' % self.end_time_plan)
            else:  # bei einem Meilenstein sind immer start- und endTime identisch
                req.write('startTime="%s" ' % self.end_time_plan)
                req.write('endTime="%s" ' % self.end_time_plan)
        req.write(">\n    ")
        for t in self.Subtasks:
            t.loadGanttData(req)
        req.write("</task>\n")
        self.writeActiveTask(req)

    def writeActiveTask(self, req):
        if self.start_time_act and self.end_time_act and not self.milestone:
            req.write("<task ")
            req.write('id="%s" ' % self.task_id)
            req.write('resourceId="%s" ' % self.task_id)
            req.write('type="act" ')
            req.write('startTime="%s" ' % self.start_time_act)
            req.write('endTime="%s" ' % self.end_time_act)
            req.write(">\n")
            req.write("</task>\n")

    def loadGanttRelationData(self, req):
        relations = self.PredecessorTaskRelationsByType["EA"]
        for rel in relations:
            req.write(
                '<task id="" task_id="%s" task_id2="%s" type="%s" resourceId="%s" startTime="" endTime="" />\n'
                % (rel.task_id, rel.task_id2, rel.rel_type, rel.task_id)
            )
        relations = self.SuccessorTaskRelationsByType["EA"]
        for rel in relations:
            req.write(
                '<task id="" task_id="%s" task_id2="%s" type="%s" resourceId="%s" startTime="" endTime="" />\n'
                % (rel.task_id, rel.task_id2, rel.rel_type, rel.task_id2)
            )
