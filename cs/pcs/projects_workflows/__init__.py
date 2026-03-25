#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.classbody import classbody
from cdb.objects import Forward, Reference_N, ReferenceMethods_N

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task

fProcess = Forward("cs.workflow.processes.Process")


@classbody
class Project:

    Processes = Reference_N(fProcess, fProcess.cdb_project_id == Project.cdb_project_id)


@classbody
class Task:
    def _get_processes(self):
        from cs.workflow.briefcases import BriefcaseReference
        from cs.workflow.processes import Process

        refs = BriefcaseReference.KeywordQuery(cdb_content_id=self.cdb_object_id)
        in_clause = "','".join([ref.Process.cdb_process_id for ref in refs])
        return Process.Query(f"cdb_process_id IN ('{in_clause}')")

    Processes = ReferenceMethods_N(fProcess, _get_processes)
