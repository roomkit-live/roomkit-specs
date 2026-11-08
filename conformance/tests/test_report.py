from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_source import marked
from traceability.report import artifact, build, markdown
from traceability.source import extract


class ReportTests(unittest.TestCase):
    def test_section_citations_do_not_become_mappings(self) -> None:
        registry = extract("### 9.3 Hooks\n" + marked("A hook MUST return a result."))
        evidence = {"python_commit": "p", "links": [], "executions": []}
        scenarios = {"some-case": {"rules": ["§9.3"], "expect": {"anything": 1}}}
        report, errors = build(registry, evidence, scenarios, {"sections": []})
        self.assertEqual(errors, [])
        self.assertEqual(report["requirements"][0]["mapping"], "unmapped")
        self.assertEqual(report["sections"][0]["review"], "not_reviewed")
        self.assertIn(
            "1 annotated source units; 0 have reviewed mappings", markdown(report)
        )

    def test_a_changed_section_requires_inventory_review(self) -> None:
        before = extract("### 9.3 Hooks\nAn implicit rule.\n")
        review = {
            "section": "9.3",
            "sha256": before["sections"][0]["sha256"],
            "classification": "normative",
            "review": "Implicit rule reviewed.",
        }
        after = extract("### 9.3 Hooks\nA different implicit rule.\n")
        _, errors = build(
            after,
            {"python_commit": "p", "links": [], "executions": []},
            {},
            {"sections": [review]},
        )
        self.assertIn("source changed", errors[0])

    def test_a_reviewed_section_cannot_hide_unannotated_keywords(self) -> None:
        registry = extract("### 9.3 Hooks\nA hook MUST return a result.\n")
        review = {
            "section": "9.3",
            "sha256": registry["sections"][0]["sha256"],
            "classification": "normative",
            "review": "Reviewed.",
        }
        _, errors = build(
            registry,
            {"python_commit": "p", "links": [], "executions": []},
            {},
            {"sections": [review]},
        )
        self.assertIn("unannotated keywords", errors[0])

    def test_artifact_drift_fails_and_update_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coverage.md"
            self.assertTrue(artifact(path, "expected", False))
            self.assertEqual(artifact(path, "expected", True), [])
            self.assertEqual(artifact(path, "expected", False), [])
            self.assertTrue(artifact(path, "different", False))
            self.assertEqual(path.read_text(), "expected")


if __name__ == "__main__":
    unittest.main()
