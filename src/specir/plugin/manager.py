"""Entry-point based plugin discovery and dependency-aware loading."""
from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Iterable

from .dependency import topological_sort
from .schema import PluginManifest
from .state import LoadedPlugin, PluginState

log = logging.getLogger(__name__)


class PluginManager:
    def __init__(self, group: str = "specir.domains") -> None:
        self.group = group
        self._plugins: dict[str, LoadedPlugin] = {}

    def discover(self) -> list[tuple[PluginManifest, object]]:
        found: list[tuple[PluginManifest, object]] = []
        for entry_point in entry_points(group=self.group):
            try:
                loaded = entry_point.load()
                instance = loaded() if isinstance(loaded, type) else loaded
            except Exception as error:
                log.warning("ignoring plugin %s: %s", entry_point.name, error)
                continue
            manifest_raw = getattr(instance, "manifest", None)
            if isinstance(manifest_raw, PluginManifest):
                manifest = manifest_raw
            elif isinstance(manifest_raw, dict):
                manifest = PluginManifest.from_dict(manifest_raw)
            else:
                manifest = PluginManifest(
                    name=entry_point.name,
                    version=getattr(instance, "version", "0.0.0"),
                    capabilities=tuple(getattr(instance, "capabilities", ())),
                    depends=tuple(getattr(instance, "depends", ())),
                )
            found.append((manifest, instance))
        return found

    def load_all(
        self, discovered: Iterable[tuple[PluginManifest, object]] | None = None
    ) -> None:
        pairs = list(discovered if discovered is not None else self.discover())
        instances = {manifest.name: instance for manifest, instance in pairs}
        try:
            ordered = topological_sort([manifest for manifest, _ in pairs])
        except ValueError as error:
            for manifest, instance in pairs:
                self._plugins[manifest.name] = LoadedPlugin(
                    manifest, PluginState.FAILED, instance, [str(error)]
                )
            return
        for manifest in ordered:
            missing = [
                dependency for dependency in manifest.depends
                if self._plugins.get(dependency, None) is None
                or self._plugins[dependency].state == PluginState.FAILED
            ]
            state = PluginState.DEGRADED if missing else PluginState.OK
            errors = [f"unavailable dependencies: {missing}"] if missing else []
            self._plugins[manifest.name] = LoadedPlugin(
                manifest, state, instances[manifest.name], errors
            )

    def all(self) -> list[LoadedPlugin]:
        return list(self._plugins.values())

    def get(self, name: str) -> LoadedPlugin | None:
        return self._plugins.get(name)

    def status(self) -> dict[str, dict]:
        return {
            plugin.name: {
                "version": plugin.manifest.version,
                "state": plugin.state.value,
                "capabilities": list(plugin.manifest.capabilities),
                "errors": plugin.errors,
            }
            for plugin in self.all()
        }
