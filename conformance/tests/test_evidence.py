from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traceability.evidence import execution_status, validate
from traceability.receipts import cargo, junit
from traceability.references import check_assertion, pointer, python_symbol
from traceability.source import digest


class ReferenceTests(unittest.TestCase):
    def test_only_actual_expectations_can_be_claimed(self) -> None:
        scenarios = {"hooks/check": {"setup": {}, "expect": {"timeline": {"r": []}}}}
        reference = {
            "scenario": "hooks/check",
            "pointer": "/expect/timeline/r",
            "sha256": digest([]),
            "scenario_sha256": digest(scenarios["hooks/check"]),
        }
        self.assertEqual(check_assertion(reference, scenarios), [])
        scenarios["hooks/check"]["setup"] = {"different": True}
        self.assertIn("scenario changed", check_assertion(reference, scenarios)[0])
        scenarios["hooks/check"]["setup"] = {}
        for path in ["/setup", "/expect/missing", "/steps/0/expect/result"]:
            with self.subTest(path=path):
                self.assertTrue(
                    check_assertion({**reference, "pointer": path}, scenarios)
                )
        scenarios["hooks/check"]["expect"]["timeline"]["r"] = ["unexpected"]
        self.assertIn("assertion changed", check_assertion(reference, scenarios)[0])

    def test_pointer_escapes_and_array_bounds(self) -> None:
        self.assertEqual(pointer({"a/b": {"~": [7]}}, "/a~1b/~0/0"), 7)
        for path in ["/a/01", "/a/-1", "/a/2", "/a/~3"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                pointer({"a": [1]}, path)

    def test_python_reference_resolves_the_exact_class_and_decorators(self) -> None:
        text = "class TestOne:\n    @mark.parametrize('x', [1, 2])\n    async def test_it(self, x):\n        assert x\n"
        found = python_symbol(text, "TestOne::test_it")
        self.assertIn("parametrize", found)
        self.assertIn("assert x", found)
        for name in ["test_it", "TestTwo::test_it", "TestOne"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                python_symbol(text, name)

    def test_a_helper_is_not_a_test_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "test"):
            python_symbol("def helper():\n    return 1\n", "helper")


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = {"a": {"expect": {"count": 1}}, "b": {"expect": {"count": 0}}}
        self.link = {
            "id": "hook-case",
            "requirement": "RK-9.3-001",
            "clause_sha256": "c",
            "scope": "one trigger",
            "coverage": "partial",
            "review": "only this trigger",
            "missing": ["other triggers"],
            "tests": [],
            "assertions": [
                {
                    "scenario": "a",
                    "pointer": "/expect/count",
                    "sha256": digest(1),
                    "scenario_sha256": digest(self.scenarios["a"]),
                }
            ],
        }
        self.run = {
            "id": "run",
            "implementation": "python",
            "implementation_commit": "p",
            "rfc_sha256": "r",
            "backend": "memory",
            "runtime": "asyncio",
            "command": ["pytest"],
            "results": [
                {
                    "scenario": "a",
                    "sha256": digest(self.scenarios["a"]),
                    "outcome": "passed",
                }
            ],
        }

    def state(self, run: dict | None = None) -> str:
        return execution_status(self.link, [run or self.run], self.scenarios, "r", "p")[
            0
        ]["state"]

    def test_pass_requires_matching_revisions_and_asserted_scenarios(self) -> None:
        self.assertEqual(self.state(), "recorded_pass")
        for field in ["rfc_sha256", "implementation_commit"]:
            self.assertEqual(self.state({**self.run, field: "changed"}), "stale")
        self.scenarios["a"]["expect"]["count"] = 5
        self.assertEqual(self.state(), "stale")

    def test_skip_and_failure_never_become_passes(self) -> None:
        for status in ["skipped", "failed", "not_run"]:
            run = copy.deepcopy(self.run)
            run["results"][0]["outcome"] = status
            self.assertEqual(self.state(run), "not_passed")

    def test_partial_runs_are_not_unioned_into_a_complete_execution(self) -> None:
        self.link["assertions"].append({"scenario": "b"})
        other = {
            **self.run,
            "id": "another",
            "results": [
                {
                    "scenario": "b",
                    "sha256": digest(self.scenarios["b"]),
                    "outcome": "passed",
                }
            ],
        }
        states = execution_status(
            self.link, [self.run, other], self.scenarios, "r", "p"
        )
        self.assertEqual(
            [item["state"] for item in states], ["incomplete", "incomplete"]
        )

    def test_missing_specialized_execution_is_not_assumed_from_scenarios(self) -> None:
        self.link["tests"] = [{"nodeid": "tests/test_hook.py::test_it"}]
        self.assertEqual(self.state(), "incomplete")

    def test_changed_clause_and_contradictory_coverage_are_errors(self) -> None:
        document = {"links": [self.link], "python_commit": "p", "executions": []}
        registry = {"requirements": [{"id": "RK-9.3-001", "sha256": "different"}]}
        self.assertIn(
            "clause or applicability changed",
            validate(document, registry, self.scenarios, None)[0],
        )
        self.link["coverage"] = "complete"
        self.assertTrue(
            any(
                "cannot list missing" in error
                for error in validate(document, registry, self.scenarios, None)
            )
        )

    def test_junit_skip_cannot_be_declared_as_a_pass(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a]"><skipped/></testcase></testsuite>'
        self.assertIn("JUnit says skipped", junit(self.run, xml)[0])
        self.run["results"][0]["outcome"] = "skipped"
        self.assertEqual(junit(self.run, xml), [])

    def test_junit_does_not_mix_memory_and_sqlite(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a[sqlite]]"/></testsuite>'
        self.assertIn("JUnit says not_run", junit(self.run, xml)[0])
        self.run["backend"] = "sqlite"
        self.assertEqual(junit(self.run, xml), [])

    def test_cargo_requires_a_complete_runtime_summary(self) -> None:
        self.run.update(implementation="rust", runtime="multi_thread:4")
        self.assertTrue(
            cargo(self.run, "one thread: 1 scenarios, 0 failing: []\ntest result: ok.")
        )
        good = "four workers: 1 scenarios, 0 failing: []\ntest result: ok."
        self.assertTrue(cargo(self.run, good))
        self.assertTrue(cargo(self.run, good.replace("1 scenarios", "2 scenarios")))
        self.assertTrue(cargo(self.run, good + "\ntest result: FAILED"))

    def test_aggregate_cargo_output_cannot_prove_backend_or_selection(self) -> None:
        self.run.update(
            implementation="rust",
            runtime="current_thread",
            command=["cargo", "test", "-p", "roomkit-sqlite"],
        )
        output = "one thread: 1 scenarios, 0 failing: []\ntest result: ok."
        self.assertTrue(cargo(self.run, output))


if __name__ == "__main__":
    unittest.main()
