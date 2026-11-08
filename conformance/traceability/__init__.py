"""Traceability checks used by the existing conformance checker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import evidence, report, source
from .provenance import provenance
from .references import git_text


def layout(value: Any) -> str:
    """The conformance suite's JSON layout."""
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def inventory_schema() -> dict[str, Any]:
    """Section review records are explicit; regeneration never updates them."""
    return {
        "type": "object",
        "required": ["version", "sections"],
        "additionalProperties": False,
        "properties": {
            "version": {"const": 1},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section", "sha256", "classification", "review"],
                    "additionalProperties": False,
                    "properties": {
                        "section": {"type": "string", "minLength": 1},
                        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "classification": {"enum": ["normative", "informative"]},
                        "review": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


def check(
    root: Path,
    text: str,
    scenarios: list[dict[str, Any]],
    *,
    python_repo: Path | None = None,
    rust_repo: Path | None = None,
    update: bool = False,
    base_ref: str | None = None,
) -> list[str]:
    """Validate sources first, then check or regenerate the derived artifacts."""
    directory = root / "conformance"
    try:
        registry = source.extract(text)
        document = json.loads((directory / "evidence.json").read_text())
        reviews = json.loads((directory / "inventory.json").read_text())
        schema = json.loads((directory / "evidence.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        errors = [
            f"evidence: {'/'.join(map(str, error.path))}: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(document)
        ]
        errors += [
            f"inventory: {error.message}"
            for error in Draft202012Validator(inventory_schema()).iter_errors(reviews)
        ]
        if errors:
            return errors
        by_id = {scenario["id"]: scenario for scenario in scenarios}
        errors += evidence.validate(document, registry, by_id, python_repo)
        errors += provenance(document, root, {"python": python_repo, "rust": rust_repo})
        previous = {"requirements": []}
        retired = []
        if base_ref is not None:
            previous = source.extract(git_text(root, base_ref, "roomkit-rfc.md"))
            try:
                retired = json.loads(
                    git_text(root, base_ref, "conformance/evidence.json")
                )["retired"]
            except ValueError:
                # The baseline predates traceability only when it has no annotated IDs.
                if previous["requirements"]:
                    raise
        errors += source.check_history(registry, previous, document["retired"], retired)
        coverage, review_errors = report.build(registry, document, by_id, reviews)
        errors += review_errors
        if errors:
            return errors
        for name, value in [
            ("requirements.json", layout(registry)),
            ("coverage.json", layout(coverage)),
            ("coverage.md", report.markdown(coverage)),
        ]:
            errors += report.artifact(directory / name, value, update)
        return errors
    except (OSError, ValueError) as error:
        return [f"traceability: {error}"]
