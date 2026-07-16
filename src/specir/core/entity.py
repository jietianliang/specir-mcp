"""Core, protocol-neutral SpecIR entities."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Confidence(str, Enum):
    EXTRACTED = "extracted"
    CURATED = "curated"
    INFERRED = "inferred"


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Document(Serializable):
    spec: str
    name: str
    revision: str | None = None
    publication_date: str | None = None
    source_uri: str | None = None
    sha256: str | None = None


@dataclass
class Section(Serializable):
    uid: str
    spec: str
    raw_label: str
    title: str
    level: int = 1
    parent_uid: str | None = None
    text: str = ""
    page_start: int = 0
    page_end: int = 0
    confidence: str = Confidence.EXTRACTED
    evidence: str = ""


@dataclass
class Table(Serializable):
    uid: str
    spec: str
    raw_label: str
    raw_number: str = ""
    caption: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    page: int = 0
    section_uid: str | None = None
    confidence: str = Confidence.EXTRACTED
    evidence: str = ""


@dataclass
class Figure(Serializable):
    uid: str
    spec: str
    raw_label: str
    caption: str = ""
    content_text: str = ""
    page: int = 0
    section_uid: str | None = None
    confidence: str = Confidence.EXTRACTED
    evidence: str = ""


@dataclass
class Entity(Serializable):
    """A domain-defined entity resolved by kind + identifier."""

    uid: str
    spec: str
    kind: str
    identifier: str
    name: str = ""
    section_uid: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: str = Confidence.EXTRACTED
    evidence: str = ""


@dataclass
class Passage(Serializable):
    uid: str
    spec: str
    section_uid: str | None
    source_type: str
    source_uid: str | None
    page: int
    ordinal: int
    text: str
    bbox: list[float] = field(default_factory=list)
    content_hash: str = ""
    confidence: str = Confidence.EXTRACTED
    evidence: str = ""


@dataclass
class Edge(Serializable):
    src: str
    dst: str
    type: str
    evidence: str = ""
    confidence: str = Confidence.EXTRACTED
