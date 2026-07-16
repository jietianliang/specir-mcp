# specir-mcp

[English](README.md) | [简体中文](README_zh-CN.md)

`specir-mcp` is a data-neutral framework for turning technical documents into
a structured intermediate representation (SpecIR) and querying it through five
stable MCP tools.

The repository contains no standards PDFs, extracted specification text,
knowledge-base databases, model weights, or vendor-specific protocol tables.
All bundled demo content is fictional.

## Features

- Document, section, table, figure, entity, passage, provenance, and edge IR.
- Extensible domain plugin manifests with dependency-aware loading.
- PDF outline-based section extraction and reusable structure parsers.
- SQLite-backed exact lookup, fetch, explanation, search, and status APIs.
- A five-tool FastMCP surface:
  `specir_resolve`, `specir_fetch`, `specir_explain`, `specir_search`,
  and `specir_status`.
- Explicit coverage metadata so missing extraction is not confused with absence
  from a source document.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"

# Generate a small database from the fictional Acme Device Interface fixture.
specir-demo --output data/demo.db

export SPEC_IR_DB="$PWD/data/demo.db"
specir-mcp-server
```

The same server may be launched from a source checkout:

```bash
fastmcp run src/specir/query/server.py
```

Example MCP calls:

```text
specir_resolve(kind="command", id="A1h", spec="acme-device")
specir_fetch(uid="acme-device:2.1", include_xrefs=true)
specir_explain(name="Read Telemetry", kind="command", spec="acme-device")
specir_search(query="telemetry", spec="acme-device")
specir_status()
```

When a database contains one document, `spec="auto"` selects it. With multiple
documents, exact lookups return candidates and request an explicit spec.

## Using your own data

Create a database with `specir.query.schema.create_database`, then insert
documents and entities using the schema documented by the Python dataclasses.
Set `SPEC_IR_DB` to that database before starting the server. The framework
never downloads or bundles source documents.

The optional PDF extractor can build coordinate-clipped section records:

```python
from specir.extractors.pdf import build_section_tree

sections = build_section_tree("my-spec", "path/to/your-document.pdf")
```

You are responsible for having permission to process and store the documents
you supply.

## Development

```bash
pytest
python -m build
```

The tests create temporary synthetic databases and do not require external
specifications or network access.

## License

Apache License 2.0. See [LICENSE](LICENSE).
