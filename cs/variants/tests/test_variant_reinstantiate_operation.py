# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
# pylint: disable=protected-access

from mock import MagicMock, patch

import cs
from cdb import testcase, ue
from cs.variants import Variant
from cs.vp.items import Item


def get_context_mock(max_bom_id=None):
    ctx_mock = MagicMock()
    ctx_mock.dialog.max_bom_id = max_bom_id
    return ctx_mock


class TestVariantReInstantiate(testcase.RollbackTestCase):
    @patch("cs.variants.api.check_classification_attributes")
    @patch("cs.variants.api.rebuild_instance")
    def test_one_variant_with_invalid_classification(self, mock_rebuild, mock_check):
        maxbom = Item.ByKeys(teilenummer="9508575", t_index="")
        self.assertIsNotNone(maxbom)
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        self.assertIsNotNone(variant)
        part = Item.ByKeys(teilenummer="9508577", t_index="")
        self.assertIsNotNone(part)

        ctx_mock = get_context_mock(maxbom.cdb_object_id)
        mock_check.return_value = False
        mock_rebuild.return_value = True

        try:
            cs.variants.items._reinstantiate_part_now([part], ctx_mock)
        except ue.Exception as ex:
            self.assertIn("Merkmale", str(ex))

        mock_check.assert_called_once()
        mock_rebuild.assert_not_called()
