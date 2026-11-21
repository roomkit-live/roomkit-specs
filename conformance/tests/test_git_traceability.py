from __future__ import annotations

import copy
import hashlib
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
from traceability import check, layout, receipts
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
            lambda d: d["executions"][0].update(results_sha256="f" * 64),
            lambda d: d["executions"][0].update(counts={"passed": 2}),
            lambda d: d["executions"][0].update(backend="redis"),
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

    def coverage_rows(self) -> list[tuple[str, str]]:
        """The (execution, state) rows coverage.json gives the link."""
        coverage = json.loads((self.directory / "coverage.json").read_text())
        (link,) = coverage["requirements"][0]["links"]
        return [(row["execution"], row["state"]) for row in link["executions"]]

    def test_a_receipt_holds_no_results_the_checker_derives_them(self) -> None:
        memory, sqlite = self.document["executions"]
        for run in (memory, sqlite):
            self.assertNotIn("results", run)
        self.assertEqual(
            (memory["counts"], sqlite["counts"]), ({"passed": 1, "skipped": 1}, {"failed": 1})
        )
        self.assertEqual(self.compare(), [])
        # The link asserts scenario `a`, which the report holds as passed on memory
        # and failed on SQLite; its specialized test leaves the pass incomplete.
        self.assertEqual(
            self.coverage_rows(), [(memory["id"], "incomplete"), (sqlite["id"], "not_passed")]
        )

    def test_the_guard_refuses_a_reader_that_reads_an_old_report_otherwise(self) -> None:
        memory = self.document["executions"][0]["id"]

        def skips_read_as_passes(case) -> str:
            return "failed" if case.find("failure") is not None else "passed"

        with patch("traceability.receipts.case_outcome", skips_read_as_passes):
            errors = self.compare()
        self.assertEqual(
            errors,
            [
                f"{memory}: its report now reads {{'passed': 2}}, "
                "the receipt recorded {'passed': 1, 'skipped': 1}",
                f"{memory}: the results its report and corpus derive differ from its "
                "results_sha256",
            ],
        )

    def test_the_guard_refuses_swapped_outcomes_that_keep_the_counts(self) -> None:
        memory = self.document["executions"][0]["id"]
        read = receipts.outcomes

        def swapped(raw: bytes, backend: str) -> dict[str, str]:
            found = read(raw, backend)
            if {"a", "b"} <= found.keys():
                found["a"], found["b"] = found["b"], found["a"]
            return found

        with patch("traceability.receipts.outcomes", swapped):
            errors = self.compare()
        self.assertEqual(
            errors,
            [
                f"{memory}: the results its report and corpus derive differ from its "
                "results_sha256"
            ],
        )

    def test_a_missing_or_unreadable_report_is_an_error_not_a_traceback(self) -> None:
        names = [run["id"] for run in self.document["executions"]]
        report = self.root / self.document["executions"][0]["artifact"]["path"]
        content = report.read_bytes()
        report.unlink()
        errors = self.compare()
        self.assertEqual(len(errors), 2, errors)
        for name, error in zip(names, errors, strict=True):
            self.assertRegex(error, f"^{name}: cannot read execution artifact: .*No such file")
        report.write_bytes(content[: len(content) // 2])
        for run in self.document["executions"]:
            run["artifact"]["sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
        self.write_document(self.document)
        errors = self.compare()
        self.assertEqual(len(errors), 2, errors)
        for name, error in zip(names, errors, strict=True):
            self.assertRegex(error, f"^{name}: cannot read the JUnit report: ")

    def test_the_report_leaves_out_a_superseded_receipt_s_rows(self) -> None:
        self.assertEqual(self.compare(), [])
        self.assertEqual(len(self.coverage_rows()), 2)
        # Scenario `a` changed since the run: both receipts are superseded.
        self.cases[0]["expect"]["v"] = 3
        self.document["links"][0]["assertions"][0].update(
            sha256=digest(self.cases[0]["expect"]),
            scenario_sha256=digest(self.cases[0]),
        )
        self.write_document(self.document)
        self.assertEqual(self.compare(), [])
        self.assertEqual(self.coverage_rows(), [])
        markdown = (self.directory / "coverage.md").read_text()
        self.assertNotIn("stale", markdown)
        for run in self.document["executions"]:
            self.assertIn(f"- `{run['id']}`:", markdown)

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
