#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import openpyxl

from cs.tools.powerreports import XMLReportTemplate
from cs.variants import Variant
from cs.variants.reports import VariantBOMComparison
from cs.vp.bom import Item


def get_report_link(teilenummer: str, t_index: str = "") -> str:
    return (
        f"cdb:///byname/classname/part/CDB_ShowObject/batch"
        f"?teile_stamm.teilenummer={teilenummer}&teile_stamm.t_index={t_index} "
        f"cdb:texttodisplay:{teilenummer}"
    )


class DialogMock(dict[str, Any]):
    def __init__(self) -> None:
        super().__init__()

    def get_attribute_names(self):
        return self.keys()


class MockedContext:
    """cloned from cs.powerreports"""

    def __init__(self, max_bom_id=None):
        self.dialog = DialogMock()

    def url(self, link):
        assert isinstance(link, str), "url link is type string"

    def file(self, fname):
        assert os.stat(fname).st_size != 0, "Template file is empty"
        os.remove(fname)

    def upload_to_client(
        self, srv_filename, client_filename=None, delete_file_after_upload=1
    ):
        assert os.stat(srv_filename).st_size != 0, "XML zip file is empty"
        os.remove(srv_filename)


def assert_comparison_common(template_object_id: str) -> None:
    """test all the things which are identical in both languages"""
    variant_a = Variant.ByKeys(
        variability_model_id="1771fe02-f5e3-11eb-923d-f875a45b4131", id="1"
    )
    assert variant_a is not None
    variant_b = Variant.ByKeys(
        variability_model_id="1771fe02-f5e3-11eb-923d-f875a45b4131", id="2"
    )
    assert variant_b is not None
    maxbom = Item.ByKeys(cdb_object_id="8f2354cb-fc0a-11eb-923e-f875a45b4131")
    assert maxbom is not None

    ctx = MockedContext()
    ctx.objects = [variant_a, variant_b]
    ctx.dialog["max_bom_id"] = maxbom.cdb_object_id

    template = XMLReportTemplate.ByKeys(cdb_object_id=template_object_id)
    assert template is not None

    result = Variant.generate_report(template, ctx)
    # result is a list with files. The files are not deleted automatically
    assert len(result) == 1
    the_result_file = Path(result[0])
    assert the_result_file.exists()

    workbook = openpyxl.load_workbook(the_result_file)
    maxbom_sheet = workbook["MaxBOM"]
    vba_guard = maxbom_sheet["F2"].value
    assert vba_guard == "1"

    assert maxbom_sheet["B5"].value == maxbom.teilenummer
    assert maxbom_sheet["B6"].value is None

    # Variant list count
    assert maxbom_sheet["T12"].value == 1
    assert maxbom_sheet["T13"].value == 2
    assert maxbom_sheet["U12"].value == variant_a.id
    assert maxbom_sheet["U13"].value == variant_b.id

    the_result_file.unlink()


def test_call_comparison_en() -> None:
    assert_comparison_common("53ec044e-3cb4-11ec-b976-98fa9bf98f6d")


def test_call_comparison_de() -> None:
    assert_comparison_common("46bc1bea-3cb4-11ec-b976-98fa9bf98f6d")


def assert_hierarchical_common(template_object_id: str) -> None:
    variant_a = Variant.ByKeys(
        variability_model_id="1771fe02-f5e3-11eb-923d-f875a45b4131", id="1"
    )
    assert variant_a is not None
    maxbom = Item.ByKeys(cdb_object_id="8f2354cb-fc0a-11eb-923e-f875a45b4131")
    assert maxbom is not None

    ctx = MockedContext()
    ctx.objects = [variant_a]
    ctx.dialog["max_bom_id"] = maxbom.cdb_object_id

    template = XMLReportTemplate.ByKeys(cdb_object_id=template_object_id)
    assert template is not None

    result = Variant.generate_report(template, ctx)
    # result is a list with files. The files are not deleted automatically
    assert len(result) == 1
    the_result_file = Path(result[0])
    assert the_result_file.exists()

    the_result_file.unlink()


def test_call_hierarchical_en() -> None:
    assert_hierarchical_common("17dffeb5-3bf8-11ec-b976-98fa9bf98f6d")


def test_call_hierarchical_de() -> None:
    assert_hierarchical_common("0927ba75-3bf8-11ec-b976-98fa9bf98f6d")


@dataclass
class ParentObject:
    parent_object: Any

    def getObject(self):
        return self.parent_object


def assert_result(
    result: list[Any],
    expected_result: list[tuple[int, str]],
    keys_to_check: tuple[str, str],
) -> None:
    for each_result in zip(result, expected_result):
        result_tuple = tuple(each_result[0][key] for key in keys_to_check)
        assert result_tuple == each_result[1]


@patch("cs.variants.reports.powerreports.ReportDataList")
@patch("cs.variants.reports.powerreports.ReportData")
def test_comparison_get_data(data_mock: MagicMock, data_list_mock: MagicMock) -> None:
    """
    Comparison must use the imprecise profile 'latest_working'

    Use Product MIXED_IMPR_PRESIZE

    There are no selection condition on any assembly item.
    This test does not test the correct diff but only the correct usage of the imprecise profile
    """
    data_list_mock.side_effect = lambda x: []
    data_mock.side_effect = lambda x, y: {}

    variant_a = Variant.ByKeys(
        variability_model_id="d0e236e1-edaa-11ed-b5eb-f875a45b4131", id="1"
    )
    assert variant_a is not None
    variant_b = Variant.ByKeys(
        variability_model_id="d0e236e1-edaa-11ed-b5eb-f875a45b4131", id="2"
    )
    assert variant_b is not None
    maxbom = Item.ByKeys(cdb_object_id="8abc0e56-edaa-11ed-8dd1-f875a45b4131")
    assert maxbom is not None

    provider = VariantBOMComparison()
    result = provider.getData(
        [ParentObject(variant_a), ParentObject(variant_b)],
        {"max_bom_id": maxbom.cdb_object_id},
    )

    keys_to_check = (
        "cdbxml_level",
        "item_hyperlink",
    )

    expected_result = [
        (1, get_report_link("9508670")),
        (2, get_report_link("9508671")),
        (3, get_report_link("9508672")),
        (3, get_report_link("9508673")),
        (2, get_report_link("9508674")),
        (3, get_report_link("9508675")),
        (3, get_report_link("9508676")),
        (1, get_report_link("9508677")),
        (2, get_report_link("9508678")),
        (3, get_report_link("9508679")),
        (3, get_report_link("9508680")),
        # 'a' is the latest_working index; no index is 'as_saved'
        (2, get_report_link("9508681", "a")),
        (3, get_report_link("9508682")),
        (3, get_report_link("9508683")),
    ]

    assert_result(result, expected_result, keys_to_check)


@patch("cs.variants.reports.powerreports.ReportDataList")
@patch("cs.variants.reports.powerreports.ReportData")
def test_menge(data_mock: MagicMock, data_list_mock: MagicMock) -> None:
    """
    E073262 Report variant BOM comparison does not take into account dynamic quantity
    due to rules on occurrence

    VariabilityModel: VAR_TEST_REINSTANTIATE
    MaxBOM: 9508575
    """
    data_list_mock.side_effect = lambda x: []
    data_mock.side_effect = lambda x, y: {}

    variant_a = Variant.ByKeys(
        variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
    )
    assert variant_a is not None
    variant_b = Variant.ByKeys(
        variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="2"
    )
    assert variant_b is not None
    maxbom = Item.ByKeys(cdb_object_id="d98e5c4f-23ff-11eb-9218-24418cdf379c")
    assert maxbom is not None

    provider = VariantBOMComparison()
    result = provider.getData(
        [ParentObject(variant_a), ParentObject(variant_b)],
        {"max_bom_id": maxbom.cdb_object_id},
    )

    keys_to_check = (
        "menge",
        "item_hyperlink",
        "difference",
        "difference_en",
        "varianteA",
        "varianteB",
    )

    expected_result = [
        (1, get_report_link("9508576"), "Vorkommen", "found", 0, 1),
        (1, get_report_link("9508579"), "keine", "none", 1, 1),
        (1, get_report_link("9508582"), "Vorkommen", "found", 0, 1),
        (2, get_report_link("9508583"), "Vorkommen", "found", 1, 2),
        (2, get_report_link("9508580"), "Vorkommen", "found", 1, 2),
        (2, get_report_link("9508581"), "Vorkommen", "found", 0, 1),
        (1, get_report_link("9508584"), "keine", "none", 1, 1),
        (2, get_report_link("9508585"), "Vorkommen", "found", 1, 2),
    ]

    assert_result(result, expected_result, keys_to_check)
