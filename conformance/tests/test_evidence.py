from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traceability.evidence import execution_status, validate
from traceability.receipts import derive, rust_id
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
            "artifact": {"path": "conformance/executions/run.xml", "format": "pytest_junit"},
            "results": [
                {
                    "scenario": "a",
                    "sha256": digest(self.scenarios["a"]),
                    "outcome": "passed",
                }
            ],
        }

    def rows(self, run: dict | None = None) -> list[dict]:
        return execution_status(self.link, [run or self.run], self.scenarios, "r", "p")

    def state(self, run: dict | None = None) -> str:
        return self.rows(run)[0]["state"]

    def derived(self, run: dict, xml: bytes) -> list[tuple[str, str]]:
        """The (scenario, outcome) pairs the checker derives from the report *xml*."""
        return [
            (result["scenario"], result["outcome"])
            for result in derive(run, xml, self.scenarios.__getitem__)
        ]

    def test_pass_requires_matching_revisions_and_asserted_scenarios(self) -> None:
        self.assertEqual(self.state(), "recorded_pass")
        # A receipt of another revision is superseded: the report shows no row of it.
        for field in ["rfc_sha256", "implementation_commit"]:
            self.assertEqual(self.rows({**self.run, field: "changed"}), [])
        self.scenarios["a"]["expect"]["count"] = 5
        self.assertEqual(self.rows(), [])

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

    def test_a_receipt_may_name_a_scenario_renamed_since_its_run(self) -> None:
        # The receipt's provenance is read at its corpus_commit (provenance.py);
        # only a link has to name a scenario of the current corpus.
        renamed = copy.deepcopy(self.run)
        renamed["results"][0]["scenario"] = "old-name"
        document = {"links": [], "python_commit": "p", "executions": [renamed]}
        registry = {"requirements": [{"id": "RK-9.3-001", "sha256": "c"}]}
        self.assertEqual(validate(document, registry, self.scenarios, None), [])
        self.link["assertions"][0]["scenario"] = "old-name"
        document["links"] = [self.link]
        self.assertTrue(
            any(
                "unknown scenario old-name" in error
                for error in validate(document, registry, self.scenarios, None)
            )
        )

    def test_junit_derives_each_case_s_outcome_and_the_corpus_hash(self) -> None:
        case = '<testcase classname="tests.conformance.test_conformance" name="test_scenario[{}]">{}</testcase>'
        xml = f"<testsuite>{case.format('b', '<skipped/>')}{case.format('a', '')}</testsuite>".encode()
        self.assertEqual(
            derive(self.run, xml, self.scenarios.__getitem__),
            [
                {"scenario": "a", "sha256": digest(self.scenarios["a"]), "outcome": "passed"},
                {"scenario": "b", "sha256": digest(self.scenarios["b"]), "outcome": "skipped"},
            ],
        )
        for unreadable in [
            b"<testsuite>",
            b"<?xml version='1.0' encoding='bogus'?><testsuite/>",
            b"<?xml version='1.0' encoding='euc-jp'?><testsuite/>",
        ]:
            with self.subTest(unreadable=unreadable), self.assertRaisesRegex(
                ValueError, "cannot read the JUnit report"
            ):
                derive(self.run, unreadable, self.scenarios.__getitem__)

    def test_junit_does_not_mix_memory_and_sqlite(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a[sqlite]]"/></testsuite>'
        with self.assertRaisesRegex(ValueError, "holds no memory scenario case"):
            self.derived(self.run, xml)
        self.run["backend"] = "sqlite"
        self.assertEqual(self.derived(self.run, xml), [("a", "passed")])

    def test_junit_does_not_mix_postgres_with_another_store(self) -> None:
        postgres = b'<testsuite><testcase classname="tests.conformance.test_postgres" name="test_scenario[a[postgres]]"/></testsuite>'
        for backend in ["memory", "sqlite"]:
            self.run["backend"] = backend
            with self.assertRaisesRegex(ValueError, f"holds no {backend} scenario case"):
                self.derived(self.run, postgres)
        self.run["backend"] = "postgres"
        self.assertEqual(self.derived(self.run, postgres), [("a", "passed")])
        for other in [
            b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a[postgres]]"/></testsuite>',
            b'<testsuite><testcase classname="tests.conformance.test_postgres" name="test_scenario[a]"/></testsuite>',
        ]:
            with self.subTest(other=other), self.assertRaisesRegex(ValueError, "holds no postgres"):
                self.derived(self.run, other)

    def test_junit_postgres_scenario_takes_the_worst_of_its_cases(self) -> None:
        self.run["backend"] = "postgres"
        case = '<testcase classname="tests.conformance.test_postgres" name="test_shared_postgres_contract[a-{}]">{}</testcase>'
        passed = case.format("False", "")
        for variant, actual in [("<skipped/>", "skipped"), ("<failure/>", "failed")]:
            xml = f"<testsuite>{passed}{case.format('True', variant)}</testsuite>".encode()
            with self.subTest(actual=actual):
                self.assertEqual(self.derived(self.run, xml), [("a", actual)])
        self.assertEqual(
            self.derived(self.run, f"<testsuite>{passed}</testsuite>".encode()), [("a", "passed")]
        )

    def test_junit_redis_turns_need_a_command_that_selects_them(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a[sqlite]]"/></testsuite>'
        self.run["backend"] = "sqlite+redis-turns"
        for command in [
            ["pytest"],
            ["env", "ROOMKIT_TEST_TURN_BACKEND=memory", "pytest"],
            ["env", "-u", "ROOMKIT_TEST_TURN_BACKEND", "pytest"],
            ["env", "-a", "ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"],
        ]:
            with self.subTest(command=command), self.assertRaisesRegex(ValueError, "does not select"):
                self.run["command"] = command
                self.derived(self.run, xml)
        for command in [
            ["env", "-u", "POSTGRES_DSN", "ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"],
            ["env", "-C", "roomkit", "ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"],
            ["ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"],
        ]:
            with self.subTest(command=command):
                self.run["command"] = command
                self.assertEqual(self.derived(self.run, xml), [("a", "passed")])

    def test_junit_a_redis_command_backs_no_receipt_of_local_turns(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a]"/></testsuite>'
        self.run["command"] = ["env", "ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"]
        with self.assertRaisesRegex(ValueError, "selects the kit's turns"):
            self.derived(self.run, xml)
        self.run["backend"] = "memory+redis-turns"
        self.assertEqual(self.derived(self.run, xml), [("a", "passed")])

    def test_junit_refuses_a_command_whose_turn_mode_it_cannot_read(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a]"/></testsuite>'
        for command in [
            ["pytest", "ROOMKIT_TEST_TURN_BACKEND=redis"],
            ["sh", "-c", "ROOMKIT_TEST_TURN_BACKEND=redis pytest"],
            ["flock", "/run/suite.lock", "env", "ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"],
            ["env", "A=1", "env", "ROOMKIT_TEST_TURN_BACKEND=redis", "pytest"],
            ["env", "-S", "ROOMKIT_TEST_TURN_BACKEND=redis pytest"],
            ["env", "ROOMKIT_TEST_TURN_BACKEND=redis", "env", "-u", "ROOMKIT_TEST_TURN_BACKEND", "pytest"],
        ]:
            for backend in ["memory", "memory+redis-turns"]:
                with (
                    self.subTest(command=command, backend=backend),
                    self.assertRaisesRegex(ValueError, "cannot tell the turn mode"),
                ):
                    self.run.update(command=command, backend=backend)
                    self.derived(self.run, xml)

    def test_junit_refuses_a_backend_no_runner_profile_names(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_postgres" name="test_scenario[a[postgres]]"/></testsuite>'
        for backend in ["postgres+redis-turns", "redis", "memory+redis"]:
            with (
                self.subTest(backend=backend),
                self.assertRaisesRegex(ValueError, "unsupported pytest execution profile"),
            ):
                self.run["backend"] = backend
                self.derived(self.run, xml)

    def rust_run(self, backend: str, runtime: str) -> dict:
        commit = "c" * 40
        name = rust_id(commit, backend, runtime)
        self.run.update(
            id=name,
            implementation="rust",
            implementation_commit=commit,
            backend=backend,
            runtime=runtime,
            artifact={"path": f"conformance/executions/{name}.xml", "format": "cargo_junit"},
        )
        self.run["command"] = ["cargo", "test", "-p", "roomkit", "--test", "conformance"]
        return self.run

    def test_rust_junit_records_the_outcome_of_each_named_scenario(self) -> None:
        run = self.rust_run("memory", "multi_thread_4")
        case = '<testcase classname="conformance.memory.multi_thread_4" name="{}">{}</testcase>'
        xml = f"<testsuite>{case.format('a', '')}{case.format('b', '<skipped/>')}</testsuite>".encode()
        self.assertEqual(self.derived(run, xml), [("a", "passed"), ("b", "skipped")])
        failed = f"<testsuite>{case.format('a', '<failure/>')}</testsuite>".encode()
        self.assertEqual(self.derived(run, failed), [("a", "failed")])
        twice = f"<testsuite>{case.format('a', '')}{case.format('a', '')}</testsuite>".encode()
        with self.assertRaisesRegex(ValueError, "duplicate JUnit case a"):
            self.derived(run, twice)

    def test_rust_junit_reads_only_the_pass_of_the_receipt(self) -> None:
        xml = b'<testsuite><testcase classname="conformance.memory.current_thread" name="a"/></testsuite>'
        for backend, runtime in [
            ("memory", "multi_thread_4"),
            ("sqlite", "current_thread"),
            ("postgres", "current_thread"),
        ]:
            with self.subTest(backend=backend, runtime=runtime):
                run = self.rust_run(backend, runtime)
                with self.assertRaisesRegex(ValueError, f"holds no {backend} scenario case"):
                    self.derived(run, xml)
        self.assertEqual(self.derived(self.rust_run("memory", "current_thread"), xml), [("a", "passed")])

    def test_rust_junit_never_reads_a_plain_pass_for_the_redis_executor_one(self) -> None:
        case = '<testsuite><testcase classname="conformance.{}.{}" name="a"/></testsuite>'
        for store, runtime in [
            ("memory", "current_thread"),
            ("memory", "multi_thread_4"),
            ("sqlite", "current_thread"),
            ("postgres", "current_thread"),
        ]:
            plain = case.format(store, runtime).encode()
            redis = case.format(f"{store}+redis-executors", runtime).encode()
            for backend, own, other in [
                (store, plain, redis),
                (f"{store}+redis-executors", redis, plain),
            ]:
                with self.subTest(backend=backend, runtime=runtime):
                    run = self.rust_run(backend, runtime)
                    self.assertEqual(self.derived(run, own), [("a", "passed")])
                    with self.assertRaisesRegex(ValueError, "holds no"):
                        self.derived(run, other)

    def test_rust_id_writes_the_redis_executor_pass_apart(self) -> None:
        commit = "c" * 40
        self.assertEqual(
            rust_id(commit, "memory+redis-executors", "multi_thread_4"),
            "rust-ccccccc-memory-redis-executors-multi-thread-4",
        )
        self.assertEqual(rust_id(commit, "memory", "multi_thread_4"), "rust-ccccccc-memory-multi-thread-4")
        run = self.rust_run("sqlite+redis-executors", "current_thread")
        xml = b'<testsuite><testcase classname="conformance.sqlite+redis-executors.current_thread" name="a"/></testsuite>'
        self.assertEqual(self.derived(run, xml), [("a", "passed")])
        for misnamed in [
            "rust-ccccccc-sqlite+redis-executors-current-thread",
            "rust-ccccccc-sqlite-current-thread",
        ]:
            with self.subTest(misnamed=misnamed), self.assertRaisesRegex(ValueError, "are named"):
                self.derived({**run, "id": misnamed}, xml)

    def test_rust_junit_refuses_a_pass_no_runner_profile_names(self) -> None:
        xml = b'<testsuite><testcase classname="conformance.sqlite.multi_thread_4" name="a"/></testsuite>'
        for backend, runtime in [
            ("sqlite", "multi_thread_4"),
            ("memory", "asyncio"),
            ("memory+redis-turns", "current_thread"),
            ("sqlite+redis-executors", "multi_thread_4"),
            ("redis-executors", "current_thread"),
        ]:
            with (
                self.subTest(backend=backend, runtime=runtime),
                self.assertRaisesRegex(ValueError, "unsupported Rust execution profile"),
            ):
                self.derived(self.rust_run(backend, runtime), xml)
        self.rust_run("memory", "current_thread")["implementation"] = "python"
        with self.assertRaisesRegex(ValueError, "unsupported Rust execution profile"):
            self.derived(self.run, xml)

    def test_rust_junit_refuses_a_filtered_or_misnamed_receipt(self) -> None:
        xml = b'<testsuite><testcase classname="conformance.memory.current_thread" name="a"/></testsuite>'
        run = self.rust_run("memory", "current_thread")
        self.assertEqual(self.derived(run, xml), [("a", "passed")])
        for change in [
            {"scenario_filter": "a"},
            {"id": "rust-ccccccc-sqlite-multi-thread-4"},
            {"implementation_commit": "d" * 40},
            {"artifact": {"path": "conformance/executions/other.xml", "format": "cargo_junit"}},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.derived({**run, **change}, xml)

    def test_a_rust_receipt_is_never_read_as_a_pytest_one(self) -> None:
        xml = b'<testsuite><testcase classname="tests.conformance.test_conformance" name="test_scenario[a]"/></testsuite>'
        self.rust_run("memory", "asyncio")["artifact"]["format"] = "pytest_junit"
        with self.assertRaisesRegex(ValueError, "unsupported pytest execution profile"):
            self.derived(self.run, xml)

    def test_aggregate_cargo_output_cannot_prove_backend_or_selection(self) -> None:
        self.run.update(
            implementation="rust",
            runtime="current_thread",
            command=["cargo", "test", "-p", "roomkit-sqlite"],
            artifact={"path": "conformance/executions/run.txt", "format": "cargo"},
        )
        output = b"one thread: 1 scenarios, 0 failing: []\ntest result: ok."
        with self.assertRaisesRegex(ValueError, "cargo receipts are unsupported"):
            self.derived(self.run, output)


if __name__ == "__main__":
    unittest.main()
