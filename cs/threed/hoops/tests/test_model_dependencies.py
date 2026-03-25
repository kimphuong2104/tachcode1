# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import sqlapi
from cdb.testcase import RollbackTestCase, skip_dbms

from cs.threed.hoops.converter.tests import common


class TestModelDependencies(RollbackTestCase):
    def setUp(self):

        super(TestModelDependencies, self).setUp()

        self.items = [common.generateItem() for x in range(4)]

        self.root_doc, self.parent_doc, self.child_doc, self.another_doc = [
            common.generateCADDocument(item) for item in self.items]

        self.docs = [self.root_doc, self.parent_doc, self.child_doc, self.another_doc]

        self.doc_pairs = [
            (self.root_doc, self.parent_doc),
            (self.parent_doc,self.child_doc),
            (self.root_doc, self.another_doc)
        ]
        self.create_doc_rels(self.doc_pairs)

    def create_doc_rels(self, doc_pairs):
        cols = ["z_nummer", "z_index", "z_nummer2", "z_index2",
                "logischer_name", "reltype", "t_nummer2", "t_index2", "cdb_link"]

        for (dependency, doc) in doc_pairs:
            vals = [dependency.z_nummer, dependency.z_index, doc.z_nummer,
                    doc.z_index, "", "", doc.teilenummer, doc.t_index, "0"]
            sqlapi.SQLinsert("INTO cdb_doc_rel ({cols}) VALUES ('{vals}')".format(
                cols=", ".join(cols), vals="', '".join(vals)))

    def add_doc_rels(self, doc_pairs):
        self.doc_pairs.extend(doc_pairs)
        self.create_doc_rels(doc_pairs)

    def force_rollback(self):
        doc_rel_condition = " OR ".join(["z_nummer='%s' AND z_index='%s' AND z_nummer2='%s' AND z_index2='%s'" % (
            doc_pair[0].z_nummer, doc_pair[0].z_index, doc_pair[1].z_nummer, doc_pair[1].z_index) for doc_pair in self.doc_pairs])
        sqlapi.SQLdelete("FROM cdb_doc_rel WHERE {condition}".format(condition=doc_rel_condition))

        doc_condition = " OR ".join(["z_nummer='%s' AND z_index='%s'" %
                                     (doc.z_nummer, doc.z_index) for doc in self.docs])
        sqlapi.SQLdelete("FROM zeichnung WHERE {condition}".format(condition=doc_condition))

        item_condition = " OR ".join(["teilenummer='%s' AND t_index='%s'" %
                                      (item.teilenummer, item.t_index) for item in self.items])
        sqlapi.SQLdelete("FROM teile_stamm WHERE {condition}".format(condition=item_condition))

        sqlapi.SQLcommit()

    def _test_model_deps(self, expected, dependencies):
        expected_oids = sorted([exp.cdb_object_id for exp in expected])
        got_oids = sorted([dep.cdb_object_id for dep in dependencies])
        self.assertEqual(expected_oids, got_oids)

    def test_get_model_dependencies_fast(self):
        """ the `getModelDependenciesFast` method returns all the dependecies of a given document"""
        self._test_model_deps(
            expected=[self.root_doc, self.parent_doc],
            dependencies=self.child_doc.getModelDependenciesFast()
        )

    def test_get_model_dependencies_slow(self):
        """ the `getModelDependenciesSlow` method returns all the dependecies of a given document"""
        self._test_model_deps(
            expected=[self.root_doc, self.parent_doc],
            dependencies=self.child_doc.getModelDependenciesSlow()
        )

    def test_get_model_dependencies(self):
        """ the `getModelDependencies` method returns all the dependecies of a given document"""
        self._test_model_deps(
            expected=[self.root_doc, self.parent_doc],
            dependencies=self.child_doc.getModelDependencies()
        )

    @skip_dbms(sqlapi.DBMS_MSSQL)
    def test_get_model_dependencies_cyclic(self):
        """ `getModelDependencies` method returns all the dependecies of a given document containing cyclic references"""
        self.add_doc_rels([(self.another_doc, self.parent_doc), (self.child_doc, self.another_doc)])

        self._test_model_deps(
            expected=self.docs,
            dependencies=self.child_doc.getModelDependencies()
        )

    @skip_dbms(sqlapi.DBMS_ORACLE, sqlapi.DBMS_SQLITE)
    def test_get_model_dependencies_cyclic_manual_rollback(self):
        """ `getModelDependencies` method returns all the dependecies of a given document containing cyclic references with manual rollback"""
        self.add_doc_rels([(self.another_doc, self.parent_doc), (self.child_doc, self.another_doc)])
        sqlapi.SQLcommit()

        try:
            self._test_model_deps(
                expected=self.docs,
                dependencies=self.child_doc.getModelDependencies()
            )
        finally:
            self.force_rollback()
