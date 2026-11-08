"""Match execution receipts to saved runner output, without running commands."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


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


def junit(run: dict[str, Any], raw: bytes) -> list[str]:
    """Resolve the Python runner's exact case/backend, including skips and errors."""
    if (
        run["implementation"] != "python"
        or run["backend"] not in {"memory", "sqlite"}
        or run["runtime"] != "asyncio"
    ):
        return [f"{run['id']}: unsupported pytest execution profile"]
    cases: dict[str, str] = {}
    for case in ET.fromstring(raw).iter("testcase"):
        if case.get("classname") != "tests.conformance.test_conformance":
            continue
        name = case.get("name", "")
        if name in cases:
            return [f"{run['id']}: duplicate JUnit case {name}"]
        outcome = "passed"
        if case.find("skipped") is not None:
            outcome = "skipped"
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        cases[name] = outcome
    errors = []
    for result in run["results"]:
        name = result["scenario"]
        suffix = "[sqlite]" if run["backend"] == "sqlite" else ""
        actual = cases.get(f"test_scenario[{name}{suffix}]", "not_run")
        if actual != result["outcome"]:
            errors.append(
                f"{run['id']}: {name}: receipt says {result['outcome']}, JUnit says {actual}"
            )
    return errors


def cargo(run: dict[str, Any], text: str) -> list[str]:
    """Read a complete, zero-failure scenario pass of one Rust runtime."""
    if run["implementation"] != "rust" or run["backend"] != "memory":
        return [
            f"{run['id']}: cargo receipts currently support only Rust's memory backend"
        ]
    labels = {"current_thread": "one thread", "multi_thread:4": "four workers"}
    label = labels.get(run["runtime"])
    if label is None:
        return [f"{run['id']}: unsupported cargo runtime"]
    pattern = re.escape(label) + r": (\d+) scenarios, 0 failing: \[\]"
    summaries = re.findall(r"^" + pattern + r"$", text, re.MULTILINE)
    if len(summaries) != 1 or int(summaries[0]) != len(run["results"]):
        return [
            f"{run['id']}: cargo scenario summary does not match the receipt's complete selection"
        ]
    if "test result: FAILED" in text or "test result: ok." not in text:
        return [f"{run['id']}: cargo test did not finish successfully"]
    if any(result["outcome"] != "passed" for result in run["results"]):
        return [f"{run['id']}: zero-failure cargo summary requires passing results"]
    return []
