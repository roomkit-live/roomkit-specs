"""Read stable requirement annotations without changing the RFC's text."""

from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_right
from typing import Any

ID = re.compile(r"RK-(?:[0-9]+|[A-Z])(?:\.[0-9]+)*-[0-9]{3,}")
HEADING = re.compile(r"^#{2,6} (?:Appendix )?([A-Z0-9]+(?:\.[0-9]+)*)[.:]? (.+)$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
MARKER = re.compile(r"<!--\s*(rfc:\s*\{.*?\}|/rfc)\s*-->", re.DOTALL)
KEYWORD = re.compile(
    r"\b(?:MUST(?: NOT)?|SHALL(?: NOT)?|SHOULD(?: NOT)?|MAY|REQUIRED|RECOMMENDED)\b"
)
KINDS = {"behavior", "structural", "non_testable"}


def digest(value: Any) -> str:
    """Fingerprint JSON values independent of indentation and key order."""
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def text_digest(text: str) -> str:
    """Fingerprint source text, including conditions and punctuation."""
    return hashlib.sha256(text.encode()).hexdigest()


def prose(text: str) -> str:
    """Mask fenced examples without moving any character or line offset."""
    lines = []
    fence = ""
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line.rstrip("\n"))
        hidden = bool(fence)
        if match and not fence:
            fence = match[1]
            hidden = True
        elif (
            match and fence and match[1][0] == fence[0] and len(match[1]) >= len(fence)
        ):
            if not match[2].strip():
                fence = ""
        lines.append(
            "".join("\n" if char == "\n" else " " for char in line) if hidden else line
        )
    return "".join(lines)


def section_spans(text: str) -> list[dict[str, Any]]:
    """Numbered headings and each heading's own body, outside examples."""
    found: list[dict[str, Any]] = []
    offset = 0
    seen = set()
    for line_number, line in enumerate(prose(text).splitlines(keepends=True), 1):
        match = HEADING.match(line.rstrip("\n"))
        if match:
            number = match[1]
            if number in seen:
                raise ValueError(f"duplicate RFC section {number}")
            seen.add(number)
            if found:
                found[-1]["end"] = offset
            found.append(
                {
                    "section": number,
                    "title": match[2],
                    "line": line_number,
                    "start": offset,
                    "body_start": offset + len(line),
                    "end": len(text),
                }
            )
        offset += len(line)
    if found and text[: found[0]["start"]].strip():
        found.insert(
            0,
            {
                "section": "0",
                "title": "Preface (Abstract and contents)",
                "line": 1,
                "start": 0,
                "body_start": 0,
                "end": found[0]["start"],
            },
        )
    return found


def annotation(metadata: Any) -> dict[str, str]:
    """An annotation names a requirement and its scope, never a test result."""
    if not isinstance(metadata, dict) or set(metadata) != {"id", "kind", "applies"}:
        raise ValueError("an rfc annotation requires exactly id, kind and applies")
    if not isinstance(metadata["id"], str) or ID.fullmatch(metadata["id"]) is None:
        raise ValueError(f"invalid requirement id: {metadata['id']!r}")
    if not isinstance(metadata["kind"], str) or metadata["kind"] not in KINDS:
        raise ValueError(f"invalid requirement kind: {metadata['kind']!r}")
    if not isinstance(metadata["applies"], str) or not metadata["applies"].strip():
        raise ValueError("an rfc annotation requires non-empty applicability")
    return metadata


def strip_annotations(text: str) -> str:
    """Remove annotation lines or inline comments, preserving the original RFC."""
    ranges = []
    for marker in MARKER.finditer(prose(text)):
        start = text.rfind("\n", 0, marker.start()) + 1
        end = text.find("\n", marker.end())
        end = len(text) if end == -1 else end + 1
        if (
            not text[start : marker.start()].strip()
            and not text[marker.end() : end].strip()
        ):
            ranges.append((start, end))
        else:
            ranges.append((marker.start(), marker.end()))
    for start, end in reversed(ranges):
        text = text[:start] + text[end:]
    return text


def extract(text: str) -> dict[str, Any]:
    """Extract reviewed source units; unannotated keywords remain candidates."""
    sections = section_spans(text)
    starts = [section["start"] for section in sections]
    masked = prose(text)
    requirements = []
    seen = set()
    opening = None
    ranges = []
    for marker in MARKER.finditer(masked):
        if marker[1] != "/rfc":
            if opening is not None:
                raise ValueError("nested rfc annotations")
            metadata = annotation(json.loads(marker[1][4:]))
            if metadata["id"] in seen:
                raise ValueError(f"duplicate requirement {metadata['id']}")
            seen.add(metadata["id"])
            opening = (marker, metadata)
            continue
        if opening is None:
            raise ValueError("rfc closing marker has no opening marker")
        begin, metadata = opening
        at = bisect_right(starts, begin.start()) - 1
        if at < 0 or marker.end() > sections[at]["end"]:
            raise ValueError(
                f"{metadata['id']}: annotation must stay within one numbered section"
            )
        body = text[begin.end() : marker.start()].strip()
        if not body:
            raise ValueError(f"{metadata['id']}: empty requirement")
        fingerprint = digest(
            {"text": body, "kind": metadata["kind"], "applies": metadata["applies"]}
        )
        requirements.append(
            {
                **metadata,
                "section": sections[at]["section"],
                "line": text.count("\n", 0, begin.start()) + 1,
                "text": body,
                "sha256": fingerprint,
            }
        )
        ranges.append((begin.start(), marker.end()))
        opening = None
    if opening is not None:
        raise ValueError(f"{opening[1]['id']}: unclosed annotation")
    # Unknown or malformed marker syntax must not disappear from the inventory.
    remaining = list(masked)
    for start, end in ranges:
        remaining[start:end] = " " * (end - start)
    unmarked = "".join(remaining)
    if re.search(r"<!--\s*/?rfc\b", MARKER.sub("", masked)):
        raise ValueError("malformed rfc marker")
    uncovered = list(text)
    for start, end in ranges:
        uncovered[start:end] = [
            "\n" if char == "\n" else " " for char in text[start:end]
        ]
    uncovered = "".join(uncovered)
    inventory = []
    for section in sections:
        start, end = section["body_start"], section["end"]
        body = text[start:end].strip()
        candidates = sorted(
            {
                text.count("\n", 0, match.start() + start) + 1
                for match in KEYWORD.finditer(unmarked[start:end])
            }
        )
        content_lines = [
            text.count("\n", 0, start) + offset + 1
            for offset, line in enumerate(uncovered[start:end].splitlines())
            if line.strip()
            and line.strip() not in {"---", "-", "*", "+"}
            and not re.fullmatch(r"\*\*[^*]+\*\*:?", line.strip())
        ]
        inventory.append(
            {
                "section": section["section"],
                "title": section["title"],
                "line": section["line"],
                "sha256": text_digest(body),
                "unannotated_keyword_lines": candidates,
                "unannotated_content_lines": content_lines,
            }
        )
    return {
        "version": 1,
        "rfc_sha256": text_digest(strip_annotations(text)),
        "sections": inventory,
        "requirements": requirements,
    }


def check_history(
    current: dict[str, Any],
    previous: dict[str, Any],
    retired: list[str],
    previously_retired: list[str] = (),
) -> list[str]:
    """IDs are retained or retired explicitly and are never reassigned."""
    errors = []
    active = {item["id"] for item in current["requirements"]}
    before = {item["id"] for item in previous["requirements"]}
    errors += [
        f"{item}: retirement removed"
        for item in sorted(set(previously_retired) - set(retired))
    ]
    if len(retired) != len(set(retired)) or any(
        ID.fullmatch(item) is None for item in retired
    ):
        errors.append("retired requirement IDs must be unique valid IDs")
    errors += [f"{item}: retired ID reused" for item in sorted(active & set(retired))]
    errors += [
        f"{item}: removed without retirement"
        for item in sorted(before - active - set(retired))
    ]
    return errors
