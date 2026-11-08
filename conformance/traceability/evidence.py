"""Validate reviewed mappings and report only the executions they actually name."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .references import check_assertion, check_test
from .source import digest


def validate(
    document: dict[str, Any],
    registry: dict[str, Any],
    scenarios: dict[str, Any],
    python_repo: Path | None,
) -> list[str]:
    """Check semantics after JSON Schema, without treating references as passes."""
    requirements = {item["id"]: item for item in registry["requirements"]}
    errors = []
    ids = set()
    for link in document["links"]:
        name = link["id"]
        if name in ids:
            errors.append(f"duplicate evidence link {name}")
        ids.add(name)
        if link["requirement"] not in requirements:
            errors.append(f"{name}: unknown requirement {link['requirement']}")
            continue
        requirement = requirements[link["requirement"]]
        if link["clause_sha256"] != requirement["sha256"]:
            errors.append(
                f"{name}: clause or applicability changed; review the mapping"
            )
        if not link["assertions"] and not link["tests"]:
            errors.append(f"{name}: a mapping needs an assertion or a specialized test")
        if link["coverage"] == "complete" and link["missing"]:
            errors.append(f"{name}: a complete mapping cannot list missing cases")
        if link["coverage"] == "partial" and not link["missing"]:
            errors.append(f"{name}: a partial mapping must explain what remains")
        for reference in link["assertions"]:
            errors += [
                f"{name}: {error}" for error in check_assertion(reference, scenarios)
            ]
        if link["tests"] and python_repo is None:
            errors.append(
                f"{name}: --python-repo is required to validate the pinned tests"
            )
        elif python_repo is not None:
            for reference in link["tests"]:
                errors += [
                    f"{name}: {error}"
                    for error in check_test(
                        reference, python_repo, document["python_commit"]
                    )
                ]
    errors += validate_executions(document, scenarios)
    return errors


def validate_executions(
    document: dict[str, Any], scenarios: dict[str, Any]
) -> list[str]:
    """A receipt records results; it cannot silently upgrade a skip to a pass."""
    errors = []
    ids = set()
    for run in document["executions"]:
        if run["id"] in ids:
            errors.append(f"duplicate execution {run['id']}")
        ids.add(run["id"])
        if not run["command"] or not run["results"]:
            errors.append(f"{run['id']}: empty execution command or result set")
        seen = set()
        for result in run["results"]:
            name = result["scenario"]
            if name in seen:
                errors.append(f"{run['id']}: duplicate result {name}")
            seen.add(name)
            if name not in scenarios:
                errors.append(f"{run['id']}: unknown scenario {name}")
            # A historical receipt is retained even when its scenario changed.
            # execution_status marks it stale rather than applying it to new data.
    return errors


def execution_status(
    link: dict[str, Any],
    runs: list[dict[str, Any]],
    scenarios: dict[str, Any],
    rfc_sha256: str,
    python_commit: str,
) -> list[dict[str, Any]]:
    """Keep per-revision/backend results separate; never union partial runs."""
    wanted = {assertion["scenario"] for assertion in link["assertions"]}
    reported = []
    for run in runs:
        selected = {
            item["scenario"]: item
            for item in run["results"]
            if item["scenario"] in wanted
        }
        if not selected:
            continue
        state = "recorded_pass"
        if wanted != selected.keys() or link["tests"]:
            state = "incomplete"
        if any(item["outcome"] != "passed" for item in selected.values()):
            state = "not_passed"
        if run["rfc_sha256"] != rfc_sha256 or any(
            item["sha256"] != digest(scenarios[name]) for name, item in selected.items()
        ):
            state = "stale"
        if (
            run["implementation"] == "python"
            and run["implementation_commit"] != python_commit
        ):
            state = "stale"
        reported.append(
            {
                "execution": run["id"],
                "implementation": run["implementation"],
                "commit": run["implementation_commit"],
                "backend": run["backend"],
                "runtime": run["runtime"],
                "state": state,
            }
        )
    return reported


def requirement_status(
    requirement: dict[str, Any],
    links: list[dict[str, Any]],
    document: dict[str, Any],
    scenarios: dict[str, Any],
    rfc_sha256: str,
) -> dict[str, Any]:
    """Expose mapped scope and remaining gaps without claiming conformance."""
    selected = [link for link in links if link["requirement"] == requirement["id"]]
    coverage = "unmapped"
    if selected:
        coverage = "mapped_partial"
    if any(link["coverage"] == "complete" for link in selected):
        coverage = "mapped_complete"
    return {
        "id": requirement["id"],
        "section": requirement["section"],
        "mapping": coverage,
        "links": [
            {
                "id": link["id"],
                "scope": link["scope"],
                "coverage": link["coverage"],
                "missing": link["missing"],
                "executions": execution_status(
                    link,
                    document["executions"],
                    scenarios,
                    rfc_sha256,
                    document["python_commit"],
                ),
            }
            for link in selected
        ],
    }
