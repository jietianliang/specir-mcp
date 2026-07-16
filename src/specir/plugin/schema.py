"""Plugin manifest contract."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    kind: str = "domain"
    api_version: str = "1.0"
    core_api_range: str = ">=1.0,<2.0"
    spec_name: str = ""
    description: str = ""
    capabilities: tuple[str, ...] = ()
    depends: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> "PluginManifest":
        unknown = set(raw) - {
            "name", "version", "kind", "api_version", "core_api_range",
            "spec_name", "description", "capabilities", "depends",
        }
        if unknown:
            raise ValueError(f"unknown manifest keys: {sorted(unknown)}")
        if raw.get("kind", "domain") not in {"domain", "infra"}:
            raise ValueError("kind must be domain or infra")
        data = dict(raw)
        data["capabilities"] = tuple(data.get("capabilities", ()))
        data["depends"] = tuple(data.get("depends", ()))
        return cls(**data)
