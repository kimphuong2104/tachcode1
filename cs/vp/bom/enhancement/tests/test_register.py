import pytest

from cs.vp.bom.enhancement.plugin import AbstractRestPlugin
from cs.vp.bom.enhancement.register import (
    PluginRegisterData,
    PluginRegister,
    BomTableScope,
)


class FakePluginRegister(PluginRegister):
    def __new__(cls):
        return object.__new__(cls)


class FakePluginOne(AbstractRestPlugin):
    DISCRIMINATOR = "fake_discriminator"


class FakePluginTwo(AbstractRestPlugin):
    DISCRIMINATOR = "fake_discriminator"


class FakePluginContext(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginContext"


class FakePluginUse(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginUse"
    DEPENDENCIES = (FakePluginContext,)


class FakePluginUse2(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginUse2"
    DEPENDENCIES = (FakePluginContext,)


class FakePluginContextCircular(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginContextCircular"
    # DEPENDENCIES = (FakePluginUseCircular,) has to be defined later class not defined until now


class FakePluginUseCircular(AbstractRestPlugin):
    DISCRIMINATOR = "FakePluginUseCircular"
    DEPENDENCIES = (FakePluginContextCircular,)


FakePluginContextCircular.DEPENDENCIES = (FakePluginUseCircular,)


@pytest.fixture
def plugin_register() -> PluginRegister:
    return FakePluginRegister()


def test_closed_registration(plugin_register: PluginRegister) -> None:
    plugin_register.close_registration()

    with pytest.raises(RuntimeError):
        plugin_register.register_plugin(FakePluginUse, "scope")

    with pytest.raises(RuntimeError):
        plugin_register.unregister_plugin(FakePluginUse, "scope")


def test_multiple_registration(plugin_register: PluginRegister) -> None:
    plugin_register.register_plugin(
        FakePluginOne,
        BomTableScope.DIFF_LOAD,
    )
    plugin_register.register_plugin(
        FakePluginTwo,
        BomTableScope.DIFF_LOAD,
    )
    plugin_register.register_plugin(
        FakePluginOne,
        BomTableScope.DIFF_LOAD,
    )
    plugin_register.close_registration()

    assert len(plugin_register.plugin_list) == 2

    p1 = PluginRegisterData(BomTableScope.DIFF_LOAD, FakePluginOne)
    p2 = PluginRegisterData(BomTableScope.DIFF_LOAD, FakePluginTwo)
    assert p1 in plugin_register
    assert p2 in plugin_register


def test_multiple_registration_different_scopes(
    plugin_register: PluginRegister,
) -> None:
    """test with different scopes"""

    plugin_register.register_plugin(FakePluginOne, BomTableScope.DIFF_LOAD)
    plugin_register.register_plugin(FakePluginOne, BomTableScope.INIT)
    plugin_register.register_plugin(FakePluginTwo, BomTableScope.DIFF_LOAD)
    plugin_register.register_plugin(FakePluginTwo, BomTableScope.INIT)
    plugin_register.close_registration()

    assert len(plugin_register.plugin_list) == 4

    p1 = PluginRegisterData(BomTableScope.DIFF_LOAD, FakePluginOne)
    p2 = PluginRegisterData(BomTableScope.DIFF_LOAD, FakePluginTwo)
    p3 = PluginRegisterData(BomTableScope.INIT, FakePluginOne)
    p4 = PluginRegisterData(BomTableScope.INIT, FakePluginTwo)
    assert p1 in plugin_register
    assert p2 in plugin_register
    assert p3 in plugin_register
    assert p4 in plugin_register


def test_registration_with_lists(plugin_register: PluginRegister) -> None:
    """test with list of scopes"""
    plugin_register.register_plugin(
        FakePluginOne, [BomTableScope.DIFF_LOAD, BomTableScope.INIT]
    )
    plugin_register.close_registration()

    p1 = PluginRegisterData(BomTableScope.DIFF_LOAD, FakePluginOne)
    p2 = PluginRegisterData(BomTableScope.INIT, FakePluginOne)

    assert len(plugin_register.plugin_list) == 2

    assert p1 in plugin_register
    assert p2 in plugin_register


def test_registration_with_new_scope(plugin_register: PluginRegister) -> None:
    """test with predefined and new scopes"""
    plugin_register.register_plugin(
        FakePluginOne, ["MyScopeA", "MyScopeB", BomTableScope.DIFF_LOAD]
    )
    plugin_register.close_registration()

    p1 = PluginRegisterData("MyScopeA", FakePluginOne)
    p2 = PluginRegisterData("MyScopeB", FakePluginOne)
    p3 = PluginRegisterData(BomTableScope.DIFF_LOAD, FakePluginOne)

    assert len(plugin_register.plugin_list) == 3

    assert p1 in plugin_register
    assert p2 in plugin_register
    assert p3 in plugin_register


def test_register_with_dependencies(plugin_register: PluginRegister) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginContext)

    assert p1 in plugin_register
    assert p2 in plugin_register


def test_register_with_circular_dependencies(plugin_register: PluginRegister) -> None:
    plugin_register.register_plugin(FakePluginUseCircular, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUseCircular)
    p2 = PluginRegisterData("scope", FakePluginContextCircular)

    assert p1 in plugin_register
    assert p2 in plugin_register


def test_get_plugin_data(plugin_register: PluginRegister) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.close_registration()

    p = plugin_register.get_plugin_data(FakePluginContext, "scope")
    assert p is not None
    assert p.plugin_cls == FakePluginContext
    assert p.scope == "scope"

    p = plugin_register.get_plugin_data(FakePluginContext, "unknown_scope")
    assert p is None

    p = plugin_register.get_plugin_data(FakePluginOne, "scope")
    assert p is None


def test_dependency_walker(plugin_register: PluginRegister) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.close_registration()

    generator = plugin_register.dependency_reverse_walker("scope")
    p = next(generator)
    assert p.plugin_cls == FakePluginContext
    p = next(generator)
    assert p.plugin_cls == FakePluginUse

    # only 2 plugins expected
    with pytest.raises(StopIteration):
        next(generator)


def test_unregister_with_dependencies_with_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.unregister_plugin(FakePluginUse, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 not in plugin_register


def test_unregister_with_dependencies_with_multiple_scopes(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.unregister_plugin(FakePluginUse, ["scope", "abc"])
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 not in plugin_register


def test_unregister_with_dependencies_without_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.unregister_plugin(FakePluginUse)
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 not in plugin_register


def test_unregister_plugin_is_a_dependency_with_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.unregister_plugin(FakePluginContext, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginContext)

    assert p1 in plugin_register
    assert p2 in plugin_register


def test_unregister_plugin_is_a_dependency_without_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.unregister_plugin(FakePluginContext)
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginContext)

    assert p1 in plugin_register
    assert p2 in plugin_register


def test_unregister_with_dependencies_from_multiple_only_one_with_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.register_plugin(FakePluginUse2, "scope")
    plugin_register.unregister_plugin(FakePluginUse, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginUse2)
    p_dep = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 in plugin_register
    assert p_dep in plugin_register


def test_unregister_with_dependencies_from_multiple_all_with_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.register_plugin(FakePluginUse2, "scope")
    plugin_register.unregister_plugin(FakePluginUse, "scope")
    plugin_register.unregister_plugin(FakePluginUse2, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginUse2)
    p_dep = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 not in plugin_register
    assert p_dep not in plugin_register


def test_unregister_with_dependencies_from_multiple_only_one_without_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.register_plugin(FakePluginUse2, "scope")
    plugin_register.unregister_plugin(FakePluginUse2)
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginUse2)
    p_dep = PluginRegisterData("scope", FakePluginContext)

    assert p1 in plugin_register
    assert p2 not in plugin_register
    assert p_dep in plugin_register


def test_unregister_with_dependencies_from_multiple_all_without_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.register_plugin(FakePluginUse2, "scope")
    plugin_register.unregister_plugin(FakePluginUse2)
    plugin_register.unregister_plugin(FakePluginUse)
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginUse2)
    p_dep = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 not in plugin_register
    assert p_dep not in plugin_register


def test_unregister_before_register_with_dependencies_from_multiple_with_scope(
    plugin_register: PluginRegister,
) -> None:
    plugin_register.unregister_plugin(FakePluginUse, "scope")
    plugin_register.register_plugin(FakePluginUse, "scope")
    plugin_register.register_plugin(FakePluginUse2, "scope")
    plugin_register.close_registration()

    p1 = PluginRegisterData("scope", FakePluginUse)
    p2 = PluginRegisterData("scope", FakePluginUse2)
    p_dep = PluginRegisterData("scope", FakePluginContext)

    assert p1 not in plugin_register
    assert p2 in plugin_register
    assert p_dep in plugin_register
