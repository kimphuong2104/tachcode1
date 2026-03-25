# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import sig
from cdb import constants

from cdb.classbody import classbody
from cdb.objects import Forward, references
from cdb.objects.operations import operation

from cs.tools.semanticlinks import SemanticLink
from cs.requirements import fRQMSpecification, RQMSpecification
from cs.pcs.projects import Project


fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")


@classbody
class RQMSpecification(object):
    Project = references.Reference_1(fProject, fProject.cdb_project_id == fRQMSpecification.cdb_project_id)
    TopLevelProjectTasks = references.ReferenceMethods_N(fTask, lambda self: self._TopLevelProjectTasks())

    def _TopLevelProjectTasks(self):
        if self.Project:
            return self.Project.Tasks
        else:
            return []


@classbody
class Project(object):
    Specifications = references.Reference_N(fRQMSpecification, fRQMSpecification.cdb_project_id == fProject.cdb_project_id)

    @sig.connect(Project, "copy", "pre_mask")
    def checkSpecifications(self, ctx):
        if "create_project_from_template" in ctx.ue_args.get_attribute_names():
            if ctx.ue_args.create_project_from_template == "1":
                if "found_template_without_spec_template" not in ctx.dialog.get_attribute_names():
                    template = Project.ByKeys(ctx.cdbtemplate.cdb_project_id)
                    found_not_template = False
                    for spec in template.Specifications:
                        if not spec.is_template:
                            found_not_template = True
                            break
                    if found_not_template:
                        msgbox = ctx.MessageBox("cdbrqm_project_template_found", [], "found_template_without_spec_template",
                                                ctx.MessageBox.kMsgBoxIconInformation)
                        msgbox.addButton(ctx.MessageBoxButton("ok", 1))
                        msgbox.addCancelButton()
                        ctx.show_message(msgbox)

    @sig.connect(Project, "copy", "post")
    def copySpecifications(self, ctx):
        template = Project.ByKeys(ctx.cdbtemplate.cdb_project_id)
        for spec in template.Specifications:
            newspec = None
            if "create_project_from_template" in ctx.ue_args.get_attribute_names():
                if ctx.ue_args.create_project_from_template == "1" and spec.is_template == 1:
                    args = dict(is_template=0,
                                cdb_project_id=self.cdb_project_id)
                    newspec = operation(constants.kOperationCopy,  # @UndefinedVariable
                                        spec,
                                        **args)
            else:
                args = dict(cdb_project_id=self.cdb_project_id)
                newspec = operation(constants.kOperationCopy,  # @UndefinedVariable
                                    spec,
                                    **args)
            if newspec:
                from cs.pcs.projects.tasks import Task
                from cs.requirements import RQMSpecObject
                sl_subjs = SemanticLink.KeywordQuery(subject_object_id=newspec.Requirements.template_oid,
                                                     object_object_classname=Task.__classname__)
                for sl_subj in sl_subjs:
                    newTask = Task.KeywordQuery(template_oid=sl_subj.object_object_id,
                                                cdb_project_id=newspec.cdb_project_id)
                    newReq = RQMSpecObject.KeywordQuery(template_oid=sl_subj.subject_object_id)
                    if newTask and newReq:
                        newsl = sl_subj.Copy(subject_object_id=newReq[-1].cdb_object_id,
                                             object_object_id=newTask[-1].cdb_object_id)
                        newsl.generateMirrorLink()
