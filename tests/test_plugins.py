from specir.plugin import PluginManager, PluginManifest, PluginState
from specir.plugin.dependency import topological_sort


class Example:
    pass


def test_dependency_order():
    base = PluginManifest("base", "1.0")
    child = PluginManifest("child", "1.0", depends=("base",))
    assert [item.name for item in topological_sort([child, base])] == ["base", "child"]


def test_manager_loads_supplied_plugins():
    manager = PluginManager()
    manager.load_all([
        (PluginManifest("base", "1.0", capabilities=("parse",)), Example()),
        (PluginManifest("child", "1.0", depends=("base",)), Example()),
    ])
    assert manager.get("base").state == PluginState.OK
    assert manager.get("child").state == PluginState.OK
