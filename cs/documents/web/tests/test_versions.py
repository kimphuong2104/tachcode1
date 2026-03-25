# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


__docformat__ = "restructuredtext en"


import unittest

from webtest import TestApp as Client

from cdb import sig
from cdb.testcase import RollbackOnceTestCase, RollbackTestCase, error_logging_disabled
from cs.platform.web.root import Root


class TestDocumentsObject(RollbackOnceTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Set up the test case
        """
        super(TestDocumentsObject, cls).setUpClass()

        try:
            from cs.documents import Document
        except ImportError:
            raise unittest.SkipTest("this test needs cs.documents")
        cls.created = Document.Create(
            z_nummer=Document.makeNumber(None),
            z_index="",
            titel="test",
            z_categ1=142,
            z_categ2=153,
            autoren="Administrator",
            z_bereich="IT",
            erzeug_system="PAPIER",
            z_status_txt="In Progress",
            z_art="doc_standard",
            z_status=0,
            cdb_obsolete=0,
            cdb_mpersno="caddok",
            cdb_mdate="05.12.2014 16:49:58",
            cdb_cpersno="caddok",
            cdb_cdate="05.12.2014 16:49:58",
        )
        cls.created_a = Document.Create(
            z_nummer=cls.created.z_nummer,
            z_index="a",
            titel="test 2",
            z_categ1=142,
            z_categ2=153,
            autoren="Administrator",
            z_bereich="IT",
            erzeug_system="PAPIER",
            z_status_txt="In Progress",
            z_art="doc_standard",
            z_status=0,
            cdb_obsolete=0,
            cdb_mpersno="caddok",
            cdb_mdate="05.12.2014 16:49:58",
            cdb_cpersno="caddok",
            cdb_cdate="05.12.2014 16:49:58",
        )

        app = Root()
        cls.c = Client(app)

    def test_document_GET_without_index(self):
        oid = self.created.z_nummer
        response = self.c.get("/api/v1/collection/document/%s" % oid)
        self.assertEqual(response.json["z_index"], "a")
        self.assertEqual(response.json["titel"], "test 2")
        self.assertEqual(response.json["category1_name"], "Allgemeines")
        self.assertEqual(response.json["category2_name"], "Besuchsbericht")

    def test_document_GET_with_index(self):
        oid = self.created.z_nummer
        response = self.c.get("/api/v1/collection/document/%s@" % oid)
        self.assertEqual(response.json["z_index"], "")
        self.assertEqual(response.json["titel"], "test")
        self.assertEqual(response.json["category1_name"], "Allgemeines")
        self.assertEqual(response.json["category2_name"], "Besuchsbericht")

    def test_document_GET_with_method(self):
        oid = self.created.z_nummer
        response = self.c.get(
            "/api/v1/collection/document/%s@one_version_method@GetLatestObjectVersion"
            % oid
        )
        self.assertEqual(response.json["z_index"], "a")
        self.assertEqual(response.json["titel"], "test 2")
        self.assertEqual(response.json["category1_name"], "Allgemeines")
        self.assertEqual(response.json["category2_name"], "Besuchsbericht")

    def test_document_GET_invalid_without_index(self):
        oid = "invalid"
        with error_logging_disabled():
            response = self.c.get(
                "/api/v1/collection/document/%s" % oid, expect_errors=True
            )
        self.assertEqual(response.status_code, 404)

    def test_document_GET_invalid_with_index(self):
        oid = "invalid"
        with error_logging_disabled():
            response = self.c.get(
                "/api/v1/collection/document/%s@" % oid, expect_errors=True
            )
        self.assertEqual(response.status_code, 404)


class TestObjectVersions(RollbackTestCase):
    def setUp(self):
        """
        Set up the test case
        """
        super(TestObjectVersions, self).setUp()

        try:
            from cs.documents import Document
        except ImportError:
            raise unittest.SkipTest("this test needs cs.documents")
        self.created = Document.Create(
            z_nummer=Document.makeNumber(None),
            z_index="",
            titel="test",
            z_categ1=142,
            z_categ2=153,
            autoren="Administrator",
            z_bereich="IT",
            erzeug_system="PAPIER",
            z_status_txt="In Progress",
            z_art="doc_standard",
            z_status=0,
            cdb_obsolete=0,
            cdb_mpersno="caddok",
            cdb_mdate="05.12.2014 16:49:58",
            cdb_cpersno="caddok",
            cdb_cdate="05.12.2014 16:49:58",
        )

        app = Root()
        self.c = Client(app)

    def test_versions_GET(self):
        oid = self.created.z_nummer
        response = self.c.get("/api/v1/collection/document/%s/versions" % oid)
        self.assertEqual(len(response.json), 1)
        self.assertEqual(response.json[0]["z_index"], "")
        self.assertEqual(response.json[0]["z_status_txt"], "In Progress")
        link = response.json[0]["@id"]
        response = self.c.get(link)
        self.assertEqual(response.json["z_index"], "")

    def test_versions_PUT(self):
        oid = self.created.z_nummer
        with error_logging_disabled():
            response = self.c.put_json(
                "/api/v1/collection/document/%s/versions" % oid, {}
            )
        self.assertEqual(len(response.json), 2)
        self.assertEqual(response.json[0]["z_index"], "")
        self.assertEqual(response.json[1]["z_index"], "a")
        link = response.json[1]["@id"]
        response = self.c.get(link)
        self.assertEqual(response.json["z_index"], "a")
        # check GetLatestObjectVersion on 2 non-released docs
        response = self.c.get("/api/v1/collection/document/%s" % oid)
        self.assertEqual(response.json["titel"], "test")

    def test_versions_PUT_content(self):
        json = {"cdb::argument.z_index_neu": "b"}
        oid = self.created.z_nummer
        with error_logging_disabled():
            response = self.c.put_json(
                "/api/v1/collection/document/%s/versions" % oid, json
            )
        self.assertEqual(len(response.json), 2)
        self.assertEqual(response.json[0]["z_index"], "")
        self.assertEqual(response.json[1]["z_index"], "b")
        link = response.json[1]["@id"]
        response = self.c.get(link)
        self.assertEqual(response.json["z_index"], "b")

    def test_versions_PUT_date(self):
        url = "/api/v1/collection/document/{}/versions".format(self.created.z_nummer)
        src_cdate = "2000-12-15T14:32:54"
        self.c.put_json(url, {"src_cdate": src_cdate})
        url = "/api/v1/collection/document/{}/versions".format(self.created.z_nummer)
        doc_indices = self.c.get(url).json
        self.assertEquals(2, len(doc_indices))
        indices = set()
        src_cdates = set()
        for index in doc_indices:
            self.assertEquals(self.created.z_nummer, index["z_nummer"])
            indices.add(index["z_index"])
            src_cdates.add(index.get("src_cdate", None))
        self.assertSetEqual(set(["", "a"]), indices)
        self.assertSetEqual(set([None, src_cdate]), src_cdates)

    def test_uses_restapi(self):
        from cs.documents import Document

        try:

            @sig.connect(Document, "index", "post")
            def index_post(_, ctx):
                self.assertTrue(ctx.uses_restapi)

            url = "/api/v1/collection/document/{}/versions".format(
                self.created.z_nummer
            )
            self.c.put_json(url, {})

            url = "/api/v1/collection/document/{}/versions".format(
                self.created.z_nummer
            )
            doc_indices = self.c.get(url).json
            self.assertEquals(2, len(doc_indices))
            indices = set()
            for index in doc_indices:
                self.assertEquals(self.created.z_nummer, index["z_nummer"])
                indices.add(index["z_index"])
            self.assertSetEqual(set(["", "a"]), indices)

        finally:
            sig.disconnect(index_post)


class TestDocumentsCollection(RollbackOnceTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Set up the test case
        """
        super(TestDocumentsCollection, cls).setUpClass()

        try:
            from cs.documents import Document
        except ImportError:
            raise unittest.SkipTest("this test needs cs.documents")
        cls.created = Document.Create(
            z_nummer=Document.makeNumber(None),
            z_index="",
            titel="test",
            z_categ1=142,
            z_categ2=153,
            autoren="Administrator",
            z_bereich="IT",
            erzeug_system="PAPIER",
            z_status_txt="In Progress",
            z_art="doc_standard",
            z_status=0,
            cdb_obsolete=0,
            cdb_mpersno="caddok",
            cdb_mdate="05.12.2014 16:49:58",
            cdb_cpersno="caddok",
            cdb_cdate="05.12.2014 16:49:58",
        )
        cls.created_a = Document.Create(
            z_nummer=cls.created.z_nummer,
            z_index="a",
            titel="test 2",
            z_categ1=142,
            z_categ2=153,
            autoren="Administrator",
            z_bereich="IT",
            erzeug_system="PAPIER",
            z_status_txt="In Progress",
            z_art="doc_standard",
            z_status=0,
            cdb_obsolete=0,
            cdb_mpersno="caddok",
            cdb_mdate="05.12.2014 16:49:58",
            cdb_cpersno="caddok",
            cdb_cdate="05.12.2014 16:49:58",
        )

        app = Root()
        cls.c = Client(app)

    def test_document_GET_without_version_para(self):
        oid = self.created.z_nummer
        response = self.c.get(
            "/api/v1/collection/document?$filter=z_nummer eq '%s'" % oid
        )
        # We should got the highest index
        objs = response.json["objects"]
        self.assertEqual(len(objs), 2)

    def test_document_GET_with_version_para_1(self):
        oid = self.created.z_nummer
        response = self.c.get(
            "/api/v1/collection/document?$filter=z_nummer eq '%s'&all_versions=1" % oid
        )
        # We should got the highest index
        objs = response.json["objects"]
        self.assertEqual(len(objs), 2)

    def test_document_GET_with_version_para_0(self):
        oid = self.created.z_nummer
        response = self.c.get(
            "/api/v1/collection/document?$filter=z_nummer eq '%s'&all_versions=0" % oid
        )
        # We should got the highest index
        objs = response.json["objects"]
        self.assertEqual(len(objs), 1)
        obj = objs[0]
        self.assertEqual(obj["titel"], self.created_a.titel)

    def test_document_GET_with_one_version_method(self):
        oid = self.created.z_nummer
        response = self.c.get(
            "/api/v1/collection/document?$filter=z_nummer eq '%s'&one_version_method=GetLatestObjectVersion"
            % oid
        )
        # We should got the highest index
        objs = response.json["objects"]
        self.assertEqual(len(objs), 1)
        obj = objs[0]
        self.assertEqual(obj["titel"], self.created_a.titel)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
