#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""

from __future__ import absolute_import

import html
import re

from lxml import etree
import six

from cdb import dotlib
from cdb import tools
from cdb import sqlapi
from cdb.objects import ByID
from cdb.objects import Rule
from cdb.platform.mom import entities
from cdb.platform.mom.entities import Entity
from cs.tools import semanticlinks as SemanticLinks
from cs.platform.web.rest.support import rest_name, rest_key

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
__linkgraph_object_rules__ = {}
# Exported objects
__all__ = []


def _check_obj_rule(obj, config):
    global __linkgraph_object_rules__
    obj_rule = None
    dict_key = (obj.GetClassname(), config.cdb_object_id)
    if dict_key in __linkgraph_object_rules__:
        obj_rule = __linkgraph_object_rules__[dict_key]
    if obj_rule is None:
        return True
    __linkgraph_object_rules__[dict_key] = obj_rule
    return obj_rule.match(obj)


def myfixtag(tag, namespaces):
    if isinstance(tag, etree.QName):
        tag = tag.text

    return tag[1:].split("}")[1], None

etree.fixtag = myfixtag


class DotGraph(dotlib.Graph):

    def __init__(self, name):
        self.f = ["digraph %s {" % name]

    def _write(self, line):
        self.f.append("%s\n" % line)

    def close(self):
        self._write("}")
        self.closed = True

    def setProp(self, name, val):
        self.write('%s="%s"' % (name, val))

    def getGraph(self):
        if self.closed:
            return "".join(self.f)
        return ""


def render_svg(svgstr, localres):
    rootmarked = False
    try:
        tree = etree.fromstring(svgstr)
    except Exception as e:
        return "XML parse error: %s" % e

    for e in tree.getiterator():

        if str(e.tag).endswith("svg"):
            e.attrib["id"] = "linkgraph"
            e.attrib["xmlns"] = "http://www.w3.org/2000/svg"
            e.attrib["{http://www.w3.org/2000/svg}xlink"] = "http://www.w3.org/1999/xlink"
            e.attrib["version"], e.attrib["width"], e.attrib["height"] = "1.1", "100%", "100%"
            del e.attrib["viewBox"]

        if str(e.tag).endswith("svg"):
            # Schattierungen
            myfilter = etree.Element('filter')
            myfilter.attrib["id"] = "dropshadow"
            myfilter.attrib["height"] = "130%"

            fegauss = etree.Element('feGaussianBlur')
            fegauss.attrib["stdDeviation"] = "2"
            fegauss.attrib["in"] = "SourceAlpha"

            myfilter.append(fegauss)

            feoffset = etree.Element("feOffset")
            feoffset.attrib["result"] = "offsetblur"
            feoffset.attrib["dx"] = "0"
            feoffset.attrib["dy"] = "0"

            femerge = etree.Element("feMerge")
            femergenode = etree.Element("feMergeNode")
            femergenode.attrib["in"] = "SourceGraphic"

            femergenode_empty = etree.Element("feMergeNode")
            femerge.append(femergenode_empty)
            femerge.append(femergenode)
            myfilter.append(femerge)
            myfilter.append(feoffset)

            e.append(myfilter)

            # Linear Gradient Filter
            filter2 = etree.Element('linearGradient')
            filter2.attrib["id"], filter2.attrib["x1"], filter2.attrib["y1"], filter2.attrib["x2"], \
                filter2.attrib["y2"] = "grad1", "0%", "0%", "100%", "0%"
            stop = etree.Element("stop")
            stop.attrib["offset"] = "0%"
            stop.attrib["style"] = "stop-color:rgb(224,238,238);stop-opacity:1"

            stop2 = etree.Element("stop")
            stop2.attrib["offset"] = "100%"
            stop2.attrib["style"] = "stop-color:rgb(92,172,238);stop-opacity:1"

            filter2.append(stop)
            filter2.append(stop2)

            e.append(filter2)

        # Text aus g-Umgebung entfernen
        if str(e.tag).endswith("g") and e.attrib.get("id") == "linkgraph_graph":
            e.attrib["id"] = "viewport"
            for c in e.getiterator():
                if c.tag.endswith("title"):
                    c.text = ""
                    break

        # Mouse Events mit Tooltips versehen und Icons hinzufuegen
        if str(e.tag).endswith("g") and e.attrib.get("class") == "node":
            try:
                obj = ByID(e.attrib.get('id'))
            except:
                obj = None

            if obj is None:
                cls = e.attrib.get('id').split('___')
                if len(cls) > 1 and cls[0] is not None and cls[1] is not None:
                    cls = cls[0]
                    clazz = Entity.KeywordQuery(classname=cls)
                    if len(clazz) and clazz[0] is not None and clazz.CheckAccess("read"):
                        clazz = clazz[0]
                        fpyname = clazz.getFqpyname()
                        if fpyname is not None:
                            VClass = tools.getObjectByName(fpyname)
                            args = e.attrib.get('id').split('___')[1:]
                            args.reverse()
                            obj = VClass.ByKeys(*args)
            if not obj.CheckAccess("read"):
                obj = None
            if obj is not None:
                e.attrib["url"] = "/api/v1/collection/%s/%s" % (rest_name(obj), rest_key(obj))
                e.attrib["cdbwin_url"] = obj.MakeURL(plain=1)
            pos = ""
            # Root hervorheben
            for c in e.getiterator():
                if c.tag.endswith("title"):
                    c.text = ""
                elif not rootmarked and c.tag.endswith("text"):
                    c.attrib["font-weight"] = "bold"

                elif not rootmarked and c.tag.endswith("polygon"):
                    points = c.attrib["points"].split(" ")[-3:-1]
                    ps1 = points[0].split(",")
                    pos += "%s,%s" % (str(float(ps1[0]) - 3), str(float(ps1[1]) + 0.5))
                    ps2 = points[1].split(",")
                    pos += " %s,%s" % (str(float(ps2[0]) - 3), str(float(ps2[1]) - 0.5))

                elif not rootmarked and c.tag.endswith("path"):
                    c.attrib["fill"] = "rgb(255,230,128)"

                if c.tag.endswith("polygon"):
                    c.attrib["style"] = c.attrib.get("style", "") + ";myfilter:url(#dropshadow)"

            if not rootmarked:
                new = etree.Element('polyline')
                new.attrib["points"] = pos
                new.attrib["stroke"] = "rgb(252,185,0)"
                new.attrib["stroke-width"] = "5"
                e.append(new)

            rootmarked = True

            if obj is not None:
                for c in e.getiterator():
                    if c.tag.endswith("text"):
                        x = c.attrib['x']
                        y = c.attrib['y']
                        break
                new = etree.Element('image')
                new.attrib["width"] = "16"
                new.attrib["height"] = "16"
                new.attrib["x"] = six.text_type(float(x) - 8)
                new.attrib["y"] = six.text_type(float(y) - 12)
                new.attrib["{http://www.w3.org/1999/xlink}href"] = obj.GetObjectIcon()

                e.append(new)

    return etree.tostring(tree)


def query_ORACLE(root_object_id, view, filter, maxradius):
    return """
           WITH hierarchical (cdb_object_id, subject_object_id, object_object_id, linktype_name,
             subject_object_classname, object_object_classname, link_weight, radius)
            AS (
                SELECT slv.cdb_object_id, slv.subject_object_id, slv.object_object_id, slv.linktype_name, slv.subject_object_classname,
                 slv.object_object_classname, slv.link_weight, 1 as radius
                FROM {view} slv
                WHERE subject_object_id = '{root_id}' {filter1}
                UNION ALL
                SELECT slu.cdb_object_id, slu.subject_object_id, slu.object_object_id, slu.linktype_name, slu.subject_object_classname,
                 slu.object_object_classname, slu.link_weight, radius+1 as radius
                FROM {view} slu
                JOIN hierarchical ON hierarchical.object_object_id = slu.subject_object_id AND hierarchical.radius < {radius} {filter2}
            )
            select distinct  cdb_object_id, subject_object_id, object_object_id, linktype_name, subject_object_classname,
             object_object_classname, link_weight from hierarchical group by cdb_object_id, subject_object_id,
             object_object_id, linktype_name, subject_object_classname, object_object_classname, link_weight, radius
           """.format(root_id=root_object_id, radius=maxradius, filter1=filter[0], filter2=filter[1], view=view)


def query_MSSQL(root_object_id, view, filter, maxradius):
    return """
            WITH hierarchical (cdb_object_id, subject_object_id, object_object_id, linktype_name, subject_object_classname,
             object_object_classname, link_weight, radius)
            AS (
                SELECT slv.cdb_object_id, slv.subject_object_id, slv.object_object_id, slv.linktype_name, slv.subject_object_classname,
                 slv.object_object_classname, slv.link_weight, 1 as radius
                FROM {view} slv
                WHERE subject_object_id = '{root_id}' {filter1}
                UNION ALL
                SELECT slu.cdb_object_id, slu.subject_object_id, slu.object_object_id, slu.linktype_name, slu.subject_object_classname,
                 slu.object_object_classname, slu.link_weight, h.radius+1 as radius
                FROM {view} slu
                JOIN hierarchical h ON h.object_object_id = slu.subject_object_id AND h.radius < {radius} {filter2}
            )
            select distinct cdb_object_id, subject_object_id, object_object_id, linktype_name, subject_object_classname,
             object_object_classname, link_weight from hierarchical
            """.format(root_id=root_object_id, radius=maxradius, filter1=filter[0], filter2=filter[1],
                       view=view)


def query_SQLITE(root_object_id, view, filter, maxradius):
    return """
            WITH RECURSIVE hierarchical (cdb_object_id, subject_object_id, object_object_id, linktype_name,
             subject_object_classname, object_object_classname, link_weight, radius)
            AS (
                SELECT slv.cdb_object_id, slv.subject_object_id, slv.object_object_id, slv.linktype_name, slv.subject_object_classname,
                 slv.object_object_classname, slv.link_weight, 1 as radius
                FROM {view} slv
                WHERE subject_object_id = '{root_id}' {filter1}
                UNION
                SELECT slu.cdb_object_id, slu.subject_object_id, slu.object_object_id, slu.linktype_name, slu.subject_object_classname,
                 slu.object_object_classname, slu.link_weight, radius+1 as radius
                FROM {view} slu
                JOIN hierarchical ON hierarchical.object_object_id = slu.subject_object_id AND radius < {radius} {filter2}
            )
            select distinct  cdb_object_id, subject_object_id, object_object_id, linktype_name, subject_object_classname,
             object_object_classname, link_weight from hierarchical group by subject_object_id, object_object_id,
              linktype_name
            """.format(root_id=root_object_id, radius=maxradius, filter1=filter[0], filter2=filter[1],
                       view=view)


def render_dot(config, root, radius=7, filtermap={}):

    def mkdotid(obj):
        dotid = ""
        if "cdb_object_id" in obj:
            dotid = obj.cdb_object_id.replace("-", "")
        else:
            dotid = obj.GetClassname() + "___" + "___".join(list(six.itervalues(obj.KeyDict())))
        return "G%s" % dotid

    def tohex(r, g, b):
        hexchars = "0123456789ABCDEF"
        return "#" + hexchars[int(r / 16)] + hexchars[int(r % 16)] + hexchars[int(g / 16)] + hexchars[int(g % 16)] + hexchars[int(b / 16)] + hexchars[int(b % 16)]

    color = tohex(255, 255, 255)

    graph = DotGraph("linkgraph")
    graph.setProp("overlap_scaling", "10.5")
    graph.setProp("splines", "true")
    graph.setProp("id", "linkgraph_graph")

    maxradius = radius
    visited = {}

    def getspecialprops(node):
        shape = "record"
        cls = entities.Entity.ByKeys(node.GetClassname())
        if cls is not None and cls.CheckAccess("read"):
            cls = cls.BaseClass
        fillcolor = color
        style = "filled"

        try:
            node_id = node.cdb_object_id
        except:
            node_id = node.GetClassname() + "___" + "___".join(list(six.itervalues(node.KeyDict())))

        return {"shape": shape,
                "id": node_id,
                'fontname': config.font_name if config.font_name else "Sans-Serif",
                'fontsize': "%dpx" % config.font_size if config.font_size else "9px",
                'style': style,
                "fillcolor": fillcolor}

    def wrap(line):
        i = 0
        newline = ""
        for c in line:
            if i > 9 and c == " ":
                newline += "\\n"
                i = 0
            newline += c
            i += 1

        return newline

    def writeEdge(node1, node2, link):
        label = html.escape(link.linktype_name)
        linkid = html.escape(link.cdb_object_id)
        links_match = False
        if node1.cdb_object_id == link.cdb_object_id:
            links_match = True
        elif node2.cdb_object_id == link.cdb_object_id:
            links_match = True
        graph.write(dotlib.Edge(mkdotid(node1) + "->" + mkdotid(node2),
                                weight=link.link_weight,
                                label=label,
                                pad="0.5",
                                id=linkid if not links_match else "",
                                fontname=config.font_name if config.font_name else "Sans-Serif",
                                fontsize="%dpx" % config.font_size if config.font_size else "9px",
                                arrowsize="0.5",
                                style="setlinewidth(0.5)"))

    def construct_filter(filtermap):
        filter1 = ""
        filter2 = ""
        if "links" in filtermap:
            filter1 += " and slv.linktype_name not in ('{links}')".format(
                links="','".join(filtermap["links"]).replace("%%20", " "))
            filter2 += " and slu.linktype_name not in ('{links}')".format(
                links="','".join(filtermap["links"]).replace("%%20", " "))
        if "obsolete" in filtermap:
            if int(filtermap["obsolete"]) == 1:
                filter1 += " and (slv.subject_cdb_obsolete in (0,1) and slv.object_cdb_obsolete in (0,1))"
                filter2 += " and (slu.subject_cdb_obsolete in (0,1) and slu.object_cdb_obsolete in (0,1))"
            else:
                filter1 += " and (slv.subject_cdb_obsolete = 0 and slv.object_cdb_obsolete = 0)"
                filter2 += " and (slu.subject_cdb_obsolete = 0 and slu.object_cdb_obsolete = 0)"
        if "classes" in filtermap:
            filter1 += " and slv.subject_object_classname not in ('{}')".format(
                "','".join(filtermap["classes"]).replace("%%20", " "))
            filter1 += " and slv.object_object_classname not in ('{}')".format(
                "','".join(filtermap["classes"]).replace("%%20", " "))
            filter2 += " and slu.subject_object_classname not in ('{}')".format(
                "','".join(filtermap["classes"]).replace("%%20", " "))
            filter2 += " and slu.object_object_classname not in ('{}')".format(
                "','".join(filtermap["classes"]).replace("%%20", " "))
        return filter1, filter2

    def walk(root, ignore_contains, view, filtermap):
        props = getspecialprops(root)
        graph.write(
            dotlib.Node(mkdotid(root), label="  &nbsp; &nbsp; &nbsp; &nbsp;|" + re.escape(wrap(root.GetDescription())).replace("\\\\n", "\\n"),
                        **props))
        visited[root.cdb_object_id] = root
        filter = construct_filter(filtermap)
        DBDependentQuery = {
            sqlapi.DBMS_ORACLE: query_ORACLE,
            sqlapi.DBMS_MSSQL: query_MSSQL,
            sqlapi.DBMS_SQLITE: query_SQLITE
        }
        DBType = sqlapi.SQLdbms()
        query = DBDependentQuery.get(DBType, query_SQLITE)(root.cdb_object_id,
                                                           'cdb_semantic_link_v' if ignore_contains else view,
                                                           filter,
                                                           maxradius)
        all_links = sqlapi.RecordSet2(sql=query)

        for link in all_links:
            allowed = True
            if link.subject_object_id not in visited:
                if not link.subject_object_id:
                    continue
                subject = ByID(link.subject_object_id)
                if subject.CheckAccess("read"):
                    props = getspecialprops(subject)
                    graph.write(dotlib.Node(mkdotid(subject), label="  &nbsp; &nbsp; &nbsp; &nbsp;|" + re.escape(
                        wrap(subject.GetDescription())).replace("\\\\n", "\\n"), **props))
                    visited[link.subject_object_id] = subject
                else:
                    allowed = False
            else:
                subject = visited[link.subject_object_id]
            if link.object_object_id not in visited:
                if not link.object_object_id:
                    continue
                obj = ByID(link.object_object_id)
                if obj.CheckAccess("read"):
                    props = getspecialprops(obj)
                    graph.write(dotlib.Node(mkdotid(obj), label="  &nbsp; &nbsp; &nbsp; &nbsp;|" + re.escape(
                        wrap(obj.GetDescription())).replace("\\\\n", "\\n"), **props))
                    visited[link.object_object_id] = obj
                else:
                    allowed = False
            else:
                obj = visited[link.object_object_id]

            if allowed:
                writeEdge(subject, obj, link)

    if config.view_name:
        walk(root, ignore_contains=config.ignore_contains, view=config.view_name, filtermap=filtermap)
    else:
        walk(root, ignore_contains=True, view="cdb_semantic_link_v", filtermap=filtermap)
    graph.close()

    return graph.getGraph()
