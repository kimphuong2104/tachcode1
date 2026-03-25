#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module for SemanticLink management

"""

from __future__ import absolute_import

import six

from cdb import elink, sqlapi
from cdb import tools, util
from cdb import ue
from cdb.objects import ByID
from cdb.objects.PersonalObjectSettings import PersonalObjectSetting
from cdb.platform import mom
from cdb.platform.mom.entities import Entity
from cdb.platform.mom.relships import Relship
from cs.tools import semanticlinks as SemanticLinks
from cs.tools.semanticlinks import LinkMatrixConfig
from cs.tools.semanticlinks import LinkMatrixRelship
from cs.tools.semanticlinks.linkmatrix import data_loaders
import math
from cdb.objects.operations import operation
from cdb.constants import kOperationNew  # @UnresolvedImport
from cdb.constants import kOperationDelete  # @UnresolvedImport
from cdb.constants import kOperationModify  # @UnresolvedImport


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@elink.using_template_engine("chameleon")
class LinkmatrixApp(elink.Application):

    def setup(self):
        self.add("", LinkmatrixPage())
        self.add("row_data_loader", data_loaders.RowDataLoader())
        self.add("column_data_loader", data_loaders.ColDataLoader())
        self.add("search", LinkmatrixSearchPage())
        self.addJSON(self.save)
        self.addJSON(self.save_hook)
        self.addJSON(self.get_types)
        self.addJSON(self.fetchall)
        self.addJSON(self.determine_parent_tree)

    def save_hook(self, context_object_id):
        if not context_object_id:
            raise ue.Exception("cdb_link_matrix_no_context")
        context = ByID(context_object_id)
        if context is not None and context.CheckAccess("read") and \
        hasattr(context, 'matrix_save_post_hook'):
            context.matrix_save_post_hook()

    def fetchall(self, **kwargs):
        result = {}
        for link in list(six.itervalues(kwargs)):
            if len(link) == 2:
                row_object_id = link[0]
                column_object_id = link[1]
                if row_object_id and column_object_id:
                    lks = SemanticLinks.SemanticLink.KeywordQuery(subject_object_id=row_object_id, object_object_id=column_object_id)
                    if len(lks):
                        if row_object_id not in list(result):
                            result[row_object_id] = {}
                        result[row_object_id][column_object_id] = (lks[0].link_type_object_id, lks[0].linktype_name)
                    else:
                        if row_object_id not in list(result):
                            result[row_object_id] = {}
                        result[row_object_id][column_object_id] = ("", "")
        return {'result': result}

    def determine_parent_tree(self, cdb_object_id, config_object_id, row_classname, col_classname, classname):
        parent_path = []
        tmp_object = None
        if config_object_id is not None:
            config = LinkMatrixConfig.ByKeys(config_object_id)
        else:
            raise ue.Exception("cdb_link_matrix_no_config")
        if row_classname is not None and col_classname is not None and config.CheckAccess("read"):
            relship = LinkMatrixRelship.ByKeys(dsm_object_id=config.cdb_object_id,
                                               row_classname=row_classname,
                                               column_classname=col_classname)
        if relship is not None and relship.CheckAccess("read"):
            up_reference = None
            if classname is not None:
                if classname == row_classname:
                    up_reference = relship.row_structure_rolename
                else:
                    up_reference = relship.column_structure_rolename
            if cdb_object_id is not None:
                tmp_object = ByID(cdb_object_id)
            if tmp_object is not None and tmp_object.CheckAccess("read"):
                while getattr(tmp_object, up_reference) is not None and\
                getattr(tmp_object, up_reference).CheckAccess('read'):
                    tmp_object = getattr(tmp_object, up_reference)
                    parent_path.append(tmp_object.cdb_object_id)
                parent_path.reverse()
        return parent_path

    def search_enterprise(self, querystr, entity, context_object_id, pageno=0):
        from cdb.storage.index import standard_query
        from cdb.storage.index import queries
        result_objects = []
        result_total_count = 0
        if querystr != "" and entity is not None and context_object_id is not None:
            query = standard_query.StandardQuery("%s AND %s" % (querystr, context_object_id))
            query.set_owner_type(entity.__classname__)
            queryhelper = queries.ESQueryHelper(query)
            page = queryhelper.get_page(pageno)
            result_objects = [entity.ByKeys(hit.get_object_id()) for hit in page]
            result_objects = [x for x in result_objects if x.CheckAccess('read')]
            result_total_count = queryhelper.curr_total
        return result_objects, result_total_count

    def filter_search_results(self, search_result, context_object_id):
        filtered_result = []
        if search_result is not None:
            for hit in search_result:
                if hasattr(hit, "cdb_baseline") and hit.is_baseline == 1:
                    continue
                if hasattr(hit, "context_object_id") and context_object_id is not None:
                    if hit.context_object_id == context_object_id:
                        filtered_result.append(hit)
                else:
                    filtered_result.append(hit)
        return filtered_result

    def search(self, querystr, classname, context_object_id, config_object_id, row_classname, column_classname, pageno):
        from cdb.platform.mom.entities import Entity
        if config_object_id is None:
            raise ue.Exception("cdb_link_matrix_no_config")
        if classname is not None and querystr is not None and \
        context_object_id is not None and row_classname is not None and \
        column_classname is not None:
            search_class = Entity.ByKeys(classname)
            if not search_class or not search_class.CheckAccess("read"):
                raise ue.Exception("cdb_link_matrix_no_class")
            if not search_class.fqpyname:
                raise ue.Exception("cdb_link_matrix_no_fqpyname")
            search_entity = tools.getObjectByName(search_class.fqpyname)
            try:
                page = int(pageno)
            except ValueError:
                page = 0
            search_result, curr_total = self.search_enterprise(querystr, search_entity, context_object_id, page)
            filtered_result = self.filter_search_results(search_result, context_object_id)
            return filtered_result, curr_total
        return [], 0

    def get_types(self, config_object_id, subject_type_classname=None, object_type_classname=None, result_type="0"):
        config = LinkMatrixConfig.ByKeys(config_object_id)
        result_relships = []
        cls_attr = None
        if config is not None and config.CheckAccess("read"):
            if object_type_classname is not None:
                result_relships = LinkMatrixRelship.KeywordQuery(column_classname=object_type_classname,
                                                                    dsm_object_id=config.cdb_object_id)
                cls_attr = "row_classname"
            elif subject_type_classname is not None:
                result_relships = LinkMatrixRelship.KeywordQuery(row_classname=subject_type_classname,
                                                                    dsm_object_id=config.cdb_object_id)
                cls_attr = "column_classname"
            else:
                result_relships = LinkMatrixRelship.KeywordQuery(dsm_object_id=config.cdb_object_id)
                cls_attr = "row_classname" if result_type == "0" else "column_classname"
            result_relships = [x for x in set(result_relships) if x.CheckAccess('read')]
            lookup_dict = {}
            for relship in result_relships:
                cls_name = getattr(relship, cls_attr)
                cls_entity = Entity.ByKeys(classname=cls_name)
                if cls_entity.CheckAccess('read'):
                    lookup_dict[cls_entity.Label[""]] = cls_name
            sorted_keys = list(lookup_dict)
            sorted_keys.sort()
            result_types = []
            for label in sorted_keys:
                result_types.append({"cls_name": lookup_dict[label],
                                      "label": label})
            return result_types

    def _create_sem_link(self, row_object_id, column_object_id, link_type_object_id):
        operation(kOperationNew,
                  SemanticLinks.SemanticLink,
                  subject_object_id=row_object_id,
                  object_object_id=column_object_id,
                  link_weight=1,
                  link_type_object_id=link_type_object_id)
        link = SemanticLinks.SemanticLink.ByKeys(subject_object_id=row_object_id, object_object_id=column_object_id)
        link_object_id = link.cdb_object_id if link else ""
        return link_object_id

    def _modify_sem_link(self, link, link_type_object_id):
        operation(kOperationModify,
                  link,
                  link_type_object_id=link_type_object_id)

    def _delete_sem_link(self, link):
        operation(kOperationDelete,
                  link)

    def save(self, link_object_id, row_object_id, column_object_id, link_type_object_id):
        if link_object_id and link_type_object_id:
            link = SemanticLinks.SemanticLink.ByKeys(link_object_id)
            if link is not None:
                self._modify_sem_link(link, link_type_object_id)
            elif link_type_object_id:
                link_object_id = self._create_sem_link(row_object_id,
                                                       column_object_id,
                                                       link_type_object_id)
        else:
            if link_type_object_id:
                link_object_id = self._create_sem_link(row_object_id,
                                                       column_object_id,
                                                       link_type_object_id)
            else:
                link = SemanticLinks.SemanticLink.ByKeys(subject_object_id=row_object_id,
                                                         object_object_id=column_object_id)
                if link is not None:
                    self._delete_sem_link(link)

        return {'success': 'ok', 'link_object_id': link_object_id}


class LinkmatrixSearchPage(elink.Template):

    __template__ = "search.html"

    def render(self, context, querystr, classname, context_object_id, config_object_id, row_classname, column_classname, pageno):
        try:
            if int(pageno) > 0:
                pageno = int(pageno) - 1
            else:
                pageno = int(pageno)
        except ValueError:
            pageno = 0
        search_results, curr_total = self.application.search(querystr, classname, context_object_id, config_object_id, row_classname, column_classname, pageno)
        search_results.sort(key=lambda x: x.GetDescription())
        total_pages = int(math.ceil(curr_total / 10.0))
        return {"search_results": search_results,
                "paginator": (pageno + 1, total_pages)}


class LinkmatrixPage(elink.Template):

    __template__ = "index.html"

    def getStartobjects(self, context_object_id, config, rel_col_cls_name=None, rel_row_cls_name=None, relation_id=None):
        row_start_objects = []
        column_start_objects = []
        link_types = []
        subject_options = []
        object_options = []
        config_object_id = config.cdb_object_id
        if not relation_id:
            if rel_col_cls_name is not None and rel_row_cls_name is not None:
                relships = SemanticLinks.LinkMatrixRelship.KeywordQuery(dsm_object_id=config_object_id,
                                                                        row_classname=rel_row_cls_name,
                                                                        column_classname=rel_col_cls_name)
            else:
                relship_object_id = PersonalObjectSetting.getValue(config_object_id,
                                                                   "elink.apps.base.linkmatrix.start_relation")
                if relship_object_id is not None:
                    relships = SemanticLinks.LinkMatrixRelship.KeywordQuery(dsm_object_id=config_object_id,
                                                                            cdb_object_id=relship_object_id)
                else:
                    relships = SemanticLinks.LinkMatrixRelship.KeywordQuery(dsm_object_id=config_object_id)
            if len(relships):
                relship = relships[0]
            else:
                raise util.ErrorMessage("cdb_link_matrix_no_relship")
        else:
            relship = LinkMatrixRelship.ByKeys(relation_id)
        if relship is None or not relship.CheckAccess("read"):
            raise ue.Exception("cdb_link_matrix_no_relship")
        context_obj = ByID(context_object_id)
        if context_obj is None or not context_obj.CheckAccess("read"):
            raise ue.Exception("cdb_link_matrix_no_context")
        PersonalObjectSetting.setValue(config_object_id,
                                       "elink.apps.base.linkmatrix.start_relation",
                                       value=relship.cdb_object_id)
        if not hasattr(context_obj, relship.row_roots_rolename):
            raise ue.Exception("cdb_link_matrix_cfg_error", relship.row_roots_rolename, config.GetDescription())
        if not hasattr(context_obj, relship.column_roots_rolename):
            raise ue.Exception("cdb_link_matrix_cfg_error", relship.column_roots_rolename, config.GetDescription())
        row_start_objects = [x for x in getattr(context_obj, relship.row_roots_rolename) if x.CheckAccess("read")]
        column_start_objects = [x for x in getattr(context_obj, relship.column_roots_rolename) if x.CheckAccess("read")]

        link_types = SemanticLinks.SemanticLinkType.getValidLinkTypes(subject_object_classname=relship.row_classname,
                                                                      object_object_classname=relship.column_classname)
        subject_options = self.application.get_types(config_object_id, object_type_classname=relship.column_classname)
        object_options = self.application.get_types(config_object_id, subject_type_classname=relship.row_classname)

        return (row_start_objects, column_start_objects, link_types, relship, subject_options, object_options)

    def render(self, context, *args, **varkw):
        """
        varkw:
        - column_start: start object for the column tree (if not set, the toplevel object from context is used)
        - row_start: start object for the row tree (if not set, the toplevel object from context is used)
        - config_object_id: object-id of the dsm-configuration
        """
        from cdb.platform.mom import entities
        links = {}
        rows = []
        columns = []
        row_has_ctx = "none"
        column_has_ctx = "none"
        self.content_type("text/html")

        config_object_id = varkw.get('config_object_id')
        context_object_id = varkw.get('context_object_id')
        relship_object_id = varkw.get('config_relship_id')
        rel_col_cls_name = varkw.get('rel_col_cls_name')
        rel_row_cls_name = varkw.get('rel_row_cls_name')

        if not config_object_id:
            raise util.ErrorMessage("cdb_link_matrix_no_config")
        if not context_object_id:
            raise ue.Exception("cdb_link_matrix_no_context")

        config = LinkMatrixConfig.ByKeys(config_object_id)
        if config is None or not config.CheckAccess("read"):
            raise util.ErrorMessage("cdb_link_matrix_no_config")
        row_start_objects, column_start_objects, link_types, choosen_relship, subject_options, object_options = self.getStartobjects(context_object_id,
                                                                                                                                     config,
                                                                                                                                     rel_col_cls_name,
                                                                                                                                     rel_row_cls_name,
                                                                                                                                     relship_object_id)
        column_cdef = entities.CDBClassDef(choosen_relship.column_classname)
        if column_cdef:
            attrdef = column_cdef.getAttributeDefinition("context_object_id")
            if attrdef:
                column_has_ctx = "block"

        row_cdef = entities.CDBClassDef(choosen_relship.row_classname)
        if row_cdef:
            attrdef = row_cdef.getAttributeDefinition("context_object_id")
            if attrdef:
                row_has_ctx = "block"

        for row in row_start_objects:
            links[row.cdb_object_id] = {}
            readonly = False
            for col in column_start_objects:
                if row.cdb_object_id == col.cdb_object_id:
                    readonly = True
                links[row.cdb_object_id][col.cdb_object_id] = data_loaders.get_link(row.cdb_object_id,
                                                                                    col.cdb_object_id,
                                                                                    readonly)
        for s in row_start_objects:
            rows.append({'object': s, 'group': data_loaders.has_children(config, s)})

        for s in column_start_objects:
            columns.append({'object': s, 'group': data_loaders.has_children(config, s)})

        app_id = "cs.tools.semanticlinks.linkmatrix"
        from cs.shared.elink_plugins.collapsible_blocks import get_blocks_expand
        expanded = get_blocks_expand(app_id)
        if expanded is None or expanded == []:
            expanded = False
        else:
            expanded = True

        page_title = '%s - %s' % (util.get_label('cdb_link_matrix'), ByID(context_object_id).GetDescription())

        return {"row_start_objects": rows,
                "column_start_objects": columns,
                'config_object_id': config_object_id,
                "link_types": link_types,
                "links": links,
                "choosen_relship": choosen_relship,
                "context_object_id": context_object_id,
                "page_title_brand": page_title,
                "subject_options": subject_options,
                "object_options": object_options,
                "expanded": expanded,
                "column_has_ctx": column_has_ctx,
                "row_has_ctx": row_has_ctx}


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = LinkmatrixApp("Link Matrix")
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)
