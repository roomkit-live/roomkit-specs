"""Record Python execution receipts from pytest JUnit reports, never by hand.

A report is cleaned (no host, timestamp, duration or local path), retained under
`conformance/executions/`, and each backend it holds becomes one receipt in
`evidence.json` at the evidence's `python_commit`.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, NamedTuple

from . import layout
from .evidence import validate_executions
from .receipts import PROFILES, junit, outcomes
from .references import git_text
from .source import digest, extract

# The attributes a retained report keeps; every other one (hostname, timestamp,
# time, file, line, ...) and every other element (properties, system-out,
# system-err) is dropped, with all element text (tracebacks, captured output).
_KEPT = {
    "testcase": ("classname", "name"),
    "skipped": ("type", "message"),
    "failure": ("type", "message"),
    "error": ("type", "message"),
}
_OUTCOMES = ("skipped", "failure", "error")

# A path under a machine's own directories, up to its last separator.
_LOCAL_PATH = re.compile(
    r"(?<![\w.~-])/(?:home|Users|root|tmp|private|var|opt|usr|github|__w|mnt|srv|nix)/"
    r"(?:[^/\s'\":]+/)*"
)


class Recording(NamedTuple):
    """A cleaned report and the receipts it supports, before anything is written."""

    artifact: Path
    content: bytes
    receipts: list[dict[str, Any]]


def clean(raw: bytes, modules: set[str]) -> bytes:
    """The report's cases of *modules*, each with its class, name and outcome, and
    the reason pytest gave for a skip or a failure with local paths cut out. The
    suite counts are recomputed from the cases kept."""
    source = ET.fromstring(raw)
    if source.tag not in ("testsuites", "testsuite"):
        raise ValueError(f"not a JUnit report: root element {source.tag}")
    cases = [case for case in source.iter("testcase") if case.get("classname") in modules]
    suite = ET.Element("testsuite", {"name": "pytest"})
    for case in cases:
        suite.append(_copy(case))
    for tag, count in [
        ("errors", "error"),
        ("failures", "failure"),
        ("skipped", "skipped"),
    ]:
        suite.set(tag, str(sum(case.find(count) is not None for case in cases)))
    suite.set("tests", str(len(cases)))
    root = ET.Element("testsuites", {"name": "pytest tests"})
    root.append(suite)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _copy(case: ET.Element) -> ET.Element:
    kept = ET.Element("testcase", _attributes(case))
    for child in case:
        if child.tag in _OUTCOMES:
            kept.append(ET.Element(child.tag, _attributes(child)))
    return kept


def _attributes(element: ET.Element) -> dict[str, str]:
    """The kept attributes; a message loses the local directories of its paths.
    A case's class and name are its identity and stay as pytest wrote them."""
    kept = {}
    for name in _KEPT[element.tag]:
        value = element.get(name)
        if value is not None:
            kept[name] = _LOCAL_PATH.sub("", value) if name == "message" else value
    return kept


def leftovers(content: bytes) -> list[str]:
    """What a retained report must not carry: volatile attributes, text, local paths."""
    found = []
    for element in ET.fromstring(content).iter():
        allowed = _KEPT.get(element.tag, ("name", "errors", "failures", "skipped", "tests"))
        found += [f"{element.tag}@{name}" for name in element.attrib if name not in allowed]
        if (element.text or "").strip() or (element.tail or "").strip():
            found.append(f"{element.tag}: text")
        message = element.get("message", "")
        if _LOCAL_PATH.search(message):
            found.append(f"{element.tag}@message: local path")
    return found


_JUNIT_OPTIONS = ("--junitxml", "--junit-xml")


def portable(command: list[str]) -> list[str]:
    """The command with its JUnit output path reduced to the file name. Refuses
    a command that still names a local path: evidence.json is published."""
    words = []
    for position, word in enumerate(command):
        option, equals, path = word.partition("=")
        if option in _JUNIT_OPTIONS and equals:
            word = f"{option}={Path(path).name}"
        elif position and command[position - 1] in _JUNIT_OPTIONS:
            word = Path(word).name
        words.append(word)
    if local := [word for word in words if _LOCAL_PATH.search(word)]:
        raise ValueError(f"the command names local paths: {local}")
    return words


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def scenarios_at(repo: Path, commit: str, directory: str) -> dict[str, Any]:
    """Every scenario of *directory* at *commit*, by id."""
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", f"{commit}:{directory}"],
        capture_output=True,
        check=False,
    )
    if archive.returncode:
        raise ValueError(f"scenarios unavailable: {commit}:{directory}")
    found = {}
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as files:
        for member in files.getmembers():
            if member.isfile() and member.name.endswith(".json"):
                stream = files.extractfile(member)
                assert stream is not None
                found[member.name.removesuffix(".json")] = json.load(stream)
    return found


def current_scenarios(specs: Path) -> dict[str, Any]:
    directory = specs / "conformance" / "scenarios"
    return {
        path.relative_to(directory).with_suffix("").as_posix(): json.loads(path.read_text())
        for path in directory.glob("**/*.json")
    }


def revisions(specs: Path, python_repo: Path, commit: str) -> dict[str, Any]:
    """The revisions a receipt at *commit* names: the corpus its copy was synced
    from, and the last commit of the RFC, whose text must be the checkout's."""
    corpus = git_text(python_repo, commit, "tests/conformance/SPECS_COMMIT").strip()
    rfc_commit = git(specs, "log", "-1", "--format=%H", "--", "roomkit-rfc.md")
    rfc = git_text(specs, rfc_commit, "roomkit-rfc.md")
    if rfc != (specs / "roomkit-rfc.md").read_text():
        raise ValueError("roomkit-rfc.md differs from its last commit; commit it first")
    return {
        "implementation": "python",
        "implementation_commit": commit,
        "rfc_commit": rfc_commit,
        "corpus_commit": corpus,
        "rfc_sha256": extract(rfc)["rfc_sha256"],
    }


def prepare(
    specs: Path,
    python_repo: Path,
    raw: bytes,
    name: str,
    backends: list[str],
    command: list[str],
) -> Recording:
    """Clean *raw* and build its receipts at the evidence's `python_commit`,
    checked as `check.py` checks them. Nothing is written."""
    unknown = [backend for backend in backends if backend not in PROFILES]
    if unknown or not backends:
        raise ValueError(f"backends must be among {sorted(PROFILES)}: {unknown or 'none'}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError(f"a run name is lower-case words joined by hyphens: {name!r}")
    document = json.loads((specs / "conformance" / "evidence.json").read_text())
    commit = document["python_commit"]
    template = revisions(specs, python_repo, commit)
    content = clean(raw, {PROFILES[backend].module for backend in backends})
    if found := leftovers(content):
        raise ValueError(f"the cleaned report still carries {found}")
    artifact = specs / "conformance" / "executions" / f"{name}-{commit[:7]}.xml"
    if artifact.exists() and artifact.read_bytes() != content:
        raise ValueError(f"{artifact.name} exists with other content")
    template |= {
        "runtime": "asyncio",
        "command": portable(command),
        "artifact": {
            "path": artifact.relative_to(specs).as_posix(),
            "format": "pytest_junit",
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }
    corpus = scenarios_at(specs, template["corpus_commit"], "conformance/scenarios")
    copied = scenarios_at(python_repo, commit, "tests/conformance/scenarios")
    receipts = [
        receipt(template, f"{name}-{commit[:7]}", backend, content, corpus, copied)
        for backend in backends
    ]
    errors = validate_executions(
        {"executions": document["executions"] + receipts}, current_scenarios(specs)
    )
    for run in receipts:
        errors += junit(run, content)
    if errors:
        raise ValueError("; ".join(errors))
    return Recording(artifact, content, receipts)


# The order of a receipt's keys in evidence.json, as earlier receipts have them.
_RECEIPT_KEYS = (
    "id", "implementation", "implementation_commit", "rfc_commit", "corpus_commit",
    "rfc_sha256", "backend", "runtime", "command", "artifact", "results",
)


def receipt(
    template: dict[str, Any],
    prefix: str,
    backend: str,
    content: bytes,
    corpus: dict[str, Any],
    copied: dict[str, Any],
) -> dict[str, Any]:
    """The receipt of *backend*'s scenarios in the cleaned report."""
    found = outcomes(content, backend)
    if not found:
        raise ValueError(f"the report holds no {backend} scenario case")
    results = []
    for scenario in sorted(found):
        if scenario not in corpus:
            raise ValueError(f"{scenario}: not in the corpus at {template['corpus_commit']}")
        if scenario not in copied or digest(copied[scenario]) != digest(corpus[scenario]):
            raise ValueError(f"{scenario}: the implementation's copy differs from the corpus")
        results.append(
            {"scenario": scenario, "sha256": digest(corpus[scenario]), "outcome": found[scenario]}
        )
    run = {"id": f"{prefix}-{backend.replace('+', '-')}", "backend": backend, "results": results}
    return {key: run[key] if key in run else template[key] for key in _RECEIPT_KEYS}


def write(specs: Path, recordings: list[Recording]) -> list[dict[str, Any]]:
    """Retain each report and append its receipts to `evidence.json`."""
    path = specs / "conformance" / "evidence.json"
    document = json.loads(path.read_text())
    taken = {run["id"] for run in document["executions"]}
    new = [run for recording in recordings for run in recording.receipts]
    clashes = sorted(taken.intersection(run["id"] for run in new))
    if clashes or len({run["id"] for run in new}) != len(new):
        raise ValueError(f"receipt ids already recorded: {clashes or 'within this import'}")
    for recording in recordings:
        recording.artifact.write_bytes(recording.content)
    document["executions"] += new
    path.write_text(layout(document))
    return new


def counts(run: dict[str, Any]) -> dict[str, int]:
    tally: dict[str, int] = {}
    for result in run["results"]:
        tally[result["outcome"]] = tally.get(result["outcome"], 0) + 1
    return dict(sorted(tally.items()))
