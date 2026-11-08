from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_source import marked
from traceability import check, layout
from traceability.provenance import copied_scenarios
from traceability.source import digest, extract


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "conformance"
        self.directory.mkdir()
        self.text = "## 9. Hooks\n" + marked("Keep the event.")
        self.document = {
            "version": 1,
            "python_commit": "a" * 40,
            "retired": [],
            "links": [],
            "executions": [],
        }
        self.write("evidence.json", self.document)
        self.write("inventory.json", {"version": 1, "sections": []})
        schema = Path(__file__).resolve().parents[1] / "evidence.schema.json"
        (self.directory / schema.name).write_bytes(schema.read_bytes())

    def write(self, name: str, value: object) -> None:
        (self.directory / name).write_text(layout(value))

    def test_regeneration_and_drift_detection_use_the_real_entrypoint(self) -> None:
        self.assertEqual(check(self.root, self.text, [], update=True), [])
        self.assertEqual(check(self.root, self.text, []), [])
        self.assertTrue(check(self.root, self.text.replace("Keep", "Drop"), []))
        old = (self.directory / "requirements.json").read_bytes()
        self.document["unexpected"] = True
        self.write("evidence.json", self.document)
        self.assertTrue(check(self.root, self.text, [], update=True))
        self.assertEqual((self.directory / "requirements.json").read_bytes(), old)

    def git(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.root), *args], text=True
        ).strip()

    def commit(self) -> str:
        self.git("init", "-q")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Conformance Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "fixture",
        )
        return self.git("rev-parse", "HEAD")

    def test_a_retirement_cannot_be_removed_from_the_committed_history(self) -> None:
        (self.root / "roomkit-rfc.md").write_text(self.text)
        self.document["retired"] = ["RK-9.3-002"]
        self.write("evidence.json", self.document)
        base = self.commit()
        self.document["retired"] = []
        self.write("evidence.json", self.document)
        errors = check(self.root, self.text, [], update=True, base_ref=base)
        self.assertTrue(any("retirement removed" in error for error in errors), errors)

    def test_invalid_scenario_links_return_errors_without_building_a_report(
        self,
    ) -> None:
        requirement = extract(self.text)["requirements"][0]
        self.document["links"] = [
            {
                "id": "missing-link",
                "requirement": requirement["id"],
                "clause_sha256": requirement["sha256"],
                "scope": "one case",
                "coverage": "partial",
                "review": "fixture",
                "missing": ["other cases"],
                "tests": [],
                "assertions": [
                    {
                        "scenario": "missing",
                        "pointer": "/expect",
                        "sha256": "a" * 64,
                        "scenario_sha256": "b" * 64,
                        "proves": "fixture",
                    }
                ],
            }
        ]
        self.document["executions"] = [
            {
                "id": "missing-run",
                "implementation": "python",
                "implementation_commit": "a" * 40,
                "rfc_commit": "a" * 40,
                "corpus_commit": "a" * 40,
                "rfc_sha256": extract(self.text)["rfc_sha256"],
                "backend": "memory",
                "runtime": "asyncio",
                "command": ["pytest"],
                "artifact": {
                    "path": "conformance/executions/missing.xml",
                    "sha256": "b" * 64,
                    "format": "pytest_junit",
                },
                "results": [
                    {"scenario": "missing", "sha256": "c" * 64, "outcome": "passed"}
                ],
            }
        ]
        self.write("evidence.json", self.document)
        errors = check(self.root, self.text, [])
        self.assertTrue(any("unknown scenario" in error for error in errors), errors)

    def test_receipt_must_match_the_implementation_copy_and_rust_selection(
        self,
    ) -> None:
        scenarios = self.directory / "scenarios"
        scenarios.mkdir()
        a, b = {"id": "a", "expect": {"value": 1}}, {"id": "b", "expect": {"value": 2}}
        (scenarios / "a.json").write_text(json.dumps(a))
        (scenarios / "b.json").write_text(json.dumps(b))
        run = {
            "id": "rust-run",
            "implementation": "rust",
            "implementation_commit": self.commit(),
            "results": [{"scenario": "a", "sha256": digest(a), "outcome": "passed"}],
        }
        self.assertIn("entire filtered selection", copied_scenarios(run, self.root)[0])
        run["scenario_filter"] = "a"
        self.assertEqual(copied_scenarios(run, self.root), [])
        altered = copy.deepcopy(run)
        altered["results"][0]["sha256"] = digest(b)
        self.assertIn(
            "implementation's copy differs", copied_scenarios(altered, self.root)[0]
        )


if __name__ == "__main__":
    unittest.main()
