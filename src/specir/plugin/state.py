from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .schema import PluginManifest


class PluginState(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    state: PluginState
    instance: Any = None
    errors: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.manifest.name
