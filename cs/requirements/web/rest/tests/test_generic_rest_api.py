# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import json

from cdb.testcase import RollbackTestCase, without_error_logging, \
    error_logging_disabled
from cs.platform.web.root import root as RootApp
import logging

from webtest import TestApp

from cs.audittrail import AuditTrailObjects
from cs.requirements import RQMSpecification

LOG = logging.getLogger(__name__)


class TestRQMGenericRESTAPIEndpoints(RollbackTestCase):

    def __init__(self, *args, **kwargs):
        super(TestRQMGenericRESTAPIEndpoints, self).__init__(*args, **kwargs)
        self.client = None

    def setUp(self):
        RollbackTestCase.setUp(self)
        self.client = TestApp(RootApp)
        self.spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]

    def count_audittrail_entries_for_object(self, obj):
        return len(AuditTrailObjects.KeywordQuery(object_id=obj.cdb_object_id))


    def test_spec_object_put_invalid_xml_chars(self):
        req = self.spec.Requirements[0]
        url = '/api/v1/collection/spec_object/{cdb_object_id}'.format(cdb_object_id=req.cdb_object_id)
        title = 'the && invalid  title'
        body = 'the invalid body'
        richtext = '<xhtml:div><xhtml:div>{title}</xhtml:div><xhtml:div>{body}</xhtml:div></xhtml:div>'.format(body=body, title=title)
        for iso in ['de', 'en']:
            attr_name = 'cdbrqm_spec_object_desc_{iso}'.format(iso=iso)
            short_attr_name = 'name_{iso}'.format(iso=iso)
            audittrail_count_before = self.count_audittrail_entries_for_object(req)
            self.assertNotEqual(req.GetText(attr_name), richtext)
            self.assertNotEqual(getattr(req, short_attr_name), title)
            resp = self.client.put_json(url, {attr_name: richtext}, expect_errors=True)
            response_body = json.loads(resp.body)
            self.assertEqual(response_body['detail'], 'Anfrage enthält XML-Syntaxfehler.')


    def test_spec_object_put(self):
        req = self.spec.Requirements[0]
        url = '/api/v1/collection/spec_object/{cdb_object_id}'.format(cdb_object_id=req.cdb_object_id)
        title = 'the new title'
        body = 'the new body'
        richtext = '<xhtml:div><xhtml:div>{title}</xhtml:div><xhtml:div>{body}</xhtml:div></xhtml:div>'.format(body=body, title=title)
        for iso in ['de', 'en']:
            attr_name = 'cdbrqm_spec_object_desc_{iso}'.format(iso=iso)
            short_attr_name = 'name_{iso}'.format(iso=iso)
            audittrail_count_before = self.count_audittrail_entries_for_object(req)
            self.assertNotEqual(req.GetText(attr_name), richtext)
            self.assertNotEqual(getattr(req, short_attr_name), title)

            self.client.put_json(url, {attr_name: richtext})
            req.Reload()
            # the new richtext was saved correctly
            self.assertEqual(req.GetText(attr_name), richtext)
            self.assertEqual(getattr(req, short_attr_name), title)
            audittrail_count_after = self.count_audittrail_entries_for_object(req)
            self.assertGreater(audittrail_count_after, audittrail_count_before)
        req.Reload()
        self.assertEqual(req.name_de, title)
        self.assertEqual(req.name_en, title)


    def test_sliding_window_get(self):
        """ test whether the sliding window rest api does work as expected """

        def get_sliding_window(context_obj, **params):
            url = '/internal/specificationeditor/{cdb_object_id}'.format(cdb_object_id=context_obj.cdb_object_id)
            if 'status_code' in params:
                status_code = params.pop('status_code')
                res = self.client.get(url, params=params, status=status_code)
            else:
                res = self.client.get(url, params=params)
            return res.json

        context_obj = self.spec
        first_req = self.spec.Requirements.Query("1=1", order_by="sortorder")[0]
        last_req = self.spec.Requirements.Query("1=1", order_by="sortorder")[-1]

        res = get_sliding_window(context_obj, initial=1)
        # default one before one after but in case of specifications use the first req as starting point
        self.assertEqual(len(res.get('objects')), 2)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        res = get_sliding_window(context_obj, initial=1, before=0, after=4)
        self.assertEqual(len(res.get('objects')), 5)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        res = get_sliding_window(context_obj, initial=1, before=0, after=2)
        self.assertEqual(len(res.get('objects')), 3)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        res = get_sliding_window(last_req)
        # default one before and one after therefore 2
        self.assertEqual(len(res.get('objects')), 2)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        res = get_sliding_window(last_req, before=4, after=0)
        self.assertEqual(len(res.get('objects')), 5)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        res = get_sliding_window(last_req, before=0, after=0)
        self.assertEqual(len(res.get('objects')), 1)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        # after the last is nothing so setting after to high leads not to higher amounts
        res = get_sliding_window(last_req, before=2, after=2)
        self.assertEqual(len(res.get('objects')), 3)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        # before the first is nothing so setting before to high leads not to higher amounts
        res = get_sliding_window(first_req, before=2, after=2)
        self.assertEqual(len(res.get('objects')), 3)
        self.assertEqual(res.get('first_id'), first_req.cdb_object_id)
        self.assertEqual(res.get('last_id'), last_req.cdb_object_id)

        with error_logging_disabled():
            # stupid cases lead to bad request
            res = get_sliding_window(first_req, before='not_an_integer', status_code=400)
            res = get_sliding_window(first_req, after='not_an_integer', status_code=400)
            res = get_sliding_window(first_req, initial='not_an_integer', status_code=400)
            res = get_sliding_window(first_req, before=-1, status_code=400)
            res = get_sliding_window(first_req, after=-1, status_code=400)
