"""Protocol-neutral text passage chunking."""
from __future__ import annotations

import hashlib
import re


def chunk_text(text: str, maximum: int = 520) -> list[dict]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    sentences = re.split(r"(?<=[.;!?])\s+", clean)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > maximum:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return [
        {
            "ordinal": ordinal,
            "text": chunk,
            "content_hash": hashlib.sha256(chunk.casefold().encode()).hexdigest(),
        }
        for ordinal, chunk in enumerate(chunks)
    ]
