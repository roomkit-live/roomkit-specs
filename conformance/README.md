# The RoomKit conformance suite

Scenarios that every implementation of RoomKit runs, as the executable form of
the RFC's rules. A scenario is data, written in the RFC's serialized form (§1.4
names "conformance fixtures" among what that form is for): a setup, the kit's
calls, and what the RFC says they come to. Each implementation has a runner
that reads the scenarios and runs them on its own core; the suite says nothing
of either implementation's API.

This is the first cut (roomkit-rs step 3, milestone 1). It covers Level 0
without the turn backend and streaming; "Coverage" says what it holds and what
it does not yet.

## Layout

| Path | What it is |
|---|---|
| `scenarios/<area>/<name>.json` | One scenario; its `id` is `<area>/<name>` |
| `scenario.schema.json` | The JSON Schema every scenario validates against |
| `check.py` | The checker (below) |
| `RFC_COMMIT` | The roomkit-specs commit whose `roomkit-rfc.md` the scenarios' `rules` are checked against |

An implementation keeps a copy of `scenarios/`, taken from one commit of this
repository by its `make conformance-sync`, which records that commit beside the
copy (`SPECS_COMMIT`). The copy is never edited there.

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

It then lists, as gaps, the rows of the §26.1 trigger and framework-event table
that no scenario asserts (a trigger is asserted by a scenario that expects calls
of a hook on it, a framework event by one that expects it), and the reentrancy
cells no scenario names. A change to the RFC that moves a rule fails the check
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

Made before anything is recorded: framework events, hook calls and deliveries
of the setup are not compared.

- `kit`: `max_chain_depth` (default 5) and `process_timeout_ms` (the
  implementation's default when absent).
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
  - `parse`, `deliver` and `on_event` hold its **reactions** (below).
- `rooms`: each is created (`id`, `organization_id`, `metadata`, `timers`),
  then each of its `bindings` attached (`channel_id`, `category`, `access`,
  `muted`, `visibility`, `metadata`, `participant_id`); a `status` of
  `closed` or `archived` is reached through the kit's own transitions.
- `hooks`: each is registered on the kit: `name`, `trigger` (a HookTrigger:
  `before_broadcast`, `after_broadcast`, `on_room_created`...), `execution`
  (default `sync`), `priority`, `timeout_ms`, `channel_types`, `channel_ids`,
  `directions`, `fail_closed`, `needs_lock`, and its `reactions`. A
  **scripted hook** records each call (its trigger, the room of its context,
  its payload), then reacts; with no reaction it allows.

### Reactions

A channel's or a hook's reactions are tried in order on each call: the first
whose `when` holds is used, once, unless it has `"repeat": true`. When none is
left, the call does what it does by default. A reaction:

| Member | What it does |
|---|---|
| `when` | Holds when every member equals the call's: `room_id`, `text` (a text content's body), `type` (the event type), `source_channel_id`, `chain_depth` |
| `gate` | Holds the call at this gate until a step opens it |
| `do` | Kit calls the hook or the channel makes while it runs, in its execution context, in order: an **action** is a call (below) with an optional `as` and `expect`. Its error is caught, kept and checked, never raised into the kit |
| `fail` | Then raises, with this message |
| `respond` | Event templates: the turn's response events (`on_event` only) |
| `output` | `tasks`, `observations` and `metadata_updates` of the channel's output |
| `result` | A hook's HookResult (§9.4). A modify's `event` is a patch on the payload: its members replace the payload's. Its injected events, tasks and observations are templates |

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

### Steps

| Step | What it does |
|---|---|
| a call | Makes the call and waits for it; `expect` checks its outcome |
| a call with `"background": true` and `as` | Starts the call and goes on |
| `{"await": label}` | Waits for the background call; `expect` checks its outcome |
| `{"concurrent": [calls]}` | Starts the calls together and waits for all |
| `{"wait_for": gate}` | Waits until a call is held at the gate (a runner fails after 5 s) |
| `{"open": gate}` | Opens the gate: every call held there, and every later one, goes on |
| `{"idle": true}` | Waits until the kit runs nothing in the background |

A call that has not returned after 10 s fails the scenario.

### Calls

Each takes the RFC's name and the RFC's arguments, and may name an
`organization_id` it acts for (§17.2). Records are in the serialized form.

| Call | Arguments | Result |
|---|---|---|
| `process_inbound` | `message` (an InboundMessage), `room_id` | an InboundResult: `event`, `blocked`, `reason`, `error` (its message), `response_metadata`, `delivery_results` |
| `send_event` | `room_id`, `channel_id`, `content`, `event_type`, `participant_id`, `visibility`, `response_visibility`, `addressed_to`, `parent_event_id`, `idempotency_key`, `metadata`, `chain_depth`, `standalone` | the event |
| `post` | `room_id`, `content`, `participant_id`, `addressed_to`, `metadata`, `channel_id`, `idempotency_key`, `chain_depth` | the event |
| `commit_event` | `room_id`, `event` (a template) | the event |
| `update_event` | `room_id`, `event_id`, `content`, `source`, `metadata` | the event, or null |
| `delete_event` | `room_id`, `event_id`, `cascade_replies` (default true) | the ids removed |
| `create_room` | `room`: `id`, `organization_id`, `metadata`, `timers` | the room |
| `attach_channel` | `room_id`, `channel_id`, and a binding's `category`, `access`, `visibility`, `muted`, `metadata`, `participant_id` | the binding |
| `detach_channel` | `room_id`, `channel_id` | unspecified |
| `mute`, `unmute` | `room_id`, `channel_id` | the binding |
| `set_access`, `set_visibility` | `room_id`, `channel_id`, `access` or `visibility` | the binding |
| `close_room`, `archive_room` | `room_id` | the room |
| `check_timers` | `room_id` | the room, once its due transitions are applied |
| `register_channel` | `channel` (as in the setup) | null |
| `unregister_channel` | `channel_id` | null |
| `register_hook` | `hook` (as in the setup) | null |

**References.** A string argument may name what the run made:

- `$room`, `$event`: in an action, the room of the hook's or the channel's
  context, and the event it runs for;
- `$r1`, `$r2`...: the rooms the run created that the scenario does not name,
  in the order of their `room_created`;
- `<room>#<rank>`: the event of that rank in the room's timeline as it stands
  when the call is made (Normalization);
- `$<label>`: the event the call labelled `<label>` returned.

### Expectations

`expect` names what is compared; what it does not name is not.

| Member | What is compared |
|---|---|
| `timeline` | Per room, the whole timeline in index order, `BLOCKED` records included, lifecycle records left out |
| `rooms`, `bindings` | Per room, the room record; per room and channel, the binding, `null` for none |
| `framework_events` | Per room (`*` for the events of no room), every framework event of the §26.1 table and `process_timeout`, in emission order |
| `hooks` | Per scripted hook, its calls in order: `trigger`, `room_id`, `event` (the payload, when an event) |
| `hook_order` | The order in which the hooks it lists were called |
| `deliveries` | Per room and channel, the events a scripted channel's `deliver()` received, as delivered, in order |
| `turns` | Per room and intelligence channel, the events its `on_event()` received |
| `observations`, `tasks` | Per room, the stored side effects |
| `actions` | Per action label, the outcomes of its runs, in the order they ended |

An outcome is `{"result": ...}`, matched as below, or `{"error": name}` (or
`{"error": {"name": ..., "reason": ...}}`). A call whose outcome names neither
must not fail. An action with no `expect` must not fail either, unless
`expect.actions` checks its label.

Each runner also checks, for every scenario, that no lifecycle record was
delivered or handed to a turn (§5.1).

### Normalization

Before matching, a runner rewrites what changes from run to run, and what
the RFC leaves to each implementation:

- **Lifecycle records** (§5.1: the framework's source, the visibility
  `internal`, a system content) MAY be written, so they are left out of the
  timelines, and every index is read without them: an event's `index`
  becomes its **rank**, the number of the room's other events at a lower
  index (an instruction's provisional index too). Appendix B counts the same
  way.
- **Rooms** the run created and the scenario does not name are `$r1`, `$r2`...
  in the order of their `room_created`.
- **Events** of a timeline are `<room>#<rank>`, wherever their id appears.
  Any other event id (an instruction, a refused event, an event a hard delete
  removed) is `$e1`, `$e2`... in the order the step outcomes, then the
  framework events, show it first.
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
- `{"$contains": "text"}`: a string holding the text.

In `framework_events` a bare string names the event: `"room_created"` is
`{"event": "room_created"}`.

## Errors

A call's error is named by what it means in the RFC, never by an
implementation's class. A runner maps its errors with the table below, which
extends roomkit-rs `docs/rfc-gaps.md` G-085's; an error that maps to no name
fails the scenario.

| Name | RFC meaning | roomkit (Python) | roomkit-rs |
|---|---|---|---|
| `invalid_argument` | An argument refused before anything is read or written: the visibility `internal` (§7.3), a channel id the grammar refuses (§7.3), `standalone` on another type and an instruction's refusals on a direct injection (§10.1.1), a record naming another room (§10.5), a post from a channel that is not a host channel, a message on a host channel (§10.5), a host channel bound as an intelligence channel, a reserved room metadata key (§5.1), a hook registration §9.1 refuses | `ValueError` | `InboundError::{NotAHostChannel, InboundOnHostChannel, HostAsIntelligence, StandaloneOutsideInstruction, InternalVisibility}`, `Refused` with an instruction's reason, `LifecycleError::{InternalVisibility, HostAsIntelligence, ReservedMetadataKey}`, `MutationError::OtherRoom`, `KitError::{Config, Registration}`, a `ChannelId` refused |
| `channel_not_registered` | The channel named is not registered (§10.1 step 1, §10.5) | `ChannelNotRegisteredError` | `InboundError::UnknownChannel`, `KitError::UnknownChannel` |
| `room_not_found` | No such room, or another organization's (§17.2) | `RoomNotFoundError` | `InboundError::{RoomNotFound, OtherOrganization}`, `LifecycleError::RoomNotFound`, `MutationError::RoomNotFound` |
| `channel_not_bound` | The room does not bind the channel: a direct injection or a post from it (§10.5), a detach or a binding change of it (§7.2) | `ChannelNotFoundError`; `detach_channel()` answering `False` | `Refused { reason: "source_unbound" }`, `LifecycleError::ChannelNotBound` |
| `room_closed` | The room's status refuses new events (§5.1) | `RoomClosedError` | `Refused { reason: "room_closed" }`, `MutationError::Refused` |
| `transition_refused` | A transition from a status it does not leave from (§5.1) | `TransitionRefusedError` | `LifecycleError::TransitionRefused` |
| `change_refused` | An edit or a delete step 8a refuses, with its `reason` (§10.1 step 8a, §10.5) | `ChangeRefusedError` | `Refused` with one of step 8a's reasons |
| `process_timeout` | `process_timeout` passed before the commit (§13.6) | `ProcessTimeoutError` | `Refused { reason: "process_timeout" }` |
| `participant_not_found` | A post's speaker is no participant the host channel reaches (§10.5) | `ParticipantNotFoundError` | `InboundError::ParticipantNotFound` |
| `reentrant` | A message routed back into the room whose lock or admission order its caller holds (§9.5.1 A message routed back) | `ReentrantCallError` | `KitError::Reentrant` |
| `reentry_loop_cap` | A direct change past its cascade's hook calls (§8.3, §10.3) | `ReentryLoopCapError` | `MutationError::ReentryLoopCap` |

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

102 scenarios. Counted by the sections their `rules` cite (a scenario counts once
under each section it cites):

| Section | Scenarios | Section | Scenarios |
|---|---|---|---|
| §5.1 | 13 | §9.5.1 | 13 |
| §5.2, §5.8, §4.2 | 1 each | §10.1 | 42 |
| §6.6 | 7 | §10.1.1 | 4 |
| §7.2 | 4 | §10.2 | 10 |
| §7.3 | 5 | §10.3 | 11 |
| §7.4 | 2 | §10.4 | 4 |
| §7.5 | 15 | §10.5 | 18 |
| §8.1 | 1 | §13.4 | 3 |
| §8.2 | 18 | §13.5 | 7 |
| §8.3 | 6 | §13.6 | 3 |
| §9.1 | 4 | §17.2 | 2 |
| §9.2 | 11 | §19.3, §19.3.1 | 4, 1 |
| §9.3 | 8 | §26.1 | 37 |
| §9.4 | 6 | Appendix B.1, B.2, B.4, B.5, B.6, B.7 | 1 each |

Every row of the §26.1 trigger and framework-event table is asserted by at least
one scenario, and each of the 16 reentrancy cells is named by one.

**Not covered yet** (M1's second pass):

- §7.5 rule 8 and §10.1.1 rule 7: what a channel is handed of the room's history
  (a scripted turn does not record its context yet), a deleted event's content
  withheld from it (§10.3);
- §7.5 rule 6 (a binding never widened), which needs delegation;
- §5.1: the integrator's pause, resume and reopen (roomkit has no `pause_room`
  or `resume_room` call), the activity a `BLOCKED` record or a record does not
  count, the shape of a lifecycle record when one is written;
- §8.5: response visibility and its narrowing; §9.4: the response visibility a
  modify narrows;
- §9.3: unusable results other than a raise or a timeout (a modify with no
  payload, a payload of the wrong type), `hook_invalid_result`; a failing
  off-lock hook's `hook_error` and `hook_timeout`; ON_ERROR's categories but
  `generation`;
- §9.5.1: the ticket's release on every path, a hook body's budget once it
  returned (a spawned task), "Past the cap" for messages and posts;
- §10.1: step 2's re-routing when the locked check finds the room no longer the
  sender's, `group` bindings, recipient keys and replies to a chat (§5.7), a
  room created concurrently by two calls; step 18's detached completion;
  explicit delivery cancellation;
- §10.3: ADMIN and SYSTEM deletes, a hook's injected change, an edit's
  visibility narrowed to its target's, `cascade_replies = false`;
- §10.4: identity-based routing (`resolve_identity`), a PAUSED room, a
  delivery status's routing;
- §10.5: a post's idempotency key, its `chain_depth`, a detached host channel,
  a post from the room's own work past the budget;
- §13.4: a key a hard delete removed; §13.5: a failed lock release;
  §13.6: a caller that stops waiting (a timing race, left to each
  implementation);
- §17.2: the remaining calls acting for another organization (an attach, a
  post, a room's creation), a routed message's identity read in its
  organization;
- §19.3.1: `ADDRESSED_ONLY`; the turn backend (§10.6) and streaming, out of
  scope for step 3.

## Known failures

A scenario an implementation fails because the implementation breaks the RFC.
Its runner lists it (roomkit `KNOWN_FAILURES` in
`tests/conformance/test_conformance.py`, roomkit-rs `KNOWN_FAILURES` in
`crates/roomkit/tests/conformance/main.rs`); the runner expects it to fail and
fails once it passes, so a fix shows and takes it off both lists. The fixes
are not made here: roomkit-rs's are milestone 2's, roomkit's cards of their own.

| Scenario | Implementation | The rule broken | Probe |
|---|---|---|---|
| `inbound/an-agent-s-output-updates-the-room` | roomkit 5635662c | §10.1 step 15: the room metadata updates of a cascade's channel outputs are never applied. `EventRouter` merges them into `BroadcastResult.metadata_updates`, which nothing reads | An agent answering `ChannelOutput(responded=True, metadata_updates={"stage": "q"})` leaves the room's metadata `{}`; roomkit-rs writes `stage` |
| `injection/an-injection-from-an-unregistered-channel-raises` | roomkit 5635662c | §10.5 ("The channel it names MUST be registered"): `send_event()` from a channel no one registered raises `ChannelNotFoundError` ("Channel nope not in room room-1"), the error of a channel the room does not bind, not `ChannelNotRegisteredError` | `kit.send_event("room-a", "nope", TextContent(body="x"))` raises `ChannelNotFoundError` |
| `hooks/an-async-hook-on-a-sync-trigger-observes` | roomkit-rs 8f8be5a | §9.2: on a SYNC trigger, the hooks registered ASYNC run as observers once the chain allowed. A hook registered ASYNC on `BEFORE_BROADCAST` never runs: `HookRegistry::observers` would list it, but the inbound operation fires no observer of `BEFORE_BROADCAST` | The scenario's `watcher` is never called (`hook_order` is `["rewrite"]`); roomkit calls it with the rewritten payload |

## Writing a scenario

- Expect what the RFC says, not what an implementation does. Where the RFC
  leaves a point open (the order of two framework events no rule orders, which
  of two concurrent deliveries ends first, a lifecycle record, a counter that
  counts lifecycle records), do not assert it: use `$unordered`, or leave the
  member out.
- Cite each rule the scenario relies on in `rules`, as precisely as the RFC
  allows; `check.py` must resolve it.
- Give every member you assert in a template, and a reason to every block.
- Keep timing out of it: a gate orders two calls, never a delay. A hook's or a
  call's timeout, when the scenario is about it, is a few tens of milliseconds.
- Run `check.py --fix`, then both runners, before committing. A scenario that
  fails on an implementation is either wrong, and fixed, or a known failure,
  listed above with its probe.
