"""Stable five-tool facade over :class:`SpecIRQueryEngine`."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .engine import SpecIRQueryEngine

TOOL_NAMES = (
    "specir_resolve",
    "specir_fetch",
    "specir_explain",
    "specir_search",
    "specir_status",
)


def _engine() -> SpecIRQueryEngine | None:
    value = os.environ.get("SPEC_IR_DB")
    if not value:
        return None
    path = Path(value).expanduser()
    return SpecIRQueryEngine(path) if path.is_file() else None


def _no_engine() -> dict[str, Any]:
    return {
        "result": None,
        "_meta": {
            "coverage": "no-engine",
            "warning": "set SPEC_IR_DB to a generated or user-owned SpecIR database",
        },
    }


def resolve(kind: str, id: str, spec: str = "auto") -> dict[str, Any]:
    engine = _engine()
    return engine.resolve(kind, id, spec) if engine else _no_engine()


def fetch(uid: str, include_xrefs: bool = False) -> dict[str, Any]:
    engine = _engine()
    return engine.fetch(uid, include_xrefs) if engine else _no_engine()


def explain(
    name: str, kind: str = "command", spec: str = "auto"
) -> dict[str, Any]:
    engine = _engine()
    return engine.explain(name, kind, spec) if engine else _no_engine()


def search(
    query: str, spec: str | None = None, limit: int = 10,
    mode: str = "hybrid",
) -> dict[str, Any]:
    engine = _engine()
    return engine.search(query, spec, limit, mode) if engine else _no_engine()


def status(manager: Any = None) -> dict[str, Any]:
    engine = _engine()
    payload = {
        "plugins": manager.status() if manager is not None else {},
        "tools": list(TOOL_NAMES),
    }
    if engine is None:
        payload["db"] = None
        payload["_meta"] = _no_engine()["_meta"]
    else:
        db_status = engine.status()
        payload["db"] = db_status["result"]
        payload["_meta"] = db_status["_meta"]
    return payload


def dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def register_tools(mcp: Any, manager: Any = None) -> list[str]:
    @mcp.tool()
    def specir_resolve(kind: str, id: str, spec: str = "auto") -> str:
        """Resolve an exact domain entity, section, table, or figure."""
        return dumps(resolve(kind, id, spec))

    @mcp.tool()
    def specir_fetch(uid: str, include_xrefs: bool = False) -> str:
        """Fetch an entity by canonical UID, optionally with graph edges."""
        return dumps(fetch(uid, include_xrefs))

    @mcp.tool()
    def specir_explain(
        name: str, kind: str = "command", spec: str = "auto"
    ) -> str:
        """Combine a named entity with its defining section."""
        return dumps(explain(name, kind, spec))

    @mcp.tool()
    def specir_search(
        query: str, spec: str | None = None, limit: int = 10,
        mode: str = "hybrid",
    ) -> str:
        """Search structured entities or raw passages."""
        return dumps(search(query, spec, limit, mode))

    @mcp.tool()
    def specir_status() -> str:
        """Report plugin state and database coverage."""
        return dumps(status(manager))

    return list(TOOL_NAMES)
