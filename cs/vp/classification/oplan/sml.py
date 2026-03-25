#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
SML Objektplan
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
import os
import mimetypes
import urllib.parse

from cdb import CADDOK
from cdb import cmsg
from cdb import elink
from cdb import misc
from cdb import sqlapi
from cdb import util
from cdb import rte
from cs.documents import Document
from cs.shared.elink_plugins.picture_uploader import PictureUploader

# Exported objects
__all__ = ['getPSetInfoURL',
           'ELINK_OPLAN_TEMPLATE_NAME',
           'Oplan']

NODES = {}
HIERARCHYCACHE = {}

_IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
}

ELINK_OPLAN_TEMPLATE_NAME = "sml"


class Node(object):
    IMG_PURPOSES = ['Bild in Maske/Objektplan', 'Bild im Objektplan']

    def __init__(self, record, key, parent_id):
        super(Node, self).__init__()
        self._children = None
        self._sml = None
        self._parent_id = parent_id
        self._key = key
        self._record = record
        NODES[(self.getkey(), self.getparentid())] = self

    def getparentid(self):
        return self._parent_id

    def getkey(self):
        return self._key

    def _get_children(self):
        if self._children is None:
            self._children = self.build_children()
        return self._children

    def has_image(self):
        pic = sqlapi.RecordSet2("cdbsml_cg_docs", "cgroup_id='%s'" % self.getkey())
        if not pic:
            pic = sqlapi.RecordSet2("cdbsml_pset_doc", "pset_id='%s'" % self.getkey())
            if not pic:
                return False
        try:
            doc = Document.ByKeys(pic[0].z_nummer, pic[0].z_index)
        except IndexError:
            doc = None
            return False
        if doc and doc.getPrimaryFiles() > 0:
            return True
        return False

    def __str__(self):
        data = ""
        for key, val in self.__dict__.items():
            data += "self.%s: %s\n" % (key, val)
        return data

    def labelcontent(self):
        labeltext = ""
        label = ""
        if (self.getkey(), self._parent_id) in HIERARCHYCACHE:
            label = HIERARCHYCACHE[self.getkey(), self._parent_id]["label_" + misc.getConfigValue("CADDOK_ISOLANG")]
        else:
            if self._parent_id not in ('preroot'):
                add_to_cache(self.getkey(), self._parent_id)
            showid = rte.environ.get("CADDOK_SML_SHOWID", "true")
            if showid.upper() == "TRUE":
                labeltext = (self.getkey())
            label = '%s %s' % (labeltext, self.short_label())
        return label

    def short_label(self):
        return "%s" % self._record["name_" + misc.getConfigValue("CADDOK_ISOLANG")]


class CgroupNode(Node):
    def __init__(self, record, key, parent_id):
        misc.cdblogv(misc.kLogMsg, 4, "CgroupNode(%s, %s (children of %s))" % (
            record, key, parent_id))
        super(CgroupNode, self).__init__(record, key, parent_id)

    def build_children(self):
        children = []
        key = self.getkey()
        for record in sqlapi.RecordSet2("cdbsml_cgroup",
                                        "cgroup_id IN(SELECT child_id FROM cdbsml_cg_hier where cgroup_id='%s')" % key,
                                        addtl="order by cgroup_id"):
            children.append(CgroupNode(record, record.cgroup_id, key))
        for record in sqlapi.RecordSet2("cdbsml_propset",
                                        "pset_id IN(SELECT pset_id FROM cdbsml_cg_pset where cgroup_id='%s')" % key,
                                        addtl="order by pset_id"):
            children.append(PsetNode(record, record.pset_id, key))
        return children

    def get_doc(self):
        purposes = ", ".join(["'%s'" % sqlapi.quote(purpose) for purpose in self.IMG_PURPOSES])
        pic = sqlapi.RecordSet2("cdbsml_cg_docs",
                                "cgroup_id='%s' and "
                                "purpose in (%s)" % (self.getkey(), purposes),
                                addtl="ORDER BY purpose")
        if not pic:
            misc.cdblogv(
                misc.kLogErr, 0,
                "Could not retrieve document for ID '%s'- " % self.getkey())
            doc = None
        else:
            try:
                doc = Document.ByKeys(pic[0].z_nummer, pic[0].z_index)
            except IndexError:
                doc = None
        return doc

    def sml(self):
        return 0


class PsetNode(Node):
    def __init__(self, record, key, parent_id):
        misc.cdblogv(misc.kLogMsg, 4, "PsetNode(%s, %s (children of %s))" % (
            record, key, parent_id))
        super(PsetNode, self).__init__(record, key, parent_id)

    def build_children(self):
        return []

    def sml(self):
        return 1

    def get_search_link(self):
        search_link = cmsg.Cdbcmsg("part", "CDB_Search", 1)
        search_link.add_item("sachgruppe", "", self.getkey())
        search_link.add_sys_item("predefinedsc", self.getkey())
        return search_link.eLink_url()

    def get_create_link(self):
        create_link = cmsg.Cdbcmsg("part", "CDB_Create", 1)
        create_link.add_item("sachgruppe", "", self.getkey())
        create_link.add_sys_item("predefinedsc", self.getkey())
        return create_link.eLink_url()

    def get_doc(self):
        purposes = ", ".join(["'%s'" % sqlapi.quote(purpose) for purpose in self.IMG_PURPOSES])
        pic = sqlapi.RecordSet2("cdbsml_pset_doc", "pset_id='%s' and "
                                "purpose in (%s)" % (self.getkey(), purposes),
                                addtl="ORDER BY purpose")
        if not pic:
            misc.cdblogv(
                misc.kLogErr, 0,
                "Could not retrieve document for ID '%s'- " % self.getkey())
            doc = None
        else:
            try:
                doc = Document.ByKeys(pic[0].z_nummer, pic[0].z_index)
            except IndexError:
                doc = None
        return doc


def add_to_cache(child_id, parent_id):
    misc.cdblogv(misc.kLogMsg, 8, "Add Child (%s), Parent (%s) to Hierarchy Cache" % (child_id, parent_id))
    rset = sqlapi.RecordSet2("cdbsml_cg_hier", "child_id = '%s' and cgroup_id = '%s'" % (child_id, parent_id))
    for rec in rset:
        parent_cg_id = rec.cgroup_id
        if parent_cg_id == '':
            parent_cg_id = 'root'
        HIERARCHYCACHE[rec.child_id, parent_cg_id] = rec


def _get_node(key, parent_id):
    if key == '':
        key = 'root'
    if parent_id == '':
        parent_id = 'preroot'
    klass = CgroupNode
    misc.cdblogv(misc.kLogMsg, 4, "_get_node('%s')" % key)
    if (key, parent_id) in NODES:
        return NODES[(key, parent_id)]
    rset = sqlapi.RecordSet2("cdbsml_cgroup", "cgroup_id='%s'" % key)
    if not rset:
        rset = sqlapi.RecordSet2("cdbsml_propset", "pset_id='%s'" % key)
        if rset:
            klass = PsetNode
        else:
            raise Exception("Unbekannte Sachgruppe %s" % key)
    return klass(rset[0], key, parent_id)


def getCGroupInfoURL(cgroup):
    """
    `cgroup` can be either the id itself as a string object, or a dictionary
    like object containing `cgroup_id`
    """
    cgroupid = cgroup if isinstance(cgroup, str) else cgroup["cgroup_id"]
    return "powerscript/cs.vp.classification.oplan/cgroup?cgroup_id=%s" % (
        urllib.parse.quote(cgroupid.encode("utf8")))


def getPSetInfoURL(pset, preview=False):
    """
    Retrieving an URL pointing to the subject characteristic page
    in the object plan. If you need the URL for a preview set
    `preview` to ``True``
    `pset` can be either the id itself as a string object, or a dictionary
    like object containing `pset_id`
    """
    psetid = pset if isinstance(pset, str) else pset["pset_id"]
    return "powerscript/cs.vp.classification.oplan/pset?pset_id=%s%s" % (
        urllib.parse.quote(psetid.encode("utf8")), "&preview_call=1" if preview else "")


class Oplan(elink.VirtualPathTemplate):
    __template__ = "sml.html"

    def render(self, context, *args, **varkw):
        path = self.get_path_segments(True)
        misc.cdblogv(misc.kLogMsg, 8, "(OPLAN) Init Path: %s" % path)
        misc.cdblogv(misc.kLogMsg, 8, "(OPLAN) Resource Name: %s" % self._name)
        base_uri = self.request.base_uri + self.request.script_name

        # if self.request.env['SCRIPT_URI'][-1] == "/":
        #     current_uri = self.request.env['SCRIPT_URI']
        # else:
        #     current_uri = self.request.env['SCRIPT_URI'] + "/"
        # current_uri = ""
        current_uri = base_uri + self.request.path
        if current_uri[-1] != "/":
            current_uri += "/"

        if not path:
            key, parent_id = 'root', 'preroot'
        elif len(path) == 1:
            key, parent_id = path[-1], 'preroot'
        else:
            key, parent_id = path[-1], path[-2]
        node = _get_node(key, parent_id)
        misc.cdblogv(misc.kLogMsg, 8, "(OPLAN) Node Class: %s" % node.__class__.__name__)

        childs = []
        for child in node._get_children():
            doc = child.get_doc()
            d = {}
            d['key'] = child.getkey()
            d['label'] = child.short_label()
            d['info_link'] = self.request.base_uri + getCGroupInfoURL(child.getkey())
            d['sml'] = child.sml()
            d['has_image'] = child.has_image()
            d['img_cdb_file_id'] = PictureUploader.get_preview_img(doc) if doc else None
            if child.__class__.__name__ == "PsetNode":
                d['info_link'] = (self.request.base_uri + getPSetInfoURL(child.getkey()))
                d['create_link'] = child.get_create_link()
                d['search_link'] = child.get_search_link()
            childs.append(d)

        content = {"path": self._get_breadcrumb(path, base_uri),
                   "current_uri": current_uri,
                   "base_uri": base_uri,
                   "resource_name": self._name,
                   "node": node,
                   "get_label": util.get_label,
                   "label": node.short_label(),
                   "children": childs}
        return content

    def _get_breadcrumb(self, path, base_uri):
        b = []
        base = base_uri + self._name + "/"
        for i in range(0, len(path)):
            if i == 0:
                key, parent_id = 'root', 'preroot'
            elif i == 1:
                key, parent_id = path[-1], 'preroot'
            else:
                key, parent_id = path[-1], path[-2]
            node = _get_node(path[i], path[i - 1])

            misc.cdblogv(misc.kLogMsg, 8, "(OPLAN) Node Class: %s" % str(node.__class__))
            misc.cdblogv(misc.kLogMsg, 8, "(OPLAN) key value: %s, %s" % (path[i], path[i - 1]))
            base = "%s%s/" % (base, urllib.parse.quote(node.getkey()))
            id = node.getkey().split("-")[-1]
            b.append({
                'label': node.labelcontent(),
                'link': base,
                'id': id
            })
        return b
