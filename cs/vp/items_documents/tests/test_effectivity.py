# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import datetime

from cdb import constants, ElementsError
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase
from cs.documents import Document

from cs.vp import items
from cs.vp.items_documents import DocumentToPart
from cs.vp.tests import test_utils


class TestEffectivity(RollbackTestCase):

    def _create_part(self):
        item_args = dict(
            benennung="Blech",
            t_kategorie="Baukasten",
            t_bereich="Engineering",
            mengeneinheit="qm"
        )
        part = operation(
            constants.kOperationNew,
            items.Item,
            **item_args
        )
        self.assertIsNotNone(part, 'part could not be created!')
        return part

    def _create_document(self, title, part=None):
        create_args = {
            "titel": title,
            "z_nummer": Document.makeNumber(None),
            "z_index": "",
            "z_categ1": "142",
            "z_categ2": "153"
        }
        if part:
            create_args["teilenummer"] = part.teilenummer
            create_args["t_index"] = part.t_index
        doc = Document.Create(**create_args)
        self.assertIsNotNone(doc, 'document could not be created!')
        return doc

    def _create_reference(self, doc, part, valid_from, valid_to, kind=DocumentToPart.KIND_WEAK):
        create_args = {
            "z_nummer": doc.z_nummer,
            "z_index": doc.z_index,
            "teilenummer": part.teilenummer,
            "t_index": part.t_index,
            "kind": kind,
            "ce_valid_from": valid_from,
            "ce_valid_to": valid_to
        }
        reference = operation(
            constants.kOperationNew,
            DocumentToPart,
            **create_args
        )
        self.assertIsNotNone(doc, 'reference could not be created!')
        return reference

    def test_effectivity_period(self):
        """
        Asserts that a document reference can be created if the start date of the effectivity period is
        BEFORE the end date.
        """

        doc = self._create_document('Test Doc')
        part = self._create_part()

        reference = self._create_reference(
            doc,
            part,
            valid_from=datetime.date(2021, 8, 1),
            valid_to=datetime.date(2021, 8, 2))

        self.assertIsNotNone(reference)

    def test_effectivity_period_same_day(self):
        """
        Asserts that a document reference can be created if the start date of the effectivity period is
        THE SAME as the end date.
        """

        doc = self._create_document('Test Doc')
        part = self._create_part()

        reference = self._create_reference(
            doc,
            part,
            valid_from=datetime.date(2021, 8, 1),
            valid_to=datetime.date(2021, 8, 1))

        self.assertIsNotNone(reference)

    def test_invalid_effectivity_period(self):
        """
        Asserts that an error is raised if the start date of the effectivity period is AFTER the end date when
        creating a document reference.
        """

        doc = self._create_document('Test Doc')
        part = self._create_part()

        expected_msg = str(test_utils.get_error_message("cdbvp_bom_invalid_effectivity_period"))

        with self.assertRaisesRegex(ElementsError, expected_msg):
            self._create_reference(
                doc,
                part,
                valid_from=datetime.date(2021, 8, 2),
                valid_to=datetime.date(2021, 8, 1)
            )
