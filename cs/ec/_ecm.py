#!/usr/bin/env python
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# CDB:Browse
#
# pylint: disable-msg=R0201,R0903,R0904,E0213,W0232,W0201,W0212,W0142

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from urllib.parse import quote

from cdb import misc
from cdb import ue
from cdb import util
from cdb import auth
from cdb import cmsg
from cdb import sig
from cdb.classbody import classbody
from cdb.rte import require_config

from cdb.objects import State
from cdb.objects import Transition
from cdb.objects import NULL

from cdb.platform import gui
from cdb.platform.mom import entities, relships
from cs.platform.web.rest import support

from cs.ec import EngineeringChange
from cs.workflow.processes import Process

# Sentinel: raise when "std-solution" is not set
require_config("std-solution")


@classbody
class EngineeringChange(object):

    ECStateToTypeMap = {0: "ECR",
                        30: "ECR",
                        60: "ECR",
                        40: "ECO",
                        50: "ECO",
                        100: "ECN",
                        200: "ECN"}

    class CREATED(State):
        status = 0

    class APPROVAL(State):
        status = 100

        def pre(state, self, ctx):  # @NoSelf
            # Statuswechsel zugeordneter Artikel und Dokumente nach 'in Prüfung'
            # Aktualisierung Trefferlisten erfolgt in on_wf_step_post(...), da hier nicht verfügbar.
            map(lambda i: i.ChangeState(100), [i for i in self.Items if i.status == 0])
            map(lambda d: d.ChangeState(100), [d for d in self.Documents if d.status == 0])

        def Constraints(state, self):  # @NoSelf
            return [("checkCDBLock", [self.Documents])]

    class REJECTED(State):
        status = 180

        def post(state, self, ctx):  # @NoSelf
            if ctx.error:
                return

            # Statuswechsel für zugehörige Prozesse auch nach verworfen.
            processes = set([briefcase.Process for briefcase in self.Briefcases])
            for process in processes:
                if process.status in [
                    Process.NEW.status,
                    EngineeringChange._get_ready_state(Process).status,
                    EngineeringChange._get_onhold_state(Process).status
                ]:
                    process.cancel_process()

    class ALL_WF_STEPS(Transition):
        transition = ('*', '*')

        def pre(transition, self, ctx):  # @NoSelf
            # Prüfung Rollensysteme der zu startenden Prozesse
            for templ_ref in self.ProcessTemplateReferencesByState[self.status]:
                if templ_ref.Process:
                    self._CheckRoles(templ_ref.Process)

        def post(transition, self, ctx):  # @NoSelf
            if ctx.error:
                return
            self.ec_state = self.ECStateToTypeMap.get(self.status, "")
            self._RunProcesses()

    class LEAVE_CREATED(Transition):
        transition = (0, '*')

        def pre(transition, self, ctx):  # @NoSelf
            if (self.Category.planned_changes_only and not self.PlannedChangesItemReferences
                    and not self.PlannedChangesDocumentReferences):
                # Die EC Kategorie verlangt die Zuordnung aller geplanten Änderungen im voraus.
                raise ue.Exception("cdbecm_err_assign5")

    def checkCDBLock(self, object_list):
        # Constraint checker for locked documents.
        msg = ""
        objects = [obj for obj in object_list if obj and (obj.cdb_lock) not in [NULL, "", auth.persno]]
        if objects:
            msg = "%s\n - " % (gui.Message.GetMessage("cdbecm_docs_locked"))
            msg += "\n - ".join([t.GetDescription() for t in objects])
        return msg

    @classmethod
    def MakeID(cls):
        return "EC%08d" % (util.nextval("cdbecm_ecid"))

    @sig.connect(EngineeringChange, 'create', 'pre')
    @sig.connect(EngineeringChange, 'copy', 'pre')
    def _setDefaults(self, ctx):
        self.setDefaults(ctx)

    def setDefaults(self, ctx):
        self.cdb_ec_id = self.MakeID()
        self.cdb_objektart = self.Category.workflow

    def on_state_change_pre_mask(self, ctx):
        self.Super(EngineeringChange).on_state_change_pre_mask(ctx)

        if not ctx.batch:
            # Disable state changes to be done by managed processes
            for s in ctx.statelist:
                if self._StateChangeByManagedProcess(s):
                    ctx.excl_state(s)

    def on_wf_step_post(self, ctx):  # FIXME: Braucht man das noch? Testen!
        # Beim Statuswechsel nach 'in Prüfung' werden die zugeordneten Dokumente und Artikel
        # auch in Prüfung genommen.
        if self.status == 100:
            ctx.refresh_tables(['zeichnung', 'teile_stamm'])

    def on_modify_pre_mask(self, ctx):
        ctx.set_readonly("template")

    def on_modify_pre(self, ctx):
        if self.template and self.category != ctx.object.category:
            self.cdb_objektart = self.Category.workflow

    def on_create_pre_mask(self, ctx):
        # Nur Vorlagen können direkt angelegt werden
        self.template = 1
        self.ec_state = "ECT"

    def on_copy_pre_mask(self, ctx):
        if ("operation_create_from_template" in ctx.sys_args.get_attribute_names() and
                ctx.sys_args.operation_create_from_template == "1"):
            self.ec_state = "ECR"
            if "tmpl_template_ec_id" in ctx.sys_args.get_attribute_names():
                self.template_ec_id = ctx.sys_args.tmpl_template_ec_id

    def createFollowUp(self, ctx):
        """
        Tells `ctx` to start the follow up operation
        ``cdbecm_ec``. The follow up is
        only created if there is no pending error. Because
        CDB/Win starts a follow up on its own when performing
        a copy on the toplevel structure node, this method
        skips the creation of an additional follow up in this case.
        """
        if ctx.error:
            return

        if ctx.action != "copy" or getattr(ctx.sys_args, "structurerootaction", "") != "1":
            if ctx.uses_webui:
                ctx.set_followUpOperation("CDB_ShowObject", 1)
            else:
                ctx.set_followUpOperation("cdbecm_ec", 1)

    @classmethod
    def on_cdbecm_create_ec_from_template_now(cls, ctx):
        def _uniquote(s):
            if isinstance(s, str):
                v = s.encode('utf-8')
            else:
                v = s
            return quote(v)

        if ctx.uses_webui:
            from cs.ec.web.template_create_app.main import TemplateCreateApp
            url = TemplateCreateApp.MOUNT_PATH + "/ec"
            if ctx.relationship_name:
                # We have to provide information about the relationship and the parent
                rs = relships.Relship.ByKeys(ctx.relationship_name)
                cdef = entities.CDBClassDef(rs.referer)
                o = support._RestKeyObj(cdef, ctx.parent)
                key = support.rest_key(o)
                url += "?classname=%s&rs_name=%s&keys=%s" % \
                       (_uniquote(rs.referer),
                        _uniquote(rs.rolename),
                        _uniquote(key))
            ctx.url(url)
            return

        if not ctx.catalog_selection:
            browser_attr = {}
            ctx.start_selection(catalog_name="cdbecm_ec_templates", **browser_attr)
        else:
            cdb_ec_id = ctx.catalog_selection[0]["cdb_ec_id"]
            template = cls.ByKeys(cdb_ec_id=cdb_ec_id)
            ctx.set_followUpOperation(
                "CDB_Copy",
                keep_rship_context=True,
                predefined=[
                    ("cdb::argument.operation_create_from_template", "1"),
                    ("cdb::argument.tmpl_template_ec_id", template.cdb_ec_id),
                    ("template", "0")  # must be set here. if changed in pre mask the mask will not appear
                ],
                op_object=template
            )

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    def on_copy_post(self, ctx):
        self.createFollowUp(ctx)
        self.copy_template_process_refs(ctx)
        self.create_reference_to_defect(ctx)
