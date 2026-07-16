"""In-memory SpecIR graph with JSON serialization."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .entity import Edge


class SpecIRGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.provenance: list[dict[str, Any]] = []
        self.issues: list[dict[str, Any]] = []

    def add_node(self, node: Any) -> str:
        data = node.to_dict()
        data["__type__"] = type(node).__name__
        self.nodes[data["uid"]] = data
        return data["uid"]

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge.to_dict())

    def get_node(self, uid: str) -> dict[str, Any] | None:
        return self.nodes.get(uid)

    def get_nodes_by_type(self, type_name: str) -> list[dict[str, Any]]:
        return [node for node in self.nodes.values() if node.get("__type__") == type_name]

    def get_nodes_by_spec(self, spec: str) -> list[dict[str, Any]]:
        return [node for node in self.nodes.values() if node.get("spec") == spec]

    def get_edges_from(self, uid: str) -> list[dict[str, Any]]:
        return [edge for edge in self.edges if edge["src"] == uid]

    def get_edges_to(self, uid: str) -> list[dict[str, Any]]:
        return [edge for edge in self.edges if edge["dst"] == uid]

    def stats(self) -> dict[str, Any]:
        types: dict[str, int] = {}
        specs: dict[str, int] = {}
        for node in self.nodes.values():
            types[node.get("__type__", "unknown")] = types.get(node.get("__type__", "unknown"), 0) + 1
            specs[node.get("spec", "unknown")] = specs.get(node.get("spec", "unknown"), 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": types,
            "nodes_by_spec": specs,
        }

    def save(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / "nodes.json").write_text(
            json.dumps(list(self.nodes.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (path / "edges.json").write_text(
            json.dumps(self.edges, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> "SpecIRGraph":
        path = Path(directory)
        graph = cls()
        for node in json.loads((path / "nodes.json").read_text(encoding="utf-8")):
            graph.nodes[node["uid"]] = node
        graph.edges = json.loads((path / "edges.json").read_text(encoding="utf-8"))
        return graph
