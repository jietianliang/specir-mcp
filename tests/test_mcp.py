import pytest
from fastmcp import FastMCP

from specir.query.server import build
from specir.query.tools import TOOL_NAMES


@pytest.mark.anyio
async def test_server_has_exactly_five_tools():
    app = build()
    assert isinstance(app, FastMCP)
    names = {tool.name for tool in await app.list_tools()}
    assert names == set(TOOL_NAMES)
