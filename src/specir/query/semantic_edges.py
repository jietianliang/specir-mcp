"""Deterministic, data-neutral typed edges for product related views."""
from __future__ import annotations

import json
import sqlite3


OWNED_TYPES = ("defines", "listed_in", "member_of", "mentions_status")


def rebuild_typed_entity_edges(
    connection: sqlite3.Connection, spec: str | None = None
) -> dict[str, int]:
    """Rebuild typed edges from generic entity metadata and exact mentions."""
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in OWNED_TYPES)
    if spec:
        connection.execute(
            f"DELETE FROM edges WHERE type IN ({placeholders}) "
            "AND src IN (SELECT uid FROM entities WHERE spec=?)",
            (*OWNED_TYPES, spec),
        )
    else:
        connection.execute(
            f"DELETE FROM edges WHERE type IN ({placeholders})", OWNED_TYPES
        )
    counts = {edge_type: 0 for edge_type in OWNED_TYPES}

    sql = "SELECT * FROM entities" + (" WHERE spec=?" if spec else "")
    params = (spec,) if spec else ()
    entities = list(connection.execute(sql, params))
    for entity in entities:
        try:
            payload = json.loads(entity["payload"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        section_uid = str(entity["section_uid"] or "")
        if entity["kind"] in {"command", "opcode", "feature"} and section_uid:
            if connection.execute(
                "SELECT 1 FROM sections WHERE uid=?", (section_uid,)
            ).fetchone():
                connection.execute(
                    "INSERT INTO edges(src,dst,type,evidence,confidence) "
                    "VALUES (?,?,'defines',?,'extracted')",
                    (entity["uid"], section_uid, entity["evidence"] or "entity.section_uid"),
                )
                counts["defines"] += 1
        listed_in_uid = str(payload.get("listed_in_uid") or "")
        if entity["kind"] == "feature" and listed_in_uid:
            if connection.execute(
                "SELECT 1 FROM tables WHERE uid=?", (listed_in_uid,)
            ).fetchone():
                connection.execute(
                    "INSERT INTO edges(src,dst,type,evidence,confidence) "
                    "VALUES (?,?,'listed_in',?,'extracted')",
                    (entity["uid"], listed_in_uid, entity["evidence"] or "payload.listed_in_uid"),
                )
                counts["listed_in"] += 1
        parent_uid = str(payload.get("parent_uid") or "")
        if entity["kind"] == "field" and parent_uid:
            if _entity_exists(connection, parent_uid):
                connection.execute(
                    "INSERT INTO edges(src,dst,type,evidence,confidence) "
                    "VALUES (?,?,'member_of',?,'extracted')",
                    (entity["uid"], parent_uid, entity["evidence"] or "payload.parent_uid"),
                )
                counts["member_of"] += 1

    for status in (entity for entity in entities if entity["kind"] == "status"):
        phrase = str(status["name"] or "").strip()
        if len(phrase) < 8:
            continue
        seen_sections: set[str] = set()
        passages = connection.execute(
            "SELECT uid,section_uid,page,text FROM passages WHERE spec=? "
            "AND trim(coalesce(section_uid,''))<>'' "
            "AND instr(lower(text),lower(?))>0 ORDER BY page,uid",
            (status["spec"], phrase),
        )
        for passage in passages:
            section_uid = str(passage["section_uid"])
            if section_uid in seen_sections:
                continue
            seen_sections.add(section_uid)
            connection.execute(
                "INSERT INTO edges(src,dst,type,evidence,confidence) "
                "VALUES (?,?,'mentions_status',?,'extracted')",
                (
                    section_uid,
                    status["uid"],
                    f"passage_uid={passage['uid']}; page={passage['page']}; "
                    f"text={str(passage['text'])[:300]}",
                ),
            )
            counts["mentions_status"] += 1
    return counts


def _entity_exists(connection: sqlite3.Connection, uid: str) -> bool:
    return any(
        connection.execute(f"SELECT 1 FROM {table} WHERE uid=?", (uid,)).fetchone()
        for table in ("sections", "tables", "figures", "entities")
    )
