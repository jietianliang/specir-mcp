"""Data-neutral SQLite query engine."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


JSON_COLUMNS = {"headers", "rows", "payload", "bbox", "source_ids"}


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

    def fetch(self, uid: str, include_xrefs: bool = False) -> dict[str, Any]:
        for table in ("sections", "tables", "figures", "entities", "passages"):
            row = self.conn.execute(f"SELECT * FROM {table} WHERE uid=?", (uid,)).fetchone()
            result = self._row(row)
            if result:
                response = self._envelope(result, spec=result.get("spec"))
                if include_xrefs:
                    response["xrefs"] = {
                        "outgoing": [
                            dict(edge) for edge in self.conn.execute(
                                "SELECT src,dst,type,evidence,confidence FROM edges WHERE src=?",
                                (uid,),
                            )
                        ],
                        "incoming": [
                            dict(edge) for edge in self.conn.execute(
                                "SELECT src,dst,type,evidence,confidence FROM edges WHERE dst=?",
                                (uid,),
                            )
                        ],
                    }
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
        return self._envelope(
            {"entity": entity, "section": section},
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
