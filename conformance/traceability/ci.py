"""Receipts from roomkit CI: the reports of its `integration-junit` artifact, the
commands that wrote them, and the check that CI still runs those commands."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .importer import Recording, prepare
from .references import git_text


class CiReport(NamedTuple):
    """A JUnit report of the artifact, and the command that wrote it."""

    file: str
    name: str
    backends: tuple[str, ...]
    command: tuple[str, ...]  # as its receipts record it
    step: str  # the step of the integration job, whitespace collapsed, comments left out


CI_WORKFLOW = ".github/workflows/ci.yml"
CI_JOB = "integration"
CI_ARTIFACT = "integration-junit"
_DSN = "postgresql://postgres:postgres@localhost:5432/roomkit_test"
_REDIS = "redis://localhost:6379"
# The job's environment, which every step of the job runs with.
CI_JOB_ENV = f"POSTGRES_DSN: {_DSN} REDIS_URL: {_REDIS}"
CI_REPORTS = (
    CiReport(
        "postgres-scenarios.xml",
        "python-postgres-scenarios",
        ("postgres",),
        ("env", f"POSTGRES_DSN={_DSN}", f"REDIS_URL={_REDIS}", "uv", "run", "pytest", "-v",
         "-n", "auto", "--dist", "worksteal", "--junitxml=postgres-scenarios.xml",
         "tests/conformance/test_postgres.py"),
        "- name: Run the shared scenarios on PostgreSQL run: >- uv run pytest -v -n auto "
        "--dist worksteal --junitxml=test-results/postgres-scenarios.xml "
        "tests/conformance/test_postgres.py",
    ),
    CiReport(
        "redis-turns.xml",
        "python-redis-turns",
        ("memory+redis-turns", "sqlite+redis-turns"),
        ("env", "-u", "POSTGRES_DSN", "ROOMKIT_TEST_TURN_BACKEND=redis", f"REDIS_URL={_REDIS}",
         "uv", "run", "--with", "fastapi", "--with", "httpx2", "pytest", "-q", "-n", "auto",
         "--dist", "worksteal", "--junitxml=redis-turns.xml"),
        "- name: Run the suite with the kit's turns across Redis env: "
        "ROOMKIT_TEST_TURN_BACKEND: redis run: env -u POSTGRES_DSN uv run --with fastapi "
        "--with httpx2 pytest -q -n auto --dist worksteal "
        "--junitxml=test-results/redis-turns.xml",
    ),
)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _body(lines: list[str], start: int, indent: int) -> list[str]:
    """The lines under `lines[start]`: blank, or deeper than *indent*."""
    body = []
    for line in lines[start + 1 :]:
        if line.strip() and _indent(line) <= indent:
            break
        body.append(line)
    return body


def _collapse(lines: list[str]) -> str:
    return " ".join(
        word for line in lines if not line.lstrip().startswith("#") for word in line.split()
    )


def _steps(job: list[str]) -> list[str]:
    """Each step of the job, collapsed."""
    if "    steps:" not in job:
        return []
    blocks: list[list[str]] = []
    for line in _body(job, job.index("    steps:"), 4):
        if _indent(line) == 6 and line.lstrip().startswith("- "):
            blocks.append([])
        if blocks:
            blocks[-1].append(line)
    return [_collapse(block) for block in blocks]


def workflow_drift(workflow: str, report: CiReport) -> list[str]:
    """How the workflow no longer runs *report*'s command exactly as recorded: a
    workflow environment, another job environment, or another step."""
    lines = workflow.splitlines()
    fix = f"update CI_REPORTS ({report.file}) to what CI runs"
    if any(re.match(r"env\s*:", line) for line in lines):  # block or flow style
        return [f"{CI_WORKFLOW} sets a workflow environment: {fix}"]
    if f"  {CI_JOB}:" not in lines:
        return [f"{CI_WORKFLOW} has no job {CI_JOB}: {fix}"]
    job = _body(lines, lines.index(f"  {CI_JOB}:"), 2)
    drift = []
    env = next((_collapse(_body(job, i, 4)) for i, line in enumerate(job) if line == "    env:"), "")
    if env != CI_JOB_ENV:
        drift.append(f"{CI_WORKFLOW}: the {CI_JOB} job's environment is {env!r}: {fix}")
    if report.step not in _steps(job):
        drift.append(f"{CI_WORKFLOW}: no {CI_JOB} step is {report.step!r}: {fix}")
    return drift


def run_gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def ci_run(repository: str, commit: str, gh: Callable[..., str] = run_gh) -> int:
    """The latest completed push run of the CI workflow on *commit*, when it succeeded."""
    runs = json.loads(
        gh("run", "list", "-R", repository, "--commit", commit, "--workflow", "CI",
           "--event", "push", "--json", "databaseId,status,conclusion")
    )
    done = [run for run in runs if run["status"] == "completed"]
    if not done or done[0]["conclusion"] != "success":
        raise ValueError(f"no successful CI run of {commit} in {repository}: {runs}")
    return done[0]["databaseId"]


def from_ci(
    specs: Path,
    python_repo: Path,
    repository: str,
    commit: str,
    gh: Callable[..., str] = run_gh,
) -> tuple[list[Recording], list[str]]:
    """The recordings of the reports CI's run of *commit* holds, and what it did
    not record. Nothing is written."""
    workflow = git_text(python_repo, commit, CI_WORKFLOW)
    run = ci_run(repository, commit, gh)
    notes = [f"CI run {run} of {commit}"]
    recordings = []
    with tempfile.TemporaryDirectory() as directory:
        gh("run", "download", str(run), "-R", repository, "-n", CI_ARTIFACT, "-D", directory)
        for report in CI_REPORTS:
            path = Path(directory) / report.file
            if not path.exists():
                notes.append(f"{report.file}: not in the run's {CI_ARTIFACT}, not recorded")
                continue
            if drift := workflow_drift(workflow, report):
                raise ValueError("; ".join(drift))
            recordings.append(
                prepare(specs, python_repo, path.read_bytes(), report.name,
                        list(report.backends), list(report.command))
            )
    if not recordings:
        raise ValueError(f"the run's {CI_ARTIFACT} artifact holds no report to record")
    return recordings, notes
