#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
from collections import OrderedDict

from cdb import cdbuuid, sqlapi, typeconversion, util
from cdb.objects import org
from cdb.objects.operations import operation
from cs.calendar import CalendarProfile, workday

from cs.pcs import projects, timeschedule
from cs.pcs.projects import calendar, tasks
from cs.pcs.projects.common import partition
from cs.pcs.projects.tests.common import generate_baseline_of_project
from cs.pcs.helpers import get_dbms_split_count

PERSON = "caddok"
NOW_DATE = datetime.date(2010, 1, 1)
NOW_DATE_TIME = datetime.datetime(2010, 1, 1, 10, 11, 12)
CAL = {}


class TestCalendar:

    days = {}
    start_date_idx = 0

    def __init__(self, cdb_project_id, start_date=NOW_DATE):
        self.days = calendar.project_workdays(cdb_project_id)
        self.start_date_idx = workday.get_index_of_day(start_date, self.days, next=-1)

    def get_date_values(self, no, workdays):
        sd_idx = self.start_date_idx + workdays * no
        ed_idx = self.start_date_idx + workdays * no + workdays - 1
        sd = typeconversion.to_legacy_date_format(self.days[sd_idx])
        ed = typeconversion.to_legacy_date_format(self.days[ed_idx])
        return {
            "end_time_fcast": ed,
            "end_time_plan": ed,
            "start_time_fcast": sd,
            "start_time_plan": sd,
        }


DEFAULT_PROJECT = {
    "auto_update_effort": 1,
    "auto_update_time": 1,
    "calendar_profile_id": "1cb4cf41-0f40-11df-a6f9-9435b380e702",
    "category": "Entwicklung",
    "cdb_aacl_entry": None,
    "cdb_adate": NOW_DATE_TIME,
    "cdb_apersno": PERSON,
    "cdb_cdate": NOW_DATE_TIME,
    "cdb_cpersno": PERSON,
    "cdb_mdate": NOW_DATE_TIME,
    "cdb_mpersno": PERSON,
    "cdb_objektart": "cdbpcs_project",
    "cdb_project_id": "default_id",
    "cdb_status_txt": "New",
    "currency_object_id": "",
    "customer": "",
    "days": 1,
    "days_fcast": 1,
    "description": "",
    "division": "IT",
    "effort_act": 0.0,
    "effort_fcast": 10.0,
    "effort_fcast_a": 0.0,
    "effort_fcast_d": 0.0,
    "effort_plan": 0.0,
    "end_time_act": None,
    "end_time_fcast": "",
    "end_time_plan": "",
    "image_object_id": "",
    "is_group": 1,
    "locked_by": "",
    "material_cost": None,
    "msp_active": 0,
    "msp_z_nummer": "",
    "parent_project": "",
    "percent_complet": 0,
    "position": None,
    "project_manager": PERSON,
    "project_name": "project",
    "psp_code": "",
    "rating": "",
    "rating_descr": "",
    "risk_id": None,
    "start_time_act": None,
    "start_time_fcast": "",
    "start_time_plan": "",
    "status": 0,
    "status_effort_fcast": 1,
    "status_resource_total": None,
    "status_time_fcast": 1,
    "taskboard_oid": "",
    "template": 0,
    "template_oid": "",
}


DEFAULT_TASK = {
    "auto_update_effort": 1,
    "auto_update_time": 1,
    "automatic": 1,
    "category": "",
    "cdb_cdate": NOW_DATE_TIME,
    "cdb_cpersno": PERSON,
    "cdb_mdate": NOW_DATE_TIME,
    "cdb_mpersno": PERSON,
    "cdb_object_id": "",
    "cdb_objektart": "cdbpcs_task",
    "cdb_status_txt": "in Planung",
    "constraint_type": "0",
    "days": 1,
    "days_fcast": 1,
    "description": "",
    "division": "IT",
    "effort_fcast": 10.0,
    "effort_fcast_a": 0.0,
    "effort_fcast_d": 0.0,
    "effort_plan": 10.0,
    "end_time_act": "",
    "end_time_fcast": "",
    "end_time_plan": "",
    "is_group": 0,
    "milestone": 0,
    "parent_task": "",
    "percent_complet": 0,
    "position": 0,
    "psp_code": "",
    "rating": "",
    "rating_descr": "",
    "start_time_act": "",
    "start_time_fcast": "",
    "start_time_plan": "",
    "status": 0,
    "status_effort_fcast": 1,
    "status_time_fcast": 1,
    "subject_id": PERSON,
    "subject_type": "Person",
    "task_id": "default_id",
    "work_uncovered": 0,
}


DEFAULT_TASK_REL = {
    "cross_project": 0,
    "minimal_gap": 0,
    "rel_type": "EA",
    "violation": 0,
}


DEFAULT_TIME_SCHEDULE = {
    "cdb_cdate": NOW_DATE_TIME,
    "cdb_cpersno": PERSON,
    "cdb_mdate": NOW_DATE_TIME,
    "cdb_mpersno": PERSON,
    "cdb_objektart": "cdbpcs_time_schedule",
    "cdb_project_id": "default_id",
    "cdb_status_txt": "New",
    "name": "schedule name",
    "status": 0,
    "subject_id": PERSON,
    "subject_type": "Person",
}


def get_id(project, no=0):
    new_id = f"{project.cdb_project_id}_{str(no).zfill(5)}"
    return new_id


def delete_content(content):
    if content:
        content.Delete()


def delete_project(cdb_project_id, ce_baseline_id=None):
    """
    Delete complete project with all Tasks, TaskRelations,
    TeamMembers, ProjectRoles and Time Schedule with content.
    Also delete content of given baseline.
    """
    p = projects.Project.ByKeys(cdb_project_id=cdb_project_id)
    if not p:
        return
    # delete connections between project and time schedules
    connections = timeschedule.Project2TimeSchedule.KeywordQuery(
        cdb_project_id=p.cdb_project_id
    )
    delete_content(connections)

    # delete time schedules and content
    for schedule in p.PrimaryTimeSchedule:
        delete_content(schedule.TimeScheduleContents)
    delete_content(p.PrimaryTimeSchedule)

    # delete generated baseline content if any
    if ce_baseline_id:
        p.remove_all_baseline_elements(ce_baseline_id, True)

    # delete project and content
    delete_content(p.TaskRelations)
    delete_content(p.Tasks)
    delete_content(p.TeamMembers)
    delete_content(p.Roles)
    operation("CDB_Delete", p)


def create_complete_project(
    name, start_date=NOW_DATE, workdays_for_tasks=1, number_of_tasks=100, cluster_size=0
):
    """
    Construct complete project with Tasks, TaskRelations,
    default ProjectRoles and one Time Schedule with created
    project as content.

    :param name: name and id of project (max. 14 characters long,
        because tasks are created with a postfix of six characters)
    :type name: string

    :param start_date: start date of project
    :type start_date: datetime

    :param workdays_for_tasks: duration of the tasks
    :type workdays_for_tasks: integer

    :param number_of_tasks: number of tasks to be created
    :type number_of_tasks: integer

    :param cluster_size: number of connected tasks
    :type cluster_size: integer

    :returns: new project and baseline id of created baseline
    :rtype: tuple of object of type cs.pcs.projects.Project and string

    Example:
    import datetime
    from cs.pcs.projects.tests import common_data
    project, bid = common_data.create_complete_project(
        "my_project"
        start_date=datetime.date(2000, 1, 1),
        workdays_for_tasks=1,
        number_of_tasks=100,
        cluster_size=0
    )

    # if you want to ensure, that the project tasks
    # are positioned correctly, additionally use...
    project.recalculate()
    """
    assert len(name) <= 14, "project name may not exceed 14 characters"  # nosec
    project, bid = create_project(name, start_date)
    tasks = create_tasks(project, workdays_for_tasks, number_of_tasks)
    create_task_relations(project, tasks, cluster_size)
    create_time_schedule(project)
    days = 1
    if cluster_size:
        days = workdays_for_tasks * cluster_size
    c = CAL.get(project.cdb_project_id, None)
    project.Update(**c.get_date_values(0, days))
    project.Reload()
    return project, bid


def create_structured_project(
    name,
    start_date=NOW_DATE,
    days=1,
    tasks_per_level=3,
    depth=2,
    with_dates=False,
    cluster_size=0,
):
    project, bid = create_project(name, start_date)
    create_new_task_structure(
        project,
        None,
        no=0,
        days=days,
        tasks_per_level=tasks_per_level,
        depth=depth,
        with_dates=with_dates,
    )
    create_task_rel_structure(project, project.TopTasks, cluster_size)
    create_time_schedule(project)
    days = 1
    c = CAL.get(project.cdb_project_id, None)
    project.Update(**c.get_date_values(0, days))
    project.Reload()
    return project, bid


def create_new_task_structure(
    project, parent=None, no=0, days=1, tasks_per_level=3, depth=2, with_dates=False
):
    parent_id = ""
    c = CAL.get(project.cdb_project_id, None)
    if parent:
        parent_id = parent.task_id
    for _ in range(tasks_per_level):
        kwargs = c.get_date_values(no, days) if with_dates else {}
        parent = create_task(
            project,
            no,
            days=days,
            parent_task=parent_id,
            is_group=int(depth > 0),
            **kwargs,
        )
        no += 1
        if depth:
            no = create_new_task_structure(
                project,
                parent,
                no,
                days=days,
                tasks_per_level=tasks_per_level,
                depth=depth - 1,
                with_dates=with_dates,
            )
    return no


def create_project(
    name="project", start_date=NOW_DATE, calendar_profile_id=None, user_id=None
):
    if projects.Project.ByKeys(cdb_project_id=name):
        delete_project(name)
    if not calendar_profile_id:
        profile = CalendarProfile.KeywordQuery(name="Standard")[0]
        calendar_profile_id = profile.cdb_object_id
    kwargs = DEFAULT_PROJECT.copy()
    kwargs.update(
        calendar_profile_id=calendar_profile_id,
        cdb_object_id=cdbuuid.create_uuid(),
        cdb_project_id=name,
        project_name=name,
        ce_baseline_id="",
    )
    project = projects.Project.Create(**kwargs)
    create_roles(project, user_id)
    c = CAL.get(project.cdb_project_id, None)
    if not c:
        c = TestCalendar(project.cdb_project_id, start_date)
        CAL[project.cdb_project_id] = c
    project.Update(**c.get_date_values(0, 1))
    project.Reload()
    baseline = generate_baseline_of_project(project)
    return project, baseline.ce_baseline_id


def create_roles(project, user_id=None):
    pm = org.Person.ByKeys(personalnummer=user_id or PERSON)
    project.createBasicRoles(None)
    project.assignTeamMember(pm)
    project.assignDefaultRoles(pm)
    role = project.createRole("Projektleiter")
    role.assignSubject(pm)


def create_tasks(project, workdays=1, number_of_tasks=100):
    tasks = []
    c = CAL.get(project.cdb_project_id, None)
    for no in range(number_of_tasks):
        kwargs = c.get_date_values(no, workdays)
        tasks.append(_create_task_data(project, no, workdays, **kwargs))
    insert_new_tasks(tasks)
    project.Reload()
    return project.Tasks


def create_task(project, no, days=1, name=None, **kwargs):
    t = _create_task_data(project, no, days=days, task_name=name, **kwargs)
    return tasks.Task.Create(**t)


def _create_task_data(project, no, days=1, **kwargs):
    t = DEFAULT_TASK.copy()
    new_id = get_id(project, no)
    t.update(
        cdb_object_id=new_id,
        cdb_project_id=project.cdb_project_id,
        ce_baseline_id="",
        days=days * 1,
        days_fcast=days * 1,
        position=no * 10 + 10,
        task_id=new_id,
        task_name=new_id,
    )
    if "task_name" in kwargs and not kwargs["task_name"]:
        kwargs.pop("task_name")
    t.update(**kwargs)
    return t


def create_task_relations(project, tasks, cluster_size=None):
    if len(tasks) > 1:
        for d in range(len(tasks) - 1):
            if cluster_size and (d + 1) % cluster_size:
                create_task_relation(project, tasks[d], tasks[d + 1])


def create_task_rel_structure(project, tasks, cluster_size=None):
    if not cluster_size or cluster_size < 0:
        return
    generated_relships = len(tasks) - 1
    create_task_relations(project, tasks, cluster_size)
    for task in tasks:
        create_task_rel_structure(
            project, task.OrderedSubTasks, cluster_size - generated_relships
        )


def create_task_relation(project, predecessor, successor, **kwargs):
    rel = DEFAULT_TASK_REL.copy()
    rel.update(
        cdb_project_id=project.cdb_project_id,
        cdb_project_id2=project.cdb_project_id,
        pred_project_oid=project.cdb_object_id,
        pred_task_oid=predecessor.cdb_object_id,
        succ_project_oid=project.cdb_object_id,
        succ_task_oid=successor.cdb_object_id,
        task_id=successor.task_id,
        task_id2=predecessor.task_id,
    )
    rel.update(**kwargs)
    tasks.TaskRelation.Create(**rel)


def create_time_schedule(project, subject_id=None):
    kwargs = DEFAULT_TIME_SCHEDULE.copy()

    if subject_id:
        kwargs["subject_id"] = subject_id

    if not project:
        return timeschedule.TimeSchedule.Create(**kwargs)

    schedule = project.getPrimaryTimeSchedule()
    if schedule:
        return schedule

    kwargs.update(
        cdb_project_id=project.cdb_project_id,
        name=project.project_name,
    )
    schedule = timeschedule.TimeSchedule.Create(**kwargs)
    connect_time_schedule_to_project(schedule, project)
    return schedule


def connect_time_schedule_to_project(schedule, project):
    timeschedule.TimeScheduleObject.Create(
        cdb_content_classname="cdbpcs_project",
        cdb_project_id=project.cdb_project_id,
        content_oid=project.cdb_object_id,
        position=0,
        unremovable=0,
        view_oid=schedule.cdb_object_id,
    )
    timeschedule.Project2TimeSchedule.Create(
        cdb_project_id=schedule.cdb_project_id,
        time_schedule_oid=schedule.cdb_object_id,
    )


def insert_new_tasks(tasks_to_insert):
    # do not process empty list
    if not tasks_to_insert:
        return

    # create list of keys
    keys_to_sql = []
    for k, _ in iter(tasks_to_insert[0].items()):
        keys_to_sql.append(k)
        keys_to_sql.sort()
    keys_to_insert = ", ".join(keys_to_sql)

    # create list of value tuples
    cca = tasks.Task.MakeChangeControlAttributes()
    oids_to_remove = []
    values_to_insert = []
    table_info = util.tables["cdbpcs_task"]
    for task_to_create in tasks_to_insert:
        values_to_sql = []
        task_to_create = OrderedDict(**task_to_create)
        task_to_create.update(**cca)
        for k in keys_to_sql:
            v = sqlapi.make_literal(table_info, k, task_to_create[k])
            values_to_sql.append(v)
            if k == "cdb_object_id":
                oids_to_remove.append(v)
        values_to_insert.append(", ".join(values_to_sql))

    # insert values
    split_count = get_dbms_split_count()
    for oids in partition(oids_to_remove, split_count):
        sqlapi.SQLdelete(f"FROM cdbpcs_task WHERE cdb_object_id IN ({', '.join(oids)})")
    for values in partition(values_to_insert, split_count):
        stmt = f"INTO cdbpcs_task ({keys_to_insert})"
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            stmt += " "
            for value_to_insert in values:
                stmt += f"SELECT {value_to_insert} FROM dual UNION ALL "
            stmt = stmt[:-10]
        else:
            stmt += " VALUES "
            stmt += f"({'), ('.join(values)})"
        sqlapi.SQLinsert(stmt)

    # adjust table cdb_object
    sqlapi.SQLinsert(
        """INTO cdb_object (id, relation)
            SELECT cdb_object_id, 'cdbpcs_task' FROM cdbpcs_task
            WHERE cdb_object_id NOT IN (SELECT id FROM cdb_object
                                        WHERE relation = 'cdbpcs_task')"""
    )
