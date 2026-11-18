# Requirement traceability

The RFC is normative. `requirements.json` is generated from its annotations;
`evidence.json` contains reviewed links, never replacement rules.
`coverage.md` and `coverage.json` keep inventory, mappings and executions separate.
They do not certify a conformance level or calculate a percentage of compliance.

## Check and regenerate

Use Python 3.12+ with the checker's existing `jsonschema` dependency. A local
clone of roomkit must contain the full `python_commit` from `evidence.json`.

```sh
python conformance/check.py --strict --traceability --python-repo ../roomkit
python -m unittest discover -s conformance/tests -v
```

Add `--update-traceability` only to regenerate the derived artifacts
(`requirements.json`, `coverage.json`, `coverage.md` and the pages of `rules/`).
This never updates review records or proof fingerprints. `--base-ref <full SHA>`
checks ID removals and retirement history against a previous specs commit.
The historical `--strict` check still uses `RFC_COMMIT`; traceability uses the
current RFC file by default. Neither repins the other.

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
"requirements": ["RK-10.4-003"]
```

The checker refuses an ID that names no unit of the current RFC, a retired ID
(cite the units that replace it) and a `non_testable` unit. A citation says the
scenario tests the unit; it is not a reviewed link, and a scenario can cite a
unit it covers only in part.

### Level

The reviewer of a unit sets its level in the annotation, whatever its keywords:

```markdown
<!-- rfc: {"id":"RK-10.4-003","kind":"behavior","applies":"Inbound routing","level":"must"} -->
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
    "RK-10.4-003": {
      "routing/a-message-from-an-unknown-address-opens-a-room": "5f0c…"
    }
  }
}
```

The lock lives here only: the implementations' copies never hold it, so a
change to the RFC changes no scenario and needs no sync. `check.py` prints a
`lock:` line, which fails `--strict`, when:

- a cited unit's text, kind or applicability changed since a scenario read it:
  `RK-10.4-003 changed since routing/x read it: reread it, then run python3
  conformance/check.py --pin RK-10.4-003`;
- a citation has no entry: `routing/x cites RK-10.4-003 with no lock entry:
  once it is read against them, run python3 conformance/check.py --pin
  routing/x`;
- an entry has no citation: `links.lock.json pins routing/x to RK-10.4-004,
  which it does not cite: run python3 conformance/check.py --pin routing/x`.

### Re-pinning

Reread the scenario against the unit's new text, fix it if it no longer tests
what the unit says, then pin by name:

```sh
python3 conformance/check.py --pin RK-10.4-003            # every citation of this unit
python3 conformance/check.py --pin routing/x routing/y    # every citation of these scenarios
```

A pin records the named units' or scenarios' citations at the current text,
drops their entries that no citation holds any more, and moves nothing else.
It needs at least one name, and pins nothing while a citation is wrong.

### The process rule

`check.py --changed-units --base-ref <full sha>` reads the units added since
that commit, or whose text, kind, applicability or level changed:

- `must`: a scenario cites it, or `untested.json` gives the reason none does;
  otherwise an error;
- `should`: without either, a warning;
- `may`: nothing;
- no level: listed as unreviewed, never blocking.

A `non_testable` unit is exempt: its kind is its reason. CI does not run the
rule yet.

```text
$ python3 conformance/check.py --changed-units --base-ref 2f35a764a425fe69453e22bdba378482673c7e34
error: RK-10.4-008 (must, added since 2f35a764a425): no scenario cites it and untested.json gives no reason
```

`untested.json` maps a current unit to its reason; a unit scenarios cite cannot
keep an entry (`--strict` says so):

```json
{
  "version": 1,
  "units": {
    "RK-10.4-008": "Needs a carrier's number lookup, which no runner reaches."
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
| RK-10.4-003 | behavior | must | `routing/x` | pinned | memory passed, sqlite passed |  |
```

An outcome counts when its receipt ran the scenario's current text (the same
hash), whatever its RFC commit. Receipts are appended as they are recorded, so
the last one listed is the latest. Rust's column stays empty until its runner
writes receipts.

## Reviewed links

Each link pins the clause, a JSON pointer into an actual expectation, and the
whole scenario. A setup change invalidates its review even when the expected
value remains the same. `scope`, `proves`, `review` and `missing` describe what
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
copied into the implementation. Supported profiles are Python JUnit with
`asyncio`, one backend per receipt: `memory` and `sqlite` (cases of
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

Rust's aggregate cargo summary is deliberately refused: memory and SQLite emit
the same summary, and equal scenario counts do not identify the executed IDs.
Retain such runs separately; they cannot create a `recorded_pass` here until a
runner format identifies backend and cases. Other backends and specialized test
executions also remain unrecorded.


`recorded_pass` applies only to the named scope, revision, backend and runtime.
Missing cases, skips, failures, stale inputs and source-only specialized tests
never become passes. Separate partial runs are never combined into one complete
execution. An absent receipt means **not recorded**, not failed or verified.
The hooks pilot and static access/mute matrices have partial mappings and
Python memory receipts. The specialized wrong-payload test remains source-only;
Rust execution is not recorded here.
Historical runs are not silently relabeled as current results.
A receipt may name a scenario renamed or removed since its run: its results
are read at its corpus commit, and only a link has to name a current scenario.
