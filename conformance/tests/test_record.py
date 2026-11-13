from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_source import marked
from traceability import layout
from traceability.ci import CI_REPORTS, from_ci, workflow_drift
from traceability.importer import clean, leftovers, portable, prepare, write
from traceability.provenance import provenance
from traceability.receipts import validate_artifact
from traceability.source import digest

MODULE = "tests.conformance.test_conformance"
REPORT = f"""<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="1" skipped="1"
 tests="4" time="3.2" timestamp="2026-11-13T04:09:50" hostname="runner-7">
<properties><property name="worker" value="gw3"/></properties>
<testcase classname="{MODULE}" name="test_scenario[a]" time="0.4" file="tests/x.py" line="3"/>
<testcase classname="{MODULE}" name="test_scenario[b]" time="0.1"><skipped type="pytest.skip"
 message="in process: /home/someone/roomkit/tests/conftest.py says so">/home/someone/roomkit/tests/conftest.py:165: in process</skipped></testcase>
<testcase classname="{MODULE}" name="test_scenario[a[sqlite]]" time="0.2"><failure message="/tmp/run/x.py:3: /expect/timeline/r differs">Traceback /home/someone/x.py</failure><system-out>log /home/someone</system-out></testcase>
<testcase classname="tests.conformance.test_acp_fixture" name="test_fixture[/srv/shared]" time="0.1"/>
</testsuite></testsuites>""".encode()
POSTGRES_REPORT = b"""<testsuites><testsuite name="pytest">
<testcase classname="tests.conformance.test_postgres" name="test_scenario[a[postgres]]"/>
<testcase classname="tests.conformance.test_postgres" name="test_shared_postgres_contract[b-False]"/>
</testsuite></testsuites>"""

# The shape of roomkit's .github/workflows/ci.yml at 781f0c9d5, shortened.
WORKFLOW = """name: CI

on:
  push:
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    env:
      OTHER: value
    steps:
      - name: Ruff check
        run: uv run ruff check .

  # Runs the tests that need real infrastructure.
  integration:
    name: Integration (real Postgres + WebRTC)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
    env:
      POSTGRES_DSN: postgresql://postgres:postgres@localhost:5432/roomkit_test
      REDIS_URL: redis://localhost:6379
    steps:
      - uses: actions/checkout@v7

      # The shared scenarios on PostgreSQL: each case runs on a schema of its
      # own, created before it and dropped after it, so they run in parallel.
      - name: Run the shared scenarios on PostgreSQL
        run: >-
          uv run pytest -v -n auto --dist worksteal
          --junitxml=test-results/postgres-scenarios.xml
          tests/conformance/test_postgres.py

      # Every kit built without a turn backend gets one across Redis.
      - name: Run the suite with the kit's turns across Redis
        env:
          ROOMKIT_TEST_TURN_BACKEND: redis
        run: env -u POSTGRES_DSN uv run --with fastapi --with httpx2 pytest -q -n auto --dist worksteal --junitxml=test-results/redis-turns.xml

      - name: Upload the JUnit reports
        if: ${{ !cancelled() }}
        uses: actions/upload-artifact@v7
        with:
          name: integration-junit
          path: test-results/
"""
REDIS_STEP_RUN = "--dist worksteal --junitxml=test-results/redis-turns.xml\n"
POSTGRES_STEP_RUN = "          tests/conformance/test_postgres.py\n"


class CleaningTests(unittest.TestCase):
    def test_a_retained_report_keeps_identity_and_outcome_only(self) -> None:
        content = clean(REPORT, {MODULE})
        self.assertEqual(leftovers(content), [])
        text = content.decode()
        for gone in ["runner-7", "2026-11-13", "time=", "file=", "line=", "worker",
                     "Traceback", "log ", "/home/", "/tmp/", "test_acp_fixture"]:
            with self.subTest(gone=gone):
                self.assertNotIn(gone, text)
        for kept in ['name="test_scenario[b]"', 'type="pytest.skip"',
                     'message="in process: conftest.py says so"',
                     'message="x.py:3: /expect/timeline/r differs"',
                     'tests="3"', 'skipped="1"', 'failures="1"', 'errors="0"']:
            with self.subTest(kept=kept):
                self.assertIn(kept, text)

    def test_leftovers_name_what_a_report_must_not_carry(self) -> None:
        for raw, found in [
            ('<testsuite hostname="h"/>', "testsuite@hostname"),
            (f'<testsuite><testcase classname="{MODULE}" name="x" time="1"/></testsuite>',
             "testcase@time"),
            ("<testsuite><testcase>trace</testcase></testsuite>", "testcase: text"),
            ('<testsuite><testcase><skipped message="/home/me/x.py"/></testcase></testsuite>',
             "skipped@message: local path"),
        ]:
            with self.subTest(found=found):
                self.assertIn(found, leftovers(raw.encode()))

    def test_only_the_output_path_of_a_command_is_reduced(self) -> None:
        self.assertEqual(
            portable(["env", "A=/x/y", "pytest", "--junitxml=/home/me/out/run.xml",
                      "--junit-xml", "/home/me/two.xml", "--junit-xml=/tmp/three.xml"]),
            ["env", "A=/x/y", "pytest", "--junitxml=run.xml", "--junit-xml", "two.xml",
             "--junit-xml=three.xml"],
        )
        with self.assertRaisesRegex(ValueError, "local paths"):
            portable(["env", "PYTHONPATH=/home/me/roomkit/src", "pytest"])


class WorkflowTests(unittest.TestCase):
    """`record.py ci` records the CI steps' commands only while CI runs them."""

    def drift(self, workflow: str) -> dict[str, list[str]]:
        return {report.file: workflow_drift(workflow, report) for report in CI_REPORTS}

    def test_the_recorded_commands_are_the_workflow_s(self) -> None:
        self.assertEqual(self.drift(WORKFLOW), {"postgres-scenarios.xml": [], "redis-turns.xml": []})

    def test_a_changed_environment_or_step_is_drift(self) -> None:
        job_env = "      REDIS_URL: redis://localhost:6379\n"
        for label, workflow, drifting in [
            ("job turns", WORKFLOW.replace(job_env, job_env + "      ROOMKIT_TEST_TURN_BACKEND: redis\n"),
             {"postgres-scenarios.xml", "redis-turns.xml"}),
            ("workflow env", WORKFLOW.replace("jobs:\n", "env:\n  A: b\n\njobs:\n"),
             {"postgres-scenarios.xml", "redis-turns.xml"}),
            ("flow workflow env",
             WORKFLOW.replace("jobs:\n", "env: {ROOMKIT_TEST_TURN_BACKEND: redis}\n\njobs:\n"),
             {"postgres-scenarios.xml", "redis-turns.xml"}),
            ("step env", WORKFLOW.replace(
                "      - name: Run the shared scenarios on PostgreSQL\n",
                "      - name: Run the shared scenarios on PostgreSQL\n        env:\n"
                "          POSTGRES_DSN: postgresql://elsewhere/db\n"),
             {"postgres-scenarios.xml"}),
            ("selection", WORKFLOW.replace(POSTGRES_STEP_RUN, POSTGRES_STEP_RUN.rstrip() + " -k x\n"),
             {"postgres-scenarios.xml"}),
            ("argument", WORKFLOW.replace(REDIS_STEP_RUN, REDIS_STEP_RUN.rstrip() + " -x\n"),
             {"redis-turns.xml"}),
            ("no report yet", WORKFLOW.replace(" --junitxml=test-results/redis-turns.xml", ""),
             {"redis-turns.xml"}),
        ]:
            with self.subTest(label=label):
                self.assertEqual({file for file, found in self.drift(workflow).items() if found},
                                 drifting)


class RecordingTests(unittest.TestCase):
    """The importer against two throwaway repositories: specs and roomkit."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.specs = Path(temp.name) / "specs"
        self.python = Path(temp.name) / "roomkit"
        self.scenarios = {"a": {"id": "a", "expect": {"v": 1}}, "b": {"id": "b", "expect": {"v": 2}}}
        (self.specs / "conformance" / "executions").mkdir(parents=True)
        (self.specs / "roomkit-rfc.md").write_text("## 9. Hooks\n" + marked("Keep the event."))
        self.place(self.specs / "conformance" / "scenarios")
        corpus = self.commit(self.specs)
        copy = self.python / "tests" / "conformance"
        self.place(copy / "scenarios")
        (copy / "SPECS_COMMIT").write_text(corpus + "\n")
        (self.python / ".github" / "workflows").mkdir(parents=True)
        (self.python / ".github" / "workflows" / "ci.yml").write_text(WORKFLOW)
        self.python_commit = self.commit(self.python)
        self.evidence = {
            "version": 1, "python_commit": self.python_commit, "retired": [],
            "links": [], "executions": [],
        }
        (self.specs / "conformance" / "evidence.json").write_text(layout(self.evidence))
        self.command = ["env", "-u", "POSTGRES_DSN", "ROOMKIT_TEST_TURN_BACKEND=redis",
                        "uv", "run", "pytest", "--junitxml=/home/me/redis-turns.xml"]

    def place(self, directory: Path) -> None:
        directory.mkdir(parents=True)
        for name, scenario in self.scenarios.items():
            (directory / f"{name}.json").write_text(json.dumps(scenario))

    def commit(self, repo: Path) -> str:
        def git(*args: str) -> str:
            return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Conformance Test", "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        return git("rev-parse", "HEAD")

    def record(self, backends: list[str], command: list[str] | None = None):
        return prepare(
            self.specs, self.python, REPORT, "python-redis-turns", backends, command or self.command
        )

    def test_a_report_becomes_receipts_check_py_accepts(self) -> None:
        recording = self.record(["memory+redis-turns", "sqlite+redis-turns"])
        write(self.specs, [recording])
        document = json.loads((self.specs / "conformance" / "evidence.json").read_text())
        memory, sqlite = document["executions"]
        self.assertEqual(memory["id"], f"python-redis-turns-{self.python_commit[:7]}-memory-redis-turns")
        self.assertEqual(memory["implementation_commit"], self.python_commit)
        self.assertEqual(
            list(memory),
            ["id", "implementation", "implementation_commit", "rfc_commit", "corpus_commit",
             "rfc_sha256", "backend", "runtime", "command", "artifact", "results"],
        )
        self.assertEqual(memory["command"][-1], "--junitxml=redis-turns.xml")
        self.assertEqual(
            [(r["scenario"], r["outcome"]) for r in memory["results"]],
            [("a", "passed"), ("b", "skipped")],
        )
        self.assertEqual([(r["scenario"], r["outcome"]) for r in sqlite["results"]], [("a", "failed")])
        self.assertEqual(memory["results"][0]["sha256"], digest(self.scenarios["a"]))
        self.assertEqual(leftovers(recording.artifact.read_bytes()), [])
        for run in document["executions"]:
            self.assertEqual(validate_artifact(run, self.specs), [])
        self.assertEqual(provenance(document, self.specs, {"python": self.python}), [])
        with self.assertRaisesRegex(ValueError, "already recorded"):
            write(self.specs, [recording])

    def test_a_redis_report_needs_the_command_that_selects_redis(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not select"):
            self.record(["memory+redis-turns"], ["env", "ROOMKIT_TEST_TURN_BACKEND=memory", "pytest"])

    def test_a_backend_absent_from_the_report_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no postgres scenario case"):
            self.record(["postgres"], ["pytest"])
        with self.assertRaisesRegex(ValueError, "backends must be among"):
            self.record(["postgres+redis-turns"])

    def test_a_copy_that_differs_from_the_corpus_is_refused(self) -> None:
        copy = self.python / "tests" / "conformance" / "scenarios" / "a.json"
        copy.write_text(json.dumps({"id": "a", "expect": {"v": 3}}))
        self.python_commit = self.commit(self.python)
        self.evidence["python_commit"] = self.python_commit
        (self.specs / "conformance" / "evidence.json").write_text(layout(self.evidence))
        with self.assertRaisesRegex(ValueError, "copy differs"):
            self.record(["memory+redis-turns"])

    def gh(self, runs: list[dict], files: dict[str, bytes]):
        """A `gh` that lists *runs* and downloads *files*; it notes each call."""
        calls: list[tuple[str, ...]] = []

        def gh(*args: str) -> str:
            calls.append(args)
            if args[:2] == ("run", "download"):
                directory = Path(args[args.index("-D") + 1])
                for name, content in files.items():
                    (directory / name).write_bytes(content)
                return ""
            return json.dumps(runs)

        return gh, calls

    def from_ci(self, gh):
        return from_ci(self.specs, self.python, "roomkit-live/roomkit", self.python_commit, gh)

    def test_ci_records_the_reports_of_the_commit_s_latest_completed_run(self) -> None:
        runs = [
            {"databaseId": 3, "status": "in_progress", "conclusion": ""},
            {"databaseId": 2, "status": "completed", "conclusion": "success"},
        ]
        gh, calls = self.gh(runs, {"postgres-scenarios.xml": POSTGRES_REPORT, "redis-turns.xml": REPORT})
        recordings, notes = self.from_ci(gh)
        self.assertEqual(calls[0][calls[0].index("--commit") + 1], self.python_commit)
        self.assertEqual(calls[1][:3], ("run", "download", "2"))
        self.assertEqual(
            [run["backend"] for recording in recordings for run in recording.receipts],
            ["postgres", "memory+redis-turns", "sqlite+redis-turns"],
        )
        postgres = recordings[0].receipts[0]
        self.assertEqual(postgres["command"][-2:], ["--junitxml=postgres-scenarios.xml",
                                                    "tests/conformance/test_postgres.py"])
        self.assertEqual([r["scenario"] for r in postgres["results"]], ["a", "b"])
        self.assertEqual(notes, [f"CI run 2 of {self.python_commit}"])

    def test_ci_refuses_a_failed_run_drift_and_an_empty_artifact(self) -> None:
        failed = [{"databaseId": 2, "status": "completed", "conclusion": "failure"}]
        with self.assertRaisesRegex(ValueError, "no successful CI run"):
            self.from_ci(self.gh(failed, {})[0])
        green = [{"databaseId": 2, "status": "completed", "conclusion": "success"}]
        with self.assertRaisesRegex(ValueError, "holds no report"):
            self.from_ci(self.gh(green, {})[0])
        recordings, notes = self.from_ci(self.gh(green, {"postgres-scenarios.xml": POSTGRES_REPORT})[0])
        self.assertEqual(len(recordings), 1)
        self.assertIn("redis-turns.xml: not in the run's integration-junit", notes[1])
        workflow = self.python / ".github" / "workflows" / "ci.yml"
        workflow.write_text(WORKFLOW.replace("-q -n auto", "-q -n 4"))
        self.python_commit = self.commit(self.python)
        self.evidence["python_commit"] = self.python_commit
        (self.specs / "conformance" / "evidence.json").write_text(layout(self.evidence))
        with self.assertRaisesRegex(ValueError, "no integration step"):
            self.from_ci(self.gh(green, {"redis-turns.xml": REPORT})[0])


if __name__ == "__main__":
    unittest.main()
