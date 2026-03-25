import logging
from dataclasses import dataclass
from unittest.mock import patch, MagicMock, Mock

import pytest

from cs.vp.variants.filter import CsVpVariantsProductContextPlugin, CsVpVariantsFilterPlugin, \
    CsVpVariantsAttributePlugin, CsVpVariantsFilterContextPlugin

THINK_ABOUT_IT_ = "discriminator changed, think about it!"


def test_product_context_plugin_dependencies():
    """context plugin has no dependencies"""
    assert CsVpVariantsProductContextPlugin.DEPENDENCIES == ()
    assert CsVpVariantsProductContextPlugin.DISCRIMINATOR == "cs.vp.variantFilterProductContext", THINK_ABOUT_IT_


def test_product_context_plugin_init():
    """all the different init calls"""
    plugin = CsVpVariantsProductContextPlugin("product_object_id")

    assert plugin.product_object_id == "product_object_id"

    with pytest.raises(ValueError) as ex:
        CsVpVariantsProductContextPlugin(None)
    assert str(ex.value) == "Need a product_object_id"


def test_product_context_plugin_from_rest():
    """create from valid rest data"""
    rest_data = {"product_object_id": "product_object_id"}

    plugin: CsVpVariantsProductContextPlugin = CsVpVariantsProductContextPlugin.create_from_rest_data(
        rest_data, {})

    assert plugin.product_object_id == "product_object_id"


def test_product_context_plugin_from_rest_no_product():
    """create from invalid rest data"""
    rest_data = {}

    with pytest.raises(KeyError):
        CsVpVariantsProductContextPlugin.create_from_rest_data(rest_data, {})


def test_product_context_plugin_from_rest_with_none_data():
    plugin = CsVpVariantsProductContextPlugin.create_from_rest_data(None, {})
    assert plugin is None


def test_pcp_get_default_data_no_product() -> None:
    """no product - no default data"""
    plugin = CsVpVariantsProductContextPlugin("123")
    plugin.product_object_id = None

    result = plugin.get_default_data()

    assert result == (None, None)


@patch("cs.vp.variants.filter.Product.ByKeys")
def test_pcp_get_default_data_unknown_product(product_bykeys_mock, caplog) -> None:
    """url parameter refer to a non-existing product"""
    product_bykeys_mock.return_value = None
    caplog.set_level(logging.INFO)

    plugin = CsVpVariantsProductContextPlugin("product123")

    result = plugin.get_default_data()
    assert result == (None, None)
    assert product_bykeys_mock.called
    product_bykeys_mock.assert_called_with(cdb_object_id="product123")
    last_log = caplog.messages[-1]
    assert plugin.product_object_id in last_log


@patch("cs.vp.variants.filter.Product.ByKeys")
def test_pcp_get_default_data_with_product(product_bykeys_mock) -> None:
    """url parameter refer to a existing product"""
    @dataclass
    class FakeProduct:
        def GetDescription(self):
            return "product description"

    product_bykeys_mock.return_value = FakeProduct()

    plugin = CsVpVariantsProductContextPlugin("product123")

    initial, reset = plugin.get_default_data()
    assert reset is None
    assert initial == {
        "product_object_id": "product123",
        "system:description": "product description"
    }
    assert product_bykeys_mock.called
    product_bykeys_mock.assert_called_with(cdb_object_id="product123")


def test_variant_filter_context_plugin_dependencies():
    assert CsVpVariantsFilterContextPlugin.DEPENDENCIES == (CsVpVariantsProductContextPlugin,)
    assert CsVpVariantsFilterContextPlugin.DISCRIMINATOR == "cs.vp.variantFilterContext", THINK_ABOUT_IT_


def test_variant_filter_context_plugin_init():
    """all the different init calls"""
    context_plugin = CsVpVariantsProductContextPlugin("adadf")

    # no plugin - no variant - no signature
    with pytest.raises(Exception):
        CsVpVariantsFilterContextPlugin(None)

    # no variant_id and no signature
    with pytest.raises(ValueError) as ex:
        CsVpVariantsFilterContextPlugin(context_plugin)

    assert str(ex.value) == "variant_id **or** signature is needed"

    # with both variant_id and signature
    with pytest.raises(ValueError) as ex:
        CsVpVariantsFilterContextPlugin(context_plugin, "1", "sig")

    assert str(ex.value) == "Only variant_id **or** signature is supported"

    # just variant_id
    plugin = CsVpVariantsFilterContextPlugin(context_plugin, variant_object_id="1")
    assert plugin.product_context_plugin == context_plugin
    assert plugin.variant_object_id == "1"

    # just signature
    plugin = CsVpVariantsFilterContextPlugin(context_plugin, signature="sig")
    assert plugin.signature == "sig"


def test_variant_filter_context_plugin_from_rest():
    """all the different create from rest calls"""
    rest_data = None
    dependencies = {
        CsVpVariantsProductContextPlugin: CsVpVariantsProductContextPlugin("product_object_id")}

    # no rest data - no instance
    p = CsVpVariantsFilterContextPlugin.create_from_rest_data(rest_data, dependencies)
    assert p is None

    # valid rest data - check if __init__ is called with values from rest data
    rest_data = {"variant_id": "x"}
    p: CsVpVariantsFilterContextPlugin = CsVpVariantsFilterContextPlugin.create_from_rest_data(rest_data,
                                                                                               dependencies)
    assert p.variant_object_id == "x"


@patch("cs.vp.variants.filter.Variant.ByKeys")
@patch("cs.vp.variants.filter.VariantBOMFilter")
@patch("cs.vp.variants.filter.VirtualVariantBOMFilter")
def test_variant_filter_context_plugin_correct_variant_filter(VirtualVariantBOMFilterMock, VariantBOMFilter,
                                                              VariantMock):
    class V:
        id = 1

    VariantMock.return_value = V
    dependencies = {
        CsVpVariantsProductContextPlugin: CsVpVariantsProductContextPlugin("product_object_id")}

    # with variant
    rest_data = {"variant_id": "x"}
    p: CsVpVariantsFilterContextPlugin = CsVpVariantsFilterContextPlugin.create_from_rest_data(rest_data,
                                                                                               dependencies)
    assert p.variant_filter is not None
    assert VariantMock.called
    VariantMock.assert_called_with(cdb_object_id="x")
    assert VariantBOMFilter.called
    VariantBOMFilter.assert_called_with("product_object_id", 1)

    # with signature
    rest_data = {"signature": "sig"}
    p: CsVpVariantsFilterContextPlugin = CsVpVariantsFilterContextPlugin.create_from_rest_data(rest_data,
                                                                                               dependencies)
    assert p.variant_filter is not None
    assert VirtualVariantBOMFilterMock.called
    VirtualVariantBOMFilterMock.assert_called_with("product_object_id", "sig")


@patch("cs.vp.variants.filter.CsVpVariantsFilterContextPlugin.__init__")
def test_variant_filter_context_plugin_create_for_default_data(plugin_init_mock):
    plugin_init_mock.return_value = None  # avoid TypeError: __init__() should return None, not 'MagicMock'
    # no product context plugin -> return None
    kwargs = {"bom_table_url": "adsadaf/?variant=2"}

    result = CsVpVariantsFilterContextPlugin.create_for_default_data({CsVpVariantsProductContextPlugin: None},
                                                                     **kwargs)
    assert result is None
    plugin_init_mock.assert_not_called()

    # no variant or signature in url -> return None
    kwargs = {"bom_table_url": "adsadaf/?xxx=2"}

    result = CsVpVariantsFilterContextPlugin.create_for_default_data({CsVpVariantsProductContextPlugin: {}},
                                                                     **kwargs)
    assert result is None
    plugin_init_mock.assert_not_called()

    # variant in url
    kwargs = {"bom_table_url": "adsadaf/?variant=2"}

    result = CsVpVariantsFilterContextPlugin.create_for_default_data(
        {CsVpVariantsProductContextPlugin: "plugin"},
        **kwargs)
    assert result is not None
    plugin_init_mock.assert_called_with("plugin", variant_object_id="2", signature=None)

    # signature in url
    kwargs = {"bom_table_url": "adsadaf/?signature=2"}

    result = CsVpVariantsFilterContextPlugin.create_for_default_data(
        {CsVpVariantsProductContextPlugin: "plugin"},
        **kwargs)
    assert result is not None
    plugin_init_mock.assert_called_with("plugin", variant_object_id=None, signature="2")

    # both signature and variant in url
    kwargs = {"bom_table_url": "adsadaf/?signature=2&variant=42"}

    result = CsVpVariantsFilterContextPlugin.create_for_default_data(
        {CsVpVariantsProductContextPlugin: "plugin"},
        **kwargs)
    assert result is not None
    plugin_init_mock.assert_called_with("plugin", variant_object_id="42", signature="2")


@patch("cs.vp.variants.filter.Variant.ByKeys")
def test_variant_filter_context_plugin_get_default_data(variant_bykeys_mock, caplog) -> None:
    plugin = CsVpVariantsFilterContextPlugin(None, "123", None)
    # now fake it
    plugin.variant_object_id = None

    assert plugin.get_default_data() == (None, None)


@patch("cs.vp.variants.filter.Variant.ByKeys")
def test_variant_filter_context_plugin_get_default_data_unknown_variant(variant_bykeys_mock,
                                                                          caplog) -> None:
    """url parameter refer to a non existing variant"""
    variant_bykeys_mock.return_value = None
    caplog.set_level(logging.INFO)

    plugin = CsVpVariantsFilterContextPlugin(None, "variant123", None)

    result = plugin.get_default_data()
    assert result == (None, None)
    assert variant_bykeys_mock.called
    variant_bykeys_mock.assert_called_with(cdb_object_id="variant123")
    last_log = caplog.messages[-1]
    assert plugin.variant_object_id in last_log


@patch("cs.vp.variants.filter.Variant.ByKeys")
def test_variant_filter_context_plugin_get_default_data_valid_variant(variant_bykeys_mock) -> None:
    """url parameter refer to a valid variant"""
    @dataclass
    class FakeVariant:
        name: str

        def GetDescription(self):
            return "variant description"

    fake_var = FakeVariant("Variant 123")
    variant_bykeys_mock.return_value = fake_var

    plugin = CsVpVariantsFilterContextPlugin(None, "variant123", None)

    initial_val, reset_val = plugin.get_default_data()
    assert reset_val is None

    assert initial_val == {
            "signature": None,
            "variant_id": "variant123",
            "system:description": "variant description",
            "name": "Variant 123"
    }

    assert variant_bykeys_mock.called
    variant_bykeys_mock.assert_called_with(cdb_object_id="variant123")


def test_variant_filter_context_plugin_get_default_data_only_signature() -> None:
    """no variant - only signature is returned"""
    plugin = CsVpVariantsFilterContextPlugin(None, None, "signature123")

    initial_val, reset_val = plugin.get_default_data()
    assert reset_val is None

    assert initial_val == {
        "signature": "signature123",
    }


def test_variant_filter_plugin_dependencies():
    assert CsVpVariantsFilterPlugin.DEPENDENCIES == (CsVpVariantsFilterContextPlugin,)
    assert CsVpVariantsFilterPlugin.DISCRIMINATOR == "cs.vp.variantFilter", THINK_ABOUT_IT_


def test_variant_filter_plugin_init():
    """all the different init calls"""
    context_plugin = CsVpVariantsProductContextPlugin("adadf")
    filter_context = CsVpVariantsFilterContextPlugin(context_plugin, "1")
    # no plugin
    with pytest.raises(ValueError) as ex:
        CsVpVariantsFilterPlugin(None)

    assert str(ex.value) == "filter_context_plugin can not be None"

    p = CsVpVariantsFilterPlugin(filter_context)
    assert p.variant_filter_context_plugin == filter_context


def test_variant_filter_plugin_from_rest():
    """all the different create from rest calls"""
    rest_data = None

    dependencies = {CsVpVariantsFilterContextPlugin: None}
    # no context - no instance
    p = CsVpVariantsFilterPlugin.create_from_rest_data(rest_data, dependencies)
    assert p is None

    product_plugin = CsVpVariantsProductContextPlugin("product_object_id")
    variant_context = CsVpVariantsFilterContextPlugin(product_plugin, "1")
    dependencies = {
        CsVpVariantsFilterContextPlugin: variant_context}

    # valid variant_filter_context - saved as property
    p: CsVpVariantsFilterPlugin = CsVpVariantsFilterPlugin.create_from_rest_data(rest_data, dependencies)
    assert p.variant_filter_context_plugin == variant_context


def test_variant_filter_plugin_filter_bom_items():
    context_plugin = CsVpVariantsProductContextPlugin("product_object_id")
    filter_context = CsVpVariantsFilterContextPlugin(context_plugin, "1")
    plugin = CsVpVariantsFilterPlugin(filter_context)

    class FilterFake:
        def eval_bom_item(self, item):
            return item is True

    filter_context._variant_filter = FilterFake()
    data = [False, True, True, False]

    result = plugin.filter_bom_item_records(data)
    assert result == [True, True]


def test_attribute_filter_plugin_dependencies():
    assert CsVpVariantsAttributePlugin.DEPENDENCIES == (CsVpVariantsFilterContextPlugin,)
    assert CsVpVariantsAttributePlugin.DISCRIMINATOR == "cs.vp.variantAttribute", THINK_ABOUT_IT_


def test_attribute_filter_plugin_init():
    """all the different init calls"""
    p = CsVpVariantsAttributePlugin()
    assert p.variant_filter_context_plugin is None

    mock = MagicMock()
    p = CsVpVariantsAttributePlugin(mock)
    assert p.variant_filter_context_plugin == mock


def test_attribute_filter_select_stmt():
    """table alias argument must be used in query"""
    plugin = CsVpVariantsAttributePlugin()

    result = plugin.get_bom_item_select_stmt_extension()
    assert plugin.BOM_ITEM_TABLE_ALIAS in result


def test_attribute_filter_additional_attributes():
    """eval_bom_item must be called"""

    # without variant_filter_plugin in_variant is always True
    plugin = CsVpVariantsAttributePlugin()

    bom_item = MagicMock()
    bom_item.has_predicates = 1
    result = plugin.get_additional_bom_item_attributes(bom_item)

    assert result == {"has_predicates": 1, "in_variant": True}

    # with variant_filter_plugin 'eval_bom_item' must be called

    filter_context = CsVpVariantsFilterContextPlugin(MagicMock(), "1")

    filter_mock = MagicMock()
    attrs = {"eval_bom_item.return_value": False}
    filter_mock.configure_mock(**attrs)
    filter_context._variant_filter = filter_mock

    plugin = CsVpVariantsAttributePlugin(filter_context)

    bom_item = MagicMock()
    bom_item.configure_mock(has_predicates=0)
    result = plugin.get_additional_bom_item_attributes(bom_item)

    assert result == {"has_predicates": 0, "in_variant": False}

    assert filter_mock.eval_bom_item.called
