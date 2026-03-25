#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import hashlib
import json
import logging
from datetime import date, datetime

import isodate
from cdb import sqlapi, ue
from cdb.lru_cache import lru_cache
from cdb.objects import DataDictionary, Object
from cdb.objects.operations import operation, system_args
from cdb.platform.mom.entities import Entity
from cdb.platform.mom.fields import (
    DDCharField,
    DDDateField,
    DDFloatField,
    DDIntegerField,
    DDPredefinedField,
)

logger = logging.getLogger(__name__)

MSP_XML_SCHEMA = "http://schemas.microsoft.com/project"
MSP_XML_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Start of the manual part for DEFAULT_START_TIME
DEFAULT_START_TIME = "08:00"
# End of the manual part for DEFAULT_START_TIME

# Start of the manual part for DEFAULT_FINISH_TIME
DEFAULT_FINISH_TIME = "17:00"
# End of the manual part for DEFAULT_FINISH_TIME

# Start of the manual part for DEFAULT_DURATION
DEFAULT_DURATION = 8.0
# End of the manual part for DEFAULT_DURATION

REF_OBJECTS_SEPARATOR = ";;"
REF_OBJECT_TOKENS_SEPARATOR = "::"
REF_PROJECT_ID_FIELD = "project_name"
REF_CHECKLIST_ID_FIELD = "checklist_name"
REF_WORKFLOW_ID_FIELD = "title"

DD_CLSNAME_CACHE = {}
DD_FIELD_CACHE = {}


@lru_cache(maxsize=2, clear_after_ue=False)
def parse_default_time(time_str):
    """
    :param time: Time to add to the date in format "%H:%m".
        Defaults to midnight.
    :type hours: str

    :returns: Parsed hour and minute values
    :rtype: tuple(int, int)
    """
    hours, minutes = time_str.split(":")
    return int(hours), int(minutes)


def date2xml_date(date_value, time_str=None):
    """
    :param date_value: Date without time information
    :type date_value: date

    :param time_str: Time to add to the date in format "%H:%m".
        Defaults to midnight.
    :type hours: str

    :param hours: Minutes to use for return value. Defaults to 0.
    :type hours: int

    :returns: Date in isoformat as suitable for MSP XML
    :rtype: str
    """
    if time_str:
        hours, minutes = parse_default_time(time_str)
    else:
        hours, minutes = 0, 0
    dt = datetime(date_value.year, date_value.month, date_value.day, hours, minutes)
    return dt.strftime(MSP_XML_DATETIME_FORMAT)


def xml_date2date(isodate_value, ignore_time=False, morning=None, evening=None):
    """
    :param isodate_value: Date with time in ISO format as read from MSP XML
    :type isodate_value: str

    :param ignore_time: If time information is to be reset to 0 hours.
        Defaults to False.
    :type ignore_time: bool

    :param morning: Time in format "%H:%m" representing the start of a workday.
        Defaults to 8am.
    :type morning: str

    :param evening: Time in format "%H:%m" representing the end of a workday.
        Defaults to 8am.
    :type evening: str

    :returns: The date without time information and the early / late flag value:
        - 1 if the time was 8am
        - 0 if the time was 5pm
        - None if ``ignore_time`` is True
    :rtype: tuple(date, int)
    """
    if not isodate_value:
        return None, None

    parsed = isodate.parse_datetime(isodate_value)
    date_value = parsed.date()

    if ignore_time:
        return date_value, None

    morning_time = parse_default_time(morning or DEFAULT_START_TIME)

    if (parsed.hour, parsed.minute) == morning_time:
        return date_value, 1

    evening_time = parse_default_time(evening or DEFAULT_FINISH_TIME)

    if (parsed.hour, parsed.minute) == evening_time:
        return date_value, 0

    # rely on "check_start_value" and "check_end_value" to handle other times
    # (for other dates, we simply accept the None being mapped to DEFAULT_FINISH_TIME)
    return date_value, None


def get_base_classname_from_tablename(tbl_name):
    if tbl_name not in DD_CLSNAME_CACHE:
        sw_rec = DataDictionary().getRootClassRecord(tbl_name)
        DD_CLSNAME_CACHE[tbl_name] = sw_rec.classname
    return DD_CLSNAME_CACHE[tbl_name]


def get_classname(obj_or_cls_or_clsname):
    """Return classname of given class's base class"""
    if isinstance(obj_or_cls_or_clsname, Object):
        tbl_name = obj_or_cls_or_clsname.GetTableName()
        return get_base_classname_from_tablename(tbl_name)
    elif isinstance(obj_or_cls_or_clsname, type):
        tbl_name = getattr(obj_or_cls_or_clsname, "__maps_to__")
        return get_base_classname_from_tablename(tbl_name)
    return obj_or_cls_or_clsname


def get_icon_name(clsname):
    supported_icons = {
        "cdbpcs_project": "cdbpcs_project",
        "cdbpcs_task": "cdbpcs_task",
        "cdbpcs_taskrel": "cdbpcs_taskrelation",
        "cdbpcs_checklist": "cdbpcs_checklist",
        "cdbpcs_deliverable": "cdbpcs_deliverable",
        "cdbpcs_qualitygate": "cdbpcs_qualitygate",
        "cdbwf_process": "cdbwf_process_class",
    }
    return supported_icons.get(clsname, "")


def get_dd_field(classname, attr):
    """Returns (and caches) the data dictionary type of a PCS field."""
    cached_classname = DD_FIELD_CACHE.setdefault(classname, {})
    if "entity" not in cached_classname:
        cached_classname["entity"] = Entity.ByKeys(classname=classname)
    cached_attributes = cached_classname.setdefault("attributes", {})
    if attr not in cached_attributes:
        cached_attributes[attr] = cached_classname["entity"].getField(attr)
    return cached_attributes[attr]


def get_value_diff(pcs_object, pcs_attr, msp_value):
    pcs_value = getattr(pcs_object, pcs_attr, None)
    classname = get_classname(pcs_object)
    dd_field = _dd_field = get_dd_field(classname, pcs_attr)
    if isinstance(dd_field, DDPredefinedField):
        dd_field = dd_field.ReferencedField
    if isinstance(dd_field, DDCharField):
        if pcs_value is None:
            if msp_value == "":
                return None
            pcs_value = ""
    if isinstance(dd_field, (DDFloatField, DDIntegerField)):
        if pcs_value is None:
            if msp_value == 0:
                return None
            pcs_value = 0
    if pcs_value != msp_value:
        return {
            "label": _dd_field.getLabel(),
            "old_value": pcs_value,
            "new_value": msp_value,
        }
    else:
        return None


def to_db_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return f"'{value}'"
    if isinstance(value, (datetime, date)):
        return sqlapi.SQLdbms_date(value)
    return f"{value}"


def operation_ex(name, target, kwargs=None, called_from_officelink=False):
    """Set special operation context arguments"""
    kwargs = kwargs or {}
    sys_args = {"batch_mode": True}
    if called_from_officelink:
        sys_args["active_integration"] = "OfficeLink"
    return operation(name, target, system_args(**sys_args), **kwargs)


class MspToPcs:
    TaskLinkType = {
        # see constants cs.pcs.projects.tasks.kTaskDependency*
        0: "EE",  # pjFinishToFinish
        1: "EA",  # pjFinishToStart
        2: "AE",  # pjStartToFinish
        3: "AA",  # pjStartToStart
    }

    @staticmethod
    def convert_value(pcs_obj_or_cls, pcs_attr, msp_value):
        """Takes an MSP task value (string) and automatically typecasts it for the PCS field."""
        classname = get_classname(pcs_obj_or_cls)
        dd_field = get_dd_field(classname, pcs_attr)
        if isinstance(dd_field, DDPredefinedField):
            dd_field = dd_field.ReferencedField
        if isinstance(dd_field, DDCharField):
            return msp_value[0 : dd_field.data_length].rstrip()
        elif isinstance(dd_field, DDDateField):
            date_value, _ = xml_date2date(msp_value, ignore_time=True)
            return date_value
        elif isinstance(dd_field, DDFloatField):
            return float(msp_value) if msp_value else 0
        elif isinstance(dd_field, DDIntegerField):
            return int(msp_value) if msp_value else 0
        raise ue.Exception(
            f"The field type for '{classname}.{pcs_attr}' is not supported yet"
        )  # i18n

    @staticmethod
    def _do_check_date_values(msp_object):
        if (
            getattr(msp_object, "PercentComplete", 0) < 100
            and getattr(msp_object, "Active", 1)
            and (
                getattr(msp_object, "Manual", 1)
                or not getattr(msp_object, "Summary", 1)
            )
        ):
            return True
        return False

    @staticmethod
    def check_start_value(tmpl_val, msp_object):
        if tmpl_val:
            msp_value = f'{getattr(msp_object, "Start", "")}'
            if msp_value:
                msp_str = str(datetime.strptime(msp_value, MSP_XML_DATETIME_FORMAT))
                msp_str = msp_str.split()[1][:5]
                if msp_str != tmpl_val:
                    if MspToPcs._do_check_date_values(msp_object):
                        raise ue.Exception("cdbpcs_msp_start_config", msp_str, tmpl_val)

    @staticmethod
    def check_end_value(tmpl_val, msp_object):
        if tmpl_val:
            msp_value = f'{getattr(msp_object, "Finish", "")}'
            if msp_value:
                msp_str = str(datetime.strptime(msp_value, MSP_XML_DATETIME_FORMAT))
                msp_str = msp_str.split()[1][:5]
                if msp_str != tmpl_val:
                    if MspToPcs._do_check_date_values(msp_object):
                        raise ue.Exception("cdbpcs_msp_end_config", msp_str, tmpl_val)

    @staticmethod
    def check_milestone_value(tmp_vals, msp_object):
        tmp_vals.append("")
        if tmp_vals:
            msp_start_value = f'{getattr(msp_object, "Start", "")}'
            msp_end_value = f'{getattr(msp_object, "Finish", "")}'
            if msp_start_value or msp_end_value:
                msp_start_str = str(
                    datetime.strptime(msp_start_value, MSP_XML_DATETIME_FORMAT)
                )
                msp_start_str = msp_start_str.split()[1][:5]
                msp_end_str = str(
                    datetime.strptime(msp_end_value, MSP_XML_DATETIME_FORMAT)
                )
                msp_end_str = msp_end_str.split()[1][:5]
                if msp_start_str not in tmp_vals or msp_end_str not in tmp_vals:
                    raise ue.Exception(
                        "cdbpcs_msp_milestone_config",
                        msp_start_str,
                        msp_end_str,
                        tmp_vals[0],
                        tmp_vals[1],
                    )


class PcsToMsp:

    TaskLinkType = {
        "EE": 0,  # pjFinishToFinish
        "EA": 1,  # pjFinishToStart
        "AE": 2,  # pjStartToFinish
        "AA": 3,  # pjStartToStart
    }

    ExtendedAttributes = {
        "Number1": 188743767,
        "Number2": 188743768,
        "Number3": 188743769,
        "Number4": 188743770,
        "Number5": 188743771,
        "Number6": 188743982,
        "Number7": 188743983,
        "Number8": 188743984,
        "Number9": 188743985,
        "Number10": 188743986,
        "Number11": 188743987,
        "Number12": 188743988,
        "Number13": 188743989,
        "Number14": 188743990,
        "Number15": 188743991,
        "Number16": 188743992,
        "Number17": 188743993,
        "Number18": 188743994,
        "Number19": 188743995,
        "Number20": 188743996,
        "Text1": 188743731,
        "Text2": 188743734,
        "Text3": 188743737,
        "Text4": 188743740,
        "Text5": 188743743,
        "Text6": 188743746,
        "Text7": 188743747,
        "Text8": 188743748,
        "Text9": 188743749,
        "Text10": 188743750,
        "Text11": 188743997,
        "Text12": 188743998,
        "Text13": 188743999,
        "Text14": 188744000,
        "Text15": 188744001,
        "Text16": 188744002,
        "Text17": 188744003,
        "Text18": 188744004,
        "Text19": 188744005,
        "Text20": 188744006,
        "Text21": 188744007,
        "Text22": 188744008,
        "Text23": 188744009,
        "Text24": 188744010,
        "Text25": 188744011,
        "Text26": 188744012,
        "Text27": 188744013,
        "Text28": 188744014,
        "Text29": 188744015,
        "Text30": 188744016,
        "Start1": 188743732,
        "Start2": 188743735,
        "Start3": 188743738,
        "Start4": 188743741,
        "Start5": 188743744,
        "Start6": 188743962,
        "Start7": 188743964,
        "Start8": 188743966,
        "Start9": 188743968,
        "Start10": 188743970,
        "Finish1": 188743733,
        "Finish2": 188743736,
        "Finish3": 188743739,
        "Finish4": 188743742,
        "Finish5": 188743745,
        "Finish6": 188743963,
        "Finish7": 188743965,
        "Finish8": 188743967,
        "Finish9": 188743969,
        "Finish10": 188743971,
        "Duration1": 188743783,
        "Duration2": 188743784,
        "Duration3": 188743785,
        "Duration4": 188743955,
        "Duration5": 188743956,
        "Duration6": 188743957,
        "Duration7": 188743958,
        "Duration8": 188743959,
        "Duration9": 188743960,
        "Duration10": 188743961,
    }


class KeyObject:
    """
    Hashable dictionary like container class

    Contains a unique identifier of the type :py:func:`cdb.objects.Object.KeyDict` for each object
    """

    def __init__(self, *args, **kwargs):
        """
        If the first parameter is an instance of :py:class:`cdb.objects.Object`, the identifier
        will be determined using :py:func:`cdb.objects.Object.KeyDict`

        Otherwise, all given attribute-value pairs will be used.
        """
        if args and isinstance(args[0], Object):
            self._dict = args[0].KeyDict()
        else:
            self._dict = dict(*args, **kwargs)

    def __setitem__(self, key, value):
        self._dict[key] = value

    def __setattr__(self, name, value):
        if name == "_dict":
            object.__setattr__(self, name, value)
        else:
            self._dict[name] = value

    def __getitem__(self, key):
        try:
            return object.__getitem__(self, key)
        except AttributeError:
            return self._dict[key]

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return self._dict[name]

    def __delitem__(self, key):
        del self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        return iter(self._dict)

    def __repr__(self):
        return self._dict.__repr__()

    def __str__(self):
        return self._dict.__str__()

    def __hash__(self):
        _hash = json.dumps(self._dict, default=str, sort_keys=True)
        _hash = hashlib.sha1(_hash.encode("utf-8")).hexdigest()  # nosec
        _hash = int(_hash, 16) % (10**8)
        return _hash

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def update(self, *args, **kwargs):
        self._dict.update(dict(*args, **kwargs))

    def setdefault(self, key, default=None):
        return self._dict.setdefault(key, default)

    def keys(self):
        return list(self._dict)

    def items(self):
        return list(self._dict.items())

    def values(self):
        return list(self._dict.values())
