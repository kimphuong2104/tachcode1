from dataclasses import dataclass
from typing import Self, Any, Optional

import pytest

from cs.vp.bom.enhancement.plugin import AbstractRestPlugin, Dependencies
from cs.vp.bom.enhancement.register import ScopeType, PluginRegister
from cs.vp.bom.enhancement import FlatBomRestEnhancement
from cs.vp.bom.enhancement.tests.test_register import FakePluginRegister


class FakePluginContext(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginContext"

    def __init__(self, context: str) -> None:
        self.context: str = context

    def get_default_data(self) -> tuple[Any, Any]:
        return (self.context, None)

    @classmethod
    def create_for_default_data(
        cls, dependencies: Dependencies, **kwargs: Any
    ) -> Optional[Self]:
        if "only_for_context" in kwargs:
            return cls(kwargs["only_for_context"])
        return cls("Default context")

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        return cls(rest_data)

    def get_part_where_stmt_extension(self) -> Optional[str]:
        return self.context


class FakePluginUse(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginUse"
    DEPENDENCIES = (FakePluginContext,)

    def __init__(self, context_plugin: FakePluginContext) -> None:
        self.context_plugin = context_plugin

    def get_default_data(self) -> tuple[Any, Any]:
        return (f"Use: {self.context_plugin.context}", None)

    @classmethod
    def create_for_default_data(cls, dependencies, **kwargs):
        return cls(dependencies[FakePluginContext])

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies
    ) -> Optional[Self]:
        return cls(dependencies[FakePluginContext])

    def get_part_where_stmt_extension(self) -> Optional[str]:
        return self.context_plugin.context


@dataclass
class FakeRequest:
    json: dict[Any, Any]


class FakeEnhancement(FlatBomRestEnhancement):
    def __init__(self, scope: ScopeType):
        super().__init__(scope)
        self.register = FakePluginRegister()

    def get_plugin_register(self) -> PluginRegister:
        self.register.close_registration()
        return self.register


@pytest.fixture
def enhancement() -> FakeEnhancement:
    return FakeEnhancement("scope")


def test_create_from_rest(enhancement: FakeEnhancement) -> None:
    """dependency must be initialized with data from rest"""
    enhancement.register.register_plugin(FakePluginUse, "scope")
    request = FakeRequest({"bomEnhancementData": {"FakePluginContext": "contextData"}})

    enhancement.initialize_from_request(request)

    p = enhancement.plugins[FakePluginContext]
    assert isinstance(p, FakePluginContext)
    assert p.context == "contextData"
    assert (
        enhancement.get_part_where_stmt_extension() == "(contextData) AND (contextData)"
    )


def test_get_dependency_plugins(enhancement: FakeEnhancement) -> None:
    enhancement.register.register_plugin(FakePluginUse, "scope")
    request = FakeRequest({"bomEnhancementData": {"FakePluginContext": "contextData"}})
    enhancement.initialize_from_request(request)

    result = enhancement.get_dependency_plugins(FakePluginUse)

    assert FakePluginUse not in result
    assert FakePluginContext in result


def test_default_data(enhancement: FakeEnhancement) -> None:
    enhancement.register.register_plugin(FakePluginUse, "scope")

    enhancement.initialize_for_default_data()

    result = enhancement.get_plugins_default_data()

    default_value = result[enhancement.DEFAULT_ENHANCEMENT_KEY]
    assert default_value[FakePluginContext.DISCRIMINATOR] == "Default context"
    assert default_value[FakePluginUse.DISCRIMINATOR] == "Use: Default context"
    assert result[enhancement.DEFAULT_RESET_DATA_KEY] == {}


def test_default_data_with_kwarg(enhancement: FakeEnhancement) -> None:
    """check if kwargs are path through the plugin"""
    enhancement.register.register_plugin(FakePluginUse, "scope")
    context_value = "The Default Context from kwargs"
    enhancement.initialize_for_default_data(only_for_context=context_value)

    result = enhancement.get_plugins_default_data()
    default_value = result[enhancement.DEFAULT_ENHANCEMENT_KEY]

    assert default_value[FakePluginContext.DISCRIMINATOR] == context_value
    assert default_value[FakePluginUse.DISCRIMINATOR] == f"Use: {context_value}"
    assert result[enhancement.DEFAULT_RESET_DATA_KEY] == {}


def test_default_data_none(enhancement: FakeEnhancement) -> None:
    """no default data no key in result"""

    class FakePlugin(AbstractRestPlugin):
        @classmethod
        def create_for_default_data(cls, dependencies: Dependencies, **kwargs):
            return cls()

    enhancement.register.register_plugin(FakePlugin, "scope")
    enhancement.initialize_for_default_data()

    result = enhancement.get_plugins_default_data()
    assert result[enhancement.DEFAULT_RESET_DATA_KEY] == {}
    assert result[enhancement.DEFAULT_ENHANCEMENT_KEY] == {}


def test_manual_registered_plugin_for_default_data(
    enhancement: FakeEnhancement,
) -> None:
    """mixed register and manual added the same plugin"""

    class FakePlugin(AbstractRestPlugin):
        @classmethod
        def create_for_default_data(cls, dependencies: Dependencies, **kwargs):
            return cls()

    enhancement.register.register_plugin(FakePlugin, "scope")
    enhancement.add(FakePlugin())
    enhancement.initialize_for_default_data()

    result = enhancement.get_plugins_default_data()
    assert result[enhancement.DEFAULT_RESET_DATA_KEY] == {}
    assert result[enhancement.DEFAULT_ENHANCEMENT_KEY] == {}
