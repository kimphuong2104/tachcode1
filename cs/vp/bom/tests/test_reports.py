from unittest.mock import patch, MagicMock

from cs.vp.bom.reports import BOMComparison, BOMComparisonSitePlugin


def test_bom_comparison_site_plugin_no_site() -> None:
    plugin = BOMComparisonSitePlugin()
    result = plugin.get_bom_item_where_stmt_extension()

    assert result == "1=1"


def test_bom_comparison_site_plugin_with_site() -> None:
    plugin = BOMComparisonSitePlugin("SiteA")
    result = plugin.get_bom_item_where_stmt_extension()

    assert result == "(site_object_id='SiteA' or site_object_id='' or site_object_id is null)"


@patch("cs.vp.bom.reports.bomqueries.flat_bom")
def test_get_and_filter_flat_bom_no_site(flat_bom_mock: MagicMock) -> None:
    """migration test during enhancement integration

    Just to test if flat_bom is called with enhancement
    """
    bom = BOMComparison()

    bom._get_and_filter_flat_bom_if_present("A", "B")

    assert flat_bom_mock.call_count == 2  # call_args_list

    first_call = flat_bom_mock.call_args_list[0]
    assert "bom_enhancement" in first_call.kwargs

    second_call = flat_bom_mock.call_args_list[1]
    assert "bom_enhancement" in second_call.kwargs


@patch("cs.vp.bom.reports.bomqueries.flat_bom")
def test_get_and_filter_flat_bom_with_site(flat_bom_mock: MagicMock) -> None:
    """migration test during enhancement integration

    Just to test if flat_bom is called with enhancement
    """
    bom = BOMComparison()
    bom.addtl_filter["site_object_id"] = "TheSite"

    bom._get_and_filter_flat_bom_if_present("A", "B")

    assert flat_bom_mock.call_count == 2  # call_args_list

    first_call = flat_bom_mock.call_args_list[0]
    assert "bom_enhancement" in first_call.kwargs

    second_call = flat_bom_mock.call_args_list[1]
    assert "bom_enhancement" in second_call.kwargs
