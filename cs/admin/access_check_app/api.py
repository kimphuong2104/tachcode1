# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
REST API for the access checker app
"""

from __future__ import absolute_import

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


from operator import itemgetter
from six.moves import zip
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal
from cs.platform.web.uisupport import get_ui_link
from cdb import auth
from cdb import misc
from cdb.objects import ClassRegistry
from cdb.platform.mom import CDBObjectHandle
from cdb.platform.mom.entities import CDBClassDef
from cdbwrapc import RestTabularData
from cdb.objects.core import object_from_handle
from cs.platform.web.uisupport.resttable import RestTableWrapper
from cdb.platform.acs import AccessControlDomain


class AccessCheckApi(JsonAPI):
    pass


@Internal.mount(app=AccessCheckApi, path="/cs-admin/access-check-api")
def _mount_app():
    return AccessCheckApi()


class AccessCheckApiModel(object):
    def __init__(self, ohandle_id, user):
        self.ohandle_id = ohandle_id
        self.user = user

    def _inject_link(self, rest_data, attr, objs):
        """
        The column `attr` should be a link. `rest_data` has
        to contain the data provided to the RestTableWrapper
        and injects a link to `objs`.
        """
        pos = 0
        for col in rest_data["tabledef"]["columns"]:
            if col["attribute"] == attr:
                col["isHTMLLink"] = True
                for row, obj in zip(rest_data["rows"], objs):
                    text = row["columns"][pos]
                    link = ""
                    if obj:
                        link = get_ui_link(None, obj)
                    row["columns"][pos] = {
                        "link": {"to": link},
                        "text": text}
                break
            pos += 1

    def _get_acdtable_data(self, acd_ids):
        domains = AccessControlDomain.KeywordQuery(acd_id=acd_ids).Execute()
        cdef = CDBClassDef("cdb_acd")
        tabdef = cdef.getProjection("access_check_acd_tab", True)
        # Think about - reduce statements, e.g. by using rest-ids and multi
        # objects methods
        acd_objs = [d.ToObjectHandle() for d in domains]
        rt = RestTabularData(acd_objs, tabdef)
        result = RestTableWrapper(rt).get_rest_data()
        self._inject_link(result, "acd_id", domains)
        return result

    def _get_roletable_data(self, ctx_info):
        role_relation = ctx_info["role_relation"]
        # There is a SL that does not provide role_relation_attr
        role_relation_attr = ctx_info.get("role_relation_attr",
                                          ctx_info.get("context_attr"))
        val = ctx_info.get("context_attr_val", "")
        roles = ctx_info.get("roles", [])
        cls = ClassRegistry().find(role_relation, generate=True)
        qparam = {"role_id": roles}
        if role_relation_attr and val:
            qparam[role_relation_attr] = val
        roles = cls.KeywordQuery(**qparam).Execute()
        cdef = CDBClassDef(role_relation)
        tabdef = cdef.getDefaultProjection()
        # Think about - reduce statements, e.g. by using rest-ids and multi
        # objects methods
        role_objs = [r.ToObjectHandle() for r in roles]
        rt = RestTabularData(role_objs, tabdef)
        result = RestTableWrapper(rt).get_rest_data()
        self._inject_link(result, "role_id", roles)
        return result

    def _get_ctx_info(self, ctx):
        return {
            "name": ctx["context_name"],
            "ctx_attr": ctx.get("context_attr", ""),
            "ctx_attr_val": ctx.get("context_attr_val", ""),
            "acd_table": self._get_acdtable_data(ctx.get("access_domains", [])),
            "role_table": self._get_roletable_data(ctx)
        }

    def get_check_results(self):
        oh = CDBObjectHandle(self.ohandle_id)
        acinfo = []
        ctx_info = []
        if self.user:
            ai = oh.getAccessInfo(self.user)
            acinfo = [{"access": key,
                       "allowed": allowed,
                       "errmsg": misc.unescape_string(msg)}
                      for key, (allowed, msg) in ai.items()]
            acinfo.sort(key=itemgetter("access"))
            asinfo = oh.getAccessSystemInfo(self.user)
            org_ctxs = asinfo["contexts"]
            ctx_info = [self._get_ctx_info(ctx) for ctx in org_ctxs.values()]
            # We want the global context to be the first
            # so sort by ctx_attr which is empty.
            ctx_info.sort(key=itemgetter("ctx_attr"))
        obj = object_from_handle(oh)
        result = {"access_info": acinfo,
                  "org_ctx_info": ctx_info,
                  "object_label": oh.getDesignation(),
                  "object_icon": obj.GetObjectIcon() if obj else ""}
        return result


@AccessCheckApi.path(model=AccessCheckApiModel, path="")
def _path(ohandle_id, user=None):
    return AccessCheckApiModel(ohandle_id, user)


@AccessCheckApi.json(model=AccessCheckApiModel)
def _json(model, request):
    return model.get_check_results()
