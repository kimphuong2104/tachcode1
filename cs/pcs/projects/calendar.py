#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access,too-many-locals,too-many-lines,consider-using-f-string

from collections import defaultdict

from cdb import auth, sqlapi, ue
from cdb.classbody import classbody
from cdb.typeconversion import to_legacy_date_format
from cs.calendar import CalendarProfile  # pylint: disable=unused-import
from cs.calendar import CalendarDayType
from cs.calendar import getNextStartDate as getNextStartDate_base
from cs.calendar import getWorkdays as getWorkdays_base
from cs.calendar import workday
from cs.calendar.workday import _fxcl

DAY_TYPE_WORK = 0
DAY_TYPE_OFF = 1

START = "START"
END = "END"
REL_TYPE_POSITIONS = {
    # see constants cs.pcs.projects.tasks.kTaskDependency*
    "AA": (START, START),
    "EA": (END, START),
    "AE": (START, END),
    "EE": (END, END),
}
TO_REL_TYPE = {START: "A", END: "E"}

# use calendar index for calculation
ACTIVATE_CACHE = True

CALENDAR_ID_CACHE = {}
CALENDAR_CACHE = {}
STF_CACHE = {}
ETF_CACHE = {}
STP_CACHE = {}
ETP_CACHE = {}
TASKS_BY_PARENT_ID = defaultdict(set)
TASKS = {}
LOCKED_TASKS = set()
PRED = defaultdict(set)
SUCC = defaultdict(set)
MINIMAL_GAPS = defaultdict(int)
NO_PREDS = set()


def clearChaches():
    CALENDAR_ID_CACHE.clear()
    STF_CACHE.clear()
    ETF_CACHE.clear()
    STP_CACHE.clear()
    ETP_CACHE.clear()
    TASKS_BY_PARENT_ID.clear()
    TASKS.clear()
    LOCKED_TASKS.clear()
    PRED.clear()
    SUCC.clear()
    MINIMAL_GAPS.clear()
    NO_PREDS.clear()


@classbody
class CalendarProfile:
    def on_cdb_recalculate_projects_now(self, ctx):
        from cs.pcs.projects import Project
        from cs.pcs.projects.tasks import Task

        if ctx is not None:
            tasks = []
            wrong_date_projects = []

            if ctx.classname == "cdb_calendar_profile":
                for p in self.Projects:
                    if p.checkProjectCalendarDates(self):
                        wrong_date_projects.append(p.GetDescription())
                        continue
                    p.recalculate()
                    tasks += p.Tasks

            if ctx.classname == "cdbpcs_project":
                for obj in ctx.objects:
                    p = Project.ByKeys(cdb_project_id=obj.cdb_project_id)
                    p.recalculate()
                    tasks += p.Tasks

            if tasks:
                Task.adjustDependingObjects_many(tasks)

            if wrong_date_projects:
                raise ue.Exception(
                    "cdbpcs_invalid_calendar_profile", "\n".join(wrong_date_projects)
                )


class WithCalendarIndex:
    def getCalendarProfileID(self):
        prj_id = self.cdb_project_id
        if prj_id not in CALENDAR_ID_CACHE:
            CALENDAR_ID_CACHE[prj_id] = self.mapped_calendar_profile_id
        return CALENDAR_ID_CACHE.get(prj_id, None)

    def getChacheID(self):
        return getChacheID(cdb_project_id=self.cdb_project_id, task_id=self.task_id)

    def _mayNotBeMovedAutomatically(self, check_access=True):
        return (
            self.status in [50, 200, 250]
            or check_access
            and not self.CheckAccess("save", auth.persno)
        )

    def adjust_all_idx_to_subtasks(self):
        for t in TASKS_BY_PARENT_ID[
            getChacheID(cdb_project_id=self.cdb_project_id, task_id="")
        ]:
            t._adjust_idx_to_subtasks()

    def _adjust_idx_to_subtasks(self):
        for t in TASKS_BY_PARENT_ID[self.getChacheID()]:
            t._adjust_idx_to_subtasks()
        self._adjustIDX()

    def _adjustIDX(self):
        if self.is_group:
            subtask_start_idx = []
            subtask_end_idx = []
            for t in self.OrderedSubTasks:
                stidx = t.getStartTimeFcastIDX()
                if stidx:
                    subtask_start_idx.append(stidx)
                etidx = t.getEndTimeFcastIDX()
                if etidx:
                    subtask_end_idx.append(etidx)
            if subtask_start_idx:
                self.setStartTimePlanIDX(min(subtask_start_idx))
            else:
                self.setStartTimePlanIDX()
            if subtask_end_idx:
                self.setEndTimePlanIDX(max(subtask_end_idx))
            else:
                self.setEndTimePlanIDX()
            if self.auto_update_time and getattr(self, "automatic", 1):
                self.setStartTimeFcastIDX(self.getStartTimePlanIDX())
                self.setEndTimeFcastIDX(self.getEndTimePlanIDX())
        else:
            self.setStartTimePlanIDX(self.getStartTimeFcastIDX())
            self.setEndTimePlanIDX(self.getEndTimeFcastIDX())

    def moveFcastIDX(self, movement):
        sidx = self.getStartTimeFcastIDX()
        eidx = self.getEndTimeFcastIDX()
        if sidx and eidx:
            self.setStartTimeFcastIDX(sidx + movement)
            self.setEndTimeFcastIDX(eidx + movement)

    def movePlanIDX(self, movement):
        sidx = self.getStartTimePlanIDX()
        eidx = self.getEndTimePlanIDX()
        if sidx and eidx:
            self.setStartTimePlanIDX(sidx + movement)
            self.setEndTimePlanIDX(eidx + movement)

    def setStartTimeFcastIDX(self, new_idx=""):
        STF_CACHE[self] = new_idx

    def setEndTimeFcastIDX(self, new_idx=""):
        ETF_CACHE[self] = new_idx

    def setStartTimePlanIDX(self, new_idx=""):
        STP_CACHE[self] = new_idx

    def setEndTimePlanIDX(self, new_idx=""):
        ETP_CACHE[self] = new_idx

    def getStartTimeFcastIDX(self):
        idx = STF_CACHE.get(self, None)
        if idx is None:
            idx = self._calculateStartTimeFcastIDX()
            STF_CACHE[self] = idx
        return idx

    def getEndTimeFcastIDX(self):
        idx = ETF_CACHE.get(self, None)
        if idx is None:
            idx = self._calculateEndTimeFcastIDX()
            ETF_CACHE[self] = idx
        return idx

    def getStartTimePlanIDX(self):
        idx = STP_CACHE.get(self, None)
        if idx is None:
            idx = self._calculateStartTimePlanIDX()
            STP_CACHE[self] = idx
        return idx

    def getEndTimePlanIDX(self):
        idx = ETP_CACHE.get(self, None)
        if idx is None:
            idx = self._calculateEndTimePlanIDX()
            ETP_CACHE[self] = idx
        return idx

    def _calculateStartTimeFcastIDX(self):
        return getLateIndexByDate(self.getCalendarProfileID(), self.getStartTimeFcast())

    def _calculateEndTimeFcastIDX(self):
        return getEarlyIndexByDate(self.getCalendarProfileID(), self.getEndTimeFcast())

    def _calculateStartTimePlanIDX(self):
        return getLateIndexByDate(self.getCalendarProfileID(), self.getStartTimePlan())

    def _calculateEndTimePlanIDX(self):
        return getEarlyIndexByDate(self.getCalendarProfileID(), self.getEndTimePlan())

    def getDateByIndex(self, myindex):
        return getDateByIndex(
            calendar_profile_id=self.getCalendarProfileID(), myindex=myindex
        )

    def getDirektPredecessors(self, connection_type):
        return getDirektPredecessors(task=self, connection_type=connection_type)

    def getDirektSuccessors(self, connection_type):
        return getDirektSuccessors(task=self, connection_type=connection_type)

    def getAllPredecessors(self, connection_type):
        return getAllPredecessors(task=self, connection_type=connection_type)

    def getAllSuccessors(self, connection_type):
        return getAllSuccessors(task=self, connection_type=connection_type)

    def move_date(self, connection_type, movement):
        # check if changes would violate fix end dates
        if connection_type == START:
            idx = self.getStartTimeFcastIDX()
            if idx:
                self.setStartTimeFcastIDX(idx + movement)
                if not self.is_group or self.auto_update_time:
                    self.setStartTimePlanIDX(idx + movement)
        elif connection_type == END:
            idx = self.getEndTimeFcastIDX()
            if idx:
                self.setEndTimeFcastIDX(idx + movement)
                if not self.is_group or self.auto_update_time:
                    self.setEndTimePlanIDX(idx + movement)


def _getTask(oid, forced_load=True):
    t = TASKS.get(oid, None)
    if not t and forced_load:
        from cs.pcs.projects.tasks import Task

        cdb_project_id, task_id = oid
        t = Task.ByKeys(cdb_project_id=cdb_project_id, task_id=task_id)
        if not t:
            raise ue.Exception("cdbpcs_projects_task_not_found", oid)
        _addTask(t)
    return t


def getChacheID(cdb_project_id, task_id, **kwargs):
    return (cdb_project_id, task_id)


def _addTask(obj):
    toid = getChacheID(cdb_project_id=obj.cdb_project_id, task_id=obj.task_id)
    TASKS[toid] = obj
    poid = getChacheID(cdb_project_id=obj.cdb_project_id, task_id=obj.parent_task)
    TASKS_BY_PARENT_ID[poid].add(obj)


def _addLockedTask(obj):
    LOCKED_TASKS.add(obj)


def getParentTask(obj):
    if obj.parent_task:
        toid = getChacheID(cdb_project_id=obj.cdb_project_id, task_id=obj.parent_task)
        return TASKS[toid]
    return None


def getTasks():
    return list(TASKS.values())


def getLockedTasks():
    return LOCKED_TASKS.copy()


def getDirektPredecessors(task, connection_type):
    return PRED.get((task, connection_type), set())


def getDirektSuccessors(task, connection_type):
    return SUCC.get((task, connection_type), set())


def getAllPredecessors(task, connection_type):
    return _getRelationsFromChache(
        relation_chache=PRED, task=task, connection_type=connection_type
    )


def getAllSuccessors(task, connection_type):
    return _getRelationsFromChache(
        relation_chache=SUCC, task=task, connection_type=connection_type
    )


def _getRelationsFromChache(relation_chache, task, connection_type, result_set=None):
    if result_set is None:
        result_set = set()
    for entry in relation_chache.get((task, connection_type), set()):
        if entry not in result_set:
            result_set.add(entry)
            _getRelationsFromChache(
                relation_chache=relation_chache,
                task=entry[0],
                connection_type=entry[1],
                result_set=result_set,
            )
    return result_set


def loadTasks(prj_id, check_access=True):
    from cs.pcs.projects.tasks import Task

    for t in Task.KeywordQuery(cdb_project_id=prj_id, ce_baseline_id=""):
        _addTask(obj=t)
        if t._mayNotBeMovedAutomatically(check_access=check_access):
            _addLockedTask(obj=t)
    return list(TASKS.values())


def enforceSubtaskMovement(parent, connection_type):
    if parent.is_group and not parent.auto_update_time:
        PRED[(parent, END)].discard((parent, START))
        SUCC[(parent, START)].discard((parent, END))
        if connection_type == START:
            for subtask in getSubtasks(parent):
                PRED[(subtask, START)].add((parent, START))
                SUCC[(parent, START)].add((subtask, START))
        elif connection_type == END:
            for subtask in getSubtasks(parent):
                PRED[(parent, END)].add((subtask, END))
                SUCC[(subtask, END)].add((parent, END))


def getAllSubtasks(parent):
    result = []
    for subtask in getSubtasks(parent):
        result.append(subtask)
        result += getAllSubtasks(subtask)
    return result


def getSubtasks(parent):
    return TASKS_BY_PARENT_ID.get(parent.getChacheID(), [])


def getActiveSubtasks(parent, allsubtasks=False):
    if allsubtasks:
        return [x for x in getAllSubtasks(parent) if not x.isDiscarded()]
    return [x for x in getSubtasks(parent) if not x.isDiscarded()]


def _refreshTaskRelation(task_rel):
    pred_pos, succ_pos = REL_TYPE_POSITIONS[task_rel.rel_type]
    pred = task_rel.PredecessorTask
    succ = task_rel.SuccessorTask
    gap = 0
    p_discarded = pred.isDiscarded()
    s_discarded = succ.isDiscarded()
    if s_discarded:
        succ_pos = START
    if task_rel.minimal_gap and not p_discarded and not s_discarded:
        gap += task_rel.minimal_gap
    NO_PREDS.discard(succ)

    if pred.milestone and succ.milestone:
        if not pred.start_is_early and succ.start_is_early:
            gap += 1
    elif pred.milestone:
        if not pred.start_is_early and succ_pos == START:
            gap += 1
    elif succ.milestone:
        if succ.start_is_early and pred_pos == END:
            gap += 1
    elif pred_pos == END and succ_pos == START:
        gap += 1

    if p_discarded:
        gap -= pred.getDaysFcast()
    elif not pred.milestone and pred_pos == START:
        gap -= pred.getDaysFcast() - 1
    if not succ.milestone and succ_pos == END:
        gap -= succ.getDaysFcast() - 1

    pred_pos = END
    succ_pos = START
    PRED[(succ, succ_pos)].add((pred, pred_pos))
    SUCC[(pred, pred_pos)].add((succ, succ_pos))
    MINIMAL_GAPS[(pred, pred_pos, succ, succ_pos)] = gap
    MINIMAL_GAPS[(succ, succ_pos, pred, pred_pos)] = gap


def loadTaskRelations(prj_id, check_access=True):
    # For each task start / end, store all task relations.
    # Each task has an implicit relation from start to end, this simplifies
    # the logic later because we don't have to distinguish between the
    # various relation types.
    tasks = loadTasks(prj_id=prj_id, check_access=check_access)
    for task in tasks:
        NO_PREDS.add(task)
        PRED[(task, END)].add((task, START))
        SUCC[(task, START)].add((task, END))
        MINIMAL_GAPS[(task, START, task, END)] = max(0, task.getDaysFcast() - 1)

    # Add the explicitly stored task relations.
    from cs.pcs.projects.tasks import TaskRelation

    result = TaskRelation.KeywordQuery(cdb_project_id=prj_id, cdb_project_id2=prj_id)
    for tr in result:
        _refreshTaskRelation(tr)

    # Child tasks may not start before their parents, and not end after their parents.
    # ignore this, if the parents values are not automatically updated
    # The Order in witch the set is created is identical to the order in witch
    # they are adjusted; therefore relations to parents have to be evaluated at the end
    for parent_id in list(TASKS_BY_PARENT_ID):
        if parent_id[1]:
            parent = _getTask(parent_id)
            if parent.is_group:
                for subtask in getAllSubtasks(parent):
                    PRED[(subtask, START)].add((parent, START))
                    SUCC[(parent, START)].add((subtask, START))
                    PRED[(parent, END)].add((subtask, END))
                    SUCC[(subtask, END)].add((parent, END))

    _removeTasksWithPredecessors(toid=getChacheID(cdb_project_id=prj_id, task_id=""))


def _removeTasksWithPredecessors(toid, parent_constraint=False):
    task = _getTask(toid, forced_load=False)
    if task:
        if task not in NO_PREDS:
            parent_constraint = True
        elif parent_constraint:
            NO_PREDS.discard(task)
        else:
            parent_constraint = parent_constraint or not task.isASAP()
    for t in TASKS_BY_PARENT_ID[toid]:
        _removeTasksWithPredecessors(
            toid=getChacheID(cdb_project_id=t.cdb_project_id, task_id=t.task_id),
            parent_constraint=parent_constraint,
        )


def hasNoPredecessors(task):
    return task in NO_PREDS


def getMinimalGap(pred, succ):
    return MINIMAL_GAPS[(pred[0], pred[1], succ[0], succ[1])]


def getEarlyIndexByDate(calendar_profile_id, mydate):
    idx = getIndexByDate(calendar_profile_id, mydate)
    return idx[0]


def getLateIndexByDate(calendar_profile_id, mydate):
    idx = getIndexByDate(calendar_profile_id, mydate)
    return idx[1]


def getIndexByDate(calendar_profile_id, mydate):
    if not calendar_profile_id or not mydate:
        return None, None
    dict_by_day = getCalendarIndex(calendar_profile_id)[0]
    return dict_by_day.get(mydate, (None, None))


def getDateByIndex(calendar_profile_id, myindex):
    if not calendar_profile_id or not myindex:
        return ""
    dict_by_idx = getCalendarIndex(calendar_profile_id)[1]
    result = dict_by_idx.get(myindex, None)
    if not result:
        raise ue.Exception("cdbpcs_calendar_outdated")
    return result


def clearCalendarIndex(calendar_profile_id):
    CALENDAR_CACHE.pop(calendar_profile_id, None)


def getCalendarIndex(calendar_profile_id):
    my_key = calendar_profile_id
    dict_by_day, dict_by_idx = CALENDAR_CACHE.get(my_key, ({}, {}))
    if not dict_by_day:
        dict_by_day, dict_by_idx = _getCalendarIndex(calendar_profile_id)
        CALENDAR_CACHE[my_key] = (dict_by_day, dict_by_idx)
    return dict_by_day, dict_by_idx


def _getCalendarIndex(calendar_profile_id):
    if not calendar_profile_id:
        return {}, {}

    entries = sqlapi.RecordSet2(
        "cdb_calendar_entry",
        "calendar_profile_id = '{}'"
        " AND personalnummer IS NULL"
        " AND cdb_project_id IS NULL".format(calendar_profile_id),
        columns=["day", "early_work_idx", "late_work_idx"],
        addtl="ORDER BY day",
    )
    dict_by_day = {}
    dict_by_idx = {}

    for x in entries:
        day = x.day
        early = x.early_work_idx
        late = x.late_work_idx

        dict_by_day[day] = (early, late)
        if early == late:
            dict_by_idx[early] = day

    return dict_by_day, dict_by_idx


def calculateTimeFrame(
    calendar_oid, start=None, end=None, days=None, shift_right=True, milestone=False
):
    if not calendar_oid:
        return None, None, 0
    if not start:
        start = None
    if not end:
        end = None
    if not days:
        days = None
    if milestone:
        if end:
            return end, end, 0
        return start, start, 0
    elif not start and end and isinstance(days, int):
        # calculate start date
        start = getNextStartDate_base(calendar_oid, end, max(0, days - 1) * -1)
    elif start and not end and isinstance(days, int):
        # calculate end date
        end = getNextStartDate_base(calendar_oid, start, max(0, days - 1))
    elif start and end:
        # calculate duration
        if start > end:
            if shift_right:
                end = start
            else:
                start = end
        days = max(getWorkdays_base(calendar_oid, start, end), 1)

    return start, end, days


def getWorkdays(prj_id, start_date, end_date):
    if not start_date or not end_date:
        return 0
    if start_date == end_date:
        return 1
    sd = sqlapi.SQLdbms_date(start_date)
    ed = sqlapi.SQLdbms_date(end_date)
    sql = """ SELECT day, early_work_idx, late_work_idx
              FROM cdb_calendar_entry c, cdbpcs_project p
              WHERE (day = %s OR day = %s)
              AND c.calendar_profile_id = p.calendar_profile_id
              AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
              AND p.cdb_project_id = '%s'
              AND p.ce_baseline_id = ''
              ORDER BY day
          """ % (
        sd,
        ed,
        prj_id,
    )
    result = sqlapi.RecordSet2(sql=sql)
    return int(result[1]["early_work_idx"]) - int(result[0]["late_work_idx"]) + 1


def _get_sql_statement_for_day_count(cdb_project_id, start_attr, end_attr):
    return (
        "(1 + "
        "(SELECT early_work_idx"
        " FROM cdb_calendar_entry c, cdbpcs_project p"
        " WHERE cdbpcs_project.{end_attr} = c.day"
        " AND c.calendar_profile_id = p.calendar_profile_id"
        " AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL"
        " AND p.cdb_project_id = '{cdb_project_id}'"
        " AND p.ce_baseline_id = '') - "
        "(SELECT late_work_idx"
        " FROM cdb_calendar_entry c, cdbpcs_project p"
        " WHERE cdbpcs_project.{start_attr} = c.day"
        " AND c.calendar_profile_id = p.calendar_profile_id"
        " AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL"
        " AND p.cdb_project_id = '{cdb_project_id}'"
        " AND p.ce_baseline_id = '')"
        ")"
    ).format(cdb_project_id=cdb_project_id, start_attr=start_attr, end_attr=end_attr)


def get_sql_statement_for_days(cdb_project_id, days_attr, start_attr, end_attr):
    return (
        "cdbpcs_project SET"
        " {days_attr} = {day_count}"
        " WHERE cdb_project_id = '{cdb_project_id}' AND ce_baseline_id = ''"
        " AND {start_attr} IS NOT NULL AND {end_attr} IS NOT NULL"
    ).format(
        cdb_project_id=cdb_project_id,
        days_attr=days_attr,
        start_attr=start_attr,
        end_attr=end_attr,
        day_count=_get_sql_statement_for_day_count(
            cdb_project_id, start_attr, end_attr
        ),
    )


def adjustProjectWorkdays(prj_id):
    sqlapi.SQLupdate(
        get_sql_statement_for_days(
            prj_id, "days_fcast", "start_time_fcast", "end_time_fcast"
        )
    )
    sqlapi.SQLupdate(
        get_sql_statement_for_days(prj_id, "days", "start_time_plan", "end_time_plan")
    )


def getNextStartDate(prj_id, myDate, distance=0):
    if not myDate:
        return myDate
    date = sqlapi.SQLdbms_date(myDate)
    sql = """ SELECT a.day
              FROM cdb_calendar_entry a, cdb_calendar_entry c, cdbpcs_project p
              WHERE c.day = %s AND c.late_work_idx = a.late_work_idx - %s
              AND a.calendar_profile_id = p.calendar_profile_id
              AND a.personalnummer IS NULL AND a.cdb_project_id IS NULL
              AND c.calendar_profile_id = p.calendar_profile_id
              AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
              """
    if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
        sql += "AND p.cdb_project_id = '%s' AND p.ce_baseline_id = '' AND a.day_type_id = '%s'"
    else:
        sql += "AND p.cdb_project_id = '%s' AND p.ce_baseline_id = '' AND a.day_type_id = %s"
    stmt = sql % (date, distance, prj_id, 1)
    result = sqlapi.RecordSet2(sql=stmt)
    return result[0]["day"]


def getNextEndDate(prj_id, myDate, distance=0):
    if not myDate:
        return myDate
    date = sqlapi.SQLdbms_date(myDate)
    sql = """SELECT a.day
             FROM cdb_calendar_entry a, cdb_calendar_entry c, cdbpcs_project p
             WHERE c.day = %s AND c.early_work_idx = a.early_work_idx - %s
             AND a.calendar_profile_id = p.calendar_profile_id
             AND a.personalnummer IS NULL AND a.cdb_project_id IS NULL
             AND c.calendar_profile_id = p.calendar_profile_id
             AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
          """
    if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
        sql += "AND p.cdb_project_id = '%s' AND p.ce_baseline_id = '' AND a.day_type_id = '%s'"
    else:
        sql += "AND p.cdb_project_id = '%s' AND p.ce_baseline_id = '' AND a.day_type_id = %s"
    stmt = sql % (date, distance, prj_id, 1)
    result = sqlapi.RecordSet2(sql=stmt)
    return result[0]["day"]


def getDistance(prj_id, old_date, new_date):
    if not old_date or not new_date:
        return 0
    od = sqlapi.SQLdbms_date(old_date)
    nd = sqlapi.SQLdbms_date(new_date)
    sql = """SELECT day, early_work_idx, late_work_idx
             FROM cdb_calendar_entry c, cdbpcs_project p
             WHERE (day = %s OR day = %s)
             AND c.calendar_profile_id = p.calendar_profile_id
             AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL
             AND p.cdb_project_id = '%s' AND p.ce_baseline_id = ''
             ORDER BY day
          """ % (
        od,
        nd,
        prj_id,
    )
    result = sqlapi.RecordSet2(sql=sql)
    if not result or len(result) < 2:
        raise ue.Exception("cdbpcs_calendar_outdated")
    return int(result[1]["late_work_idx"]) - int(result[0]["late_work_idx"])


def getProjectWorkdays(
    prj_rule=None,
    with_prj_ids=None,
    without_prj_ids=None,
    start_date=None,
    end_date=None,
):
    """
    Return a dictionary of lists of (datetime, daytype_name) pairs for all
    workdays in the [start_date, end_date] interval for each
    project in the input list_of_proj.
    """
    return _getProjectDays(
        prj_rule, with_prj_ids, without_prj_ids, start_date, end_date, DAY_TYPE_WORK
    )


def getProjectDaysOff(
    prj_rule=None,
    with_prj_ids=None,
    without_prj_ids=None,
    start_date=None,
    end_date=None,
):
    """
    Return a dictionary of lists of (datetime, daytype_name) pairs for all
    days off in the [start_date, end_date] interval for each
    project in the input list_of_proj.
    """
    return _getProjectDays(
        prj_rule, with_prj_ids, without_prj_ids, start_date, end_date, DAY_TYPE_OFF
    )


def _getProjectDays(
    prj_rule=None,
    with_prj_ids=None,
    without_prj_ids=None,
    start_date=None,
    end_date=None,
    day_type=DAY_TYPE_OFF,
):
    """
    Return the days of or workdays for all projects given as input.

    :Parameters:
        - prj_rule: a CDB Rule (cdb.objects.Rule) to filter all projects.
        - with_prj_ids: a list of additional projects ids to take into
          consideration (might fall outside the prj_rule).
        - without_prj_ids: a list of projects ids which should not be taken
          into consideration when evaluating the days.
        - start_date: a datetime start date for the returned interval
        - end_date: a datetime end date for the returned interval
    :Returns:
        - dictionary of lists of (datetime, daytype_name) pairs for all
          days off or workdays in the [start_date, end_date] interval for each
          project determined by the list of input parameters. cdb_project_id is
          used as a dictionary key.
    """
    # The data collection will be done in getCalendarDaysForProjects
    # This methode remains to keep the calls/interfaces working.
    proj_dict, cal_dict = getCalendarDaysForProjects(
        prj_rule, with_prj_ids, without_prj_ids, start_date, end_date, day_type
    )
    day_dict = {}
    for proj_id, cal_id in proj_dict.items():
        day_dict[proj_id] = cal_dict.get(cal_id, [])
    return day_dict


def getCalendarDaysForProjects(
    prj_rule=None,
    with_prj_ids=None,
    without_prj_ids=None,
    start_date=None,
    end_date=None,
    day_type=DAY_TYPE_OFF,
):
    """
    Return the days of or workdays for all projects given as input.

    :Parameters:
        - prj_rule: a CDB Rule (cdb.objects.Rule) to filter all projects.
        - with_prj_ids: a list of additional projects ids to take into
          consideration (might fall outside the prj_rule).
        - without_prj_ids: a list of projects ids which should not be taken
          into consideration when evaluating the days.
        - start_date: a datetime start date for the returned interval
        - end_date: a datetime end date for the returned interval
    :Returns:
        - dictionary of calendar profile ids for each
          project determined by the list of input parameters. cdb_project_id is
          used as a dictionary key.
        - dictionary of lists of (datetime, daytype_name) pairs for all
          days off or workdays in the [start_date, end_date] interval for relevant
          calendar profiles for the projects determined by the list of input
          parameters. calendar_profile_id is used as a dictionary key.
    """
    # A maximum number of elements in the WHERE IN clause
    MAX_ELEMS_IN_CLAUSE = 500
    start_limit = end_limit = ""
    if not prj_rule and not with_prj_ids:
        return {}
    if isinstance(start_date, (type(""), type(""))) or isinstance(
        end_date, (type(""), type(""))
    ):
        raise ue.Exception("cdbpcs_calendar_wrong_date_type")
    if start_date is not None:
        start_limit = " AND %s <= v.day " % sqlapi.SQLdbms_date(
            to_legacy_date_format(start_date, full=False)
        )
    if end_date is not None:
        end_limit = " AND v.day <= %s " % sqlapi.SQLdbms_date(
            to_legacy_date_format(end_date, full=False)
        )

    chr1 = "''"
    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        chr1 = "chr(1)"

    # Split the input with_prj_ids list into smaller lists of maximum size
    # MAX_ELEMS_IN_CLAUSE.
    list_of_groups = []
    if with_prj_ids:
        # Filter out duplicates.
        list_of_proj = list(set(with_prj_ids))
        cutoffs = list(range(0, len(list_of_proj), MAX_ELEMS_IN_CLAUSE)) + [
            len(list_of_proj)
        ]
        for n in range(len(cutoffs) - 1):
            list_of_groups.append(list_of_proj[cutoffs[n] : cutoffs[n + 1]])
    # Keep a dictionary of day types and their names in the current language.
    dayTypes = CalendarDayType.Query()
    dayTypeMap = {}
    for day_t in dayTypes:
        dayTypeMap[day_t.day_type_id] = day_t["name"]
    # Define project dictionary and calendar-days dictionary
    proj_dict = {}
    caldays_dict = {}

    # Send a SELECT query evaluating the project rule and the without_prj_ids
    # list (if there is a rule) and the first MAX_ELEMS_IN_CLAUSE items in the
    # with_prj_ids list. Then send the remaining SELECT queries until all the
    # elements from with_prj_ids are evaluated. Add the resulting data to the
    # project->day dictionary - but the days would be filled later.
    idx = 0
    while idx < len(list_of_groups) or prj_rule:
        if prj_rule:
            cls = prj_rule.getClasses()[0]  # always cdbpcs_project class
            root = prj_rule._GetNode(cls)
            sqlProjTableAlias = root.alias
            sql_prj_rule = "%s" % prj_rule.expr(cls)
            prj_rule = None
        else:
            sql_prj_rule = " 0 = 1 "
            sqlProjTableAlias = "cdbpcs_project"
        if without_prj_ids:
            excl_proj_cond = "cdb_project_id NOT IN ( %s ) " % ", ".join(
                ["'%s'" % sqlapi.quote(proj) for proj in without_prj_ids]
            )
            excl_proj_rel = "%s.%s" % (sqlProjTableAlias, excl_proj_cond)
        else:
            excl_proj_rel = " 1 = 1 "
        if idx < len(list_of_groups):
            proj_cond = "cdb_project_id IN ( %s ) AND ce_baseline_id = '' " % ", ".join(
                ["'%s'" % sqlapi.quote(proj) for proj in list_of_groups[idx]]
            )
            proj_rel = "%s.%s" % (sqlProjTableAlias, proj_cond)
        else:
            proj_rel = " 0 = 1"

        # The "1st" query determines the cdb_project_ids and their calendar_profile_ids that fit.
        # Also fill up the days dictionary with the initial empty lists
        sqlStatement1 = (
            "SELECT cdb_project_id, calendar_profile_id FROM cdbpcs_project %s "
            "WHERE  (%s OR %s) AND %s AND ce_baseline_id = ''"
            % (sqlProjTableAlias, sql_prj_rule, proj_rel, excl_proj_rel)
        )
        proj_recs = sqlapi.RecordSet2(sql=sqlStatement1)
        for rec in proj_recs:
            proj_dict[rec.cdb_project_id] = rec.calendar_profile_id
            # set the empty list for days
            if rec.calendar_profile_id not in caldays_dict:
                caldays_dict[rec.calendar_profile_id] = []
        idx += 1

    # The 2nd query to fill up the days list of the found calendars
    # Assume that the calendar id list dose not overflow the SQL statement
    profile_cond = "calendar_profile_id IN ( %s ) " % ", ".join(
        ["'%s'" % sqlapi.quote(prfl) for prfl in list(caldays_dict)]
    )
    sqlStatement2 = (
        "SELECT calendar_profile_id, day, day_type_id "
        "FROM   cdb_calendar_entry_v v "
        "WHERE v.%s"
        "  AND v.is_day_off_type = %s "
        "  AND (v.personalnummer IS NULL OR v.personalnummer IN (%s, '')) "
        "  AND (v.cdb_project_id IS NULL OR v.cdb_project_id IN (%s, '')) "
        " %s %s "
        "ORDER BY v.day " % (profile_cond, day_type, chr1, chr1, start_limit, end_limit)
    )
    cal_days = sqlapi.RecordSet2(sql=sqlStatement2)
    for rec in cal_days:
        caldays_dict[rec.calendar_profile_id].append(
            (rec.day.date(), dayTypeMap[rec.day_type_id])
        )
    return proj_dict, caldays_dict


def combined_workday_count(
    start_date, end_date, prj=None, persno=None, assignment_oid=None
):
    sd = sqlapi.SQLdbms_date(start_date)
    ed = sqlapi.SQLdbms_date(end_date)
    sql = None
    uuid = persno or assignment_oid

    is_postgres = sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES

    if uuid:
        sql = f"""
            SELECT COUNT(*) AS count
            FROM cdbpcs_capa_sched_pd
            WHERE day >= {sd}
                AND day <= {ed}
                AND assignment_oid = '{uuid}'
            """
    elif prj:
        sql = f"""
            SELECT COUNT(*) AS count
            FROM cdb_calendar_entry
            WHERE day_type_id={"'1'" if is_postgres else "1"}
                AND personalnummer IS NULL
                AND day >= {sd}
                AND day <= {ed}
                AND calendar_profile_id = '{prj.calendar_profile_id}'
            """
    if sql:
        return int(sqlapi.RecordSet2(sql=sql)[0]["count"])
    return 0


def combined_workdays(cdb_project_id, persno, start_date=None, end_date=None):
    if _fxcl():
        if cdb_project_id and persno:
            proj_cal = project_workdays(
                cdb_project_id=cdb_project_id, start_date=start_date, end_date=end_date
            )
            pers_cal = workday.personal_workdays(
                persno=persno, start_date=start_date, end_date=end_date
            )
            return [x for x in proj_cal if x in pers_cal]
        if cdb_project_id:
            return project_workdays(
                cdb_project_id=cdb_project_id, start_date=start_date, end_date=end_date
            )
        if persno:
            return workday.personal_workdays(
                persno=persno, start_date=start_date, end_date=end_date
            )
    if start_date and end_date:
        return workday.workdays(start_date, end_date)
    return []


def project_workdays(cdb_project_id, start_date=None, end_date=None):
    if _fxcl() and cdb_project_id:
        cal = getProjectWorkdays(
            with_prj_ids=[cdb_project_id], start_date=start_date, end_date=end_date
        )
        if cdb_project_id not in cal:
            return []
        return [x[0] for x in cal[cdb_project_id]]
    if start_date and end_date:
        return workday.workdays(start_date, end_date)
    return []
