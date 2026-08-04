import json
import sqlite3

import pytest

from specir.demo.builder import build_demo
from specir.query.engine import SpecIRQueryEngine
from specir.query import tools


@pytest.fixture()
def demo(tmp_path):
    path = build_demo(tmp_path / "demo.db")
    engine = SpecIRQueryEngine(path)
    yield path, engine
    engine.close()


def test_demo_resolve_fetch_explain_search_status(demo):
    _, engine = demo
    command = engine.resolve("command", "A1h")
    assert command["result"]["name"] == "Read Telemetry"
    assert command["_meta"]["spec_revision"] == "1.0"

    fetched = engine.fetch("acme-device:2.1", include_xrefs=True)
    assert fetched["result"]["title"] == "Read Telemetry command"
    assert fetched["xrefs"]["outgoing"]
    assert fetched["related_entities"]
    assert fetched["xrefs_raw"]["profile"] == "test_points"
    assert [item["uid"] for item in fetched["xrefs_raw"]["suppressed_references"]] == [
        "acme-device:1"
    ]

    explained = engine.explain("Read Telemetry", "command")
    assert explained["result"]["section"]["uid"] == "acme-device:2.1"
    assert explained["result"]["related_entities"]

    searched = engine.search("telemetry", spec="acme-device")
    assert any(item["uid"] == "acme-device:2.1" for item in searched["result"])

    raw = engine.search("temperature", spec="acme-device", mode="raw_linked")
    assert raw["result"][0]["source"] == "passage"

    status = engine.status()["result"]
    assert status["documents"] == 1
    assert status["entities_by_kind"]["command"] == 1


def test_product_related_view_and_typed_edges(demo):
    _, engine = demo
    command = engine.fetch("acme-device:command:a1h", include_xrefs=True)
    assert any(
        item["uid"] == "acme-device:2.1"
        and item["relation_type"] == "defines"
        for item in command["related_entities"]
    )
    assert all(item["uid"] != "acme-device:1" for item in command["related_entities"])

    generic = engine.fetch(
        "acme-device:2.1", include_xrefs=True, xref_profile="generic"
    )
    assert any(item["uid"] == "acme-device:1" for item in generic["xrefs_raw"]["outgoing"])
    assert all(item["uid"] != "acme-device:1" for item in generic["related_entities"])

    feature = engine.fetch("acme-device:feature:01h", include_xrefs=True)
    assert {
        (item["type"], item["relation_type"])
        for item in feature["related_entities"]
    } >= {("section", "defines"), ("table", "listed_in")}

    field = engine.fetch("acme-device:field:mode", include_xrefs=True)
    assert any(
        item["uid"] == "acme-device:register:ctrl"
        and item["relation_type"] == "member_of"
        for item in field["related_entities"]
    )

    section = engine.fetch("acme-device:2.1", include_xrefs=True)
    assert any(
        item["uid"] == "acme-device:status:01h"
        and item["relation_type"] == "mentions_status"
        for item in section["related_entities"]
    )
    both = engine.fetch(
        "acme-device:2.1", include_xrefs=True, xref_direction="both"
    )
    assert any(item["uid"] == "acme-device:1" for item in both["xrefs_raw"]["incoming"])


def test_tool_facade_and_json(demo, monkeypatch):
    path, _ = demo
    monkeypatch.setenv("SPEC_IR_DB", str(path))
    assert tools.resolve("register", "CTRL")["result"]["offset"] == "00h"
    assert tools.explain("Read Telemetry")["result"]["entity"]["identifier"] == "A1h"
    json.dumps(tools.status())
    assert tools.validate()["result"] == {}


def test_no_engine_degrades(monkeypatch):
    monkeypatch.delenv("SPEC_IR_DB", raising=False)
    result = tools.resolve("command", "A1h")
    assert result["result"] is None
    assert result["_meta"]["coverage"] == "no-engine"


def test_multiple_specs_require_explicit_scope(demo):
    path, engine = demo
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO documents VALUES (?,?,?,?,?,?)",
        ("other", "Other Fictional Interface", "1.0", None, "demo://other", None),
    )
    connection.execute(
        "INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "other:command:a1h", "other", "command", "A1h", "Other Read",
            None, "{}", "curated", "fictional test",
        ),
    )
    connection.commit()
    connection.close()
    result = engine.resolve("command", "A1h")
    assert result["result"] is None
    assert len(result["candidates"]) == 2
    assert "pass spec explicitly" in result["_meta"]["warning"]
    explicit = engine.resolve("command", "A1h", spec="other")
    assert explicit["result"]["name"] == "Other Read"
