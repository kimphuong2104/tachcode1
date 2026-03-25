#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
# pylint: disable=W0212

import os
import io
import urllib
from cdb.platform.mom import entities
from cdb.platform.mom import relships
from cs.platform.web.rest import support
from cdb import misc
from cdb import sig
from cdb.objects import Object, Reference_N, Reference_1, Forward, State, Transition
from cdb import sqlapi, ue, util
from cdb import transactions
from cdb.objects.operations import operation, system_args
from cdb.platform import gui
from cdb.comparch import tools
from cdb.cad import isFalse

from cs.workplan.visualization import cswp_workplan_visualization
from cs.vp.items import Item
from cdb.objects.org import Organization
from cs.workplan.tasklists import TaskList
from cs.web.components.generic_ui.detail_view import DETAIL_VIEW_SETUP

fWorkplan = Forward(__name__ + ".Workplan")


@sig.connect(Item, "query_catalog", "pre")
def preset_empty_part_index_as_search_cond(cls, ctx):
    if ctx.catalog_name == "cswp_bom_item_structure_catalog":
        if ctx.catalog_invoking_dialog.joined_assembly_index == "":
            ctx.set("t_index", "=''")


def ensure_csp_header_set(request):
    try:
        from cs.threed.hoops.web.utils import add_csp_header
        request.after(add_csp_header)
    except ImportError:
        pass


class Workplan(Object):
    __classname__ = "cswp_workplan"
    __maps_to__ = "cswp_workplan"

    class DRAFT(State):
        status = 0

        def pre_mask(state, self, ctx):
            if not ctx.batch:
                ctx.excl_state(self.RELEASED.status)
            super(self.DRAFT, state).pre_mask(self, ctx)

    class REVIEW(State):
        status = 100

        def Constraints(state, self):
            return [
                (
                    "check_object_assigned",
                    [
                        self.is_template,
                        self.Assembly,
                        "cswp_state_change_no_assembly_set",
                    ],
                ),
                (
                    "check_state",
                    [
                        self.is_template,
                        self.Assembly,
                        [200],
                        "cswp_state_change_assembly_state",
                    ],
                ),
                (
                    "check_object_assigned",
                    [self.is_template, self.Plant, "cswp_state_change_no_plant_set"],
                ),
            ]

        def check_object_assigned(self, template, obj, err_msg):
            if not template and not obj:
                return gui.Message.GetMessage(err_msg)
            return None

        def check_state(self, template, obj, states, err_msg):
            if not template:
                if obj and obj.status not in states:
                    return gui.Message.GetMessage(err_msg)
            return None

    class BLOCKED(State):
        status = 170

    class OBSOLETE(State):
        status = 180

    class REVISION(State):
        status = 190

        def pre_mask(state, self, ctx):
            if not ctx.batch:
                ctx.excl_state(self.RELEASED.status)
                ctx.excl_state(self.OBSOLETE.status)
                ctx.excl_state(self.DRAFT.status)
            super(self.REVISION, state).pre_mask(self, ctx)

    class RELEASED(State):
        status = 200

        def pre_mask(state, self, ctx):
            if not ctx.batch:
                ctx.excl_state(self.REVISION.status)
            super(self.RELEASED, state).pre_mask(self, ctx)

    class TO_RELEASED(Transition):
        transition = ("*", 200)

        def post(transition, self, ctx):
            old_state = self.REVISION.status
            new_state = self.OBSOLETE.status
            revision_wps = Workplan.KeywordQuery(
                workplan_id=self.workplan_id, status=old_state
            )
            for revision_wp in revision_wps:
                try:
                    revision_wp.ChangeState(new_state)
                    revision_wp.cdb_obsolete = 1
                except RuntimeError as e:
                    raise ue.Exception(
                        "cswp_state_change_error", "%s" % old_state, "%s" % new_state, e
                    )

    WorkPlanTaskLists = Reference_N(
        TaskList,
        TaskList.workplan_id == fWorkplan.workplan_id,
        TaskList.workplan_index == fWorkplan.workplan_index,
    )

    RootTaskList = Reference_1(
        TaskList,
        TaskList.workplan_id == fWorkplan.workplan_id,
        TaskList.workplan_index == fWorkplan.workplan_index,
        TaskList.task_list_type == "standard",
    )

    Assembly = Reference_1(
        Item,
        Item.teilenummer == fWorkplan.assembly_id,
        Item.t_index == fWorkplan.assembly_index,
    )

    Plant = Reference_1(Organization, Organization.org_id == fWorkplan.plant_id)

    def set_workplan_id(self, ctx):
        if "new_index" not in ctx.sys_args.get_attribute_names():
            self.workplan_id = "WP%07d" % util.nextval(self.__classname__)

        else:
            ctx.skip_dialog()
        self.cdb_obsolete = 0

    def check_lot_size_range(self, ctx):
        if self.lot_size_from:
            if self.lot_size_from >= self.lot_size_to:
                raise ue.Exception("cswp_workplan_lot_size_range")

    def remove_index(self, ctx):
        if "new_index" not in ctx.sys_args.get_attribute_names():
            self.workplan_index = ""

    def create_standard_task_list(self, ctx):

        task_list_args = {
            "task_list_id": "SQ%04d" % 0,
            "workplan_id": self.workplan_id,
            "workplan_index": self.workplan_index,
            "task_list_type": "standard",
            "task_list_name_de": self.workplan_name_de,
            "task_list_name_en": self.workplan_name_en,
            "lot_size_from": self.lot_size_from,
            "lot_size_to": self.lot_size_to,
        }
        operation("CDB_Create", TaskList, **task_list_args)

    @classmethod
    def on_cswp_create_new_from_template_now(cls, ctx):

        if misc.CDBApplicationInfo().rootIsa(misc.kAppl_HTTPServer):
            url = "/cs-workplan-web-template_create_app"
            if ctx.relationship_name:
                # We have to provide information about the relationship and the
                # parent
                rs = relships.Relship.ByKeys(ctx.relationship_name)
                cdef = entities.CDBClassDef(rs.referer)
                o = support._RestKeyObj(cdef, ctx.parent)
                key = support.rest_key(o)
                url += "?classname=%s&rs_name=%s&keys=%s" % (
                    urllib.parse.quote(rs.referer),
                    urllib.parse.quote(rs.rolename),
                    urllib.parse.quote(key)
                )

            ctx.url(url)

        if not ctx.catalog_selection:
            kwargs = {}
            ctx.start_selection(catalog_name="cswp_workplan_template", **kwargs)
        else:
            workplan_id = ctx.catalog_selection[0]["workplan_id"]
            workplan_index = ctx.catalog_selection[0]["workplan_index"]
            template = cls.ByKeys(
                workplan_id=workplan_id, workplan_index=workplan_index
            )

            ctx.set_followUpOperation(
                "CDB_Copy", predefined=[("is_template", 0)], op_object=template
            )

    def on_cswp_workplan_visualization_now(self, ctx):
        """Shows a .svg file visualizing the work plan using graphviz-dotlib in seperate tab
        (inspired by method 'on_cdb_package_show_dependencies_now' in packages.py)
        """
        graph = cswp_workplan_visualization(self)
        svgfile = graph.render("svg", None)
        with io.open(svgfile, "r", encoding="utf-8") as resultfile:
            result = resultfile.read()
        os.unlink(svgfile)
        # drop XML header and return the actual SVG content
        result = result[result.index("<svg"):]
        ctx.file(tools.htmlfile(result, util.Labels()["cswp_workplan_visualization"]))

    def cswp_workplan_visualization_render(self, orientation="horizontal"):
        """Creates a .svg file visualizing the work plan using graphviz-dotlib
        (inspired by method 'on_cdb_package_show_dependencies_now' in packages.py)
        """
        graph = cswp_workplan_visualization(self, orientation)
        svgfile = graph.render("svg", None)
        with io.open(svgfile, "r", encoding="utf-8") as resultfile:
            result = resultfile.read()
        os.unlink(svgfile)
        # drop XML header and return the actual SVG content
        result = '<svg  id="workplan" width="100%" height="100%" ' + result[result.index("<svg") + 4:]
        return result

    def sorted_tasklists(self):
        """
        Returns the task lists in dependency order
        """
        result = []
        dep = {tl: tl.ReferenceTaskList for tl in self.WorkPlanTaskLists}

        while dep:
            candidates = [tl for tl, requires in dep.items() if not requires]
            for cand in candidates:
                result.append(cand)
                del dep[cand]
                for tl, requires in dep.items():
                    if requires == cand:
                        dep[tl] = None
        return result

    def cswp_import_workplan_pre_mask(self, ctx):
        if not self.CheckAccess("save"):
            raise ue.Exception("cswp_workplan_not_modifiable")

    def import_workplan(self, ctx):
        source_workplan = Workplan.ByKeys(workplan_id=ctx.dialog.source_workplan_id,
                                          workplan_index=ctx.dialog.source_workplan_index)
        target_standard_task_list = self.RootTaskList

        with transactions.Transaction():
            # append tasks of standard sequence
            task_id_map = target_standard_task_list.import_tasks(source_workplan.RootTaskList)

            # copy other sequences in dependency order
            # note that the first one is the root sequence, which is not copied.
            task_list_id_map = {}
            for source_task_list in source_workplan.sorted_tasklists()[1:]:
                args = {}
                args["workplan_id"] = self.workplan_id
                args["workplan_index"] = self.workplan_index
                if source_task_list.ReferenceTaskList == source_workplan.RootTaskList:
                    # get the new task ids for the start and return tasks
                    args["start_task"] = task_id_map.get(source_task_list.start_task)
                    args["return_task"] = task_id_map.get(source_task_list.return_task)
                else:
                    args["reference_task_list"] = task_list_id_map.get(source_task_list.reference_task_list)
                new_task_list = operation("CDB_Copy", source_task_list, **args)
                task_list_id_map[source_task_list.task_list_id] = new_task_list.task_list_id

    def change_state_from_revision_to_released(self, ctx):
        # change state of predecessor index from REVISION to RELEASED
        old_state = self.REVISION.status
        new_state = self.RELEASED.status
        workplans_in_revision = Workplan.KeywordQuery(
            workplan_id=self.workplan_id, status=old_state
        )
        for revision_wp in workplans_in_revision:
            # should only be one work plan
            try:
                revision_wp.ChangeState(new_state)
            except RuntimeError as e:
                raise ue.Exception(
                    "cswp_state_change_error", "%s" % old_state, "%s" % new_state, e
                )

    # helper function: generates char from given integer
    # if integer > 26 -> 'aa'
    def get_index_value(self, index):
        n = self.chr2num(index) + 1
        rst = ""
        while True:
            if n > 26:
                n, r = divmod(n - 1, 26)
                rst = chr(r + ord("a")) + rst
            else:
                return chr(n + ord("a") - 1) + rst

    # helper function: returns number of cha
    # a -> 1
    # z -> 26
    def chr2num(self, index):
        num = 0
        for c in index:
            if c.isalpha():
                num = num * 26 + (ord(c) - ord("a")) + 1
        return num

    def create_index(self, ctx):
        index_value = "a"
        if ctx.mode == "pre_mask":
            result = sqlapi.RecordSet2(
                sql="SELECT workplan_index "
                "FROM cswp_workplan "
                "WHERE workplan_id='%s' "
                "ORDER BY LENGTH(workplan_index)" % (self.workplan_id)
            )

            if result[-1].workplan_index:
                index_value = self.get_index_value(result[-1].workplan_index)

            ctx.set("cdb::argument.workplan_index", index_value)
            ctx.keep("new_index_value", index_value)

        if ctx.mode == "now":
            # create/copy new work plan object with new index and draft status
            index_value = getattr(ctx.ue_args, "new_index_value")
            user_input = {
                "workplan_id": self.workplan_id,
                "workplan_index": index_value,
                "status": 0,
            }

            operation("CDB_Copy", self, system_args(new_index=1), **user_input)

            # change status of predecessor index from RELEASED to REVISION
            if self.status == self.RELEASED.status:
                self.ChangeState(self.REVISION.status)

    def set_hash(self, ctx):
        self.workplan_id = "#"

    def disable_sap_tab(self, ctx):
        # hide sap specific dialog tab, if property wpsc is disabled (default)
        if isFalse(util.get_prop("wpsc")):
            ctx.disable_registers(["cswp_workplan_sap", "cswp_workplan_sap_search"])

    event_map = {
        ("create", "pre_mask"): "set_hash",
        (("create", "copy"), "pre"): ("set_workplan_id", "check_lot_size_range"),
        ("copy", "pre_mask"): "remove_index",
        ("cswp_create_index", ("pre_mask", "now")): "create_index",
        ("create", "post"): "create_standard_task_list",
        ("cswp_import_workplan", "now"): "import_workplan",
        ("cswp_import_workplan", "pre_mask"): "cswp_import_workplan_pre_mask",
        ("delete", "post"): "change_state_from_revision_to_released",
        (("create", "copy", "modify", "query", "requery", "info"), "pre_mask"): "disable_sap_tab"
    }


class Workplace(Object):
    __classname__ = "cswp_workplace"
    __maps_to__ = "cswp_workplace"


class WorkplaceType(Object):
    __classname__ = "cswp_workplace_type"
    __maps_to__ = "cswp_workplace_type"


@sig.connect(Workplan, DETAIL_VIEW_SETUP)
def _app_setup(obj, request, app_setup):
    ensure_csp_header_set(request)
