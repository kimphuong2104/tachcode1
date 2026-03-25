# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function, unicode_literals

import datetime
import logging

from cdb import testcase, objects, sqlapi
from cs.classification import prepare_read
from cs.requirements import RQMSpecification, RQMSpecObject, rqm_utils
from cs.requirements.rqm_utils import RQMHierarchicals

from .utils import RequirementsTestCase
from cdb.platform import mom

LOG = logging.getLogger(__name__)


class TestTreeDownContext(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestTreeDownContext, self).__init__(*args, need_uberserver=False,
                                                  **kwargs)

    def setUp(self):
        RequirementsTestCase.setUp(self)
        prepare_read(RQMSpecObject.__classname__)

    def _walk(self, output, tree_down_context, obj=None, level=0):
        target_value_cache = tree_down_context.get('target_value_cache')
        if obj is not None:
            if hasattr(obj, 'specobject_id'):
                output.append(" " * level + obj.specobject_id)
            if obj.cdb_object_id in target_value_cache:
                for t in target_value_cache.get(obj.cdb_object_id):
                    output.append(" " * (level + 1) + t.targetvalue_id)
        root = tree_down_context.get('root')
        children = root._tree_depth_first_next(tree_down_context, obj)
        for child in children:
            self._walk(output, tree_down_context, child, level=level + 1)
    
    def test_tree_down_context_huge(self):
        # due to E068544 some problems are only detected when we have more than 1000 elements within
        # the specification
        new_spec_args = {
            u"name": u'Test Specification %s' % datetime.datetime.now(),
            u"is_template": 0,
            u"category": u'System Specification'
        }
        new_spec = objects.operations.operation(
            "CDB_Create",
            RQMSpecification,
            **new_spec_args
        )
        start = datetime.datetime.now()
        with testcase.max_sql(2002): # one query for the object creation + one for cdb_object entry creation?
            for i in range(0, 1001):
                description = 'req%s' % i
                args = {
                    "parent_object_id": '',
                    "specification_object_id": new_spec.cdb_object_id,
                    "specobject_id": 'RT_C_%05d' % i,
                    "position": i,
                    "cdbrqm_spec_object_desc_de": "<xhtml:div>{}</xhtml:div>".format(description)
                }
                RQMSpecObject.CreateNoResult(**args)
        new_spec.update_sortorder()
        new_spec.Reload()
        self.assertEqual(len(new_spec.Requirements), 1001)
        end = datetime.datetime.now()
        duration = (end-start).total_seconds()
        LOG.info("preparation took %s seconds", duration)
        success = False
        try:
            with testcase.max_sql(15): # just to make sure it stays constant
                tree_down_context = RQMHierarchicals.get_tree_down_context(new_spec)
            success = True
        except TypeError:
            pass
        self.assertTrue(success)

    def test_tree_down_context(self):
        # initialize dd system seems to cost 27 queries and is not what we want to test
        RQMSpecification.GetTextFieldNames()
        spec = RQMSpecification.KeywordQuery(name=u"Tree Performance Test")[0]
        other_spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        get_text_field_query_entities_cnt = 2
        hierarchical_query_cnt = 1  # one hierarchy

        # for tv we have a query to get the cdb_object_ids in right position
        # whereas for reqs we have them from the hierarchical
        entity_cache_query_cnt = 1  # two entities
        get_object_handles_from_object_ids_per_entity = 2

        long_text_query_cnt = 2  # two entities
        classification_query_cnt = 3  # two for oid to classname, one for query on eav
        total_allowed_queries = (
            hierarchical_query_cnt +
            entity_cache_query_cnt +
            get_text_field_query_entities_cnt +
            long_text_query_cnt +
            classification_query_cnt +
            get_object_handles_from_object_ids_per_entity * 2  # query object ids -> relation + query relation
        )
        # AC system warmup to make sure AC caches etc. does not lead to too high query count
        # use another spec to ensure no specific caches of tree_down_context are pre-loaded for
        # the object under test
        ids = [
            other_spec.cdb_object_id,
            other_spec.Requirements[0].cdb_object_id,
            other_spec.TargetValues[0].cdb_object_id
        ]
        mom.getObjectHandlesFromObjectIDs(ids, True, True)  # activate acs check and fresh objects
        with testcase.max_sql(total_allowed_queries):
            LOG.info('allowed queries : %d' % total_allowed_queries)
            output = [""]
            output.append(spec.spec_id)
            # sqlapi.SQLselect('1 -- start of tree down')
            tree_down_context = RQMHierarchicals.get_tree_down_context(spec)
            # sqlapi.SQLselect('1 -- stop of tree down')
            self._walk(output, tree_down_context)
            output = "\n".join(output)
            LOG.info(output)
        exspected = """
ST000000005
 RT000000042
  RT000000041
   RT000000040
    AT0000008
    AT0000009
 RT000000039
  RT000000038
   RT000000037
    AT0000010
    AT0000011"""
        self.assertEqual(exspected, output)
