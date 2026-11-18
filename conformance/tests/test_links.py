from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check import CELLS
from test_source import marked
from traceability import links, process
from traceability.references import check_assertion
from traceability.source import digest, extract, scenario_digest

HERE = Path(__file__).resolve().parents[1]


def rfc(*units: str) -> dict:
    return extract("### 10.4 Routing\n" + "".join(units))


class CitationTests(unittest.TestCase):
    def test_a_citation_names_a_current_testable_unit(self) -> None:
        registry = rfc(
            marked("Route it.", "RK-10.4-001"),
            marked("Operators review it.", "RK-10.4-002", kind="non_testable"),
        )
        scenarios = {
            "routing/a": {"requirements": ["RK-10.4-001"]},
            "routing/b": {"requirements": ["RK-10.4-009"]},
            "routing/c": {"requirements": ["RK-10.4-003"]},
            "routing/d": {"requirements": ["RK-10.4-002"]},
        }
        self.assertEqual(
            links.check_citations(scenarios, registry, ["RK-10.4-003"]),
            [
                "routing/b: requirement RK-10.4-009: no such unit in the RFC",
                "routing/c: requirement RK-10.4-003: retired; cite the units that replace it",
                "routing/d: requirement RK-10.4-002: non_testable; no scenario can cite it",
            ],
        )

    def test_an_untested_reason_names_a_current_unit(self) -> None:
        registry = rfc(marked("Route it.", "RK-10.4-001"))
        untested = {"RK-10.4-001": "a", "RK-10.4-003": "b", "RK-10.4-009": "c"}
        self.assertEqual(
            links.check_untested(untested, registry, ["RK-10.4-003"]),
            [
                "untested.json: RK-10.4-003: retired",
                "untested.json: RK-10.4-009: no such unit in the RFC",
            ],
        )


class LockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = rfc(
            marked("Route it.", "RK-10.4-001"), marked("Refuse it.", "RK-10.4-002")
        )
        self.sha = {item["id"]: item["sha256"] for item in self.registry["requirements"]}
        self.scenarios = {
            "routing/a": {"requirements": ["RK-10.4-001", "RK-10.4-002"]},
            "routing/b": {"requirements": ["RK-10.4-001"]},
        }
        self.lock = {
            "RK-10.4-001": {"routing/a": self.sha["RK-10.4-001"], "routing/b": "0" * 64},
            "RK-10.4-002": {"routing/a": self.sha["RK-10.4-002"]},
        }

    def test_a_changed_unit_names_the_scenarios_to_reread(self) -> None:
        self.assertEqual(
            links.lock_problems(self.scenarios, self.registry, self.lock, {}),
            [
                "RK-10.4-001 changed since routing/b read it: reread it, then run "
                "python3 conformance/check.py --pin RK-10.4-001"
            ],
        )

    def test_a_citation_and_its_pin_go_together(self) -> None:
        del self.lock["RK-10.4-002"]
        self.lock["RK-10.4-001"]["routing/b"] = self.sha["RK-10.4-001"]
        self.lock["RK-10.4-001"]["routing/gone"] = self.sha["RK-10.4-001"]
        self.assertEqual(
            links.lock_problems(self.scenarios, self.registry, self.lock, {}),
            [
                "routing/a cites RK-10.4-002 with no lock entry: once it is read "
                "against it, run python3 conformance/check.py --pin RK-10.4-002 routing/a",
                "links.lock.json pins routing/gone to RK-10.4-001, which it does not "
                "cite: run python3 conformance/check.py --pin RK-10.4-001 routing/gone",
            ],
        )

    def test_a_cited_unit_cannot_keep_an_untested_reason(self) -> None:
        self.lock["RK-10.4-001"]["routing/b"] = self.sha["RK-10.4-001"]
        problems = links.lock_problems(
            self.scenarios, self.registry, self.lock, {"RK-10.4-002": "no fake"}
        )
        self.assertEqual(
            problems,
            [
                "untested.json gives a reason RK-10.4-002 has no scenario, but "
                "routing/a cite it: remove its entry"
            ],
        )

    def test_a_pin_moves_only_what_it_names(self) -> None:
        self.lock["RK-10.4-002"]["routing/gone"] = "1" * 64
        updated, errors = links.pin(
            ["routing/b"], self.scenarios, self.registry, self.lock
        )
        self.assertEqual(errors, [])
        self.assertEqual(updated["RK-10.4-001"]["routing/b"], self.sha["RK-10.4-001"])
        self.assertEqual(updated["RK-10.4-002"], self.lock["RK-10.4-002"])
        updated, _ = links.pin(["RK-10.4-002"], self.scenarios, self.registry, self.lock)
        self.assertEqual(updated["RK-10.4-002"], {"routing/a": self.sha["RK-10.4-002"]})
        self.assertEqual(updated["RK-10.4-001"], self.lock["RK-10.4-001"])

    def test_a_unit_and_a_scenario_together_name_one_citation(self) -> None:
        # routing/a's citation of RK-10.4-001 changed since it was read: pinning
        # routing/a's new citation alone must not record that one as reread.
        self.lock["RK-10.4-001"]["routing/a"] = "2" * 64
        del self.lock["RK-10.4-002"]
        updated, errors = links.pin(
            ["RK-10.4-002", "routing/a"], self.scenarios, self.registry, self.lock
        )
        self.assertEqual(errors, [])
        self.assertEqual(updated["RK-10.4-002"], {"routing/a": self.sha["RK-10.4-002"]})
        self.assertEqual(updated["RK-10.4-001"], self.lock["RK-10.4-001"])

    def test_a_pin_refuses_a_name_that_names_nothing(self) -> None:
        registry = rfc(
            marked("Route it.", "RK-10.4-001"),
            marked("Refuse it.", "RK-10.4-002"),
            marked("Log it.", "RK-10.4-003"),
        )
        for names, error in (
            (["RK-10.4-007"], "--pin RK-10.4-007: names no citation or entry of links.lock.json"),
            (["RK-10.4-003"], "--pin RK-10.4-003: names no citation or entry of links.lock.json"),
            (["routing/z"], "--pin routing/z: names no citation or entry of links.lock.json"),
            (
                ["RK-10.4-002", "routing/b"],
                "--pin RK-10.4-002 routing/b: these name no citation together",
            ),
        ):
            with self.subTest(names=names):
                updated, errors = links.pin(names, self.scenarios, registry, self.lock)
                self.assertEqual(updated, self.lock)
                self.assertEqual(errors, [error])

    def test_the_lock_keeps_its_sorted_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.assertEqual(links.read_lock(directory), {})
            path = directory / links.LOCK
            path.write_text(links.lock_layout(self.lock))
            self.assertEqual(links.read_lock(directory), self.lock)
            self.assertEqual(links.lock_layout_errors(directory, self.lock), [])
            value = json.loads(path.read_text())
            value["links"] = dict(reversed(value["links"].items()))
            path.write_text(json.dumps(value, indent=2) + "\n")
            self.assertEqual(links.read_lock(directory), self.lock)
            self.assertEqual(
                links.lock_layout_errors(directory, self.lock),
                ["links.lock.json: not in its sorted layout; any --pin rewrites it"],
            )
            path.write_text(json.dumps({"version": 1, "links": {"RK-10.4-001": {}}}))
            with self.assertRaisesRegex(ValueError, "links.lock.json"):
                links.read_lock(directory)

    def test_a_malformed_citation_list_is_left_to_the_schema(self) -> None:
        for requirements, cited in (
            (None, {}),
            ("RK-10.4-001", {}),
            ([1, "RK-10.4-001"], {"RK-10.4-001": {"routing/a"}}),
        ):
            with self.subTest(requirements=requirements):
                scenarios = {"routing/a": {"requirements": requirements}}
                self.assertEqual(links.check_citations(scenarios, self.registry, []), [])
                self.assertEqual(links.citations(scenarios), cited)


class FingerprintTests(unittest.TestCase):
    def test_a_citation_reopens_no_evidence_link_or_receipt(self) -> None:
        scenario = {"id": "routing/a", "expect": {"value": 1}}
        cited = {**scenario, "requirements": ["RK-10.4-001"]}
        self.assertEqual(scenario_digest(scenario), digest(scenario))
        self.assertEqual(scenario_digest(cited), digest(scenario))
        self.assertNotEqual(scenario_digest({**scenario, "notes": "n"}), digest(scenario))
        reference = {
            "scenario": "routing/a",
            "pointer": "/expect/value",
            "sha256": digest(1),
            "scenario_sha256": digest(scenario),
        }
        self.assertEqual(check_assertion(reference, {"routing/a": cited}), [])


class ProcessRuleTests(unittest.TestCase):
    def test_a_changed_unit_needs_a_scenario_by_its_level(self) -> None:
        base = rfc(
            marked("Kept as is.", "RK-10.4-001", level="must"),
            marked("Reworded.", "RK-10.4-002", level="must"),
            marked("Reviewed now.", "RK-10.4-003"),
        )
        current = rfc(
            marked("Kept as is.", "RK-10.4-001", level="must"),
            marked("Reworded again.", "RK-10.4-002", level="must"),
            marked("Reviewed now.", "RK-10.4-003", level="should"),
            marked("New, cited.", "RK-10.4-004", level="must"),
            marked("New, explained.", "RK-10.4-005", level="must"),
            marked("New, optional.", "RK-10.4-006", level="may"),
            marked("New, not reviewed.", "RK-10.4-007"),
            marked("New, operational.", "RK-10.4-008", kind="non_testable", level="must"),
        )
        scenarios = {"routing/a": {"requirements": ["RK-10.4-004"]}}
        untested = {"RK-10.4-005": "needs a real carrier"}
        errors, warnings, unreviewed = process.process_rule(
            current, base, scenarios, untested, "a" * 40
        )
        self.assertEqual(
            errors,
            [
                "RK-10.4-002 (must, changed since aaaaaaaaaaaa): no scenario cites it "
                "and untested.json gives no reason"
            ],
        )
        self.assertEqual(
            warnings,
            ["RK-10.4-003 (should, changed since aaaaaaaaaaaa): no scenario cites it"],
        )
        self.assertEqual(
            unreviewed, ["RK-10.4-007 (added since aaaaaaaaaaaa): no level yet"]
        )


class CommandTests(unittest.TestCase):
    """check.py as a scenario author runs it, on a copy of the checker."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.directory = self.root / "conformance"
        self.directory.mkdir()
        shutil.copy(HERE / "check.py", self.directory)
        shutil.copy(HERE / "scenario.schema.json", self.directory)
        shutil.copytree(
            HERE / "traceability",
            self.directory / "traceability",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.write("evidence.json", {"retired": []})
        source = HERE / "scenarios/orchestration"
        name = "a-conversation-state-is-saved-only-in-a-room-the-store-holds.json"
        scenario = json.loads((source / name).read_text())
        scenario["id"] = "routing/a"
        scenario["rules"] = ["§10.4"]
        scenario["requirements"] = ["RK-10.4-001"]
        scenario["reentrancy"] = CELLS
        self.write("scenarios/routing/a.json", scenario)
        self.rfc = self.root / "roomkit-rfc.md"
        self.rfc.write_text("### 10.4 Routing\n" + marked("Route it.", "RK-10.4-001"))

    def write(self, name: str, value: object) -> None:
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

    def check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.directory / "check.py"), "--rfc", str(self.rfc)]
            + list(args),
            capture_output=True,
            text=True,
        )

    def test_a_citation_is_pinned_then_reread_after_its_unit_changes(self) -> None:
        run = self.check("--strict")
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertIn(
            "lock: routing/a cites RK-10.4-001 with no lock entry: once it is read "
            "against it, run python3 conformance/check.py --pin RK-10.4-001 routing/a",
            run.stdout,
        )
        self.assertEqual(self.check("--pin", "routing/a").returncode, 0)
        self.assertEqual(self.check("--strict").returncode, 0)
        self.rfc.write_text(
            "### 10.4 Routing\n" + marked("Route it twice.", "RK-10.4-001")
        )
        run = self.check("--strict")
        self.assertEqual(run.returncode, 1)
        self.assertIn(
            "lock: RK-10.4-001 changed since routing/a read it: reread it, then run "
            "python3 conformance/check.py --pin RK-10.4-001",
            run.stdout,
        )
        self.assertEqual(self.check().returncode, 0, "drift fails only --strict")

    def test_a_pin_names_what_it_pins(self) -> None:
        run = self.check("--pin")
        self.assertEqual(run.returncode, 2)
        self.assertIn("expected at least one argument", run.stderr)
        self.assertFalse((self.directory / links.LOCK).exists())

    def test_a_scenario_in_error_pins_nothing(self) -> None:
        for change, error in (
            ({"requirements": ["RK-10.4-009"]}, "requirement RK-10.4-009: no such unit"),
            ({"requirements": None}, "schema: requirements: None is not of type 'array'"),
            ({"unknown": 1}, "schema: : Additional properties are not allowed"),
        ):
            with self.subTest(change=change):
                path = self.directory / "scenarios/routing/a.json"
                scenario = {**json.loads(path.read_text()), **change}
                self.write("scenarios/routing/a.json", scenario)
                run = self.check("--pin", "routing/a")
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertIn(f"error: routing/a: {error}", run.stdout)
                self.assertIn("error: --pin: nothing pinned", run.stdout)
                self.assertFalse((self.directory / links.LOCK).exists())
                scenario.pop("unknown", None)
                scenario["requirements"] = ["RK-10.4-001"]
                self.write("scenarios/routing/a.json", scenario)

    def test_a_pin_rewrites_a_lock_out_of_its_layout(self) -> None:
        self.assertEqual(self.check("--pin", "routing/a").returncode, 0)
        lock = self.directory / links.LOCK
        lock.write_text(json.dumps(json.loads(lock.read_text()), indent=4) + "\n")
        run = self.check()
        self.assertEqual(run.returncode, 1)
        self.assertIn("error: links.lock.json: not in its sorted layout", run.stdout)
        self.assertEqual(self.check("--pin", "RK-10.4-001").returncode, 0)
        self.assertEqual(self.check("--strict").returncode, 0)

    def git(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.root), *args], text=True
        ).strip()

    def test_the_process_rule_reads_the_base_commit(self) -> None:
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
            "base",
        )
        base = self.git("rev-parse", "HEAD")
        self.rfc.write_text(
            self.rfc.read_text() + marked("Log it.", "RK-10.4-002", level="must")
        )
        self.assertEqual(self.check("--pin", "routing/a").returncode, 0)
        run = self.check("--changed-units", "--base-ref", base)
        self.assertEqual(run.returncode, 1)
        self.assertIn(
            f"error: RK-10.4-002 (must, added since {base[:12]}): no scenario cites "
            "it and untested.json gives no reason",
            run.stdout,
        )
        self.write("untested.json", {"version": 1, "units": {"RK-10.4-002": "a log"}})
        self.assertEqual(self.check("--changed-units", "--base-ref", base).returncode, 0)
        run = self.check("--changed-units", "--base-ref", base[:12])
        self.assertEqual(run.returncode, 2)
        self.assertIn("full 40-character sha", run.stderr)

    def test_the_process_rule_does_not_hold_back_the_traceability_check(self) -> None:
        self.write(
            "evidence.json",
            {"version": 1, "python_commit": "a" * 40, "retired": [], "links": [], "executions": []},
        )
        self.write("inventory.json", {"version": 1, "sections": []})
        shutil.copy(HERE / "evidence.schema.json", self.directory)
        self.test_the_process_rule_reads_the_base_commit()
        self.write("untested.json", {"version": 1, "units": {}})
        base = self.git("rev-list", "--max-parents=0", "HEAD")
        run = self.check("--traceability", "--changed-units", "--base-ref", base)
        self.assertEqual(run.returncode, 1)
        self.assertIn("error: RK-10.4-002 (must, added since", run.stdout)
        self.assertIn("error: requirements.json: generated artifact differs", run.stdout)


if __name__ == "__main__":
    unittest.main()
