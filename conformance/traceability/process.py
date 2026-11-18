"""The process rule: a unit added or changed arrives with a scenario or a reason.

A unit's level decides what its change needs (TRACEABILITY.md, "The process
rule"). The rule compares the current RFC with a base commit's.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .links import UNTESTED, citations


def changed_units(
    registry: dict[str, Any], base: dict[str, Any]
) -> list[tuple[dict[str, Any], str]]:
    """The units added since the base, or whose text, kind, applicability or
    level changed, in RFC order."""
    before = {item["id"]: item for item in base["requirements"]}
    found = []
    for item in registry["requirements"]:
        old = before.get(item["id"])
        if old is None:
            found.append((item, "added"))
        elif old["sha256"] != item["sha256"] or old.get("level") != item.get("level"):
            found.append((item, "changed"))
    return found


def enclosing(section: str) -> list[str]:
    """A section and the sections around it, outermost first: 10.6.3 gives
    10, 10.6 and 10.6.3."""
    parts = section.split(".")
    return [".".join(parts[:end]) for end in range(1, len(parts) + 1)]


def levelled_sections(base: dict[str, Any]) -> set[str]:
    """The sections every unit of which, its subsections' included, had a
    level at the base."""
    units: Counter[str] = Counter()
    levelled: Counter[str] = Counter()
    for item in base["requirements"]:
        for section in enclosing(item["section"]):
            units[section] += 1
            levelled[section] += item.get("level") is not None
    return {section for section, count in units.items() if levelled[section] == count}


def process_rule(
    registry: dict[str, Any],
    base: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
    untested: dict[str, str],
    base_ref: str,
) -> tuple[list[str], list[str], list[str]]:
    """Errors, warnings and unreviewed units among the units changed since the
    base: a must unit needs a citing scenario or a reason in untested.json, a
    should unit without either warns, a may unit passes, a unit with no level
    is unreviewed. A non_testable unit needs neither: its kind is its reason.
    In a section every unit of which had a level at the base, a unit with no
    level is an error, whether added, moved in or with its level dropped."""
    cited = citations(scenarios)
    levelled = levelled_sections(base)
    changed = {item["id"]: how for item, how in changed_units(registry, base)}
    errors, warnings, unreviewed = [], [], []
    since = base_ref[:12]
    for item in registry["requirements"]:
        unit, level, how = item["id"], item.get("level"), changed.get(item["id"])
        if level is None:
            around = [part for part in enclosing(item["section"]) if part in levelled]
            if around:  # how is None: unchanged, the unit has moved in
                errors.append(
                    f"{unit} ({how or 'moved'} since {since}): no level, in "
                    f"§{around[0]} where every unit has one"
                )
            elif how is not None:
                unreviewed.append(f"{unit} ({how} since {since}): no level yet")
            continue
        if how is None or item["kind"] == "non_testable":
            continue
        if unit in cited or unit in untested:
            continue
        if level == "must":
            errors.append(
                f"{unit} (must, {how} since {since}): no scenario cites it "
                f"and {UNTESTED} gives no reason"
            )
        elif level == "should":
            warnings.append(f"{unit} (should, {how} since {since}): no scenario cites it")
    return errors, warnings, unreviewed
