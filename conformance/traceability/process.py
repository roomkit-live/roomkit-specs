"""The process rule: a unit added or changed arrives with a scenario or a reason.

A unit's level decides what its change needs (TRACEABILITY.md, "The process
rule"). The rule compares the current RFC with a base commit's.
"""

from __future__ import annotations

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
    is unreviewed. A non_testable unit is exempt: its kind is its reason."""
    cited = citations(scenarios)
    errors, warnings, unreviewed = [], [], []
    since = base_ref[:12]
    for item, how in changed_units(registry, base):
        unit, level = item["id"], item.get("level")
        if level is None:
            unreviewed.append(f"{unit} ({how} since {since}): no level yet")
            continue
        if item["kind"] == "non_testable" or unit in cited or unit in untested:
            continue
        if level == "must":
            errors.append(
                f"{unit} (must, {how} since {since}): no scenario cites it "
                f"and {UNTESTED} gives no reason"
            )
        elif level == "should":
            warnings.append(f"{unit} (should, {how} since {since}): no scenario cites it")
    return errors, warnings, unreviewed
