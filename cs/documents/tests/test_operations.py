#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test Module test_worflow_issues

This is the documentation for the tests.
"""


__docformat__ = "restructuredtext en"


import unittest
from datetime import date, datetime
from io import BytesIO

from cdb import ElementsError, auth, constants, sqlapi, testcase, typeconversion
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cdb.util import PersonalSettings
from cs.activitystream.objects import Subscription
from cs.documents import Document, DocumentCategory


# Tests
class Test_document_Create(testcase.RollbackTestCase):
    """
    Test CDB_Create operation for document class
    """

    def tearDown(self):
        super(Test_document_Create, self).tearDown()
        PersonalSettings().invalidate()

    def test_wf_init_on_create(self):
        """
        The standard initializes the workflow using the category
        """
        categ = DocumentCategory.ByKeys(322)
        d = operation(
            constants.kOperationNew,
            "document",
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
        )
        self.assertEqual(d.z_status, 0)
        self.assertEqual(d.z_status_txt, "Draft")
        self.assertEqual(d.z_art, categ.getWorkflow(""))

    def test_initial_values_set(self):
        """
        Check if the intial attributes are set and do not
        overwrite values provided to the function.
        """
        initial_values = Document.GetInitialCreateValues()
        self.assertTrue(
            "zeichner" in initial_values,
            "Test has to be changed (initial attr missing)",
        )
        categ = DocumentCategory.ByKeys(322)
        d = operation(
            constants.kOperationNew,
            "document",
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
            zeichner="unknown",
        )
        initial_values["zeichner"] = "unknown"
        for attr, val in initial_values.items():
            doc_val = d[attr]
            if isinstance(doc_val, datetime) and isinstance(val, str):
                val = typeconversion.to_python_rep(sqlapi.SQL_DATE, val)
            if isinstance(doc_val, datetime):
                val = val.replace(microsecond=0)
            self.assertEqual(d[attr], val)

    def test_as_autosubscription(self):
        PersonalSettings()["cs.documents.creation.autosubscribe"] = "0"
        categ = DocumentCategory.ByKeys(322)
        d = operation(
            constants.kOperationNew,
            "document",
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
            zeichner="unknown",
        )
        self.assertFalse(Subscription.ByKeys(d.cdb_object_id, d.cdb_cpersno))
        PersonalSettings()["cs.documents.creation.autosubscribe"] = "1"
        d = operation(
            constants.kOperationNew,
            "document",
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
            zeichner="unknown",
        )
        self.assertTrue(Subscription.ByKeys(d.cdb_object_id, d.cdb_cpersno))


class Test_document_object_op(testcase.RollbackTestCase):
    """
    Base class for testing object operations.
    """

    def setUp(self):
        super(Test_document_object_op, self).setUp()
        categ = DocumentCategory.ByKeys(200)  # doc_approve
        self.doc = operation(
            constants.kOperationNew,
            "document",
            cdb_obsolete=1,
            pruefer="caddok",
            autoren="hinz, kunz",
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
            anlegetag=date(2021, 1, 1),
        )

    def tearDown(self):
        super(Test_document_object_op, self).tearDown()
        PersonalSettings().invalidate()


class Test_document_Modify(Test_document_object_op):
    """
    Test CDB_Modify operation for document class
    """

    def test_wf_init_on_change(self):
        """
        It is allowed to change the workflow in the initial state.
        """
        categ = DocumentCategory.ByKeys(322)
        d = operation(
            constants.kOperationModify,
            self.doc,
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
        )
        self.assertEqual(d.z_status, 0)
        self.assertEqual(d.z_art, categ.getWorkflow(""))

    def test_refuse_wf_change(self):
        """
        It is not allowed to change the workflow in a state != ``0``.
        """
        self.doc.ChangeState(100)
        categ = DocumentCategory.ByKeys(322)
        with self.assertRaises(ElementsError):
            operation(
                constants.kOperationModify,
                self.doc,
                z_categ1=categ.parent_id,
                z_categ2=categ.categ_id,
            )


class Test_document_Copy(Test_document_object_op):
    """
    Test CDB_Copy operation for document class
    """

    def test_attr_init(self):
        """
        Check if initial attributes are set and others are resetted
        """
        categ = DocumentCategory.ByKeys(322)
        d = operation(
            constants.kOperationCopy,
            self.doc,
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
        )
        self.assertEqual(d.z_status, 0)
        self.assertEqual(d.z_art, categ.getWorkflow(""))
        # cdb_obsolete and pruefer has to be resetted
        self.assertEqual(d.pruefer, "")
        self.assertEqual(d.cdb_obsolete, 0)
        self.assertEqual(d.autoren, auth.get_name())
        self.assertEqual(d.source_oid, self.doc.cdb_object_id)
        t = datetime.utcnow()
        self.assertEqual(d.anlegetag.year, t.year)
        self.assertEqual(d.anlegetag.month, t.month)
        self.assertEqual(d.anlegetag.day, t.day)

    def test_as_autosubscription(self):
        PersonalSettings()["cs.documents.creation.autosubscribe"] = "0"
        categ = DocumentCategory.ByKeys(322)
        d = operation(
            constants.kOperationCopy,
            self.doc,
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
        )
        self.assertFalse(Subscription.ByKeys(d.cdb_object_id, d.cdb_cpersno))
        PersonalSettings()["cs.documents.creation.autosubscribe"] = "1"
        d = operation(
            constants.kOperationCopy,
            self.doc,
            z_categ1=categ.parent_id,
            z_categ2=categ.categ_id,
        )
        self.assertTrue(Subscription.ByKeys(d.cdb_object_id, d.cdb_cpersno))

    def test_wsp_filename_naming(self):
        # With the standard naming convention wsp_filename defines
        # the name of a file
        self.doc.wsp_filename = "myfilename"
        s = BytesIO(b"Hello")
        args = {"cdbf_type": "JPG"}
        f = CDB_File.NewFromFile(self.doc.cdb_object_id, "", True, args, stream=s)
        self.assertEqual(f.cdbf_name, "myfilename.jpg")
        # The filename does not change if copying the doc
        PersonalSettings()[("cs.documents.clear_wsp_filename", "copy")] = "0"
        d = operation(constants.kOperationCopy, self.doc)
        copied_files = d.Files.Execute()
        self.assertEqual(len(copied_files), 1)
        self.assertEqual(copied_files[0].cdbf_name, "myfilename.jpg")

        PersonalSettings()[("cs.documents.clear_wsp_filename", "copy")] = "1"
        d = operation(constants.kOperationCopy, self.doc)
        self.assertEqual(d.wsp_filename, "")
        copied_files = d.Files.Execute()
        self.assertEqual(len(copied_files), 1)
        # Filename should something like D0000-.jpg
        self.assertNotEqual(copied_files[0].cdbf_name, "myfilename.jpg")


class Test_document_Index(Test_document_object_op):
    """
    Test CDB_Index operation for document class
    """

    def test_attr_init(self):
        """
        Check if initial attributes are set and others are resetted
        """
        d = operation(constants.kOperationIndex, self.doc)
        # cdb_obsolete and pruefer has to be resetted
        self.assertEqual(d.pruefer, "")
        self.assertEqual(d.cdb_obsolete, 0)
        # The author should stay
        self.assertEqual(d.autoren, self.doc.autoren)
        # anlegetag is the date of the first index
        self.assertEqual(d.anlegetag, self.doc.anlegetag)

    def test_as_subscription_behaviour(self):
        PersonalSettings()["cs.documents.creation.autosubscribe"] = "0"
        Subscription.subscribeToChannel(self.doc.cdb_object_id, "test.documents")
        d = operation(constants.kOperationIndex, self.doc)
        # Existing subscriptions should be copied
        self.assertTrue(Subscription.ByKeys(d.cdb_object_id, "test.documents"))
        self.assertFalse(Subscription.ByKeys(d.cdb_object_id, d.cdb_cpersno))

        PersonalSettings()["cs.documents.creation.autosubscribe"] = "1"
        d = operation(constants.kOperationIndex, self.doc)
        self.assertTrue(Subscription.ByKeys(d.cdb_object_id, d.cdb_cpersno))

    def test_wsp_filename_naming(self):
        # With the standard naming convention wsp_filename defines
        # the name of a file
        self.doc.wsp_filename = "myfilename"
        s = BytesIO(b"Hello")
        args = {"cdbf_type": "JPG"}
        f = CDB_File.NewFromFile(self.doc.cdb_object_id, "", True, args, stream=s)
        self.assertEqual(f.cdbf_name, "myfilename.jpg")
        # The filename does not change if copying the doc
        PersonalSettings()[("cs.documents.clear_wsp_filename", "index")] = "0"
        d = operation(constants.kOperationIndex, self.doc)
        copied_files = d.Files.Execute()
        self.assertEqual(len(copied_files), 1)
        self.assertEqual(copied_files[0].cdbf_name, "myfilename.jpg")

        PersonalSettings()[("cs.documents.clear_wsp_filename", "index")] = "1"
        d = operation(constants.kOperationIndex, self.doc)
        self.assertEqual(d.wsp_filename, "")
        copied_files = d.Files.Execute()
        self.assertEqual(len(copied_files), 1)
        # Filename should something like D0000-.jpg
        self.assertNotEqual(copied_files[0].cdbf_name, "myfilename.jpg")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
