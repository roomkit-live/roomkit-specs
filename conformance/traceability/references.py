"""Resolve explicit assertion and Python source references at pinned revisions."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from .source import digest, text_digest

COMMIT = re.compile(r"[0-9a-f]{40}")
ASSERTION = re.compile(r"/(?:expect(?:/|$)|steps/[0-9]+/expect(?:/|$))")


def pointer(document: Any, path: str) -> Any:
    """Read an RFC 6901 pointer, including empty arrays as absence assertions."""
    if not path.startswith("/"):
        raise ValueError(f"not a JSON pointer: {path!r}")
    value = document
    for raw in path[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise ValueError(f"invalid pointer escape in {path!r}")
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part) or int(part) >= len(value):
                raise ValueError(f"pointer does not resolve: {path}")
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise ValueError(f"pointer does not resolve: {path}")
    return value


def check_assertion(reference: dict[str, Any], scenarios: dict[str, Any]) -> list[str]:
    """A link names an actual expectation and pins the expectation's value."""
    name, path = reference["scenario"], reference["pointer"]
    if name not in scenarios:
        return [f"unknown scenario {name}"]
    if not ASSERTION.match(path):
        return [f"{name}: {path} is not an expectation"]
    try:
        expected = pointer(scenarios[name], path)
    except ValueError as error:
        return [f"{name}: {error}"]
    if reference["sha256"] != digest(expected):
        return [f"{name}:{path}: assertion changed; review its requirement link"]
    if reference["scenario_sha256"] != digest(scenarios[name]):
        return [f"{name}: scenario changed; review its requirement link"]
    return []


def git_text(repo: Path, commit: str, path: str) -> str:
    """Read a relative file from a named commit, never from a mutable checkout."""
    relative = PurePosixPath(path)
    if not COMMIT.fullmatch(commit) or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(
            "a source reference needs a full commit and a safe relative path"
        )
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"source unavailable: {commit}:{path}")
    return result.stdout


def python_symbol(text: str, name: str) -> str:
    """Find a qualified function and its decorators without importing the test."""
    body = ast.parse(text).body
    node = None
    for part in name.split("::"):
        node = next(
            (
                item
                for item in body
                if isinstance(
                    item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
                and item.name == part
            ),
            None,
        )
        if node is None:
            raise ValueError(f"unknown Python symbol {name}")
        body = node.body
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f"{name} is not a test function")  # noqa: TRY004 — invalid name, not argument type
    start = min([node.lineno, *(item.lineno for item in node.decorator_list)])
    return "\n".join(text.splitlines()[start - 1 : node.end_lineno])


def check_test(reference: dict[str, str], repo: Path, commit: str) -> list[str]:
    """Validate the exact qualified test, not a file or a name guessed from it."""
    try:
        path, name = reference["nodeid"].split("::", 1)
        text = git_text(repo, commit, path)
        symbol = python_symbol(text, name)
        if text_digest(symbol) != reference["sha256"]:
            return [f"{reference['nodeid']}: test changed; review its requirement link"]
    except (ValueError, SyntaxError) as error:
        return [f"{reference['nodeid']}: {error}"]
    return []
