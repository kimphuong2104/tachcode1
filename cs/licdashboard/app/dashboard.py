# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
Backend functionality for the dashboard app.
"""

from __future__ import absolute_import

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

from collections import defaultdict
from copy import deepcopy

import isodate
import six
from webob.exc import HTTPForbidden

from cdb import sig, tools, typeconversion, util
from cdb.objects.org import Person
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.mom.operations import OperationInfo
from cdbwrapc import RestTabularData, get_help_url, get_licsystem_info
from cs.licdashboard.app.site_provider import (
    LicenseSiteProvider,
    OrganizationSiteProvider,
    SiteProviderBase,
)
from cs.platform.web import PlatformApp
from cs.platform.web.root import Internal, Root, get_internal
from cs.platform.web.uisupport import get_ui_link
from cs.platform.web.uisupport.resttable import RestTableWrapper
from cs.web.components.configurable_ui import (
    ConfigurableUIApp,
    ConfigurableUIModel,
    SinglePageModel,
)

DEFAULT_HEADERS = {
    "default-src": {"'self'", "'unsafe-inline'"},
    "img-src": {"'self'", "data:", "blob:"},
    "connect-src": {"'self'", "data:"},
    "worker-src": {"'self'", "data:", "blob:"},
    "media-src": {"'self'", "blob:"},
    "font-src": {"'self'", "data:", "blob:"},
}


class LicDashboardApp(ConfigurableUIApp):
    pass


@Root.mount(app=LicDashboardApp, path="licensing/license_dashboard")
def _mount_app():
    return LicDashboardApp()


class LicenseDashboardModel(SinglePageModel):
    page_name = "cs-licdashboard-dashboard"


@LicDashboardApp.path(path="", model=LicenseDashboardModel)
def _get_dashboard_model():
    return LicenseDashboardModel()


@LicDashboardApp.view(model=LicenseDashboardModel, name="document_title", internal=True)
def _document_title(self, request):
    return util.get_label("web.licdashboard.label")


class InternalLicDashboardApp(PlatformApp):
    pass


@Internal.mount(path="license_dashboard", app=InternalLicDashboardApp)
def _mount_internal_licdashboard_app():
    return InternalLicDashboardApp()


class LicenseInfoModel(object):
    def __init__(self):
        self.info = None
        self.persnos = None
        self.siteinfo = None

    def get_info(self):
        """
        Returns the data the frontend needs to display the license
        dashboard.
        """
        self._init_info()
        self._add_allocation_data()
        cdef = CDBClassDef("cdbfls_lusage")
        tdef = cdef.getProjection("licdashboard_tab", True)
        slots = self.info.get("slots", [])
        used = [slot for slot in slots if slot["allocated"] or slot["reserved"]]
        self._add_user_data(used, tdef)
        self._add_license_full_label(used)
        self._add_license_visible_flag()
        rowspersite = defaultdict(list)
        self._add_site_info(used, tdef, rowspersite)
        # Until now each adjustment has changed the original
        # We have to work on a copy now because the date is not
        # json-serializable
        tab_used = [self._adjust_datetime(slot) for slot in used]
        rt = RestTabularData(tab_used, tdef)
        self.info["slot_table"] = RestTableWrapper(rt).get_rest_data()
        self._inject_person_link(used)
        self.info["slot_table"]["rowspersite"] = rowspersite
        self.info["chart_info"] = self.info.get("licenses", {})
        self._init_siteinfo()
        sites = self.siteinfo.get_sites()
        self.info["user_info"] = self._get_user_data(used)
        sites = self._sort_sites(sites, self.info["user_info"])
        self.info["sites"] = [
            {"site_id": s["site_id"], "name": s["name"], "region": s["region"]}
            for s in sites
        ]
        if self.siteinfo.has_unknown_sites():
            self.info["sites"].append(self.siteinfo.get_unknown_site())
        return self.info

    def _init_siteinfo(self):
        if self.siteinfo is not None:
            return
        self._init_persnos()
        provider = util.PersonalSettings().getValueOrDefault(
            "licensedashboard.site_provider_class", "", "-"
        )
        if provider:
            cls = tools.getObjectByName(provider)
            self.siteinfo = cls(self.persnos)
        else:
            self.siteinfo = LicenseSiteProvider(self.persnos)
            if not self.siteinfo.is_available():
                self.siteinfo = OrganizationSiteProvider(self.persnos)

    def _init_info(self):
        """
        Initializes `self.info` if not yet done.
        """
        if self.info is None:
            self.info = get_licsystem_info()

    def _sort_sites(self, sites, userinfo):
        """
        Sorts the sites - we use the number of active accounts.
        """

        def _get_sortable_value(t):
            # To sort descending by the number of active users and
            # ascending by name we build this string
            return "%07d" % (9000000 - t[0]) + t[1]["name"]

        au = userinfo["active_accounts"]["sites"]
        # Build a list of (active_users, site) tuples
        sort_l = [(au.get(s["site_id"], 0), s) for s in sites]
        sort_l.sort(key=_get_sortable_value)
        return [s[1] for s in sort_l]

    def _adjust_datetime(self, slot):
        new_slot = dict(slot)
        # Adjust the date fields
        for attr in ("lbtime", "ldate", "release_allowed_date"):
            utc = slot.get(attr)
            if utc:
                new_slot[attr] = isodate.parse_datetime(utc)
        return new_slot

    def _inject_person_link(self, slot_data):
        """
        The column ``person.name`` should be a link. `slot_data` has
        to contain the data provided to the RestTableWrapper - the code
        will retrieve the ``personalnummer`` from that data.
        """
        st = self.info["slot_table"]
        pos = 0
        for col in st["tabledef"]["columns"]:
            if col["attribute"] == "person.name":
                col["isHTMLLink"] = True
                for row, slot in six.moves.zip(st["rows"], slot_data):
                    text = row["columns"][pos]
                    # We have selected all persons before - ByKeys
                    # Should not produce a select
                    p = Person.ByKeys(slot["uname"])
                    link = ""
                    if p:
                        link = get_ui_link(None, p)
                    row["columns"][pos] = {"link": {"to": link}, "text": text}
                break
            pos += 1

    def _add_license_visible_flag(self):
        """
        Set the visible flag depending on the settings. This allows the user
        to hide some licenses from the charts.
        """
        lic = self.info.get("licenses", {})
        for licname, info in lic.items():
            v = util.PersonalSettings().getValueOrDefault(
                "licensedashboard.license_visible", licname, "1"
            )
            info["visible_chart"] = typeconversion.to_bool(v)

    def _add_license_full_label(self, slots):
        """
        Add ``mno_label`` to all slots in `used`.
        """
        self._init_info()
        lstats = {
            "fl.session": "Floating Session",
            "user": "Named User",
            "float": "Floting Option",
        }

        lics = self.info.get("licenses", {})
        for slot in slots:
            linfo = lics.get(slot["mno"])
            label = linfo.get("label", slot["mno"]) if linfo else slot["mno"]
            slot["mno_label"] = (
                slot["mno"]
                + ": "
                + label
                + " / "
                + lstats.get(slot["lstat"], slot["lstat"])
            )

    def _add_allocation_data(self):
        """
        Add the license allocation information.
        """
        self._init_info()
        lics = self.info.get("licenses", {})
        for s in self.info.get("slots", {}):
            mno = s["mno"]
            kind = s["lstat"]
            d = lics.get(mno)
            if d is None:
                continue
            if kind not in d:
                d[kind] = {"allocated": 0, "reserved": 0, "free": 0, "sites": {}}
            allocated = s["allocated"]
            if allocated:
                d[kind]["allocated"] += 1
            reserved = s["reserved"]
            if reserved:
                d[kind]["reserved"] += 1
            if not (allocated or reserved):
                d[kind]["free"] += 1
            else:
                self._init_siteinfo()
                # Add site info
                site_id = self.siteinfo.get_site_id_by_person(s["uname"])
                if site_id not in d[kind]["sites"]:
                    d[kind]["sites"][site_id] = {"allocated": 0, "reserved": 0}

                if allocated:
                    d[kind]["sites"][site_id]["allocated"] += 1
                if reserved:
                    d[kind]["sites"][site_id]["reserved"] += 1

    def _get_user_data(self, slots):
        self._init_persnos()
        user_per_site = defaultdict(int)
        active_per_site = defaultdict(int)
        for person in self.persnos:
            site_id = self.siteinfo.get_site_id_by_person(person)
            user_per_site[site_id] += 1
        active_users = set([s["uname"] for s in slots if s["allocated"]])
        for person in active_users:
            site_id = self.siteinfo.get_site_id_by_person(person)
            active_per_site[site_id] += 1
        return {
            "active_accounts": {"count": self.active_accounts, "sites": user_per_site},
            "active_users": {"count": len(active_users), "sites": active_per_site},
        }

    @staticmethod
    def _get_columns(tdef, prefix):
        columns = []
        for col in tdef.getColumns():
            attr = col.getAttribute()
            if attr.startswith(prefix):
                columns.append(attr[len(prefix) :])
        return columns

    def _add_user_data(self, slots, tdef):
        if not slots:
            return
        columns = self._get_columns(tdef, "person.")
        if not columns:
            return
        if "personalnummer" not in columns:
            columns.append("personalnummer")

        person2slots = defaultdict(list)
        for nr, slot in enumerate(slots):
            if slot["uname"] not in ("", "nobody"):
                person2slots[slot["uname"]].append(nr)

        persnos = list(person2slots)
        persons = Person.Query(Person.personalnummer.one_of(*persnos), columns=columns)
        for person in persons:
            for slotnr in person2slots[person.personalnummer]:
                slot = slots[slotnr]
                for col in columns:
                    slot["person.%s" % col] = person[col]

    def _add_site_info(self, slots, tdef, rowspersite):
        if not slots:
            return
        columns = self._get_columns(tdef, "lic_site.")
        self._init_siteinfo()
        if columns and "site_id" not in columns:
            columns.append("site_id")
        for nr, slot in enumerate(slots):
            site = self.siteinfo.get_site_by_person(slot["uname"])
            if site:
                rowspersite[site["site_id"]].append(nr)
            else:
                self.unknown_sites = True
                rowspersite[SiteProviderBase.get_unknown_site_id()].append(nr)
            for col in columns:
                if site:
                    slot["lic_site.%s" % col] = site[col]
                else:
                    if col == "name":
                        slot[
                            "lic_site.%s" % col
                        ] = SiteProviderBase.get_unknown_site_name()
                    else:
                        slot["lic_site.%s" % col] = ""

    def _init_persnos(self):
        if self.persnos is not None:
            return
        try:
            from cdbwrapc import get_active_account_sqlcond

            cond = get_active_account_sqlcond(False)
        except ImportError:
            cond = "active_account = '1' AND (is_system_account = 0 OR is_system_account is NULL)"

        self.persnos = set(
            Person.Query(condition=cond, columns=["personalnummer"]).personalnummer
        )
        self.active_accounts = len(self.persnos)
        self._init_info()
        slots = self.info.get("slots", {})

        # We need all users that owns a slot and all active users
        persons = set(
            [slot["uname"] for slot in slots if slot["uname"] not in ("nobody", "")]
        )
        self.persnos.update(persons)


@InternalLicDashboardApp.path(model=LicenseInfoModel, path="licenseinfo")
def _get_license_info_model(self):
    return LicenseInfoModel()


@InternalLicDashboardApp.json(model=LicenseInfoModel, request_method="GET")
def _get_license_info(self, _request):
    return self.get_info()


def stringify_headers(headers):
    header_string = ""
    for key, value in six.iteritems(headers):
        header_string += " ".join([key] + list(value)) + "; "

    if six.PY3:
        return header_string[:-2]
    else:
        return header_string[:-2].encode("utf-8")


def unstringify_headers(headers_str):
    headers = {}
    if headers_str:
        headers_str = headers_str[:-1] if headers_str[-1] == ";" else headers_str
        for header_entry in headers_str.split(";"):
            header_entry_list = header_entry.strip().split(" ")
            key = header_entry_list[0]
            value = {e for e in header_entry_list[1:]}
            headers[key] = value
    return headers


def merge_headers(extra_headers):
    headers = deepcopy(DEFAULT_HEADERS)
    for extra_header in extra_headers:
        for key, value in six.iteritems(extra_header):
            if key not in headers:
                headers[key] = set()
            headers[key].update(value)

    return headers


def ensure_csp_header_set(request):
    extra_headers = {
        "default-src": {"'unsafe-eval'"},
    }

    # pylint: disable=unused-variable
    @request.after
    def add_csp_header(response):
        response.headers.add(
            "Content-Security-Policy" if six.PY3 else b"Content-Security-Policy",
            stringify_headers(
                merge_headers(
                    [
                        unstringify_headers(
                            response.headers.get("Content-Security-Policy", "")
                        )
                    ]
                    + [extra_headers]
                )
            ),
        )


@sig.connect(LicenseDashboardModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    # Check if the user is authorized
    if not OperationInfo("", "cs_license_dashboard"):
        raise HTTPForbidden(
            "You are not authorized to use the operation cs_license_dashboard"
        )

    # Unfortunately plotly uses eval
    ensure_csp_header_set(request)
    app = get_internal(request).child("license_dashboard")
    lsil = request.class_link(LicenseInfoModel, app=app)
    hurl = get_help_url("licdashboard_dashboard")
    app_setup.merge_in(["cs-licdashboard"], {"slot_info_link": lsil, "help_url": hurl})
