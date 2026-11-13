"""Match execution receipts to saved runner output, without running commands."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, NamedTuple


class Profile(NamedTuple):
    """Where the Python runner reports a backend's scenarios in its JUnit file."""

    module: str  # the testcase classname
    store: str  # the store a case name carries: none for memory, else `[<store>]`
    redis_turns: bool  # the kit's turns crossed Redis (ROOMKIT_TEST_TURN_BACKEND=redis)


# A receipt's backend names its store and, with `+redis-turns`, the turn transport.
# The Redis turn mode runs the same cases under the same names: only the command
# that ran tells the two apart, so the command is checked too.
PROFILES = {
    "memory": Profile("tests.conformance.test_conformance", "memory", False),
    "sqlite": Profile("tests.conformance.test_conformance", "sqlite", False),
    "memory+redis-turns": Profile("tests.conformance.test_conformance", "memory", True),
    "sqlite+redis-turns": Profile("tests.conformance.test_conformance", "sqlite", True),
    "postgres": Profile("tests.conformance.test_postgres", "postgres", False),
}

TURN_BACKEND = "ROOMKIT_TEST_TURN_BACKEND"

# `test_scenario[<id>]`, `test_scenario[<id>[sqlite]]`, `test_scenario[<id>[postgres]]`,
# and test_postgres.py's `test_shared_postgres_contract[<id>-False]` (plain) and
# `[<id>-True]` (its slow-preparation variant). Scenario ids hold no brackets.
_SCENARIO_CASE = re.compile(r"test_scenario\[([^\[\]]+?)(?:\[(sqlite|postgres)\])?\]")
_SHARED_POSTGRES_CASE = re.compile(r"test_shared_postgres_contract\[([^\[\]]+)-(?:False|True)\]")

# Worst first: a scenario with several cases takes the worst of their outcomes.
_SEVERITY = ("failed", "skipped", "passed")


def validate_artifact(run: dict[str, Any], root: Path) -> list[str]:
    """An execution must retain the output supporting each recorded outcome."""
    reference = run["artifact"]
    path = (root / reference["path"]).resolve()
    if not path.is_relative_to((root / "conformance" / "executions").resolve()):
        return [f"{run['id']}: execution artifact must be under conformance/executions"]
    try:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
            return [f"{run['id']}: execution artifact fingerprint differs"]
        if reference["format"] == "pytest_junit":
            return junit(run, raw)
        return cargo(run, raw.decode())
    except (OSError, UnicodeError, ET.ParseError, ValueError) as error:
        return [f"{run['id']}: cannot read execution artifact: {error}"]


def scenario_case(name: str) -> tuple[str, str] | None:
    """The scenario and store a runner case name stands for, or None for another test."""
    if match := _SCENARIO_CASE.fullmatch(name):
        return match[1], match[2] or "memory"
    if match := _SHARED_POSTGRES_CASE.fullmatch(name):
        return match[1], "postgres"
    return None


def case_outcome(case: ET.Element) -> str:
    """A testcase's outcome; an expected failure (xfail) reports as skipped."""
    if case.find("failure") is not None or case.find("error") is not None:
        return "failed"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def outcomes(raw: bytes, backend: str) -> dict[str, str]:
    """Each scenario's outcome on *backend* in a JUnit report, read from the cases of
    the backend's module and store only. Raises ValueError on a duplicate case."""
    profile = PROFILES[backend]
    names: set[str] = set()
    found: dict[str, str] = {}
    for case in ET.fromstring(raw).iter("testcase"):
        if case.get("classname") != profile.module:
            continue
        name = case.get("name", "")
        if name in names:
            raise ValueError(f"duplicate JUnit case {name}")
        names.add(name)
        parsed = scenario_case(name)
        if parsed is None or parsed[1] != profile.store:
            continue
        scenario, outcome = parsed[0], case_outcome(case)
        if scenario in found:
            outcome = min(found[scenario], outcome, key=_SEVERITY.index)
        found[scenario] = outcome
    return found


def turn_backend(command: list[str]) -> str | None:
    """The ROOMKIT_TEST_TURN_BACKEND a command's leading assignments set, as `env`
    arguments or shell words, or None when it sets none. Raises ValueError when
    another word names the variable (a wrapped, nested or split command): its
    turn mode cannot be read from the words."""
    through_env = command[:1] == ["env"]
    words = command[1:] if through_env else command
    value = None
    read = 0  # the leading words read: env's options and their arguments, assignments
    while read < len(words):
        word = words[read]
        if through_env and word in ("-u", "--unset"):
            read += 2  # the variable unset: the run's default, not Redis
            continue
        if through_env and word.startswith("-") and not word.startswith(("-S", "--split")):
            read += 2 if word in ("-C", "--chdir") else 1
            continue
        name, equals, assigned = word.partition("=")
        if not equals or not name.isidentifier():
            break
        if name == TURN_BACKEND:
            value = assigned
        read += 1
    if any(TURN_BACKEND in word for word in words[read:]):
        raise ValueError(f"cannot tell the turn mode of the command {command}")
    return value


def junit(run: dict[str, Any], raw: bytes) -> list[str]:
    """Resolve the Python runner's exact case/backend, including skips and errors."""
    profile = PROFILES.get(run["backend"])
    if run["implementation"] != "python" or profile is None or run["runtime"] != "asyncio":
        return [f"{run['id']}: unsupported pytest execution profile"]
    try:
        turns = turn_backend(run["command"])
    except ValueError as error:
        return [f"{run['id']}: {error}"]
    if (turns == "redis") != profile.redis_turns:
        selects = "does not select" if profile.redis_turns else "selects"
        return [
            f"{run['id']}: its command {selects} the kit's turns across Redis "
            f"({TURN_BACKEND}=redis), unlike its backend {run['backend']}"
        ]
    try:
        cases = outcomes(raw, run["backend"])
    except ValueError as error:
        return [f"{run['id']}: {error}"]
    errors = []
    for result in run["results"]:
        name = result["scenario"]
        actual = cases.get(name, "not_run")
        if actual != result["outcome"]:
            errors.append(
                f"{run['id']}: {name}: receipt says {result['outcome']}, JUnit says {actual}"
            )
    return errors


def cargo(run: dict[str, Any], text: str) -> list[str]:
    """Aggregate Rust summaries cannot identify the executed backend and IDs."""
    return [
        (
            f"{run['id']}: cargo receipts are unsupported: aggregate output does not "
            "prove the backend and scenario selection; retain the run outside the coverage registry"
        )
    ]
