# Retained execution evidence

`python-hooks-33d1f4.xml` retains all 55 selected scenario outcomes from:

```sh
ROOMKIT_TEST_TURN_BACKEND=memory PYTHONPATH=src python -m pytest tests/conformance -k hooks -n 0 --junitxml=python-hooks.xml
```

The run used a clean checkout at `33d1f4415e2a5697cbe5b4f6cb8413ee05f33363`,
Linux, Python 3.13.3, pytest 9.1.1 and pytest-asyncio 1.4.0, with the memory store
and explicitly selected in-process turns (`ROOMKIT_TEST_TURN_BACKEND=memory`). Its copied corpus is
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


## Static permission matrices and hooks

`python-permissions-ecf9bc5.xml` retains all 81 selected scenario outcomes from:

```sh
ROOMKIT_TEST_TURN_BACKEND=memory PYTHONPATH=src python -m pytest tests/conformance -k 'permissions or hooks' -n 0 --junitxml=python-permissions.xml
```

The run used the clean Python commit
`ecf9bc5f7e92a440413b2518e799afce31bd5042`, Linux, Python 3.13.3, pytest 9.1.1
and pytest-asyncio 1.4.0, the memory store and in-process turns. Both the copied
corpus and reviewed RFC are from `7a684109f1e416f793f6425adaff5617f5b86af4`.
All 81 cases passed, with no skips, failures or errors. The selection includes
both new access/mute matrices and the existing permissions and hooks cases;
it refreshes the pilot's scenario results without executing its specialized
wrong-payload test. Host, timestamp and duration metadata is removed, preserving
every testcase's class, name and outcome. The same scope limits above apply.

## Visibility grammar and private history

`python-visibility-8fb44e9.xml` retains all 89 selected scenario outcomes from:

```sh
ROOMKIT_TEST_TURN_BACKEND=memory PYTHONPATH=src uv run --active --no-sync pytest tests/conformance -k 'permissions or hooks' --junitxml=python-visibility.xml -q
```

The run used clean Python commit `8fb44e947b1c2e6d6b74de18bc28cd921cd47726`,
Linux, Python 3.13.3, pytest 9.1.1 and pytest-asyncio 1.4.0, an existing activated
virtual environment, the memory store and in-process turns. Both the copied
corpus and reviewed RFC are from `a27e1eee5d85a6aed74b89aa162dee4aa7b2f011`.
The command records a portable output filename; its machine-local destination
and virtual-environment path are omitted. The artifact retains every testcase's
class, name and outcome, and removes host, timestamp, duration and local-path
attributes before publication. All 89 cases passed without skips or errors.

This selection refreshes the permission and hook scenario evidence, including
the eight visibility/history scenarios. It does not execute specialized Python
tests, other stores or Rust. A complete static clause mapping and a passed
execution receipt are separate checks; neither establishes whole-framework
conformance. The broader visibility units remain partially mapped.

## Response scopes and refused/deleted history

`python-response-history-3e4e215.xml` retains all 102 selected scenario outcomes from:

```sh
ROOMKIT_TEST_TURN_BACKEND=memory PYTHONPATH=src uv run --active --no-sync pytest tests/conformance -k 'permissions or hooks or a-sent-event-keeps-its-answer-scope or a-greeting-stays-within' --junitxml=python-response-history.xml -q
```

The run used clean Python commit `3e4e215c3ca0b9efcce4c7e5f84be3dfb7d7fd9e`,
Linux, Python 3.13.3, pytest 9.1.1 and pytest-asyncio 1.4.0, the activated
virtual environment, memory store and in-process turns. The copied corpus and
reviewed RFC are from `836945ce526c19b04fee39d8b2dca01c828bb2b9`.
Every selected case passed; none was skipped, failed or errored. Only portable
case identity and outcome attributes are retained; hostnames, timestamps,
durations and local paths were removed before publication.

The selection includes the eleven response/history scenarios, the extended
injection scope case and the existing greeting proof, as well as the prior
permissions/hooks selection. Specialized Python and Rust tests, voice record
creation, other stores and distributed turns are outside this receipt. Their
source mappings do not become passed executions through this artifact.

## Hook injection passes

`python-hook-injections-a6daaf1.xml` retains all 55 selected scenario outcomes from:

```sh
ROOMKIT_TEST_TURN_BACKEND=memory PYTHONPATH=src uv run --active --no-sync pytest tests/conformance/test_conformance.py -k 'inject or a-challenge' -q --junitxml=python-hook-injections.xml
```

The run used clean Python commit `a6daaf1391214c917936b1b37f50b5e2f7c88e20`,
with the memory store and in-process turns. The copied corpus and reviewed RFC
are from `175c13890427434e6d2e9ed7611ef2c8b109f3a5`. Every selected case passed,
with no skips or errors. Host, timestamps, durations and local paths are removed;
testcase names, classes and outcomes are retained. The command records a portable
output filename instead of its local artifact destination.

The selection covers the new injection scenarios and related existing cases. It
does not prove specialized Python fault injection or warning assertions, Rust
execution, other stores, or the remaining obligations of the partial RFC clauses.


## Remaining injection obligations

`python-injection-obligations-d8cc647.xml` retains the 37 exact scenario IDs named by the receipt's
`command` in `evidence.json`, run on clean Python commit
`d8cc647ca46e0dc75664bc6966567f5914da3b10`. The copied corpus and reviewed RFC are
`df7bcc9d8d9659e56d41d91f55ea692a7aa7ee54`. All 37 passed, with no skips, failures or
errors, on the memory store, in-process turns and asyncio. The run used Linux,
Python 3.13.3, pytest 9.1.1 and pytest-asyncio 1.4.0 with the existing virtual
environment. The artifact removes host, timestamp, duration and local-path
attributes, preserving every testcase's class, name and outcome.

This selection covers injection passes, forbidden instruction injections and
eligibility at broadcast, delivery, verification and identity challenge calls.
It does not execute the specialized trigger-policy matrices or silent voice
contexts, other stores, distributed turns or Rust. RK-9.4-004 and RK-9.4-006
remain partially mapped; a successful receipt does not expand that scope.
