"""Generate a runnable SQLite database from the fictional demo fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

from specir.extractors.passages import chunk_text
from specir.query.schema import create_database
from specir.query.semantic_edges import rebuild_typed_entity_edges


def build_demo(output: str | Path) -> Path:
    fixture_path = files("specir.demo") / "fixture.json"
    raw_bytes = fixture_path.read_bytes()
    fixture = json.loads(raw_bytes)
    destination = Path(output)
    if destination.exists():
        destination.unlink()
    connection = create_database(destination)
    try:
        document = fixture["document"]
        connection.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?)",
            (
                document["spec"], document["name"], document["revision"],
                document["publication_date"], document["source_uri"],
                hashlib.sha256(raw_bytes).hexdigest(),
            ),
        )
        spec = document["spec"]
        for section in fixture["sections"]:
            connection.execute(
                "INSERT INTO sections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    section["uid"], spec, section["raw_label"], section["title"],
                    section.get("level", 1), section.get("parent_uid"),
                    section.get("text", ""), section.get("page_start", 0),
                    section.get("page_end", 0), "curated", "fictional demo fixture",
                ),
            )
            for passage in chunk_text(section.get("text", "")):
                uid = f"{section['uid']}:passage:{passage['ordinal']:03d}"
                connection.execute(
                    "INSERT INTO passages VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        uid, spec, section["uid"], "section", section["uid"],
                        section.get("page_start", 0), passage["ordinal"],
                        passage["text"], "[]", passage["content_hash"], "curated",
                        "fictional demo fixture",
                    ),
                )
        for table in fixture["tables"]:
            connection.execute(
                "INSERT INTO tables VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    table["uid"], spec, table["raw_label"], table["raw_number"],
                    table["caption"], json.dumps(table["headers"]),
                    json.dumps(table["rows"]), table["page"],
                    table.get("section_uid"), "curated", "fictional demo fixture",
                ),
            )
        for figure in fixture["figures"]:
            connection.execute(
                "INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    figure["uid"], spec, figure["raw_label"], figure["caption"],
                    figure["content_text"], figure["page"],
                    figure.get("section_uid"), "curated", "fictional demo fixture",
                ),
            )
        for entity in fixture["entities"]:
            connection.execute(
                "INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    entity["uid"], spec, entity["kind"], entity["identifier"],
                    entity["name"], entity.get("section_uid"),
                    json.dumps(entity.get("payload", {})), "curated",
                    "fictional demo fixture",
                ),
            )
        for edge in fixture["edges"]:
            connection.execute(
                "INSERT INTO edges(src,dst,type,evidence,confidence) VALUES (?,?,?,?,?)",
                (
                    edge["src"], edge["dst"], edge["type"],
                    "fictional demo fixture", "curated",
                ),
            )
        rebuild_typed_entity_edges(connection, spec)
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("demo database integrity check failed")
    finally:
        connection.close()
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/demo.db"))
    args = parser.parse_args(argv)
    result = build_demo(args.output)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
