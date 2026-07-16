"""Coordinate-clipped PDF section extraction using document outlines."""
from __future__ import annotations

import re
from typing import Any

import fitz


def _page_text(
    document: fitz.Document,
    start_page: int,
    end_page: int,
    start_y: float,
    end_y: float | None,
) -> str:
    parts: list[str] = []
    for page_number in range(start_page, end_page + 1):
        page = document[page_number - 1]
        top = start_y if page_number == start_page else 0
        bottom = end_y if page_number == end_page and end_y is not None else page.rect.height
        clip = fitz.Rect(0, top, page.rect.width, bottom)
        parts.append(page.get_text(clip=clip, sort=True))
    return "\n".join(parts).strip()


def build_section_tree(spec: str, pdf_path: str) -> list[dict[str, Any]]:
    """Extract a flat section tree from a PDF outline.

    The caller must have permission to process the supplied document.
    """
    document = fitz.open(pdf_path)
    try:
        outline = document.get_toc(simple=False)
        entries: list[tuple[int, str, int, float]] = []
        for item in outline:
            level, title, page = item[:3]
            destination = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
            point = destination.get("to")
            top = float(getattr(point, "y", 0) or 0)
            if title.strip() and page > 0:
                entries.append((level, title.strip(), page, top))
        if not entries:
            return []

        minimum = min(level for level, *_ in entries)
        parents: dict[int, str] = {}
        number_pattern = re.compile(r"^([A-Za-z]?\d+(?:\.\d+)*|[A-Z])\s+(.+)$")
        sections: list[dict[str, Any]] = []
        for index, (level, title, page, top) in enumerate(entries):
            normalized_level = level - minimum + 1
            match = number_pattern.match(title)
            label, clean_title = (
                (match.group(1), match.group(2).strip())
                if match else (f"outline-{index + 1}", title)
            )
            uid = f"{spec}:{label}"
            next_page = entries[index + 1][2] if index + 1 < len(entries) else len(document)
            next_top = entries[index + 1][3] if index + 1 < len(entries) else None
            parent_uid = None
            for parent_level in range(normalized_level - 1, 0, -1):
                if parent_level in parents:
                    parent_uid = parents[parent_level]
                    break
            parents[normalized_level] = uid
            sections.append({
                "uid": uid,
                "spec": spec,
                "raw_label": label,
                "title": clean_title,
                "level": normalized_level,
                "parent_uid": parent_uid,
                "text": _page_text(document, page, max(page, next_page), top, next_top),
                "page_start": page,
                "page_end": max(page, next_page),
                "confidence": "extracted",
                "evidence": f"pdf:outline:{page}:coordinate-clipped",
            })
        return sections
    finally:
        document.close()
