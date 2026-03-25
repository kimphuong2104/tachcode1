# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from webob.exc import HTTPBadRequest, HTTPNotFound

from cdb import fls, sqlapi
from cdb.platform.mom import increase_eviction_queue_limit
from cdb.profiling import profile
from cs.platform.web.rest.app import get_collection_app
from cs.platform.web.rest.generic.main import get_generic_app
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.rqm_utils import DescriptionColumnProvider
from cs.requirements.web.rest.diff.deleted_model import DiffDeletedAPIModel
from cs.requirements.web.rest.diff.diff_indicator_model import (
    DiffCriterionRegistry, DiffIndicatorAPIModel)
from cs.requirements.web.rest.diff.requirements_model import RequirementsModel

from .acceptance_criterion_model import DiffAcceptanceCriterionAPIModel
from .classification_model import DiffClassificationAPIModel
from .file_model import DiffFileAPIModel
from .header_model import DiffHeaderAPIModel
from .main import DiffAPI
from .matching_model import DiffMatchingAPIModel
from .metadata_model import DiffMetadataAPIModel
from .richtext_model import DiffRichTextAPIModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@DiffAPI.json(model=DiffHeaderAPIModel, request_method="GET")
def diff_header_view(model, request):
    return model.diff(languages=request.GET.get("languages").split(","))


@DiffAPI.json(model=DiffRichTextAPIModel, request_method="GET")
def diff_richtext_view(model, request):
    return model.diff(languages=request.GET.get("languages").split(","))


@DiffAPI.json(model=DiffMetadataAPIModel, request_method="GET")
def diff_metadata_view(model, request):
    return model.diff(languages=request.GET.get("languages").split(","))


@DiffAPI.json(model=DiffClassificationAPIModel, request_method="GET")
def diff_classification_view(model, request):
    return model.diff(languages=request.GET.get("languages").split(","))


@DiffAPI.json(model=DiffFileAPIModel, request_method="GET")
def diff_file_view(model, request):
    return model.diff(languages=request.GET.get("languages").split(","), request=request)


@DiffAPI.json(model=DiffAcceptanceCriterionAPIModel, request_method="GET")
def diff_acceptance_criterion_view(model, request):
    return model.diff(languages=request.GET.get("languages").split(","))


@DiffAPI.json(model=DiffMatchingAPIModel, request_method="GET")
def diff_matching_view(model, request):
    matching_object = model.get_matching_object()
    if matching_object:
        collection_app = get_collection_app(request)
        return request.view(matching_object, app=collection_app)
    else:
        raise HTTPNotFound


@DiffAPI.json(model=DiffDeletedAPIModel, request_method="GET")
def diff_deleted_view(model, request):
    deleted_object_ids = model.get_deleted_object_ids()
    collection_app = get_collection_app(request)
    objects = []
    for r in model.left_spec.Requirements.KeywordQuery(
        cdb_object_id=deleted_object_ids, order_by="sortorder"
    ).Query("1=1", access='read'):
        obj = request.view(
            r,
            app=collection_app
        )
        objects.append(obj)
    return {
        "objects": objects,
        "result_complete": True
    }


def _add_structure_information(
        obj, has_target_value_cache=None, parents_included_in_request=None, sortorder_cache=None
):
    if sortorder_cache is None:
        sortorder_cache = {}
    if 'sortorder' in obj:  # all recs
        sortorder_cache[obj['cdb_object_id']] = obj['sortorder']
    if (
        parents_included_in_request is not None and
        obj['cdb_object_id'] in parents_included_in_request
    ):
        obj['system:structure_parent_preloaded'] = True
    if has_target_value_cache is None:
        has_target_value_cache = {}
    classname = obj['system:classname']
    if classname == 'cdbrqm_specification':
        obj['system:structure_sortorder'] = '00000'
        obj['system:structure_parent_id'] = ''
        obj['system:structure_id'] = obj['cdb_object_id']
        obj['hasChildren'] = True
    elif classname == 'cdbrqm_spec_object' and not obj['parent_object_id']:
        # top level
        obj['system:structure_parent_id'] = obj['specification_object_id']
        obj['system:structure_id'] = obj['cdb_object_id']
        obj['hasChildren'] = obj['is_group'] or (
            has_target_value_cache.get(obj['cdb_object_id']) is not None
        )
    elif classname == 'cdbrqm_spec_object' and obj['parent_object_id']:
        # second level
        obj['system:structure_parent_id'] = obj['parent_object_id']
        obj['system:structure_id'] = obj['cdb_object_id']
        obj['hasChildren'] = obj['is_group'] or (
            has_target_value_cache.get(obj['cdb_object_id']) is not None
        )
    elif classname == 'cdbrqm_target_value':
        obj['system:structure_sortorder'] = (
            sortorder_cache[obj['requirement_object_id']] + '/%05d' % obj['pos']
        )
        obj['system:structure_id'] = obj['cdb_object_id']  # needed to map between rows/structure ids
        obj['system:structure_parent_id'] = obj['requirement_object_id']
        obj['hasChildren'] = False
    else:
        raise NotImplementedError('%s is not supported currently' % classname)


def _get_requirements(model, request, parent_object_ids):
    fls.allocate_license('RQM_070')
    with profile():
        with increase_eviction_queue_limit(10000):
            reqs = []
            # as of now the we do not have kernel relationship query with IN condition
            # which delivers object handles - another option might be to query with sqlapi to gather
            # all object ids and then use something like getObjectHandlesFromObjectIDs
            # this could also work for id lists received from recursive queries
            # look into cs.platform.web.rest.generic.model.ObjectCollection for further ideas
            if parent_object_ids[0] == '':
                reqs = [model.spec]
            for parent_object_id in parent_object_ids:
                reqs.extend(model.get_requirements(parent_object_id))  # non toplevel
            if len(parent_object_ids) == 0:
                reqs.extend(model.get_requirements())  # toplevel
            spec_app = get_generic_app(request, 'specification')
            spec_object_app = get_generic_app(request, 'spec_object')
            # app caches/preloads/settings needs a platform change
            spec_object_app.__application_performance_args__ = {
                'prefer_object_handles': True,
                'text_preload_cache': model.get_requirements_text_cache(reqs),
                'should_cache_system_relships': True
            }
            tv_app = get_generic_app(request, 'target_value')
            app = {
                RQMSpecification.__maps_to__: spec_app,
                RQMSpecObject.__maps_to__: spec_object_app,
                TargetValue.__maps_to__: tv_app
            }
            objects = []
            parent_object_ids_without_spec = [x for x in parent_object_ids if x]
            parents_sortorder_stmt = """
                SELECT cdb_object_id, sortorder FROM cdbrqm_spec_object WHERE {condition}
            """.format(
                condition=RQMSpecObject.cdb_object_id.one_of(*parent_object_ids_without_spec)
            )
            sortorder_cache = {
                r['cdb_object_id']: r['sortorder']
                for r in sqlapi.RecordSet2(sql=parents_sortorder_stmt)
            } if len(parent_object_ids_without_spec) > 0 else {}
            has_target_value_cache = model.get_requirements_target_value_cache(reqs)
            for r in reqs:
                obj = request.view(
                    r,
                    name="relship-target",
                    app=app[r.__maps_to__]
                )
                _add_structure_information(
                    obj, has_target_value_cache, parent_object_ids, sortorder_cache)
                objects.append(obj)
            column_data = DescriptionColumnProvider.getColumnData(None, objects)
            if len(column_data) == len(objects):
                for i in range(0, len(objects)):
                    objects[i]['cs.requirements.rqm_utils.DescriptionColumnProvider'] = (
                        column_data[i]['description']
                    )
            return {
                "objects": sorted(
                    objects, key=lambda x: x.get('sortorder', x.get('system:structure_sortorder'))
                ),
                "result_complete": True
            }


@DiffAPI.json(model=RequirementsModel, request_method="GET")
def get_requirements(model, request):
    parent_object_ids = []
    try:
        query_all = request.GET.get('all', False)
        parent_object_ids = str(request.GET.get('parent_object_ids', '')).split(',')
        object_id = str(request.GET.get('cdb_object_id', ''))
        if object_id:
            parent_object_ids = model.get_parents(
                cdb_object_id=object_id, parent_object_ids=parent_object_ids
            )
            if len(parent_object_ids) > 1:  # otherwise all is already loaded in client
                return parent_object_ids
            raise HTTPBadRequest()
        parent_object_ids = [x for x in parent_object_ids if x or not query_all]
    except ValueError:
        raise HTTPBadRequest()
    return _get_requirements(model, request, parent_object_ids)


@DiffAPI.json(model=RequirementsModel, request_method="POST")
def get_requirements_multi(model, request):
    parent_object_ids = []
    try:
        query_all = request.POST.get('all', False)
        parent_object_ids = str(request.POST.get('parent_object_ids', '')).split(',')
        parent_object_ids = [x for x in parent_object_ids if x or not query_all]
    except ValueError:
        raise HTTPBadRequest()
    return _get_requirements(model, request, parent_object_ids)


@DiffAPI.json(model=DiffIndicatorAPIModel, requests_method="GET")
def get_diff_indicator_data(model, request):
    languages = request.GET.get("languages").split(",")
    criterions = request.GET.get('criterions').split(",")

    return model.get_diff_indicator_for_all_tree_nodes(
        DiffCriterionRegistry.get_settings_by_criterions(criterions, languages)
    )
