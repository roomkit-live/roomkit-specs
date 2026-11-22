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
        report, errors = build(registry, evidence, scenarios, {"sections": []}, {})
        self.assertEqual(errors, [])
        self.assertEqual(report["requirements"][0]["mapping"], "unmapped")
        self.assertEqual(report["sections"][0]["review"], "not_reviewed")
        self.assertEqual(report["sections"][0]["candidate_scenarios"], ["some-case"])
        self.assertIn(
            "1 annotated source units; 0 have reviewed mappings", markdown(report)
        )

    def test_a_decided_gap_shows_its_class_and_card_and_earns_no_mapping(self) -> None:
        registry = extract(
            "### 9.3 Hooks\n"
            + marked("Keep it.", "RK-9.3-001", level="must")
            + marked("Log it.", "RK-9.3-002", level="must")
            + marked("Trace it.", "RK-9.3-003", level="should")
            + "### 9.4 Results\n"
            + marked("Return it.", "RK-9.4-001", level="must")
        )
        evidence = {"python_commit": "p", "links": [], "executions": []}
        gaps = {
            "RK-9.3-001": {"class": "step", "card": "RMK-1904", "note": "A | source."},
            "RK-9.3-003": {"class": "step", "card": "RMK-1905"},
            "RK-9.4-001": {"class": "phase6", "card": "RMK-1904"},
        }
        report, errors = build(registry, evidence, {}, {"sections": []}, gaps)
        self.assertEqual(errors, [])
        units = {item["id"]: item for item in report["requirements"]}
        self.assertEqual(
            units["RK-9.3-001"],
            {
                "id": "RK-9.3-001",
                "section": "9.3",
                "mapping": "unmapped",
                "links": [],
                "gap": {"class": "step", "card": "RMK-1904", "note": "A | source."},
            },
        )
        self.assertNotIn("gap", units["RK-9.3-002"])
        self.assertEqual(report["sections"][0]["decided_gaps"], {"step": 2})
        self.assertEqual(report["sections"][1]["decided_gaps"], {"phase6": 1})
        text = markdown(report)
        self.assertIn(
            "| Section | Inventory review | Units | Unmapped | Partial mappings | "
            "Complete mappings | Candidate scenarios | Keyword lines to review | "
            "Decided writable | Decided step | Decided phase6 |",
            text,
        )
        self.assertIn("| §9.3 Hooks | not_reviewed | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |", text)
        self.assertIn("| §9.4 Results | not_reviewed | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |", text)
        self.assertIn("| RK-9.3-001 | §9.3 | step | RMK-1904 | A \\| source. |", text)
        self.assertIn("| RK-9.3-003 | §9.3 | step | RMK-1905 |  |", text)
        self.assertIn("| RK-9.4-001 | §9.4 | phase6 | RMK-1904 |  |", text)
        self.assertNotIn("RK-9.3-002 |", text)
        empty, _ = build(registry, evidence, {}, {"sections": []}, {})
        self.assertNotIn("## Decided gaps", markdown(empty))

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
            {},
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
            {},
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

    def test_implicit_rules_and_model_defaults_cannot_disappear_from_review(
        self,
    ) -> None:
        for body in [
            "Return a fresh copy.\n",
            "**Return a fresh copy.**\n",
            "```\nOptions\n  timeout = 30\n```\n",
        ]:
            registry = extract("### 9.3 Hooks\n" + body)
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
                {},
            )
            self.assertTrue(
                any("unannotated content" in error for error in errors), errors
            )


if __name__ == "__main__":
    unittest.main()
