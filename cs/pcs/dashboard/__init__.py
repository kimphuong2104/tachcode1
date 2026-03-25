#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module cs.pcs.dashboard implements an eLink application to provide the user
overview over projects that he is working on or responsible to.
"""

import datetime
from math import ceil

from cdb import auth, elink, sig
from cdb.objects import Rule
from cdb.objects.org import Person
from cdb.typeconversion import to_legacy_date_format_auto
from cs.shared.elink_plugins.picture_uploader import PictureUploader

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task

PROJECT_RULE = "cdbpcs: Kosmodrom: My Objects"
FINALIZED_TASK_RULE = "cdbpcs: Finalized Task"
LOAD_OBJECT_STEP = 10


class WidgetBase:
    # which filters should be displayed
    __filters__ = []

    # CDB class for result objects
    __result_cls__ = None

    # HTML template for widget
    __widget__ = ""

    # Rule for active objects
    __active_rule__ = "cdbpcs: Kosmodrom: Active Objects"

    # Rule for my responsible objects
    __my_rule__ = "cdbpcs: Kosmodrom: My Objects"

    # Rule for overdue objects
    __overdue_rule__ = "cdbpcs: Kosmodrom: Overdue Objects"

    # Rule for searching objects by dates
    __date_rule__ = "cdbpcs: Kosmodrom: Objects By Date"

    # Rule for searching objects in period
    __period_rule__ = "cdbpcs: Kosmodrom: Objects In Period"
    # how many days from now on would be considered by "later" filter?
    # (however, today and tomorrow will be excluded by searching)
    __later_days__ = 7

    # Rule for searching objects, which are recently created
    __recent_rule__ = "cdbpcs: Kosmodrom: Objects Recently Created"
    # how many days from now on would be considered by "recently" filters?
    __recent_days__ = 7

    # an attribute besides cdb_project_id, to combine the sql
    # subqueries from Rule.stmt like <attr in (select attr from table)>
    __stmt_attr__ = ""

    # How many entries would be listed once
    __load_step__ = LOAD_OBJECT_STEP

    # order_by some attributes
    __order_by__ = None

    @staticmethod
    def rebuild_stmt_attribute(stmt, attr):
        new_stmt = stmt.replace(".*", f".{attr}", 1)
        return f"{attr} in ({new_stmt})"

    @staticmethod
    def get_rule_stmt(rule, cls, attr, *args, **varkw):
        return WidgetBase.rebuild_stmt_attribute(rule.stmt(cls, *args, **varkw), attr)

    @classmethod
    def get_rule_add_expr(cls, cdb_project_id):
        return f"cdb_project_id='{cdb_project_id}'"

    @classmethod
    def get_rule_add_expr_baseline(cls, add_expr):
        return add_expr + " AND ce_baseline_id=''"

    @classmethod
    def _get_filter_cond(cls, cdb_project_id, filters):
        add_expr = cls.get_rule_add_expr(cdb_project_id)
        if cls.__result_cls__ in (Task, Project):
            add_expr = cls.get_rule_add_expr_baseline(add_expr)
        ands = [add_expr]
        stmtattr = cls.__stmt_attr__

        if cls.__active_rule__:
            actrule = Rule.ByKeys(name=cls.__active_rule__)
            if actrule:
                ands.append(
                    cls.get_rule_stmt(
                        actrule, cls.__result_cls__, stmtattr, add_expr=add_expr
                    )
                )
        # mine
        if "filter_mine" in filters:
            myrule = Rule.ByKeys(name=cls.__my_rule__)
            if myrule:
                ands.append(
                    cls.get_rule_stmt(
                        myrule, cls.__result_cls__, stmtattr, add_expr=add_expr
                    )
                )

        # overdue
        overdues = []
        if "filter_overdue" in filters:
            odrule = Rule.ByKeys(name=cls.__overdue_rule__)
            if odrule:
                overdues.append(
                    cls.get_rule_stmt(
                        odrule, cls.__result_cls__, stmtattr, add_expr=add_expr
                    )
                )
        if "filter_today" in filters:
            odrule = Rule.ByKeys(name=cls.__date_rule__)
            if odrule:
                overdues.append(
                    cls.get_rule_stmt(
                        odrule,
                        cls.__result_cls__,
                        stmtattr,
                        add_expr=add_expr,
                        by_date=to_legacy_date_format_auto(datetime.datetime.now()),
                    )
                )
        if "filter_tomorrow" in filters:
            odrule = Rule.ByKeys(name=cls.__date_rule__)
            if odrule:
                by_date = to_legacy_date_format_auto(
                    datetime.date.today() + datetime.timedelta(days=1)
                )
                overdues.append(
                    cls.get_rule_stmt(
                        odrule,
                        cls.__result_cls__,
                        stmtattr,
                        add_expr=add_expr,
                        by_date=by_date,
                    )
                )
        if "filter_later" in filters:
            odrule = Rule.ByKeys(name=cls.__period_rule__)
            if odrule:
                start_date = to_legacy_date_format_auto(
                    datetime.date.today() + datetime.timedelta(days=2)
                )
                end_date = to_legacy_date_format_auto(
                    datetime.date.today() + datetime.timedelta(days=cls.__later_days__)
                )
                overdues.append(
                    cls.get_rule_stmt(
                        odrule,
                        cls.__result_cls__,
                        stmtattr,
                        add_expr=add_expr,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
        if overdues:
            ands.append(f'({" or ".join(overdues)})')

        # recently created
        if "filter_recently_created" in filters:
            rcrule = Rule.ByKeys(name=cls.__recent_rule__)
            if rcrule:
                start_date = to_legacy_date_format_auto(
                    datetime.date.today() - datetime.timedelta(days=cls.__later_days__)
                )
                ands.append(
                    cls.get_rule_stmt(
                        rcrule,
                        cls.__result_cls__,
                        stmtattr,
                        add_expr=add_expr,
                        start_date=start_date,
                    )
                )

        return ands

    @classmethod
    def get_filter_cond(cls, cdb_project_id, filters):
        ands = cls._get_filter_cond(cdb_project_id, filters)
        return " and ".join(ands)

    @classmethod
    def get_later_days(cls):
        return cls.__later_days__

    @classmethod
    def get_recent_days(cls):
        return cls.__recent_days__

    @classmethod
    def get_count(cls, cdb_project_id, filters):
        return len(
            cls.__result_cls__.Query(
                cls.get_filter_cond(cdb_project_id, filters), access="read"
            )
        )

    @classmethod
    def get_counts(cls, cdb_project_id):
        result = {}
        for flt in cls.__filters__:
            result[flt] = cls.get_count(cdb_project_id, [flt])
        return result

    @classmethod
    def get_objects(cls, cdb_project_id, filters, pageno, step=None):
        if step is None:
            step = cls.__load_step__
        results = cls.__result_cls__.Query(
            cls.get_filter_cond(cdb_project_id, filters),
            order_by=cls.__order_by__,
            access="read",
        )
        return KosmodromTools.make_page(results, pageno, step)

    @classmethod
    def get_icon(cls, cdb_project_id=""):
        icon = ""
        if cls.__result_cls__:
            icon = cls.__result_cls__.GetClassIcon()
        return icon

    @classmethod
    def get_object_class(cls):
        return cls.__result_cls__

    @classmethod
    def get_data(cls, cdb_project_id, **varkw):
        result = {
            "filtered_counter": {"all": 0, "filtered": 0},
            "all_counters": {},
            "objects": [],
        }
        step = varkw.get("load_step", None)
        pageno = varkw.get("load_page_no", 1)
        result["filters"] = [kn for kn in varkw if kn.startswith("filter_")]
        result["filtered_counter"]["all"] = cls.get_count(cdb_project_id, [])
        result["filtered_counter"]["filtered"] = cls.get_count(
            cdb_project_id, result["filters"]
        )
        result["all_counters"] = cls.get_counts(cdb_project_id)
        result["objects"], result["paginator"] = cls.get_objects(
            cdb_project_id, result["filters"], pageno, step
        )
        result["widget_icon"] = cls.get_icon(cdb_project_id)
        return {"kosmodromtools": KosmodromTools, "widget_data": result}


class KosmodromTools:
    @staticmethod
    def templates():
        return _getapp().getTemplates()

    @staticmethod
    def get_overview_url():
        return ProjectOverviewApp.getModuleURL()

    @staticmethod
    def get_detail_url(project):
        if not project:
            return "#"
        return f"/powerscript/cs.pcs.dashboard/detail?cdb_project_id={project.cdb_project_id}"

    @staticmethod
    def get_preview_img(project):
        return PictureUploader.get_preview_img(project)

    @staticmethod
    def get_image_access(project):
        """Checks whether the current user can modify the project picture."""
        if project.CheckAccess("save", auth.persno):
            return ""
        else:
            return "disabled"

    @staticmethod
    def get_timeline_positions(sd, ed, currdate):
        """Get position on a time line for a given date.
        @param sd: start date of the time line
        @param ed: end date of the time line
        @param currdate: datetime to be checked
        """
        if not ed or not sd:
            return 0
        duration = (ed - sd).days
        result = 100
        if not currdate:
            currdate = datetime.date.today()
        if duration > 0:
            result = (currdate - sd).days * 100 / duration
            result = min(100, result)
            result = max(0, result)
        return result

    @staticmethod
    def get_today_position(sd, ed):
        today = datetime.date.today()
        return KosmodromTools.get_timeline_positions(sd, ed, today)

    @staticmethod
    def get_milestones(proj, sd, ed):
        mstones = proj.Tasks.Query("milestone=1", access="read")
        crule = Rule.ByKeys(name=FINALIZED_TASK_RULE)
        result = []
        today = datetime.date.today()
        for mstone in mstones:
            ms_color = 3  # Light Gray
            msend = mstone.end_time_fcast
            ms_pos = 0
            ms_tooltip = 0
            if msend:
                if msend <= today:
                    if crule.match(mstone):
                        ms_color = 0  # Green
                    else:
                        ms_color = 1  # Red
                ms_pos = KosmodromTools.get_timeline_positions(sd, ed, msend)
            result.append((mstone, ms_pos, ms_color, ms_tooltip))
        if result:
            result = sorted(result, key=lambda x: x[1])
            try:
                first_gray_ms = next(x for x in result if x[2] == 3)
                gray_ind = result.index(first_gray_ms)
                if gray_ind != 0:
                    ms_tooltip += 1
                    first_with_tooltip = result[gray_ind - 1]
                    result[gray_ind - 1] = (
                        first_with_tooltip[0],
                        first_with_tooltip[1],
                        first_with_tooltip[2],
                        ms_tooltip,
                    )  # tooltip
                # Dark Gray & tooltip
                result[gray_ind] = (
                    first_gray_ms[0],
                    first_gray_ms[1],
                    2,
                    ms_tooltip + 1,
                )
            except Exception:
                first_with_tooltip = result[-1]
                result[-1] = (
                    first_with_tooltip[0],
                    first_with_tooltip[1],
                    first_with_tooltip[2],
                    1,
                )  # tooltip
        return result

    @staticmethod
    def date_to_str(date, evaltime=False):
        from cdb.typeconversion import to_legacy_date_format

        # heg: todo
        return to_legacy_date_format(date, evaltime) if date else str("")

    @staticmethod
    def get_roles_of_project(project):
        roles = {}
        for person in [teamMember.Person for teamMember in project.TeamMembers]:
            roles[f"{person.personalnummer}"] = [
                str(role.mapped_name)
                for role in [role for role in project.Roles if person in role.Persons]
            ]
        return roles

    @staticmethod
    def format_date(date):
        if date is None:
            return ""
        # TODO: localize the date?
        return to_legacy_date_format_auto(date)

    @staticmethod
    def make_page(objlist, pageno, step=None):
        try:
            step = int(step)
        except ValueError:
            step = LOAD_OBJECT_STEP

        # Only use paging if step > 0, otherwise return all results.
        if step > 0:
            try:
                pageno = int(pageno)
            except ValueError:
                pageno = 1
            start = (pageno - 1) * step
            end = pageno * step
            # Paginator: (current page No., total pages)
            paginator = (pageno, int(ceil(len(objlist) * 1.0 / step)))
            return objlist[start:end], paginator
        else:
            return objlist, (1, 1)


@elink.using_template_engine("chameleon")
class ProjectOverviewApp(elink.Application):
    def setup(self):
        self.__init_msgs__ = []
        self.add("", ProjectOverviewPage())
        self.add("detail", ProjectDetailPage())
        self.add("list", Objectlist())
        self.add("upload", _ProjectImage())

    @classmethod
    def on_CDB_eLink_kosmodrom_now(cls, ctx):
        return cls.OpenModule()

    def add_init_msg(self, msg):
        """Adds messages that should be displayed when page opened."""
        if msg:
            if isinstance(msg, list):
                self.__init_msgs__ += msg
            else:
                self.__init_msgs__ += [msg]

    def get_init_msg(self):
        """Gets messages that should be displayed when page opened.
        They should be removed after showed once.
        """
        result = self.__init_msgs__
        if self.__init_msgs__:
            self.__init_msgs__ = []
        return result


class ProjectOverviewPage(elink.Template):
    __template__ = "projectoverview.html"
    __cdbhelpid__ = "cdbwinusrman-pcs-projects-overview"
    __project_per_page__ = LOAD_OBJECT_STEP

    def render(self, context, **varkw):
        init_msg = self.application.get_init_msg()
        projects = []
        project_ids = varkw.get("project", [])

        if len(project_ids) == 0:
            rule = Rule.ByKeys(name=PROJECT_RULE)
            if rule:
                projects = [
                    proj
                    for proj in rule.getObjects(Project, order_by="project_name")
                    if proj.CheckAccess("read")
                ]
        else:
            url_projects = Project.KeywordQuery(
                cdb_project_id=project_ids, ce_baseline_id=""
            )
            projects.extend(
                [project for project in url_projects if project.CheckAccess("read")]
            )

        plugins = sig.emit("cs.pcs.dashboard.widget", "projectoverview")()
        plugin = None
        if plugins:
            plugin = plugins[0][1]
            if not hasattr(plugin, "kosmodromtools"):
                plugin.kosmodromtools = KosmodromTools

        pageno = varkw.get("page_no", 1)
        try:
            pageno = int(pageno)
        except ValueError:
            pageno = 1

        if (
            len(projects) > 0
            and not len(projects) > (pageno - 1) * self.__project_per_page__
        ):
            while not len(projects) > (pageno - 1) * self.__project_per_page__:
                pageno -= 1
            self.redirect(self.make_page_url(pageno, projects))
        projs, paginator = KosmodromTools.make_page(
            projects, pageno, self.__project_per_page__
        )
        result = {
            "projects": projs,
            "projects_paginator": paginator,
            "project": None,
            "kosmodromtools": KosmodromTools,
            "plugin": plugin,
            "elink_startup_cdb_messages": init_msg,
            "upload_action_url": f'{self.application.getURLPaths()["approot"]}upload',
        }
        return result

    def make_page_url(self, page, projects):
        url_projects = ""
        if len(projects):
            url_projects = (
                "&".join([f"project={project.cdb_project_id}" for project in projects])
                + "&"
            )
        return f"./?{url_projects}page_no={page:d}"


class ProjectDetailPage(elink.Template):
    __template__ = "projectdetail.html"
    __cdbhelpid__ = "cdbwinusrman-pcs-projects-details"

    #    __detail_widgets__ = {
    #                    1: "widget_projectoverview.html",
    #                    3: "widget_tasks.html",
    #                    4: "widget_issues.html",
    #                    5: "widget_documents.html",
    #                    6: "widget_items.html",
    #                    7: "widget_projectteam.html",
    #                    8: "widget_projecttimeschedule.html",
    #                    }

    __detail_widgets__ = None

    def get_detail_widgets(self):
        if self.__detail_widgets__ is None:
            self.__detail_widgets__ = {}
            for wdg in sig.emit("cs.pcs.dashboard.getplugins")():
                self.__detail_widgets__[wdg[0]] = wdg[1]
        app_id = "cdb.elink.kosmodrom"
        from cs.shared.elink_plugins.collapsible_blocks import get_blocks_order

        _order = [int(i) for i in get_blocks_order(app_id)]
        if not _order:
            _order = sorted(self.__detail_widgets__.keys())
        # _expanded not defined: expand the first widget
        from cs.shared.elink_plugins.collapsible_blocks import get_blocks_expand

        _expanded = [int(i) for i in get_blocks_expand(app_id, f"{_order[0]}")]
        result = []
        for i in _order:
            if i in self.__detail_widgets__:
                result.append((i, self.__detail_widgets__[i], i in _expanded))
        # unsorted widgets at end
        for i in list(self.__detail_widgets__):
            if i not in _order:
                result.append((i, self.__detail_widgets__[i], i in _expanded))
        return result

    def render(self, context, **varkw):
        init_msg = self.application.get_init_msg()
        proj = Project.ByKeys(cdb_project_id=varkw.get("cdb_project_id", ""))
        if proj and not proj.CheckAccess("read"):
            proj = None

        result = {
            "project": proj,
            "widgets": self.get_detail_widgets(),
            "kosmodromtools": KosmodromTools,
            "elink_startup_cdb_messages": init_msg,
            "upload_action_url": f'{self.application.getURLPaths()["approot"]}upload',
        }
        return result


class _ProjectImage(elink.Template):
    """Widget class to attach preview picture to project or person."""

    MAX_IMG_SIZE = 220
    __html__ = "<html></html>"

    @staticmethod
    def set_project_image(request):
        project_obj = Project.ByKeys(cdb_project_id=request.form_data["cdb_project_id"])
        return PictureUploader.set_image(
            request, project_obj, _ProjectImage.MAX_IMG_SIZE
        )

    @staticmethod
    def set_proj_team_image(request):
        person_obj = Person.ByKeys(personalnummer=request.form_data["person_id"])
        return PictureUploader.set_image(
            request, person_obj, _ProjectImage.MAX_IMG_SIZE
        )

    def render(self, context, **varkw):
        if self.request.upstreams:
            if (
                "person_id" in self.request.form_data
                and self.request.form_data["person_id"] != ""
            ):
                self.application.add_init_msg(
                    _ProjectImage.set_proj_team_image(self.request)
                )
            else:
                self.application.add_init_msg(
                    _ProjectImage.set_project_image(self.request)
                )
            return self.redirect()
        return {}


class Objectlist(elink.Template):
    __template__ = "list.html"

    def render(self, context, cdb_project_id, **varkw):
        result = {"plugin": None}
        widget = varkw.get("widget", None)
        if widget:
            widgets = sig.emit("cs.pcs.dashboard.widget", widget)()
            if widgets:
                widget = widgets[0][1]
                result["plugin"] = widget
                result["widget_data"] = []
                if hasattr(widget, "dashboard_widget"):
                    result.update(
                        widget.dashboard_widget.get_data(cdb_project_id, **varkw)
                    )
        return result


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)


# lazy instantiation
_APP = None


def _getapp():
    global _APP  # pylint: disable=global-statement
    if _APP is None:
        _APP = ProjectOverviewApp("Kosmodrom")
    return _APP
