#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath view implementations for Web UI history
"""

from __future__ import absolute_import
import six
__revision__ = "$Id$"
from datetime import datetime
from collections import defaultdict
from webob.exc import HTTPNoContent


from cdb import auth
from cdb import sqlapi
from cdb import transactions
from cdb import ElementsError
from cdb.objects.core import Object
from cdb.objects.iconcache import IconCache
from cdb.constants import kAccessRead
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web.rest import get_collection_app
from cs.platform.web.uisupport import get_ui_link
from cs.platform.web.rest import support
from cs.web.components.ui_support import utils

from .model import HistoryCollection, HistoryItem
from .main import HistoryApp
from . import get_history_entries_per_class


@HistoryApp.json(model=HistoryCollection)
def _history_collection_get(model, request):
    collection_app = get_collection_app(request)

    def render_item(item, item_handle):
        cldef = item_handle.getClassDef()
        icon_id = cldef.getObjectIconId()
        rest_url = request.class_link(Object,
                                      {'rest_name': item.rest_name,
                                       'keys': item.rest_id},
                                      app=collection_app)

        return {
            'title': item_handle.getDesignation(),
            'frontend_url': get_ui_link(request, item_handle),
            'rest_url': six.moves.urllib.parse.unquote(rest_url),
            'icon_url': IconCache.getIcon(icon_id, accessor=item_handle) if icon_id else None,
            'timestamp': item.cdb_cdate.isoformat(),
            'classname': cldef.getClassname(),
            'rootclass': cldef.getRootClass().getClassname(),
            'ref_object_id': item.ref_object_id
        }

    def get_handles_from_restitems(for_items):
        cls2rest_ids = defaultdict(list)
        for item in for_items:
            cls2rest_ids[item.rest_name].append(item.rest_id)
        all_handles = {}
        for rest_name, rest_ids in six.iteritems(cls2rest_ids):
            if rest_name:
                try:
                    # For each REST name, collect objects with one call. Make sure to retrieve only
                    # those items that the user has access to.
                    objects = [obj for obj in support.get_objects_from_rest_name(rest_name,
                                                                                 rest_ids, False)
                               if obj and obj.CheckAccess(kAccessRead)]
                    all_handles[rest_name] = {
                        support.rest_key(obj): obj.ToObjectHandle() for obj in objects
                    }
                except ValueError:
                    # Fail safe if rest name of the class changed and the object is not
                    # constructable (maybe temporary, so don't delete it).
                    pass

        # Collect results in the order of the items given as input. For entries
        # where the target object could not be found (either deleted, or no rights)
        # a None value is returned.
        return [
            all_handles.get(item.rest_name, {}).get(item.rest_id, None) if item.rest_name else None
            for item in for_items]

    items = model.get_recent_items()
    if model.classname:
        handles = utils.get_handles_from_restitems_for_class(items, model.classname)
    else:
        handles = get_handles_from_restitems(items)
    if model.as_table is None:
        result = {'@id': request.link(model),
                  'history_items': [render_item(item, item_handle)
                                    for (item, item_handle) in six.moves.zip(items, handles)
                                    if item_handle is not None]
                  }
    else:
        result = {'@id': request.link(model)}
        valid_handles = [hndl for hndl in handles if hndl is not None]
        result.update(model.getTableResult(valid_handles).get_rest_data(request))
    return result


def update_history_collection(rest_name, rest_id, ref_object_id):
    with transactions.Transaction():
        # Try to update the timestamp for the record that should be added, to
        # move it to the top of the list. If this returns 0 (ie. no records
        # updated), the entry is not in the DB yet and must be created.
        stmt = ("%s SET cdb_cdate=%s"
                " WHERE cdb_cpersno='%s' AND rest_name='%s' AND rest_id='%s'"
                % (HistoryItem.GetTableName(),
                   sqlapi.SQLdbms_date(datetime.utcnow()),
                   sqlapi.quote(auth.persno),
                   sqlapi.quote(rest_name),
                   sqlapi.quote(rest_id)))
        updates = sqlapi.SQLupdate(stmt)
        if updates == 0:
            # Entry doesn't exist yet, so make one. Don't do any access checks here,
            # because that will be done anyway when retrieving the entries later on.
            HistoryItem.CreateNoResult(cdb_cpersno=auth.persno,
                                       rest_name=rest_name,
                                       rest_id=rest_id,
                                       cdb_cdate=datetime.utcnow(),
                                       ref_object_id=ref_object_id)
            # Check if there are more entries then the maximum number per user for
            # this REST name. If so, delete the oldest ones.
            existing = (HistoryItem
                        .KeywordQuery(cdb_cpersno=auth.persno, rest_name=rest_name)
                        .Query(condition="1=1",
                               order_by='cdb_cdate desc',
                               max_rows=get_history_entries_per_class() + 1)
                        .Execute())
            if len(existing) > get_history_entries_per_class():
                # There are too many! Get the timestamp of the last 'valid' entry
                # (which is the entry before the last), and delete everything that
                # is older.
                del_stmt = ("FROM %s"
                            " WHERE cdb_cpersno='%s' AND rest_name='%s' AND cdb_cdate < %s"
                            % (HistoryItem.GetTableName(),
                               sqlapi.quote(auth.persno),
                               sqlapi.quote(rest_name),
                               sqlapi.SQLdbms_date(existing[-2].cdb_cdate)))
                sqlapi.SQLdelete(del_stmt)


@HistoryApp.json(model=HistoryCollection, request_method='POST')
def _history_collection_post(model, request):
    """ Add a new history entry to the DB. Returns the new list of history
        entries for the current user.
    """
    json = request.json
    classname = json['classname']
    try:
        cdef = CDBClassDef(classname)
        if not cdef.isRecentObjectRelevant():
            return
    except ElementsError:
        pass
    rest_name = support.rest_name_for_class_name(classname)
    rest_id = json['rest_id']
    ref_object_id = json.get('ref_object_id')
    update_history_collection(rest_name, rest_id, ref_object_id)
    return HTTPNoContent()


@HistoryApp.json(model=HistoryCollection, request_method='DELETE')
def _history_collection_delete(model, request):
    """ Deletes the history of the current user.
    """
    del_stmt = ("FROM %s WHERE cdb_cpersno='%s'"
                % (HistoryItem.GetTableName(), sqlapi.quote(auth.persno)))
    sqlapi.SQLdelete(del_stmt)

    # Return the updated list
    return request.view(model)
