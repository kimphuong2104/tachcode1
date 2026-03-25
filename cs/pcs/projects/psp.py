#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# CDB:Browse
# pylint: disable-msg=E0213,E1103,E0102,E0203,W0212,W0621,W0201

import logging
import sys
import traceback

from cdb import sig, ue
from cdb.classbody import classbody
from cdb.objects import ByID
from cdb.objects.org import WithSubject

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task

kpsp_id_min_length = 2


class WithPSP:
    def getProject(self):
        return Project.ByKeys(
            cdb_project_id=self.cdb_project_id, ce_baseline_id=self.ce_baseline_id
        )

    def getPSPParent(self):
        return ByID(self.parent_oid)

    def includeParentPSPCode(self):
        return True

    def getPSPSubElements(self):
        return []

    def getPSPID(self):
        return None

    def _calculateNextPSPID(self):
        parent = self.getPSPParent()
        if parent:
            psp_codes = [x.getPSPCode() for x in parent.getPSPSubElements()]
            psp_codes = [x for x in psp_codes if x]
            if psp_codes:
                max_code = max(psp_codes)
                if self.includeParentPSPCode():
                    max_code = max_code[len(parent.getPSPCode()) + 1 :]
                try:
                    return int(max_code) + 1
                except (ValueError, TypeError):
                    msg = "".join(traceback.format_exception(*sys.exc_info()))
                    msg = (
                        "Fallback on the number of tasks while "
                        f"the PSP code is being calculated.\n{msg}"
                    )
                    logging.warning(msg)
            return len(psp_codes) + 1
        return None

    def _fillPSPID(self, psp_id):
        return (f"{psp_id}").zfill(kpsp_id_min_length)

    def getPSPCode(self):
        return self.psp_code

    def getNextPSPID(self, psp_id=None):
        code = self.getPSPID()  # pylint: disable=assignment-from-none
        if not code and isinstance(psp_id, int):
            code = self._fillPSPID(psp_id)
        if not code:
            code = psp_id
        if not code:
            code = self._fillPSPID(self._calculateNextPSPID())
        return code

    def resetPSPCode(self):
        self.psp_code = ""
        for s in self.getPSPSubElements():
            s.resetPSPCode()

    def setPSPCode(self, psp_id=None, enforce=False):
        result = []
        code = self.getNextPSPID(psp_id)
        if code:
            if self.includeParentPSPCode():
                parent = self.getPSPParent()
                if parent:
                    code = f"{parent.getPSPCode()}.{code}"
            if enforce or not self.psp_code:
                self.psp_code = code
        else:
            self.psp_code = ""
            result.append(self.GetDescription())
        sub_elements = self.getPSPSubElements()
        for i, sub_element in enumerate(sub_elements):
            if enforce:
                result += sub_element.setPSPCode(psp_id=i + 1, enforce=enforce)
            else:
                result += sub_element.setPSPCode(enforce=enforce)
        return result


@classbody
class Project(WithPSP):
    def on_cdbpcs_create_psp_code_now(self, ctx):
        result = self.setPSPCode(enforce=self.status == 0)
        if result:
            output = "\n".join(result)
            raise ue.Exception("cdbpcs_psp_code_invalid", output)
        self.mark_as_changed()
        Task.mark_as_changed(cdb_project_id=self.cdb_project_id, ce_baseline_id="")

    def getPSPParent(self):
        return self.getParent()

    def includeParentPSPCode(self):
        return False

    def getPSPID(self):
        if self.psp_code:
            return self.psp_code
        return self.cdb_project_id

    def getPSPSubElements(self):
        subelements = self.TopTasks
        subprojects = self.OrderedSubProjects
        if subprojects:
            subelements += subprojects
        return subelements

    @sig.connect(Project, "modify", "pre_mask")
    def set_psp_code_read_only(self, ctx):
        """
        The WBS code can only be recalculated if the project prefix remains unchanged.
        If the project status is New, the code is completely recalculated,
        including the prefix from the project.
        """
        if (self.status or 0) > Project.NEW.status:
            ctx.set_fields_readonly(["psp_code"])


@classbody
class Task(WithPSP):
    def getPSPParent(self):
        return self.getParent()

    def getPSPSubElements(self):
        return self.OrderedSubTasks


class Phase(WithSubject, WithPSP):
    def getPSPID(self):
        return self.ID()

    def getPSPSubElements(self):
        return []


class WorkContingent(WithSubject, WithPSP):
    def getPSPID(self):
        return self.ID()

    def getPSPSubElements(self):
        return []
