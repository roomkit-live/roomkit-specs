"""Check receipt revisions and the actual corpus copied into each implementation.

The receipts come with the results `receipts.with_results` derived from their
retained reports and the corpus at their corpus commits."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .references import GitText, git_text
from .source import extract, scenario_digest


def copied_scenarios(
    run: dict[str, Any], repo: Path, *, read: GitText = git_text
) -> list[str]:
    """A test of one copy cannot certify assertions taken from another copy."""
    prefix = "tests/conformance" if run["implementation"] == "python" else "conformance"
    commit = run["implementation_commit"]
    errors = []
    for result in run["results"]:
        copied = json.loads(
            read(repo, commit, f"{prefix}/scenarios/{result['scenario']}.json")
        )
        if scenario_digest(copied) != result["sha256"]:
            errors.append(
                f"{run['id']}: {result['scenario']}: implementation's copy differs"
            )
    if run["implementation"] == "rust":
        # A Rust receipt is a whole pass: every scenario of the copy, narrowed only
        # by `scenario_filter`, never a selection of the cases it reported.
        names = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "ls-tree",
                "-r",
                "--name-only",
                commit,
                "--",
                f"{prefix}/scenarios/",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        selected = {
            name.removeprefix(f"{prefix}/scenarios/").removesuffix(".json")
            for name in names
            if name.endswith(".json")
        }
        needle = run.get("scenario_filter", "")
        selected = {name for name in selected if needle in name}
        if selected != {item["scenario"] for item in run["results"]}:
            errors.append(
                f"{run['id']}: Rust receipt does not contain its entire filtered selection"
            )
    return errors


def provenance(
    document: dict[str, Any],
    root: Path,
    repositories: dict[str, Path | None],
    *,
    read: GitText = git_text,
) -> list[str]:
    """Receipts point to real source versions, not merely SHA-shaped strings."""
    errors = []
    for run in document["executions"]:
        try:
            rfc = extract(read(root, run["rfc_commit"], "roomkit-rfc.md"))
            if rfc["rfc_sha256"] != run["rfc_sha256"]:
                errors.append(
                    f"{run['id']}: RFC receipt fingerprint does not match its commit"
                )
            implementation = run["implementation"]
            repository = repositories.get(implementation)
            if repository is None:
                errors.append(
                    f"{run['id']}: --{implementation}-repo required for implementation provenance"
                )
            else:
                errors += copied_scenarios(run, repository, read=read)
        except (ValueError, subprocess.CalledProcessError) as error:
            errors.append(f"{run['id']}: {error}")
    return errors
