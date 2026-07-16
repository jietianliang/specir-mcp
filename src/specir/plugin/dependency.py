"""Dependency ordering for plugin manifests."""
from __future__ import annotations

from .schema import PluginManifest


def topological_sort(manifests: list[PluginManifest]) -> list[PluginManifest]:
    by_name = {manifest.name: manifest for manifest in manifests}
    missing = {
        dep for manifest in manifests for dep in manifest.depends if dep not in by_name
    }
    if missing:
        raise ValueError(f"missing plugin dependencies: {sorted(missing)}")
    output: list[PluginManifest] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"circular plugin dependency involving {name}")
        visiting.add(name)
        for dependency in by_name[name].depends:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        output.append(by_name[name])

    for plugin_name in by_name:
        visit(plugin_name)
    return output
