"""Small deterministic parsers for common technical-document structures."""
from __future__ import annotations

import re


PATTERNS = {
    "packet": [r"\bByte\s+\d+", r"\bHeader\b", r"\bOffset\b"],
    "register": [r"\bBits?\s+\d+(?::\d+)?", r"\bRO\b|\bRW\b|\bR/W\b"],
    "waveform": [r"\bSCL\b|\bSDA\b|\bCLK\b", r"\bt[A-Z]{2,}\b"],
    "state_machine": [r"\bIdle\b|\bStart\b|\bStop\b|\bWait\b", r"->|→"],
}


def classify_figure(text: str) -> str:
    scores = {
        kind: sum(bool(re.search(pattern, text, re.I)) for pattern in patterns)
        for kind, patterns in PATTERNS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "generic"


def parse_register_fields(text: str) -> list[dict]:
    fields = []
    pattern = re.compile(
        r"(?P<bits>\d+(?::\d+)?)\s*[|,:-]\s*(?P<name>[A-Za-z][\w ]+?)"
        r"(?:\s*[|,:-]\s*(?P<access>RO|RW|R/W|WO))?(?:$|\n)",
        re.I,
    )
    for match in pattern.finditer(text):
        fields.append({
            "bit_range": match.group("bits"),
            "name": match.group("name").strip(),
            "access": (match.group("access") or "").upper(),
        })
    return fields


def parse_packet_fields(text: str) -> list[dict]:
    fields = []
    pattern = re.compile(
        r"(?:Byte|Offset)\s+(?P<offset>\d+)\s*[|,:-]\s*"
        r"(?P<name>[A-Za-z][\w /-]+)",
        re.I,
    )
    for match in pattern.finditer(text):
        fields.append({
            "offset": int(match.group("offset")),
            "name": match.group("name").strip(),
        })
    return fields


def parse_waveform(text: str) -> dict:
    signals = sorted(set(re.findall(r"\b(?:SCL|SDA|CLK|DATA|TX|RX)\b", text, re.I)))
    timings = sorted(set(re.findall(r"\bt[A-Z][A-Z0-9_]+\b", text)))
    return {"signals": signals, "timing_labels": timings}


def parse_state_transitions(text: str) -> list[dict]:
    transitions = []
    for source, target in re.findall(
        r"\b([A-Za-z][\w ]*?)\s*(?:->|→)\s*([A-Za-z][\w ]*)", text
    ):
        transitions.append({"from": source.strip(), "to": target.strip()})
    return transitions
