# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import datetime

from cdb import ElementsError
from cdb.testcase import RollbackTestCase

from cs.vp.bom.tests import generateAssemblyComponent
from cs.vp.bom.tests import generateItem
from cs.vp.tests import test_utils


class TestEffectivity(RollbackTestCase):

    def test_effectivity_period(self):
        """
        Asserts that a bom item can be created if the start date of the effectivity period is BEFORE the
        end date.
        """

        bom = generateItem()
        child = generateItem()

        # From and to are different dates.
        bom_item = generateAssemblyComponent(
            bom,
            child,
            ce_valid_from=datetime.date(2021, 8, 1),
            ce_valid_to=datetime.date(2021, 8, 2)
        )

        self.assertIsNotNone(bom_item)

    def test_effectivity_period_same_day(self):
        """
        Asserts that a bom item can be created if the start date of the effectivity period is THE SAME as the
        end date.
        """

        bom = generateItem()
        child = generateItem()

        # From and to are different dates.
        bom_item = generateAssemblyComponent(
            bom,
            child,
            ce_valid_from=datetime.date(2021, 8, 1),
            ce_valid_to=datetime.date(2021, 8, 1)
        )

        self.assertIsNotNone(bom_item)

    def test_invalid_effectivity_period(self):
        """
        Asserts that an error is raised if the start date of the effectivity period is AFTER the end date.
        """

        bom = generateItem()
        child_1 = generateItem()

        expected_msg = str(test_utils.get_error_message("cdbvp_bom_invalid_effectivity_period"))

        with self.assertRaisesRegex(ElementsError, expected_msg):
            generateAssemblyComponent(
                bom,
                child_1,
                ce_valid_from=datetime.date(2021, 8, 2),
                ce_valid_to=datetime.date(2021, 8, 1)
            )
