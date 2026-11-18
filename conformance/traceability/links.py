"""Scenario citations of RFC units, and the lock pinning each to the text read.

A scenario cites the units it tests in `requirements`. `links.lock.json` keeps,
for each (unit, scenario) citation, the unit's fingerprint when the scenario
was last read against it: a unit whose text changes since names the scenarios
to reread, until `check.py --pin` records that they were. `untested.json` gives
the reason a unit has no scenario.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .source import ID

LOCK = "links.lock.json"
UNTESTED = "untested.json"
PIN = "python3 conformance/check.py --pin"

_UNIT = ID.pattern
_SCENARIO = "^[a-z0-9.-]+/[a-z0-9-]+$"
_SHA256 = "^[0-9a-f]{64}$"

LOCK_SCHEMA = {
    "type": "object",
    "required": ["version", "links"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": 1},
        "links": {
            "type": "object",
            "propertyNames": {"pattern": f"^{_UNIT}$"},
            "additionalProperties": {
                "type": "object",
                "minProperties": 1,
                "propertyNames": {"pattern": _SCENARIO},
                "additionalProperties": {"type": "string", "pattern": _SHA256},
            },
        },
    },
}

UNTESTED_SCHEMA = {
    "type": "object",
    "required": ["version", "units"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": 1},
        "units": {
            "type": "object",
            "propertyNames": {"pattern": f"^{_UNIT}$"},
            "additionalProperties": {"type": "string", "pattern": r"\S"},
        },
    },
}

# A unit's citations: scenario id -> the unit's fingerprint when it was read.
Lock = dict[str, dict[str, str]]


def cited_by(scenario: dict[str, Any]) -> list[str]:
    """The units a scenario cites; a malformed list is the schema's error."""
    units = scenario.get("requirements", [])
    return [unit for unit in units if isinstance(unit, str)] if isinstance(units, list) else []


def citations(scenarios: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """Each cited unit and the scenarios citing it."""
    cited: dict[str, set[str]] = defaultdict(set)
    for name, scenario in scenarios.items():
        for unit in cited_by(scenario):
            cited[unit].add(name)
    return dict(cited)


def check_citations(
    scenarios: dict[str, dict[str, Any]],
    registry: dict[str, Any],
    retired: list[str],
) -> list[str]:
    """A citation names a current unit that a scenario can test."""
    units = {item["id"]: item for item in registry["requirements"]}
    errors = []
    for name, scenario in sorted(scenarios.items()):
        for unit in cited_by(scenario):
            if unit in retired:
                errors.append(
                    f"{name}: requirement {unit}: retired; cite the units that replace it"
                )
            elif unit not in units:
                errors.append(f"{name}: requirement {unit}: no such unit in the RFC")
            elif units[unit]["kind"] == "non_testable":
                errors.append(
                    f"{name}: requirement {unit}: non_testable; no scenario can cite it"
                )
    return errors


def read(directory: Path, name: str, schema: dict[str, Any], empty: Any) -> Any:
    """A lock or untested file, validated; an absent file holds nothing."""
    path = directory / name
    if not path.exists():
        return empty
    value = json.loads(path.read_text(encoding="utf-8"))
    errors = [
        f"{name}: {'/'.join(map(str, error.absolute_path))}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(value)
    ]
    if errors:
        raise ValueError("; ".join(errors))
    return value


def read_lock(directory: Path) -> Lock:
    """The lock's citations; ValueError when it is malformed."""
    return read(directory, LOCK, LOCK_SCHEMA, {"version": 1, "links": {}})["links"]


def lock_layout_errors(directory: Path, lock: Lock) -> list[str]:
    """A lock out of its sorted layout, as a hand-merged one can be."""
    path = directory / LOCK
    if path.exists() and path.read_text(encoding="utf-8") != lock_layout(lock):
        return [f"{LOCK}: not in its sorted layout; any --pin rewrites it"]
    return []


def read_untested(directory: Path) -> dict[str, str]:
    """Each unit with no scenario, and the reason."""
    return read(directory, UNTESTED, UNTESTED_SCHEMA, {"version": 1, "units": {}})[
        "units"
    ]


def lock_layout(lock: Lock) -> str:
    """The lock's one layout: units, then scenarios, sorted."""
    value = {
        "version": 1,
        "links": {
            unit: dict(sorted(lock[unit].items())) for unit in sorted(lock) if lock[unit]
        },
    }
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def lock_problems(
    scenarios: dict[str, dict[str, Any]],
    registry: dict[str, Any],
    lock: Lock,
    untested: dict[str, str],
) -> list[str]:
    """What `--strict` refuses: a cited unit changed since a scenario read it, a
    citation the lock does not pin, a pin with no citation, a stale reason.
    A citation of a unit the RFC lacks is check_citations' error, not drift."""
    fingerprints = {item["id"]: item["sha256"] for item in registry["requirements"]}
    cited = citations(scenarios)
    known = {unit: names for unit, names in cited.items() if unit in fingerprints}
    problems = to_reread(known, fingerprints, lock)
    problems += unpinned(known, lock)
    problems += orphans(cited, lock)
    problems += [
        f"{UNTESTED} gives a reason {unit} has no scenario, but "
        f"{', '.join(sorted(cited[unit]))} cite it: remove its entry"
        for unit in sorted(untested.keys() & cited.keys())
    ]
    return problems


def to_reread(
    cited: dict[str, set[str]], fingerprints: dict[str, str], lock: Lock
) -> list[str]:
    """Each cited unit whose text changed since a scenario was read against it."""
    problems = []
    for unit in sorted(cited):
        pinned = lock.get(unit, {})
        stale = sorted(
            name
            for name in cited[unit]
            if name in pinned and pinned[name] != fingerprints[unit]
        )
        if stale:
            problems.append(
                f"{unit} changed since {', '.join(stale)} read it: reread "
                f"{'it' if len(stale) == 1 else 'them'}, then run {PIN} {unit}"
            )
    return problems


def unpinned(cited: dict[str, set[str]], lock: Lock) -> list[str]:
    """Each scenario citing units the lock does not pin for it."""
    found: dict[str, list[str]] = defaultdict(list)
    for unit, names in cited.items():
        for name in names - lock.get(unit, {}).keys():
            found[name].append(unit)
    return [
        f"{name} cites {', '.join(sorted(found[name]))} with no lock entry: once "
        f"it is read against {'it' if len(found[name]) == 1 else 'them'}, run "
        f"{PIN} {' '.join(sorted(found[name]))} {name}"
        for name in sorted(found)
    ]


def orphans(cited: dict[str, set[str]], lock: Lock) -> list[str]:
    """Each scenario the lock pins to units it no longer cites."""
    found: dict[str, list[str]] = defaultdict(list)
    for unit, pinned in lock.items():
        for name in pinned.keys() - cited.get(unit, set()):
            found[name].append(unit)
    return [
        f"{LOCK} pins {name} to {', '.join(sorted(found[name]))}, which it does "
        f"not cite: run {PIN} {' '.join(sorted(found[name]))} {name}"
        for name in sorted(found)
    ]


def check_untested(
    untested: dict[str, str], registry: dict[str, Any], retired: list[str]
) -> list[str]:
    """A reason names a current unit."""
    units = {item["id"] for item in registry["requirements"]}
    return [
        f"{UNTESTED}: {unit}: {'retired' if unit in retired else 'no such unit in the RFC'}"
        for unit in sorted(untested)
        if unit not in units
    ]


def pin(
    names: list[str],
    scenarios: dict[str, dict[str, Any]],
    registry: dict[str, Any],
    lock: Lock,
) -> tuple[Lock, list[str]]:
    """Record the named citations as read against the current text, and drop
    the named entries no citation holds any more. A unit names its citations,
    a scenario its own; naming both names the citations of those units by
    those scenarios. Nothing else moves."""
    fingerprints = {item["id"]: item["sha256"] for item in registry["requirements"]}
    cited = citations(scenarios)
    pairs = {
        (unit, name)
        for unit, citing in cited.items()
        if unit in fingerprints
        for name in citing
    } | {(unit, name) for unit, entries in lock.items() for name in entries}
    units = {name for name in names if ID.fullmatch(name)}
    named = set(names) - units
    errors = [
        f"--pin {name}: names no citation or entry of {LOCK}"
        for name in sorted(units | named)
        if not any(name in pair for pair in pairs)
    ]
    selected = {
        (unit, name)
        for unit, name in pairs
        if (not units or unit in units) and (not named or name in named)
    }
    if not errors and not selected:
        errors.append(f"--pin {' '.join(names)}: these name no citation together")
    if errors:
        return lock, errors
    updated: Lock = {
        unit: {name: sha for name, sha in entries.items() if (unit, name) not in selected}
        for unit, entries in lock.items()
    }
    for unit, name in sorted(selected):
        if name in cited.get(unit, ()):
            updated.setdefault(unit, {})[name] = fingerprints[unit]
    return {unit: entries for unit, entries in updated.items() if entries}, []
