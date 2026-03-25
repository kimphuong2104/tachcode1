#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module workflows

Handling of project roles for workflows
"""

from cs.workflow import misc

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

if misc.is_installed("cs.pcs.projects"):
    from cs.workflow.processes import Process  # @UnusedImport
    from cs.pcs import projects
    from cdb.objects import Reference_1
    from cdb import classbody
    from cdb import ue

    @classbody.classbody
    class Process(object):
        Project = Reference_1(projects.Project, Process.cdb_project_id)

        def _check_project_roles(self):
            """ Called before starting a workflow.
                If some workflow task has a project role as responsible, check
                if the workflow has been assigned to a project. If yes, check
                if the role has been assigned in the project.
            """
            tasks = self.AllTasks.KeywordQuery(subject_type="PCS Role")
            if (tasks):
                if not self.Project:
                    raise ue.Exception("cdbwf_no_project_assigned")

                errors = []
                for task in tasks:
                    role = self.Project.RolesByID[task.subject_id]
                    if not role or not role.Owners:
                        errors.append(task.title)

                if errors:
                    raise ue.Exception("cdbwf_project_roles_undefined",
                                       "\n".join(errors))
