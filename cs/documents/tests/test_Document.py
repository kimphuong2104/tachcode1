#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Test Module test_Document

This is the documentation for the tests.

"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"


import unittest
from datetime import datetime

from cdb import rte, sig, sqlapi, testcase, typeconversion, util
from cdb.constants import kOperationDelete, kOperationNew
from cdb.objects import operations
from cdb.objects.operations import operation
from cdb.objects.org import Person
from cs.documents import Document, DocumentCategory


class test_Document(testcase.RollbackTestCase):
    """Documentation for this test case"""

    def setUp(self):
        super(test_Document, self).setUp()
        # This test assumes that there are some document records
        # in the installation
        self.docs = Document.Query(Document.erzeug_system != sqlapi.NULL)

    def test_getExternalFilename(self):
        for doc in self.docs:
            assert type(doc.getExternalFilename()) == type(u""), (  # noqa E721 # nosec
                "Failed %s" % doc
            )
            assert type(doc.getExternalFilename("pdf")) == type(  # noqa E721 # nosec
                u""
            ), (  # noqa E721
                "Failed %s" % doc
            )
            # Es sollte auch niemals None als String drin stehen.
            assert doc.getExternalFilename("pdf") != str(None), (  # nosec
                "Failed %s" % doc
            )
            assert doc.getExternalFilename("pdf") != str(None), (  # nosec
                "Failed %s" % doc
            )

    def test_GetDefaultErzSystem(self):
        self.assertTrue(isinstance(Document.GetDefaultErzSystem(), str))

    def test_GetInitialCreateValues(self):
        self.assertTrue(isinstance(Document.GetInitialCreateValues(), dict))

    def test_GetInitialIndexValues(self):
        self.assertTrue(isinstance(Document.GetInitialIndexValues(), dict))

    def test_GetInitialCopyValues(self):
        self.assertTrue(isinstance(Document.GetInitialCopyValues(), dict))


class Test_document_GetReviewer(testcase.RollbackTestCase):
    def setUp(self):
        self.d = Document.ByKeys("D014503", "")
        self.p = Person.ByKeys("test.documents")
        if not self.d or not self.p:
            unittest.SkipTest("Test requires testdata from cs.doctest")
        super(Test_document_GetReviewer, self).setUp()

    def test_GetReviewer(self):
        self.d.pruefer = self.p.name
        self.assertEqual(self.d.GetReviewer(), [self.p.personalnummer])


class Test_document_setFilename(testcase.RollbackTestCase):
    """
    Test of legacy code. This should ensure that setFilename is called
    after the document number has been generated.
    """

    def setUp(self):
        if "std-solution" not in rte.enabled_options():
            unittest.SkipTest("Test requires activated std-solution")
        super(Test_document_setFilename, self).setUp()

    def test_setFilename(self):
        categ = DocumentCategory.ByKeys(200)  # doc_approve
        doc = operation(
            kOperationNew,
            "document",
            cdb_obsolete=1,
            pruefer="caddok",
            autoren="hinz, kunz",
            erzeug_system="Catia",
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
        )
        self.assertEqual(doc.dateiname, doc.z_nummer + "-" + doc.z_index)


class Test_document_copyDoc(testcase.RollbackTestCase):
    def setUp(self):
        self.d = Document.ByKeys("D014503", "")
        self.p = Person.ByKeys("test.documents")
        if not self.d or not self.p:
            unittest.SkipTest("Test requires testdata from cs.doctest")
        super(Test_document_copyDoc, self).setUp()

    def test_copyDoc_noargs(self):
        copy = self.d.copyDoc()
        self.assertTrue(copy)
        for (attr, value) in Document.GetInitialCopyValues().items():
            c_val = copy[attr]
            if isinstance(value, str):
                if isinstance(c_val, datetime):
                    # This strips the 00:00:00
                    c_val = typeconversion.to_legacy_date_format_auto(c_val)
                else:
                    c_val = typeconversion.to_untyped_c_api(c_val)
            if isinstance(value, datetime):
                value = value.date()
                c_val = c_val.date()
            self.assertEqual(
                c_val, value, "Attribute '%s': '%s' != '%s'" % (attr, value, copy[attr])
            )

    def test_copyDoc_withargs(self):
        new_args = {"cdb_obsolete": 1, "pruefer": "TUEV"}
        copy = self.d.copyDoc(**new_args)
        self.assertTrue(copy)
        for (attr, value) in new_args.items():
            self.assertEqual(
                copy[attr],
                value,
                "Attribute '%s': '%s' != '%s'" % (attr, value, copy[attr]),
            )


class Test_document_PreviousIndex(testcase.RollbackTestCase):
    def setUp(self):
        self.d = Document.ByKeys("D014503", "")
        if not self.d:
            unittest.SkipTest("Test requires testdata from cs.doctest")
        super(Test_document_PreviousIndex, self).setUp()
        self.d1 = self.d.CreateIndex()
        self.d2 = self.d1.CreateIndex()

    def test_empty_index(self):
        self.assertEqual(self.d.PreviousIndex, None)

    def test_index(self):
        self.assertEqual(self.d1.PreviousIndex.z_index, self.d.z_index)
        self.assertEqual(self.d2.PreviousIndex.z_index, self.d1.z_index)

    def test_previous_delete_post(self):
        try:

            @sig.connect(Document, "delete", "post")
            def calc_previous(doc, ctx):
                self.deleted_index = doc.PreviousIndex

            expected = self.d2.PreviousIndex.z_index
            operations.operation(kOperationDelete, self.d2)
            self.assertTrue(self.deleted_index)
            self.assertEqual(expected, self.deleted_index.z_index)
        finally:
            sig.disconnect(calc_previous)


class Test_document_references_base(testcase.RollbackTestCase):
    """
    Base class for ``cdb_doc_rel`` tests.
    The setup creates the references for this structure
    TestE038449_HBG (Produkt/Teil/3D Baugruppe) D014503/
        TestE038449_UBG1 (Produkt/Teil/3D Baugruppe) D014504/
           TestE038449_ET1 (Produkt/Teil/3D Einzelteil) D014506/
           TestE038449_ET2 (Produkt/Teil/3D Einzelteil) D014507/
        TestE038449_UBG2 (Produkt/Teil/3D Baugruppe) D014505/
           TestE038449_ET2 (Produkt/Teil/3D Einzelteil) D014507/
    """

    def setUp(self):
        self.parent = Document.ByKeys("D014503", "")
        if not self.parent:
            unittest.SkipTest("Test requires testdata from cs.doctest")

        super(Test_document_references_base, self).setUp()
        self.links = [
            ("D014503", "D014504"),
            ("D014503", "D014505"),
            ("D014504", "D014506"),
            ("D014504", "D014507"),
            ("D014505", "D014507"),
        ]
        for referer, reference in self.links:
            self._insert_link(referer, reference)

    def _insert_link(self, referer, reference):  # pylint: disable=no-self-use
        i = util.DBInserter("cdb_doc_rel")
        i.add("logischer_name", "link")
        i.add("reltype", "Reftest")
        i.add("z_index", "")
        i.add("z_index2", "")
        i.add("z_nummer", referer)
        i.add("z_nummer2", reference)
        i.insert()


class Test_document_resolveReferencedDocuments(Test_document_references_base):
    """
    Test for Document.resolveReferencedDocuments
    """

    def test_depth(self):
        """
        We have 2 elements on the first level and further 2 on the second
        """
        self.assertEqual(len(self.parent.resolveReferencedDocuments(1)), 2)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(2)), 4)
        self.assertEqual(len(self.parent.resolveReferencedDocuments()), 4)

    def test_order(self):
        """
        The references has to be sorted.
        """
        refs = [d.z_nummer for d in self.parent.resolveReferencedDocuments(2)]
        for referer, reference in self.links:
            if referer != self.parent.z_nummer:
                self.assertTrue(
                    refs.index(referer) < refs.index(reference),
                    "%s is not before %s" % (referer, reference),
                )

    def test_direct_recursion(self):
        """
        A document pointed to itself
        """
        self._insert_link("D014505", "D014505")
        self.assertEqual(len(self.parent.resolveReferencedDocuments(1)), 2)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(2)), 4)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(5)), 4)

    def test_parent_recursion(self):
        """
        A document pointed to the parent of all
        """
        self._insert_link("D014505", self.parent.z_nummer)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(1)), 2)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(2)), 4)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(5)), 4)

    def test_other_recursion(self):
        """
        Circle (D014504->D014506-->D014507-->D014504)
        """
        self._insert_link("D014506", "D014507")
        self._insert_link("D014507", "D014504")
        self.assertEqual(len(self.parent.resolveReferencedDocuments(1)), 2)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(2)), 4)
        self.assertEqual(len(self.parent.resolveReferencedDocuments(5)), 4)

    def test_invalid_target(self):
        """
        E047640 (ProE:IRef references might refer a part instead of a
        document.
        """
        self._insert_link("D014503", "DDNone")
        self.assertEqual(len(self.parent.resolveReferencedDocuments(1)), 2)


class Test_document_GetReferencedDocsWithInvalidState(Test_document_references_base):
    """
    Test for Document.GetReferencedDocsWithInvalidState
    """

    def test_all_referenced_states_valid(self):
        # All referenced docs have the initial state ``0``
        self.assertEqual([], self.parent.GetReferencedDocsWithInvalidState([0]))
        self.assertEqual([], self.parent.GetReferencedDocsWithInvalidState([0, 5]))

    def test_all_referenced_states_invalid(self):
        result = self.parent.GetReferencedDocsWithInvalidState([10, 20])
        self.assertEqual(len(result), 2)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
