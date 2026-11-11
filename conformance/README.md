# The RoomKit conformance suite

Scenarios that every implementation of RoomKit runs, as the executable form of
the RFC's rules. A scenario is data, written in the RFC's serialized form (§1.4
names "conformance fixtures" among what that form is for): a setup, the kit's
calls, and what the RFC says they come to. Each implementation has a runner
that reads the scenarios and runs them on its own core; the suite says nothing
of either implementation's API.

Coverage is tracked in the [generated report](coverage.md). It distinguishes
source inventory, reviewed assertion links and versioned execution receipts;
a passing scenario suite alone certifies no conformance level.

## Layout

| Path | What it is |
|---|---|
| `scenarios/<area>/<name>.json` | One scenario; its `id` is `<area>/<name>` |
| `scenario.schema.json` | The JSON Schema every scenario validates against |
| `check.py` | The checker (below) |
| `requirements.json`, `coverage.json`, `coverage.md` | Generated inventory and evidence report |
| `evidence.json`, `inventory.json` | Reviewed links, execution receipts and source inventory reviews |
| `TRACEABILITY.md` | Update and review procedure |
| `RFC_COMMIT` | The roomkit-specs commit whose `roomkit-rfc.md` the scenarios' `rules` are checked against |

An implementation keeps a copy of `scenarios/`, taken from one commit of this
repository's `origin/main` by its `make conformance-sync`, which records that
commit beside the copy (`SPECS_COMMIT`) and the copy's fingerprint
(`SCENARIOS_SHA256`: `sha256sum` over `sha256sum` of each file of `scenarios/`,
by path in byte order). The runner's suite checks the fingerprint, so a copy
edited or synced in part fails. The copy is never edited there: change the
scenarios here, push them, fetch, and sync again. The target finds this
repository beside the implementation's main checkout, from a worktree too
(`SPECS_DIR`), takes `origin/main` by default (`SPECS_REF`), and refuses a commit
`origin/main` does not hold unless `ALLOW_UNPUSHED=1`, for a copy that is synced
again before it is pushed. Each implementation's `make all` runs
`conformance-check` first, which fails while the copy's commit is not on
`origin/main` (a warning under `ALLOW_UNPUSHED=1`), and is skipped where no
roomkit-specs checkout sits beside it, as in CI.

| Implementation | Copy | Runner | Run it |
|---|---|---|---|
| roomkit (Python) | `tests/conformance/scenarios` | `tests/conformance/` | `uv run pytest tests/conformance` |
| roomkit-rs (tokio runtime) | `conformance/scenarios` | `crates/roomkit/tests/conformance/` | `cargo test -p roomkit --test conformance` |

## The checker

```
python3 conformance/check.py            # check; exit 1 on an error
python3 conformance/check.py --fix      # rewrite each file in the suite's layout first
python3 conformance/check.py --rfc roomkit-rfc.md   # resolve the rules against a file
python3 conformance/check.py --strict   # coverage gaps are errors too
```

It needs `jsonschema`. For each scenario it checks that:

- it validates against `scenario.schema.json`, its `id` names its path, and it
  is written in the suite's one layout (`json.dumps(indent=2,
  ensure_ascii=False)` and a newline);
- each entry of its `rules` resolves in `roomkit-rfc.md` at `RFC_COMMIT`:
  - `§10.1`, `Appendix B.2`: a heading;
  - `§10.1 step 9`, `§10.1 step 5a`, `§10.2 step 3c`: a step of the section's
    pipeline, `3c` being step 3's item `c.`;
  - `§7.5 rule 2`: the numbered item of the section's prose, which must be
    the only one so numbered;
  - `§9.5.1 Reentrance`, `§10.3 Validation rule 4`: a paragraph that opens
    with that bold label, and the numbered item after it.

It then lists, as gaps, what of the §26.1 trigger and framework-event table no
scenario asserts. A trigger is asserted by a scenario that expects calls of a
hook on it, a framework event by one that expects it; a row is credited only
by the scenarios that cite one of the places it names (`§10.1 steps 10, 11 and
15`: a scenario citing `§10.1 step 11`; `(§7.2)`: one citing §7.2), and each of
those places must be cited by a scenario that asserts one of the row's names. A
row that names no place is credited by any scenario. It also lists the
reentrancy cells no scenario names. A label resolves only as the whole bold
label of its paragraph, never as a prefix of one. A change to the RFC that moves a rule fails the check
until `RFC_COMMIT` and the scenarios follow it.

## A scenario

```json
{
  "$schema": "../../scenario.schema.json",
  "id": "rooms/closed-room-refuses-a-message",
  "title": "A closed room refuses a message with room_closed, stores nothing, and says so",
  "rules": ["§5.1", "§10.1 step 6", "§8.2", "§26.1"],
  "setup": {
    "channels": [
      { "id": "sms", "type": "sms", "category": "transport" },
      { "id": "ws", "type": "websocket", "category": "transport" }
    ],
    "rooms": [{ "id": "room-1", "bindings": [{ "channel_id": "sms" }, { "channel_id": "ws" }] }],
    "hooks": [{ "name": "closed", "trigger": "on_room_closed", "execution": "async" }]
  },
  "steps": [
    { "call": "close_room", "room_id": "room-1", "expect": { "result": { "status": "closed" } } },
    {
      "call": "process_inbound",
      "room_id": "room-1",
      "message": { "channel_id": "sms", "sender_id": "+15551234567", "content": { "type": "text", "body": "Hello?" } },
      "expect": { "result": { "blocked": true, "reason": "room_closed", "event": null } }
    }
  ],
  "expect": {
    "timeline": { "room-1": [] },
    "deliveries": { "room-1": { "ws": [] } },
    "hooks": { "closed": [{ "trigger": "on_room_closed", "room_id": "room-1" }] },
    "framework_events": {
      "room-1": [
        { "event": "room_closed", "reason": { "$absent": true } },
        { "event": "room_refused_event", "status": "closed", "operation": "inbound", "event_type": "message" }
      ]
    }
  }
}
```

A runner makes the setup, starts recording, runs the steps in order, waits until
the kit runs nothing more in the background, reads the store, and matches what
it recorded against `expect` and each step's `expect`. Any mismatch fails the
scenario. `notes` says in prose what the scenario relies on when the RFC's text
alone does not make it plain.

### Setup

Made before anything is recorded: framework events, hook calls, deliveries and
room callbacks of the setup are not compared.

- `kit`: `max_chain_depth` (default 5), `process_timeout_ms` (the
  implementation's default when absent), and `router`, a scripted router in
  place of the default one, answering every routed message with its
  `room_id`, an answer the kit holds to §10.1 step 2's rules, held first at
  its `gate` when it names one; calls are recorded before that gate under
  `router_calls`; for identity
  resolution (§11), `identity_resolver`, a **scripted resolver** (below),
  `identity_channel_types`, the channel types it runs for (§11.4, every type
  when absent), and `identity_timeout_ms` (§11.5, the implementation's
  default when absent); and `delivery_backend`, the in-memory delivery
  backend (§22.2) the kit is built and started with, its `retry_delay_ms`,
  `max_retry_delay_ms`, `max_queue_size` and `max_dead_letter_size`: a
  runner's idle wait then waits for its queue, its items waiting out a
  retry and those its worker holds; and `verification_policy`, the kit's
  identity verification policy (§11.7) the kit is built with: `ttl_ms`,
  `request_ttl_ms`, `code_request_ttl_ms`, `max_attempts`, `code_length`,
  `release_on_verify`, `release_max_messages`, `release_max_age_ms` and
  `hold_unverified`, the implementation's default for each member absent;
  for an author's media (§6.4), serving every AI channel registered on the
  kit, `media_resolver`, the kit's media resolver, answering each reference
  its `media` names with those bytes (written in base64) and any other with
  none, whatever the room, and recording each call under `media_resolver`
  (the media's `url`, the `room_id` of the turn), and `attached_media`, the
  kit's attached-media reader, naming as an event's media the media
  contents (in the serialized form) its metadata lists under `key`; and
  `orchestration`, the id of a scripted strategy (below) the kit is built
  with as its default, which every room it creates takes unless the
  creation names another or none (§19.7); and for the room lock (§13.5),
  `lock_manager`, the in-memory lock manager whose release fails with its
  `release_error` while a `lock_releases` step has set it failing, as a
  distributed lock that finds its lease expired, and
  `delivery_gap_timeout_ms`, how long a delivery lane waits on a cursor hole
  no lane runs before it skips it (the implementation's default when
  absent); and `inbound_rate_limit`, the kit's inbound rate limit
  (`max_per_second`, `max_per_minute`, `max_per_hour`): a bucket of tokens
  per channel, full at first and holding at least one, refilled at the most
  precise bound's rate, a message past it refused before anything is read
  or written; and `persistence_policy`, the kit's persistence policy
  (`persist_types`, `exclude_types`, each a list of event types): what the
  kit's commits store, every type when absent, `exclude_types` winning over
  `persist_types`.
- `channels`: each is registered. A channel of type `host` is the
  implementation's host channel (§10.5); any other is a **scripted channel**:
  - `id`, `type` (a ChannelType: `sms`, `websocket`, `whatsapp`, `email`,
    `ai`...), `category` (default `intelligence` for `ai`, else
    `transport`), `direction` (default `bidirectional`), `capabilities` (a
    ChannelCapabilities; a reader's default for the absent members, text
    only), `recipient_key` (default null: the channel delivers to a
    destination of its own and needs no recipient, §10.2 step 3d);
  - its parse builds the event the way a transport does: the message's type,
    content, metadata and idempotency key, and the source `{channel_id,
    channel_type, direction: inbound, participant_id: sender_id,
    external_id, raw_payload, provider_message_id}`; the pipeline writes the
    rest;
  - its delivery succeeds, and its turn (`on_event` of an intelligence
    channel) answers nothing;
  - `parse`, `deliver` and `on_event` hold its **reactions** (below);
  - `on_room_attached` and `on_room_detached` hold the reactions of its
    room callbacks (§6.1): it records each call under `room_callbacks`, and
    in `hook_order` as `<id>.on_room_attached` or `<id>.on_room_detached`,
    then reacts (`gate`, `do`, `fail`); with no reaction it does nothing;
  - with `streams`, it takes a streamed response as it is written (§6.1
    `supports_streaming_delivery`): its `deliver_stream` reads what it is
    handed to the stream's end, recording each item under `streamed`, and
    its `deliver_stream` reactions may stop it (`stop_after`, `stop_after_rows`), hold its read
    at a gate once it was handed a text (`hold_after`, `hold_gate`), make it
    raise once it stopped (`fail`) or return an `output`; with `streams_in`, it takes one only in
    the rooms listed (§6.1 `supports_streaming_delivery_for`), whether it
    declares `streams` or not: the framework asks it at each stream;
    with `reads_usage`, it also records what each generation tells of its
    usage (§6.1 `deliver_stream`, §6.4), which it skips otherwise; with
    `reads_loop_end`, the turn's end the stream hands last, its reason, its
    rounds and its usage (§6.4), which it skips otherwise;
  - `recent_events_window` (default 0): how many of the room's latest
    events it declares it reads (§6.1), which sizes the room's context;
  - with `addresses`, its own address methods answer in place of the
    defaults (§5.7, §10.4): `normalizes` lists the addresses
    `normalize_address` writes otherwise, `conversation_key` the metadata
    key `conversation_address` reads a message's conversation under (its
    sender when absent), and on a channel with a `recipient_key`,
    `reply_metadata`, `recipient_metadata` and `recipient_address` name and
    read the recipient under that key, `recipient_at` the key
    `recipient_address` reads in its place; without it, an address is written as
    given, a conversation is its sender's, and a routed sender is recorded
    with no recipient;
  - with `sender_is_participant`, it names its own senders: its inbound
    `sender_id` is a room's `Participant.id`, which no resolver is asked
    about (§11.6);
  - with `verbs`, its per-room verbs (§10.6.3), by name: `keeps` merges the
    call's arguments into what this build keeps for the room and answers
    that, `reads` answers it, `result` is answered as written; what it keeps
    is the room's state of §10.6.2, dropped by `on_room_detached`;
  - with `declared`, the kit holds it by its declaration alone, and the
    executors of `executors` that host it build it (below);
  - an `ai` channel with a `model` is a **scripted agent** instead (below).
- `rooms`: each is created (`id`, `organization_id`, `metadata`, `timers`),
  `store_metadata` then written through the store (`patch_room_metadata`), the
  way to seed a key only the framework writes (§5.1), which `metadata` has
  dropped, then each of its `bindings` attached (`channel_id`, `category`, `access`,
  `muted`, `visibility`, `metadata`, `participant_id`), then each of its
  `participants` stored as the room's record of them (a Participant, §5.5,
  completed with its room and `joined_at`); a `status` of `paused`, `closed`
  or `archived` is reached through the kit's own transitions.
- `hooks`: each is registered on the kit: `name`, `trigger` (a HookTrigger:
  `before_broadcast`, `after_broadcast`, `on_room_created`...), `execution`
  (default `sync`), `priority`, `timeout_ms`, `channel_types`, `channel_ids`,
  `directions`, `fail_closed`, `needs_lock`, and its `reactions`. A
  **scripted hook** records each call (its trigger, the room of its context,
  its payload), then reacts; with no reaction it allows. A hook with a
  `router` is a **conversation router's** hook instead (§19.4), on
  `before_broadcast`: the implementation's ConversationRouter built from
  its `rules` (each `agent_id`, `priority` (default 0) and `conditions`:
  `phases`, `channel_types`, `intents`, `source_channel_ids`, each a list,
  absent for no condition), `default_agent_id` and `supervisor_id`, the
  hook its router gives. It records no call and has no reactions. A room's
  hook (`add_room_hook`) may have one too.
- `identities`: each stored in the kit's store before the rooms are made,
  an Identity (§5.6) in the serialized form: what `resolve_participant`
  reads.
- `identity_hooks`: each is registered as an identity hook (§11.2), apart
  from the hooks of §9.1: `name`, `trigger` (`on_identity_ambiguous` or
  `on_identity_unknown`), `channel_types`, `channel_ids`, `directions`, and
  its `reactions` (`when`, `repeat`, `gate`, `fail`, `result`). It records
  each call under `hooks`, with the IdentityResult it is handed as
  `identity_result`, then answers its reaction's `result`, an
  IdentityHookResult (§11.3), whose `inject.event` is a template completed
  as a hook's injected event; with no reaction, or a `result` of null, it
  answers null.
- `strategies`: each a **scripted strategy** (§19.7), a host's own, none
  installed: `id`, how the calls name it, one object whatever the room it
  is installed in; `agents`, the channel ids of its agents, channels the
  kit holds, which the kit attaches to the room as intelligence channels
  before the install runs; `install` and `uninstall`, what its install and
  its own uninstall step do, each as a reaction does: it holds at its
  `gate`, makes the actions of its `do` in order, `$room` naming the room
  it is installed in, then, for an install, refuses the room with
  `refuse`, the strategy's own refusal, an `invalid_argument` (an
  uninstall step refuses nothing). A strategy with a `loop` is the
  implementation's **Loop** instead (§19.7.4), built from its members:
  `agent`, the producer, and `reviewer` or `reviewers`, each the channel id
  of a scripted agent with an `agent` identity, `max_iterations` (default 3)
  and `strategy`, a WorkerStrategy (`sequential` or `parallel`), the
  implementation's default when absent. A strategy with a `supervisor` is
  the implementation's **Supervisor** (§19.7.3), built from its members:
  `supervisor` and `workers`, the channel ids of scripted agents with an
  `agent` identity, `strategy` (absent: one `delegate_to_<worker>` tool per
  worker), `share_channels`, `task_timeout_ms`, its `task_timeout` in
  milliseconds, `max_revisions`, `auto_delegate`, `refine_task`,
  `refine_instruction`, `delegation_message`, `wait_for_result` and
  `async_delivery`, each the
  implementation's default when absent. A strategy with a `swarm` is the
  implementation's **Swarm** (§19.7): `agents`, the channel ids of scripted
  agents with an `agent` identity, and `entry`, the first agent when absent.
  A strategy with a `pipeline` is the implementation's **Pipeline** (§19.7.1):
  `agents`, the same, each handing off to the next, and `supervisor_id`.
  A strategy with a `discussion` is the implementation's **Discussion**
  (§19.7.5): `agents`, the channel ids of scripted agents, its `handles`,
  `people`, `addressed_only`, `everyone`, `max_turns`, `max_depth`,
  `silent_token` and `rules`, with `done`, a `done` answering what the last
  `discussion.done` call named, and with `dispatch`, a **scripted dispatch
  policy** (§19.7.5 rule 18), the implementation's mock: each decision asked
  takes the next of its `decisions`, a list of channel ids (reason `scripted`)
  or a decision whole (`agents`, `reason`, `judgments`), the last one
  repeating, and with none it decides what the message asks with no policy;
  it holds at its `gate`, waits `delay_ms`, then raises `error` when given;
  `dispatch_timeout_ms`, the discussion's `dispatch_timeout`, in milliseconds. A runner's idle wait counts a discussion's turn
  to give, not its driver's rest between two looks at the queue.
- `session_auditor`: the run's **session auditor** (§15.8.2), the
  implementation's JSONL session auditor over a file of its own, which
  `expect.session_audit` reads; with `attached: true`, attached to the kit
  before the steps, as the implementation's `attach` registers its hooks.
- `processes`: other **processes** serving the rooms (§19.7.5 rule 16), each
  `id`, how a call's `kit` names it: a kit of its own over the run's store
  and lock manager, as processes share a database and its locks, holding
  the setup's channels as objects of its own, registered in the same order;
  a scripted agent answers from the one model of its channel id, whichever
  process runs its turn. The rooms, hooks and strategies of the setup are
  the run's own kit's.
- `executors`: **turn executors** beside the kit (§10.6.2, §10.6.7), served
  on the kit's turn backend, each `id`, the channel ids it `hosts` (each a
  name, or a prefix ending in `*`: `acme-*`, and `*` for every channel), the
  ones its factory `builds` (every declared one when absent; for another it
  builds nothing), `max_channels`, how many it keeps built at most (no bound
  when absent), the
  `hooks` it registers and the `room_hooks` it defines on triggers a turn
  fires (§10.6.6), `started` (default true; false: served only by an
  `executor.start` step) and `answers` (default true; false: it takes each
  turn it is given and never answers it, `gate` naming a gate it reaches as it
  takes one, for a `wait_for` step). The channels it runs are the ones
  the setup marks `declared`: each executor builds its own copy, and a
  scripted agent answers from the one model of its channel id, whichever
  executor runs its turn. `kit.turn_timeouts` gives the bounds of a turn
  (§10.6.8): `accept_ms`, `heartbeat_interval_ms`, `heartbeat_timeout_ms` and
  `cancel_ms`, the implementation's default for each absent. Which of several
  executors declaring a channel takes a room's first turn is the backend's
  to choose (§10.6.7): a scenario that needs one starts the other afterwards.

### Identity resolution

The **scripted resolver** records each call under `resolver` (the room of
its context, the message's `channel_id` and `sender_id`), then answers with
the first of its `answers` whose `when` holds (`sender_id`, `channel_id`,
`room_id`, `text`), used once unless it has `"repeat": true`: it holds at
its `gate`, then raises with `fail`, or answers `result`, an IdentityResult
(§11.1). With no answer left, it answers `{"status": "unknown"}`.

### Reactions

A channel's or a hook's reactions are tried in order on each call: the first
whose `when` holds is used, once, unless it has `"repeat": true`. When none is
left, the call does what it does by default. A reaction:

| Member | What it does |
|---|---|
| `when` | Holds when every member equals the call's: `room_id`, `text` (a text content's body), `type` (the event type), `source_channel_id`, `chain_depth` |
| `gate` | Holds the call at this gate until a step opens it |
| `do` | Kit calls the hook or the channel makes while it runs, in its execution context, in order: an **action** is a call (below) with an optional `as` and `expect`. Its error is caught, kept and checked, never raised into the kit |
| `after_turn` | In an `on_event` reaction: actions the turn leaves to work it began, a task in the turn's execution context that makes them in order once the turn ended (§10.6.5): a `host.<verb>` then crosses as a `room_call`. A runner waits for that work when it waits for the kit to go idle |
| `fail` | Then raises, with this message |
| `refuse` | In a `deliver` or `on_event` reaction: then fails with the provider's explicit refusal (§5.13), its `error`, the `code` and `retryable` it declares, and the `provider_message_id` it names |
| `respond` | Event templates: the turn's response events (`on_event` only) |
| `output` | `tasks`, `observations` and `metadata_updates` of the channel's output; `provider_result`, the provider receipt (`success`, optional `provider_message_id`, `error`, `metadata`) returned in its `ChannelOutput` and preserved in the delivery result (§5.13), or null; a refusal uses `refuse`; in an `on_event` reaction, `response_metadata`, the record its turn writes (§6.4), and `error`: the error the channel met while producing it, with that message, which goes on with its responses and surfaces as a raised one's (ON_ERROR) |
| `writes_record` | In a hook's reaction: first of all, before its `gate`, writes these keys on the turn's record (§6.7), on `before_ai_generation` through its context's `response_metadata`, on another trigger through `current_response_metadata()` when it answers one |
| `stop_after` | In a `deliver_stream` reaction: the channel stops reading the stream once it was handed the text delta or the piece of reasoning this string equals |
| `stop_after_rows` | In a `deliver_stream` reaction: the channel stops reading the stream once it was handed this many of its rows, a call's start or end |
| `parsed` | In a `parse` reaction: a patch on the event the channel builds, what it reads off its own wire: its members replace the event's, those of its `source` the source's; its strings name what the run made (References) |
| `result` | A hook's HookResult (§9.4). A modify's `event` is a patch on the payload: its members replace the payload's. Its injected events, tasks and observations are templates; event aliases in a room-event hook result resolve after its actions, before the result is returned |
| `invalid_result` | A deliberate unusable return on a SYNC `before_broadcast` hook: `{ "kind": "no_result" }` returns null; `{ "kind": "missing_payload", ... }` returns an unchecked MODIFY with no event, optionally carrying `tasks`, `observations`, and `injected_events` templates. Mutually exclusive with `result` and `fail`. A runner validates the fixture before invoking the hook; a malformed fixture is a runner failure, never a simulated hook exception |

An invalid return exercises the hook chain, not the model constructor. A
`missing_payload` is constructed unchecked (Python `model_copy`, Rust struct
fields); it must not be replaced by a constructor error. A wrong payload type
is tested on implementations that can return one: Rust's typed hook callback
cannot return a `HookResult<String>` where `HookResult<RoomEvent>` is required.
Such a language-specific proof is reported separately, never simulated by a
hook exception in the shared runner.

**Templates.** A runner completes a template, written in the serialized form,
with what the record requires: a fresh `id`, the room of the call as `room_id`,
`type` `message`, `created_at` now. An agent's response gets the agent's source
(`direction: outbound`) and `chain_depth` one more than its trigger's; an event
a hook injects, or a record `commit_event` commits, the framework's source
(`{channel_id: system, channel_type: system, direction: inbound}`); a task or an
observation an `id`, the room, and for an observation the channel that made it
(`system` for a hook). Members the template gives win, and a member it does not
give takes each implementation's default: a scenario that asserts a member gives
it.

### Scripted agents

An `ai` channel with a `model` is the implementation's own AI channel (§6.4),
run on a scripted model and scripted tools, so that its tool loop is the one
under test. Its turn builds the conversation and runs the loop as the
implementation's AI channel does; only the provider and the tools are
scripted.

- `model.streaming`: true by default. False runs `generate()` through the
  provider's default whole-response adapter, including tool calls and gates.
  Each round is reserved before waiting at its gate. In this mode the
  stream-only fields `deltas`, `thinking`, `stream`, `done`,
  `failure_after_calls` and `failure_after_done` are refused; use `text`,
  `calls`, `whole_response`, `usage`, `finish_reason`, `fails` or `refuses`.
  A `whole_response` cannot be combined with `fails` or `refuses` in this
  mode; script a failing round without `whole_response` instead.
  A `fallback_model` takes the same option.
- `model.rounds`: the model's answer to the agent's n-th generation of the
  run is its n-th round: `text` (default empty), `calls`, `finish_reason`
  (default `tool_calls` when it calls, else `stop`) and `usage`, counters
  the turn's record sums (§6.4, The turn's record). A call is `id`, `name`,
  `arguments` (an object, default `{}`; a text `$<label>` in it is read,
  once the model writes the call, as References read it: the id of the
  task a step labelled `<label>` delegated), and `cut` when the response was
  cut short over its arguments, which never arrived whole: the round's last
  call, under a `finish_reason` that cuts calls (§6.4). A generation past
  the last round fails the turn. `deltas` writes the round's text in those
  pieces, in place of `text`: the model waits between two, so a reader is
  handed each apart (deltas yielded without waiting may cross as one,
  §10.6.4). `thinking`: the round's reasoning, in the pieces the model
  streams it before its text (§6.7). `fails` makes the model fail with that
  message once it wrote its text, before its calls and its end: its response stream raises
  (§12.2 step 13s). `done: false` ends its stream after its text and its
  calls without the done event that carries its finish reason and usage.
  `refuses` makes the provider refuse the request once the model wrote its
  text, before its calls and its end: an error with that `status` (an HTTP
  status) and `message` (§6.4), worth another try when `retryable` is true
  (default false), classed as a context too long for the model when
  `context_overflow` is true, as not one when it is false, unclassed when it
  is absent, refused by the provider `provider` names, none when it is
  absent. `failure_after_calls: true` moves the
  round's `fails` or `refuses` after its calls: the model writes its text,
  then its calls, then fails, never reaching its end. `failure_after_done:
  true` moves it after the done event: the model writes its text, its calls
  and its end, then fails.
  `stream`: the round's events in the order the model streams them, in place
  of `text`, `deltas`, `thinking` and `calls`: `{thinking, signature, block,
  redacted}`, `{text}` or `{call}` (§6.4). `whole_response`: the round is a
  response read whole, its text and calls as the round gives them, its
  reasoning its `thinking`, `thinking_signature` and `thinking_parts` (each
  `{thinking, signature, redacted}`), which reach the loop first (§6.4). A
  call's `metadata`: provider-owned data, replayed with it (§6.4).
  `gate` holds the round at that gate, before it writes anything, until a
  step opens it. `model.vision`: whether the model sees images (§6.4, a
  provider's `supports_vision`), false by default. `model.response_schema`
  and `model.response_schema_with_tools`: whether the model takes a response
  schema, and one beside tools (§6.7, a provider's `supports_response_schema`
  and `supports_response_schema_with_tools`), false by default; the model then
  keeps the provider's contract as the implementation's mock provider does: a
  request it cannot take under a schema is refused before it is made
  (`unsupported`), and no request is kept; a round that calls no tool, and
  does not end on a call its provider could not hand over, is checked: a
  `finish_reason` of `refusal` is refused, one that ran out of room is
  `truncated`, any other text not the JSON document the schema asks for is
  `invalid_json`, a streamed round's check coming before its done event,
  which the error replaces; a `fallback_model` takes them too. `model.pricing`: the
  model's catalogue price (§6.7, a provider's `catalog_entry().pricing`,
  Python's `ModelPricing` fields), none when absent; a `fallback_model`
  takes one too.
  `model.chat_dialect`: the implementation's Chat Completions rendering, `openai`,
  `openai_thinking_field` (OpenAI's, told by its configuration that the server reads
  `reasoning_content`), `deepseek`, `minimax`, `kimi`, or `anthropic` (native Messages, without cache markers), each request is also written through, whatever the rounds
  answer (`models`, `chat_messages`); a dialect the implementation does not have
  fails the scenario; a `fallback_model` takes one too.
  `model.deferred_tools`: whether this provider holds unseen definitions and accepts
  tool references (false by default); a fallback model takes it too.
  `model.name` and `model.provider`: the names a turn's record gives as
  `ai_model` and `ai_provider` (§6.4), `scripted` when absent; a
  `fallback_model` takes them too.
- `tools`: what the agent serves, each declared with its `name`,
  `description` and `parameters` (a JSON Schema), and answering every call
  one way: `returns` a text, `returns_json` a JSON value (the model reads
  it as JSON, §6.7, and a list of mappings each in a part's exact shape as
  those parts, §21.4), `returns_parts` content parts in order, each
  `{text}` or `{image, mime_type}` (a text and its images, §6.4), `raises` an error of a `kind` with a `message`
  (the model reads the kind, the observers the message, §9.3), `fails` or
  `refuses` with words the model reads (§9.3), or `hangs`, never answering;
  with `gate`, each call is held at that gate until a step opens it, then
  answered so; with `declared: false`, the agent does not declare it, and
  its tool handler serves it all the same, for a hook that declares it.
  `writes_record`: each call first writes these keys on the turn's record
  through `current_response_metadata()` (§6.7), before a `gate` holds it.
  `changes_state: true` declares it on its definition as a tool that
  changes state (Python's `AITool(changes_state=True)`, §6.4).
- `tool_policy`: a ToolPolicy's `allow` and `deny` patterns (§21.1);
  `max_tool_rounds`: the loop's bound on rounds of calls (Appendix A.9,
  default 50); `max_empty_retries`: how many times a round with no call to
  run is tried again (Appendix A.9, default 1).
- `tool_timeout_ms`: the bound on each call of its tools (§21.6), `null`
  bounding nothing, the implementation's default when absent;
  `tool_timeouts_ms`: a bound per tool name, above that default and above a
  tool's own bound, `null` leaving the tool unbounded.
- `turn_budget_tokens`: the turn's budget of billed tokens (§6.4), a
  round's `usage` counting its `input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`,
  `input_image_tokens` and `output_image_tokens`.
- `turn_budget_usd`: the turn's cost budget (§6.4), each generation's
  `usage` priced as one response at the model's `pricing` (its catalogue
  price: `input_per_million`, `output_per_million`, the cache and image
  rates, `long_context_threshold_tokens` and its multipliers, `currency`,
  `verified`), the costs added up; a model with no `pricing` refuses it.
- `reasoning_effort`: the effort the agent's turns ask for (§6.7), under
  the one its binding's metadata sets (`null` there keeps the agent's).
- `response_schema`: the JSON Schema each of the agent's turns answers in
  (§6.7), under the one its binding's metadata or its `config_provider`
  sets (Appendix A.9, per-turn settings); none when absent.
- `system_prompt`, `temperature`, `max_tokens`, `thinking_budget` and
  `enable_thinking`: the agent's own settings (§6.4, §6.7), each under the
  one its binding's metadata or its `config_provider` sets (Appendix A.9,
  per-turn settings). The binding's
  `tools` declare tools the agent's handler serves, before the agent's own
  (definitions: `name`, `description`, `parameters`).
- `text_coalesce_ms`, `text_coalesce_chars` and `publish_text_deltas`: how long
  and how many characters its answer's text batches into one `TEXT_DELTA`, and
  whether a turn read as a delegated task's trace publishes it (§6.4).
- `thinking_coalesce_ms` and `thinking_coalesce_chars`: how long and how many
  characters its model's reasoning batches into one `thinking_delta` (§6.7); 0
  ms publishes each piece.
- `publish_thinking_text`: whether those events carry the reasoning's text;
  false when absent, a subscriber then reading its length alone (§6.7).
- `config_provider`: what the agent's per-turn configuration returns for a
  turn, by the room id of the binding it is called with (the room of the
  context must be the same): a `turn_config`, Python's
  `AIChannelTurnConfig`, or `null`, as a room it does not name, for none; a
  list gives that room's turns in order, one each, its last standing for the
  turns after.
  Its `system_prompt`, `temperature`, `max_tokens`, `thinking_budget`,
  `enable_thinking`, `reasoning_effort`, `turn_budget_tokens` and
  `turn_budget_usd` sit under the binding's
  metadata and over the agent's own, a `null` not set; its `tools`
  replace the toolset the binding's metadata declares, the agent's own
  tools after them; its `tool_handler`, scripted tools as `tools`
  describes them, serves the host's tools for that turn alone, in place of
  the agent's handler, a name it does not hold unserved; its `skills` give
  the turn a registry of its own in place of the agent's, for that turn alone
  (§24.3).
- `skills`: the agent's skill registry (§24.3), each skill's `name`,
  `description`, `instructions` and `references` (file names and their text)
  written to a directory of its own, as a host's skills are, and discovered
  from there; `[]` is an empty registry, which is not none: a turn's registry
  is read only on an agent given one. `skills_in_prompt`: false leaves the
  listing to the host, whichever registry a turn reads; the instructions of
  the skills active are written either way (default true).
- `retry_policy`: the agent's retry policy (§6.4): a generation its
  provider refused as worth another try (`refuses.retryable`) before it
  handed anything is tried again, at most `max_retries` times (default 3),
  each attempt after `base_delay_ms` (default 1000) times
  `exponential_base` (default 2) to the attempt's number, at most
  `max_delay_ms` (default 60000); no retry when absent. `fallback_model`:
  its fallback provider, a scripted model asked once those retries are
  spent, whose requests `models` holds under `<agent>/fallback`. The agent's
  router is the implementation's fallback router over `model` and
  `fallback_model`: every turn starts on `model`, and once a generation's
  retries are spent it is handed to the other one.
- `router`: the agent's router (§6.4), in place of a `fallback_model`, with
  `model` still its own model. `models`: more scripted models by name, whose
  requests `models` holds under `<agent>/<name>`. `turns`: the model each
  turn's start picks, `retries`: the model each retry picks once a
  generation's retries are spent (`[null]` by default, null picking none),
  each list taken in order, its last entry repeating. A pick names a model as
  `models` does: `<agent>` for the agent's own, `<agent>/<name>` for one of the
  router's. What the router was asked is under `ai_routes`.
- `max_context_events`: the window of the agent's default memory, a sliding
  window of the room's latest events (§20.3, default 50).
- `max_author_images`: how many of the newest author images a turn sends as
  images, its history and its input counted together (§6.4, default 4),
  `null` bounding nothing; `describe_empty_event`: the host's describer,
  asked of an event that reads as nothing in the turn's transcript (§6.4),
  answering every event it is asked about with `says`, `null` leaving the
  event out.
- `evict_threshold_tokens`: the estimated tokens (a quarter of the
  characters, plus one) past which an outcome of a call reaches the model as
  a preview, its whole text stored for `read_stored_result` to read back
  (§21.5, default 5000).
- `serialize_room_turns`: its turns in a room run one after the other (§6.4,
  default false); `steer_room_turns`: a message for a room where its turn
  runs is steered into that turn rather than a turn of its own (§6.4,
  §21.3, default false), its turns serialized.
- `agent`: the agent is an implementation's Agent, an AI channel with an
  identity (§19.7): its `name`, `role`, `description`, `purpose`, `scope`
  and `language`, each unset by default; its turns end their system prompt
  with its identity block (`role`, `description`, `scope`, then `language`,
  each on a line under `--- Agent Identity ---`), in the language the room's
  conversation state sets (`metadata._conversation_state.context.language`)
  over its own, unless `identity_in_prompt` is false (default true). With a
  `greeting` and `auto_greet` (default true), it greets each room a text
  session starts in that binds it, once per room: its greeting stored as its
  event, marked `auto_greeting`, and delivered before the message that
  started the session is processed (§19.1).
- `memory`: a **scripted memory** in place of the default (§20): the room's
  latest `max_events` events as a sliding window reads them (default the
  agent's `max_context_events`); `returns_current_event: true` also returns
  the answered event once, before the first retained event with a greater
  index, or last when none has one (default false). This exercises the
  provider style §20.1 permits alongside omitting the turn's input.
  It also returns the `messages` it built (each `role`
  and `text`, or `role` and `parts`, texts it holds back to back as text
  parts), the `notes` it retrieved for the turn alone and the
  `speakers` its messages name (§20.2), and `writes_record`, keys each read
  writes on the turn's record through `current_response_metadata()` (§6.7); it keeps each
  event it is handed (`ingest`), which `expect.ingested` reads; `compacts` scripts what it
  answers each compaction between two tool rounds (§6.4, §20.1), the n-th its n-th item and
  nothing past the last: `null` hands back nothing, an object its `messages` then the last
  `keep` messages of the history it was handed (default 0), or `fails` with that message, and
  it keeps each compaction it is asked, which `expect.compacted` reads; `budget_aware` wraps it in the
  implementation's budget-aware memory, of its `max_context_tokens`,
  `safety_margin_ratio` (default 0.15), `min_events` (default 3) and
  `reserved_tokens` (default 0) (§20.3); `compacting` and `summarizing`
  wrap the memories before them in the implementation's compacting and
  summarizing memories (§20.3), of the parameters the schema names, which
  summarize with `summarizer`, a scripted model whose requests `models`
  holds under `<agent>/summarizer`; `retrieval` wraps them in the
  implementation's retrieval memory, which searches its scripted knowledge
  `sources` for the turn's words (§20.2).
- `human_input`: its human-input handler (§9.3, ON_USER_INPUT_REQUIRED,
  where the other party is a human; §10.6.5, Human input): the agent
  declares `tools` (each `name`, `description`, `parameters`) and serves
  every name of `tool_names` itself, before its tools' handler, a name it
  does not define served when another of its tools declares it. Each call
  opens a request, which fires `on_user_input_required`, and waits for its
  answer at most `timeout_ms` (default 300000), bounded by that alone: the
  model reads the answer; a rejection, or a hook's block, as a refusal
  (`{"error": "Human input rejected: <reason>"}`); no answer in time as a
  failure (`{"error": "Human input timed out after <s>s for tool '<name>'"}`,
  the seconds as Python writes a float).
- `kit_tools`: tools the kit makes that the agent is given as its own,
  among its tools (§23.4): `task_status` is the implementation's
  TaskStatusTool over the kit, `cancel_task` its CancelTaskTool, each with
  its default window, reading the room and the channel of the call it
  serves; a call its scripted tools do not name goes on to them.
- `tool_search`, `tool_search_pinned`, `tool_search_threshold`,
  `tool_search_threshold_pct`, `tool_search_miss_hint` and
  `tool_search_threshold_tokens`: its Tool Search (§6.4), each the
  implementation's default when absent; `model.context_window`, the window
  of the model's catalogue entry (§6.7), which it measures a catalogue
  against, unknown when absent; a tool's `tags`, which `find_tools` searches.
- `audit`: the auditor its tool calls are recorded to (§15.8): its tool
  handler, serving every scripted tool, is wrapped in the implementation's
  `audit_tool_handler` under the agent's id, recording to the run's **tool
  auditor**, the implementation's JSONL tool auditor over a file of its own
  (`tool_auditor`), or to the run's session auditor through its
  `tool_auditor` bridge (`session_auditor`).

A hook on `before_tool_use` or `on_tool_call` is registered on the kit as the
implementation registers a hook on those triggers. Its payload is a tool
call, which it records as `tool_call` (below), and its `result` is a
HookResult as for any hook: a `block` with its `reason`, or a `modify` whose
`event` is a patch on the tool call (`arguments`, `result`).

A hook on the triggers of an agent's loop (§6.4) is handed what its trigger
hands, and records it (below): on `before_ai_generation` the generation
(`AIGenerationEvent`), as `generation`; on `after_tool_round` the round
(`ToolRoundEvent`), as `tool_round`; on `on_ai_response` the turn's response
(`AIResponseEvent`), as `response`. A `modify`'s `event` is a patch: on a
generation, the replacement event whose context's `system_prompt`,
`messages` (each `{role, text}`), `reasoning_effort`, `thinking_budget`,
`enable_thinking`, `response_schema` (null clearing it, §6.7) and
`response_metadata` (a record of its own, §6.7) are the patch's,
whose `tools` are
those of the context the patch names, and then each tool `define` gives
(`name`, `description`, `parameters`) in place of the tool of its name, or
after them; on a round, what the hook does to the
event in place (§6.4, Between two rounds): each name of `withdrawn`
withdrawn, each text of `messages` added.

A hook on `on_user_input_required` is handed the request (`PendingInputEvent`),
which it records as `request` (below); a `block` rejects the request, unless
it was answered first.

### Scripted ACP agents

An `ai` channel with an `acp` member is the implementation's ACP agent channel
(§6.4): RoomKit is the ACP client, and the agent is a **scripted ACP agent**
the runner serves in its own process over a pipe, through the channel's
transport seam, with no process. The agent is written at the wire's level,
JSON-RPC 2.0 one message per line, in neither implementation's ACP code, so
that both runners check the same messages.

- `acp.cwd`: the channel's `cwd`, an absolute path.
- `acp.agent.initialize`: its `initialize` answer: `protocol_version` (the
  client's when absent), `closes_sessions` (whether it announces
  `session/close`, true by default), `agent_info` (sent as written, none when
  absent).
- Its `session/new` answers are `session-1`, `session-2`... in the order it
  is asked, with no config option; `session/close` is answered `{}`;
  `session/cancel` is taken.
- `acp.agent.prompts`: its answer to its n-th `session/prompt` of the run:
  held at its `gate` first when it names one, then each of its `updates`
  sent as a `session/update` of the prompt's session, in order, then its
  answer, `error` (a JSON-RPC error) or else `stopReason` (`stop_reason`,
  `end_turn` by default) and `usage` when given. A prompt past the last is
  answered `end_turn` with no update.
- Any other request is answered `method_not_found`.

`expect.acp_wire`, per ACP channel: what its agent received, in order, each
`{method, params}`, `params` as the client wrote them, matched as a patch. A
client's `clientInfo.version` is its implementation's own.

### Steps

| Step | What it does |
|---|---|
| a call | Makes the call and waits for it; `expect` checks its outcome |
| a call with `"background": true` and `as` | Starts the call and goes on once the call has run to its first wait: what the next step does or wakes comes after that part of the call |
| `{"await": label}` | Waits for the background call; `expect` checks its outcome |
| `{"concurrent": [calls]}` | Starts the calls together and waits for all |
| `{"wait_for": gate}` | Waits until a call is held at the gate (a runner fails after 5 s) |
| `{"open": gate}` | Opens the gate: every call held there, and every later one, goes on |
| `{"idle": true}` | Waits until the kit runs nothing in the background; with `processes`, until none of the kits does, each discussion's driver roused first, so that it reads what another process stored |
| `{"wait_for_lock": room, "waiters": n}` | Waits until `n` calls (1 by default) wait for the room's lock (a runner fails after 5 s): calls started in the background are then known to overlap. `room` may be a reference, a room the run created (`$r1`) |
| `{"lock_releases": "fail"}`, `{"lock_releases": "succeed"}` | Sets the releases of the kit's `lock_manager` failing or succeeding, from the next one on |

A call that has not returned after 10 s fails the scenario.

### Calls

Each takes the RFC's name and the RFC's arguments, and may name an
`organization_id` it acts for (§17.2). Records are in the serialized form.
A call taking `kit` runs on the process it names (`setup.processes`), on the
run's own kit when absent.

| Call | Arguments | Result |
|---|---|---|
| `process_inbound` | `message` (an InboundMessage), `room_id` | an InboundResult: `event`, `blocked`, `duplicate`, `reason`, `error` (its message), `response_metadata`, `response_events`, `unavailable_targets`, `delivery_results`, `cancellation_reason` |
| `process_inbound` with `defer_delivery: true` | as above | the InboundResult at the commit (§10.1 step 18); its completion handle is named by the call's `as` label |
| `delivery.cancel` | `of`, the label of a deferred `process_inbound`; `reason` (default `caller_cancelled`), `timeout_ms` (default 5000) | the handle's InboundResult once the turns it cut are over (§10.1 Explicit delivery cancellation); a handle done returns its result unchanged |
| `delivery.wait` | `of`, as above | the handle's InboundResult once its delivery is over (§10.1 step 18) |
| `regenerate_response` | `room_id`, `trigger_id`, optional `kit` (§13.6): the named kit's room agents answer its last message again, chosen under the room lock | an InboundResult, as `process_inbound`'s, its `event` the message answered again; null when the room holds no message to answer again |
| `regenerate_target` | `room_id`: the message `regenerate_response` would answer again, read outside the lock | the event, or null; its `as` label names it |
| `send_event` | `room_id`, `channel_id`, `content`, `event_type`, `participant_id`, `visibility`, `response_visibility`, `addressed_to`, `parent_event_id`, `idempotency_key`, `metadata`, `chain_depth`, `standalone` | the event |
| `post` | `room_id`, `content`, `participant_id`, `addressed_to`, `metadata`, `channel_id`, `idempotency_key`, `chain_depth` | the event |
| `commit_event` | `room_id`, `event` (a template) | the event |
| `update_event` | `room_id`, `event_id`, `content`, `source`, `metadata` | the event, or null |
| `delete_event` | `room_id`, `event_id`, `cascade_replies` (default true) | the ids removed |
| `create_room` | `room`: `id`, `organization_id`, `metadata`, `timers`; `orchestration`, a scripted strategy's id, `null` for none, the kit's default when absent (§19.7) | the room |
| `attach_channel` | `room_id`, `channel_id`, and a binding's `category`, `access`, `visibility`, `muted`, `metadata`, `participant_id` | the binding |
| `detach_channel` | `room_id`, `channel_id` | unspecified |
| `mute`, `unmute` | `room_id`, `channel_id` | the binding |
| `mute_output`, `unmute_output` | `room_id`, `channel_id` | the binding |
| `set_access`, `set_visibility` | `room_id`, `channel_id`, `access` or `visibility` | the binding |
| `update_binding_metadata` | `room_id`, `channel_id`, `metadata` | the binding |
| `close_room`, `archive_room` | `room_id` | the room |
| `pause_room`, `resume_room`, `reopen_room` | `room_id` | the room after the integrator's transition; a status it cannot leave, `transition_refused` (§5.1) |
| `send_greeting` | `room_id`, optional `channel_id`, `agent_id`, `greeting` | null: the agent's greeting, or `greeting`, stored as its event and delivered (§19.1) |
| `get_room`, `list_bindings` | `room_id` | the room, or its bindings, through the public API in any room status |
| `get_binding` | `room_id`, `channel_id` | the binding; an unbound channel, `channel_not_bound` |
| `list_members` | `room_id`, `include_left` (false) | ACTIVE members by default; with `include_left`, every member |
| `get_timeline` | `room_id`, `offset` (0), `limit` (50), `visibility_filter`, `after_index`, `before_index`, `newest_first` (false), `include_blocked` (false) | the public timeline; lifecycle records remain visible when their visibility matches |
| `check_all_timers` | optional `organization_id` | every room whose status the sweep changed; order is unspecified, use `$unordered` |
| `check_timers` | `room_id` | the named room only, once its due transitions are applied through `check_room_timers`; the caller's `organization_id` is checked before applying any transition (§5.1, §17.2) |
| `set_room_timers` | `room_id`, `timers` (`inactive_after_seconds`, `closed_after_seconds`, `last_activity_at`) | the room, its timers replaced under its lock, its last activity kept when `timers` names none (§5.1) |
| `set_agent_response_policy` | `room_id`, `policy` (`agent_chain`, `addressed_only`) | the room, its agent response policy set under its lock, unchanged when it holds it (§19.3.1) |
| `register_channel` | `channel` (as in the setup) | null |
| `unregister_channel` | `channel_id` | null |
| `register_hook` | `hook` (as in the setup) | null |
| `process_delivery_status` | `status` (a DeliveryStatus: `room_id`, `channel_id`, `provider`, `message_id`, `status`, `recipient`, `sender`, `error_code`, `error_message`, `timestamp`, `raw`) | null |
| `deliver` | `room_id`, `content` (a text), `channel_id`, `strategy` (`immediate`, `wait_for_idle`, `queued`), `metadata`, `addressed_to`, `idempotency_key`, `session_id`, `chain_depth`, `instruction` (§22.1) | a DeliveryOutcome: `status`, `reason`, `delivery_item_id`, `event_id`, `duplicate`, `unavailable_targets`, `session_ids`, `session_outcomes`, `error`, `turn_complete` |
| `process_webhook` | `meta` (a WebhookMeta: `provider`, `sender`, `recipient`, `body`, `external_id`, `timestamp`, `raw`, `media_urls`, `direction`, `event_type`), `channel_id` | null |
| `mark_read` | `room_id`, `channel_id`, `event_id` | null |
| `mark_all_read` | `room_id`, `channel_id` | null |
| `list_read_markers` | `room_id` | each channel's marker, an index |
| `add_room_hook` | `room_id`, `hook`: a hook as in the setup, for that room alone, with no filter and the default timeout (`name`, `trigger`, `execution`, `priority`, `fail_closed`, `needs_lock`, `reactions`) | unspecified |
| `remove_room_hook` | `room_id`, `name` | whether the room held a hook of that name |
| `cancel_delivery` | `key`, the `delivery_key` of the messages whose delivery it cancels, and `reason` (§10.1 Explicit delivery cancellation) | how many deliveries it cancelled |
| `close` | none | null once the kit's shutdown ended (§12.10.4) |
| `steer` | `room_id`, the room whose turns it reaches, `channel_id`, the agent, and `directive` (a SteeringDirective in the serialized form: `{"type": "cancel", "reason"}`, ...) (§21.3) | how many of the agent's running loops in the room it reached |
| `install_strategy` | `room_id`, `strategy` (a scripted strategy's id) (§19.7) | null |
| `uninstall_strategy` | `room_id` (§19.7) | whether the room held a strategy |
| `claim_room_strategy` | `room_id`, `strategy`: claims the room for the strategy, or refuses, installing nothing (§19.7) | null |
| `room_strategy` | `room_id` | the id of the scripted strategy installed in the room, null for none (§19.7) |
| `default_router.route` | `channel_id`, `channel_type`, `participant_id`, `identity_id`, `organization_id`: the implementation's DefaultInboundRoomRouter over the kit's store, whatever router the kit holds (§10.4), reading no channel | the id of the room, null for none |
| `save_conversation_state` | `room_id`, `transitions`: each a phase transition (`to_phase`, `to_agent`, `reason`, `metadata`) made in order from the conversation state of the room the store holds, the default state for a room it lacks; the state the last one leaves is saved as the room's (§19.2) | null |
| `handoff_handler` | `handler`, the name the later calls give it; `router`, a conversation router as a hook's (§19.4); `agent_aliases`, `phase_map`, `allowed_transitions` (each phase's list of phases), `known_agents` and `event_channel_id`: the implementation's HandoffHandler, serving no agent yet and installing no hook, its `greeting_map` set from the call's (§19.6) | null |
| `install_router` | `handler`, `router`, `agents` (channel ids), `agent_aliases`, `phase_map`, `hook_priority`: the router's `install` on the kit, its handler named `handler` (§19.6) | null |
| `conversation_pipeline` | `stages` (each `phase`, `agent_id`, `next`, `can_return_to`, `description`), `default_phase`, `supervisor_id`: the implementation's ConversationPipeline, built and read (§19.5) | `stages` (each with `can_return_to` as a sorted list), `phase_map`, `allowed_transitions` (each phase's sorted list) |
| `discussion` | `agents`, each a channel id or an agent given live (`id`, its channel id, and `name`, its display name), `handles`, `people`, `addressed_only`, `everyone`, `max_turns`, `max_depth`, `silent_token`, `rules`, `dispatch` (a scripted dispatch policy, as a setup's) and `dispatch_timeout_ms`, each the implementation's default when absent: the implementation's Discussion, built and read, installed nowhere (§19.7.5) | `agents`, the channel ids in order; `handles`, what its `handles()` answers: empty while an agent named by an id that is no handle waits for the install to read its name |
| `speak_queue` | `room_id`, `organization_id`: the kit's `speak_queue` (§19.7.5 rule 17) | `{speaking, queue, listening, asked, waiting, over}`, `listening` sorted; null for a room holding none |
| `discussion.done` | `strategy`, `holds`: what that discussion's `done` answers from now on | null |
| `listen_only` | `room_id`, `channel_ids`, `organization_id`: the kit's `listen_only` (§19.7.5 rule 12) | null; a room holding no discussion in the scope, `invalid_argument` |
| `talk_again` | `room_id`, `channel_ids`, `organization_id`: the kit's `talk_again` (§19.7.5 rule 12) | null; a room holding no discussion in the scope, `invalid_argument` |
| `room_strategy_is_current` | `room_id`, `kind` (`Discussion`, `Pipeline`, `Swarm`, `Loop` or `Supervisor`, the implementation's strategy of that name), `organization_id`, `kit`: the kit's `room_strategy_is_current` (§19.7.5 rule 16) | whether the discussion this process installed is the one the room stores; a kind not stored with the room, `kind_not_stored`; a room outside the scope, `room_not_found` |
| `close` | `kit`: closes the kit (§12.10.4), a process that stops; no later step calls it | null |
| `executor.start` | `executor`, an id of `setup.executors`: serves it on the kit's turn backend (§10.6.7) | null |
| `executor.close` | `executor`: it takes no more turns and ends those it runs (§10.6, §10.6.8) | null |
| `executor.kill` | `executor`: to the room it stops as a killed process stops, sending nothing more and hearing nothing more, its turns left to the owner's liveness checks (§10.6.8) | null |
| `executor.pause`, `executor.resume` | `executor`: it stops declaring its channels, or declares them again, keeping what it holds (§10.6.7) | null |
| `executor.calls` | `executor`: what it did so far, as `expect.executors` reads it; a turn's reaction may make it, to read that at a point of the turn | the list |
| `channel.publish` | `executor`, `channel_id`, `room_id`, `kind` (an ephemeral event's type), `data`, `gate`: in a reaction's `after_turn`, work the turn began publishes on the channel's realtime, once held at `gate` when it names one; the call returns once the room owner took it, or refused it (§10.6.3) | null |
| `channel_call` | `channel_id`, `room_id`, `verb`, `arguments`: the channel's per-room verb, on the executor holding the room's state (§10.6.3) | the verb's result |
| `release_channel` | `channel_id`: every executor holding a build of it lets it go, closed once the turns running on it end, and builds it anew for the next one (§10.6.3) | null |
| `executors` | none: the executors served on the kit's turn backend, its own executor aside (§10.6.7) | the list, in any order, each `{executor_id, hosts, room_hooks, online}`: `hosts` the ids and prefixes it declares, sorted (null for a predicate or every id), `room_hooks` sorted; a closed executor is not listed |
| `agent_presence` | `room_id`: the room's intelligence channels, each online while an executor alive covers it in the room (declares it, and defines the room's enabled hooks), a channel the kit holds live while the kit runs (§10.6.7, §10.6.8) | the list sorted by `channel_id`, each `{channel_id, online, executors}`, `executors` the ids of the executors covering it, sorted |
| `enable_room_hook` | `room_id`, `name`: the room's turns run the room hook the executors define under `name`, and only an executor that defines it takes them (§10.6.6, §10.6.7) | null |
| `install_pipeline` | `handler`, `stages`, `default_phase`, `supervisor_id`, `agents` (channel ids), `agent_aliases`, `hook_priority`: the ConversationPipeline's `install` on the kit, its handler named `handler` (§19.5) | null |
| `setup_handoff` | `agent_id`, `handler`, `targets` (each an id and its description or null: the tool `build_handoff_tool` builds; absent: the generic one), `room_id` (absent: every room): serves the handoff tool on the agent (§19.6) | null |
| `handoff.handle` | `handler`, `room_id`, `calling_agent_id`, `arguments`, the tool call's: the handler's `handle` (§19.6) | the HandoffResult (`accepted`, `new_agent_id`, `new_phase`, `message`, `reason`) |
| `handoff.set_language` | `handler`, `room_id`, `language`: the handler's `set_language` (§19.6) | null |
| `handoff.send_greeting` | `handler`, `room_id`, `channel_id`: the handler's `send_greeting` (§19.1, §19.6) | null |
| `delegate_handler` | `handler`, the name the later calls give it; `notify`, `default_share_channels`, `cache` (true: a CompletedTaskCache of the implementation's default time to live), `serialize_per_room`, `max_conversation`, each the implementation's default when absent: the implementation's DelegateHandler, serving no agent yet (§23.4) | null |
| `setup_delegation` | `agent_id`, `handler`, `targets` (each an id and its description or null: the tool `build_delegate_tool` builds; absent: the generic one): serves `delegate_task` on the agent (§23.4) | null |
| `delegate.handle` | `handler`, `room_id`, `calling_agent_id`, `arguments`, the tool call's: the handler's `handle` (§23.4) | what the tool answers: `status`, `task_id`, `child_room_id`, `agent_id`; a repeat answered from the cache, `result` and `from_cache` too; its `as` label names the task's id |

### Calls on the store

A call `store.<operation>` is the operation of the store's own interface
(§14.1), made on the kit's store, whatever the kit does: its arguments are the
operation's, by name, and its result is the operation's in the serialized
form, a map's values included. A record it takes is a template, completed as
the record requires (Templates): a room's `created_at` and `updated_at`, a
binding's `attached_at`, a participant's `joined_at` and an event's `id`,
`type` and `created_at` are now when it leaves them out, and an event's room
is the call's `room_id`, its source the framework's. A runner runs the
scenarios of `store/` and `idempotency/` on each store it ships that needs no server.

| Call | Arguments | Result |
|---|---|---|
| `store.create_room` | `room` | the room |
| `store.delete_room` | `room_id` | whether the store held it |
| `store.add_binding`, `store.update_binding` | `binding` | the binding |
| `store.remove_binding` | `room_id`, `channel_id` | whether the room bound it |
| `store.add_participant` | `participant` | the participant |
| `store.commit_event` | `room_id`, `event`, `target`, `activity` (default true) | the event |
| `store.room_exists` | `room_id` | a boolean |
| `store.binding_exists` | `room_id`, `channel_id` | a boolean |
| `store.find_latest_room` | `participant_id`, `channel_type`, `status` | the room, or null |
| `store.find_room_id_by_channel` | `channel_id`, `status` | the room's id, or null |
| `store.get_timeline` | `room_id`, `event_filter`, `limit`, `after_index`, `newest_first` | the events |
| `store.get_thread_summaries` | `room_id`, `root_event_ids` | each summary by its root's id |
| `store.add_event` | `event`, its room the template's | the event |
| `store.add_event_auto_index` | `room_id`, `event` | the event |
| `store.check_idempotency` | `room_id`, `key`, `channel_id` (null for any channel) | whether the room holds the key in that scope |
| `store.get_event_by_idempotency_key` | `room_id`, `key`, `channel_id` (null for any channel) | the event holding the key; with no channel, the one of lowest index; null for none |
| `store.get_event` | `event_id` | the event, or null |
| `store.update_event` | `event` | the event |
| `store.delete_event` | `room_id`, `event_id`, `cascade_replies` (default true) | the events removed |
| `store.record_delivery_results` | `room_id`, `event_id`, `results` | null |
| `store.write_change_target` | `room_id`, `target` | null |
| `store.get_room` | `room_id` | the room, or null |
| `store.patch_room_metadata` | `room_id`, `patch`, `unset` (default empty) | the room with only those metadata keys changed, or null |
| `store.update_room_if` | `room`, `status`, `paused_at`, `last_activity_at` | the room written, or null |
| `store.mark_read` | `room_id`, `channel_id`, `event_id` | null |
| `store.mark_all_read` | `room_id`, `channel_id` | null |
| `store.get_unread_count` | `room_id`, `channel_id` | a count |
| `store.list_read_markers` | `room_id` | each channel's marker, an index |
| `store.add_task`, `store.update_task` | `task` | the task |
| `store.get_task` | `task_id` | the task, or null |
| `store.list_tasks` | `room_id`, `status` | the tasks |
| `store.put_verification` | `verification` | the verification |
| `store.get_verification` | `identity_id`, `organization_id` | the verification, or null |
| `store.list_verifications_in_force` | none | the verifications |
| `store.create_verification_request`, `store.update_verification_request` | `request` | the request |
| `store.get_verification_request` | `request_id` | the request, or null |

A task's template is completed with an `id`, its room and a `created_at`. A
verification and a verification request (§11.7.1, §11.7.2) are taken as
written, with their records' defaults. An
index a store call returns is the store's: the scenarios of `store/` write
no lifecycle record, so it reads as normalized.

### Calls on the status bus, a room's observations and the turn's host

A call `status.<operation>` is the operation of the kit's status bus (§19.8);
`status.post` is its `post_async`, which returns once the bus's subscribers
ran. A call `host.<verb>` is a verb of the turn's host (§10.6.5), made by an
action of a scripted intelligence channel's turn (`on_event`), during the
turn (`do`) or after it (`after_turn`): a runner refuses one made anywhere
else, where no turn's host is.

| Call | Arguments | Result |
|---|---|---|
| `status.post` | `agent_id`, `action`, `status` (a StatusLevel: `ok`, `failed`, `pending`, `info`, `completed`), `detail`, `metadata` | the entry |
| `status.recent` | `n` (default 10), `agent_id`, `status` | the entries, oldest first |
| `status.recent_text` | `n` (default 10) | the newest entries as an agent's context reads them, one line each: `[HH:MM:SS] <agent>: <action> → <status> | “<detail>”`, the agent and the action as identifiers, the detail quoted (§19.8, §6.4); `No activity yet.` for none |
| `update_room_metadata` | `room_id`, `metadata` | the room |
| `submit_feedback` | `room_id`, `rating`, `event_id`, `channel_id`, `comment`, `dimension`, `metadata` | null |
| `list_observations` | `room_id` | the room's observations |
| `list_tasks` | `room_id`, `status` | the room's tasks, of that status when it names one |
| `host.send_event` | as `send_event` | the event |
| `host.post_status` | as `status.post` | null |
| `host.update_room_metadata` | `room_id`, `metadata` | the room |
| `host.add_observation` | `observation`: an observation's template, its `room_id` and `channel_id` given, completed with an `id` and a `created_at` | null |
| `host.delegate` | `room_id`, `agent_id`, `task`, and `delegate`'s `context`, `share_channels`, `notify`, `post_status`, `brief`, `conversation`, `hand_back` | the task's id, which its `as` label names |
| `host.wait_task` | `task_id`, `timeout_ms` (the RFC's `timeout`, in milliseconds; none by default) | `{result, exception}` once the task ended: its DelegatedTaskResult and its failure's error record; null for a task the room's hosts did not delegate, or once `timeout_ms` passed first |
| `host.room_tasks` | none | the turn's room's tasks, as `task_status` reads them (§23.4) |
| `delegate` | `room_id`, `agent_id`, `task`, `wait` (default false), `context`, `share_channels`, `notify`, `post_status` (default true), `brief`, `conversation` (default 0), `hand_back` (default `relay`), `require_structured_result` (default false) and `max_result_retries` (default 3), an inline run's result tool, `submit_result`, served in the child room alone (§23.3) | the task: `id`, `child_room_id`, `parent_room_id`, `agent_id`, `task`, `brief`, `description`, `hand_back`, `status` and `result`, its DelegatedTaskResult once it ended (`task_id`, `child_room_id`, `parent_room_id`, `agent_id`, `status`, `output`, `error`, `duration_ms`, `metadata`); its `as` label names the task's id |
| `task.wait` | `task_id`: a task `delegate` returned, named by its label | its DelegatedTaskResult, once it ended |
| `start_task` | `room_id`, `agent_id`, `task`, `hand_back` (default: the agent's background setup's) | the task, as `delegate` returns it, started for the agent as its `work_in_background` call would (§23.4) |
| `setup_background` | `agent_id`, `worker`, `hand_back` (default `relay`) | null; the agent is given `work_in_background`, served by the room's owner (§23.4, §10.6.5) |
| `setup_task_tools` | `agent_id` | null; the agent is given `task_status` and `cancel_task`, served by the room's owner (§23.4, §10.6.5) |
| `answer_input` | `request_id`, `value` | whether the tool waiting on the human-input request reads the answer (§10.6.5): false for one settled otherwise first, or answered already |
| `reject_input` | `request_id`, `reason` (default empty) | whether the waiting tool reads the rejection, as a refusal (§10.6.5, §9.3) |
| `cancel_task` | `task_id` | whether a background task the kit's task runner held was running and is now cancelled (§23.3); false for any other, or one of a room of another organization than the call's `organization_id` (§17.2) |

The room's members (§5.5, Appendix B.3), each change under the room's lock:

| Call | Arguments | Result |
|---|---|---|
| `ensure_participant` | `room_id`, `channel_id`, `participant_id`, `display_name` | the participant, created reached through the channel, or the room's record of that id with the channel recorded among those it was reached through |
| `resolve_participant` | `room_id`, `participant_id`, `identity_id`, `resolved_by` (default `manual`) | the participant, identified as the stored identity |
| `add_member` | `room_id`, `channel_id`, `participant_id`, `identity_id`, `display_name`, `role` (default `member`) | the member |
| `remove_member` | `room_id`, `participant_id`, `status` (default `left`) | the participant |
| `rename_member` | `room_id`, `participant_id`, `display_name` | the participant |
| `is_member` | `room_id`, `identity_id` | whether an active participant of the room is that identity |

Identity verification (§11.7), each transition of an identity serialized with
its others:

| Call | Arguments | Result |
|---|---|---|
| `request_verification` | `identity_id`, `room_id`, `channel_id`, `method` (default `link`), `window_start` | `{request, secret}`: the request opened (§11.7.2) and its secret, returned once; its `as` label names the request's id, and `<label>.secret` its secret |
| `complete_verification` | `request_id`, `secret`, `method` (default: the request's) | the verification the request completed |
| `record_failed_attempt` | `request_id` | the request, one attempt more, or failed by the last one |
| `revoke_verification` | `identity_id`, `reason` (default `revoked`) | the verification ended, or null when none was in force |
| `verification_of` | `identity_id` | the identity's verification as it stands now, unverified for none (§11.7.1) |
| `check_verifications` | none | the verifications whose time had passed, which it ended (§11.7.5) |
| `sender_verification` | none: an action of a scripted hook, it reads the event and the context the hook was handed | the verification of the event's sender in the room's organization, or null when the pipeline did not label the event (§11.7.3) |

A verification's expiry and a request's are timers: a scenario waits for one
through a gate of a hook on `on_verification_ended`, never through a delay.

**References.** A string argument may name what the run made:

- `$room`, `$event`: in an action, the room of the hook's or the channel's
  context, and the event it runs for;
- `$r1`, `$r2`...: the rooms the run created that the scenario does not name,
  in the order of their `room_created`;
- `<room>#<index>`: the event at that index of the room's timeline as it
  stands when the call is made, read as Normalization reads it;
- `$<label>`: the event the call labelled `<label>` returned, the task's
  id for a `delegate`;
- `$<label>.secret`: the secret of the verification request the call
  labelled `<label>` opened;
- `$request`: in an action of a hook on `on_user_input_required`, the id of
  the request the hook was handed;
- `$p1`, `$p2`...: the human-input requests the run raised, in the order it
  first showed them (a hook's payload, a `user_input_required` framework
  event).

### Expectations

`expect` names what is compared; what it does not name is not.

| Member | What is compared |
|---|---|
| `timeline` | Per room, the whole timeline in index order, `BLOCKED` records included, lifecycle records left out |
| `rooms`, `bindings` | Per room, the room record; per room and channel, the binding, `null` for none |
| `framework_events` | Per room (`*` for the events of no room), every framework event of the §26.1 table and `process_timeout`, and of the Level 2 features the suite exercises, `status_posted` (§19.8) and `feedback` (§15.9), identity resolution's `identity_resolved` and `identity_timeout` (§8.2), a human-input request's `user_input_required` (§9.3), and identity verification's `verification_requested`, `verification_completed` and `verification_ended` (§8.2, §11.7), and a delivery lane's `delivery_skipped` (§8.2, §13.5), in emission order |
| `hooks` | Per scripted hook, its calls in order: `trigger`, `room_id`, `event` (the payload, when an event), `context_room` (the room supplied to an event or session hook, captured on entry), `tool_call` (the payload, when a tool call: `name`, `tool_call_id`, `arguments` as the call runs or was stopped with, and, on `on_tool_call`, `result` as the model reads it, `is_error`, `refused`, `cancelled` and `error_detail`), `delivery_status` (the payload, when a delivery status, §10.4), `status_entry` (the payload, when a status entry: `on_status_posted`), `dispatch_decision` (the payload, on `on_dispatch_decision`: `room_id`, `event`, `candidates`, `decision` as `{agents, reason, judgments}`, `duration_ms`), `observation` (the payload, when an observation: `on_feedback`), `request` (the payload, when a human-input request: `pending_id`, `tool_name`, `arguments`, `room_id`, `tool_call_id`, `channel_id`, `channel_type`, `actor_id`), `identity_result` (what an identity hook is handed, §11.2), `generation` (the payload, on `before_ai_generation`: `channel_id`, `provider_name`, `purpose`, `trigger` the event the turn answers, and its context's `system_prompt`, `messages` as `models` reads them and the names of its `tools`), `tool_round` (on `after_tool_round`: `channel_id`, `round_index`, its `calls`, each `{tool_call_id, name, arguments, metadata, partial, garbled}`, its `results` as `models` reads them, and the names of the turn's `tools`), `response` (on `on_ai_response`: `channel_id`, `response_content`, `segments`, `tool_calls_count`, `round_count`, `loop_end_reason`, `usage`, `streaming`, `thinking`, and `declared_tools`, by name: `position`, `description`, `parameters`, `origin`) |
| `hook_order` | The order in which the hooks it lists were called, a scripted channel's room callbacks among them (`<id>.on_room_attached`, `<id>.on_room_detached`) |
| `room_callbacks` | Per room and scripted channel, its room callbacks (§6.1) in order: `{"call": "on_room_attached", "binding": ...}`, the binding it was handed, or `{"call": "on_room_detached"}` |
| `deliveries` | Per room and channel, the events a scripted channel's `deliver()` received, as delivered, in order |
| `contexts` | Per room and scripted channel, the context each of its `deliver()` calls and, for an intelligence channel, each of its turns (`on_event()`) was handed, in order: `call` (`deliver` or `on_event`) and `recent_events`, the ids of its events read as Normalization reads them, lifecycle records left out |
| `text_events` | Per room, a minted one's as `$r1`, the `text_delta` ephemeral events the room's realtime is handed, in order: each `{text, round, channel_id}` (§6.4) |
| `thinking_events` | Per room, the `thinking_start`, `thinking_delta` and `thinking_end` ephemeral events its subscribers read, in order: each `{type, thinking_length, round, channel_id}`, and `thinking` for an agent with `publish_thinking_text` |
| `tool_events` | Per room, the `tool_call_start`, `tool_call_end` and `tool_call_delta` ephemeral events its subscribers read, in order: each `{type, tool_calls, round, channel_id}`, and `duration_ms` for an end that ran its calls (§6.4, §8.4) |
| `presence_events` | Per room, the `presence_online` and `presence_offline` ephemeral events its subscribers read during the steps, in order: each `{type, user_id}`, `user_id` the agent's channel id (§10.6.7, §8.4) |
| `streamed` | Per room and streaming channel, the items its `deliver_stream` read, in order: `{"text": ...}` for a text delta, `{"thinking": ...}` for a piece of the model's reasoning, `{"usage": ..., "model": ..., "provider": ...}` for what a generation used, when the channel `reads_usage`, `{"row": event}` for a row the store holds, `{"loop_end": {"reason", "rounds", "usage"}}` for the turn's end, when the channel `reads_loop_end`, `{"failed": true}` where the stream raised |
| `turns` | Per room and intelligence channel, the events its `on_event()` received |
| `ingested` | Per room and scripted agent with a scripted `memory`, the events its memory was handed (§20, `ingest`), in order, matched as the timeline's |
| `compacted` | Per room and scripted agent with a scripted `memory`, the compactions between two tool rounds its memory was asked (§6.4, §20.1, `compact`), in order: each `{history, usage}`, `history` the messages it was handed, each as `models` reads a request's (`{role, text, parts, round}`), `usage` the round's token counters |
| `dispatch_turns` | Per setup strategy with a scripted `dispatch`, the turns its policy was handed (§19.7.5 rule 18), in order: `room_id`, `event` and `recent`, matched as the timeline's events, `speakers`, each `[event id, label]` in the order of `recent` then `event`, `candidates`, each `{channel_id, name, role, description, handle}`, and `asked` |
| `observations`, `tasks` | Per room, the stored side effects |
| `actions` | Per action label, the outcomes of its runs, in the order they ended |
| `ai_events` | Per room, the framework events of an AI channel's turn (§8.2, Level 1): `before_ai_generation` and `ai_response`, in emission order, matched as `framework_events`, which does not hold them |
| `models` | Per scripted agent, each generation's `method` (`generate` or `generate_structured_stream`, recorded at the actual script reservation; absent for native Rust memory summarizers), and its request as its model received it, in order: the `messages` it carries, each `{role, text, parts, round}`, `text` its text parts joined (empty for a message with none, a tool's result among them), `parts` its text and image parts in order, each `{"text": ...}` or `{"image": url, "mime_type": ...}`, null for a message whose content is a text, `round` its reasoning, text and call parts in order, each `{"thinking": ..., "signature": ..., "redacted": ...}`, `{"text": ...}` or `{"call": id, "arguments": ..., "metadata": ...}`, null for a message whose content is a text, and the `tool_results`, each `{tool_call_id, name, content, is_error, references}`, `name` the tool of its call, `content` as the model reads it (a text, or a result's text and image parts in order, written as `parts` are), `is_error` whether it reads the call as failed, its `system_prompt`, its `temperature` and `max_tokens`, its `reasoning_effort`, `thinking_budget` and `enable_thinking`, its `response_schema` (null for none), the `deferred_tools` names held unseen, the `reopened_tools` names referenced by synthetic opening exchanges, the `tools` it declares, by name: each one's position in the declaration, so that a scenario names those it asserts, declared or `$absent`, and, for a model with a `chat_dialect`, `chat_messages`: the request as that rendering writes it on the wire, its system prompt first when it has one, each message's `role`, `content`, `tool_calls`, `tool_call_id` and its dialect's reasoning field |
| `acp_wire` | Per ACP channel, the requests and notifications its scripted ACP agent received, in order, each `{method, params}` (Scripted ACP agents) |
| `executors` | Per executor of the setup, what it did, in order: `{call, channel_id, build}`, and `room_id` for a call about a room: `built` (a copy of the channel made, `build` counting them per executor and channel), `on_event`, `on_room_attached`, `on_room_detached`, `channel_call` (with its `verb`) and `close`. A detach from a room this build never saw let go of nothing and is not listed |
| `lifecycle` | Per room, the lifecycle records (§5.1) in index order, when the implementation writes them: an implementation that writes none passes. It says which changes write one, and which write none (a change that changes nothing, §7.2) |
| `participants` | Per room, the participants the store holds (§5.5), in the store's order |
| `ai_routes` | Per scripted agent with a `router`, each request its router was asked, in order (§6.4): `reason` (`turn` at a turn's start, `retry` once a generation's retries are spent), `text` (what the turn answers, as text: the text of the event it answers), `previous` (for a retry, the model whose retries are spent, named as `models` names it; null at a turn's start) and `failed` (for a retry, the last refusal as `{status, message}`; null at a turn's start) |
| `router_calls` | The custom inbound router calls in order: `{channel_id, channel_type, participant_id, channel_data, organization_id, identity_id}`; absent identity, organization and sender are null |
| `resolver` | The scripted resolver's calls, in order |
| `media_resolver` | The kit's media resolver's calls, in order: `{url, room_id}` |
| `tool_audit`, `session_audit` | The run's tool auditor's and session auditor's entries, in the order each recorded them, each entry's members (§15.8.3: a tool entry's `ts`, `agent_id`, `tool_name`, `arguments`, `result`, `status`, `duration_ms`, `metadata`; a session entry's `ts`, `type`, `role`, `content`, `duration_ms`, `metadata`); the runner also checks that the auditor's JSONL file holds one line per entry, those members |

An outcome is `{"result": ...}`, matched as below, or `{"error": name}` (or
`{"error": {"name": ..., "reason": ...}}`). A call whose outcome names neither
must not fail. An action with no `expect` must not fail either, unless
`expect.actions` checks its label.

Each runner also checks, for every scenario, that no lifecycle record was
delivered or handed to a turn (§5.1), and that each room's indexes, read as
stored, are given out once each (§8.1).

A member a runner does not know fails the scenario before it runs: a top-level
member, an expectation, a step of no known kind, a call's argument, a
reaction's, a hook's or a channel's member, an outcome's. Records in the
serialized form (messages, contents, templates, capabilities) are each
implementation's to read.

### Normalization

Before matching, a runner rewrites what changes from run to run, and what
the RFC leaves to each implementation:

- **Lifecycle records** (§5.1: the framework's source, the visibility
  `internal`, a system content) MAY be written, so they are left out of the
  timelines (`lifecycle` compares them), and every index is read without
  them: an index loses one for each lifecycle record at or below it. That
  holds for an event's `index` (an instruction's provisional index too) and a
  room's `latest_index` (null when it reaches below 0) and `delivered_index`
  (-1 at least), and a `delivery_skipped`'s `from_index` and `to_index`; a
  room's `event_count` loses one for each lifecycle record below it. Every other gap stays: a hard delete leaves its index given out
  (§8.1). Appendix B counts the same way.
- **Rooms** the run created and the scenario does not name are `$r1`, `$r2`...
  in the order of their `room_created`. In `rooms`, the key `$created` reads
  their records as one list in that order, for a `$unordered` match where
  the RFC leaves the order of their creation open (rooms created side by
  side).
- **Events** of a timeline are `<room>#<index>`, its index read as above,
  wherever their id appears, an object's key included.
  Any other event id (an instruction, a refused event, an event a hard delete
  removed) is `$e1`, `$e2`... in the order the step outcomes, then the
  framework events, show it first. A participant's or an identity's `id`
  is the scenario's own, kept as written.
- **Human-input requests** are `$p1`, `$p2`... wherever their id appears, in
  the order the run first showed them.
- **Instants** (an RFC 3339 string) are `@1`, `@2`... by their order among the
  run's instants, equal ones alike.
- A **framework event** is an object: `event`, its name, and the members its row
  of the §8.2 table names, a `data.x` member under `data`.

### Matching

An expectation matches the actual value when:

- an object: each member it names matches the actual's member, an absent
  member reading as null; the actual's other members are not compared;
- a list: the actual has as many items, each matching in order;
- a scalar: equal, numbers by value;
- `"$any"`: anything, absent included;
- `{"$unordered": [...]}`: a list of as many items, matching in some order;
  in a room's `framework_events`, as many consecutive events in any order;
  in `actions`, the outcomes in any order;
- `{"$absent": true}`: absent or null; `{"$present": true}`: neither;
- `{"$contains": "text"}`: a string holding the text;
- `{"$starts_with": "text"}`: a string beginning with the text;
- `{"$lacks": "text"}`: a string not holding the text;
- `{"$as": "name"}`: a value present, named: across the scenario's step
  expectations and its `expect`, every `$as` of one name matches equal
  values, and `$as` of two names never match equal values. It compares what
  a run gives out with itself (a `correlation_id`). A name is a string,
  held by the first value it matches; within a `$unordered`, by the order
  that matches. The runners compare `expect`'s members in orders of their
  own, so a name that a `$unordered` group or an `actions` label in any
  order holds is matched in no other member.

In `framework_events` a bare string names the event: `"room_created"` is
`{"event": "room_created"}`.

## Errors

A call's error is named by what it means in the RFC, never by an
implementation's class. A runner maps its errors with the table below, which
extends roomkit-rs `docs/rfc-gaps.md` G-085's; an error that maps to no name
fails the scenario. A runner reads a call's arguments before it makes the call,
and an argument it cannot read (a typo in the scenario) fails the scenario: it
is never an `invalid_argument`. Only a refusal of the implementation's own
validators is (roomkit: a pydantic `value_error`; roomkit-rs: a value type that
refuses its value, a `ChannelId`).

| Name | RFC meaning | roomkit (Python) | roomkit-rs |
|---|---|---|---|
| `kit_closed` | A new operation refused once the kit's shutdown started (§12.10.4) | `KitClosedError` | `RoomKitError::KitClosed` |
| `invalid_argument` | An argument refused before anything is read or written: the visibility `internal` (§7.3), a channel id the grammar refuses (§7.3), `standalone` on another type and an instruction's refusals on a direct injection (§10.1.1), a record naming another room (§10.5), a post from a channel that is not a host channel, a message on a host channel (§10.5), a host channel bound as an intelligence channel, a reserved room metadata key (§5.1), a hook registration §9.1 refuses, a tool set up on an agent under a name it serves already (§21.1), a strategy for a room that holds one, or that the strategy refuses (§19.7), `listen_only` or `talk_again` for a room holding no discussion (§19.7.5) | `ValueError` | `InboundError::{NotAHostChannel, InboundOnHostChannel, HostAsIntelligence, StandaloneOutsideInstruction, InternalVisibility}`, `Refused` with an instruction's reason, `LifecycleError::{InternalVisibility, HostAsIntelligence, ReservedMetadataKey}`, `MutationError::OtherRoom`, `KitError::{Config, Registration}`, `RoomKitError::ToolNameCollision`, a `ChannelId` refused |
| `channel_not_registered` | The channel named is not registered (§10.1 step 1, §10.5) | `ChannelNotRegisteredError` | `InboundError::UnknownChannel`, `KitError::UnknownChannel` |
| `room_not_found` | No such room, or another organization's (§17.2) | `RoomNotFoundError` | `InboundError::{RoomNotFound, OtherOrganization}`, `LifecycleError::RoomNotFound`, `MutationError::RoomNotFound` |
| `channel_not_bound` | The room does not bind the channel: a direct injection or a post from it (§10.5), a detach or a binding change of it (§7.2) | `ChannelNotFoundError`; `detach_channel()` answering `False` | `Refused { reason: "source_unbound" }`, `LifecycleError::ChannelNotBound` |
| `room_closed` | The room's status refuses new events (§5.1) | `RoomClosedError` | `Refused { reason: "room_closed" }`, `MutationError::Refused` |
| `transition_refused` | A transition from a status it does not leave from (§5.1) | `TransitionRefusedError` | `LifecycleError::TransitionRefused` |
| `change_refused` | An edit or a delete step 8a refuses, with its `reason` (§10.1 step 8a, §10.5) | `ChangeRefusedError` | `Refused` with one of step 8a's reasons |
| `process_timeout` | `process_timeout` passed before the commit (§13.6) | `ProcessTimeoutError` | `Refused { reason: "process_timeout" }` |
| `participant_not_found` | A post's speaker is no participant the host channel reaches (§10.5); a member call names no participant of the room (§5.5) | `ParticipantNotFoundError` | `InboundError::ParticipantNotFound`, `RoomKitError::ParticipantNotFound` |
| `identity_not_found` | No such identity, or another organization's (§5.6, §17.2) | `IdentityNotFoundError` | `RoomKitError::IdentityNotFound` |
| `reentrant` | A message routed back into the room whose lock or admission order its caller holds (§9.5.1 A message routed back) | `ReentrantCallError` | `KitError::Reentrant` |
| `waits_for_itself` | A completion handle's cancel from the room's lane or under its lock, where its cleanup would wait for its caller (§10.1 step 18) | `RuntimeError` from `DeliveryHandle.cancel` | `RoomKitError::Runtime` from `DeliveryHandle::cancel` |
| `reentry_loop_cap` | A direct change past its cascade's hook calls (§8.3, §10.3) | `ReentryLoopCapError` | `MutationError::ReentryLoopCap` |
| `idempotency_key_taken` | A direct record or store write tries another event under a key its source channel holds in the room (§13.4, §14.3) | `IdempotencyKeyTakenError` | `RoomKitError::IdempotencyKeyTaken`, `StoreError::IdempotencyKeyTaken` |
| `event_not_found` | A write naming an event its room does not hold: a change's target, `update_event` (§14.3) | `EventNotFoundError` | `StoreError::EventNotFound` |
| `task_not_found` | An update of a task the store does not hold (§14.3) | `TaskNotFoundError` | `StoreError::TaskNotFound` |
| `verification_refused` | A verification request refused, with its `reason`: `not_found` (none in the caller's organization), `not_open`, `expired`, `mismatch` (a wrong secret, counted) or `failed` (the last attempt) (§11.7.2) | `VerificationRefusedError` | `RoomKitError::VerificationRefused` |
| `channel_failed` | A channel's own error, which the caller is handed (§6.1): a transport's `on_room_attached` refusing an attach, its `on_room_detached` failing a detach | the scripted channel's failure, raised as it is | `RoomKitError::Channel` |
| `kind_not_stored` | `room_strategy_is_current` asked of a kind of strategy that is not stored with the room (§19.7.5 rule 16) | `TypeError` | `RoomKitError::Type` |
| `turn_link` | A turn, channel call or event no executor could carry, with its `reason`: `no_executor` (§10.6.7), `executor_lost`, `backend_closed` (§10.6.8) | `TurnLinkError` | `RoomKitError::TurnLink` |
| `already_set_up` | A handoff's tool set up again where it is declared, or an install over an agent whose handoff is set up already (§19.6); `delegate_task` set up again on an agent (§23.4) | `RuntimeError`, `setup_handoff() already called`, `setup_delegation() already called` | `RoomKitError::Runtime` |

## Reentrancy cells

A call into room R depends on where its caller's execution context stands in R
(§9.5.1, §13.5, §10.5, §10.3). The suite names the cells of that table
`<call>@<place>`, and a scenario lists those it exercises in `reentrancy`:

| Call \ place | `locked`: under R's lock (a locked hook) | `admitted`: in R's admission order (an off-lock hook's body, a message's parse) | `cascade`: R's work outside the lock (a turn, a delivery, an ASYNC hook's body) | `outside`: anywhere else |
|---|---|---|---|---|
| `inject`: `send_event`, `post`, `process_inbound` naming R | adopted, committed ahead of the section's event | adopted beside the work, committed ahead of its event | a new arrival on the delivering cascade's budget, answered at its decision, at least as deep as the turn's answer | a new arrival |
| `routed`: `process_inbound` routed back into R | fails at once (`reentrant`) | fails at once (`reentrant`) | a new arrival | routed as any message |
| `commit`: `commit_event`, a lifecycle change | takes the lock again at once | waits for the lock | waits for the lock | waits for the lock |
| `change`: `update_event`, `delete_event` | takes the lock again at once, drawing nothing | waits for the lock, drawing nothing | from an ASYNC hook's body, draws one of the cascade's hook calls, `reentry_loop_cap` past them | its own budget |

Timing races (a caller that stops waiting, cancellation, concurrent sections
at one instant) stay in each implementation's own tests.

## Coverage

The [generated traceability report](coverage.md) contains the current scenario
count and RFC inventory, and exposes unreviewed candidate scenarios, reviewed
partial mappings and missing evidence. Its JSON counterpart records the exact
scope and execution states. A section citation is navigation, not a proof.

Follow [TRACEABILITY.md](TRACEABILITY.md) to annotate a clause, review an
assertion link, retain a run or regenerate artifacts. The CI checks the scenario
schema, reference resolution, stable ID history, source and evidence fingerprints,
implementation provenance, and generated-file drift. It runs the checker's
regression tests; it does not rerun the framework suites or certify Rust parity.

The table/cell checks described above remain useful targeted checks. They are
not an exhaustive assertion-level assessment of the RFC. Unmapped units may
already have tests whose exact assertions have not been reviewed. Broad source
units must be decomposed before claiming their complete coverage.

## Waiting for the kit to go idle

Each runner waits for the framework work its scenario started before comparing
final state. Pending deliveries, observers and held tasks must remain visible
to that wait; a run that reports success before they finish is not evidence of
the final state. Timing races remain in the implementation tests.

## On a distributed turn backend

A runner may run the suite with every turn crossing a distributed backend's
transport, the kit's own executor reached as one elsewhere. roomkit's is
`ROOMKIT_TEST_TURN_BACKEND=redis REDIS_URL=... uv run pytest tests/conformance`,
which its CI runs. It skips what a transport cannot give the runner, each
with its reason in `tests/conformance/test_conformance.py`: a scripted turn
that calls the kit it holds (across a backend a turn reaches its room through
its host, `host.*`), an ASYNC hook whose timeout falls after its turn, and a
tool answering right after its turn's cut.

## Known failures

A known failure is a scenario whose observable result breaks the RFC. Its
runner names the scenario and broken rule at an implementation revision
(roomkit's `KNOWN_FAILURES` in `tests/conformance/test_conformance.py`,
roomkit-rs's lists in `crates/roomkit/tests/conformance/main.rs`; its shared
loop, `scenarios.rs`, reports the `executors/` area without running it, having
no executor beside the kit). Strict
expected failures fail the suite when they start passing; timing exceptions
can pass on a particular run. Neither exception policy establishes conformity.

Read each runner's exception lists at the implementation commit being assessed,
including runtime-specific lists such as Rust's several-worker exceptions. A
suite can exit successfully while expected failures remain. The traceability
report records only explicit receipts and never promotes an expected failure
or a skip to a passing result.

## Writing a scenario

- Expect what the RFC says, not what an implementation does. Where the RFC
  leaves a point open (the order of two framework events no rule orders, which
  of two concurrent deliveries ends first, a lifecycle record, a counter that
  counts lifecycle records), do not assert it: use `$unordered`, or leave the
  member out.
- Cite each rule the scenario relies on in `rules`, as precisely as the RFC
  allows; `check.py` must resolve it.
- Give every member you assert in a template, and a reason to every block.
- Hold on every runtime: a runner on one thread and one on several
  (roomkit-rs runs the suite on both) give the same outcomes. Two things
  that run side by side end, and start, in either order on several threads:
  assert their order only where the RFC gives one.
- Keep timing out of it: a gate orders two calls, never a delay. A hook's or a
  call's timeout, when the scenario is about it, must leave enough margin for
  any work expected to complete within the same budget, including store I/O
  and CI scheduling. Hold the worker expected to time out at a gate no step
  opens. A short timeout is suitable only when no successful work races it;
  the parallel-team and supervised-step timeout scenarios use 2 s (RMK-1331),
  including the supervisor's task-framing pass. Real-time scenarios
  still depend on the runner making progress within their budgets.
- Run `check.py --fix`, then both runners, before committing. A scenario that
  fails on an implementation is either wrong, and fixed, or a known failure,
  listed above with its probe.

A scripted round's `stream` also accepts `{tool_call_delta: {id, name, index, arguments_delta}}`,
with index 0 and empty arguments by default. A `refuses` or `fails` after an
explicit stream comes before its done event, or after it with `failure_after_done`.
