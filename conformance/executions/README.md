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


## Core shutdown and pre-commit deadlines

`python-core-close-final-corpus-e89dc28.xml` retains the clean run on Python
`e89dc28e3b09d708ad1448125585d3e8bf99b657`, copied corpus and reviewed RFC
`f7ce8cf4e8b8bcda1381a739093c3a53a09701cc`. The command in the receipts runs
`tests/conformance` and `tests/test_precommit_timeout.py`, with in-process turns
and one pytest worker. All 2,168 tests pass without skips or errors.

The receipts identify 1,739 memory scenarios and 380 SQLite scenarios. Auxiliary
runner and native deadline tests in the retained artifact are not scenario
receipts. PostgreSQL and Rust checks are recorded separately. The mapping of
shutdown and processing deadlines remains partial: no execution fills a missing
assertion or proves an untested lifecycle entry point. Volatile host, timestamp,
duration and local-path metadata is removed from the artifact.


## Core shutdown answers

`python-core-shutdown-answers-a7fac2f.xml` retains the clean run on Python
`a7fac2fc0e63bb82f18b7ef78557aca383840521`, with copied corpus and reviewed RFC
`14a09d13f65d1ff01101da3e053c991462f4bce4`. The command in `evidence.json`
runs `tests/conformance` with in-process turns and one pytest worker.
All 2,210 cases pass without skips, failures or errors: 1,784 memory scenarios,
393 SQLite scenarios and 33 auxiliary runner cases. Only the scenarios enter
the execution receipts. Host, timestamp, duration and local-path attributes
are removed; testcase classes, names and outcomes are preserved.

The new assertions cover an answer's observer closing the kit after a channel
response or an AFTER_BROADCAST send. The native retained-cursor witness in
`tests/test_kit_close_own_answer.py` is referenced as source evidence and is not
executed by this command. It supplies a temporal premise that an un-gated
scenario cannot establish on several workers. This receipt neither certifies
Rust execution nor closes the remaining shutdown annex, other stores or remote
executor variants. The linked RFC requirement remains partially covered.

## Discussion task names

`python-task-names-1280f23.xml` retains the clean run on Python
`1280f23489f044354d552703d99dcadf3eefc08e`, with copied corpus and reviewed RFC
`d5ee856f626f4266ff18f1bb3a0b8c682cba6fa5`. All 2,213 cases pass without skips,
failures or errors: 1,787 memory scenarios, 393 SQLite scenarios and 33 auxiliary
runner cases. Only the scenarios enter the execution receipts. Host, timestamp,
duration and local-path attributes are removed; classes, names and outcomes
are preserved.

The three added scenarios cover a relayed result and both task-status tool
installations naming a discussion worker by its handle, while internal task
records retain channel ids. They ran on memory only. The composite discussion
requirement remains partially covered; this receipt does not certify Rust,
remote executors or the remaining task-result paths.

The command records a portable output filename in place of its machine-local
destination. The same normalization applies to the four command arguments in
the earlier `python-core-shutdown-boundaries-0aa9b53` and
`python-core-shutdown-answers-a7fac2f` receipts. Only output destinations were
normalized; their retained XML, results and fingerprints are unchanged.

## Local executor and named room hooks

`python-kit-executor-43d2f2e.xml` retains the clean run on Python
`43d2f2e29020481721bddc422901276a4f8f8bde`, with copied corpus
`8e9a51f0a132f679cbfd6d6832e6dc8f1c7bf1a4` and reviewed RFC
`17d793e75512f562bc879329b94089a6c0fd59c2`. The run follows the approved
clarification that enabling the same name again preserves one activation and
its order; collisions with another room-hook registration remain refused.
The scenario corpus is unchanged by that clarification.

The receipts' command runs `tests/conformance` with in-process turns, asyncio
and one pytest worker. All 2,395 cases pass without skips, failures or errors:
1,899 memory scenarios, 409 SQLite scenarios and 87 auxiliary runner cases.
Only scenarios enter the two receipts; the nine new named-hook cases are
memory only. The XML keeps testcase identity and outcome, with host, timestamp
and local-path attributes removed and durations normalized to zero.

The links remain partial. This run does not certify the paired native API tests,
Rust, remote executors, real PostgreSQL or all lifecycle methods of the local
executor. The 75 previously published receipts remain unchanged.

## Recording receipts

`conformance/record.py` writes every receipt from a pytest JUnit report; none
is edited by hand. It records at the `python_commit` of `evidence.json` only:
whoever moves that commit moves it first, then records. It reads the corpus the
implementation copied (`tests/conformance/SPECS_COMMIT` at that commit) and the
last commit of `roomkit-rfc.md`, which must match the checkout's RFC.

The retained report keeps only the testcases of the runner module of the
recorded backends (`tests.conformance.test_conformance`, or
`tests.conformance.test_postgres`), each with its class, its name and its
outcome; a skip, failure or error keeps pytest's `type` and `message`, with the
directories of local paths cut out of the message. Hosts, timestamps,
durations, file and line attributes, properties, captured output and
tracebacks are dropped, and the suite counts are recomputed from the cases kept.
The command's `--junitxml` path becomes its file name. Each backend becomes one
receipt, `<name>-<commit>-<backend>` with `+` written `-`, holding every
scenario case of that backend in the report with its outcome and the scenario's
hash at the copied corpus; a scenario with several cases in the report takes
the worst of them. The import is refused when a backend has no case in the
report; when a Redis turn-mode receipt's command does not set
`ROOMKIT_TEST_TURN_BACKEND=redis`, another one's does, or the command names the
variable where its turn mode cannot be read (a wrapper such as `flock` or
`sh -c` around it: record the command without its wrapper); when the command
still names a local path; when the implementation's copy of a scenario differs
from the corpus; when the receipt id is already recorded; or when the retained
file exists with other content.

After `python_commit` moves, once roomkit's CI run of that commit is green,
one command refreshes the PostgreSQL and Redis turn-mode receipts:

```sh
uv run --no-project --python 3.13 --with jsonschema==4.26.0 \
  python conformance/record.py ci --python-repo ../roomkit
```

It takes the successful push run of the `CI` workflow on that exact commit,
downloads its `integration-junit` artifact with `gh`, and records
`postgres-scenarios.xml` as `python-postgres-scenarios-<commit>-postgres` and
`redis-turns.xml` as `python-redis-turns-<commit>-memory-redis-turns` and
`-sqlite-redis-turns`. Their commands are the CI steps' own, written in
`CI_REPORTS` (`traceability/ci.py`). The import is refused unless
`.github/workflows/ci.yml` at that commit sets no workflow environment, gives the
integration job exactly the recorded environment, and holds each step exactly as
recorded, comments aside. CI writes
`redis-turns.xml` from roomkit `781f0c9d5fd01682e4f90285d942ba74fae2e0e7` on;
an artifact without it records PostgreSQL only and says so. Then regenerate the
report:

```sh
uv run --no-project --python 3.13 --with jsonschema==4.26.0 \
  python conformance/check.py --strict --traceability --update-traceability \
  --python-repo ../roomkit
```

A local run is recorded with `record.py junit`, the command that ran after
`--`, for instance the memory and SQLite receipts of a conformance run:

```sh
uv run --no-project --python 3.13 --with jsonschema==4.26.0 \
  python conformance/record.py junit --python-repo ../roomkit \
  --junit ../roomkit/python-conformance.xml --name python-<lot> \
  --backend memory --backend sqlite \
  -- env -u POSTGRES_DSN ROOMKIT_TEST_TURN_BACKEND=memory uv run pytest \
     tests/conformance -q --junitxml=python-conformance.xml
```

## PostgreSQL and the Redis turn mode

`python-postgres-scenarios-6dc6edb.xml` retains the 447 cases of roomkit CI run
43363231272 on Python `6dc6edb3f58722247ff9f851b686f73bf124f543`, job
Integration, step "Run the shared scenarios on PostgreSQL": PostgreSQL 16 and
Redis 7 services, Python 3.12, `pytest -n auto`, each case on a schema of its
own. The copied corpus is `9552d7f4db41c05227e2f40cb0709029a37e9788`; the
RFC is `07f7bf2b9ca7dd77b9bcbee91ad7c76bd34ea38a`. All 447 cases passed. They
are 444 scenarios: 428 `test_scenario` cases (the scenarios whose contract
writes to the store, and every scenario with other processes) and 16
`test_shared_postgres_contract` cases, three of which also run a
slow-preparation variant. The receipt
`python-postgres-scenarios-6dc6edb-postgres` records 444 passes.

`python-redis-turns-6dc6edb.xml` retains the 2,629
`tests.conformance.test_conformance` cases of CI's Redis-pass command, restricted
to `tests/conformance`, run on a clean detached checkout of the same commit:
Linux, Python 3.13.3, pytest 9.1.1, pytest-xdist 3.8.0 and pytest-asyncio 1.4.0,
and a local Redis 7.4 (the `REDIS_URL` in the command). A lock and a CPU
affinity wrapped the command; neither changes what runs, and the recorded
command leaves them out. The whole run passed 2,736
cases and skipped 468, exit 0; the 447 PostgreSQL cases skip there by design,
the Redis pass unsetting `POSTGRES_DSN`. The receipts record:

- `python-redis-turns-6dc6edb-memory-redis-turns`: 2,063 scenarios, 2,051
  passed and 12 skipped;
- `python-redis-turns-6dc6edb-sqlite-redis-turns`: 565 scenarios, 556 passed
  and 9 skipped.

They select the same scenarios as `python-acp-permissions-6dc6edb-memory` and
`-sqlite`. The 21 skips are the cases marked `in_process`: 20 whose scripted
agent's turn calls the kit it holds, and `acp/tools-observer-reentry-bound`,
whose tool observer calls its captured kit. Across Redis such a turn reaches the
room through its TurnHost (RK-10.6.5-003); the receipts say skipped, so those
scenarios have no Redis pass. CI's own Redis pass at roomkit
`781f0c9d5fd01682e4f90285d942ba74fae2e0e7` (run 43379749129), whose tree
differs only by `ci.yml`, gives the same counts for these cases.

These receipts prove the named scenarios at that commit on real PostgreSQL, and
with the kit's turns carried by Redis to its own executor in the same process.
They do not prove PostgreSQL with turns across Redis, a real process death, an
executor in another process, the specialized PostgreSQL and Redis tests (store
contracts, advisory locks, multi-process and process-death tests), which stay
source evidence, or Rust. No receipt is merged with another.
