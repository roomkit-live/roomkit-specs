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
| `evidence.json`, `inventory.json` | Reviewed links, execution receipts and source inventory reviews; a receipt's results are read from its report under `executions/` |
| `links.lock.json`, `untested.json` | Each scenario citation pinned to its unit's text; the reason a unit has no scenario |
| `gaps.json` | The decided gaps: units a scenario can test and none cites yet, each with its class and card; the process rule accepts them |
| `rules/` | Generated per-rule report: each unit, its citing scenarios and their latest results |
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
python3 conformance/check.py --strict   # coverage gaps and lock drift are errors too
python3 conformance/check.py --pin RK-10.4-022   # re-pin a unit's citations after reading them
python3 conformance/check.py --changed-units --base-ref <full sha>   # the process rule
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
    with that bold label, and the numbered item after it;
- each entry of its `requirements` names a unit of the current `roomkit-rfc.md`
  that is neither retired nor `non_testable`, and `links.lock.json` pins it to
  the unit's current text ([TRACEABILITY.md](TRACEABILITY.md), "Citing units").

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

A scenario can list the features it needs in `requires_features`. The defined
names are `message_session`, `protocol_trace`, `voice`, `realtime`,
`conference`, `video`, `recording`, `executor_media`, `scoring` and
`source_provider`.
`executor_media` requires a standalone executor that accepts both host media
readers (§10.6.2). `scoring` requires a turn scoring hook that can attach to a
kit or a standalone executor (§10.6.6). `source_provider` requires scripted
sources on the source interface (§6.5), attached to the kit (`sources`,
below). Three more names are reserved for the
decided gaps that need them; no scenario uses them yet, so neither the schema
nor a runner lists them:
`transport_provider`, the implementation's own channel of a platform type
(Appendix A) over a scripted provider that implements that type's provider
interface; `websocket_channel`, the implementation's WebSocket channel and its
connection registry (§8.2); and `classifier_dispatch`, a step that asks a
scripted classifier its questions (§6.8). The corpus never drives a vendor's
provider, and no feature names one: what a provider reads and writes on its
vendor's wire is proven by that provider's own tests, outside roomkit's
conformance. `untested.json` names none of them: for each unit it says what
the core guarantees and which tests prove it, on roomkit's mocks, scripted
providers and built-in defaults, or that the unit has no core side. Each
runner declares the features it provides. Before setup, it reports the
scenario skipped if any are missing, naming the missing features in its test
result. With the member absent, the scenario runs without a feature
prerequisite.

### Setup

Made before anything is recorded: framework events, hook calls, deliveries and
room callbacks of the setup are not compared.

- `kit`: `max_chain_depth` (default 5), `process_timeout_ms` (the
  implementation's default when absent), `close_grace_ms`, the one grace the
  kit's close gives its running work from its start before it cuts it
  (§12.10.4, the kit's `close_grace`; the implementation's default, 5 s, when
  absent), and `router`, a scripted router in
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
  retry and those its worker holds; and `turn_timeouts`, the bounds of the
  kit's turns (§10.6.8), with or without `executors`, as `executors` below
  says; and `verification_policy`, the kit's
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
  `lock_manager`: `{"kind": "memory"}` explicitly selects the in-memory
  lock manager, including on a durable store, for fixtures requiring a controlled
  FIFO wait queue. With `release_error`, its release fails while a
  `lock_releases` step has set it failing, as a distributed lock that finds its
  lease expired. Absent, the runner keeps its normal manager. Also,
  `delivery_gap_timeout_ms`, how long a delivery lane waits on a cursor hole
  no lane runs before it skips it (the implementation's default when
  absent); and `inbound_rate_limit`, the kit's inbound rate limit
  (`max_per_second`, `max_per_minute`, `max_per_hour`): a bucket of tokens
  per channel, full at first and holding at least one, refilled at the most
  precise bound's rate, a message past it refused before anything is read
  or written; and `persistence_policy`, the kit's persistence policy
  (`persist_types`, `exclude_types`, each a list of event types): what the
  kit's commits store, every type when absent, `exclude_types` winning over
  `persist_types`; and `store_faults: true`, the kit built over the run's
  store wrapped so that `store_fault` steps make its operations fail or
  hold, every operation the store's own otherwise; a runner runs such a
  scenario on each store it ships; and `store_owner`, who owns the run's
  store, which the kit is then built over wrapped as `store_faults` wraps
  it (§12.10.4): `kit`, a store the kit's close closes, every operation made
  after its close failing as a closed store's own failure (roomkit's
  `RuntimeError`, roomkit-rs's `StoreError::Unavailable`), or `integrator`,
  a store the kit's close leaves open, as a pool the integrator handed in; a
  `store.<operation>` call reaches it before the kit's close and after it,
  and the runner's own reads once the steps ran read what it holds.
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
  - `close` holds the reactions of its close (§6.1, §12.10.4): every
    scripted channel records each call of its close under `channel_closes`,
    then reacts (`spawn`, `gate`, `do`, then `fail`, the close's failure,
    which roomkit raises and roomkit-rs, whose close returns nothing,
    panics with); with no reaction it does nothing;
  - `update_binding: {}` enables its synchronous binding callback recorder (§7.2).
    Each call records `{"call": "update_binding", "binding": ...}` under
    `room_callbacks`, and `<id>.update_binding` in `hook_order`. An optional
    `fail` string raises the scripted channel failure after recording. No
    asynchronous reactions are accepted. Without this fixture the default
    callback does nothing;
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
    rounds and its usage (§6.4), which it skips otherwise; its
    `deliver_cut` records the end of a stream cut from outside, the row it
    is handed (§6.1, §12.2 step 13s);
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
  - with `addressing`, its address methods are the implementation's own for
    a transport channel of its type (§5.7, §10.4), in place of the defaults:
    they write an address in the type's form, read a message's chat under
    the type's chat key, and name and read the recipient under the type's
    recipient key, the defaults of §5.7's table; its `country_code`, when
    it names one, is the country code the channel declares, written with or
    without its `+`, and a code the implementation refuses refuses the
    channel's registration (`invalid_argument`). A channel with
    `addressing` takes neither `recipient_key` nor `addresses`, and is
    neither a host channel, a scripted agent nor an ACP channel;
  - with `sender_is_participant`, it names its own senders: its inbound
    `sender_id` is a room's `Participant.id`, which no resolver is asked
    about (§11.6);
  - with `verbs`, its per-room verbs (§10.6.3), by name: `keeps` merges the
    call's arguments into what this build keeps for the room and answers
    that, `reads` answers it, `result` is answered as written; what it keeps
    is the room's state of §10.6.2, dropped by `on_room_detached`.
    A `gate` holds before any change; `forgets` clears the state after
    `keeps`; `do` runs actions in the calling context; `fail` raises the scripted failure after changes and before
    answering (the Python harness declares that exception for reconstruction);
  - with `declared`, the kit holds it by its declaration alone, and the
    executors of `executors` that host it build it (below);
  - with `holds_end`, a gate, on an intelligence channel or a scripted
    agent: each of its turns that its owner cuts, sending the turn's
    executor a `close` or a `cancel` (§10.6.8), owes its `end` until a step
    opens that gate. The executor applies the cut as it does any; the run's
    turn backend hands the owner the turn's `end` only once the gate is
    open, and a turn never cut has its `end` handed at once. Its executor,
    having ended the turn, beats no more meanwhile: an owner whose
    `heartbeat_timeout` passes first loses the turn (`executor_lost`). A
    runner holds the end at the transport the kit is built with: roomkit-rs's
    distributed-turn executor pass, whose transport is its own, refuses the
    member.
    `expect.turn_ends` reads what became of each turn so held;
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
  hook (`add_room_hook`) may have one too. A hook with `as` in place of
  `name` is registered with no name, the name the implementation gives it
  its own (§9.1): `as` is the label its calls are recorded under, in
  `hooks` and `hook_order`, never a name it is registered with. A room's
  hook may have one too.
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
  builds nothing), `organizations`, the organizations whose rooms it serves
  (each an exact organization id, `*` for every one; absent, the rooms
  without an organization alone), `max_channels`, how many it keeps built at
  most (no bound when absent), the
  `hooks` it registers and the `room_hooks` it defines on triggers a turn
  fires (§10.6.6), `started` (default true; false: served only by an
  `executor.start` step), `answers` (default true; false: it takes each
  turn it is given and never answers it, `gate` naming a gate it reaches as it
  takes one, for a `wait_for` step) and `own_process` (default false; true: it
  runs as in a process of its own, on a thread and an event loop of its own,
  over a node of its own of a distributed turn backend, so that the work of
  its turns stalls nothing beside it, §10.6.8; it registers no hook and
  answers its turns, and the channels it hosts are scripted channels
  holding only their turn (`on_event`), whose reactions hold no gate and
  make no action other than a `host.<verb>`, what the run's gates and
  records share staying on the run's own loop; `executor.kill`,
  `executor.pause`, `executor.resume` and `channel.publish` do not name it;
  a runner that cannot run it so skips the scenario: roomkit outside its
  distributed turn mode, roomkit-rs outside its distributed-turn executor
  pass). The channels it runs are the ones
  the setup marks `declared`: each executor builds its own copy, and a
  scripted agent answers from the one model of its channel id, whichever
  executor runs its turn. `kit.turn_timeouts` gives the bounds of a turn
  (§10.6.8): `accept_ms`, `heartbeat_interval_ms`, `heartbeat_timeout_ms` and
  `cancel_ms`, the implementation's default for each absent. Which of several
  executors declaring a channel takes a room's first turn is the backend's
  to choose (§10.6.7): a scenario that needs one starts the other afterwards.
  Each executor can take `media_resolver` and `attached_media` using the
  same shapes as the kit. The readers belong to the site that configured them.
  The kit and each executor can set `telemetry: true` to record spans locally.
  At either site, `scoring: true` attaches the implementation's scoring hook
  with a scorer that gives each response a score of 1.0 on the `default`
  dimension. The observation reaches the room owner through the turn host.
  Their `error_classes` lists name the synthetic application classes they
  rebuild. A per-room verb's `raises_class` raises a fresh instance.
  `DetailError` renders its message from an opaque local field.
  `HostProviderError` extends the provider error and carries a provider name
  and status code (§10.6.8).
  When a scenario combines `executors` and `processes`, every owner connects
  independently to the same distributed turn backend. An executor's `kit`
  selects the process serving it (`main` is reserved for the run's kit). An explicit
  `hosts` list is advertised. With `host_predicate` the executor accepts the
  exact ids in that list locally. Omitting both accepts every id locally.
  `kit.shared_realtime` gives the owners independent connections to one
  realtime bus. `kit.executor_catalogue: false` supplies a transport that
  omits the optional catalogue. `kit.turn_backend_faults` enables the
  scripted failures described alongside `turn_backend.fault`.
- `sources`: each a **scripted source** (§6.5), attached to the kit for its
  `channel_id`, a channel of the setup, after the rooms, with its
  `auto_restart` (default false) and `restart_delay_ms` (the
  implementation's default when absent); `start`, `stop` and
  `healthcheck` hold the reactions of those methods (`gate`, `do`, `spawn`,
  `fail`): its start, once its reaction ran, reads until it is cut; its
  health check answers the source's health once its reaction ran. It records
  each call of its `stop` and `healthcheck`, and each of its `start` once
  the setup is made, under `sources`, and `cut` when its start's task is
  cut. A scenario that has `sources` requires `source_provider`.
- `event_handlers`: **framework-event handlers** (§8.2), each registered on
  the kit after the hooks, in order, for the events of its `event` type (a
  framework event's name: `before_tool_use`, `tool_call`, `ai_response`...).
  It records nothing, and reacts to each event with the first of its
  `reactions` whose `when` holds (`room_id`, the event's room), used once
  unless it has `"repeat": true`: it holds at the reaction's `gate`, then
  makes its `do` actions in order, in the execution context the kit runs the
  handler in, `$room` naming the event's room (only for an event that names
  one).

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
| `delay_ms` | Waits this many milliseconds after the gate and before the actions, to separate the start of nested call deadlines; absent or zero, no delay |
| `holds_cpu_ms` | Keeps the thread running the call busy for this many milliseconds, once its actions returned and before its `after_do_gate`, yielding nothing to its event loop meanwhile, as work busy with its CPU does (§10.6.8) |
| `do` | Kit calls the hook or the channel makes while it runs, in its execution context, in order: an **action** is a call (below) with an optional `as` and `expect`, and with `own_task: true`, made on a task of its own, started in the acting code's execution context (roomkit: `asyncio.create_task`; roomkit-rs: `tokio::spawn` of `keep_context`), which the action awaits: a cut of the acting code cuts that wait, not the task. Its error is caught, kept and checked, never raised into the kit |
| `after_do_gate` | Holds after all `do` actions returned, before `after_turn` work and the reaction's result or failure; lets steps observe completed work without a delay |
| `spawn` | Once `writes_record` is written and before its `gate`: starts a task, which the call does not wait for, that holds at the spawn's `gate`, waits its `delay_ms`, makes its `do` actions in order and holds at its `after_do_gate`, each as a reaction's. The task is started in the call's execution context, as the implementation's own spawn keeps it (roomkit: `asyncio.create_task`; roomkit-rs: `tokio::spawn` of `keep_context`), so that it acts for the call while the call runs and outlives it (§9.5.1 Reentrance). A runner waits for the task when it waits for the kit to go idle |
| `on_cut` | In an `on_event` reaction: actions the reacting code makes as its cleanup once the turn it runs in is cut (§12.10.4), in its execution context, in order: roomkit makes them as the cut unwinds the call, roomkit-rs, whose cut drops the call's future and runs no async cleanup in it, on a task a guard the call holds starts with `keep_context` as it drops. A runner waits for that work when it waits for the kit to go idle |
| `after_turn` | In an `on_event` reaction: actions the turn leaves to work it began, a task in the turn's execution context that makes them in order once the turn ended (§10.6.5): a `host.<verb>` then crosses as a `room_call`. A runner waits for that work when it waits for the kit to go idle |
| `fail` | Then raises, with this message |
| `refuse` | In a `deliver` or `on_event` reaction: then fails with the provider's explicit refusal (§5.13), its `error`, the `code` and `retryable` it declares, and the `provider_message_id` it names |
| `respond` | Event templates: the turn's response events (`on_event` only) |
| `output` | `tasks`, `observations` and `metadata_updates` of the channel's output; `provider_result`, the provider receipt (`success`, optional `provider_message_id`, `error`, `metadata`) returned in its `ChannelOutput` and preserved in the delivery result (§5.13), or null; a refusal uses `refuse`; in an `on_event` reaction, `response_metadata`, the record its turn writes (§6.4), and `error`: the error the channel met while producing it, with that message, which goes on with its responses and surfaces as a raised one's (ON_ERROR) |
| `writes_record` | In a hook's reaction: first of all, before its `gate`, writes these keys on the turn's record (§6.7), on `before_ai_generation` through its context's `response_metadata`, on another trigger through `current_response_metadata()` when it answers one |
| `stop_after` | In a `deliver_stream` reaction: the channel stops reading the stream once it was handed the text delta or the piece of reasoning this string equals |
| `close_while_reading` | In a `deliver_stream` reaction, `{"running": gate, "closed": signal}` pulls the next item after a tool start row. Once the tool reaches `gate`, the target abandons the pending read, closes the stream and signals `signal`. |
| `stop_after_rows` | In a `deliver_stream` reaction: the channel stops reading the stream once it was handed this many of its rows, a call's start or end |
| `parsed` | In a `parse` reaction: a patch on the event the channel builds, what it reads off its own wire: its members replace the event's, those of its `source` the source's; its strings name what the run made (References) |
| `result` | A hook's HookResult (§9.4). A modify's `event` is a patch on the payload: its members replace the payload's. Its injected events, tasks and observations are templates; event aliases in a room-event hook result resolve after its actions, before the result is returned |
| `invalid_result` | A deliberate unusable return on a SYNC `before_broadcast` hook: `{ "kind": "no_result" }` returns null; `{ "kind": "missing_payload", ... }` returns an unchecked MODIFY with no event, optionally carrying `tasks`, `observations`, and `injected_events` templates. On a SYNC `on_tool_call` hook, only `{ "kind": "missing_payload" }`, carrying nothing: an unchecked MODIFY with no tool-call event (§9.3). Mutually exclusive with `result` and `fail`. A runner validates the fixture before invoking the hook; a malformed fixture is a runner failure, never a simulated hook exception |

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

### Scripted realtime sessions

A `realtime_voice` channel with `realtime: {}` hosts a speech-to-speech
model over a simulated provider and transport (§12.4). A step starts its
session. Its handle stays available after the session ends so the provider
can issue a late callback. The fixture starts one session per channel.
Under `realtime.tools`, each tool name maps to its handler script. The handler
waits at its optional `gate`, then returns its string `result`. An optional
`reconnect` of `handler` or `child` first reconfigures the session directly or
from a child task. To apply the reconfiguration, the provider reports the
outstanding call ids from its previous connection as abandoned. A
`realtime.reasoning_error` supplies an integrator-side backend whose turn
raises with that message.

### Scripted agents

An `ai` channel with a `model` is the implementation's own AI channel (§6.4),
run on a scripted model and scripted tools, so that its tool loop is the one
under test. Its turn builds the conversation and runs the loop as the
implementation's AI channel does; only the provider and the tools are
scripted.

- `external_tool_handler`: a real policy handler with the same `policy`, `decisions` and `reports` controls as `acp.external_tool_handler`. Its actual callbacks are read through `expect.external_handlers[channel_id]`; AIChannel does not start or stop this service.
- `thinker`: a public `Thinker` with a nonempty `thoughts` array. Each entry
  contains exactly one `thought` or `fail`, and may wait at `gate`. A thought
  has optional `text`, string `want_to_say` entries and boolean `urgent`; no
  limit is imposed on this carrier. Calls repeat the last entry. Malformed
  controls fail before channel execution. `think_wait_ms` supplies the real
  channel wait, including zero. `expect.thinker_calls[channel_id]` records
  actual calls before waiting or failing: `previous` and `context`, using the
  same message and room normalization as a model request. The real channel
  schedules the work, owns each room's thought and decides whether to speak.
  An `on_thought` hook records `thought` with the full ThoughtEvent fields:
  `room_id`, `channel_id`, `thought`, `previous`, `duration_ms`. A null duration
  identifies an update not returned by a thinker call. These are observations,
  not a fixture implementation of the thought lifecycle.
- `speak_policy`: a public `SpeakPolicy` with a nonempty `decisions` array.
  Each entry contains exactly one `decision` or `fail`, and may contain a named
  `gate`. The policy records the real `SpeakTurn`, waits at that gate when
  present, then returns the decision or raises the scripted error. Calls use
  entries in order and repeat the last one. A decision contains `mode`
  (`speak`, `offer`, `silent`) and optional `reason`, numeric `judgments`, string
  `notes`, and `final`; only silence can be final. Malformed controls fail
  outside the product's policy-error fallback. `speak_timeout_ms` supplies the
  channel's real timeout in milliseconds.
  `expect.speak_turns[channel_id]` reads the actual inputs: `event`, `recent`,
  `people`, `channel_id`, `speakers`, and `thought`. An empty array also exists
  for a scripted AI channel without a policy, so it can prove no policy call.
  An `on_speak_decision` hook records its payload under `speak_decision`:
  `room_id`, `channel_id`, `event`, `decision`, `duration_ms`, `asked_again`,
  `late`, and `thought`. A hook's modify patch contains only `decision`; the
  fixture replaces that decision in the real payload, preserving its event.
  Wall-clock timing and object identity are tested natively, not inferred
  from these recorded snapshots.
- `continuation`: a host callback `{prefix, nudge}` or `{prefix, error}`.
  Every invocation records its exact text in `expect.continuations[channel_id]`.
  Text beginning with `prefix` returns `nudge` (including an empty string or
  null) or raises the scripted error; other text returns null. The real channel
  decides whether and when to call it and whether another generation may run.
- `model.streaming`: true by default. False runs `generate()` through the
  provider's default whole-response adapter, including tool calls and gates.
  Each round is reserved before waiting at its gate. In this mode the
  stream-only fields `deltas`, `thinking`, `stream`, `done`,
  `usage_at_start`, `failure_after_calls` and `failure_after_done` are
  refused; use `text`,
  `calls`, `whole_response`, `usage`, `finish_reason`, `fails` or `refuses`.
  A `whole_response` cannot be combined with `fails` or `refuses` in this
  mode; script a failing round without `whole_response` instead.
  A `fallback_model` takes the same option.
- `model.fails_once_closed`: false by default. True makes the model a client
  its close releases for good, as a vendor's is: every generation asked after
  its `close()` fails with a provider error, `the model was closed`. Its
  close is shared by every copy of the agent, a process's or an executor's
  build, as its script is.
- `model.rounds`: the model's answer to the agent's n-th generation of the
  run is its n-th round: `text` (default empty), `calls`, `finish_reason`
  (default `tool_calls` when it calls, else `stop`; a word of the provider
  contract's one vocabulary, §6.7: `stop`, `tool_calls`, `length`,
  `content_filter`, `refusal`, `malformed_call`, `unexpected_call` or
  `error`, null for none, any other refused) and `usage`, counters
  the turn's record sums (§6.4, The turn's record). `usage_at_start`:
  counters the model tells as its stream starts, before its gate and
  anything it writes, as a provider that tells its input then does (§6.4,
  What a generation used); its done event's `usage` replaces them. A call is `id`, `name`,
  `arguments` (an object, default `{}`; a text `$<label>` in it is read,
  once the model writes the call, as References read it: the id of the
  task a step labelled `<label>` delegated), and `cut` when the response was
  cut short over its arguments, which never arrived whole: the round's last
  call, under a `finish_reason` that cuts calls (`length`, `content_filter`,
  `refusal`, `error` or null, §6.4). A generation past
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
  A call's optional `served` is the provider's already executed result (§9.3):
  `{result: string, is_error: boolean}`, defaulting to empty text and false.
  Absent or null means no mark; `{}` is a present mark. Both regular calls
  and explicit stream calls accept it; unknown members and wrong types are refused.
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
  `finish_reason` of `refusal` is refused, one of `length` is
  `truncated`, any other text not the JSON document the schema asks for is
  `invalid_json`, a streamed round's check coming before its done event,
  which the error replaces; a `fallback_model` takes them too. `model.pricing`: the
  model's catalogue price (§6.7, a provider's `catalog_entry().pricing`,
  Python's `ModelPricing` fields), none when absent; a `fallback_model`
  takes one too.
  `model.chat_dialect`: the options of the core's chat rendering (§6.4, its
  `ChatDialect`), each request also written through the core's `chat_messages`
  under them, whatever the rounds answer (`models`, `chat_messages`): an object
  of `thinking_field` (the assistant field a replayed round's reasoning goes
  in, none when absent), `names_tool_results` (each tool message names its
  tool), `flattens_text` (a message of text parts goes as one string, and an
  empty message is not sent), `round_thinking_required` (every round that
  called tools carries the field, even one that did not reason) and
  `round_thinking_placeholder` (what that field holds for a round that did
  not reason, empty when absent), each flag false when absent, and `{}` the
  default rendering, which sends no reasoning back; as the core's
  `ChatDialect` does, `round_thinking_required` needs a `thinking_field`, and
  a non-empty `round_thinking_placeholder` needs `round_thinking_required`; a
  `fallback_model` takes one too.
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
  `writes_structured_content`: each call first assigns this object or null
  to `current_tool_call().structured_content` (§9.3, §21.4), before a `gate`
  holds it or its scripted answer succeeds or fails. Every call gets its own
  copy. The value is observed on the result hook and the stored end row;
  the model still reads only the scripted result.
  `returns_allowed_names: true` is another answer: the handler calls
  `current_tool_allowed_names()` and returns a sorted JSON array of its
  names, or null when unresolved (§21.4). The runner reads the actual turn
  context; it does not infer names from the scenario's tool definitions.
  `returns_requester: true` is another answer: the handler calls
  `current_tool_requester()` and returns it as JSON, a string or null, its
  characters unescaped (§19.7, §21.4).
  `returns_actor: true` is another answer: the handler calls
  `current_tool_actor_id()` and returns it as JSON, a string or null, its
  characters unescaped (§21.4).
  `posts_progress`: each call first posts this text as its task's progress
  with `post_task_progress(kit, detail)` (§23.3), before a `gate` holds it,
  then answers as its other member says; a call outside a task's child room
  posts nothing.
  `report_claim_probe` exercises `turn_report_claim` through the public tool
  context. `matching` returns wrong-id availability, wrong-channel availability,
  then three claims from two callbacks. `reused_id` retains the first callback
  and returns its claim and a fresh callback's claim on each call.
  `previous_turn` retains the first callback without invoking it, returns
  `[null]` first, then invokes only that retained callback on later calls.
  The handler owns this state; callback results are returned as a JSON array.
  `claim_then_gate` claims the call's report, then holds the call at its
  `gate`, which it needs, and returns `[<the claim's result>]` once a step
  opens the gate: a cut in that window cuts a call whose report was made
  before its end row (§9.3).
  Scenarios separately assert model results and actual ASYNC observer reports.
  `changes_state: true` declares it on its definition as a tool that
  changes state (Python's `AITool(changes_state=True)`, §6.4).
- `mcp_servers`: MCP servers the agent's tool handler serves (§21.2), each
  one the runner serves (a subprocess over stdio, or in process over HTTP)
  and reaches through the implementation's own MCP tool provider, connected before the run (its
  tools listed then) and closed after it: the provider's `label`, none when
  absent; `gate_discovery`, false for a handler that forwards every name
  (default true); `tools`, what the server lists, each `name`,
  `description` and `input_schema` as the server writes them (`{"type":
  "object"}` when absent), answering every call with `returns`, a text;
  with `is_error: true` (false by default), a result that says `isError`
  (§9.3), its text `returns`.
  `declare` says how the agent declares them: `bare`, the provider's own
  definitions (the default); `aliases`, each under `mcp__<label>__<tool>`
  with the provider's description and parameters; `none`, not at all. The
  servers' handlers are chained in the list's order, before the handler of
  the scripted `tools`.
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
- `publish_tool_call_text`: whether its `tool_call_start` events carry each
  call's arguments and its `tool_call_end` events each result's preview;
  false when absent, a subscriber then reading each call's id, name, status
  and intent alone (§8.4).
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
  Its `tool_timeouts_ms` overlays the channel's per-tool bounds for this turn
  (§21.6): integer milliseconds by tool name, `null` values unbounded. An
  omitted or null map keeps the channel's; an empty map changes no names.
  Zero is accepted by the fixture so the public turn's validation must refuse
  it before asking the model. No bounds are installed on the shared channel.
- `skills`: the agent's skill registry (§24.3), each skill's `name`,
  `description`, `instructions` and `references` (file names and their text)
  written to a directory of its own, as a host's skills are, and discovered
  from there; `[]` is an empty registry, which is not none: a turn's registry
  is read only on an agent given one. `skills_in_prompt`: false leaves the
  listing to the host, whichever registry a turn reads; the instructions of
  the skills active are written either way (default true).
  `allowed_tools`, when present, is a comma-separated text or a list of
  tool-name patterns (`*` and `?` globs), preserved as that frontmatter type.
  Matching tools are gated behind skill activation (§24.2).
  A skill with `in_memory: true` instead builds `Skill`/`SkillMetadata` and calls
  public `SkillRegistry.add`, without writing `SKILL.md`; references remain files
  beneath a separate temporary path. Directory skills are discovered first, then
  in-memory skills are added in script order. Availability/listing marks are
  applied after registration. The control defaults to false and must be boolean.
- `script_executor`: a host executor fixture (§24.6), present even as `{}`.
  It starts no process: it records the owning skill, original script name,
  optional arguments and checked file contents, then returns `result`
  (ScriptResult fields, default `exit_code: 0`) or raises `raises.kind` with
  `raises.message`. Skills may supply `scripts`, a map of portable filenames
  to text written under their own `scripts/` directory. Each executor close
  increments its counter. `expect.script_executors` checks each channel's
  `{calls: [{skill_name, script_name, arguments, contents}], closes}`.
- `sandbox`: a host SandboxExecutor fixture, present even as `{}`. Its
  `tools` are raw definitions (`name`, optional `description` and `parameters`),
  defaulting to an empty catalogue; the fixture does not filter their prefix or
  apply policy. It records `command` and `arguments` before returning `result`
  (`exit_code` required, optional `output`, `error`, `metadata`; default result
  has exit code zero) or raising `raises.kind` with `raises.message`.
  `SandboxResult.success` is derived by the public model, never a fixture control.
  No command, process or file operation is executed. Each close increments its
  counter. `expect.sandbox_executors` checks each channel's
  `{calls: [{command, arguments}], closes}` after harness cleanup.
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
  parts), with optional `metadata` (an object, empty by default), the
  `notes` it retrieved for the turn alone and the
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
  `sources` for the turn's words (§20.2): each answers with its `results`,
  or fails with `fails`; with `indexes: true`, it first answers with the
  passages the memory handed it to index, the latest first, each with the
  metadata it was indexed with at score 1, leaving out one whose content
  is the search's query.
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
- `acp.name`, `acp.role`, `acp.description`: optional local identity attributes,
  passed unchanged to the channel constructor; null or omitted means None.
  Discussion reads them without turning the channel into a declared Agent.
- `acp.instructions`: standing application instructions, absent by default; null
  or whitespace-only text disables them. A session receives them until its first
  prompt succeeds; close, reconnect or authorized rebuild opens a new session.
- `acp.room_history`: nonnegative history window, 20 by default; zero disables
  catch-up and declares that this channel needs no recent-event history.
- `acp.context_contributor`: `{responses: [...]}`, an async host callback with
  one `{blocks: ["..."]}` or `{error: "..."}` response per invocation, optionally
  held at `gate`. Errors exercise the channel's fail-open path; exhaustion is
  always a fixture failure. `expect.acp_context_requests` records actual inputs
  before any gate: `room_id`, `event` and `recent_events`, as event records,
  and the context's `history_start_index` (null when unknown).
  Python-only invalid return types and a lone string are checked natively;
  Rust uses the approved typed list return. The fixture does not compose prompts.
- `acp.additional_directories`: additional absolute directory paths declared in
  each `session/new`; omitted and empty lists declare none.
- `acp.mcp_servers`: a fixed list of ACP SDK descriptors, or
  `{mode: "sync"|"async", responses: [...]}` supplying a callback. Each invocation
  consumes one response, `{servers: [...]}` or `{error: "..."}`. An async
  response can wait at `gate`. Descriptors use ACP's stdio (`command`, `args`,
  `env`), HTTP or SSE (`type`, `url`, `headers`) shapes, with `name`.
  Callback exhaustion is a runner failure, even if the scenario expects a
  business error. An omitted list declares no servers.
- `acp.session_config`: initial channel option values (strings or booleans).
- `acp.publish_tool_call_text`: whether room tool notifications carry call
  arguments, result previews and full intermediate progress. Defaults to false.
  Tool rows and the tool observer's report keep their ordinary contents.
- `acp.publish_thinking_text`: publish thought text in ephemeral deltas (false
  by default); the turn stream and response report still receive the full text.
- `acp.transport.provides_usage_metadata`: the transport's opt-in trust flag, false
  by default. `acp.agent.prompts[].meta` is sent unchanged as the response's
  `_meta`; the fixture does not construct usage or provenance.
- `acp.transport.refuse_prompt`: ordered entries for calls to the transport's
  connection `prompt`, including rejected attempts. `null` (also the default
  past the last entry) forwards normally. An object raises the native
  `ACPSessionInvalidatedError(reason, recovery_authorized=False)` before
  forwarding. `after_prompt: true` forwards and awaits the real prompt first,
  then raises: a deliberately late signal testing the channel's activity guard.
  This is a host-side fault fixture, never an error decoded from JSON-RPC.
- `acp.agent.new_sessions`, `set_config_options`, `close_sessions`: ordered
  replies to `session/new`, `session/set_config_option`, `session/close`. Each
  reply optionally waits at `gate`, then returns its raw JSON-RPC `result`
  or `error`. Opening merges its result into the generated `sessionId`;
  setting defaults to `{"configOptions": []}`, closing to `{}`. Missing
  entries use those defaults. Counts span the run, including reconnects.
  The fake agent never calculates option values: scenarios supply descriptors
  explicitly and assert what the real channel sends on `expect.acp_wire`.
- `acp.agent.initialize`: its `initialize` answer: `protocol_version` (the
  client's when absent), `closes_sessions` (whether it announces
  `session/close`, true by default), `agent_info` (sent as written, none when
  absent), and `mcp_capabilities` (`http`/`sse` booleans sent as
  `agentCapabilities.mcpCapabilities`). Declare support when supplying URL servers.
- Its `session/new` answers are `session-1`, `session-2`... in the order it
  is asked, with no config option; `session/close` is answered `{}`;
  `session/cancel` is taken.
- `acp.agent.prompts`: its answer to its n-th `session/prompt` of the run:
  held at its `gate` first when it names one, then each of its `updates`
  sent as a `session/update` of the prompt's session, in order, optionally held
  at `after_updates_gate`, then its answer, `error` (a JSON-RPC error) or else `stopReason` (`stop_reason`,
  `end_turn` by default) and `usage` when given. A prompt past the last is
  answered `end_turn` with no update.
- Any other request is answered `method_not_found`.

`prompts[].permission` sends one `session/request_permission` immediately before
the prompt answer, without waiting for the permission decision. It supplies raw
ACP `toolCall` and `options`; `sessionId` comes from the current prompt. This
tests receipt ordering independently of the permission policy's decision.

`prompts[].before_reply_gate` holds after all updates and permission steps,
before either the successful reply or its error. It can keep a turn active
until an observer has completed a public call.

`prompts[].after_reply` is the agent's own activity once it answered the
prompt, in the prompt's session and outside any prompt (§6.4, §10.6.6): held
first at its `gate` when it names one, it sends its `updates`, then makes its
`permission_steps`, each as a prompt's.

`prompts[].permission_steps` supplies ordered `{request, updates?}` entries.
The `request` contains raw ACP `toolCall` and `options`; `sessionId` comes
from the prompt. The agent waits for the actual permission reply, then sends
that entry's `updates`, before proceeding to the next entry or ending the
prompt. This differs from the existing unawaited `permission` receipt-order
fixture, whose behavior stays unchanged.

`acp.external_tool_handler` installs a real external handler. With no
`decisions`, it delegates to `PolicyExternalToolHandler(policy=...)`; `policy`
has the usual `allow`/`deny` lists. `decisions` instead supplies ordered
`ToolDecision` objects (`approved` required, optional `modified_input`, `result`,
`reason`, `detail`) or `{"raise": message}` callback failures. Exhausting an
explicit decision list is a runner failure, not an implicit approval/refusal.
`reports` selects normal `delegate` behavior, `raise_before`, `raise_after`, or
`skip` (an override returning normally without delegation). The two failures
happen before/after the real default report and raise `RuntimeError("audit sink down")`.

`decision_gate` holds after recording a decision request, before deciding it.
`report_gate` holds after recording a report callback, before handing it to the
default report. Both use the normal named gates and allow deterministic cuts.

`expect.acp_handlers`, per channel, records the actual calls before observation:
`method`, the handler's registered `channel_id`, and for decisions/reports
`name`, `arguments`, and the actual named parameters (`tool_call_id`, `room_id`,
`session_id`, result/reason and outcome flags where supplied). `start` and
`stop` are recorded when called; automatic cleanup after observation is not
included. No expected report or permission outcome is manufactured by the fixture.

`expect.acp_permissions`, per ACP channel: those awaited replies in received
order, each `{session_id, tool_call_id, result}` (or `error` for a JSON-RPC
error), with the raw reply body. The fixture never chooses an option or
infers a tool outcome from it.

`expect.acp_wire`, per ACP channel: what its agent received, in order, each
`{method, params}`, `params` as the client wrote them, matched as a patch. A
client's `clientInfo.version` is its implementation's own.

`expect.acp_prompts`, per ACP channel: every call at the transport's prompt
boundary, before forwarding or refusal, as `{session_id, event_id, text}`.
`text` concatenates the prompt's text blocks. Counts span reconnects; the
agent's `prompts` count only calls actually forwarded to the wire.

`expect.acp_mcp_requests`, per ACP channel: exact room identifiers passed to
its MCP callback, in invocation order before any gate. A fixed list records
no callback. The fixture calls no external MCP server: the channel resolves
and declares the descriptors in `session/new`.

### Steps

| Step | What it does |
|---|---|
| a call | Makes the call and waits for it; `expect` checks its outcome |
| a call with `"background": true` and `as` | Starts the call and goes on once the call has run to its first wait: what the next step does or wakes comes after that part of the call |
| `{"await": label}` | Waits for the background call; `expect` checks its outcome |
| `{"cancel": label}` | Consumes the label and cancels the pending background call’s caller. Its implementation decides when the cancellation returns. Later steps can release work the call already started. |
| `{"close_while_pending": label, "as": closing}` | Requires that the labelled background call is pending and starts the kit’s ordinary close in the background. Await `closing` for its outcome. |
| `{"close_cut_at": gate}` | Starts the kit's close, waits until the close reaches `gate` (fails after 5 s), then cuts the shutdown itself, as a process's end cuts every task (§12.10.4): roomkit cancels every task of its event loop but the runner's own; roomkit-rs, having started that close on a runtime of its own, drops that runtime. The close's caller is not one a later step names |
| `{"concurrent": [calls]}` | Starts the calls together and waits for all |
| `{"wait_for": gate}` | Waits until the gate is reached (fails after 5 s). Optional `after` requires that the named gate was first reached strictly earlier. Optional `pending` checks that the labelled background call is still pending when the step observes the gate |
| `{"open": gate}` | Opens the gate: every call held there, and every later one, goes on |
| `{"idle": true}` | Waits until the kit runs nothing in the background; with `processes`, until none of the kits does, each discussion's driver roused first, so that it reads what another process stored |
| `{"wait_for_lock": room, "waiters": n}` | Waits until `n` calls (1 by default) wait for the room's lock (a runner fails after 5 s): calls started in the background are then known to overlap. `room` may be a reference, a room the run created (`$r1`) |
| `{"lock_releases": "fail"}`, `{"lock_releases": "succeed"}` | Sets the releases of the kit's `lock_manager` failing or succeeding, from the next one on |
| `{"under_lock": room, "do": [calls]}` | Takes the room's lock from the kit's `lock_manager` as a host does outside any pass (§13.5), makes the calls under it in order, each waited for and checked by its `expect`, then releases the lock. `room` may be a reference, a room the run created (`$r1`) |
| `{"store_fault": operation, "fail": message}`, `{"store_fault": operation, "gate": gate}` | Arms a fault on the kit's store (`setup.kit.store_faults`), which the first call of `operation` made after the step takes, on `room_id` when the step names one (a room the run created as `$r1`): `operation` is an operation of the store's interface (§14.1), or a list of them, for a read that implementations may make with different operations (`room_exists`, `load_room_context`), whichever comes first. With `fail`, the operation does not run and the call fails with that message, as the store's own failure; with `gate`, the call holds at the gate once the operation answered, then answers it, or with `fail` too, holds in the operation's place, then fails, or with `in_place: true`, holds in the operation's place, then runs it on the store as it then stands: a store the kit closed meanwhile (`store_owner` `kit`) refuses it. A fault no call took fails the scenario |
| `{"restart_process": id}` | Closes the named process if still running and opens a fresh kit under the same id with its configured channels, store and turn backend. Its old workers stop. A later `executor.start` can serve them again. |
| `{"acp_disconnect": channel_id}` | Closes the named scripted ACP transport's pipe and drains its agent tasks. The transport then reports `is_alive=false`; the real channel decides whether and how to reconnect. Session and reply counters continue across connections. This is a fixture fault, not a framework API call. |

A call that has not returned after 10 s fails the scenario.

### Calls

Each takes the RFC's name and the RFC's arguments, and may name an
`organization_id` it acts for (§17.2). Records are in the serialized form.
A call taking `kit` runs on the process it names (`setup.processes`), on the
run's own kit when absent.

| Call | Arguments | Result |
|---|---|---|
| `conference.open` | `channel_id`, `room_id`, optional `tools` | attaches a conference backed by a scripted SFU to the room. With a map of tool names to handler-result strings, its realtime model connects when a text broadcast arrives. |
| `conference.join`, `conference.leave` | `channel_id`, `participant_id` | the SFU reports a participant arriving or departing |
| `conference.publish` | `channel_id`, `participant_id`, `track_id`, `kind` | the participant publishes an `audio`, `video` or `screen_share` track |
| `conference.unpublish`, `conference.mute`, `conference.unmute` | `channel_id`, `track_id` | the SFU reports withdrawal or a change in mute state for that track |
| `conference.active_speaker` | `channel_id`, `participant_id` | the SFU announces its dominant speaker |
| `conference.connection_quality` | `channel_id`, `participant_id`, `quality` | the SFU reports the participant’s connection quality |
| `conference.tool_call` | `channel_id`, `call_id`, `name`, optional `arguments` | the connected conference model issues a tool call and waits for the corresponding result. The step returns the provider’s received text, decoded when it is JSON. Requires both `conference` and `realtime`. |
| `video.open` | `room_id`, `channel_id`, `participants`, optional `bridge`, `vision`, `detections` | attach the video channel and join the participants to it |
| `video.frame` | `channel_id`, `participant_id`, `sequence`, `data` | the transport delivers one self-contained 1×1 RGB24 frame (three bytes in base64) |
| `video.disconnect` | `channel_id`, `participant_id` | the transport signals the end of this session |
| `video.read` | `channel_id` | `forwarded`, the base64 frames received by each peer, and `vision`, the analyses published by the channel |
| `recording.start` | `room_id`, `recorder` | start a named recorder on an existing room |
| `recording.track` | `room_id`, `track_id` | add a live PCM16 audio track to the room's recordings |
| `recording.feed` | `room_id`, `track_id`, `data` | send a base64 chunk through that track's feed |
| `recording.read` | `recorder` | the base64 chunks this recorder actually received, in order |
| `recording.stop` | `room_id` | stop the room's recordings, returning their `recording_id` and `url` |
| `voice.open` | `room_id`, `channel_id`, `participants` and the optional provider inputs below | registers and attaches a voice channel, then joins the named participants to that room |
| `voice.feed` | `channel_id`, `participant_id`, `frames` (base64 PCM16 mono at 16 kHz) | the transport delivers these inbound frames in order |
| `voice.say` | `channel_id`, `participant_id`, `text` | speak to the participant, awaiting playback |
| `voice.stream` | `channel_id`, `chunks` (strings) | deliver a streamed reply to the channel |
| `voice.barge_in` | `channel_id`, `participant_id` | the transport signals an interruption |
| `voice.settle` | `channel_id` | wait for outstanding voice work after the utterance, playback or bridge frame |
| `voice.read` | `channel_id` | `synthesized` (the sentences the TTS provider received) and `audio` (per participant, the base64 chunks received by their transport) |
| `realtime.start` | `channel_id`, `room_id`, `participant_id` | opens the realtime session |
| `realtime.end` | `channel_id` | ends the session |
| `realtime.read` | `channel_id` | the provider's `injections` (text, role, silent) and `results` (call_id, result), and the tool `handlers` (name, outcome of `returned` or `interrupted`), in observation order |
| `realtime.inject` | `channel_id`, `text`, `role` | injects the text into the live session |
| `realtime.tool_call` | `channel_id`, `call_id`, `name`, optional `arguments` | the provider issues the call |
| `realtime.cancel` | `channel_id`, `call_ids` | the provider reports that it abandoned these calls |
| `realtime.delegate` | `channel_id`, `delegation_id`, `target` (`hosted` or `integrator`) | the model hands work to the backend |
| `realtime.error` | `channel_id`, `code`, `message` | the provider reports a session error |
| `parse_voice_session` | `session` (a voice session with `id`, `room_id`, `channel_id`, `participant_id` and optional `metadata`), `channel_id`, optional `metadata` | the InboundMessage made by the voice adapter (§5.12), including its session |
| `emit_protocol_trace` | `trace`, a §5.14 record for a registered channel; its optional `raw` is text, null, or `{"base64": "..."}` for bytes | emits through the channel; the kit supplies the timestamp and dispatches the trace to its room's hooks (§9.2) |
| `process_inbound` | `message` (an InboundMessage; its optional `session` uses the same form as `parse_voice_session`), `room_id` | an InboundResult: `event`, `blocked`, `duplicate`, `reason`, `error` (its message), `response_metadata`, `response_events`, `unavailable_targets`, `delivery_results`, `cancellation_reason` |
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
| `create_room` | `room`: `id`, `organization_id`, `metadata`, `timers`; `orchestration`, a scripted strategy's id, `null` for none, the kit's default when absent (§19.7); optional `kit` | the room |
| `attach_channel` | `room_id`, `channel_id`, and a binding's `category`, `access`, `visibility`, `muted`, `metadata`, `participant_id`; optional `kit` | the binding |
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
| `add_room_hook` | `room_id`, `hook`: a hook as in the setup, for that room alone, with no filter and the default timeout (`name` or `as`, `trigger`, `execution`, `priority`, `fail_closed`, `needs_lock`, `reactions`); optional `kit`, a process whose hook it is, which runs only there | unspecified |
| `remove_room_hook` | `room_id`, `name` | whether the room held a hook of that name |
| `hook_engine.add_room_hook` | `room_id`, `hook` (as `add_room_hook`'s): registered on the kit's hook engine (`hook_engine.add_room_hook`), below the kit, which reads no room (§9.1, §17.2) | unspecified |
| `kit_executor.add_owner_room_hook` | `room_id`, `hook` (as `add_room_hook`'s, on a trigger a turn fires): given straight to the kit's own executor for the room (`turn_executor.hooks.add_owner_room_hook`), below the kit, which reads no room (§9.1, §10.6.6) | unspecified |
| `subscribe_room` | `room_id`, `subscriber` (a label), optional `kit`, `types` and `gate`: the kit's `subscribe_room` (§8.4), a callback recording each ephemeral event it reads under `expect.subscribers`, by the subscriber's name. With `types`, the callback records matching types only. It signals `gate` after each recorded event | unspecified |
| `publish_typing` | `room_id`, `user_id`, `is_typing` (default true), optional `kit`: the kit's `publish_typing` (§8.4) | null |
| `cancel_delivery` | `key`, the `delivery_key` of the messages whose delivery it cancels, and `reason` (§10.1 Explicit delivery cancellation) | how many deliveries it cancelled |
| `close` | none | null once the kit's shutdown ended (§12.10.4) |
| `source_health` | `channel_id`: the kit's `source_health` (§6.5), a read | the `status` of the health of the source attached for the channel; null for none |
| `enter` | none: enters the kit's context, as an integrator opens the kit (§12.10.4): roomkit's `async with` (its `__aenter__`), roomkit-rs's `start` | null; once the kit's close started, `kit_closed` |
| `steer` | `room_id`, the room whose turns it reaches, `channel_id`, the agent, optional `kit` selecting the owner, and `directive` (a SteeringDirective in the serialized form: `{"type": "cancel", "reason"}`, ...) (§21.3) | how many of the agent's running loops in the room it reached |
| `install_strategy` | `room_id`, `strategy` (a scripted strategy's id) (§19.7) | null |
| `uninstall_strategy` | `room_id` (§19.7) | whether the room held a strategy |
| `claim_room_strategy` | `room_id`, `strategy`: claims the room for the strategy, or refuses, installing nothing (§19.7) | null |
| `room_strategy` | `room_id` | the id of the scripted strategy installed in the room, null for none (§19.7) |
| `default_router.route` | `channel_id`, `channel_type`, `participant_id`, `identity_id`, `organization_id`: the implementation's DefaultInboundRoomRouter over the kit's store, whatever router the kit holds (§10.4), reading no channel | the id of the room, null for none |
| `addressing_of.normalize` | `channel_type`, `address`, `country_code`: the addressing the implementation gives a channel of that type by default (`addressing_of`), writing `address` in its form with that country code, none when absent (§5.7) | the address so written; a country code it refuses, `invalid_argument` |
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
| `turn_backend.fault` | `operation` (`claim_presence` or `publish_presence`) and `enabled`. While enabled, each attempt fails at the corresponding owner-side backend operation. An optional `gate` signals the first failed attempt. A fault that was never taken fails the scenario. | null |
| `executor.start` | `executor`, an id of `setup.executors`: serves it on the kit's turn backend (§10.6.7) | null |
| `executor.close` | `executor`: it takes no more turns and ends those it runs (§10.6, §10.6.8) | null |
| `executor.kill` | `executor`: to the room it stops as a killed process stops, sending nothing more and hearing nothing more, its turns left to the owner's liveness checks (§10.6.8) | null |
| `owner.kill` | none: the run's kit, the owner of its turns, falls silent on each turn's link as a killed process does: it sends nothing more there, releases nothing and reads nothing more, its turns left to the executors' liveness checks (§10.6.8); the rest of the kit runs on, its node of a distributed backend included, and no scenario observes what it does of those turns; a kit with `turn_backend_faults` or `executor_catalogue: false` takes none | null |
| `executor.pause`, `executor.resume` | `executor`: it stops declaring its channels, or declares them again, keeping what it holds (§10.6.7) | null |
| `telemetry.spans` | `site` (`owner` or `executor/<id>`), `kind` (`framework.broadcast`, `llm.generate`, `hook.sync` or `llm.tool_call`), optional exact `attributes` to select matching spans | completed spans at that site, each with `name`, `span_id` and `parent_id` |
| `executor.calls` | `executor`: what it did so far, as `expect.executors` reads it; a turn's reaction may make it, to read that at a point of the turn | the list |
| `channel.publish` | `executor`, `channel_id`, `room_id`, `kind` (an ephemeral event's type), `data`, `gate`: in a reaction's `after_turn`, work the turn began publishes on the channel's realtime, once held at `gate` when it names one; the call returns once the room owner took it, or refused it (§10.6.3) | null |
| `acp.close` | `channel_id`: close the local ACP channel directly, leaving the kit alive so its shutdown cannot hide a pending channel preparation | null |
| `acp.cancel` | `channel_id`, `room_id`: call the local ACP channel's public `cancel(room_id)` directly, without a kit steering directive | whether a preparing turn or existing session was reached |
| `channel_call` | `channel_id`, `room_id`, `verb`, `arguments`: the channel's per-room verb, on the executor holding the room's state (§10.6.3) | the verb's result. With `capture_error`, saves the received exception under that label and returns its structured observation |
| `release_channel` | `channel_id`: every executor holding a build of it lets it go, closed once the turns running on it end, and builds it anew for the next one (§10.6.3) | null |
| `kit_executor.executor_id` | none | the kit's own public executor id; a `$as` matcher can bind it for exact presence assertions |
| `executors` | none: the executors served on the kit's turn backend, its own executor aside (§10.6.7) | the list, in any order, each `{executor_id, hosts, organizations, room_hooks, online}`: `hosts` the ids and prefixes it declares, sorted (null for a predicate or every id), `organizations` the ones it serves, sorted (null: the rooms without an organization alone), `room_hooks` sorted; a closed executor is not listed |
| `agent_presence` | `room_id`, optional `kit` and `wait_for_online`. The latter polls this owner’s public view for up to 5 s until the named agent is online, allowing distributed catalogue reads to converge. Returns the room's intelligence channels, each online while an executor alive covers it in the room (declares it, serves the room's organization, and defines the room's enabled hooks), a channel the kit holds live while the kit runs (§10.6.7, §10.6.8) | the list sorted by `channel_id`, each `{channel_id, online, executors}`, `executors` the ids of the executors covering it, sorted |
| `enable_room_hook` | `room_id`, `name`: the room's turns run the room hook the executors define under `name`, and only an executor that defines it takes them (§10.6.6, §10.6.7) | null |
| `install_pipeline` | `handler`, `stages`, `default_phase`, `supervisor_id`, `agents` (channel ids), `agent_aliases`, `hook_priority`, optional `voice_channel_id` for a realtime host: the ConversationPipeline's `install` on the kit, its handler named `handler` (§19.5) | null |
| `setup_handoff` | `agent_id`, `handler`, `targets` (each an id and its description or null: the tool `build_handoff_tool` builds; absent: the generic one), `room_id` (absent: every room): serves the handoff tool on the agent (§19.6) | null |
| `handoff.handle` | `handler`, `room_id`, `calling_agent_id`, `arguments`, the tool call's: the handler's `handle` (§19.6) | the HandoffResult (`accepted`, `new_agent_id`, `new_phase`, `message`, `reason`) |
| `handoff.set_language` | `handler`, `room_id`, `language`: the handler's `set_language` (§19.6) | null |
| `handoff.send_greeting` | `handler`, `room_id`, `channel_id`: the handler's `send_greeting` (§19.1, §19.6) | null |
| `delegate_handler` | `handler`, the name the later calls give it; `notify`, `default_share_channels`, `cache` (true: a CompletedTaskCache of the implementation's default time to live), `serialize_per_room`, `max_conversation`, `max_result_chars`, `wait_in_task_rooms`, each the implementation's default when absent: the implementation's DelegateHandler, serving no agent yet (§23.4) | null |
| `setup_delegation` | `agent_id`, `handler`, `targets` (each an id and its description or null: the tool `build_delegate_tool` builds; absent: the generic one): serves `delegate_task` on the agent (§23.4) | null |
| `delegate.handle` | `handler`, `room_id`, `calling_agent_id`, `arguments`, the tool call's: the handler's `handle` (§23.4) | what the tool answers: `status`, `task_id`, `child_room_id`, `agent_id`; a repeat answered from the cache, `result` and `from_cache` too; a call run inline (`wait_in_task_rooms`), `status` the status its task ended with, and `result`; its `as` label names the task's id |

### Video sessions and room recording

A video scenario requires `video`. The optional `vision` array on `video.open`
supplies the vision provider's descriptions in order, one per frame, an empty
string a result with no description. An optional
`detections` array scripts the filter: each event names its `frame_sequence`
and `kind`, with optional `labels`, `confidence` and `metadata`. The video
steps await the work the channel scheduled for the input before returning.
Under `expect.hooks`, `video` names the `participant_id` and carries the
bridge frame's `sequence`, the filter's detection fields or the provider's
`description` and `labels`. A bridge hook can replace the frame bytes in
`event.frame.data` (base64). A vision hook can patch the analysis fields.
`video.read.vision` reports the number of faces in each published result.

A room recording scenario requires `recording`. The recorder uses its given
name as its handle's id and returns `mock://<name>` as its result URL. A
track declared while the room records can keep feeding media when a second
recorder starts. Under `expect.hooks`, `recording` carries `recording_id`
and `room_id`, plus `urls` when the recording stops.

### Scripted voice sessions

A voice scenario declares `"requires_features": ["voice"]`. The transport feeds
real channel input. The optional inputs on `voice.open` script its providers:

- `vad` supplies one decision per inbound frame. Each is null or has a `type`
  of `speech_start`, `speech_end`, `silence` or `audio_level`, with optional
  `duration_ms`, `confidence` and `level_db`. Speech edges carry a nonempty
  pre-roll or utterance buffer.
- `speakers` supplies diarization results (`speaker_id`, `confidence`,
  `is_new_speaker`). `tones` supplies detected digits (`digit`, `duration_ms`).
- `transcripts` supplies final STT text by utterance. With `partials`, the
  recognizer streams these partial words on the first audio of the segment and
  returns its final at the end of the segment.
- `turns` supplies completeness decisions, one boolean per utterance.
  `backchannels` selects semantic interruption with the listed boolean
  classifications of incoming words during playback.
- `bridge` forwards permitted frames to the other participants when true.
  `playback_gate` holds the playback at the transport until a step opens it,
  so speech or a barge-in can arrive while the reply is playing.

Voice hook observations under `expect.hooks` expose `voice.participant_id`
from the session and the payload's scalar fields, such as the transcript's
`text` or a detected tone's `digit`. The TTS hooks carry only `voice.text`.
A synchronous transcription hook can replace the words with a `modify`
result whose `event.text` holds the replacement.

### Calls on the store

A call `store.<operation>` is the operation of the store's own interface
(§14.1), made on the kit's store, whatever the kit does: its arguments are the
operation's, by name, and its result is the operation's in the serialized
form, a map's values included. A record it takes is a template, completed as
the record requires (Templates): a room's `created_at` and `updated_at`, a
binding's `attached_at`, a participant's `joined_at` and an event's `id`,
`type` and `created_at` are now when it leaves them out, and an event's room
is the call's `room_id`, its source the framework's. A room
`store.update_room_if` writes that leaves out its `created_at` takes instead
the `created_at` of the room the store holds under its id, if any: the write
updates that room, it creates none, and a room is its id and its `created_at`
(§13.5). A runner runs the scenarios of `store/` and `idempotency/` on each
store it ships that needs no server.

| Call | Arguments | Result |
|---|---|---|
| `store.create_room` | `room` | the room |
| `store.delete_room` | `room_id` | whether the store held it |
| `store.add_binding`, `store.update_binding` | `binding` | the binding |
| `store.remove_binding` | `room_id`, `channel_id` | whether the room bound it |
| `store.add_participant`, `store.update_participant` | `participant` | the participant |
| `store.create_identity` | `identity` | the identity |
| `store.get_identity` | `identity_id` | the identity, or null |
| `store.resolve_identity` | `channel_type`, `address`, `organization_id` (null for none) | the identity of that organization the address belongs to on that channel type, or null |
| `store.link_address`, `store.unlink_address` | `identity_id`, `channel_type`, `address`, `organization_id` (null for none) | null |
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
verification and a verification request (§11.7.1, §11.7.2), and an
identity (§5.6), as `setup.identities` takes it, are taken as written, with
their records' defaults. An
index a store call returns is the store's: the scenarios of `store/` write
no lifecycle record, so it reads as normalized.

### Calls on the status bus, a room's observations and the turn's host

A call `status.<operation>` is the operation of the kit's status bus (§19.8);
`status.post` is its `post_async`, which returns once the bus's subscribers
ran. A call `host.<verb>` is a verb of the turn's host (§10.6.5), made by an
action of a scripted intelligence channel's turn (`on_event`), during the
turn (`do`) or after it (`after_turn`), or of a hook an executor fires while
the turn runs (§10.6.6): a runner refuses one made anywhere else, where no
turn's host is. `current_turn_host` reads whether one is.

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
| `host.delegate` | `room_id`, `agent_id`, `task`, and `delegate`'s `context`, `share_channels`, `notify`, `post_status`, `brief`, `conversation`, `hand_back` | the task's id, which its `as` label names; refused after the turn, `needs_turn` (§10.6.5) |
| `host.wait_task` | `task_id`, `timeout_ms` (the RFC's `timeout`, in milliseconds; none by default) | `{result, exception}` once the task ended: its DelegatedTaskResult and its failure's error record; null for a task the room's hosts did not delegate, or once `timeout_ms` passed first; refused after the turn, `needs_turn` (§10.6.5) |
| `host.room_context` | none | the current room context as JSON, including fresh room/bindings/participants and history read even when the channel window is zero; refused after the turn (§10.6.5, §10.6.6) |
| `host.room_tasks` | none | the turn's room's tasks, as `task_status` reads them (§23.4); refused after the turn, `needs_turn` (§10.6.5) |
| `current_turn_host` | none: an action, wherever it runs | whether a turn's host is bound there, as `current_turn_host()` reads it (§10.6.5, §21.4) |
| `declare_host_verb` | `name`, `handler` (below), `between_turns` (default false) | null; registers the callback on the kit through its public method (§10.6.5) |
| `host.call` | `verb`, optional `arguments` (an object or null), optional `record_keys` | the actual call's `{result, error}`; an error has its recorded `kind` and exact `message`. With `record_keys`, also reads those keys from the caller's record after the reply, or null outside the turn |
| `delegate` | `room_id`, `agent_id`, `task`, `wait` (default false), `context`, `share_channels`, `notify`, `post_status` (default true), `brief`, `conversation` (default 0), `hand_back` (default `relay`), `require_structured_result` (default false) and `max_result_retries` (default 3), an inline run's result tool, `submit_result`, served in the child room alone (§23.3) | the task: `id`, `child_room_id`, `parent_room_id`, `agent_id`, `task`, `brief`, `description`, `hand_back`, `status` and `result`, its DelegatedTaskResult once it ended (`task_id`, `child_room_id`, `parent_room_id`, `agent_id`, `status`, `output`, `error`, `duration_ms`, `metadata`); its `as` label names the task's id |
| `task.wait` | `task_id`: a task `delegate` returned, named by its label | its DelegatedTaskResult, once it ended |
| `start_task` | `room_id`, `agent_id`, `task`, `hand_back` (default: the agent's background setup's) | the task, as `delegate` returns it, started for the agent as its `work_in_background` call would (§23.4) |
| `setup_background` | `agent_id`, `worker`, `hand_back` (default `relay`) | null; the agent is given `work_in_background`, served by the room's owner (§23.4, §10.6.5) |
| `setup_task_tools` | `agent_id` | null; the agent is given `task_status` and `cancel_task`, served by the room's owner (§23.4, §10.6.5) |
| `await_input_request` | `request_id`, optional `organization_id` | fixture-only bounded wait until the public owner reader sees the request; makes the asynchronous frame-arrival precondition explicit, without changing the synchronous reader |
| `input_request` | `request_id`, optional `organization_id` | the open request of a turn this owner started (§10.6.5), with its nine `PendingInputEvent` fields and original creation `timestamp`; null when absent, settled, withdrawn or outside the organization |
| `answer_input` | `request_id`, `value` | whether the tool waiting on the human-input request reads the answer (§10.6.5): false for one settled otherwise first, or answered already |
| `reject_input` | `request_id`, `reason` (default empty) | whether the waiting tool reads the rejection, as a refusal (§10.6.5, §9.3) |
| `human_input.create` | `channel_id`, `room_id`, `tool_name`, `arguments` (default `{}`) | its id, a `$p<n>`: the request it opens as a human-input handler's `create` does (§9.3), on the handler the runner holds for `channel_id` (the implementation's, made at the run's first call naming the channel and given to nothing else), naming that room and channel; one opened during a turn belongs to it (§10.6.5) |
| `human_input.create_detached` | as `human_input.create` | its id, a `$p<n>`: the request it opens as `create_detached` does, which no one waits on and its creator releases (§10.6.5) |
| `human_input.resolve` | `channel_id`, `request_id`, `value` | whether that handler took the answer: false for a request no longer open there (§9.3) |
| `human_input.wait` | `channel_id`, `request_id`, `timeout_ms` (the handler's `timeout`, in milliseconds; its default when absent) | the answer once the request settled on that handler; `input_released` for one given up before an answer (§9.3, §10.6.5) |
| `cancel_task` | `task_id` | whether a background task the kit's task runner held was running and is now cancelled (§23.3); false for any other, or one of a room of another organization than the call's `organization_id` (§17.2) |

A declared handler with `raises_captured` throws the exception a previous
`channel_call` saved. `host.call` with `inspect_error: true` exposes the same
structured observation as `channel_call` with `capture_error`. It records
the fixture class name, displayed message, whether the received exception is
generic, the class it reads as, the ordered base names, and the attributes.
Rust checks the native class or base by downcast. A partially rebuilt
instance whose local field is absent identifies its class. The enclosing
remote error supplies its original display message.

A declared host `handler` answers with `returns` (a JSON value),
`returns_arguments: true`, `returns_context: true`, or raises `raises: {kind,
message}` (`ValueError`, `RuntimeError`, or `PermissionError`). Its context
snapshot reads the public tool accessors: arguments, room id, organization,
room metadata, channel and tool-call ids, actor, requester, depth, allowed
names (sorted or null), whether a record exists, and whether a turn host is
installed. `as` records this snapshot in `expect.actions`; `record_keys` adds
the selected record keys before and after its optional `gate`. A gate holds
the callback until opened; `cancelled` names a gate reached only if that wait
is cancelled. No wait is a fixed delay.

After the gate, `writes_record` sets keys, `removes_record` removes named keys,
`updates_record` adds or replaces entries of named mappings, and
`removes_entries` removes named entries. These mutate the actual record the
public accessor returns; each callback owns its scripted values. Changes
happen before either the scripted result or error.

A scripted tool may answer with `host_calls: {calls, concurrent, record_keys}`.
Each call names `verb` and optional `arguments`; omitted arguments use the
public default. Calls are sequential unless `concurrent: true`. A call's
`returned` reaches a named gate only after its reply; `cancel_after` starts
that call in its own task and cancels only that task once the named gate is
reached. The tool returns canonical JSON text (sorted object keys) containing
`calls`, the actual results/errors in call order, and `record`, the selected
keys after all replies. A cancelled call has error `{kind: "cancelled",
message: ""}`. Parent-task cancellation is never caught as a child result.
This formatting is fixture syntax, not a product serialization requirement.

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

### Structured task plans

A scripted AI channel's `enable_planning` is the public constructor boolean,
false when absent. It installs the real `plan_tasks` tool. Its CUSTOM events
are read under `custom_events`; `on_plan_updated` hooks expose `plan` with the
public `room_id`, `channel_id`, `tasks` and ISO timestamp. The runner neither
stores a simulated plan nor derives its tool result from these observations.

### Expectations

`expect` names what is compared; what it does not name is not.

| Member | What is compared |
|---|---|
| `timeline` | Per room, the whole timeline in index order, `BLOCKED` records included, lifecycle records left out |
| `rooms`, `bindings` | Per room, the room record; per room and channel, the binding, `null` for none |
| `framework_events` | Per room (`*` for the events of no room), every framework event of the §26.1 table and `process_timeout`, and of the Level 2 features the suite exercises, `status_posted` (§19.8) and `feedback` (§15.9), identity resolution's `identity_resolved` and `identity_timeout` (§8.2), a human-input request's `user_input_required` (§9.3), and identity verification's `verification_requested`, `verification_completed` and `verification_ended` (§8.2, §11.7), and a delivery lane's `delivery_skipped` (§8.2, §13.5), in emission order |
| `hooks` | Per scripted hook, its calls in order: `trigger`, `room_id`, `delegation` (`delegation_id`, `target` for `on_realtime_delegation`), `trace` (the §5.14 record for `on_protocol_trace`, including its UTC timestamp and binary data in base64), `event` (the payload, when an event), `context_room` (the room supplied to an event or session hook, captured on entry), `recent_events` (the ids of the events of the context supplied to an event hook, lifecycle records left out, as `contexts` reads them), `context_events`, `context_bindings` and `context_participants` (that context's events, bindings and participants, as `contexts` reads its `events`, `bindings` and `participants`), `tool_call` (the payload, when a tool call: `name`, `tool_call_id`, `arguments` as the call runs or was stopped with, and, on `on_tool_call`, `result` as the model reads it, `is_error`, `refused`, `cancelled`, `error_detail` and `structured_content`), `delivery_status` (the payload, when a delivery status, §10.4), `status_entry` (the payload, when a status entry: `on_status_posted`), `dispatch_decision` (the payload, on `on_dispatch_decision`: `room_id`, `event`, `candidates`, `decision` as `{agents, reason, judgments}`, `duration_ms`), `observation` (the payload, when an observation: `on_feedback`), `request` (the payload, when a human-input request: `pending_id`, `tool_name`, `arguments`, `room_id`, `tool_call_id`, `channel_id`, `channel_type`, `actor_id`), `identity_result` (what an identity hook is handed, §11.2), `generation` (the payload, on `before_ai_generation`: `channel_id`, `provider_name`, `purpose`, `trigger` the event the turn answers, and its context's `system_prompt`, `messages` as `models` reads them, the names of its `tools`, and `room`, `target_capabilities` and `target_media_types` as `models` reads them), `tool_round` (on `after_tool_round`: `channel_id`, `round_index`, its `calls`, each `{tool_call_id, name, arguments, metadata, partial, garbled}`, its `results` and provider-served `answered` results as `models` reads them, and the names of the turn's `tools`), `response` (on `on_ai_response`: `channel_id`, `response_content`, `segments`, `tool_calls_count`, `round_count`, `loop_end_reason`, `usage`, `usage_complete`, `usage_metadata` (the response provenance, copied unchanged), `streaming`, `thinking`, and `declared_tools`, by name: `position`, `description`, `parameters`, `origin`) |
| `hook_order` | The order in which the hooks it lists were called, a scripted channel's room callbacks among them (`<id>.on_room_attached`, `<id>.on_room_detached`) |
| `sources` | Per scripted source, by its channel id, its calls in order: `start`, `stop`, `healthcheck`, and `cut` when its start's task was cut (§6.5, §12.10.4) |
| `channel_closes` | The scripted channels whose close ran, each id once per call, in the order they ran (§6.1, §12.10.4); the order in which the kit closes its channels is the implementation's, so a scenario that names several matches them `$unordered` |
| `room_callbacks` | Per room and scripted channel, its room callbacks (§6.1) in order: `{"call": "on_room_attached", "binding": ...}`, the binding it was handed, `{"call": "on_room_detached"}`, or `{"call": "connect_session", "session": ..., "binding": ...}` for an inbound session |
| `deliveries` | Per room and channel, the events a scripted channel's `deliver()` received, as delivered, in order |
| `contexts` | Per room and scripted channel, the context each of its parses (`handle_inbound()`, §10.1 step 4), each of its `deliver()` calls and, for an intelligence channel, each of its turns (`on_event()`) was handed, in order: `call` (`parse`, `deliver` or `on_event`), `recent_events`, the ids of its events read as Normalization reads them, lifecycle records left out, `events`, those events as `timeline` reads them, `room`, its room as `rooms` reads it, counters included, `bindings`, its bindings, each as `bindings` reads one, and `participants`, its participants as `participants` reads them, each list in the context's order |
| `text_events` | Per room, a minted one's as `$r1`, the `text_delta` ephemeral events the room's realtime is handed, in order: each `{text, round, channel_id}` (§6.4) |
| `thinking_events` | Per room, the `thinking_start`, `thinking_delta` and `thinking_end` ephemeral events its subscribers read, in order: each `{type, thinking_length, round, channel_id}`, and `thinking` for an agent with `publish_thinking_text` |
| `tool_events` | Per room, the `tool_call_start`, `tool_call_end` and `tool_call_delta` ephemeral events its subscribers read, in order: each `{type, tool_calls, round, channel_id}`, and `duration_ms` for an end that ran its calls (§6.4, §8.4) |
| `custom_events` | Per room, the CUSTOM ephemeral events its subscribers read, in order: each `{room_id, channel_id, data}`; ACP configuration, plans, tool progress and usage retain their wire payload. |
| `subscribers` | Per subscriber a `subscribe_room` call named, the ephemeral events its callback read during the steps, in order: each `{type, room_id, user_id}` (§8.4, §17.2); a subscriber that read none, `[]` |
| `presence_events` | Per room, the `presence_online` and `presence_offline` ephemeral events its subscribers read during the steps, in order: each `{type, user_id}`, `user_id` the agent's channel id (§10.6.7, §8.4) |
| `streamed` | Per room and streaming channel, the items its `deliver_stream` read, in order: `{"text": ...}` for a text delta, `{"thinking": ...}` for a piece of the model's reasoning, `{"usage": ..., "partial": ..., "model": ..., "provider": ...}` for what a generation used, `partial` true for what it told before its end, when the channel `reads_usage`, `{"row": event}` for a row the store holds, `{"loop_end": {"reason", "rounds", "usage"}}` for the turn's end, when the channel `reads_loop_end`, `{"failed": true}` where the stream raised, `{"cut": event}` for the end of a stream cut from outside, the row its `deliver_cut` was handed (§6.1, §12.2 step 13s), null for none |
| `turns` | Per room and intelligence channel, the events its `on_event()` received |
| `ingested` | Per room and scripted agent with a scripted `memory`, the events its memory was handed (§20, `ingest`), in order, matched as the timeline's |
| `compacted` | Per room and scripted agent with a scripted `memory`, the compactions between two tool rounds its memory was asked (§6.4, §20.1, `compact`), in order: each `{history, usage}`, `history` the messages it was handed, each as `models` reads a request's (`{role, text, parts, round}`), `usage` the round's token counters |
| `dispatch_turns` | Per setup strategy with a scripted `dispatch`, the turns its policy was handed (§19.7.5 rule 18), in order: `room_id`, `event` and `recent`, matched as the timeline's events, `speakers`, each `[event id, label]` in the order of `recent` then `event`, `candidates`, each `{channel_id, name, role, description, handle}`, and `asked` |
| `observations`, `tasks` | Per room, the stored side effects |
| `actions` | Per action label, the outcomes of its runs, in the order they ended |
| `ai_events` | Per room, the framework events of an AI channel's turn (§8.2, Level 1): `before_ai_generation` and `ai_response`, in emission order, matched as `framework_events`, which does not hold them |
| `external_handlers` | Per AI channel, the ordered external handler callbacks; an exact empty list proves none occurred. |
| `thinker_calls` | Per scripted AI channel, real thinker inputs (`previous`, `context`) in invocation order; `[]` proves no call. |
| `speak_turns` | Per scripted AI channel, the real speaking-policy inputs, in order; `[]` proves no call. The scripted-policy protocol above defines the snapshots. |
| `continuations` | Per channel, exact continuation callback inputs in invocation order; `[]` proves it was not called. |
| `models` | Per scripted agent, each generation's `method` (`generate` or `generate_structured_stream`, recorded at the actual script reservation; absent for native Rust memory summarizers), and its request as its model received it, in order: the `messages` it carries, each `{role, text, parts, round}`, `text` its text parts joined (empty for a message with none, a tool's result among them), `parts` its text and image parts in order, each `{"text": ...}` or `{"image": url, "mime_type": ...}`, null for a message whose content is a text, `round` its reasoning, text and call parts in order, each `{"thinking": ..., "signature": ..., "redacted": ...}`, `{"text": ...}` or `{"call": id, "arguments": ..., "metadata": ...}`, null for a message whose content is a text, and the `tool_results`, each `{tool_call_id, name, content, is_error, references}`, `name` the tool of its call, `content` as the model reads it (a text, or a result's text and image parts in order, written as `parts` are), `is_error` whether it reads the call as failed, its `system_prompt`, its `temperature` and `max_tokens`, its `reasoning_effort`, `thinking_budget` and `enable_thinking`, its `response_schema` (null for none), `room` (the RoomContext snapshot, null when absent), `target_capabilities` (the outgoing transports' shared capabilities, null with no target) and `target_media_types` (their shared media types, compared as an unordered set), the `deferred_tools` names held unseen, the `reopened_tools` names referenced by synthetic opening exchanges, the `tools` it declares, by name: each one's position in the declaration, so that a scenario names those it asserts, declared or `$absent`, `tool_names`: their exact ordered list (including duplicates), `tool_definitions`: each declared tool's `description` and `parameters` as the model receives them, by name, and, for a model with a `chat_dialect`, `chat_messages`: the request as that rendering writes it on the wire, its system prompt first when it has one, each message's `role`, `content`, `tool_calls`, `tool_call_id`, `name` (a tool message's, under `names_tool_results`) and its dialect's reasoning field |
| `acp_wire` | Per ACP channel, the requests and notifications its scripted ACP agent received, in order, each `{method, params}` (Scripted ACP agents) |
| `acp_permissions` | Per ACP channel, actual replies to awaited permission requests, each `{session_id, tool_call_id, result}` or `error` (Scripted ACP agents) |
| `executors` | Per executor of the setup, what it did, in order: `{call, channel_id, build}`, and `room_id` for a call about a room: `built` (a copy of the channel made, `build` counting them per executor and channel), `on_event` (with its `tools`: the names of the scripted agent's own tools, its `tools`, whose handler that turn ran on the executor, in the order called: a host's tool runs where its turn does, §10.6.5), `on_room_attached`, `on_room_detached`, `channel_call` (with its `verb`) and `close`. A detach from a room this build never saw let go of nothing and is not listed |
| `turn_ends` | Per channel with `holds_end`, each of its turns its owner cut, in the order cut: `room_id`, `cut`, the first of `close` and `cancel` the owner sent the turn's executor, and `read`, whether the owner read the turn's `end` once the gate opened: false when it had let go of the turn first, dropping its later frames (§10.6.8) |
| `killed_owner_frames` | The type of each frame the turns' executors sent the run's kit once an `owner.kill` step killed it, each once, sorted: what reached its turns' links, which it never read (§10.6.8) |
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
  (-1 at least), an event's `metadata.follows_index` (-1 at least), and a `delivery_skipped`'s `from_index` and `to_index`; a
  RoomContext's positive `history_start_index` is read the same way (zero still means the whole conversation, and null stays unknown); a room's `event_count` loses one for each lifecycle record below it. Every other gap stays: a hard delete leaves its index given out
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
  framework events, show it first. Participant, identity and voice session IDs supplied by the
  scenario are kept as written.
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
- `{"$contains": "text"}`: a string holding the text; `{"$contains": ["a",
  "b"]}`: a string holding each text of a non-empty list in this order, each
  after the end of the one before (the parts of a text around what a run
  cannot fix, a duration); any other value is a scenario's mistake;
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
| `invalid_argument` | An argument refused before anything is read or written: the visibility `internal` (§7.3), a channel id the grammar refuses (§7.3), `standalone` on another type and an instruction's refusals on a direct injection (§10.1.1), a record naming another room (§10.5), a post from a channel that is not a host channel, a message on a host channel (§10.5), a host channel bound as an intelligence channel, a reserved room metadata key (§5.1), a hook registration §9.1 refuses, a tool set up on an agent under a name it serves already (§21.1), a tool set up for a channel whose turns do not take the owner's tools (§10.6.5), a strategy for a room that holds one, or that the strategy refuses (§19.7), `listen_only` or `talk_again` for a room holding no discussion (§19.7.5), content holding a sixth composite level (§5.3), a media URL the content model refuses (§6.4), a country code that is none, a channel's or one a number is written with (§5.7) | `ValueError` | `InboundError::{NotAHostChannel, InboundOnHostChannel, HostAsIntelligence, StandaloneOutsideInstruction, InternalVisibility}`, `Refused` with an instruction's reason, `LifecycleError::{InternalVisibility, HostAsIntelligence, ReservedMetadataKey}`, `MutationError::OtherRoom`, `KitError::{Config, Registration}`, `RoomKitError::ToolNameCollision`, a `ChannelId` refused, `ModelError::CompositeTooDeep` from `CompositeContent::new`, a URL `MediaContent::new` refuses, `InvalidCountryCode` from `CountryCode::new` |
| `channel_not_registered` | The channel named is not registered (§10.1 step 1, §10.5) | `ChannelNotRegisteredError` | `InboundError::UnknownChannel`, `KitError::UnknownChannel` |
| `room_not_found` | No such room, or another organization's (§17.2) | `RoomNotFoundError` | `InboundError::{RoomNotFound, OtherOrganization}`, `LifecycleError::RoomNotFound`, `MutationError::RoomNotFound` |
| `channel_not_bound` | The room does not bind the channel: a direct injection or a post from it (§10.5), a detach or a binding change of it (§7.2) | `ChannelNotFoundError`; `detach_channel()` answering `False` | `Refused { reason: "source_unbound" }`, `LifecycleError::ChannelNotBound` |
| `room_closed` | The room's status refuses new events (§5.1) | `RoomClosedError` | `Refused { reason: "room_closed" }`, `MutationError::Refused` |
| `transition_refused` | A transition from a status it does not leave from (§5.1) | `TransitionRefusedError` | `LifecycleError::TransitionRefused` |
| `change_refused` | An edit or a delete step 8a refuses, with its `reason` (§10.1 step 8a, §10.5) | `ChangeRefusedError` | `Refused` with one of step 8a's reasons |
| `process_timeout` | `process_timeout` passed before the commit (§13.6) | `ProcessTimeoutError` | `Refused { reason: "process_timeout" }` |
| `participant_not_found` | A post's speaker is no participant the host channel reaches (§10.5); a member call names no participant of the room (§5.5); `update_participant` of a record the room does not hold (§14.3) | `ParticipantNotFoundError` | `InboundError::ParticipantNotFound`, `RoomKitError::ParticipantNotFound`, `StoreError::ParticipantNotFound` |
| `identity_not_found` | No such identity, or another organization's (§5.6, §17.2) | `IdentityNotFoundError` | `RoomKitError::IdentityNotFound` |
| `address_linked` | An address another identity of the organization holds on the channel type, at an identity's creation or a link (§5.6) | `AddressLinkedError` | `RoomKitError::AddressLinked`, `StoreError::AddressLinked` |
| `participant_exists` | A participant added under an id its room has, the record it holds kept (§5.5, §14.3) | `ParticipantExistsError` | `StoreError::ParticipantExists` |
| `reentrant` | A message routed back into the room whose lock or admission order its caller holds (§9.5.1 A message routed back) | `ReentrantCallError` | `KitError::Reentrant` |
| `waits_for_itself` | A completion handle's cancel from the room's lane or under its lock, where its cleanup would wait for its caller (§10.1 step 18) | `RuntimeError` from `DeliveryHandle.cancel` | `RoomKitError::Runtime` from `DeliveryHandle::cancel` |
| `cleanup_incomplete` | A delivery's cleanup not known to be done, as its completion handle reports it: a `cancel` whose `timeout_ms` passed before the cut turns were over, or a `cancel` or a `wait` on a call one of whose turns is over without its executor's `end` (§10.1 Explicit delivery cancellation, §10.6.8) | `TimeoutError` from `DeliveryHandle.cancel` or `DeliveryHandle.wait` | `RoomKitError::Timeout` from `DeliveryHandle::cancel` or `DeliveryHandle::wait` |
| `reentry_loop_cap` | A direct change past its cascade's hook calls (§8.3, §10.3) | `ReentryLoopCapError` | `MutationError::ReentryLoopCap` |
| `idempotency_key_taken` | A direct record or store write tries another event under a key its source channel holds in the room (§13.4, §14.3) | `IdempotencyKeyTakenError` | `RoomKitError::IdempotencyKeyTaken`, `StoreError::IdempotencyKeyTaken` |
| `event_not_found` | A write naming an event its room does not hold: a change's target, `update_event` (§14.3) | `EventNotFoundError` | `StoreError::EventNotFound` |
| `task_not_found` | An update of a task the store does not hold (§14.3) | `TaskNotFoundError` | `StoreError::TaskNotFound` |
| `verification_refused` | A verification request refused, with its `reason`: `not_found` (none in the caller's organization), `not_open`, `expired`, `mismatch` (a wrong secret, counted) or `failed` (the last attempt) (§11.7.2) | `VerificationRefusedError` | `RoomKitError::VerificationRefused` |
| `channel_failed` | A channel's own error, which the caller is handed (§6.1): a transport's `on_room_attached` refusing an attach, its `on_room_detached` failing a detach | the scripted channel's failure, raised as it is | `RoomKitError::Channel` |
| `kind_not_stored` | `room_strategy_is_current` asked of a kind of strategy that is not stored with the room (§19.7.5 rule 16) | `TypeError` | `RoomKitError::Type` |
| `turn_link` | A turn, channel call or event no executor could carry, with its `reason`: `no_executor` (§10.6.7), `executor_lost`, `backend_closed` (§10.6.8) | `TurnLinkError` | `RoomKitError::TurnLink` |
| `needs_turn` | A verb of a turn's host that needs its turn, called by work the turn began once the turn is over, with its `reason`: the verb the error names (§10.6.5) | `RuntimeError` from `TurnHost`, `<verb> needs a turn: …` | `RoomKitError::Runtime`, `<verb> needs a turn: …` |
| `input_released` | A human-input request given up before an answer, as its waiter reads it: withdrawn with its turn, or released (§9.3, §10.6.5) | `RuntimeError` from `HumanInputHandler.wait`, `Released before an answer arrived` | `RoomKitError::Runtime` from `HumanInputHandler::wait`, `Released before an answer arrived` |
| `acp_request_refused` | A live ACP session rejects a configuration request (§6.4) | ACP `RequestError`, including its remote wrapper | `RequestError` relayed by the channel |
| `acp_connection_closed` | The ACP pipe closes while a request is waiting (§6.4) | `ConnectionError`, including its remote wrapper | `AcpError::ConnectionClosed`, relayed as `ConnectionError` |
| `acp_setup_refused` | A new ACP session cannot apply its required configuration and is never prompted (§6.4) | ACP setup `RuntimeError` | ACP `AcpError::SetupRefused`, relayed as `RuntimeError` |
| `already_set_up` | A handoff's tool set up again where it is declared, or an install over an agent whose handoff is set up already (§19.6); `delegate_task` set up again on an agent (§23.4) | `RuntimeError`, `setup_handoff() already called`, `setup_delegation() already called` | `RoomKitError::Runtime` |
| `store_failed` | A store operation that failed, as a store fault (`store_fault`) makes it fail, or as a store the kit closed refuses it (`store_owner`), the store's own failure, which the call is handed (§14.1) | the store fault's error, raised as it is | `RoomKitError::Store` |
| `channel_close_failed` | The kit's close once one or more of its channels failed to close, raised once the rest of its shutdown ran, and the same failure answered to every later close (§12.10.4) | `ExceptionGroup` from `RoomKit.close` | `RoomKitError::ExceptionGroup` |
| `shutdown_cancelled` | A close once the kit's shutdown was cut itself before it ended, to a caller nobody cancelled (§12.10.4) | `ShutdownCancelledError` | `RoomKitError::ShutdownCancelled` |

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

Shared scenarios use gates to cancel a caller before or after its decision and while
a nested call holds its room’s lock. Each implementation also tests concurrent
sections that begin at the same instant.

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
transport, the kit's own executor reached as one elsewhere. Such a pass is a
test of that backend, a provider of the core's turn interface: its
implementation's CI runs it, and it records no receipt of the core, whose
receipts are the in-memory defaults with the mocks (TRACEABILITY.md,
« Execution receipts »). roomkit selects the turn mode with
`ROOMKIT_TEST_TURN_BACKEND`. The pass skips what a transport cannot give the
runner, with its reason in `tests/conformance/test_conformance.py`: a
scripted turn that calls the kit it holds (across a backend a turn reaches
its room through its host, `host.*`). Its idle wait also waits for the work
a turn began that reaches the owner after the turn across the transport
(§10.6.3), as an ASYNC hook whose timeout falls after its turn.

## Known failures

A known failure is a scenario whose observable result breaks the RFC. Its
runner names the scenario and broken rule at an implementation revision
(roomkit's `KNOWN_FAILURES` in `tests/conformance/test_conformance.py`,
roomkit-rs's lists in `crates/roomkit/tests/conformance/main.rs` and each
store's `main.rs`, which may name a list `scenarios.rs` shares, beside the
list its shared loop reads on every store; its shared
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
- Cite the units the scenario tests in `requirements`, by their IDs in
  `requirements.json`: `"requirements": ["RK-10.4-022"]`. An unknown, retired or
  `non_testable` unit is refused. TRACEABILITY.md, "Citing units", has the rest:
  - a unit's `level` (`must`, `should`, `may`) is set in its annotation by its
    reviewer: `<!-- rfc: {"id":"RK-10.4-022",…,"level":"must"} -->`;
  - `links.lock.json` pins each citation to the unit's text; after the unit
    changes, `check.py --strict` names the scenarios to reread:
    `lock: RK-10.4-022 changed since routing/x read it: reread it, then run
    python3 conformance/check.py --pin RK-10.4-022`;
  - pin a citation by name once it is read, a unit, a scenario or both:
    `python3 conformance/check.py --pin RK-10.4-022 routing/x` pins that one
    citation, new or changed; then regenerate the report
    (`--traceability --update-traceability`);
  - the process rule, `check.py --changed-units --base-ref <full sha>`: a
    `must` unit added or changed since needs a citing scenario, a reason in
    `untested.json` (`{"RK-10.4-999": "Needs a carrier's number lookup."}`
    under `units`) or an entry in `gaps.json` (`{"RK-8.2-014": {"class":
    "step", "card": "RMK-1904"}}` under `units`); a `should` one with none of
    them warns, a unit with no level is listed as
    unreviewed, or is an error in a section every unit of which had a level at
    the base. CI runs it on every push and pull request to main, against the
    push's or the pull request's base, and fails on its errors; run it before
    pushing with `--base-ref "$(git merge-base origin/main HEAD)"`.
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

### The kit's own executor hooks

`kit_executor.close` awaits `kit.turn_executor.close()`; `kit_executor.closed`
reads its `closed` property. Neither takes arguments. Closing the local executor
refuses new turns and cancels other running turns, sparing those the call runs
under; the kit and its registered transports remain usable (§10.6.7–§10.6.8).

`kit_executor.hook` registers `hook` on `kit.turn_executor.hook`; it takes
`setup.hooks`' fields except `router` and `needs_lock`. `kit_executor.room_hook`
defines the hook under its `name` on that executor: `name`, `trigger`,
`execution`, `priority`, `timeout_ms`, `fail_closed` and `reactions`.
`kit_executor.remove_room_hook` takes `name` and returns whether that definition
was removed. None of these definitions activates a hook for a room.
`kit_executor.add_owner_room_hook` is no definition: it gives the executor a
hook for one room, below the kit (Calls).

`enable_room_hook` and `disable_room_hook` take `room_id`, `name` and optional
`organization_id`. Enable is idempotent; disable returns whether the name was
selected. A turn keeps the names its request carried, while each firing reads
the current definitions of those names (RFC §10.6.6).

### Served skill registries

`skill_registry_session` exercises public `SkillRegistry` operations against
scripted `MCPSkillServer` implementations. It takes a `servers` map and nonempty
`operations`. Each server declares optional `extensions` (the skills extension
by default) and ordered `replies`: `{method, params, result|error}`. Parameters
must match exactly, every reply is consumed once, and unexpected requests or
unused replies fail independently of any error the registry sanitizes. These
scenarios cover the registry boundary; MCP transport framing has its own host
sessions below. A server may also script host `approvals`: booleans or
`{error: text}` failures. Omitting them registers no callback; an empty list
registers one that must not be called. Every answer is consumed exactly once,
and exhaustion remains a fixture failure even when the SDK refuses execution.

Operations select a `registry` (default `main`). They name `add_mcp_server`
(`server`, `label`, optional `allow_dynamic` and `execution_tools`), `get_skill`
or `load_skill` (`name`), `read_file` (`name`, `filename`), `origin` or
`is_served` (`name`), `copy` (`target`, optional `names` and `marks`),
`mark_unavailable` (`name`, `reason`), `mark_unlisted` (`name`), or `snapshot`.
`install_channel` takes a scripted `channel` with a `model` and installs the
selected registry as its skills; a second local `skills` definition is refused.
`room_call` takes an `action` using the ordinary call vocabulary, then drains
the room. Registry sessions cannot be nested. The existing model observers
record those real turns, including prompts and tool results.
Copies use the SDK's shared catalogue and cache; the fixture keeps no duplicate
catalogue. Snapshot reads the public metadata, names, marks, manifest and tool
patterns without loading or following a cached skill.

The result holds an ordered `results` list, `requests` by server, and
`approvals` containing the actual six-field host requests by server. Each
operation returns `{status: "ok", result: value}` or
`{status: "error", error: name, message: text}`. The explicit status prevents
a missing result on a refusal from matching an expected null result. Loaded skills expose their instructions, metadata, references,
origin, held URI, bytes read and verified cache (hexadecimal bytes by URI).
No path on the host filesystem is used to represent served content.

### MCP host sessions

`mcp_session` runs public `MCPToolProvider` operations against a local HTTP
peer. The entire connection belongs to the call's coroutine, including its
explicit `connect`/`close` operations. It takes `peer`, `operations`, optional
`discover` (default true), and optional `tool_filter` (the admitted names).
No SDK request/resource method is replaced by a fake.

The peer answers `initialize` with MCP `2025-11-25` (the last protocol
version using that handshake), resources capability and its optional `server_info`, `extensions`
and `instructions`. `replies` is an ordered script of `{method, params?,
result|error|hold}`. Each request must match the next method and params
(omitted script params mean `{}`; only the initial discovery `tools/list`
may omit empty wire params). Numeric SDK progress tokens are omitted only
while observing discovery or the public `call_tool` operation. Explicit host
`request` parameters, including `_meta`, stay exact; other metadata is never
removed. HTTP requests, including notifications, remain in the raw observation.
Exactly one result, protocol error (`code`, `message`,
optional `data`) or `hold: true` is required. A held request gets no answer
before its client closes it. Unexpected requests, unused replies and fixture
errors fail the scenario independently of client errors. `framing` selects
JSON (default) or SSE replies. The HTTP peer uses an ephemeral loopback port,
closes every connection and bounds each request body to 4 MiB.

Operations name `connect`, `close`, `connected`, `tool_names`, `tool_meta`,
`server_info`, `server_extensions`, `request` or `read_resource`. Request
uses `name` for its method and optional `params`; resource reads take `uri`.
Both accept `timeout_ms`, passed to the public deadline option. Snapshot
operations may carry `mutate: {path: [key, ...], value: ...}`: mutate the
returned object before recording it, so the next read proves whether it was
an owned copy. No provider private state is read.

The call returns `results` (each `{result: value}` or `{error: name}`,
plus the server message for MCP errors) and
`requests` (wire method and params in order; initialize is recorded by method
only). Resources are normalized from the public model with JSON aliases and
only fields sent by the peer, retaining explicit nulls and extension fields;
request and information values are the public return values themselves.
Expected errors are `not_connected`, `mcp_error`, `timeout` and
`validation_error`. Every other
exception is a runner failure. Explicit close and final cleanup occur in the
same coroutine as connect. Native stdio and concurrent-close witnesses remain
separate; a successful HTTP session does not certify those boundaries.

A peer may instead provide `initializations`, a nonempty list of handshake
snapshots with optional `server_info`, `extensions` and `instructions`. Each
new connection takes the next snapshot; exhausting or leaving one unused is
a fixture error. This lets one provider reconnect to a changed catalogue.

MCP sessions also return `results_json` and `requests_json`: canonical JSON
with sorted object keys, UTF-8 characters and no insignificant whitespace.
These exact expectations prove explicit nulls and absent fields in addition
to the general partial-object matcher. Each operation result is frozen before
the next operation. Invalid raw result metadata, resource inputs and content
URI parsing failures are recorded as `validation_error`; normalization is
observed through the public model. Extension declarations remain opaque peer
data, so a non-object declaration can exercise the provider's own handling.

MCP sessions may select `constructor: "direct"` (the common constructor)
or `"from_url"` (the default), and `transport: "sse"` for legacy SSE or
`"streamable_http"` (the default). Legacy SSE opens a GET stream, reads its
announced POST endpoint and receives JSON-RPC replies on that stream; it is
distinct from the existing peer's `framing: "sse"` Streamable HTTP replies.
`headers`, `label` and `connect_timeout_ms` are passed to public construction.
`headers_after_construction` requires `headers` and replaces the original
mapping's contents before connection, exposing retention of a nonempty map
and replacement of an empty map. No provider private state is inspected.

The additional `call_tool` operation takes `name`, optional object `arguments`
and optional `timeout_ms`; it invokes the public text-returning method.
Repeated `connect` while connected is observed as `already_connected`.
A legacy peer's optional `endpoint_on_connections` is a nonempty boolean list:
each GET either announces its endpoint or leaves it pending. Every entry must
be consumed, so a timeout/reconnect scenario cannot hide a missing connection.
Explicit close and connection timeout wait for the peer to observe GET closure.

Legacy sessions additionally return `http` and exact `http_json`, with the
number of opened/closed GET connections and the ordered HTTP requests
(`method`, `target`, selected `headers`). Header names are normalized to lower
case on this wire observation; values, duplicate occurrences and their order
are preserved. Only names supplied by the scenario are selected, excluding
client-generated headers. This records the actual endpoint path and query,
including initialized notifications, rather than inferring them from MCP calls.

### Direct text prompts

`agent.direct_prompt` takes `room_id`, `channel_id` and an `event` template
with its source. It wires the live scripted AI channel through the kit's turn
executor, calls its public `on_event` with that room's current binding and
context, and consumes its response. The result is the channel's `responded`
flag. Room subscribers observe publications through the usual expectations.

### Host tool definitions

`agent.extra_tools` takes `channel_id` and reads the public host definitions,
in constructor order, with all six `AITool` fields. `agent.replace_extra_tool`
is a fixture operation: it takes `channel_id`, zero-based `index`, and a complete
`definition` (name and description required; the other fields use their usual
defaults). It reads that element through the public accessor and assigns its
fields in Python, or replaces the shared handle in Rust. It does not install
or remove a tool, or change the handler. These operations precede a turn's
preparation; they make no claim about references a running provider retained.
