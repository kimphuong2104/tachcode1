# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests preview for parts
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import mock

from cdb.testcase import RollbackTestCase
from cdb.objects import operations
from cdb import constants

from cs import documents
import cs.vp.items.tests as common

# Exported objects
__all__ = []


class TestPreview(RollbackTestCase):
    def setUp(self):
        super(TestPreview, self).setUp()

        self.part = common.generateItem()
        self.doc_old = common.generateCADDocument(self.part)
        self.doc_new = operations.operation(
            constants.kOperationIndex,
            self.doc_old
        )
        self.doc_new.t_index = self.part.t_index
        self.doc_old.Reload()

    def test_preview_shows_new_index(self):
        # requery for the object, otherwise self.doc_old will be an old instance
        doc_old = documents.Document.ByKeys(self.doc_old.z_nummer, self.doc_old.z_index)
        doc_new = documents.Document.ByKeys(self.doc_new.z_nummer, self.doc_new.z_index)

        with mock.patch.object(doc_new, "GetPreviewFile", autospec=True) as mock_new:
            with mock.patch.object(doc_old, "GetPreviewFile", autospec=True) as mock_old:
                self.part.on_preview_now(None)

                self.assertFalse(mock_old.called)
                mock_new.assert_called_once_with()
