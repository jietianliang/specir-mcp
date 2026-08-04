import pytest
from fastmcp import FastMCP

from specir.query.server import build
from specir.query.tools import TOOL_NAMES


@pytest.mark.anyio
async def test_server_has_exactly_six_tools():
    app = build()
    assert isinstance(app, FastMCP)
    names = {tool.name for tool in await app.list_tools()}
    assert names == set(TOOL_NAMES)
    assert len(names) == 6
    fetch = next(tool for tool in await app.list_tools() if tool.name == "specir_fetch")
    assert fetch.parameters["properties"]["xref_profile"]["default"] == "test_points"
