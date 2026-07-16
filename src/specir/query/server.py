"""Five-tool FastMCP server for SpecIR."""
from __future__ import annotations

from fastmcp import FastMCP

from specir.plugin import PluginManager
from specir.query.tools import TOOL_NAMES, register_tools


def build(name: str = "specir-mcp") -> FastMCP:
    manager = PluginManager()
    manager.load_all()
    app = FastMCP(
        name=name,
        instructions=(
            "Data-neutral SpecIR query server. Use resolve for exact identifiers, "
            "fetch for canonical UIDs, explain for entity-plus-section views, "
            "search for discovery, and status for coverage. "
            "A no-data response indicates extraction coverage, not necessarily "
            "absence from the user's source document."
        ),
    )
    registered = register_tools(app, manager)
    assert set(registered) == set(TOOL_NAMES)
    return app


def main() -> None:
    build().run()


mcp = build()


if __name__ == "__main__":
    main()
