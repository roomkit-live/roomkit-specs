#!/usr/bin/env python3
"""Record Python execution receipts from pytest JUnit reports, at the evidence's
`python_commit` (conformance/executions/README.md, "Recording receipts").

    # PostgreSQL and Redis turn mode, from the CI run of python_commit:
    python3 conformance/record.py ci --python-repo ../roomkit

    # any other report, with the command that wrote it after `--`:
    python3 conformance/record.py junit --python-repo ../roomkit \\
        --junit ../roomkit/python-conformance.xml --name python-core \\
        --backend memory --backend sqlite \\
        -- env -u POSTGRES_DSN ROOMKIT_TEST_TURN_BACKEND=memory uv run pytest \\
           tests/conformance --junitxml=python-conformance.xml

The report is cleaned and retained under conformance/executions/, and each
backend becomes a receipt appended to evidence.json. `ci` needs the GitHub CLI
(`gh`), and records only from a successful run of the exact commit. Then run
`check.py --strict --traceability --update-traceability --python-repo ...`.

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
from traceability.importer import counts, prepare, write  # noqa: E402


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
    args = parser.parse_args()
    if args.source == "junit":
        args.command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not args.command:
            parser.error("give the command that wrote the report after --")
    return args


def main() -> int:
    args = arguments()
    commit = json.loads((HERE / "evidence.json").read_text())["python_commit"]
    try:
        if args.source == "ci":
            recordings, notes = from_ci(ROOT, args.python_repo, args.repository, commit)
            print("\n".join(notes))
        else:
            report = args.junit.read_bytes()
            recordings = [
                prepare(ROOT, args.python_repo, report, args.name, args.backend, args.command)
            ]
        for run in write(ROOT, recordings):
            print(f"{run['id']}: {run['backend']} at {commit[:12]}, {counts(run)}")
    except subprocess.CalledProcessError as error:
        print(f"error: {' '.join(error.cmd)}: {error.stderr}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
