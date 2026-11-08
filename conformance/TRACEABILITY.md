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

Add `--update-traceability` only to regenerate the three derived artifacts.
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

## Execution receipts

Every receipt names implementation, RFC and corpus commits, backend, runtime,
command, selected scenario IDs and their hashes. Keep runner output under
`conformance/executions/` and fingerprint it. Commands are recorded, never run
by the checker. A receipt is a reviewed record of a run, not a signed attestation
that the working tree was clean; the author must run the exact clean commits.

The checker validates the saved output, actual commit contents and the corpus
copied into the implementation. Supported profiles are Python JUnit on memory
or SQLite with `asyncio`. Rust's aggregate cargo summary is deliberately
refused: memory and SQLite emit the same summary, and equal scenario counts do
not identify the executed IDs. Retain such runs separately; they cannot create a
`recorded_pass` here until a runner format identifies backend and cases. Other
backends and specialized test executions also remain unrecorded.


`recorded_pass` applies only to the named scope, revision, backend and runtime.
Missing cases, skips, failures, stale inputs and source-only specialized tests
never become passes. Separate partial runs are never combined into one complete
execution. An absent receipt means **not recorded**, not failed or verified.
The initial pilot deliberately has partial mappings and no execution receipts;
historical runs are not silently relabeled as current results.
