#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module misc

This is the documentation for the misc module.
"""

import datetime
import logging
import time

from cdb import sqlapi
from cdb import CADDOK
from cdb import constants
from cdb import i18n
from cdb import transaction
from cdb import util
from cdb.tools import getObjectByName
from cdb.lru_cache import lru_cache
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cdb.platform.olc import StateDefinition

from cdb.platform import mom
from cdb.objects import Object
from cdb.fls import allocate_license

from cs.activitystream.objects import UserPosting
from cs.calendar import workday
from cs.platform.web import get_root_url
from cs.platform.web.uisupport import get_webui_link

__all__ = [
    'calc_deadline',
    'DummyContext',
    'get_state_text',
    'is_auxiliary_file',
    'is_converted_file',
    'Link',
    'now',
    'set_state',
    'set_state_interactive',
    'is_installed',
    'create_user_posting',
    'is_csweb',
]


__STATE_TXT_CACHE = {}

EMAIL_TEMPLATE_LANGUAGES = set(["de", "en"])


def _get_pydate_format(_format):
    # Workaround for E032998
    import re

    conversions = [
        ("YYYY", "%Y"),
        ("MM", "%m"),
        ("DD", "%d"),
        ("hh", "%H"),
        ("mm", "%M"),
        ("ss", "%S")
    ]

    result = _format
    for wrong, right in conversions:
        result = re.sub(wrong, right, result)
    return result


def get_pydate_format():
    return _get_pydate_format(i18n.get_date_format())


def get_pydatetime_format():
    return _get_pydate_format(i18n.get_datetime_format())


def _run_op(opname, cls_or_obj, *args, **kwargs):
    return operation(opname, cls_or_obj, *args, **kwargs)


def calc_deadline(process):
    """
    Updates ``process.deadline`` (only if both its ``max_duration`` and
    ``start_date`` are set).

    If the ``cdb_setting`` ``cs.workflow-calc_deadline_workdays`` is ``"1"``,
    the function ``_calc_deadline_workdays`` is used, else the legacy function
    ``_calc_deadline_simple``.

    :param process: Task or process to update (named ``process`` for backwards
        compatibility)
    :type process: cs.workflow.tasks.Task or cs.workflow.processes.Process
    """
    if process.max_duration is not None and process.start_date:
        use_workdays = util.PersonalSettings().getValueOrDefault(
            "cs.workflow",
            "calc_deadline_workdays",
            "0"
        )
        if use_workdays == "1":
            _calc_deadline_workdays(process)
        else:
            _calc_deadline_simple(process)


def _calc_deadline_simple(process):
    """
    Updates ``process.deadline`` by simply offsetting its ``start_date`` with
    its ``max_duration``.

    .. warning ::
        This code does not handle fractions of a day and neither weekends nor
        holidays.

    :param process: Task or process to update (named ``process`` for backwards
        compatibility)
    :type process: cs.workflow.tasks.Task or cs.workflow.processes.Process
    """
    start_date = process.start_date
    delta = datetime.timedelta(days=process.max_duration)
    process.deadline = start_date + delta


def _calc_deadline_workdays(process):
    """
    Updates ``process.deadline``.

    If the subject is a person, use their personal calendar to determine the
    next workday (offset from ``process.start_date`` by
    ``process.max_duration``) as the deadline. Else, use a generic german
    holiday calendar.

    :param process: Task or process to update (named ``process`` for backwards
        compatibility)
    :type process: cs.workflow.tasks.Task or cs.workflow.processes.Process
    """
    duration = process.max_duration

    if duration is not None and process.start_date:
        if process.subject_type == "Person":
            deadline = workday.next_personal_workday(
                process.subject_id,
                process.start_date,
                duration
            )
        else:
            # TODO workday currently only supports german holidays
            deadline = workday.next_workday(
                process.start_date,
                duration,
                "de"
            )

        process.Update(deadline=deadline)


def set_state(obj, state, **kwargs):
    with transaction.Transaction():
        obj.ChangeState(
            state.status,
            check_access=False,
            **kwargs
        )
        if getattr(obj, "notifyAfterStateChange", None):
            obj.notifyAfterStateChange()


# Fixed E015631: the state change action can only be called in
#                interactive mode from todo panel
def set_state_interactive(obj, state, **kwargs):
    with transaction:
        obj.ChangeState(
            state.status,
            check_access=True,
            **kwargs
        )
        if getattr(obj, "notifyAfterStateChange", None):
            obj.notifyAfterStateChange()


def get_state_text(objektart, status_number, lang=None):
    key = "%s:%s" % (objektart, status_number)
    if key not in __STATE_TXT_CACHE:
        txt = ''
        sd = StateDefinition.ByKeys(objektart=objektart,
                                    statusnummer=status_number)
        if sd:
            txt = sd.StateText[lang or CADDOK.ISOLANG]
        __STATE_TXT_CACHE[key] = txt
    return __STATE_TXT_CACHE[key]


def now(fmt='%d.%m.%Y'):
    return time.strftime(fmt, time.localtime(time.time()))


def is_converted_file(fobj):
    # files created by ACS/DCS (.pdf,..)
    if fobj.cdbf_derived_from:
        orig_file = CDB_File.ByKeys(cdb_object_id=fobj.cdbf_derived_from)
        if orig_file:
            return orig_file.cdbf_object_id == fobj.cdbf_object_id
    return False


def is_auxiliary_file(fobj):
    # auxiliary files (.appinfo, .png,..) pointing to the 'main' file
    return True if fobj.cdb_belongsto else False


class DummyContext(object):
    def get_attribute_names(self):
        return list(self.__dict__)


class Link(object):
    def __init__(self, href, text, prompt="", icon=""):
        self.href = href
        self.text = text
        self.prompt = prompt
        self.icon = icon


def is_installed(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def get_object_class_by_name(clsname):
    extcls_conf = mom.entities.Class.ByClassname(clsname)
    if not extcls_conf:
        return None
    try:
        return getObjectByName(extcls_conf.getFqpyname())
    except Exception:
        pass
    return None


def notification_enabled():
    """
    Check flag: whether the email notification should be turned on or off.
    """
    return CADDOK.get("STOP_EMAIL_NOTIFICATION", None) is None


class ResponsibleBrowserEntry(Object):
    """Only for query.
    """
    __classname__ = "cdbwf_resp_browser"
    __maps_to__ = "cdbwf_resp_browser"

    @classmethod
    def DescriptionAttr(cls):
        return "description_{}".format(i18n.default())

    @classmethod
    def SubjectNameAttr(cls):
        return "subject_name_{}".format(i18n.default())

    def GetSubjectName(self):
        return getattr(self, self.SubjectNameAttr(), "")


def require_feature_viewing():
    # check license for viewing and excuting workflow
    allocate_license("WORKFLOW_001")


def require_feature_setup():
    # Check license for defining workflows
    allocate_license("WORKFLOW_002")


def require_feature_templating():
    # Check license for using workflow template
    allocate_license("WORKFLOW_003")


@lru_cache(maxsize=1, clear_after_ue=False)
def prefer_web_urls():
    preference = CADDOK.get("PREFER_LEGACY_URLS", None)
    return preference != "True"


def sync_global_briefcases():
    result = CADDOK.get("WORKFLOW_SYNC_GLOBALS", None)
    return result == "True"


def urljoin(*segments):
    """
    Returns a URL consisting of strings `segments`,
    each separated by exactly one `/`.
    If the first segment starts with any slashes,
    a single leading slash is preserved.

    :raises AttributeError: if any segment is not a string.
    """
    result = "/".join(s.strip("/") for s in segments)

    if segments[0].startswith("/"):
        result = "/{}".format(result)

    return result


def make_absolute_url(*segments):
    root = get_root_url()

    if not root or root == "http://www.example.org":
        logging.error("Root URL not set: '%s'", root)

    return urljoin(root, *segments)


def get_object_url(obj):
    if prefer_web_urls():
        webui_link = get_webui_link(None, obj)
        if not webui_link:  # None for files
            return ""
        return make_absolute_url(webui_link)
    else:
        return obj.MakeURL(plain=2)


def create_user_posting(context_object, comment):
    if comment:
        posting = operation(
            constants.kOperationNew,
            UserPosting,
            context_object_id=context_object.cdb_object_id,
        )
        posting.SetText("cdbblog_posting_txt", comment)


def is_csweb():
    from cdb import misc as cdbmisc
    root_id = cdbmisc.CDBApplicationInfo().getRootID()
    # http server == cs.web, unknown == tests
    return root_id in set([
        cdbmisc.kAppl_HTTPServer,
        cdbmisc.kAppl_Unknown,
    ])


def get_email_language(user):
    """
    :param user: Current User
    :type user: cdb.objects.org.Person

    :returns: Preferred language for emails set by the User
    Defaults to "en" if preferred language is not in EMAIL_TEMPLATE_LANGUAGES
    :rtype: str
    """
    if user is not None:
        pref = user.GetPreferredLanguage()
        if pref in EMAIL_TEMPLATE_LANGUAGES:
            return pref
    return "en"


def format_in_condition(col_name, values, max_inlist_value=None):
    def _convert(values):
        return "(%s)" % ",".join([sqlapi.make_literals(v) for v in values])

    if max_inlist_value is None:
        max_inlist_value = 1000
    if len(values) > max_inlist_value:
        in_condition = ""
        op = "{} in ".format(col_name)
        for i in range(0, len(values) // max_inlist_value):
            in_condition = in_condition + op + _convert(values[i * max_inlist_value: (i + 1) * max_inlist_value])
            op = " or {} in ".format(col_name)
        remaining_values = values[(len(values) // max_inlist_value) * max_inlist_value:]
        if remaining_values:
            in_condition = in_condition + op + _convert(remaining_values)
    else:
        in_condition = "{} in {}".format(col_name, _convert(values))

    return in_condition
