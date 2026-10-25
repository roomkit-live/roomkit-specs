#!/usr/bin/env python3
"""Check the conformance scenarios against their schema and the RFC.

For each scenario under conformance/scenarios/:

- it validates against scenario.schema.json, its `id` names its path, and
  it is written in the suite's one JSON layout (`--fix` rewrites it so);
- each entry of its `rules` resolves to a heading, a step or a rule of the
  RFC at the pinned commit (conformance/RFC_COMMIT): "§10.1", "§10.1 step
  9", "§10.2 step 3c", "§7.5 rule 2", "§9.5.1 Reentrance", "§10.3
  Validation rule 4", "Appendix B.2".

It then lists what no scenario asserts yet: the rows of the §26.1 trigger
and framework-event table (a row is credited only by the scenarios that cite
the places it names, each of them by one), and the cells of the reentrancy
table (README, "Reentrancy cells").

    python3 conformance/check.py            # check; exit 1 on an error
    python3 conformance/check.py --fix      # rewrite the layout first
    python3 conformance/check.py --rfc roomkit-rfc.md   # against a file
    python3 conformance/check.py --strict   # coverage gaps are errors too

It needs `jsonschema` (pip install jsonschema).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCENARIOS = HERE / "scenarios"

CELLS = [
    f"{row}@{column}"
    for row in ("inject", "routed", "commit", "change")
    for column in ("locked", "admitted", "cascade", "outside")
]

_HEADING = re.compile(r"^(#{2,4}) (?:Appendix )?([A-Z0-9][A-Za-z0-9.]*?)[.:]? (.*)$")
_TOP_STEP = re.compile(r"^\s*(\d+[a-z]?)\. \S")
_SUB_STEP = re.compile(r"^\s*[│ ]*[├└]── ([a-z])\. \S")
_NUMBERED = re.compile(r"^(\d+)\. ")
_REF = re.compile(r"^(?:§|Appendix )([A-Z0-9][A-Za-z0-9.]*)(?: (.+))?$")


def layout(scenario: Any) -> str:
    """The suite's one layout of a scenario file."""
    return json.dumps(scenario, indent=2, ensure_ascii=False) + "\n"


def rfc_text(path: str | None) -> tuple[str, str]:
    """The RFC's text and what it was read from: a file, or the pinned commit."""
    if path is not None:
        return Path(path).read_text(encoding="utf-8"), path
    commit = (HERE / "RFC_COMMIT").read_text(encoding="utf-8").strip()
    text = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{commit}:roomkit-rfc.md"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return text, f"roomkit-rfc.md at {commit[:12]}"


def sections(text: str) -> dict[str, list[str]]:
    """Each numbered section's own lines, up to the next heading of any level."""
    found: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            current = found.setdefault(match[2], [])
            continue
        if current is not None:
            current.append(line)
    return found


def resolve(reference: str, parts: dict[str, list[str]]) -> str | None:
    """Why `reference` names nothing of the RFC, or None when it resolves."""
    match = _REF.match(reference)
    if not match:
        return "not written as §N or Appendix X"
    number, rest = match[1], match[2]
    lines = parts.get(number)
    if lines is None:
        return f"no section {number}"
    if rest is None:
        return None
    if step := re.fullmatch(r"step (\d+)([a-z]?)", rest):
        return _step(lines, step[1], step[2])
    if rule := re.fullmatch(r"(?:(.+) )?rule (\d+)", rest):
        return _rule(lines, rule[1], rule[2])
    return None if _label(lines, rest) is not None else f"no paragraph {rest!r} in {number}"


def _step(lines: list[str], number: str, letter: str) -> str | None:
    tops = [(i, m[1]) for i, line in enumerate(lines) if (m := _TOP_STEP.match(line))]
    if any(label == number + letter for _, label in tops):
        return None
    starts = [i for i, label in tops if label == number]
    if not starts or not letter:
        return f"no step {number}{letter}"
    following = [i for i, _ in tops if i > starts[0]]
    end = following[0] if following else len(lines)
    for line in lines[starts[0] : end]:
        sub = _SUB_STEP.match(line)
        if sub and sub[1] == letter:
            return None
    return f"no step {number}{letter}"


def _rule(lines: list[str], label: str | None, number: str) -> str | None:
    start = 0
    if label is not None:
        position = _label(lines, label)
        if position is None:
            return f"no paragraph {label!r}"
        start = position
    items = [line for line in _prose(lines[start:]) if (m := _NUMBERED.match(line)) and m[1] == number]
    if not items:
        return f"no rule {number}"
    if label is None and len(items) > 1:
        return f"rule {number} is ambiguous: name the paragraph it is in"
    return None


def _prose(lines: list[str]) -> list[str]:
    """The lines outside code blocks."""
    kept, fenced = [], False
    for line in lines:
        if line.startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return kept


def _label(lines: list[str], label: str) -> int | None:
    """The line of the paragraph whose bold label is exactly `label`."""
    pattern = re.compile(r"^(?:- )?\*\*" + re.escape(label) + r"(?:[.:]?\*\*| \()")
    for position, line in enumerate(lines):
        if pattern.match(line):
            return position
    return None


_ROW_REF = re.compile(r"§(\d+(?:\.\d+)*)(?: steps? (\d+[a-z]?(?:(?:, | and )\d+[a-z]?)*))?")


def coverage_rows(parts: dict[str, list[str]]) -> list[tuple[str, list[Ref], list[str], list[str]]]:
    """The §26.1 table's rows: each step or operation, the RFC places it
    names, its triggers and its framework events."""
    events = set()
    for line in parts.get("8.2", []):
        cell = line.split("|")
        if len(cell) > 2 and re.fullmatch(r" [a-z_]+ ", cell[1]):
            events.add(cell[1].strip())
    rows = []
    for line in parts.get("26.1", []):
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 3 or cells[0] in ("Step or operation", "---") or set(cells[0]) <= {"-"}:
            continue
        refs: list[Ref] = []
        for section, steps in _ROW_REF.findall(cells[0]):
            numbers = re.findall(r"\d+[a-z]?", steps) if steps else [None]
            refs.extend((section, number) for number in numbers)
        triggers = re.findall(r"\b[A-Z][A-Z_]{3,}\b", cells[1])
        named = [word for word in re.findall(r"[a-z_]+", cells[2]) if word in events]
        rows.append((cells[0], refs, triggers, named))
    return rows


# An RFC place a §26.1 row names: a section, and one of its steps or none.
Ref = tuple[str, "str | None"]


def cites(scenario: dict[str, Any], ref: Ref) -> bool:
    """Whether the scenario's rules cite the place: its step, or its section."""
    section, step = ref
    for rule in scenario.get("rules", []):
        match = re.match(r"^§([0-9.]+)(?: step (\d+[a-z]?))?", rule)
        if match and match[1] == section and (step is None or match[2] == step):
            return True
    return False


def row_gaps(
    operation: str, refs: list[Ref], names: list[str], scenarios: list[dict[str, Any]]
) -> list[str]:
    """What the row lacks: a name no scenario citing its places asserts, and
    a place no scenario asserting one of its names cites."""
    citing = [s for s in scenarios if not refs or any(cites(s, ref) for ref in refs)]
    credited: set[str] = set()
    for scenario in citing:
        triggers, events = asserted(scenario)
        credited |= triggers | events
    gaps = []
    missing = [name for name in names if name not in credited]
    if missing:
        gaps.append(f"§26.1 row {operation!r}: nothing citing it asserts {', '.join(missing)}")
    for ref in refs:
        if not any(
            cites(s, ref) and set(names) & set().union(*asserted(s)) for s in scenarios
        ):
            place = f"§{ref[0]}" + (f" step {ref[1]}" if ref[1] else "")
            gaps.append(f"§26.1 row {operation!r}: no scenario citing {place} asserts it")
    return gaps


def asserted(scenario: dict[str, Any]) -> tuple[set[str], set[str]]:
    """The triggers whose firing a scenario asserts, and the framework events."""
    expect = scenario.get("expect", {})
    hooks = {hook["name"]: hook["trigger"] for hook in scenario.get("setup", {}).get("hooks", [])}
    triggers = set()
    for name, calls in expect.get("hooks", {}).items():
        listed = calls.get("$unordered", []) if isinstance(calls, dict) else calls
        if listed and name in hooks:
            triggers.add(hooks[name].upper())
    events = set()
    for room_events in expect.get("framework_events", {}).values():
        for item in room_events:
            group = item.get("$unordered", [item]) if isinstance(item, dict) else [item]
            for entry in group:
                events.add(entry if isinstance(entry, str) else entry.get("event", ""))
    return triggers, events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fix", action="store_true", help="rewrite each file in the suite's layout")
    parser.add_argument("--rfc", help="check against this file instead of the pinned commit")
    parser.add_argument("--strict", action="store_true", help="coverage gaps are errors")
    args = parser.parse_args()
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("check.py needs jsonschema: pip install jsonschema", file=sys.stderr)
        return 2
    schema = json.loads((HERE / "scenario.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    text, source = rfc_text(args.rfc)
    parts = sections(text)
    errors: list[str] = []
    scenarios: list[dict[str, Any]] = []
    for path in sorted(SCENARIOS.glob("**/*.json")):
        name = path.relative_to(SCENARIOS).with_suffix("").as_posix()
        raw = path.read_text(encoding="utf-8")
        scenario = json.loads(raw)
        scenarios.append(scenario)
        if args.fix and raw != layout(scenario):
            path.write_text(layout(scenario), encoding="utf-8")
        elif raw != layout(scenario):
            errors.append(f"{name}: not in the suite's layout (check.py --fix)")
        for error in validator.iter_errors(scenario):
            location = "/".join(str(p) for p in error.absolute_path)
            errors.append(f"{name}: schema: {location}: {error.message}")
        if scenario.get("id") != name:
            errors.append(f"{name}: its id is {scenario.get('id')!r}")
        for reference in scenario.get("rules", []):
            why = resolve(reference, parts)
            if why is not None:
                errors.append(f"{name}: rule {reference!r}: {why}")
    cells: set[str] = set()
    for scenario in scenarios:
        cells |= set(scenario.get("reentrancy", []))
    gaps = []
    for operation, refs, row_triggers, row_events in coverage_rows(parts):
        gaps += row_gaps(operation, refs, row_triggers + row_events, scenarios)
    gaps += [f"reentrancy cell {cell}: no scenario" for cell in CELLS if cell not in cells]
    print(f"{len(scenarios)} scenarios, rules resolved against {source}")
    for line in errors:
        print(f"error: {line}")
    for line in gaps:
        print(f"gap: {line}")
    if errors or (args.strict and gaps):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
