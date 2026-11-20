# Requirement traceability

The RFC is normative. `requirements.json` is generated from its annotations;
`evidence.json` contains reviewed links, never replacement rules.
`coverage.md` and `coverage.json` keep inventory, mappings and executions separate.
They do not certify a conformance level or calculate a percentage of compliance.

## Check and regenerate

Use Python 3.12+ with the checker's existing `jsonschema` dependency. A local
clone of roomkit must contain the full `python_commit` from `evidence.json`,
and a clone of roomkit-rs the commits its Rust receipts name.

```sh
python conformance/check.py --strict --traceability --python-repo ../roomkit \
  --rust-repo ../roomkit-rs
python -m unittest discover -s conformance/tests -v
```

Add `--update-traceability` only to regenerate the derived artifacts
(`requirements.json`, `coverage.json`, `coverage.md` and the pages of `rules/`).
This never updates review records or proof fingerprints. `--base-ref <full SHA>`
checks ID removals and retirement history against a previous specs commit.
The historical `--strict` check still resolves `rules` at `RFC_COMMIT`, and
reads `requirements` and the lock against the current RFC file, as traceability
does by default. Neither repins the other.

## Inventory and stable IDs

Wrap an exact source unit with HTML comments, without rewriting its text:

```markdown
<!-- rfc: {"id":"RK-9.3-012","kind":"behavior","applies":"ASYNC hooks"} -->
Original RFC text, including conditions and exceptions.
<!-- /rfc -->
```

IDs use the original section number and a never-reused serial. Moving a clause
preserves its ID. Splitting or withdrawing a unit retires its old ID in
`evidence.json`; replacement units get new IDs. Kinds are `behavior`,
`structural` (interfaces, fields, defaults) and `non_testable` (requirements
needing review or operational evidence). Applicability is explicit text from
the clause's context; no conformance level is inferred from its section number.

Inline comments inside a list item or table cell preserve Markdown structure.
Comments inside fenced examples are examples, not annotations. Units cannot
nest or cross numbered headings. Removing annotations restores the exact RFC
text, whose SHA-256 is recorded independently of annotations.

An inventory unit can contain several obligations. It is not an atomic test
case. Broad units stay partial until their entire scope has been reviewed.
`inventory.json` records section reviews, including informative sections;
the hash includes the text and annotations. A change invalidates that review.
Keyword detection is only a reading aid: tables, defaults, code contracts and
implicit rules require review too. Regeneration cannot approve a section.

The general inventory groups the complete text at numbered sections and named
paragraphs, keeping their conditions and examples together. A normative section
means it contains contract material, not that every explanatory sentence is a
separate obligation. Structural units identify interfaces and fields; mixed
blocks still need behavioral evidence. The preface is recorded as virtual
section `0` (no heading or section number is added to the RFC). Introduction
rationale, the withdrawn draft and the flow examples are explicitly informative.
Before marking a broad unit complete, split it into independently reviewable
contracts, retire its ID, and preserve every condition in the replacement units.

The checker rejects unannotated content in a reviewed normative section, even
without normative keywords and inside a model's code block. Candidate scenarios
in the report come from existing `rules` citations only; they guide review and
carry no coverage credit. Unmapped units can already have tests, whose assertion
links have not been reviewed yet.

## Citing units

A scenario cites the units it tests in `requirements`, beside its section
citations in `rules`, which stay for navigation:

```json
"rules": ["§10.4"],
"requirements": ["RK-10.4-022"]
```

The checker refuses an ID that names no unit of the current RFC, a retired ID
(cite the units that replace it) and a `non_testable` unit. A citation says the
scenario tests the unit; it is not a reviewed link, and a scenario can cite a
unit it covers only in part. Runners ignore `requirements`, and a scenario's
fingerprint leaves it out: citing a unit reopens none of the scenario's
reviewed links or execution receipts.

### When a scenario cites a unit

- It cites a unit when its assertions check what the unit obliges:
  `delivery/a-status-naming-no-recipient-gets-no-room-among-several` asserts
  that a status on a channel bound to several rooms reaches none, and cites
  RK-10.4-048.
- It does not cite a unit whose mechanism only brings it to the state under
  test: `discussion/a-routed-first-message-in-a-process-that-follows-reads-handles`
  routes its message only to reach the room whose discussion it tests, and
  cites no §10.4 unit.
- When it shows that a unit does not apply, it cites the unit that states the
  exclusion, not the excluded one:
  - `routing/an-explicit-room-bypasses-the-custom-router` names its room, so
    nothing routes it: it cites no §10.4 unit, never RK-10.4-008, which routes
    a message that names none, and cites the unit of §10.1 step 2 for a room
    the caller names once that section is split;
  - `routing/every-sender-on-a-group-binding-shares-its-room` cites
    RK-10.4-025, which admits every sender of a `group` binding, not
    RK-10.4-039, which records the sender on a binding that is not `group`.
- When it covers part of a unit, it cites the unit, and the report of the work
  that adds the citation names the part left uncovered:
  `routing/a-hook-refusal-keeps-the-routed-correspondent` cites RK-10.4-040
  for the sender recorded before the message is processed, not for two first
  messages racing to one room.

### Level

The reviewer of a unit sets its level in the annotation, whatever its keywords:

```markdown
<!-- rfc: {"id":"RK-10.4-022","kind":"behavior","applies":"Inbound routing","level":"must"} -->
```

The level is `must`, `should` or `may`, and `requirements.json` carries it. A
unit with no level has not been reviewed for one: the report shows `—`, and
nothing blocks on it. The level stays out of the unit's fingerprint, so setting
it reopens no link or lock entry; it edits the annotation, so the section's
inventory review is recorded again, as for any annotation change.

### The lock

`links.lock.json` pins each citation to the unit's fingerprint when the scenario
was last read against it, units then scenarios, sorted:

```json
{
  "version": 1,
  "links": {
    "RK-10.4-022": {
      "routing/a-message-from-an-unknown-address-opens-a-room": "5f0c…"
    }
  }
}
```

The lock lives here only: the implementations' copies never hold it, so a
change to the RFC changes no scenario and needs no sync. `check.py` prints a
`lock:` line, which fails `--strict`, when:

- a cited unit's text, kind or applicability changed since a scenario read it:
  `RK-10.4-022 changed since routing/x read it: reread it, then run python3
  conformance/check.py --pin RK-10.4-022`;
- a citation has no entry: `routing/x cites RK-10.4-022 with no lock entry:
  once it is read against it, run python3 conformance/check.py --pin
  RK-10.4-022 routing/x`;
- an entry has no citation: `links.lock.json pins routing/x to RK-10.4-023,
  which it does not cite: run python3 conformance/check.py --pin RK-10.4-023
  routing/x`.

A lock out of its sorted layout (a merge resolved by hand) is an error that any
`--pin` repairs.

### Re-pinning

Reread the scenario against the unit's new text, fix it if it no longer tests
what the unit says, then pin by name:

```sh
python3 conformance/check.py --pin RK-10.4-022            # every citation of this unit
python3 conformance/check.py --pin RK-10.4-022 routing/x  # this one citation
python3 conformance/check.py --pin routing/x              # every citation of this scenario
```

A unit names its citations and a scenario its own; naming both names the
citations of those units by those scenarios. A pin records the named citations
at the current text, drops the named entries no citation holds any more, and
moves nothing else. Naming a scenario alone records it as reread against every
unit it cites, changed ones included: the checker's own advice names the unit
too. A pin needs at least one name, refuses a name that selects nothing, and
pins nothing while a scenario, citation or lock check reports an error (the
`--traceability` and `--changed-units` checks run after it). It changes the
lock column of `rules/`, so run `--traceability --update-traceability` after it.

### The process rule

`check.py --changed-units --base-ref <full sha>` reads the units added since
that commit, or whose text, kind, applicability or level changed:

- `must`: a scenario cites it, or `untested.json` gives the reason none does;
  otherwise an error;
- `should`: without either, a warning;
- `may`: nothing;
- no level: listed as unreviewed, never blocking; but in a section every unit
  of which had a level at the base, its subsections' included, an error. A
  unit added there, moved there, or whose level is dropped, gets its level in
  the same change.

A `non_testable` unit needs no scenario and no reason: its kind is its reason.
It still needs a level in such a section. A unit's text is read as written,
so rewording it, or only rewrapping its lines, changes it.

```text
$ python3 conformance/check.py --changed-units --base-ref 2f35a764a425fe69453e22bdba378482673c7e34
process rule: units added or changed since 2f35a764a425: 1
error: RK-10.4-999 (must, added since 2f35a764a425): no scenario cites it and untested.json gives no reason
```

CI runs the rule on every push to main and every pull request to main, in the
step that checks the current RFC, against the base that step reads: the pull
request's base, the commit before the push, or the parent commit when there
is neither. The rule's errors fail the job. Its errors and warnings show as
GitHub annotations titled "Process rule" (`--github-annotations`). GitHub
caps how many annotations a step shows; the job's log lists every line. When
the RFC is the same as at the base, the rule reads no unit and costs nothing.

When it fires on a `must` unit, either:

- cite the unit in the `requirements` of the scenario that tests it, writing
  the scenario if none does, and pin the citation once read (`--pin
  RK-10.4-999 routing/x`);
- or, when no scenario can test it, give the reason in `untested.json`.

When it fires on a unit with no level, give the unit its level in its
annotation; the rule then reads it by that level. A `should` warning asks for
a scenario or a reason without blocking. Before pushing, run the rule
against the commit your change starts from: `--base-ref "$(git merge-base
origin/main HEAD)"`.

`untested.json` maps a current unit to its reason; a unit scenarios cite cannot
keep an entry (`--strict` says so):

```json
{
  "version": 1,
  "units": {
    "RK-10.4-999": "Needs a carrier's number lookup, which no runner reaches."
  }
}
```

### The per-rule report

[rules/](rules/README.md) holds an index and one page per top-level section,
generated and checked with the other artifacts. Each unit's row gives its kind,
its level, the scenarios citing it (or its untested reason), each citation's
lock state (`pinned`, `reread` after the unit changed, `unpinned`), and each
citing scenario's latest Python and Rust outcome per backend:

```markdown
| Unit | Kind | Level | Scenario | Lock | Python | Rust |
|---|---|---|---|---|---|---|
| RK-10.4-022 | behavior | must | `routing/x` | pinned | memory passed, sqlite passed |  |
```

An outcome counts when its receipt ran the scenario's current text (the same
hash), whatever its RFC commit. Receipts are appended as they are recorded, so
the last one listed is the latest. Rust's column stays empty until its runner
writes receipts.

## Reviewed links

Each link pins the clause, a JSON pointer into an actual expectation, and the
whole scenario but its `requirements` citations. A setup change invalidates its
review even when the expected value remains the same. `scope`, `proves`, `review` and `missing` describe what
was checked. A partial link must name its gaps; a complete link cannot list gaps.
A section citation in `rules` is useful navigation, never coverage credit.

Specialized Python tests use `file.py::Class::test_name` at the pinned commit,
with the source hash including decorators. References must use pytest test-file,
class and function naming conventions. Static resolution does not prove collection
or execution (configuration, fixtures and skips still matter). Such a link is source evidence only:
a passing scenario cannot stand in for that specialized test's execution.
Changing a fingerprint means rereading the proof, not just regenerating JSON.

Each validation reads the pinned Git objects, never checkout files. It reuses
one `git cat-file --batch` process per repository, without caching contents or
skipping historical receipts. All readers must finish before reports are written;
a broken response or failed process invalidates the check. Paths that cannot use
the line protocol and non-blob objects retain the individual `git show` reader.

## Execution receipts

Every receipt names implementation, RFC and corpus commits, backend, runtime,
command, selected scenario IDs and their hashes. Keep runner output under
`conformance/executions/` and fingerprint it. Commands are recorded, never run
by the checker. A receipt is a reviewed record of a run, not a signed attestation
that the working tree was clean; the author must run the exact clean commits.

The checker validates the saved output, actual commit contents and the corpus
copied into the implementation. Python's profiles are JUnit with `asyncio`,
one backend per receipt: `memory` and `sqlite` (cases of
`tests.conformance.test_conformance`), `postgres` (cases of
`tests.conformance.test_postgres`), and `memory+redis-turns` and
`sqlite+redis-turns`, the kit's turns across Redis. That mode runs the same
cases under the same names, so its receipt's command must set
`ROOMKIT_TEST_TURN_BACKEND=redis`, no other receipt's command may, and a
command whose turn mode cannot be read from its words is refused. A scenario
with several cases in the report (a PostgreSQL slow-preparation variant) takes
the worst of their outcomes. `conformance/record.py` writes receipts from a
JUnit report; none is written by hand (see the
[executions README](executions/README.md)).

Rust receipts come from roomkit-rs's result files (format `cargo_junit`), one
receipt per pass: a backend, `memory`, `sqlite` or `postgres`, and a tokio
runtime, `current_thread` (one thread) or `multi_thread_4` (four workers, run
on memory only). The runner writes one case per scenario, named by its id,
under the class `conformance.<backend>.<runtime>`, so the report names its
pass and the command is not read. A receipt holds the whole pass, every
scenario of the copy with the scenarios the runner sets apart as skipped. The
copy is roomkit-rs `conformance/scenarios`, synced from the corpus at its
`conformance/SPECS_COMMIT`. The report also names the commit the run was at,
which must be the checkout's, clean, when it is recorded. From a clean
roomkit-rs commit on main:

```sh
ROOMKIT_CONFORMANCE_JUNIT=target/conformance cargo test -p roomkit --test conformance
python conformance/record.py rust --rust-repo ../roomkit-rs \
  --junit ../roomkit-rs/target/conformance/memory-current_thread.xml \
  -- env ROOMKIT_CONFORMANCE_JUNIT=target/conformance cargo test -p roomkit --test conformance
```

roomkit-rs runs the scenarios with `setup.executors` only across its Redis
turn executor, when `REDIS_URL` names a Redis server; the passes above skip
them. A pass that runs them is a backend of its own, `memory+redis-executors`,
`sqlite+redis-executors` or `postgres+redis-executors`, on its store's
runtimes. From roomkit-rs `773311efae440c2b2b88a37674cfc34396b1b014` on, its
class names it (`conformance.memory+redis-executors.current_thread`): a plain
report is never recorded under that backend, nor such a report under the plain
one. An earlier runner gave that pass the plain class (see the
[executions README](executions/README.md), "Recording receipts"). Only the
scenarios with executors cross Redis in that pass;
every other scenario runs in process, as in the plain pass. Python's
`+redis-turns`, whose every turn crosses Redis, is another mode, hence another
name. The receipt and its file write `+` as `-`:
`rust-<commit>-memory-redis-executors-current-thread`.

```sh
REDIS_URL=redis://127.0.0.1:6379 ROOMKIT_CONFORMANCE_JUNIT=target/conformance \
  cargo test -p roomkit --features redis --test conformance
python conformance/record.py rust --rust-repo ../roomkit-rs \
  --junit ../roomkit-rs/target/conformance/memory+redis-executors-current_thread.xml \
  -- env REDIS_URL=redis://127.0.0.1:6379 ROOMKIT_CONFORMANCE_JUNIT=target/conformance \
     cargo test -p roomkit --features redis --test conformance
```

Rust's aggregate cargo summary (format `cargo`) stays refused: memory and
SQLite emit the same summary, and equal scenario counts do not identify the
executed IDs. Other backends and specialized test executions remain
unrecorded.


`recorded_pass` applies only to the named scope, revision, backend and runtime.
Missing cases, skips, failures, stale inputs and source-only specialized tests
never become passes. Separate partial runs are never combined into one complete
execution. An absent receipt means **not recorded**, not failed or verified.
The hooks pilot and static access/mute matrices have partial mappings and
Python memory receipts. The specialized wrong-payload test remains source-only.
Historical runs are not silently relabeled as current results.
A receipt may name a scenario renamed or removed since its run: its results
are read at its corpus commit, and only a link has to name a current scenario.
