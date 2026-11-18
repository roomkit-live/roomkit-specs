#!/usr/bin/env python3
"""Record execution receipts from JUnit reports: Python's at the evidence's
`python_commit`, roomkit-rs's at its checkout's commit
(conformance/executions/README.md, "Recording receipts").

    # PostgreSQL and Redis turn mode, from the CI run of python_commit:
    python3 conformance/record.py ci --python-repo ../roomkit

    # any other report, with the command that wrote it after `--`:
    python3 conformance/record.py junit --python-repo ../roomkit \\
        --junit ../roomkit/python-conformance.xml --name python-core \\
        --backend memory --backend sqlite \\
        -- env -u POSTGRES_DSN ROOMKIT_TEST_TURN_BACKEND=memory uv run pytest \\
           tests/conformance --junitxml=python-conformance.xml

    # roomkit-rs's result files, one pass each, with the command that wrote them:
    python3 conformance/record.py rust --rust-repo ../roomkit-rs \\
        --junit ../roomkit-rs/target/conformance/memory-current_thread.xml \\
        --junit ../roomkit-rs/target/conformance/memory-multi_thread_4.xml \\
        -- env ROOMKIT_CONFORMANCE_JUNIT=target/conformance \\
           cargo test -p roomkit --test conformance

The report is cleaned and retained under conformance/executions/, and each
backend, or each Rust pass, becomes a receipt appended to evidence.json. `ci`
needs the GitHub CLI (`gh`), and records only from a successful run of the
exact commit. Then run `check.py --strict --traceability --update-traceability
--python-repo ... --rust-repo ...`.

It needs `jsonschema`, as check.py does.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from traceability.ci import from_ci  # noqa: E402
from traceability.importer import counts, prepare, prepare_rust, write  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--python-repo", type=Path, required=True, help="a roomkit clone")
    commands = parser.add_subparsers(dest="source", required=True)
    ci = commands.add_parser(
        "ci", parents=[common], help="the reports of roomkit CI's run of python_commit"
    )
    ci.add_argument("--repository", default="roomkit-live/roomkit")
    one = commands.add_parser(
        "junit", parents=[common], help="one report, with the command that wrote it"
    )
    one.add_argument("--junit", type=Path, required=True)
    one.add_argument("--name", required=True, help="the run's name, e.g. python-redis-turns")
    one.add_argument("--backend", action="append", required=True)
    one.add_argument("command", nargs=argparse.REMAINDER)
    rust = commands.add_parser(
        "rust", help="roomkit-rs result files, with the command that wrote them"
    )
    rust.add_argument("--rust-repo", type=Path, required=True, help="a roomkit-rs clone")
    rust.add_argument("--junit", type=Path, action="append", required=True)
    rust.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.source in ("junit", "rust"):
        args.command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not args.command:
            parser.error("give the command that wrote the report after --")
    return args


def main() -> int:
    args = arguments()
    try:
        if args.source == "rust":
            recordings = [
                prepare_rust(ROOT, args.rust_repo, report.read_bytes(), args.command)
                for report in args.junit
            ]
        elif args.source == "ci":
            commit = json.loads((HERE / "evidence.json").read_text())["python_commit"]
            recordings, notes = from_ci(ROOT, args.python_repo, args.repository, commit)
            print("\n".join(notes))
        else:
            report = args.junit.read_bytes()
            recordings = [
                prepare(ROOT, args.python_repo, report, args.name, args.backend, args.command)
            ]
        for run in write(ROOT, recordings):
            print(
                f"{run['id']}: {run['backend']} / {run['runtime']} at "
                f"{run['implementation_commit'][:12]}, {counts(run)}"
            )
    except subprocess.CalledProcessError as error:
        print(f"error: {' '.join(error.cmd)}: {error.stderr}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
