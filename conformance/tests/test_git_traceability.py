from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_record
from traceability import check, layout
from traceability._git import GitReader
from traceability.references import git_text
from traceability.source import digest, extract, text_digest

ARTIFACTS = ("requirements.json", "coverage.json", "coverage.md")


class BatchedTraceabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = test_record.RecordingTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root, self.python = fixture.specs, fixture.python
        self.directory = self.root / "conformance"
        self.text = (self.root / "roomkit-rfc.md").read_text()
        self.source = "def test_value():\n    assert 1 == 1\n"
        (self.python / "tests/test_value.py").write_text(self.source)
        fixture.python_commit = fixture.commit(self.python)
        fixture.evidence["python_commit"] = fixture.python_commit
        self.write_document(fixture.evidence)
        recording = fixture.record(["memory+redis-turns", "sqlite+redis-turns"])
        test_record.write(self.root, [recording])
        self.document = json.loads((self.directory / "evidence.json").read_text())
        schema = Path(__file__).resolve().parents[1] / "evidence.schema.json"
        (self.directory / schema.name).write_bytes(schema.read_bytes())
        (self.directory / "inventory.json").write_text(
            layout({"version": 1, "sections": []})
        )
        self.cases = list(fixture.scenarios.values())
        requirement = extract(self.text)["requirements"][0]
        self.document["links"] = [
            {
                "id": "value",
                "requirement": requirement["id"],
                "clause_sha256": requirement["sha256"],
                "scope": "one value",
                "coverage": "partial",
                "review": "fixture",
                "missing": ["other cases"],
                "tests": [
                    {
                        "nodeid": "tests/test_value.py::test_value",
                        "sha256": text_digest(self.source.rstrip()),
                        "proves": "source",
                    }
                ],
                "assertions": [
                    {
                        "scenario": "a",
                        "pointer": "/expect",
                        "sha256": digest(self.cases[0]["expect"]),
                        "scenario_sha256": digest(self.cases[0]),
                        "proves": "value",
                    }
                ],
            }
        ]
        self.write_document(self.document)

    def write_document(self, document) -> None:
        (self.directory / "evidence.json").write_text(layout(document))

    def artifacts(self) -> dict[str, bytes]:
        return {
            name: (self.directory / name).read_bytes()
            for name in ARTIFACTS
            if (self.directory / name).exists()
        }

    def compare(self) -> list[str]:
        before = self.artifacts()
        with patch(
            "traceability.GitReader",
            return_value=nullcontext(SimpleNamespace(read=git_text)),
        ):
            old = check(
                self.root, self.text, self.cases, python_repo=self.python, update=True
            )
        expected = self.artifacts()
        new = check(
            self.root, self.text, self.cases, python_repo=self.python, update=True
        )
        self.assertEqual(new, old)
        self.assertEqual(self.artifacts(), expected)
        if old:
            self.assertEqual(
                expected, before, "failed provenance must not write artifacts"
            )
        return new

    def test_identical_reports_with_sources_and_historical_receipts(self) -> None:
        self.assertEqual(self.compare(), [])
        self.assertEqual(len(self.artifacts()), 3)
        self.assertEqual(
            json.loads((self.directory / "evidence.json").read_text()), self.document
        )

    def test_invalid_provenance_matches_old_verdict_without_writing_reports(
        self,
    ) -> None:
        self.assertEqual(self.compare(), [])
        original = copy.deepcopy(self.document)
        mutations = [
            lambda d: d["links"][0]["tests"][0].update(sha256="f" * 64),
            lambda d: d["executions"][0].update(corpus_commit="0" * 40),
            lambda d: d["executions"][0]["artifact"].update(sha256="f" * 64),
            lambda d: d["executions"][0]["results"][0].update(sha256="f" * 64),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                document = copy.deepcopy(original)
                mutate(document)
                self.write_document(document)
                self.assertTrue(self.compare())

    def test_stale_receipt_still_checks_the_copy_at_its_own_revision(self) -> None:
        self.cases[0]["expect"]["v"] = 3
        self.document["links"][0]["assertions"][0].update(
            sha256=digest(self.cases[0]["expect"]),
            scenario_sha256=digest(self.cases[0]),
        )
        self.write_document(self.document)
        self.assertEqual(self.compare(), [])
        copied = self.python / "tests/conformance/scenarios/a.json"
        copied.write_text(layout(self.cases[0]))
        changed = self.fixture.commit(self.python)
        self.document["executions"][0]["implementation_commit"] = changed
        self.write_document(self.document)
        errors = self.compare()
        self.assertTrue(
            any("implementation's copy differs" in error for error in errors), errors
        )

    def test_schema_failure_starts_no_git_and_writes_no_reports(self) -> None:
        self.document["extra"] = True
        self.write_document(self.document)
        with patch("traceability._git.subprocess.Popen") as start:
            self.assertTrue(
                check(
                    self.root,
                    self.text,
                    self.cases,
                    python_repo=self.python,
                    update=True,
                )
            )
            start.assert_not_called()
        self.assertEqual(self.artifacts(), {})

    def test_reader_close_failure_prevents_report_generation(self) -> None:
        class FailingClose(GitReader):
            def __exit__(self, *args):
                super().__exit__(*args)
                raise ValueError("reader could not finish")

        with patch("traceability.GitReader", FailingClose):
            errors = check(
                self.root, self.text, self.cases, python_repo=self.python, update=True
            )
        self.assertEqual(errors, ["traceability: reader could not finish"])
        self.assertEqual(self.artifacts(), {})

    def test_all_children_exit_before_report_generation(self) -> None:
        from traceability import report

        children = []
        popen, build = subprocess.Popen, report.build

        def start(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        def after_exit(*args, **kwargs):
            self.assertEqual(len(children), 2)
            self.assertTrue(all(child.poll() == 0 for child in children))
            return build(*args, **kwargs)

        with (
            patch("traceability._git.subprocess.Popen", side_effect=start),
            patch("traceability.report.build", side_effect=after_exit),
        ):
            self.assertEqual(
                check(
                    self.root,
                    self.text,
                    self.cases,
                    python_repo=self.python,
                    update=True,
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
