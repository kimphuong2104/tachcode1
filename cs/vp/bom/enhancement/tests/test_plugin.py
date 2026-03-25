import pytest

from cs.vp.bom.enhancement.plugin import AbstractRestPlugin


def test_abstract_rest_create_from_rest_raises() -> None:
    plugin = AbstractRestPlugin()
    with pytest.raises(RuntimeError):
        plugin.create_from_rest_data(None, {})


def test_abstract_rest_create_for_default() -> None:
    plugin = AbstractRestPlugin()
    assert plugin.create_for_default_data({}) is None
