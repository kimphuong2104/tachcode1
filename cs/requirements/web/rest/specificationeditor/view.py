# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import webob
from webob.exc import HTTPBadRequest, HTTPForbidden

from cdb import sqlapi
from cdb.objects.expressions import Expression, Literal
from cs.platform.web import root
from cs.platform.web.rest import support
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.requirements import RQMSpecification, RQMSpecObject, rqm_utils
from cs.requirements.richtext import RichTextModifications

from .main import SpecificationEditorAPI
from .model import SpecificationEditorAPIModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def get_context_ids(all_ids, cdb_object_id, before, after):
    """ get the ids for the sliding window all_ids is expected
     to be non empty and have to contain at least cdb_object_id
     otherwise a ValueError is raised """
    idx = all_ids.index(cdb_object_id)
    before_ids = []
    after_ids = []

    if idx > 0 and idx >= before:
        lower_bound = idx - before
        before_ids = all_ids[lower_bound:idx]
    elif idx > 0 and idx < before:
        before_ids = all_ids[:idx]
    if idx >= 0 and (idx + after + 1) <= len(all_ids):
        upper_bound = idx + after + 1
        after_ids = all_ids[idx + 1: upper_bound]
    elif idx >= 0 and (idx + after + 1) > len(all_ids):
        after_ids = all_ids[idx + 1:]
    context_ids = before_ids + [cdb_object_id] + after_ids
    return context_ids


def apply_bounds(all_ids, response):
    if len(all_ids) > 0:
        response.update({
            "first_id": all_ids[0],
            "last_id": all_ids[-1],
        })
    return response


@SpecificationEditorAPI.json(model=SpecificationEditorAPIModel, request_method="GET")
def default_view_by_id(model, request):
    # sqlapi.SQLselect('1 -- default_view_by_id start')
    try:
        initial = int(request.GET.get('initial', '0'))
        before = int(request.GET.get('before', '1'))
        after = int(request.GET.get('after', '1'))
    except ValueError:
        raise HTTPBadRequest()

    if before < 0 or after < 0:
        raise HTTPBadRequest()

    if initial:
        spec = RQMSpecification.ByKeys(cdb_object_id=model.cdb_object_id)
        if len(spec.Requirements):
            req = spec.Requirements.Query("1=1", order_by="sortorder")[0]
        else:
            return {
                "objects": [],
                "result_complete": True
            }
    else:
        req = RQMSpecObject.ByKeys(cdb_object_id=model.cdb_object_id)

    if req and req.CheckAccess('read'):
        # all_ids = req.Specification.Requirements.Query("1=1", order_by="sortorder").cdb_object_id
        spec_condition = Expression('=', RQMSpecObject.specification_object_id, Literal(RQMSpecObject.specification_object_id, req.specification_object_id)).to_string()
        all_ids = [
            x.cdb_object_id for x in sqlapi.RecordSet2(
                table=RQMSpecObject.__maps_to__,
                condition=spec_condition,
                columns=['cdb_object_id'],
                addtl="ORDER BY sortorder"
            )
        ]
        context_ids = get_context_ids(
            all_ids=all_ids,
            cdb_object_id=req.cdb_object_id,
            before=before,
            after=after,
        )
        collection_app = root.get_v1(request).child("collection")
        obj_rest_name = support.rest_name(req)
        if obj_rest_name is None:
            raise webob.exc.HTTPNotFound
        objects = []
        variable_reference_ids = context_ids
        file_cache = rqm_utils.get_file_obj_cache_by_object_id(variable_reference_ids)
        variable_values_by_id = RichTextModifications.get_variable_values_by_id(
            variable_reference_ids, req.specification_object_id
        )

        for r in req.Specification.Requirements.KeywordQuery(cdb_object_id=context_ids, order_by="sortorder").Query("1=1", access='read'):
            obj = request.view(
                r,
                app=collection_app.child(GenericApp, rest_name=obj_rest_name)
            )
            modifications = RichTextModifications.get_variable_and_file_link_modified_attribute_values(
                r,
                obj,
                from_db=True,
                variable_values_by_id=variable_values_by_id,
                file_cache=file_cache
            )
            obj.update(modifications)
            if r.CheckAccess('rqm_richtext_save') and r.CheckAccess('save'):
                obj["system:specificationeditor_readonly"] = False
            else:
                obj["system:specificationeditor_readonly"] = True
            objects.append(obj)
        # sqlapi.SQLselect('1 -- default_view_by_id end')
        return apply_bounds(all_ids, {
            "objects": objects,
            "result_complete": True
        })
    else:
        raise HTTPForbidden
