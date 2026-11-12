# Durable LLM usage history

Status: **Draft 1 — for discussion; not normative or implemented.**

This proposal defines the framework work needed for an application to show local
usage statistics across conversations. Python and Rust would expose the same
contract. It does not add a slash command or change the current RFC.

The recommendations below are candidates for review. In particular, recording
policy, storage failure behavior and retention need agreement before code lands.
The RFC amendment follows executable evidence from both implementations.

## 1. Outcome and scope

An integrator can answer: which models consumed tokens, in which conversations,
over a time range, including delegated work and model calls used for compaction?
The answer survives a restart, distinguishes known usage from missing reports,
and never counts a replayed report twice.

The initial scope is calls to conversational AI providers made through RoomKit's
instrumented generation path, both streamed and buffered. It includes fallback
providers, retries visible to the framework, and built-in memory summarization.
A host using a custom summarizer needs the same recording path and explicit
room attribution; arbitrary calls outside that path cannot be discovered.

Excluded: provider account quotas, credits, invoices, subscription allowances,
STT/TTS, realtime voice, standalone image generation, and monetary charges for
tools. ACP cumulative observations remain governed by Appendix A.9: neither
session costs nor context occupancy become per-call usage by inference.

The framework owns records, normalized counters, scoped queries and optional
price estimates. Applications own project identities, cross-database queries,
calendar/timezone choices and presentation. A terminal toolkit renders the
results without owning the accounting rules.

## 2. Existing contract and baseline

The RFC currently specifies:

| Contract | Consequence for this proposal |
|---|---|
| §6.4 **The turn's record** (`RK-6.4-033`) | A turn retains summed usage and the last generation's usage/model/provider. This is not a record of each model's contribution. |
| §6.4 **What a generation used** (`RK-6.4-034`) | `UsageMarker` is ephemeral and is never stored. Keep that stream contract; introduce a separate durable record. |
| §6.7 **Usage counters** (`RK-6.7-005`) | Input, cache reads, cache writes and output are disjoint; reasoning is a subset of output. Preserve this normalization. |
| §6.4 **A turn's budget** (`RK-6.4-031`) | Budget pricing uses each response separately at the rate of the provider the turn started on, including later handovers. Historical estimates must not silently change that budget policy. |
| Appendix A.9, ACP usage observations | Cumulative cost, context occupancy and per-prompt consumption have different scopes; none is converted to another implicitly. |

See the [current RFC](../roomkit-rfc.md) and the existing
[turn-record scenarios](../conformance/scenarios/turn-record/).

Baseline execution receipts are recorded in section 12. They test the existing
turn record, not this proposed storage API. Future scenarios in section 10 are
acceptance criteria, not claims of current support.

## 3. Accounting unit and attribution

One `UsageRecord` represents one provider invocation observable by the framework.
A logical generation can make several invocations: each retry or fallback gets
its own identity. Tool calls and stream chunks are not provider invocations.
Retries inside an opaque SDK cannot be counted separately without an adapter
exposing them; the report makes no claim to reconstruct the vendor's invoice.

A record belongs to its actual room and agent channel. An optional turn identity
associates it with a turn; a manual compaction outside a turn has none. Its purpose
is `generation` or `compaction`. Delegation is a relationship between existing
tasks/rooms, not a second copy of the worker's usage.

For example, a parent makes two calls, its child makes three, and a summarizer
makes one. An inclusive view sums six distinct records. It never adds the
parent's inclusive total to the child's total again. A cached summary reused
without a model invocation creates no usage record.

Model attribution uses the response's model when supplied, otherwise the
configured model, with the source of that identity recorded. A fallback names
its own provider/model. Editing an agent or deleting its profile does not
rewrite historical attribution. Requested and effective models remain distinct.

## 4. Candidate record

Names are provisional until the shared public API is agreed. Identifiers and
timestamps come from the framework's existing environment facilities.

| Field | Proposed meaning |
|---|---|
| `id` | Stable opaque invocation identity, generated before dispatch. |
| `operation_id`, `attempt` | The logical generation and its invocation number; retries of persistence retain both, retries of the provider increment the attempt. |
| `organization_id`, `room_id` | The room's tenant and identity, captured by trusted framework code. |
| `channel_id`, `turn_id` | The agent responsible; nullable turn identity for work outside a turn. |
| `purpose` | `generation` or `compaction`. |
| `connection_id` | Optional opaque host-supplied connection identity; never credentials, an email or an endpoint URL. |
| `provider`, `requested_model`, `model`, `model_source` | Provider identity, requested model, effective model when known, and `reported` or `configured` origin. |
| `started_at`, `finished_at` | UTC timestamps; unfinished records have no finish time. |
| `outcome` | `pending`, `succeeded`, `failed`, `cancelled` or `unknown`. Outcome does not determine whether usage was reported. |
| `usage`, `usage_status` | Normalized numeric counters and `complete`, `partial` or `unreported`. |
| `pricing`, `estimated_cost` | Optional immutable price snapshot/provenance and estimate, with currency and pricing coverage. |

A report may be complete despite the invocation failing after reporting usage.
A successful answer with no counters is unreported, not free. A recovered
unfinished invocation has unknown outcome and incomplete usage, retaining any
counters already stored; do not label it cancelled or successful just because
its process disappeared.
`unknown` is unresolved, not terminal: an authoritative late report may finalize
it. Recovery cannot demote a final record. A final record is immutable; a repeated
identical finalization succeeds, while a different finalization is a conflict.

The first version admits the existing conversational counters: `input_tokens`,
`output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and
optional `reasoning_tokens`. Missing required input/output counters stay absent;
an explicit zero remains zero. The RFC's normalized omission of zero cache
counters remains valid. Unknown vendor fields are not added to token totals.
Inputs billed through a conversational multimodal request retain the provider's
normalized counts; this proposal does not infer a text/image split.

```text
total_input = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
total_tokens = total_input + output_tokens
reasoning_tokens is already inside output_tokens
```

Known counters can be summed even when a required counter is missing, but the
result remains partial. The same rule applies to aggregates: missing values are
not presented as measured zeroes. Context occupancy remains a separate measure;
summing requests measures consumption, not the size of the current context.

## 5. Recording and recovery

Recommended lifecycle, subject to decision D2:

1. When recording is enabled, persist a pending record before invoking the
   provider. Attach its stable identity to the execution context.
2. Record normalized usage as the provider supplies a usable report. A provider
   adapter folds cumulative stream updates into a replacement snapshot for this
   invocation; it does not add each snapshot to the previous one.
3. Finalize the outcome and available counters once the invocation ends. This
   works independently of whether it wrote an assistant message.
4. On replay, perform an idempotent write of the same record. Identical repeated
   finalizations are no-ops; conflicting identities or terminal contents are
   rejected. Updates are monotonic and cannot replace a final record with a
   pending one.
5. After restart, unresolved records remain visible as unknown/partial. An
   authoritative completion may resolve one under the same identity. Recovery
   never reissues a provider request solely to obtain its missing usage.

A persistence retry reuses an identity; an actual new provider invocation does
not, even if its prompt or response is identical. Concurrent writers need
store-level uniqueness and atomic transitions, not a read-then-write check.
Executor/owner transports carry the same invocation identity and authoritative
update order; the storage owner rejects stale updates. Neither stream readers
nor independent transport subscribers create additional records.
The initial scope does not turn each SDK network retry into a record. Adapters
must identify whether a report is an invocation total or a logical-operation
total; an operation total covering several attempts cannot be added to each
attempt's counts. An adapter unable to separate them reports that limitation
instead of claiming complete per-attempt accounting.

Pending records are not evidence that the provider actually received a request:
a crash can occur between the durable start and network dispatch. They expose
uncertainty rather than inventing consumption. Exactly-once local persistence
does not imply exactly-once external execution or complete vendor billing data.

Recommended failure behavior while recording is enabled: refuse a new invocation
if its pending record cannot be saved; do not contact the model first. If saving
a result fails after the call, retain the generated answer, report a diagnostic,
retry only persistence within a bounded policy, and leave the durable pending
record incomplete if recovery fails. A usage-storage error never triggers a
model retry. This availability trade-off is explicitly open in D2.

## 6. Pricing

Token measurements are primary. A cost is an optional estimate at stated rates,
not an invoice, account spend, or remaining subscription allowance.

Resolve rates for the effective provider/model, preserving the rate values,
currency, source and verification date used. If a response identifies a model
for which no matching rates are available, keep the tokens and omit its estimate;
do not silently price it as the requested model. Custom endpoints need an
explicit host price or a matching trusted catalogue entry.

Price each invocation separately, using its own input to select a long-context
tier. Capture the estimate and tariff snapshot so later catalogue changes do not
reprice history. Missing rates for a nonzero billed counter leave pricing partial;
a documented free rate is zero. Zero and unknown cost are different.

Use an integer monetary representation with an explicitly declared precision
and deterministic rounding shared by Python and Rust. The initial recommendation
is millionths of the currency, rounding each invocation once, half up. Aggregates
sum those stored amounts and keep currencies separate; no exchange rate is inferred.

This estimator is independent of the existing turn-budget policy. In particular,
reporting the fallback's actual tariff does not change which tariff stops a turn
under §6.4. Any future budget-policy change needs its own decision and tests.

For subscriptions, an application may display token usage and an optional
clearly labelled API-price equivalent. It must not display that equivalent as a
subscription charge. Account quota integration is outside this proposal.

## 7. Storage and public reads

Recommendation D1: recording is an opt-in framework capability, off by default;
an application offering persistent statistics enables it explicitly. Unsupported
stores reject enablement clearly. Existing custom stores keep working with
recording disabled. The built-in memory, SQLite and PostgreSQL stores implement
the same behavior; only persistent stores promise survival across restarts.

Records live outside the transcript: they are not `RoomEvent`s, consume no event
index, enter no model history, trigger no conversation response and are not
discarded by context compaction. Keep them with their owning store so room/tenant
deletion and authorization can be enforced coherently. An additional independent
analytics database is not required by the framework contract.

Candidate public surface, expressed without language-specific signatures:

| Operation | Proposed result |
|---|---|
| `list_usage(query, cursor, limit)` | A bounded page of records and an opaque continuation cursor. |
| `summarize_usage(query, group_by)` | Counts, token totals, cost subtotals by currency, coverage and requested groups. |
| `delete_usage(query)` | Explicit administrative deletion within a verified tenant/room scope; returns the number removed. |

The internal store contract additionally needs atomic begin, update/finalize and
recovery operations. Final method names and signatures must be shared by Python
and Rust; a default implementation must not silently discard requested records.

Queries require an explicit, bounded set of room IDs and the same organization
scope as existing framework reads. An empty room set means empty, never all
tenants. The host resolves which rooms its user may inspect; these are host
APIs, not automatically available model tools. Supplying a filter never grants
access to a room, and grouping must not expose unauthorized identifiers.

Filters: UTC `started_at` range `[from, until)`, channel, turn, purpose, provider,
effective model and opaque connection ID. Groups: room, channel, provider/model,
purpose, connection and UTC day. Applications translate local calendar dates to
UTC ranges; non-UTC daily charts can group paged records locally in this version.
One invocation belongs to its start date, including one that crosses midnight.

The store assigns a stable sequence at creation. Pagination uses that sequence
and a captured upper bound, preventing new starts from shifting pages. Pending
records may finish between pages; a paged read is not a historical snapshot.
A summary uses one consistent store read and returns `observed_at`. Applications
refresh summaries rather than presenting separately fetched pages as atomic.

A summary returns record/known/unreported/pending counts, per-counter known sums,
unpriced/partially priced counts and separate currency subtotals. It reports
recording intervals and known retention gaps, so an empty result before
enablement cannot mean zero historical usage. Completeness describes recorded,
instrumented work only, never a provider account or calls outside RoomKit.

## 8. Privacy, deletion and historical data

Persist only identities, timestamps, numeric measures and tariff information.
Do not store prompts, responses, reasoning text, tool arguments/results, raw
provider payloads, credentials, URLs or filesystem paths in these records.
Reads and writes enforce tenant ownership; a late completion cannot resurrect
records after a room was deleted. Deleting a conversation's text alone does not
delete its usage; deleting the room deletes its usage too.

Recommendation D3: retain records while their room exists, with explicit scoped
deletion and an optional host retention policy. A recording-coverage marker keeps
the purge scope and time range without the deleted per-call identities. A room
deletion removes its coverage markers too. The first
version retains no hidden monetary totals after explicit usage deletion.

Do not fabricate per-call history from old `ai_usage` totals. A consumer may show
legacy turn totals separately, labelled as legacy with limited attribution.
For a given turn it uses either the legacy total or the new invocation records,
never both. Enabling recording takes effect for new turns; a turn already running
stays on its old policy, and auxiliary invocations capture the policy at start.
Compactions absent from historical measurements remain unknown, not backfilled.

Applications map rooms to projects outside the framework, combine authorized
results from their own stores, and label cross-project figures as local history.
Conversation, turn and provider-call counts remain distinct metrics. An
application enumerates existing rooms/turns for the first two; this record does
not redefine a conversation as one provider invocation.

## 9. Decisions to review

| ID | Recommendation in this draft | Alternative and consequence |
|---|---|---|
| D1 | Opt-in recording; built-in stores implement it; existing stores can explicitly report unsupported. | Enable by default, requiring an agreed storage/migration cost for all integrations. |
| D2 | Durable pending record before a paid invocation; a failed begin prevents dispatch. | Best-effort recording preserves availability but can lose even the evidence of a missing call after a crash; completeness must be weaker. |
| D3 | Room lifetime retention, cascading room deletion, explicit scoped purge. | Independent accounting retention requires a separate privacy and authorization contract. |
| D4 | Immutable per-invocation price estimates, including effective fallback rates, separate from budgets. | Tokens only in the framework and host-owned pricing reduce the first lot, but clients must share an estimator to agree. |
| D5 | New records plus a separately labelled legacy view; no inferred per-call backfill. | Migrate turn aggregates as another record kind, requiring mixed-granularity exclusion rules in every query. |

These are proposed defaults for discussion, not approvals to change runtime
behavior. No provider quota or billing endpoint is needed to resolve them.

## 10. Proposed conformance scenarios

These scenarios will require explicit runner/schema support. Do not add invented
calls to the active suite or credit them as coverage before that support exists.

| ID | Observable acceptance criterion |
|---|---|
| U01 | Two generations produce two records; their token sum agrees with the existing complete turn total. Streamed and buffered delivery agree. |
| U02 | Primary, retry and fallback invocations keep distinct identities and actual model attribution, including different models within one turn. |
| U03 | Repeated stream snapshots, duplicate finalizations and replay after restart count each invocation once; conflicting updates are refused. |
| U04 | A successful response without counters stays unreported; a missing required counter stays partial; explicit zero remains a measured zero. |
| U05 | Cache reads/writes are counted once, and reasoning is not added to output a second time. |
| U06 | Cancellation or a crash leaves previous reports intact and an unresolved invocation visible; recovery performs no model call. |
| U07 | Failed invocations with usable reported counters retain them; reported usage does not imply a successful answer. |
| U08 | Automatic and manual compaction calls are attributed and counted; a reused cached summary adds none. |
| U09 | A child room's usage appears once in an explicitly inclusive query; nested delegation does not duplicate descendants. |
| U10 | Each invocation applies its own tariff and long-context tier; a fallback uses its own estimate while budget behavior is unchanged. |
| U11 | Missing prices, partial rates and mixed currencies remain explicit; changing catalogue rates does not rewrite history; monetary rounding agrees. |
| U12 | Restart and query pagination preserve identities; concurrent starts/finalizations neither duplicate records nor restore stale states. |
| U13 | A failed begin dispatches no provider request under D2; a failed finalize preserves the answer and visible uncertainty, with no provider retry. |
| U14 | Tenant/room isolation holds for raw records, grouped queries and deletion; a late result cannot recreate a deleted room's records. |
| U15 | UTC range boundaries, equal timestamps, start-day assignment and filters give the same results in every supported store. |
| U16 | Disabled/unsupported recording and pre-enablement ranges cannot masquerade as measured zero use; purge retains an explicit coverage gap. |
| U17 | Existing turn totals and ephemeral `UsageMarker` delivery remain compatible; usage records appear in neither transcripts nor model prompts. |
| U18 | Legacy totals and invocation records never overlap in a consumer's total; switching recording on during a turn keeps that turn on one policy. |
| U19 | Executor/owner replay retains invocation identity and rejects stale writes; an unrelated worker cannot finalize another worker's record. |

All scenarios use scripted providers, deterministic clocks and controlled
failures. Run the same behavioral fixtures against Python and Rust, memory and
SQLite, then PostgreSQL and the applicable executor/owner path. A capability not
yet supported is reported explicitly, not counted as a passing scenario.

## 11. Implementation and RFC amendment sequence

1. Review this proposal and settle D1–D5, especially the availability trade-off.
2. Add the shared scenario vocabulary and acceptance fixtures as the behavior
   becomes executable; prove the Python public API, then its Rust counterpart.
   Include a runnable example which records work, closes the kit, reopens its
   persistent store and queries the same usage.
3. Amend the RFC from those proofs: §6.4 (recording lifecycle and unchanged turn
   records/budgets), §6.7 (measurement/pricing types), §10.6 (executor transport),
   §14 (storage and consistency), §20 (summary attribution), and §26 (capability
   coverage). Update public API parity, documentation and migration guidance.
4. Integrate the API into the application's local statistics service and the
   terminal display. Provider account usage remains a separate later feature.

The amendment should keep `UsageMarker` ephemeral and specify the durable record
separately. The existing RFC, requirement annotations and conformance evidence
remain unchanged while this document is a draft.

## 12. Baseline verification

Baseline date: 2026-11-11. Source revisions inspected:

- Original specs draft base: `2ca4f4d78d7875a28e35e6ea38a9a495f124ab43` (fetched `origin/main` on the baseline date).
- Python: `9ae6ef70ed9ae8086c64f9594cc50c15fead80f2` (local `origin/main`).
- Rust: `d4ab64bdb16d1f04aaa0a4fa67c59b4bf4f0e7e1` (local `main`).

Executed baseline checks:

| Implementation | Command | Result |
|---|---|---|
| Python | `uv run --no-sync pytest tests/conformance/test_conformance.py -k turn-record -q` | 33 passed; 2219 deselected: the 31 turn-record scenarios plus two matching task/discussion scenarios. |
| Rust | `ROOMKIT_CONFORMANCE_FILTER=turn-record/ cargo test --locked -p roomkit --test conformance every_scenario_gives_what_the_rfc_says -- --exact --nocapture` | 31 scenarios selected, 0 failing; test passed. |

The 31 turn-record fixtures are byte-identical in the original draft's base and
both implementation copies. Python pins specs `2ca4f4d78d7875a28e35e6ea38a9a495f124ab43`;
Rust pins `888957821fef0e63a191dc6686c97bbc27868a83`. The broader suites need not
be identical for this selected comparison.

The specs checker also passed with `--strict --traceability`, the inspected
Python checkout and the original draft base revision: 1,858 scenario documents
validated, including their registered evidence. This validates the corpus and traceability;
it does not execute all those scenarios.

These checks establish the baseline for reported totals, last-generation
attribution and incomplete reports. They do not prove restart durability for a
per-invocation record: that is proposed work, tested by U03, U06 and U12.

Review refresh, 2026-11-16: the proposal branch was rebased onto specs
`771ff92185c21b5752be8af18d6e300f2f1324bf`. The four annotated contracts cited in
section 2 are textually unchanged from the original baseline. The Python and Rust
test results above remain dated baseline evidence, not executions of this newer
specs revision. Decisions D1–D5 remain open.
The refreshed branch passed `check.py --strict --traceability` against that base
and the Python source repository: 2,464 scenario documents validated. This is
corpus validation, not a new execution of the Python or Rust behavior tests.
