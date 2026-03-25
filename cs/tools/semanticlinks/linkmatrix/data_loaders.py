#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
from cdb import elink, util
from cdb.objects import ByID
from cdb.platform.mom.entities import Entity

from cs.tools import semanticlinks as SemanticLinks
from cs.tools.semanticlinks import LinkMatrixConfig


class RowDataLoader(elink.Template):
    __template__ = "cdb_link_matrix_row_data_loader.html"

    def render(self, context, *args, **varkw):
        writeable = False
        ref_parent = None
        relship = None
        rows = []
        links = {}
        config, parent, row_classname, col_classname = get_start_values(**varkw)

        visible_columns = [x if x else None for x in varkw.get('visible_columns').split(";")]
        row_objs = get_children(config, parent)
        relships = SemanticLinks.LinkMatrixRelship.Query("dsm_object_id='%s' and (column_classname='%s' and row_classname='%s')" % (config.cdb_object_id,
                                                                                                                                    col_classname,
                                                                                                                                    row_classname),
                                                         access="read")

        if len(relships):
            relship = relships[0]
        if relship:
            if relship.column_classname != relship.row_classname:
                writeable = True
            else:
                parents = [parent] + get_parents(parent, relship)
                for t_parent in parents:
                    if t_parent.cdb_object_id in visible_columns:
                        ref_parent = t_parent
                        break

        for r in row_objs:
            readonly = False
            if not hasattr(r, "parent_object_id"):
                try:
                    parent_object_id = parent.cdb_object_id
                except:
                    parent_object_id = ''
                setattr(r, "parent_object_id", parent_object_id)

            rows.append({'object': r, 'group': has_children(config, r)})
            links[r.cdb_object_id] = []
            for c in visible_columns:
                if c == r.cdb_object_id:
                    readonly = True
                if c:
                    links[r.cdb_object_id].append((c, get_link(r.cdb_object_id, c, readonly)))
                if not writeable and ref_parent is not None and c == ref_parent.cdb_object_id and not r.cdb_object_id in visible_columns:
                    readonly = True

        return {'rows': rows, 'links': links}


class ColDataLoader(elink.Template):
    __template__ = "cdb_link_matrix_col_data_loader.html"

    def render(self, context, *args, **varkw):
        writeable = False
        readonly = False
        ref_parent = None
        relship = None
        columns = []
        links = {}

        config, parent, row_classname, col_classname = get_start_values(**varkw)

        visible_rows = [x if x else None for x in varkw.get('visible_rows').split(";")]
        col_objs = get_children(config, parent)
        try:
            depth = int(varkw.get('depth'))
        except ValueError:
            depth = 0
        relships = SemanticLinks.LinkMatrixRelship.Query("dsm_object_id='%s' and (column_classname='%s' and row_classname='%s')" % (config.cdb_object_id,
                                                                                                                                    col_classname,
                                                                                                                                    row_classname),
                                                         access="read")

        if len(relships):
            relship = relships[0]
        if relship:
            if relship.column_classname != relship.row_classname:
                writeable = True
            else:
                parents = [parent] + get_parents(parent, relship)
                for t_parent in parents:
                    if t_parent.cdb_object_id in visible_rows:
                        ref_parent = t_parent
                        break

        for c in col_objs:
            if not hasattr(c, "parent_object_id"):
                try:
                    parent_object_id = parent.cdb_object_id
                except:
                    parent_object_id = ''
                setattr(c, "parent_object_id", parent_object_id)

            columns.append({'object': c, 'group': has_children(config, c)})

        for c in col_objs:
            if not writeable:
                readonly = True
            for r in visible_rows:
                if r not in links:
                    links[r] = {}
                links[r][c.cdb_object_id] = get_link(r, c.cdb_object_id, readonly)
                if r == c.cdb_object_id:
                    readonly = False
                if ref_parent is not None and r == ref_parent.cdb_object_id and not c.cdb_object_id in visible_rows:
                    readonly = False

        return {'columns': columns, 'depth': depth, 'links': links}


def get_link(row_object_id, col_object_id, readonly):
    links = SemanticLinks.SemanticLink.KeywordQuery(subject_object_id=row_object_id,
                                                    object_object_id=col_object_id)
    link = {'read_only': readonly,
            'object_object_id': col_object_id,
            'subject_object_id': row_object_id,
            'link_object_id': '',
            'link_type_object_id': '',
            'link_name': ''}
    if len(links):
        link.update({'link_object_id': links[0].cdb_object_id,
                'link_type_object_id': links[0].link_type_object_id,
                'link_name': links[0].linktype_name,
        })
        return link

    return link


def get_parents(obj, relship):

    return get_parent(obj, relship, [])


def get_parent(obj, relship, lst):
    if relship.column_classname == obj.GetClassname():
        parent = getattr(obj, relship.column_structure_rolename)
    elif relship.row_classname == obj.GetClassname():
        parent = getattr(obj, relship.row_structure_rolename)

    if parent and not isinstance(parent, list) and parent.CheckAccess("read"):
        return lst + [parent] + get_parent(parent, relship, lst)
    elif parent and isinstance(parent, list):
        parent_list = []
        for p in parent:
            if p.CheckAccess("read"):
                parent_list += [p] + get_parent(p, relship, lst)
        return lst + parent_list

    return []


def has_children(config, obj, get=False):
    relships = SemanticLinks.LinkMatrixRelship.Query("dsm_object_id='%s' and (column_classname='%s' or row_classname='%s')" % (config.cdb_object_id, obj.GetClassname(), obj.GetClassname()), access="read")
    if len(relships):
        relship = relships[0]

        if relship.column_classname == obj.GetClassname():
            rolename = relship.column_structure_rolename_down

        elif relship.row_classname == obj.GetClassname():
            rolename = relship.row_structure_rolename_down

        if get:
            if hasattr(obj, rolename):
                return getattr(obj, rolename)
            return []
        else:
            if hasattr(obj, rolename):
                return len(getattr(obj, rolename))
            return 0


def get_children(config, obj):
    return has_children(config, obj, True)


def get_start_values(**varkw):
        config_object_id = varkw.get("config_object_id")
        if not config_object_id:
            raise util.ErrorMessage("cdb_link_matrix_no_config")
        config = LinkMatrixConfig.ByKeys(config_object_id)
        if config is None or not config.CheckAccess("read"):
            raise util.ErrorMessage("cdb_link_matrix_no_config")

        parent_object_id = varkw.get("parent_object_id")
        if not parent_object_id:
            raise util.ErrorMessage("cdb_link_matrix_no_parent")
        parent = ByID(parent_object_id)
        if parent is None or not parent.CheckAccess("read"):
            raise util.ErrorMessage("cdb_link_matrix_no_parent")

        row_classname = varkw.get("rel_row_cls_name")
        if not row_classname or Entity.ByKeys(row_classname) is None or \
        not Entity.ByKeys(row_classname).CheckAccess("read"):
            raise util.ErrorMessage("cdb_link_matrix_no_class")

        col_classname = varkw.get("rel_col_cls_name")
        if not col_classname or Entity.ByKeys(col_classname) is None or \
        not Entity.ByKeys(col_classname).CheckAccess("read"):
            raise util.ErrorMessage("cdb_link_matrix_no_class")

        return (config, parent, row_classname, col_classname)
