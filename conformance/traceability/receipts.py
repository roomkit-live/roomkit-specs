"""Derive execution receipts' results from saved runner output, without running
commands.

A receipt stores no results: they are read from its retained JUnit report and
the corpus at its `corpus_commit`, by `derive`, for the checker and the importer
alike. The receipt keeps their outcome counts and `results_sha256`, and the
guard refuses a reader that reads an old report otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from .references import GitText
from .source import digest, scenario_digest


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

# roomkit-rs's passes, each a backend and a tokio runtime: one thread
# (`current_thread`) or four workers (`multi_thread_4`). Its runner writes one
# JUnit case per scenario, named by the scenario's id, under the class
# `conformance.<backend>.<runtime>`, so the report itself names the pass. A
# plain pass skips the scenarios with `setup.executors`; with `REDIS_URL` set,
# the runner runs them across its Redis turn executor and names the backend
# `<store>+redis-executors`. Every other scenario runs in process in both: unlike
# Python's `+redis-turns`, the other scenarios' turns never cross Redis.
RUST_PROFILES = {
    ("memory", "current_thread"),
    ("memory", "multi_thread_4"),
    ("sqlite", "current_thread"),
    ("postgres", "current_thread"),
    ("memory+redis-executors", "current_thread"),
    ("memory+redis-executors", "multi_thread_4"),
    ("sqlite+redis-executors", "current_thread"),
    ("postgres+redis-executors", "current_thread"),
}

TURN_BACKEND = "ROOMKIT_TEST_TURN_BACKEND"
# env's options whose argument is the next word (GNU coreutils, uutils).
_ENV_OPTIONS_WITH_ARGUMENT = ("-a", "--argv0", "-C", "--chdir", "-f", "--file")

# `test_scenario[<id>]`, `test_scenario[<id>[sqlite]]`, `test_scenario[<id>[postgres]]`,
# and test_postgres.py's `test_shared_postgres_contract[<id>-False]` (plain) and
# `[<id>-True]` (its slow-preparation variant). Scenario ids hold no brackets.
_SCENARIO_CASE = re.compile(r"test_scenario\[([^\[\]]+?)(?:\[(sqlite|postgres)\])?\]")
_SHARED_POSTGRES_CASE = re.compile(r"test_shared_postgres_contract\[([^\[\]]+)-(?:False|True)\]")

# Worst first: a scenario with several cases takes the worst of their outcomes.
_SEVERITY = ("failed", "skipped", "passed")


def with_results(
    runs: list[dict[str, Any]], root: Path, *, read: GitText
) -> tuple[list[dict[str, Any]], list[str]]:
    """Each receipt with the results derived from its retained report and the
    corpus at its corpus commit, and the errors: a receipt whose results cannot
    be derived is left out, and the guard checks every other one."""
    found, errors = [], []
    for run in runs:
        try:
            results = derive(run, retained(run, root), corpus(root, run["corpus_commit"], read))
        except ValueError as error:
            errors.append(f"{run['id']}: {error}")
            continue
        errors += guard(run, results)
        found.append({**run, "results": results})
    return found, errors


def corpus(root: Path, commit: str, read: GitText) -> Callable[[str], Any]:
    """A scenario of the specs corpus at *commit*, by id."""

    def scenario(name: str) -> Any:
        return json.loads(read(root, commit, f"conformance/scenarios/{name}.json"))

    return scenario


def retained(run: dict[str, Any], root: Path) -> bytes:
    """The receipt's retained report, under conformance/executions, with the
    fingerprint the receipt records. Raises ValueError otherwise."""
    reference = run["artifact"]
    path = (root / reference["path"]).resolve()
    if not path.is_relative_to((root / "conformance" / "executions").resolve()):
        raise ValueError("execution artifact must be under conformance/executions")
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read execution artifact: {error}") from error
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("execution artifact fingerprint differs")
    return raw


def derive(
    run: dict[str, Any], raw: bytes, scenario: Callable[[str], Any]
) -> list[dict[str, str]]:
    """The receipt's results, by scenario: each scenario case of its pass in its
    report *raw*, with its outcome, and the hash of *scenario*(id), the scenario
    at the receipt's corpus commit. Raises ValueError when the receipt's profile
    or its report supports no result."""
    cases = READERS.get(run["artifact"]["format"], cargo)(run, raw)
    if not cases:
        raise ValueError(f"the report holds no {run['backend']} scenario case")
    return [
        {"scenario": name, "sha256": scenario_digest(scenario(name)), "outcome": cases[name]}
        for name in sorted(cases)
    ]


def counts(results: list[dict[str, str]]) -> dict[str, int]:
    """How many results have each outcome, as a receipt records them."""
    return dict(sorted(Counter(result["outcome"] for result in results).items()))


def results_sha256(results: list[dict[str, str]]) -> str:
    """The fingerprint of a receipt's results, as `derive` returns them."""
    return digest(results)


def guard(run: dict[str, Any], results: list[dict[str, str]]) -> list[str]:
    """The receipt's recorded counts and fingerprint are those of the results its
    report and corpus derive today: a reader that reads an old report otherwise,
    even with the same counts, is refused."""
    errors = []
    if run["counts"] != counts(results):
        errors.append(
            f"{run['id']}: its report now reads {counts(results)}, "
            f"the receipt recorded {run['counts']}"
        )
    if run["results_sha256"] != results_sha256(results):
        errors.append(
            f"{run['id']}: the results its report and corpus derive differ from its "
            "results_sha256"
        )
    return errors


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


def junit_root(raw: bytes) -> ET.Element:
    """The root element of a JUnit report. Raises ValueError when the report is
    no XML the parser can read (malformed, or in an unknown or multi-byte
    encoding)."""
    try:
        return ET.fromstring(raw)
    except (ET.ParseError, LookupError, ValueError) as error:
        raise ValueError(f"cannot read the JUnit report: {error}") from error


def outcomes(raw: bytes, backend: str) -> dict[str, str]:
    """Each scenario's outcome on *backend* in a JUnit report, read from the cases of
    the backend's module and store only. Raises ValueError on a duplicate case."""
    profile = PROFILES[backend]
    names: set[str] = set()
    found: dict[str, str] = {}
    for case in junit_root(raw).iter("testcase"):
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


def rust_class(backend: str, runtime: str) -> str:
    """The JUnit class of the Rust runner's cases on *backend* and *runtime*."""
    return f"conformance.{backend}.{runtime}"


def rust_id(commit: str, backend: str, runtime: str) -> str:
    """The id of the Rust receipt of a pass at *commit*, and its retained file's name,
    with `+` and `_` written `-`."""
    return f"rust-{commit[:7]}-{backend.replace('+', '-')}-{runtime.replace('_', '-')}"


def rust_outcomes(raw: bytes, backend: str, runtime: str) -> dict[str, str]:
    """Each scenario's outcome in the Rust runner's pass on *backend* and *runtime*,
    read from that pass's cases only. Raises ValueError on a duplicate case."""
    found: dict[str, str] = {}
    for case in junit_root(raw).iter("testcase"):
        if case.get("classname") != rust_class(backend, runtime):
            continue
        name = case.get("name", "")
        if name in found:
            raise ValueError(f"duplicate JUnit case {name}")
        found[name] = case_outcome(case)
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
            read += 2 if word in _ENV_OPTIONS_WITH_ARGUMENT else 1
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


def junit(run: dict[str, Any], raw: bytes) -> dict[str, str]:
    """Each scenario's outcome in the Python runner's report, on the receipt's
    exact case/backend, including skips and errors. Raises ValueError when the
    receipt's profile or command cannot be read so."""
    profile = PROFILES.get(run["backend"])
    if run["implementation"] != "python" or profile is None or run["runtime"] != "asyncio":
        raise ValueError("unsupported pytest execution profile")
    turns = turn_backend(run["command"])
    if (turns == "redis") != profile.redis_turns:
        selects = "does not select" if profile.redis_turns else "selects"
        raise ValueError(
            f"its command {selects} the kit's turns across Redis "
            f"({TURN_BACKEND}=redis), unlike its backend {run['backend']}"
        )
    return outcomes(raw, run["backend"])


def rust_junit(run: dict[str, Any], raw: bytes) -> dict[str, str]:
    """Each scenario's outcome in the Rust runner's pass: its cases' class names
    the backend and the runtime, so the command is not read. Raises ValueError
    when the receipt is not that pass's."""
    profile = (run["backend"], run["runtime"])
    if run["implementation"] != "rust" or profile not in RUST_PROFILES:
        raise ValueError("unsupported Rust execution profile")
    if "scenario_filter" in run:
        raise ValueError("a Rust receipt holds its whole pass, never a scenario_filter")
    name = rust_id(run["implementation_commit"], *profile)
    if run["id"] != name or Path(run["artifact"]["path"]).name != f"{name}.xml":
        raise ValueError(f"a Rust receipt and its file are named {name}")
    return rust_outcomes(raw, *profile)


def cargo(run: dict[str, Any], raw: bytes) -> dict[str, str]:
    """Aggregate cargo summaries cannot identify the executed backend and IDs."""
    raise ValueError(
        "cargo receipts are unsupported: aggregate output does not prove the backend "
        "and scenario selection; retain the run outside the coverage registry"
    )


# The reader of each artifact format; any other format is `cargo`'s.
READERS: dict[str, Callable[[dict[str, Any], bytes], dict[str, str]]] = {
    "pytest_junit": junit,
    "cargo_junit": rust_junit,
}
