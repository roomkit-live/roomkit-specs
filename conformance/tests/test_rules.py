from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_source import marked
from traceability.rules import artifacts, pages
from traceability.source import digest, extract


def receipt(implementation: str, backend: str, rfc: str, *results: tuple) -> dict:
    return {
        "implementation": implementation,
        "backend": backend,
        "rfc_commit": rfc,
        "results": [
            {"scenario": name, "sha256": sha, "outcome": outcome}
            for name, sha, outcome in results
        ],
    }


class RulesReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = extract(
            "## 10. Inbound\n### 10.4 Routing\n"
            + marked("Route it.", "RK-10.4-001", level="must")
            + marked("Refuse it.", "RK-10.4-002")
            + marked("Log it.", "RK-10.4-003")
            + "## Appendix A: Wire\n"
            + marked("A field.", "RK-A-001", kind="structural")
        )
        self.sha = {item["id"]: item["sha256"] for item in self.registry["requirements"]}
        self.scenarios = {
            "routing/a": {"requirements": ["RK-10.4-001"], "title": "a"},
            "routing/b": {"requirements": ["RK-10.4-001"], "title": "b"},
        }

    def test_each_unit_shows_its_citations_lock_and_latest_results(self) -> None:
        a, b = (digest(self.scenarios[name]) for name in ("routing/a", "routing/b"))
        executions = [
            receipt("python", "memory", "old", ("routing/a", a, "failed")),
            receipt("python", "memory", "new", ("routing/a", a, "passed")),
            receipt("python", "sqlite", "old", ("routing/a", a, "passed")),
            receipt("python", "memory", "new", ("routing/b", "0" * 64, "passed")),
        ]
        lock = {"RK-10.4-001": {"routing/a": self.sha["RK-10.4-001"], "routing/b": "1" * 64}}
        untested = {"RK-10.4-002": "needs a real | carrier"}
        report = pages(self.registry, self.scenarios, lock, untested, executions)
        self.assertEqual(sorted(report), ["README.md", "appendix-A.md", "section-10.md"])
        page = report["section-10.md"]
        self.assertIn("## §10.4 Routing", page)
        self.assertIn(
            "| RK-10.4-001 | behavior | must | `routing/a` | pinned | "
            "memory passed, sqlite passed |  |",
            page,
        )
        self.assertIn("| | | | `routing/b` | reread |  |  |", page)
        self.assertIn(
            "| RK-10.4-002 | behavior | — | untested: needs a real \\| carrier | | | |",
            page,
        )
        self.assertIn("| RK-10.4-003 | behavior | — | — | | | |", page)
        self.assertIn("# Appendix A: Wire", report["appendix-A.md"])
        self.assertIn(
            "| [§10 Inbound](section-10.md) | 3 | 1 | 0 | 0 | 2 | 1 | 2 | 1 |",
            report["README.md"],
        )

    def test_a_stale_or_extra_page_fails_until_regenerated(self) -> None:
        report = pages(self.registry, self.scenarios, {}, {}, [])
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.assertEqual(len(artifacts(directory, report, False)), 3)
            self.assertEqual(artifacts(directory, report, True), [])
            self.assertEqual(artifacts(directory, report, False), [])
            (directory / "rules/section-99.md").write_text("old")
            (directory / "rules/README.md").write_text("edited")
            self.assertEqual(
                artifacts(directory, report, False),
                [
                    "rules/README.md: generated page differs; run --update-traceability",
                    "rules/section-99.md: not a generated page; run --update-traceability",
                ],
            )
            self.assertEqual(artifacts(directory, report, True), [])
            self.assertFalse((directory / "rules/section-99.md").exists())
            self.assertEqual(artifacts(directory, report, False), [])


if __name__ == "__main__":
    unittest.main()
