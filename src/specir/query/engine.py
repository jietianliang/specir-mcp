"""Data-neutral SQLite query engine."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


JSON_COLUMNS = {"headers", "rows", "payload", "bbox", "source_ids"}
SUPPRESSED_EDGE_TYPES = {"boilerplate", "weak"}
TYPED_EDGE_SCORES = {
    "defines": 100,
    "member_of": 100,
    "mentions_status": 95,
    "listed_in": 90,
}


class SpecIRQueryEngine:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        self._connection: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.database)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for key in JSON_COLUMNS:
            if key in result and isinstance(result[key], str):
                try:
                    result[key] = json.loads(result[key])
                except json.JSONDecodeError:
                    pass
        if isinstance(result.get("payload"), dict):
            payload = result.pop("payload")
            result.update(payload)
        return result

    def documents(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute("SELECT * FROM documents ORDER BY spec")]

    def effective_spec(self, spec: str | None) -> tuple[str | None, str | None]:
        value = (spec or "auto").strip()
        if value.lower() not in {"", "auto", "*", "all"}:
            return value, None
        documents = self.documents()
        if len(documents) == 1:
            return documents[0]["spec"], None
        if len(documents) > 1:
            return None, "multiple specs are loaded; pass spec explicitly"
        return None, "no documents are registered"

    def _document_meta(self, spec: str | None) -> dict[str, Any]:
        document = None
        if spec:
            row = self.conn.execute(
                "SELECT * FROM documents WHERE spec=?", (spec,)
            ).fetchone()
            document = dict(row) if row else None
        return {
            "spec_revision": document.get("revision") if document else None,
            "source_document": document.get("source_uri") if document else None,
            "document_hash": document.get("sha256") if document else None,
        }

    def _envelope(
        self, result: Any, *, coverage: str = "extracted",
        warning: str | None = None, spec: str | None = None, **extra: Any
    ) -> dict[str, Any]:
        meta = {"coverage": coverage, "warning": warning}
        meta.update(self._document_meta(spec))
        response = {"result": result, "_meta": meta}
        response.update(extra)
        return response

    def resolve(
        self, kind: str, identifier: str, spec: str | None = "auto"
    ) -> dict[str, Any]:
        normalized_kind = kind.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", normalized_kind):
            return self._envelope(None, coverage="error", warning="invalid kind")
        scope, scope_warning = self.effective_spec(spec)

        if normalized_kind == "section":
            return self.get_section(identifier, spec=scope, warning=scope_warning)
        if normalized_kind in {"table", "figure"}:
            return self._resolve_document_entity(
                normalized_kind, identifier, scope, scope_warning
            )

        sql = "SELECT * FROM entities WHERE kind=? AND identifier=? COLLATE NOCASE"
        params: list[Any] = [normalized_kind, identifier]
        if scope:
            sql += " AND spec=?"
            params.append(scope)
        rows = [self._row(row) for row in self.conn.execute(sql, params)]
        rows = [row for row in rows if row is not None]
        if not rows:
            return self._envelope(
                None, coverage="no-data",
                warning=f"{kind} {identifier!r} not found", spec=scope,
            )
        rows.sort(key=lambda row: (row["spec"], row["uid"]))
        if len(rows) > 1 and not scope:
            return self._envelope(
                None, coverage="partial", warning=scope_warning,
                candidates=rows,
            )
        return self._envelope(rows[0], spec=rows[0]["spec"], warning=scope_warning)

    def _resolve_document_entity(
        self, kind: str, identifier: str, spec: str | None,
        warning: str | None,
    ) -> dict[str, Any]:
        table = f"{kind}s"
        label_column = "raw_number" if kind == "table" else "raw_label"
        sql = (
            f"SELECT * FROM {table} WHERE "
            f"(uid=? OR {label_column}=? COLLATE NOCASE OR raw_label=? COLLATE NOCASE)"
        )
        params: list[Any] = [identifier, identifier, identifier]
        if spec:
            sql += " AND spec=?"
            params.append(spec)
        rows = [self._row(row) for row in self.conn.execute(sql, params)]
        rows = [row for row in rows if row]
        if len(rows) > 1 and not spec:
            return self._envelope(
                None, coverage="partial", warning=warning, candidates=rows
            )
        return self._envelope(
            rows[0] if rows else None,
            coverage="extracted" if rows else "no-data",
            warning=warning if rows else f"{kind} {identifier!r} not found",
            spec=rows[0]["spec"] if rows else spec,
        )

    def get_section(
        self, identifier: str, spec: str | None = None,
        warning: str | None = None,
    ) -> dict[str, Any]:
        if ":" in identifier:
            uid = identifier
        elif spec:
            uid = f"{spec}:{identifier}"
        else:
            rows = self.conn.execute(
                "SELECT * FROM sections WHERE raw_label=? COLLATE NOCASE",
                (identifier,),
            ).fetchall()
            parsed = [self._row(row) for row in rows]
            if len(parsed) > 1:
                return self._envelope(
                    None, coverage="partial", warning=warning, candidates=parsed
                )
            if parsed:
                return self._envelope(parsed[0], spec=parsed[0]["spec"])
            uid = identifier
        result = self._row(
            self.conn.execute("SELECT * FROM sections WHERE uid=?", (uid,)).fetchone()
        )
        return self._envelope(
            result,
            coverage="extracted" if result else "no-data",
            warning=warning if result else f"section {identifier!r} not found",
            spec=result["spec"] if result else spec,
        )

    def _entity_summary(self, uid: str) -> dict[str, Any] | None:
        for table, kind, label in (
            ("sections", "section", "title"),
            ("tables", "table", "caption"),
            ("figures", "figure", "caption"),
            ("entities", None, "name"),
            ("passages", "passage", "text"),
        ):
            row = self.conn.execute(
                f"SELECT * FROM {table} WHERE uid=?", (uid,)
            ).fetchone()
            if not row:
                continue
            parsed = self._row(row) or {}
            return {
                "uid": uid,
                "type": kind or parsed.get("kind", "entity"),
                "label": str(parsed.get(label) or uid)[:200],
                "spec": parsed.get("spec"),
                "section_uid": (
                    uid if table == "sections" else parsed.get("section_uid")
                ),
            }
        return None

    def section_scope(
        self, uid: str, include_children: str = "auto",
        max_depth: int = 3, max_nodes: int = 100,
    ) -> dict[str, Any]:
        mode = (include_children or "auto").lower()
        if mode not in {"auto", "none", "direct", "recursive"}:
            return {"root_uid": uid, "scope_uids": [uid], "children": []}
        root = self.conn.execute(
            "SELECT * FROM sections WHERE uid=?", (uid,)
        ).fetchone()
        if not root:
            return {"root_uid": uid, "scope_uids": [uid], "children": []}

        def children(parent: str) -> list[sqlite3.Row]:
            return list(self.conn.execute(
                "SELECT * FROM sections WHERE parent_uid=? "
                "ORDER BY page_start,level,raw_label", (parent,)
            ))

        root_children = children(uid)
        root_stub = len(str(root["text"] or "").strip()) < 200 and bool(root_children)
        nodes: list[dict[str, Any]] = []
        if mode != "none" and (mode != "auto" or root_stub):
            queue = [(row, 1) for row in root_children]
            while queue and len(nodes) < max_nodes:
                row, depth = queue.pop(0)
                child_rows = children(row["uid"])
                stub = len(str(row["text"] or "").strip()) < 200 and bool(child_rows)
                nodes.append({
                    "uid": row["uid"], "title": row["title"],
                    "parent_uid": row["parent_uid"], "depth": depth,
                    "page_start": row["page_start"],
                    "body_chars": len(str(row["text"] or "").strip()),
                    "structural_stub": stub,
                })
                descend = mode == "recursive" or (mode == "auto" and stub)
                if descend and depth < max_depth:
                    queue.extend((child, depth + 1) for child in child_rows)
        return {
            "root_uid": uid,
            "coverage": "descendant_aggregated" if nodes else "section_only",
            "scope_uids": [uid, *(node["uid"] for node in nodes)],
            "children": nodes,
            "truncated": len(nodes) >= max_nodes,
        }

    def _trace_xrefs(
        self, anchor_uid: str, *, depth: int, direction: str,
        profile: str, scope_uids: list[str] | None = None,
    ) -> dict[str, Any]:
        roots = list(dict.fromkeys(scope_uids or [anchor_uid]))

        def trace(one_direction: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
            results: list[dict[str, Any]] = []
            suppressed: list[dict[str, Any]] = []
            visited = set(roots)
            emitted: set[str] = set()
            frontier = roots
            truncated = False
            for current_depth in range(1, max(0, min(depth, 5)) + 1):
                level: list[dict[str, Any]] = []
                for current in frontier:
                    column = "src" if one_direction == "outgoing" else "dst"
                    for edge in self.conn.execute(
                        "SELECT src,dst,type,evidence,confidence FROM edges "
                        f"WHERE {column}=? ORDER BY id", (current,)
                    ):
                        related_uid = edge["dst"] if one_direction == "outgoing" else edge["src"]
                        if related_uid in visited or related_uid in emitted:
                            continue
                        summary = self._entity_summary(related_uid)
                        if not summary:
                            continue
                        edge_type = str(edge["type"])
                        is_suppressed = edge_type in SUPPRESSED_EDGE_TYPES
                        score = TYPED_EDGE_SCORES.get(
                            edge_type,
                            75 if summary["type"] in {"table", "figure"} else 50,
                        )
                        level.append(summary | {
                            "direction": one_direction,
                            "edge_type": edge_type,
                            "depth": current_depth,
                            "relevance_score": 5 if is_suppressed else score,
                            "relevance_class": (
                                "suppressed" if is_suppressed
                                else "test_relevant" if score >= 90
                                else "supporting"
                            ),
                            "relevance_reasons": [
                                "edge_class:suppressed" if is_suppressed
                                else f"edge_type:{edge_type}"
                            ],
                            "origin_section_uid": current,
                            "evidence": [{
                                "text": edge["evidence"],
                                "confidence": edge["confidence"],
                                "evidence_type": "edge",
                            }] if edge["evidence"] else [],
                        })
                level.sort(key=lambda item: (
                    item["relevance_class"] == "suppressed",
                    -int(item["relevance_score"]), item["uid"],
                ))
                active = [item for item in level if item["relevance_class"] != "suppressed"]
                low = [item for item in level if item["relevance_class"] == "suppressed"]
                if profile == "test_points" and len(active) > 25:
                    active = active[:25]
                    truncated = True
                selected = active + low if profile == "test_points" else level
                next_frontier: list[str] = []
                for item in selected:
                    if len(results) + len(suppressed) >= 100:
                        return results, suppressed, True
                    emitted.add(item["uid"])
                    if profile == "test_points" and item["relevance_class"] == "suppressed":
                        suppressed.append(item)
                        continue
                    results.append(item)
                    if item["type"] == "section" and current_depth < depth:
                        visited.add(item["uid"])
                        next_frontier.append(item["uid"])
                frontier = next_frontier
                if not frontier:
                    break
            return results, suppressed, truncated

        outgoing: list[dict[str, Any]] = []
        incoming: list[dict[str, Any]] = []
        suppressed: list[dict[str, Any]] = []
        truncated = False
        if direction in {"outgoing", "both"}:
            outgoing, low, cut = trace("outgoing")
            suppressed.extend(low)
            truncated |= cut
        if direction in {"incoming", "both"}:
            incoming, low, cut = trace("incoming")
            suppressed.extend(low)
            truncated |= cut
        return {
            "source_uid": anchor_uid, "direction": direction,
            "profile": profile, "references": outgoing,
            "outgoing": outgoing, "incoming": incoming,
            "suppressed_references": suppressed,
            "total": len(outgoing) + len(incoming), "truncated": truncated,
        }

    def _related_entities(
        self, uid: str, product_xrefs: dict[str, Any], limit: int = 25
    ) -> list[dict[str, Any]]:
        items: dict[str, dict[str, Any]] = {}

        def add(item: dict[str, Any]) -> None:
            current = items.get(item["uid"])
            if current is None or item["relevance_score"] > current["relevance_score"]:
                items[item["uid"]] = item

        for edge in self.conn.execute(
            "SELECT src,dst,type,evidence,confidence FROM edges "
            "WHERE (src=? OR dst=?) AND type IN "
            "('defines','listed_in','member_of','mentions_status')",
            (uid, uid),
        ):
            outgoing = edge["src"] == uid
            related_uid = edge["dst"] if outgoing else edge["src"]
            summary = self._entity_summary(related_uid)
            if not summary:
                continue
            edge_type = str(edge["type"])
            add(summary | {
                "direction": "outgoing" if outgoing else "incoming",
                "relation_type": edge_type,
                "relevance_score": TYPED_EDGE_SCORES[edge_type],
                "relevance_class": "test_relevant",
                "relevance_reasons": [f"typed_edge:{edge_type}"],
                "evidence": [{"text": edge["evidence"], "confidence": edge["confidence"]}],
            })
        for one_direction in ("outgoing", "incoming"):
            for xref in product_xrefs.get(one_direction, []):
                add({
                    key: value for key, value in xref.items()
                    if key not in {"edge_type"}
                } | {"relation_type": xref["edge_type"]})
        return sorted(items.values(), key=lambda item: (
            -int(item["relevance_score"]),
            {"status": 0, "field": 1, "table": 2, "figure": 3, "section": 4}.get(item["type"], 9),
            item["uid"],
        ))[:limit]

    def fetch(
        self, uid: str, include_xrefs: bool = False, xref_depth: int = 1,
        xref_direction: str = "outgoing", xref_profile: str = "test_points",
        include_children: str = "auto",
    ) -> dict[str, Any]:
        for table in ("sections", "tables", "figures", "entities", "passages"):
            row = self.conn.execute(f"SELECT * FROM {table} WHERE uid=?", (uid,)).fetchone()
            result = self._row(row)
            if result:
                response = self._envelope(result, spec=result.get("spec"))
                if include_xrefs:
                    profile = xref_profile if xref_profile in {"generic", "test_points"} else "test_points"
                    summary = self._entity_summary(uid) or {}
                    anchor_uid = summary.get("section_uid") or uid
                    scope = self.section_scope(anchor_uid, include_children)
                    raw = self._trace_xrefs(
                        anchor_uid, depth=xref_depth,
                        direction=xref_direction, profile=profile,
                        scope_uids=scope["scope_uids"] if profile == "test_points" else None,
                    )
                    product = raw if profile == "test_points" else self._trace_xrefs(
                        anchor_uid, depth=xref_depth,
                        direction=xref_direction, profile="test_points",
                        scope_uids=scope["scope_uids"],
                    )
                    response["section_scope"] = scope
                    response["xrefs"] = raw
                    response["xrefs_raw"] = raw
                    response["related_entities"] = self._related_entities(uid, product)
                return response
        return self._envelope(
            None, coverage="no-data", warning=f"uid {uid!r} not found"
        )

    def explain(
        self, name: str, kind: str, spec: str | None = "auto"
    ) -> dict[str, Any]:
        scope, scope_warning = self.effective_spec(spec)
        sql = (
            "SELECT * FROM entities WHERE kind=? AND "
            "(name=? COLLATE NOCASE OR identifier=? COLLATE NOCASE)"
        )
        params: list[Any] = [kind.lower(), name, name]
        if scope:
            sql += " AND spec=?"
            params.append(scope)
        rows = [self._row(row) for row in self.conn.execute(sql, params)]
        rows = [row for row in rows if row]
        if len(rows) != 1:
            return self._envelope(
                None,
                coverage="partial" if rows else "no-data",
                warning=scope_warning or f"{kind} {name!r} not uniquely resolved",
                candidates=rows,
            )
        entity = rows[0]
        section = None
        if entity.get("section_uid"):
            section = self._row(
                self.conn.execute(
                    "SELECT * FROM sections WHERE uid=?", (entity["section_uid"],)
                ).fetchone()
            )
        fetched = self.fetch(entity["uid"], include_xrefs=True)
        return self._envelope(
            {
                "entity": entity, "section": section,
                "related_entities": fetched.get("related_entities", []),
                "xrefs_raw": fetched.get("xrefs_raw"),
            },
            spec=entity["spec"],
            warning=scope_warning,
        )

    def search(
        self, query: str, spec: str | None = None, limit: int = 10,
        mode: str = "hybrid",
    ) -> dict[str, Any]:
        scope = None if not spec or spec.lower() in {"auto", "all", "*"} else spec
        needle = f"%{query.strip().lower()}%"
        results: list[dict[str, Any]] = []
        if mode == "raw_linked":
            sql = "SELECT uid,spec,section_uid,source_type,page,text FROM passages WHERE lower(text) LIKE ?"
            params: list[Any] = [needle]
            if scope:
                sql += " AND spec=?"
                params.append(scope)
            results = [dict(row) | {"source": "passage"} for row in self.conn.execute(sql, params)]
        else:
            sources = [
                ("sections", "title", "text", "page_start", "section"),
                ("tables", "caption", "rows", "page", "table"),
                ("figures", "caption", "content_text", "page", "figure"),
                ("entities", "name", "payload", "0", "entity"),
            ]
            for table, label, body, page, source in sources:
                page_expr = page if page != "0" else "0 AS page"
                sql = (
                    f"SELECT uid,spec,{label} AS label,{body} AS body,"
                    f"{page_expr} FROM {table} "
                    f"WHERE (lower({label}) LIKE ? OR lower({body}) LIKE ?)"
                )
                params = [needle, needle]
                if scope:
                    sql += " AND spec=?"
                    params.append(scope)
                for row in self.conn.execute(sql, params):
                    item = dict(row)
                    item["source"] = source
                    item["snippet"] = str(item.pop("body") or "")[:360]
                    results.append(item)
        results.sort(
            key=lambda item: (
                query.casefold() not in str(item.get("label", "")).casefold(),
                item["uid"],
            )
        )
        limited = results[: max(1, min(int(limit), 100))]
        result_spec = scope or (limited[0]["spec"] if limited else None)
        return self._envelope(
            limited,
            coverage="extracted" if limited else "no-data",
            warning=None if limited else f"no matches for {query!r}",
            spec=result_spec,
            total=len(results),
            returned=len(limited),
            mode=mode,
        )

    def status(self) -> dict[str, Any]:
        counts = {}
        for table in (
            "documents", "sections", "tables", "figures", "entities",
            "passages", "edges", "provenance", "issues",
        ):
            counts[table] = self.conn.execute(
                f"SELECT count(*) FROM {table}"
            ).fetchone()[0]
        counts["entities_by_kind"] = {
            row[0]: row[1] for row in self.conn.execute(
                "SELECT kind,count(*) FROM entities GROUP BY kind ORDER BY kind"
            )
        }
        return self._envelope(counts)

    def validate(self, mode: str = "summary") -> dict[str, Any]:
        """Read persisted extraction/build issues without mutating the DB."""
        if mode == "findings":
            result: Any = [
                dict(row) for row in self.conn.execute(
                    "SELECT * FROM issues ORDER BY severity,rule,entity_uid,id"
                )
            ]
        else:
            result = {
                row[0]: row[1] for row in self.conn.execute(
                    "SELECT severity,count(*) FROM issues GROUP BY severity "
                    "ORDER BY severity"
                )
            }
        return self._envelope(result, coverage="extracted")
