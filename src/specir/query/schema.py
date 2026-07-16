"""SQLite schema and database helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS documents (
  spec TEXT PRIMARY KEY, name TEXT NOT NULL, revision TEXT,
  publication_date TEXT, source_uri TEXT, sha256 TEXT
);
CREATE TABLE IF NOT EXISTS sections (
  uid TEXT PRIMARY KEY, spec TEXT NOT NULL, raw_label TEXT, title TEXT,
  level INTEGER DEFAULT 1, parent_uid TEXT, text TEXT DEFAULT '',
  page_start INTEGER DEFAULT 0, page_end INTEGER DEFAULT 0,
  confidence TEXT DEFAULT 'extracted', evidence TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sections_spec ON sections(spec);
CREATE TABLE IF NOT EXISTS tables (
  uid TEXT PRIMARY KEY, spec TEXT NOT NULL, raw_label TEXT, raw_number TEXT,
  caption TEXT DEFAULT '', headers TEXT DEFAULT '[]', rows TEXT DEFAULT '[]',
  page INTEGER DEFAULT 0, section_uid TEXT,
  confidence TEXT DEFAULT 'extracted', evidence TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tables_spec ON tables(spec);
CREATE TABLE IF NOT EXISTS figures (
  uid TEXT PRIMARY KEY, spec TEXT NOT NULL, raw_label TEXT,
  caption TEXT DEFAULT '', content_text TEXT DEFAULT '', page INTEGER DEFAULT 0,
  section_uid TEXT, confidence TEXT DEFAULT 'extracted', evidence TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_figures_spec ON figures(spec);
CREATE TABLE IF NOT EXISTS entities (
  uid TEXT PRIMARY KEY, spec TEXT NOT NULL, kind TEXT NOT NULL,
  identifier TEXT NOT NULL, name TEXT DEFAULT '', section_uid TEXT,
  payload TEXT DEFAULT '{}', confidence TEXT DEFAULT 'extracted',
  evidence TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_entities_resolve
  ON entities(kind, identifier COLLATE NOCASE, spec);
CREATE TABLE IF NOT EXISTS passages (
  uid TEXT PRIMARY KEY, spec TEXT NOT NULL, section_uid TEXT,
  source_type TEXT NOT NULL, source_uid TEXT, page INTEGER DEFAULT 0,
  ordinal INTEGER DEFAULT 0, text TEXT NOT NULL, bbox TEXT DEFAULT '[]',
  content_hash TEXT, confidence TEXT DEFAULT 'extracted', evidence TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_passages_spec ON passages(spec);
CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT, src TEXT NOT NULL, dst TEXT NOT NULL,
  type TEXT NOT NULL, evidence TEXT DEFAULT '',
  confidence TEXT DEFAULT 'extracted'
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE TABLE IF NOT EXISTS provenance (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity_uid TEXT NOT NULL,
  source_ids TEXT DEFAULT '[]', pass_name TEXT NOT NULL, created_at TEXT
);
CREATE TABLE IF NOT EXISTS issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT, severity TEXT NOT NULL,
  rule TEXT NOT NULL, entity_uid TEXT NOT NULL, message TEXT NOT NULL
);
"""


def create_database(path: str | Path) -> sqlite3.Connection:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(destination)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_DDL)
    return connection
