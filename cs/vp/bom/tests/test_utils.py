from dataclasses import dataclass
from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from cdb.testcase import rollback

from cs.vp.bom.web.bommanager.utils import StandardSiteFilter, OtherSiteTransparencyBehavior, \
    MatchSelectedSitesFilter, SiteFilterPurpose, get_site_bom_filter_class

from cs.vp.bom.web.bommanager import utils


@dataclass
class FakeComp:
    site_object_id: str | None
    baugruppe: str = ""
    b_index: str = ""
    position: str = ""
    _from_other_site: bool | None = None


def test_standard_site_filter_transparency_behavior() -> None:
    assert StandardSiteFilter.get_other_site_transparency_behavior() == OtherSiteTransparencyBehavior.DISPLAY_BOM_GREYED


def test_standard_site_filter_bom_filter() -> None:
    # return same list if no selected_sites
    flat_bom = [1, 2]
    selected_sites = []

    result = StandardSiteFilter.site_bom_filter(flat_bom, selected_sites)
    assert result == flat_bom

    # _from_other_site False if site_object_id is not set
    flat_bom = [FakeComp(None)]
    selected_sites = ["orgA"]

    result = StandardSiteFilter.site_bom_filter(flat_bom, selected_sites)

    assert len(result) == 1
    assert result[0]._from_other_site is False

    # _from_other_site True if site_object_id not in selected_sites
    flat_bom = [FakeComp("orgB")]
    selected_sites = ["orgA"]

    result = StandardSiteFilter.site_bom_filter(flat_bom, selected_sites)

    assert len(result) == 1
    assert result[0]._from_other_site is True

    # _from_other_site False if site_object_id in selected_sites
    flat_bom = [FakeComp("orgA")]
    selected_sites = ["orgA"]

    result = StandardSiteFilter.site_bom_filter(flat_bom, selected_sites)

    assert len(result) == 1
    assert result[0]._from_other_site is False


def test_match_selected_site_filter_transparency_behavior() -> None:
    assert MatchSelectedSitesFilter.get_other_site_transparency_behavior() == OtherSiteTransparencyBehavior.DISPLAY_ITEM_GREYED


@patch("cs.vp.bom.web.bommanager.utils.get_fallback_site")
def test_match_selected_site_filter_bom_filter(fallback_site_mock: MagicMock) -> None:
    # return same list if no selected_sites
    flat_bom: list[Any] = [1, 2]
    selected_sites: list[str] = []

    result = MatchSelectedSitesFilter.site_bom_filter(flat_bom, selected_sites)
    assert result == flat_bom

    # filter comp with same site on same position but different teilenummer
    selected_sites = ["orgA"]
    flat_bom = [FakeComp("orgB", "1", "A", "p1"), FakeComp("", "2", "A", "p1")]

    result = MatchSelectedSitesFilter.site_bom_filter(flat_bom, selected_sites)
    assert result == [FakeComp("", "2", "A", "p1", _from_other_site=False)]

    # same as above but with another LOAD_TREE_DATA purpose
    result = MatchSelectedSitesFilter.site_bom_filter(flat_bom, selected_sites,
                                                      purpose=SiteFilterPurpose.LOAD_TREE_DATA)
    assert result == [FakeComp("orgB", "1", "A", "p1", _from_other_site=True),
                      FakeComp("", "2", "A", "p1", _from_other_site=False)]

    # use fallback site with same position
    fallback_site_mock.return_value = "orgX"
    selected_sites = ["orgA"]
    flat_bom = [FakeComp("orgB", "1", "A", "p1"), FakeComp("orgX", "1", "A", "p1")]
    result = MatchSelectedSitesFilter.site_bom_filter(flat_bom, selected_sites)
    assert result == [FakeComp("orgX", "1", "A", "p1", _from_other_site=False)]


@patch("cs.vp.bom.web.bommanager.utils.get_fallback_site")
def test_match_selected_site_filter_alternative_with_fallback(fallback_site_mock: MagicMock) -> None:
    """
    If bom components have the same position number, but different sites,
    these components are considered as alternatives.
    If no alternative matches exactly to a selected site,
    the fallback site is kept, if exists.
    """
    fallback_site_mock.return_value = "orgY"
    selected_sites = ["orgA", "orgX"]
    flat_bom = [FakeComp("orgB", "1", "A", "p1"), FakeComp("orgY", "1", "A", "p1")]
    result = MatchSelectedSitesFilter.site_bom_filter(flat_bom, selected_sites)
    assert result == [FakeComp("orgY", "1", "A", "p1", _from_other_site=False)]


@patch("cs.vp.bom.web.bommanager.utils.util.get_prop")
def test_get_site_bom_filter_with_fallback(prop_mock: MagicMock) -> None:
    prop_mock.return_value = None
    old_filter_class = utils._filter_class
    utils._filter_class = None

    result = get_site_bom_filter_class()
    assert type(result) == type(StandardSiteFilter)
    assert type(utils._filter_class) == type(StandardSiteFilter)

    utils._filter_class = old_filter_class


@patch("cs.vp.bom.web.bommanager.utils.util.get_prop")
def test_get_site_bom_filter_with_bmsf(prop_mock: MagicMock) -> None:
    prop_mock.return_value = "cs.vp.bom.web.bommanager.utils.MatchSelectedSitesFilter"
    old_filter_class = utils._filter_class
    utils._filter_class = None

    result = get_site_bom_filter_class()
    assert type(result) == type(MatchSelectedSitesFilter)
    assert type(utils._filter_class) == type(MatchSelectedSitesFilter)

    utils._filter_class = old_filter_class


@patch("cs.vp.bom.web.bommanager.utils.util.get_prop")
def test_get_site_bom_filter_raise(prop_mock: MagicMock, caplog: MagicMock) -> None:
    prop_mock.return_value = "cs.vp.bom.NotExistingClass"
    old_filter_class = utils._filter_class
    utils._filter_class = None

    with pytest.raises(ImportError):
        get_site_bom_filter_class()

    # check the last message
    last_log = caplog.messages[-1]
    assert "bmsf" in last_log
    assert "cs.vp.bom.NotExistingClass" in last_log

    utils._filter_class = old_filter_class
