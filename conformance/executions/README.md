# Retained execution evidence

`python-hooks-33d1f4.xml` retains all 55 selected scenario outcomes from:

```sh
PYTHONPATH=src python -m pytest tests/conformance -k hooks -n 0 --junitxml=python-hooks.xml
```

The run used a clean checkout at `33d1f4415e2a5697cbe5b4f6cb8413ee05f33363`,
Linux, Python 3.13.3, pytest 9.1.1 and pytest-asyncio 1.4.0, with the memory store
and default in-process turns. Its copied corpus is
`38d677a02ac811d4aaad2dbaf3ac97ee5bfc9fd5`; the clauses were reviewed against
RFC commit `5f60000e713e9d8bfee526d08009bb4322667ff8`. The `-k hooks` expression
also selects cases outside the hooks directory whose names contain "hooks".

The JUnit artifact preserves every selected testcase's class, name and outcome.
Volatile suite metadata (host, timestamp, durations and local paths) is omitted.
All 55 cases passed; none was skipped, failed or errored. The receipt in
`evidence.json` records their hashes and all three source commits. Its validator
checks the implementation's actual scenario copy as well as the specs source.

This is evidence of that selected run at those versions. It does not establish
complete coverage of a source unit, other stores, Redis turns, Python's later
commits, specialized tests, or Rust. See the separate mapping and execution
states in [the report](../coverage.md).
