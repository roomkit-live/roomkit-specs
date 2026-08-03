# RFC: RoomKit — Multi-Channel Conversation Framework

| | |
|---|---|
| **Status** | Draft |
| **Author** | Sylvain Boily |
| **Contributions** | TchatNSign, Angany AI |
| **Version** | v16 Draft |
| **Created** | 2026-01-27 |
| **Last Updated** | 2026-07-25 |
| **Supersedes** | v15 Draft |

---

## Abstract

RoomKit is a specification for a multi-channel conversation framework that unifies
humans, AI agents, and programs in shared conversation spaces called Rooms. This
document defines the data models, processing pipelines, channel abstractions,
permission system, hook engine, identity resolution, voice architecture, and
resilience patterns that constitute a conforming RoomKit implementation.

The specification is language-agnostic. Implementations MAY be written in any
programming language. All examples use pseudocode or structured notation.

---

## Table of Contents

1. [Conventions and Terminology](#1-conventions-and-terminology)
2. [Introduction](#2-introduction)
3. [Architecture Overview](#3-architecture-overview)
4. [Core Concepts](#4-core-concepts)
5. [Data Models](#5-data-models)
6. [Channel System](#6-channel-system)
7. [Permission Model](#7-permission-model)
8. [Event System](#8-event-system)
9. [Hook System](#9-hook-system)
10. [Processing Pipelines](#10-processing-pipelines)
11. [Identity Resolution](#11-identity-resolution)
12. [Voice and Realtime Media](#12-voice-and-realtime-media)
13. [Resilience and Error Handling](#13-resilience-and-error-handling)
14. [Storage Interface](#14-storage-interface)
15. [Observability](#15-observability)
16. [Integration Surfaces](#16-integration-surfaces)
17. [Security Considerations](#17-security-considerations)
18. [Design Principles](#18-design-principles)
19. [Multi-Agent Orchestration](#19-multi-agent-orchestration)
20. [Memory System](#20-memory-system)
21. [Tool Access Control](#21-tool-access-control)
22. [Delivery Strategies](#22-delivery-strategies)
23. [Task Delegation](#23-task-delegation)
24. [Skills Framework](#24-skills-framework)
25. [Conformance Levels](#25-conformance-levels)
26. [Appendix A: Channel Reference](#appendix-a-channel-reference)
27. [Appendix B: Complete Event Flow Examples](#appendix-b-complete-event-flow-examples)

---

## 1. Conventions and Terminology

### 1.1 Key Words

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

### 1.2 Definitions

| Term | Definition |
|---|---|
| **Room** | A conversation space where channels connect and events flow. The unit of state. |
| **Channel** | Any entity that interacts with a Room — transports messages, generates AI responses, or observes events. |
| **Event** | An immutable record of something that happened in a Room (message, system event, status change). |
| **Participant** | A human (or system identity) taking part in a Room conversation. |
| **Identity** | A cross-channel representation of a person, linking addresses across channel types. |
| **Provider** | An interchangeable implementation behind a channel (e.g., Twilio behind SMS). |
| **Source** | A persistent connection that pushes inbound events (as opposed to webhook pull). |
| **Hook** | A pluggable function that intercepts, blocks, modifies, or reacts to events. |
| **Binding** | The attachment of a channel to a room, including permissions and metadata. |
| **Side Effect** | A task or observation produced by a channel or hook, not subject to permission restrictions. |
| **Chain Depth** | The number of re-entries an event has caused (AI responds to AI responds to...). |
| **Integrator** | The developer building an application on top of a RoomKit implementation. |
| **Broadcast** | The act of routing an event to all eligible channels in a Room. |
| **Transcoding** | Converting event content from one format to another for cross-channel delivery. |
| **Audio Pipeline** | A configurable chain of audio processing stages (resampler, AEC, AGC, denoiser, VAD, diarization, DTMF, recording) between the transport and the conversation engine. |
| **AI Pipeline** | A configurable chain of AI generation stages (pre-context gates, memory retrieval, tool resolution, prompt assembly, pre-generation gate, generation, post-generation, emission) between an AIChannel receiving an event and emitting a response. Peer abstraction to Audio Pipeline and Video Pipeline. |
| **ACP** | Agent Client Protocol — a protocol for communication between code editors or conversation hosts (clients) and coding agents (servers). |
| **AEC** | Acoustic Echo Cancellation — removes the bot's own audio from the inbound stream to prevent self-triggering. |
| **AGC** | Automatic Gain Control — normalizes audio volume to a consistent level regardless of input device or distance. |
| **DTMF** | Dual-Tone Multi-Frequency — telephone keypad tones used for IVR navigation and call control. |
| **PLC** | Packet Loss Concealment — synthesizing replacement audio for packets confirmed lost in transit, preserving the temporal continuity of the inbound stream. |
| **Turn Detection** | The process of determining whether a speaker has finished their conversational turn, using acoustic and/or semantic signals. |
| **Backchannel** | Short verbal acknowledgments ("mmhmm", "ok", "yes") that signal attention without requesting a turn change. |
| **Protocol Trace** | An immutable record of a transport-level protocol exchange (e.g., SIP INVITE, 200 OK, BYE) emitted by a channel for observability and debugging. |
| **Agent** | An AIChannel subclass with structured identity metadata (role, description, scope, voice) for multi-agent orchestration. |
| **Orchestration** | The system that routes events to the correct agent, manages conversation phases, and handles agent-to-agent handoffs. |
| **Handoff** | The transfer of conversation responsibility from one agent to another, with context preservation. |
| **ConversationState** | Per-room state tracking the current phase, active agent, and orchestration metadata. |
| **Memory Provider** | A pluggable strategy for constructing AI conversation history (sliding window, summarization, retrieval, etc.). |
| **Tool Policy** | Access control rules (allow/deny glob patterns with role overrides) governing which tools an AI agent can invoke. |
| **Steering Directive** | A mid-generation instruction (Cancel, UpdateSystemPrompt, InjectMessage) injected into an active AI tool loop. |
| **Delivery Strategy** | A strategy controlling when proactive content (task results, notifications) is delivered into a conversation (Immediate, WaitForIdle, Queued). |
| **Delegation** | Dispatching background work to a specialized agent in an isolated child room, with result collection and delivery. |
| **Skill** | A self-contained, discoverable package of agent instructions, reference materials, and scripts defined by a SKILL.md file. |
| **Video Pipeline** | A configurable chain of video processing stages (decoder, resizer, transform, filter, overlay) between the transport and the vision/recording engine. |
| **Vision Provider** | A pluggable service that analyzes video frames and produces structured results (descriptions, labels, faces, OCR text). |
| **Avatar Provider** | A service that generates lip-synced video frames from TTS audio for visual agent embodiment. |
| **Video Bridge** | A component that forwards video frames between sessions in the same room, with keyframe buffering and PLI requests. |
| **StatusBus** | A shared event log for inter-agent coordination, allowing agents to post and subscribe to status updates without sending room events. |
| **Tool Auditor** | A pluggable recorder that captures every tool call (input, output, timing, status) for debugging and monitoring. |
| **Session Auditor** | A pluggable recorder that captures the full conversation timeline (speech, tool calls, vision, interruptions) for compliance and replay. |
| **SFU** | Selective Forwarding Unit — a media server that routes encoded media streams between conference participants without decoding or mixing them. |
| **Conference** | A multi-party real-time media session (audio, video, screen share) attached to a Room, whose media plane is owned by an external SFU. |
| **Track** | A single media stream (audio, video, or screen share) published by a conference participant. The unit of media identity in a conference. |
| **Bot Participant** | The framework's own server-side connection to a conference, used to subscribe to tracks (STT, vision, recording) and publish media (TTS, avatar). |
| **Egress** | Server-side media export performed by the SFU (e.g., conference recording), as opposed to framework-side recording. |

### 1.3 Notation

Data models are described using structured notation:

```
ModelName
├── field_name: Type                    # Required field
├── field_name: Type = default_value    # Field with default
├── field_name: Type | null             # Nullable field
└── field_name: map<string, any>        # Dictionary/map type
```

Enumeration values are written in UPPER_SNAKE_CASE. Field names use snake_case.

---

## 2. Introduction

### 2.1 Problem Statement

Modern conversations span multiple channels — a customer starts on SMS, continues
on WhatsApp, while an AI assistant and human advisor collaborate behind the scenes.
Each channel has different capabilities, protocols, and constraints. Building
applications that manage these multi-channel conversations requires solving the same
set of problems repeatedly: message routing, permission management, event ordering,
identity resolution, and channel abstraction.

### 2.2 Scope

RoomKit provides **primitives for multi-channel conversations**, not business logic.

**RoomKit IS:**

- A room-based conversation manager
- A unified channel abstraction (SMS, Email, AI, Voice — same interface)
- A permission system (access, mute, visibility)
- A hook engine (intercept, block, modify, enrich)
- A provider abstraction layer (channel type ≠ provider)
- An identity resolution pipeline

**RoomKit is NOT:**

- A CPaaS provider (Twilio, Sinch, etc. own the transport)
- An AI framework (LLM libraries handle agent logic)
- A chat application (RoomKit provides primitives; integrators build apps)
- Opinionated about when or why to use its primitives

### 2.3 Design Philosophy

The framework provides primitives. The integrator provides business logic.

```
FRAMEWORK provides                 INTEGRATOR decides
─────────────────────              ────────────────────
Channel access primitives          When to set each access level
Mute / unmute operations           When to mute or unmute
Visibility rules                   What visibility each channel gets
Attach / detach channels           Which channels to attach when
Hook pipeline (sync/async)         What hook handlers to register
Hook block + inject                What to block and what to inject
Event routing and permissions      Room setup and configuration
Two output paths                   What tasks and observations to create
Provider abstraction               Which provider to use
Identity resolution interface      Resolution strategy
Storage interface                  Storage implementation
Event chain depth limit            Turn budgets and orchestration
Audio pipeline stages              Which resampler, AEC, AGC, denoiser, VAD, etc. to use
```

---

## 3. Architecture Overview

A conforming RoomKit implementation consists of the following layers:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Integration Surfaces                            │
│                                                                     │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐      │
│   │   REST API    │    │  MCP Server   │    │   WebSocket   │      │
│   │  (humans,     │    │  (AI agents,  │    │   (real-time  │      │
│   │   systems)    │    │   tools)      │    │    clients)   │      │
│   └───────┬───────┘    └───────┬───────┘    └───────┬───────┘      │
└───────────┼────────────────────┼────────────────────┼──────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          RoomKit Core                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │    Room       │  │    Event     │  │   Identity   │              │
│  │   Manager     │  │   Router     │  │   Resolver   │              │
│  └──────────────┘  └──────┬───────┘  └──────────────┘              │
│                           │                                         │
│                    ┌──────┴───────┐                                  │
│                    │  Hook Engine │                                  │
│                    └──────┬───────┘                                  │
│                           │                                         │
│  ┌──────────────────────────────────────┐                           │
│  │       Conversation Store (ABC)       │                           │
│  │    (Rooms, Events, Identities)       │                           │
│  └──────────────────────────────────────┘                           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
              Channel Interface (unified for ALL)
                         │
      ┌──────────┬───────┴──┬──────────┬──────────┬──────────┐
      ▼          ▼          ▼          ▼          ▼          ▼
 ┌────────┐┌────────┐┌─────────┐┌──────────┐┌────────┐┌─────────┐
 │  SMS   ││ Email  ││  HTTP/  ││    AI    ││ Voice  ││ Custom  │
 │Channel ││Channel ││  WS     ││ Channel  ││Channel ││ Channel │
 └───┬────┘└───┬────┘└─────────┘└────┬─────┘└───┬────┘└─────────┘
     │         │                     │           │
  Provider  Provider              Provider    Provider
  Layer     Layer                 Layer       Layer
     │         │                     │           │
     ▼         ▼                     ▼           ▼
 ┌────────┐┌────────┐          ┌─────────┐┌──────────┐
 │Twilio  ││Elastic │          │Anthropic││ Deepgram │
 │Sinch   ││  Email │          │OpenAI   ││ElevenLabs│
 │Telnyx  ││SendGrid│          │Gemini   ││SherpaONNX│
 │VoiceMeUp│         │          │Mistral  ││ Google   │
 └────────┘└────────┘          │XAI/Grok ││ OpenAI   │
                               │Azure    ││ Gradium  │
                               │vLLM     ││ Qwen     │
                               └─────────┘└──────────┘
```

### 3.1 Layer Responsibilities

| Layer | Responsibility |
|---|---|
| **Integration Surfaces** | REST API for humans/systems, MCP for AI agents, WebSocket for real-time |
| **RoomKit Core** | Room lifecycle, event routing, hooks, permissions, identity, store |
| **Channel Interface** | Unified abstraction — every channel implements the same interface |
| **Provider Layer** | Interchangeable implementations behind channels |

### 3.2 Key Separations

1. **Channel type and Provider are separate.** SMS is a channel type. Twilio is a provider. Swap providers without changing room logic.
2. **Core and Integration Surfaces are separate.** Core has no web framework dependency. REST/MCP/WebSocket are thin wrappers.
3. **Framework and Business Logic are separate.** Framework provides primitives. Integrator registers hooks and configures channels.
4. **Transport and Audio Processing are separate.** The transport delivers raw audio frames. The audio pipeline (resampler, AEC, AGC, denoiser, VAD, diarization, DTMF, recording) is a distinct layer with pluggable providers, independent of the transport choice.

---

## 4. Core Concepts

### 4.1 The Room

A Room is a conversation space where channels connect and events flow through.

**Properties:**

- **Channel-agnostic** — A Room does not know whether it carries SMS or AI traffic.
- **Multi-channel** — SMS + WebSocket + AI + Observer simultaneously.
- **Dynamic** — Channels can be attached, detached, muted, or reconfigured at any time.
- **Observable** — Hooks and read-access channels see everything in the Room.
- **Persistent** — Rooms survive session boundaries, channel switches, and escalations.

A Room holds no message content directly. Content lives in Events stored in the
Room's timeline.

### 4.2 The Channel

**Everything** that interacts with a Room is a Channel. SMS, Email, WebSocket, AI,
Voice, Observer — all implement the same interface.

Channels are classified along two dimensions:

**Category** — what the channel does:

| Category | Purpose | Examples |
|---|---|---|
| TRANSPORT | Carries messages to/from external systems or humans | SMS, Email, WhatsApp, WebSocket, Voice |
| INTELLIGENCE | Processes events and produces responses or insights | AI agent, sentiment analyzer |

**Direction** — what the channel can do physically:

| Direction | Meaning |
|---|---|
| INBOUND | Can receive from outside only |
| OUTBOUND | Can send to outside only |
| BIDIRECTIONAL | Both receive and send |

**Three methods, three concerns:**

| Method | When Called | Direction |
|---|---|---|
| `handle_inbound()` | External payload arrives (webhook, WebSocket message, source push) | INBOUND |
| `deliver()` | Framework needs to push an event to the channel's external recipient | OUTBOUND |
| `on_event()` | A room event occurs and this channel has read access | READ |

Direction declares capability. Permissions restrict per room.

### 4.3 The Event

Everything in a Room is a RoomEvent — messages, system notifications, typing
indicators, channel state changes, participant joins/leaves. Events are immutable
once stored. Events are sequentially indexed within their room.

### 4.4 The Participant

A Participant is a human (or system identity) in the Room. AI channels and
integration channels are NOT participants — they are infrastructure. Participants
have roles, identity status, and are connected via one or more channels.

### 4.5 The Identity

An Identity is a cross-channel representation of a person. One person may be
reachable via SMS (+15551234), Email (john@example.com), and WhatsApp simultaneously.
Identity resolution maps channel addresses to a unified identity.

### 4.6 Two Output Paths

When a channel or hook processes an event, it produces output along two distinct
paths:

```
Channel/Hook Output
├── Room Events (messages, responses)
│   ├── Subject to permissions (access, mute, visibility)
│   ├── Broadcast according to write_visibility
│   └── Stored in timeline
│
└── Side Effects (ALWAYS allowed, even when muted)
    ├── Tasks (actionable work items)
    ├── Observations (passive insights)
    └── Metadata updates (enrich room data)
```

**Muting silences the voice, not the brain.** A muted AI channel cannot produce
room events but CAN produce tasks ("customer at risk of churning") and observations
("sentiment: negative").

---

## 5. Data Models

### 5.1 Room

```
Room
├── id: string                              # Unique identifier
├── organization_id: string | null          # Multi-tenant isolation
├── status: RoomStatus                      # Current lifecycle state
├── created_at: datetime                    # When the room was created
├── updated_at: datetime                    # Last modification time
├── closed_at: datetime | null              # When the room was closed
├── timers: RoomTimers                      # Auto-transition configuration
├── metadata: map<string, any>              # Integrator-defined data
├── event_count: int                        # Total events stored
└── latest_index: int                       # Highest event index (for read tracking)
```

**RoomStatus** enumeration:

| Value | Meaning | Accepts new events |
|---|---|---|
| ACTIVE | Room is active; channels can send and receive | Yes |
| PAUSED | Room is paused (e.g., after inactivity timer); can be resumed | Yes |
| CLOSED | Room is closed | **MUST be refused** |
| ARCHIVED | Room is archived; read-only historical access | **MUST be refused** |

A room's status governs whether it will accept another event, and
implementations MUST enforce that at **every** point where the timeline can
grow — an inbound message, direct injection (§10.5), a hook's injected event,
and the framework's own re-injection alike. Enforcing it only where an
inbound router happens to look is not conformant: a caller that names the room
explicitly bypasses the router entirely, and so does the framework when it
re-injects into a room it already knows.

A refused event MUST NOT be appended to the timeline, MUST NOT be broadcast,
and MUST NOT be stored as a `BLOCKED` event: a closed room accepts nothing,
and an audit record written into it would be the very thing the status
forbids. The framework MUST return a blocked result naming the refusal, and
SHOULD emit a framework event so the condition is observable — a room that has
gone quiet because it closed is otherwise indistinguishable from one whose
integration has broken.

One exception, and only one: the framework's own record of the transition —
the lifecycle hook, the framework event, and any timeline entry an
implementation chooses to write to mark it — is produced by the transition
itself rather than through the pipeline, and is not subject to this refusal.
Closing a room MUST remain observable: a room that simply goes quiet, with no
signal of why, is indistinguishable from one whose integration has broken.

CLOSED and ARCHIVED refuse identically; they differ in intent. CLOSED is a
conversation that has ended and that the integrator MAY reopen by returning
the room to ACTIVE. ARCHIVED is a terminal storage state.

Reading is unaffected by status: history, participants and bindings remain
readable at every status, and an implementation MUST NOT make a closed room
unreadable.

Closing a room does not, by itself, sever what is attached to it. Whether
`close_room()` detaches channels, ends voice sessions or leaves them in place
is an implementation's choice; what it MUST NOT do is leave a path by which a
still-attached channel can append to the closed room.

**RoomTimers:**

```
RoomTimers
├── inactive_after_seconds: int | null      # Seconds of inactivity before ACTIVE → PAUSED
├── closed_after_seconds: int | null        # Seconds in PAUSED before PAUSED → CLOSED
└── last_activity_at: datetime | null       # Timestamp of last event
```

Implementations MUST enforce timer transitions when configured. When
`inactive_after_seconds` elapses without a new event, the room MUST transition to
PAUSED. When `closed_after_seconds` elapses in PAUSED without resumption, the room
MUST transition to CLOSED.

### 5.2 RoomEvent

```
RoomEvent
├── id: string                              # Unique event identifier
├── room_id: string                         # Owning room
├── type: EventType                         # What kind of event
├── source: EventSource                     # Where it came from
├── content: EventContent                   # Normalized payload (discriminated union)
├── status: EventStatus                     # Delivery outcome
├── blocked_by: string | null               # Hook name if blocked
├── visibility: string                      # Who can see this event
├── addressed_to: list<string> | null       # Intelligence channels asked to act (§19.3)
├── index: int >= 0                         # Sequential position in room timeline
├── chain_depth: int >= 0                   # Response chain depth (loop prevention)
├── parent_event_id: string | null          # Event this is responding to
├── correlation_id: string | null           # Integrator's external reference
├── idempotency_key: string | null          # Duplicate prevention key
├── created_at: datetime                    # When the event was created
├── metadata: map<string, any>              # Integrator-defined data
├── channel_data: ChannelData               # Provider-specific structured metadata
└── delivery_results: map<string, any>      # Per-channel delivery outcomes
```

**EventType** enumeration:

| Value | Category | Description |
|---|---|---|
| MESSAGE | Core | Text, media, or rich content message |
| SYSTEM | Core | Framework-generated notification |
| TYPING | Ephemeral | User is typing |
| READ_RECEIPT | Status | User has read up to an index |
| DELIVERY_RECEIPT | Status | Provider confirms delivery |
| PRESENCE | Ephemeral | User online/offline/away |
| REACTION | Content | Emoji reaction to another event |
| EDIT | Content | Edit of a previous message |
| DELETE | Content | Deletion of a previous message |
| PARTICIPANT_JOINED | Lifecycle | Participant entered the room |
| PARTICIPANT_LEFT | Lifecycle | Participant left the room |
| PARTICIPANT_IDENTIFIED | Lifecycle | Pending participant was identified |
| PARTICIPANT_UPDATED | Lifecycle | Participant presentation changed (display name) |
| CHANNEL_ATTACHED | Lifecycle | Channel was attached to room |
| CHANNEL_DETACHED | Lifecycle | Channel was detached from room |
| CHANNEL_MUTED | Lifecycle | Channel was muted |
| CHANNEL_UNMUTED | Lifecycle | Channel was unmuted |
| CHANNEL_UPDATED | Lifecycle | Channel binding was modified (access/visibility) |
| DTMF | Voice | DTMF tone detected (keypad digit) |
| RECORDING_STARTED | Voice | Audio recording started for a session |
| RECORDING_STOPPED | Voice | Audio recording stopped, result available |
| TASK_CREATED | Side effect | A task was created |
| OBSERVATION | Side effect | An observation was recorded |

**EventStatus** enumeration:

| Value | Meaning |
|---|---|
| PENDING | Event created, not yet processed |
| DELIVERED | Event successfully stored and broadcast |
| READ | Event read by recipient (from read receipt) |
| FAILED | Delivery failed after all retries |
| BLOCKED | Event blocked by a sync hook |

**EventSource:**

```
EventSource
├── channel_id: string                      # Which channel produced this
├── channel_type: ChannelType               # Channel type enum
├── direction: ChannelDirection             # INBOUND or OUTBOUND
├── participant_id: string | null           # Which human, if applicable
├── external_id: string | null              # External system reference
├── provider: string | null                 # Provider/backend name for event attribution
├── raw_payload: map<string, any>           # Original provider payload — never lost
└── provider_message_id: string | null      # Provider's message identifier
```

Implementations MUST preserve `raw_payload` unmodified. This is the audit trail
and the source of truth for provider-specific data.

**EventSource.provider population:** Every channel MUST populate the `provider`
field when constructing an EventSource. The value SHOULD be the name of the
underlying provider or backend — for example, `"SIP"` for a SIP voice backend,
`"SIPRealtimeTransport"` for a SIP realtime transport, `"TwilioSMS"` for an SMS
provider. The channel SHOULD expose a `provider_name` property that returns the
appropriate name. System-generated events (`channel_id="system"`) MAY leave
`provider` as null.

### 5.3 Event Content

Event content is a **discriminated union** — each event carries exactly one content
type. Implementations MUST support all content types defined here.

**TextContent** — Plain text message:

```
TextContent
├── text: string                            # Message text
└── language: string | null                 # ISO 639-1 language code
```

**RichContent** — Formatted text with interactive elements:

```
RichContent
├── text: string                            # Primary text (may contain markdown/HTML)
├── plain_text: string | null               # Plain text fallback
├── buttons: list<Button>                   # Interactive buttons
├── cards: list<Card>                       # Structured card elements
└── quick_replies: list<QuickReply>         # Suggested quick responses
```

**MediaContent** — File, image, or document:

```
MediaContent
├── url: string                             # Media URL (or data: URI)
├── mime_type: string                       # MIME type (image/jpeg, application/pdf, etc.)
├── filename: string | null                 # Original filename
├── caption: string | null                  # Text caption
└── size_bytes: int | null                  # File size
```

**LocationContent** — Geographic coordinates:

```
LocationContent
├── latitude: float                         # Latitude
├── longitude: float                        # Longitude
├── label: string | null                    # Location name
└── address: string | null                  # Street address
```

**AudioContent** — Audio message or voice note:

```
AudioContent
├── url: string                             # Audio URL (or data: URI)
├── duration_seconds: float | null          # Duration
├── mime_type: string                       # Audio MIME type
├── size_bytes: int | null                  # File size
└── transcript: string | null               # STT transcript (if available)
```

**VideoContent** — Video message:

```
VideoContent
├── url: string                             # Video URL (or data: URI)
├── duration_seconds: float | null          # Duration
├── mime_type: string                       # Video MIME type
├── size_bytes: int | null                  # File size
└── thumbnail_url: string | null            # Preview image URL
```

**CompositeContent** — Multi-part message (e.g., text + image + audio):

```
CompositeContent
└── parts: list<EventContent>               # Ordered list of content parts
```

Implementations MUST enforce a maximum nesting depth of 5 levels for
CompositeContent.

**SystemContent** — Framework-generated message:

```
SystemContent
├── code: string                            # Machine-readable code
├── message: string                         # Human-readable description
└── data: map<string, any>                  # Structured payload
```

**TemplateContent** — Pre-approved template (WhatsApp, RCS):

```
TemplateContent
├── template_id: string                     # Template identifier
├── language: string                        # Template language
├── parameters: map<string, any>            # Variable substitutions
└── fallback: EventContent | null           # Content for channels without template support
```

**EditContent** — Edit of a previously sent message:

```
EditContent
├── target_event_id: string                # The event being edited
├── new_content: EventContent              # The replacement content
└── edit_source: string | null             # "sender" or "system" (e.g., auto-moderation)
```

**DeleteContent** — Deletion of a previously sent message:

```
DeleteContent
├── target_event_id: string                # The event being deleted
├── delete_type: DeleteType                # SENDER, SYSTEM, or ADMIN
└── reason: string | null                  # Optional reason
```

**DeleteType** enumeration: SENDER | SYSTEM | ADMIN

| Value | Description |
|---|---|
| SENDER | The original message author deleted their own message |
| SYSTEM | Automated deletion (e.g., auto-moderation, policy enforcement) |
| ADMIN | Administrative deletion by a room administrator or operator |

### 5.4 Channel Data (Typed, Per-Channel)

Each channel type MAY define a typed ChannelData structure to carry
channel-specific metadata on events. Common examples:

```
SMSChannelData
├── from_number: string
├── to_number: string
├── segments: int
└── encoding: string | null

EmailChannelData
├── from_address: string
├── to_addresses: list<string>
├── cc: list<string>
├── subject: string | null
├── thread_id: string | null
└── html_body: string | null

WhatsAppChannelData
├── wa_id: string
├── template_name: string | null
├── buttons: list<object> | null
├── context: object | null
└── is_group: bool

AIChannelData
├── model: string
├── agent_name: string | null
├── tokens_used: int | null
└── latency_ms: float | null
```

Implementations SHOULD define typed ChannelData for each supported channel type.
Unknown channel data MUST be preserved in a generic map structure.

### 5.5 Participant

```
Participant
├── id: string                              # Unique identifier
├── room_id: string                         # Owning room
├── channel_id: string                      # Primary channel used to join
├── display_name: string | null             # Human-readable name
├── role: ParticipantRole                   # Role in the room
├── status: ParticipantStatus               # Current status
├── identification: IdentificationStatus    # Identity resolution state
├── identity_id: string | null              # Resolved Identity reference
├── candidates: list<string> | null         # Candidate identity IDs (when ambiguous)
├── connected_via: list<string>             # Channel IDs this participant uses
├── external_id: string | null              # Integrator's external reference
├── resolved_at: datetime | null            # When identity was confirmed
├── resolved_by: string | null              # What resolved it (hook name, "auto", "manual")
├── joined_at: datetime                     # When participant entered the room
└── metadata: map<string, any>              # Integrator-defined data
```

**ParticipantRole** enumeration:

| Value | Description |
|---|---|
| OWNER | Room creator or primary responsible party |
| AGENT | Human agent (advisor, support representative) |
| MEMBER | Regular participant |
| OBSERVER | Read-only participant (supervisor, auditor) |
| BOT | Automated system participant |

**ParticipantStatus** enumeration:

| Value | Description |
|---|---|
| ACTIVE | Currently participating |
| INACTIVE | No recent activity |
| LEFT | Explicitly left the room |
| BANNED | Removed and blocked |

**IdentificationStatus** enumeration:

| Value | Description |
|---|---|
| IDENTIFIED | Identity confirmed — `identity_id` is set |
| PENDING | Awaiting resolution — may have `candidates` |
| AMBIGUOUS | Multiple candidates found — requires disambiguation |
| UNKNOWN | No matching identity — may create new |
| CHALLENGE_SENT | Verification challenge sent to participant |
| REJECTED | Identity challenge failed or was rejected |

**Renaming (normative):** a member's presentation can change while they are
present — their display name above all. Implementations SHOULD provide an
update operation (`rename_member`) that changes `display_name` in place,
emits `PARTICIPANT_UPDATED` and fires `ON_PARTICIPANT_UPDATED`, so an
interface reflecting the room learns of the change the same way it learned
of the join. `id` and `identity_id` are not presentation and MUST NOT be
changed through it: they are what attribution, correlation
(Section 12.10.2) and moderation stand on. A rename that changes nothing
is a no-op — no write, no event.

### 5.6 Identity

```
Identity
├── id: string                              # Unique identifier
├── organization_id: string | null          # Multi-tenant scope
├── display_name: string | null             # Human-readable name
├── channel_addresses: map<ChannelType, list<string>>
│       # Cross-channel addresses, e.g., {SMS: ["+15551234"], EMAIL: ["john@example.com"]}
├── external_id: string | null              # CRM or external system reference
└── metadata: map<string, any>              # Integrator-defined data
```

### 5.7 ChannelBinding

When a channel is attached to a Room, a ChannelBinding is created:

```
ChannelBinding
├── channel_id: string                      # Which channel
├── room_id: string                         # Which room
├── channel_type: ChannelType               # Channel type enum
├── category: ChannelCategory               # TRANSPORT or INTELLIGENCE
├── direction: ChannelDirection             # INBOUND, OUTBOUND, BIDIRECTIONAL
├── access: Access                          # Permission level
├── muted: bool                             # Temporarily silenced (suppress response events)
├── output_muted: bool                      # Output-only muting (suppress deliver(), keep on_event())
├── visibility: string                      # Write visibility rule
├── participant_id: string | null           # Bound to a specific participant
├── last_read_index: int | null             # Read horizon for unread tracking
├── attached_at: datetime                   # When attached
├── capabilities: ChannelCapabilities       # What this channel supports
├── rate_limit: RateLimit | null            # Per-channel rate limiting
├── retry_policy: RetryPolicy | null        # Per-channel retry configuration
└── metadata: map<string, any>              # Binding-specific data (recipient_id, persona, etc.)
```

### 5.8 ChannelCapabilities

Each channel declares what it supports:

```
ChannelCapabilities
├── media_types: list<ChannelMediaType>     # What content categories are supported
├── max_length: int | null                  # Maximum text length (null = unlimited)
│
│   # Text features:
├── supports_rich_text: bool
├── supports_buttons: bool
├── max_buttons: int | null
├── supports_cards: bool
├── supports_quick_replies: bool
├── supports_templates: bool
│
│   # Media features:
├── supports_media: bool
├── supported_media_types: list<string>     # MIME types
├── max_media_size_bytes: int | null
│
│   # Audio/Video features:
├── supports_audio: bool
├── supports_video: bool
│
│   # Delivery features:
├── supports_threading: bool
├── supports_typing: bool
├── supports_read_receipts: bool
├── supports_reactions: bool
├── supports_edit: bool
├── supports_delete: bool
├── delivery_mode: DeliveryMode
├── rate_limit: RateLimit | null
│
│   # Extensible:
└── custom: map<string, any>
```

**ChannelMediaType** enumeration:

| Value | Description |
|---|---|
| TEXT | Plain text messages |
| RICH | Formatted text with buttons, cards, quick replies |
| MEDIA | Images, documents, files |
| AUDIO | Audio messages, voice notes |
| VIDEO | Video messages |
| LOCATION | Geographic coordinates |
| TEMPLATE | Pre-approved message templates |

### 5.9 Three Levels of Channel Metadata

Channel-specific information lives at three levels. Implementations MUST maintain
all three and MUST NOT conflate them:

| Level | Where | Scope | Example |
|---|---|---|---|
| **Channel Instance** | Channel.info | Global, static | `{provider: "twilio", from_number: "+15551234"}` |
| **Channel Binding** | ChannelBinding.metadata | Per-room | `{persona: "formal", language: "fr"}` |
| **Event Source** | EventSource.channel_data | Per-event | `SMSChannelData{from: "+15559876", segments: 1}` |

### 5.10 Task

```
Task
├── id: string                              # Unique identifier
├── room_id: string                         # Originating room
├── type: string                            # Integrator-defined type
├── status: TaskStatus                      # Current state
├── title: string | null                    # Human-readable title
├── description: string | null              # Detailed description
├── data: map<string, any>                  # Structured payload
├── assigned_to: string | null              # Who is responsible
├── created_by: string | null               # Channel or hook that created it
├── created_at: datetime                    # When created
└── metadata: map<string, any>              # Integrator-defined data
```

**TaskStatus** enumeration: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED

### 5.11 Observation

```
Observation
├── id: string                              # Unique identifier
├── room_id: string                         # Originating room
├── type: string                            # Category (e.g., "sentiment", "compliance_violation")
├── data: map<string, any>                  # Structured payload
├── source_channel_id: string | null        # Which channel produced this
├── created_at: datetime                    # When created
└── metadata: map<string, any>              # Integrator-defined data
```

### 5.12 Inbound Message

The normalized representation of a message arriving from outside the framework:

```
InboundMessage
├── channel_id: string                      # Which registered channel
├── channel_type: ChannelType               # Channel type
├── sender_id: string                       # Sender identifier (phone number, email, user ID)
├── content: EventContent                   # Parsed content
├── raw_payload: map<string, any>           # Original provider payload
├── provider_message_id: string | null      # Provider's message ID
├── timestamp: datetime | null              # When originally sent
├── idempotency_key: string | null          # Duplicate prevention
├── room_id: string | null                  # Pre-determined room (if known)
├── session: VoiceSession | null            # Voice session to connect after processing
└── metadata: map<string, any>              # Extra data
```

**Unified voice inbound:** When the `session` field is set, `process_inbound()`
connects the voice session to the channel after successful hook processing. This
allows voice calls and text messages to flow through the same entry point, same
hooks, and same pipeline. See Section 10.1 for the additional step.

A convenience helper `parse_voice_session(session, channel_id)` SHOULD be
provided to convert a `VoiceSession` into an `InboundMessage` with a
`SystemContent(code="session_started")` body and the session pre-attached:

```
parse_voice_session(session: VoiceSession, channel_id: string) → InboundMessage
    # Returns InboundMessage with:
    #   channel_id = channel_id
    #   channel_type = VOICE or REALTIME_VOICE
    #   sender_id = session.participant_id
    #   content = SystemContent(code="session_started", data={caller, callee, ...})
    #   session = session
    #   room_id = session.room_id (if set)
    #   metadata = session.metadata
```

### 5.13 Delivery Result

```
DeliveryResult
├── channel_id: string                      # Target channel
├── status: string                          # "sent", "queued", "failed"
├── provider_message_id: string | null      # Provider's message ID
├── error: DeliveryError | null             # Error details if failed
└── retry_after: datetime | null            # When to retry (if rate limited)

DeliveryError
├── code: string                            # Machine-readable error code
├── message: string                         # Human-readable description
└── retryable: bool                         # Whether a retry may succeed
```

### 5.14 Protocol Trace

An immutable record of a transport-level protocol exchange, used for
observability and debugging. Channels that interact with signaling protocols
(SIP, RTP, SMTP, etc.) SHOULD emit traces for significant protocol events.

```
ProtocolTrace (frozen)
├── channel_id: string                      # Which channel emitted this trace
├── direction: string                       # "inbound" or "outbound"
├── protocol: string                        # Protocol name ("sip", "rtp", "smtp", etc.)
├── summary: string                         # Human-readable summary (e.g., "INVITE from +1555...")
├── raw: bytes | string | null              # Full serialized protocol message (e.g., raw SIP request)
├── metadata: map<string, any>              # Protocol-specific data (call_id, codec, etc.)
├── session_id: string | null               # Voice session identifier (if applicable)
├── room_id: string | null                  # Room identifier (if known at emission time)
└── timestamp: datetime                     # When the trace was emitted (UTC, auto-populated)
```

**Immutability:** ProtocolTrace MUST be frozen (immutable) after construction.

**Raw payloads:** When available, the `raw` field SHOULD contain the complete
serialized protocol message. For SIP, this is the full SIP request/response as
returned by the SIP library's `serialize()` method. For protocols where the raw
payload is not available (e.g., outbound requests where the library does not
expose the serialized form), `raw` MAY be null.

**Trace emission and routing:** See Section 15.6 for the trace emission
infrastructure, including channel-level APIs, framework hook wiring, and
pre-room buffering.

---

## 6. Channel System

### 6.1 Channel Interface

All channels MUST implement the following interface:

```
Channel (interface)
├── id: string                              # Unique channel identifier
├── channel_type: ChannelType               # SMS, EMAIL, WHATSAPP, AI, VOICE, etc.
├── category: ChannelCategory               # TRANSPORT or INTELLIGENCE
├── direction: ChannelDirection             # INBOUND, OUTBOUND, BIDIRECTIONAL
│
├── handle_inbound(message: InboundMessage, context: RoomContext) → RoomEvent
│       # Convert external payload to a RoomEvent
│
├── deliver(event: RoomEvent, binding: ChannelBinding, context: RoomContext) → ChannelOutput
│       # Push event to external recipient
│
├── on_event(event: RoomEvent, binding: ChannelBinding, context: RoomContext) → ChannelOutput
│       # React to a room event (default: no-op)
│
├── supports_streaming_delivery: bool (default false)
│       # Whether this channel accepts streaming text delivery
│
├── deliver_stream(text_stream, event, binding, context) → ChannelOutput
│       # Deliver streaming text to this channel
│       # Default: accumulate text, deliver as complete event via deliver()
│
├── connect_session(session: VoiceSession, room_id: string, binding: ChannelBinding) → void
│       # Connect a voice session to this channel (voice/realtime channels only)
│       # Default: no-op for non-voice channels
│
├── provider_name: string | null
│       # Provider or backend name for event attribution (see EventSource.provider)
│       # Default: provider.name if provider has a name attribute, else null
│
├── capabilities() → ChannelCapabilities
│       # Declare supported features
│
├── info() → map<string, any>
│       # Channel instance information
│
└── close() → void
        # Release resources
```

**ChannelOutput:**

```
ChannelOutput
├── events: list<RoomEvent>                 # Response events (subject to permissions)
├── response_stream: async_iterator<str>    # Streaming response (mutually exclusive with events)
│       # When set, framework pipes stream to streaming-capable channels,
│       # accumulates full text, stores event, and re-broadcasts to others.
├── tasks: list<Task>                       # Side effects (always allowed)
├── observations: list<Observation>         # Side effects (always allowed)
└── metadata_updates: map<string, any>      # Room metadata to update
```

### 6.2 ChannelType Enumeration

| Value | Category | Description |
|---|---|---|
| SMS | TRANSPORT | Short Message Service |
| MMS | TRANSPORT | Multimedia Message Service |
| RCS | TRANSPORT | Rich Communication Services |
| EMAIL | TRANSPORT | Electronic mail |
| WHATSAPP | TRANSPORT | WhatsApp Business Cloud API |
| WHATSAPP_PERSONAL | TRANSPORT | WhatsApp Web multidevice protocol |
| WEBSOCKET | TRANSPORT | WebSocket real-time connection |
| MESSENGER | TRANSPORT | Facebook Messenger |
| TEAMS | TRANSPORT | Microsoft Teams |
| WEBHOOK | TRANSPORT | Generic HTTP webhook |
| VOICE | TRANSPORT | Voice channel (STT/TTS pipeline) |
| REALTIME_VOICE | TRANSPORT | Speech-to-speech API (e.g., OpenAI Realtime, Gemini Live) |
| AUDIO_VIDEO | TRANSPORT | Combined voice + video channel (STT/TTS pipeline + video) |
| REALTIME_AUDIO_VIDEO | TRANSPORT | Combined speech-to-speech + video channel |
| VIDEO | TRANSPORT | Video-only channel |
| CONFERENCE | TRANSPORT | Multi-party SFU conference (audio + video + screen share) |
| TELEGRAM | TRANSPORT | Telegram Bot API |
| CLI | TRANSPORT | Command-line interface (development/testing) |
| PUSH | TRANSPORT | Push notification channel |
| AI | INTELLIGENCE | AI/LLM agent |
| SYSTEM | — | Framework-generated events |

Implementations MAY define additional channel types. Custom channel types SHOULD
use the format `custom:namespace` (e.g., `custom:slack`).

### 6.3 Transport Channels

Transport channels carry messages between the framework and external systems or
humans. They MUST implement `deliver()`. Common transport channels and their
reference capabilities:

| Channel | Media Types | Max Length | Key Features |
|---|---|---|---|
| SMS | TEXT, MEDIA | 1,600 | Read receipts |
| Email | TEXT, RICH, MEDIA | unlimited | Threading, rich HTML |
| WhatsApp | TEXT, RICH, MEDIA, LOCATION, TEMPLATE | 4,096 | Reactions, templates, buttons, edit, delete |
| WhatsApp Personal | TEXT, RICH, MEDIA, AUDIO, VIDEO, LOCATION | 4,096 | Typing, reactions, audio/video, edit, delete |
| Messenger | TEXT, RICH, MEDIA, TEMPLATE | 2,000 | Buttons, quick replies, delete |
| Teams | TEXT, RICH | 28,000 | Threading, reactions, rich text, edit, delete |
| RCS | TEXT, RICH, MEDIA | 8,000 | Buttons, cards, SMS fallback |
| WebSocket | TEXT, RICH, MEDIA, AUDIO, VIDEO, LOCATION | unlimited | All features, real-time, edit, delete |
| Voice | AUDIO | — | Streaming audio, STT/TTS |
| Realtime Voice | AUDIO | — | Speech-to-speech, tool calling |
| Telegram | TEXT, RICH, MEDIA, LOCATION | 4,096 | Buttons, inline keyboards, edit, delete |
| Audio/Video | AUDIO, VIDEO | — | Combined voice + video, STT/TTS + vision |
| Realtime Audio/Video | AUDIO, VIDEO | — | Speech-to-speech + video, tool calling |
| Video | VIDEO | — | Video-only, vision provider integration |
| Conference | AUDIO, VIDEO | — | Multi-party SFU, per-track STT, AI bot participant |
| Webhook | TEXT, RICH | unlimited | Generic HTTP POST |

### 6.4 Intelligence Channels

Intelligence channels process events and produce responses or insights. They
MUST implement `on_event()`. They do NOT deliver to external systems — the
framework routes their output through the normal event pipeline.

**AI Channel:**

An AI channel wraps an AI Provider (see Section 6.7). When `on_event()` is called:

1. Build conversation history from room timeline.
2. Determine target transport channel's capabilities and media types.
3. Construct AI context with capabilities, system instructions, and room metadata.
4. Call the AI provider's `generate()` method.
5. Return ChannelOutput with response event(s), tasks, and observations.

The AI channel MUST skip events originating from itself to prevent infinite loops.

**Capability-aware generation:** The framework MUST provide the target transport
channel's capabilities to the AI at generation time, NOT post-process the output.
This allows the AI to tailor its response (e.g., short text for SMS, rich for Email).

**ACP Agent Channel:**

An ACP agent channel connects a Room to an external
[Agent Client Protocol](https://agentclientprotocol.com/) agent. In this
integration RoomKit is the ACP **client** and the coding agent is the ACP
**server**. Exposing a RoomKit-built agent as an ACP server is a separate
integration surface and is outside this channel's contract.

An ACP agent channel:

1. MUST use `ChannelType.AI`, category `INTELLIGENCE`, and direction
   `BIDIRECTIONAL`;
2. MUST initialize one ACP connection per channel instance and create a distinct
   ACP session for each Room;
3. MUST serialize prompts within an ACP session while allowing different Room
   sessions to operate concurrently;
4. MUST convert Room message content into ACP prompt content and map ACP agent
   message chunks back to the normal RoomKit streaming output path;
5. MUST map ACP tool-call lifecycle updates to RoomKit tool-call stream markers
   and MUST map ACP plan updates to RoomKit realtime events;
6. MUST skip events originating from itself and persisted tool-call activity
   events, preventing duplicate prompts and agent loops;
7. MUST support cancellation of an active Room turn and MUST release ACP
   sessions and transport resources when the channel closes; and
8. MUST NOT bypass the standard RoomKit persistence, visibility, chain-depth,
   or re-broadcast behavior for generated text and tool activity.

The stable ACP protocol version MUST be the default. Experimental protocol
versions MAY be supported only behind explicit opt-in and MUST NOT silently
replace the stable default. The channel MUST negotiate the protocol version
during initialization and MUST fail clearly when no compatible version exists.

The reference transport is ACP over stdio. A stdio implementation MUST launch
the configured command as an argument vector without a shell. Alternate ACP
transports MAY be implemented when standardized, but MUST preserve the lifecycle
and permission requirements above.

ACP sessions are process-local by default. An implementation MAY add persistent
session resumption, but MUST scope resumed session identifiers to the associated
Room and agent endpoint.

ACP agents can request permission to execute tools and can request client-side
filesystem or terminal operations. An ACP agent channel:

- MUST advertise filesystem and terminal capabilities as unavailable unless the
  integrator explicitly supplies conforming implementations;
- MUST deny or cancel permission requests when no external tool handler is
  configured;
- MUST pass tool name, input, call identifier, ACP session identifier, and Room
  identifier to the configured external tool handler;
- MUST select only a permission option offered by the ACP agent; and
- SHOULD expose tool and plan progress through the realtime backend without
  persisting transient progress updates.

### 6.5 Source Providers

Source providers maintain **persistent connections** that push inbound events to
the framework. This is distinct from webhook-based channels where the framework
receives HTTP callbacks.

```
SourceProvider (interface)
├── id: string                              # Source identifier
├── status: SourceStatus                    # STOPPED, CONNECTING, CONNECTED, RECONNECTING, ERROR
│
├── start(emit: function(InboundMessage)) → void
│       # Connect and begin listening. Call `emit` for each inbound message.
│
├── stop() → void
│       # Disconnect and release resources
│
└── healthcheck() → SourceHealth
        # Report connection health
```

**SourceStatus** enumeration: STOPPED, CONNECTING, CONNECTED, RECONNECTING, ERROR

Examples of source providers:

| Source | Description |
|---|---|
| WhatsApp Personal (neonize) | Persistent WhatsApp Web multidevice connection |
| WebSocket | Client connection to an external WebSocket server |
| SSE | Server-Sent Events stream from an HTTP endpoint |

Sources are attached to the framework and MUST call the `emit` callback for
each inbound message. The framework routes emitted messages through the standard
inbound pipeline (Section 10.1).

### 6.6 Content Transcoding

When an event is broadcast to channels with different capabilities, the framework
MUST transcode content to match each target channel's supported media types.

**Default transcoding rules:**

| Source Content | Target Supports | Transcoded To |
|---|---|---|
| RichContent | TEXT only | TextContent (extract plain_text or strip formatting) |
| MediaContent | TEXT only | TextContent (use caption or filename) |
| AudioContent | TEXT only | TextContent (use transcript or "[Voice message]") |
| VideoContent | TEXT only | TextContent (use caption or "[Video]") |
| LocationContent | TEXT only | TextContent ("[Location] lat, lon - label") |
| CompositeContent | varies | Filter parts to target's supported types |
| TemplateContent | no templates | Use fallback content, or transcode to RichContent/TextContent |
| EditContent | no edit support | TextContent ("Correction: {new text}") |
| DeleteContent | no delete support | TextContent ("[Message deleted]") or SystemContent |

When the target channel supports edits or deletes natively (i.e.,
`capabilities.supports_edit` or `capabilities.supports_delete` is true), the
framework MUST deliver the EDIT or DELETE event without transcoding. When the
target channel does NOT support the operation, the framework MUST transcode to
the fallback representation shown above.

**Max length enforcement:** After transcoding, if the target channel declares a
`max_length`, the framework MUST truncate TextContent to that limit.

Implementations SHOULD allow integrators to provide a custom transcoding strategy.

### 6.7 Provider Abstraction

Channel type and Provider are separate concepts. This applies to ALL channels,
including AI.

**AI Provider interface:**

```
AIProvider (interface)
├── name: string                            # Provider name (e.g., "anthropic", "openai")
├── model_name: string                      # Model identifier (e.g., "claude-sonnet-4-5")
├── supports_streaming: bool (default false) # Whether provider supports streaming generation
│
├── generate(messages: list<AIMessage>, context: AIContext) → AIResponse
│       # Generate a response given conversation history and context
│
└── generate_stream(context: AIContext) → async_iterator<string>
        # Yield text deltas as they arrive (requires supports_streaming = true)
        # Used by VoiceChannel for streaming AI → TTS (Section 12.2)

AIMessage
├── role: string                            # "user", "assistant", "system"
└── content: list<AIContentPart>            # Text parts, image parts, etc.

AIContext
├── room: RoomContext                       # Current room state
├── target_capabilities: ChannelCapabilities | null
├── target_media_types: list<ChannelMediaType>
├── system_instructions: string | null
└── metadata: map<string, any>

AIResponse
├── text: string                            # Generated text
├── tasks: list<Task>                       # Tasks to create
├── observations: list<Observation>         # Observations to record
└── provider_metadata: map<string, any>     # Provider-specific data (tokens, latency)
```

**SMS Provider interface:**

```
SMSProvider (interface)
├── send(event: RoomEvent, to: string, from: string) → ProviderResult
├── parse_webhook(payload: map) → InboundMessage
└── verify_signature(payload, signature, timestamp) → bool
```

**Email Provider interface:**

```
EmailProvider (interface)
├── send(event: RoomEvent, to: string, from: string, subject: string | null) → ProviderResult
└── parse_inbound(payload: map) → InboundMessage
```

Implementations SHOULD define similar provider interfaces for WhatsApp, Messenger,
Teams, RCS, HTTP, Voice (STT, TTS), and any custom channel types.

---

## 7. Permission Model

The permission model consists of three orthogonal primitives. The framework
provides the primitives; the integrator decides when and how to use them.

### 7.1 Access

Controls whether a channel can read events, write events, or both within a room.

| Value | Can Read | Can Write | Description |
|---|---|---|---|
| READ_WRITE | Yes | Yes | Full participation |
| READ_ONLY | Yes | No | Observe only (events via `on_event()`) |
| WRITE_ONLY | No | Yes | Blind sender (unusual, but valid) |
| NONE | No | No | Fully disconnected (binding exists but inactive) |

### 7.2 Muting

A boolean flag on the binding. When `muted = true`:

- The channel STILL receives events via `on_event()` (reading is preserved).
- The channel's response events are SUPPRESSED (writing is blocked).
- Side effects (tasks, observations) are STILL collected.

Muting is temporary. The integrator calls `mute()` and `unmute()` as needed.

### 7.3 Visibility

Controls which channels see events produced by the source channel. Set on the
binding as a string value:

| Value | Meaning |
|---|---|
| `"all"` | All channels in the room see the event |
| `"none"` | No channels see the event (stored in timeline only) |
| `"transport"` | Only transport channels see the event |
| `"intelligence"` | Only intelligence channels see the event |
| `"channel_a,channel_b"` | Comma-separated list of specific channel IDs |
| `"channel_a"` | Single channel ID |

"See" is not "be delivered to". `"none"` reads *stored in timeline only*, and it
means it: an event a channel was not allowed to see at delivery MUST NOT reach
that channel later through history the framework rebuilds for it either. Rule 8
in §7.5 states that half.

### 7.4 Named Patterns

These are vocabulary for common configurations, NOT framework concepts. The
framework only knows access, muted, and visibility.

| Pattern | Configuration | Use Case |
|---|---|---|
| **Direct** | `access=READ_WRITE, visibility="all"` | AI speaks to everyone in the room |
| **Assistant** | `access=READ_WRITE, visibility="ws_advisor"` | AI whispers only to the advisor |
| **Observer** | `access=READ_ONLY` | Sentiment analyzer watches, produces side effects only |
| **Muted** | `muted=true` | AI temporarily silenced but still tracking |
| **Internal** | `access=READ_WRITE, visibility="none"` | Writes stored in timeline but never broadcast |

### 7.5 Permission Rules

Implementations MUST enforce these rules:

1. **Reading:** A channel receives events via `on_event()` if and only if its
   binding has `access` ∈ {READ_WRITE, READ_ONLY} AND the event's visibility
   includes this channel.
2. **Writing:** A channel's response events are broadcast if and only if its
   binding has `access` ∈ {READ_WRITE, WRITE_ONLY} AND `muted = false`.
   Likewise, an inbound or directly-injected event whose source binding cannot
   write (`access` ∉ {READ_WRITE, WRITE_ONLY} OR `muted = true`) MUST be stored
   with status `BLOCKED` (`blocked_by` = `source_read_only` or `source_muted`)
   rather than `DELIVERED`, and MUST NOT be broadcast.
3. **Side effects:** Tasks and observations are ALWAYS collected regardless of
   access or mute status — including for events blocked by rule 2.
4. **Visibility filtering:** When broadcasting an event, the framework MUST
   check the source binding's visibility and deliver only to channels included
   in the visibility rule.
5. **Self-skip:** A channel MUST NOT receive its own events via `on_event()`.
6. **A binding is never widened implicitly.** Wherever the framework creates a
   binding from an existing one — sharing a channel into a delegated room
   (§19), copying a template, re-attaching a channel it detached earlier — the
   new binding MUST NOT grant more than the one it derives from. Carrying over
   a binding's category and metadata while letting `access`, `visibility` and
   `muted` fall back to defaults silently promotes a read-only observer into a
   full participant, in a room the integrator never configured. Widening a
   binding is an explicit act: it MUST come from an integrator call that says
   so, never from a default filling a gap.
7. **Attaching a channel is a decision, not a repair.** An implementation MAY
   attach a channel automatically when a message arrives for a room the
   channel is not yet bound to. It MUST NOT do so when the channel was
   previously detached from that room, and MUST NOT use such an attach to
   replace a binding that already exists — detaching is how an integrator
   revokes a channel's access, and an automatic re-attach at default
   permissions undoes exactly that.
8. **Reconstructed context obeys the same rule as delivery.** Rule 1 governs
   `on_event()`; this one governs everything the implementation rebuilds from
   the timeline *for* a channel — the history handed to a memory provider, the
   turns assembled into a model prompt, any per-channel replay of what was said.
   A channel MUST NOT obtain there an event visibility withheld from it at
   delivery. Withholding an event at broadcast and returning it one turn later
   as context is not a partial enforcement of visibility; it is none.

   The filter is per reader, so it MUST be applied where the reader is known —
   a single `RoomContext` shared by every channel of a broadcast cannot be
   filtered once for all of them. An implementation MUST apply it before the
   history reaches a component that can transform it (a summarizing or
   compacting memory provider re-emits hidden content as a summary otherwise),
   and SHOULD expose the per-reader view so host code can ask for it.

   Three points the rule does NOT cover:

   - **A channel always sees its own events.** Rule 5 skips a channel's own
     event at delivery because it produced it, not because it may not know it.
     A rule that dropped an agent's own turns from its own prompt would erase
     the assistant pattern of §7.4 (`visibility="ws_advisor"`) from the inside.
   - **Host code reads the timeline whole.** Hooks, scorers and framework
     machinery run in the integrator's process and hold the store already;
     filtering their `recent_events` would forbid nothing and would break
     legitimate readers. Visibility is a rule between the room and its
     channels.
   - **Visibility is a live property of the binding.** An implementation that
     resolves a source's visibility from its binding at read time MUST accept
     that widening a binding widens its past too, and MUST document it. One
     that stamps the effective visibility onto the event at commit gets a
     replay-stable answer instead. Either is conformant; the choice MUST be
     stated. When the source binding no longer exists, the event's own
     `visibility` field is the whole answer — an implementation MUST NOT treat
     an unresolvable source as a reason to hide ordinary history, which would
     empty a room's context the moment a transport detaches.

---

## 8. Event System

### 8.1 Room Events

Room events are stored in the room's timeline. They have a sequential `index`
that is monotonically increasing within each room.

**Sequential indexing requirements:**

- The `index` MUST start at 0 for the first event in a room.
- Each subsequent event MUST have `index = previous_index + 1`.
- The `index` MUST be assigned atomically per room. A room-level lock (§13.5)
  serializes assignment within a single process; it is **NOT** sufficient when a
  persistent store is shared across processes (e.g. a load-balanced deployment),
  because per-process locks do not coordinate. Such a store MUST make index
  assignment authoritative at the storage layer: a `UNIQUE(room_id, index)`
  constraint, with the index computed and the event inserted in a **single
  storage transaction**, so concurrent writers serialize on the store rather
  than on an in-process lock.
- A duplicate `(room_id, index)` MUST be rejected by the store (the constraint
  violation surfaced to the caller), never silently persisted.
- The `index` enables pagination, read horizon tracking, and gap detection.

### 8.2 Framework Events

Framework events are global lifecycle notifications published to subscribers.
They are NOT stored in any room timeline.

| Event | When | Data |
|---|---|---|
| room_created | New room created | room_id, organization_id |
| room_paused | Room transitioned to PAUSED | room_id |
| room_closed | Room transitioned to CLOSED | room_id |
| room_archived | Room transitioned to ARCHIVED | room_id |
| channel_registered | Channel registered with framework | channel_id, channel_type |
| channel_unregistered | Channel unregistered | channel_id |
| source_connected | Source provider connected | source_id |
| source_disconnected | Source provider disconnected | source_id |
| event_processed | Inbound event fully processed | room_id, event_id |
| event_blocked | Event blocked by hook | room_id, event_id, hook_name |
| delivery_succeeded | Event delivered to channel | room_id, event_id, channel_id |
| delivery_failed | Delivery failed after retries | room_id, event_id, channel_id, error |
| identity_resolved | Identity was resolved | participant_id, identity_id |
| identity_timeout | Identity resolution timed out | room_id, address |
| chain_depth_exceeded | Event blocked by chain depth limit | room_id, channel_id, depth |
| hook_error | Hook raised an exception | hook_name, trigger, error |
| hook_timeout | Hook exceeded its timeout | hook_name, trigger, timeout_ms |
| circuit_breaker_opened | Channel circuit breaker tripped | channel_id, failure_count |
| circuit_breaker_closed | Channel circuit breaker recovered | channel_id |
| voice_session_started | Voice session transitioned to ACTIVE | session_id, room_id, channel_id |
| voice_session_ended | Voice session transitioned to ENDED | session_id, room_id, duration_ms |
| recording_started | Audio recording started | session_id, room_id, recording_id |
| recording_stopped | Audio recording stopped | session_id, room_id, recording_id, duration_s |
| stt_error | STT transcription failed | session_id, provider, error |
| tts_error | TTS synthesis failed | session_id, provider, error |
| voice_session_ready | Voice session audio path is live and ready | session_id, room_id, channel_id |
| conference_started | Bot connection to the conference is live | room_id, channel_id, bot_session_id |
| conference_ended | Bot left the conference | room_id, channel_id, bot_session_id, duration_ms |
| conference_participant_joined | Participant joined the media session | room_id, participant_id |
| conference_participant_left | Participant left the media session | room_id, participant_id |

Implementations MUST emit these events. Integrators subscribe to framework
events for monitoring and integration purposes.

### 8.3 Event Chain Depth

When a channel produces a response event (e.g., AI responds to a message),
that response may trigger further responses from other channels. This creates
an event chain.

**Chain depth tracking:**

- Events from external inbound (human messages, webhooks) have `chain_depth = 0`.
- When a channel produces a response event during broadcast, the response's
  `chain_depth = source_event.chain_depth + 1`.
- When `chain_depth >= max_chain_depth`, the response MUST be blocked with
  `status = BLOCKED` and `blocked_by = "event_chain_depth_limit"`.

**Requirements:**

- Implementations MUST support a configurable `max_chain_depth` (default: 5).
- Blocked events MUST still be stored in the timeline (for audit).
- Side effects from the blocked channel MUST still be collected.
- A framework event `chain_depth_exceeded` MUST be emitted.

### 8.4 Realtime / Ephemeral Events

Some events (typing indicators, presence changes) are ephemeral — they are
published in real-time but not stored in the timeline.

```
RealtimeBackend (interface)
├── publish(room_id: string, event_type: string, data: map) → void
├── subscribe(room_id: string, callback: function) → subscription
└── unsubscribe(subscription) → void
```

Implementations SHOULD provide at least an in-memory realtime backend for
single-process deployments.

---

## 9. Hook System

Hooks are the primary extensibility mechanism. They allow integrators to
intercept, block, modify, and react to events in the pipeline.

### 9.1 Hook Registration

```
HookRegistration
├── trigger: HookTrigger                    # When this hook fires
├── execution: HookExecution                # SYNC or ASYNC
├── handler: function                       # The hook function
├── priority: int = 0                       # Execution order (lower = first)
├── name: string                            # Human-readable identifier
├── timeout: float = 30.0                   # Maximum execution time (seconds)
├── channel_types: set<ChannelType> | null  # Filter: only fire for these channel types
├── channel_ids: set<string> | null         # Filter: only fire for these channel IDs
└── directions: set<ChannelDirection> | null # Filter: only fire for these directions
```

Hooks MAY be registered globally (apply to all rooms) or per-room.

### 9.2 Hook Triggers

**HookTrigger** enumeration. The **Status** column distinguishes triggers the
reference implementation emits today (**Implemented** — 72 as of this revision)
from those specified for a forthcoming capability but not yet emitted
(**Planned**), and from a trigger kept for historical reference whose behaviour
has moved elsewhere (**Superseded**). Conformance targets the Implemented set;
Planned rows are normative design intent for the named capability.

| Trigger | Execution | Status | When It Fires |
|---|---|---|---|
| BEFORE_BROADCAST | SYNC | Implemented | Before event reaches channels — can block/modify |
| AFTER_BROADCAST | ASYNC | Implemented | After all channels have processed the event |
| ON_EVENT_UPDATED | ASYNC | Implemented | A persisted event's stored state was mutated (inbound EDIT, §10.3, or direct `update_event()`) |
| ON_EVENT_DELETED | ASYNC | Implemented | A persisted event was deleted (inbound soft DELETE, §10.3, or direct hard `delete_event()`) |
| ON_CHANNEL_ATTACHED | ASYNC | Implemented | Channel attached to a room |
| ON_CHANNEL_DETACHED | ASYNC | Implemented | Channel detached from a room |
| ON_CHANNEL_MUTED | ASYNC | Implemented | Channel muted in a room |
| ON_CHANNEL_UNMUTED | ASYNC | Implemented | Channel unmuted in a room |
| ON_ROOM_CREATED | ASYNC | Implemented | New room created |
| ON_ROOM_PAUSED | ASYNC | Implemented | Room transitioned to PAUSED |
| ON_ROOM_CLOSED | ASYNC | Implemented | Room transitioned to CLOSED |
| ON_IDENTITY_AMBIGUOUS | SYNC | Implemented | Multiple identity candidates found |
| ON_IDENTITY_UNKNOWN | SYNC | Implemented | No identity match found |
| ON_PARTICIPANT_IDENTIFIED | ASYNC | Implemented | Participant identity resolved |
| ON_PARTICIPANT_JOINED | ASYNC | Implemented | Explicit member join via `add_member` |
| ON_PARTICIPANT_LEFT | ASYNC | Implemented | Explicit member leave via `remove_member` |
| ON_PARTICIPANT_UPDATED | ASYNC | Implemented | Member presentation changed via `rename_member` |
| ON_TASK_CREATED | ASYNC | Implemented | A task was created |
| ON_DELIVERY_STATUS | ASYNC | Implemented | Delivery status webhook from provider |
| ON_ERROR | ASYNC | Implemented | An error occurred in the pipeline |
| ON_SPEECH_START | ASYNC | Implemented | Audio pipeline detected speech start (voice; per conference lane) |
| ON_SPEECH_END | ASYNC | Implemented | Audio pipeline detected speech end (voice; per conference lane) |
| ON_TRANSCRIPTION | SYNC | Implemented | After STT transcription (voice) — can modify |
| BEFORE_TTS | SYNC | Implemented | Before TTS synthesis (voice) — can modify text/voice |
| AFTER_TTS | ASYNC | Implemented | After TTS synthesis (voice) |
| ON_BARGE_IN | ASYNC | Implemented | User interrupted TTS playback (voice) |
| ON_TTS_CANCELLED | ASYNC | Implemented | TTS was cancelled (voice) |
| ON_PARTIAL_TRANSCRIPTION | ASYNC | Implemented | Streaming partial STT result (voice) |
| ON_VAD_SILENCE | ASYNC | Implemented | Audio pipeline detected silence (voice) |
| ON_VAD_AUDIO_LEVEL | ASYNC | Implemented | Audio pipeline audio level update (voice) |
| ON_INPUT_AUDIO_LEVEL | ASYNC | Implemented | Per-frame inbound audio level, throttled to ~10/sec (voice) |
| ON_OUTPUT_AUDIO_LEVEL | ASYNC | Implemented | Per-frame outbound audio level, throttled to ~10/sec (voice) |
| ON_SPEAKER_CHANGE | ASYNC | Implemented | Audio pipeline detected speaker change (diarization) |
| ON_DTMF | ASYNC | Implemented | Audio pipeline detected a DTMF tone |
| ON_TURN_COMPLETE | ASYNC | Implemented | Turn detector determined user turn is complete |
| ON_TURN_INCOMPLETE | ASYNC | Implemented | Turn detector determined user is still speaking (for logging) |
| ON_BACKCHANNEL | ASYNC | Implemented | Backchannel detector classified speech as backchannel |
| ON_SESSION_STARTED | ASYNC | Implemented | Session started on any channel type (voice: audio path live; text: room auto-created) |
| ON_RECORDING_STARTED | ASYNC | Implemented | Audio recording started for a voice session, or for a conference track (Section 12.10.8) |
| ON_RECORDING_STOPPED | ASYNC | Implemented | Audio recording stopped, result available |
| ON_REALTIME_TOOL_CALL | SYNC | Superseded | Speech-to-speech tool call — superseded by `ON_TOOL_CALL` (unified across AI and realtime channels) |
| ON_REALTIME_TEXT_INJECTED | ASYNC | Implemented | Text injected into realtime session |
| ON_PROTOCOL_TRACE | ASYNC | Implemented | Transport-level protocol trace emitted (SIP, RTP, etc.) |
| BEFORE_BRIDGE_AUDIO | SYNC | Implemented | Before an audio frame is forwarded via bridge — can block/modify (voice) |
| | | | |
| **Delivery:** | | | |
| BEFORE_DELIVER | SYNC | Implemented | Before proactive delivery strategy executes — can block/modify |
| AFTER_DELIVER | ASYNC | Implemented | After proactive delivery completes |
| | | | |
| **AI Generation:** | | | |
| BEFORE_AI_CONTEXT_BUILD | SYNC | Planned | Before AI context is built (pre-memory, pre-tool-resolution) — can block cheaply |
| BEFORE_AI_GENERATION | SYNC | Implemented | Before AI provider generate() — can modify context |
| ON_AI_THINKING | ASYNC | Implemented | AI model began extended thinking/reasoning |
| ON_AI_RESPONSE | ASYNC | Implemented | AI generation completed (observability) |
| BEFORE_TOOL_USE | SYNC | Implemented | Before a tool executes — can block or override the call |
| ON_TOOL_CALL | ASYNC | Implemented | A tool was invoked during generation (unified across AI and realtime channels) |
| ON_USER_INPUT_REQUIRED | SYNC | Implemented | Human-in-the-loop: a tool paused, waiting for user input |
| | | | |
| **Orchestration:** | | | |
| ON_PHASE_TRANSITION | ASYNC | Implemented | Conversation phase changed (e.g., triage → specialist) |
| ON_HANDOFF | ASYNC | Implemented | Agent handoff accepted and executed |
| ON_HANDOFF_REJECTED | ASYNC | Implemented | Agent handoff was rejected |
| ON_STATUS_POSTED | ASYNC | Implemented | Status posted to the inter-agent StatusBus |
| | | | |
| **Delegation:** | | | |
| ON_TASK_DELEGATED | ASYNC | Implemented | Background task delegated to a child room |
| ON_TASK_COMPLETED | ASYNC | Implemented | Delegated task completed with result |
| | | | |
| **Video:** | | | |
| BEFORE_BRIDGE_VIDEO | SYNC | Implemented | Before video frame is forwarded via bridge — can block/modify |
| ON_VIDEO_SESSION_STARTED | ASYNC | Implemented | Video session became active |
| ON_VIDEO_SESSION_ENDED | ASYNC | Implemented | Video session ended |
| ON_VIDEO_TRACK_ADDED | ASYNC | Implemented | Video track added to session |
| ON_VIDEO_TRACK_REMOVED | ASYNC | Implemented | Video track removed from session |
| ON_VISION_RESULT | ASYNC | Implemented | VisionProvider returned analysis result |
| ON_SCREEN_SHARE_STARTED | ASYNC | Implemented | Screen sharing started |
| ON_SCREEN_SHARE_STOPPED | ASYNC | Implemented | Screen sharing stopped |
| ON_VIDEO_DETECTION | ASYNC | Implemented | Video detection event (object, face, etc.) |
| | | | |
| **Conference:** (SFU) | | | |
| ON_CONFERENCE_PARTICIPANT_JOINED | ASYNC | Implemented | Participant joined the conference media session |
| ON_CONFERENCE_PARTICIPANT_LEFT | ASYNC | Implemented | Participant left the conference media session |
| ON_CONFERENCE_TRACK_PUBLISHED | ASYNC | Implemented | Conference participant published a track (audio, video, screen share) |
| ON_CONFERENCE_TRACK_UNPUBLISHED | ASYNC | Implemented | Conference track unpublished |
| ON_CONFERENCE_TRACK_MUTED | ASYNC | Implemented | Publisher muted their track — "camera off" included |
| ON_CONFERENCE_TRACK_UNMUTED | ASYNC | Implemented | Publisher unmuted their track |
| ON_ACTIVE_SPEAKER_CHANGED | ASYNC | Implemented | SFU reported a dominant-speaker change |
| ON_CONNECTION_QUALITY_CHANGED | ASYNC | Implemented | SFU reported a participant's connection quality |
| | | | |
| **Other:** | | | |
| ON_PLAN_UPDATED | ASYNC | Implemented | Orchestration plan was updated |
| ON_FEEDBACK | ASYNC | Implemented | Feedback/scoring event emitted |

### 9.3 Hook Execution Modes

**SYNC hooks:**

- Run sequentially, ordered by priority (lower number = first).
- Each hook receives the event and room context.
- Each hook MUST return a HookResult.
- A BLOCK result stops the pipeline — no further hooks run.
- A hook that does not produce a usable result MUST be treated as ALLOW with an
  error logged, so that a broken hook cannot take a room down. This covers a
  hook that raises, one that exceeds its timeout, one that returns something
  other than a HookResult, and a MODIFY whose payload is not of the type the
  trigger passed in.
- **Except on triggers whose payload is content a hook may exist to withhold**,
  where every one of those outcomes MUST block instead. BEFORE_TTS and
  ON_TRANSCRIPTION are those triggers: a redaction hook that fails, times out,
  or returns something unusable must not let the original through, and allowing
  would publish exactly what the hook was there to suppress. A partial rule is
  no rule — an implementation that blocks on exceptions but allows on timeouts
  leaks through the timeout. Implementations MUST document which triggers fail
  closed.
- A MODIFY result replaces the payload whenever one is supplied, including a
  falsy one. Redacting a string to empty is a modification; treating it as
  absent would pass the original to the next hook.

**ASYNC hooks:**

- Run concurrently after the triggering operation completes.
- Cannot block or modify events.
- Exceptions MUST be caught and logged, never propagated.
- Used for observability, logging, side effects.

### 9.4 HookResult

Sync hooks MUST return a HookResult:

```
HookResult
├── action: "allow" | "block" | "modify"
├── event: any | null                       # The replacement payload (for "modify" action)
├── reason: string | null                   # Why blocked or modified
├── injected_events: list<InjectedEvent>    # Events to inject when blocking
├── tasks: list<Task>                       # Tasks to create (side effects)
├── observations: list<Observation>         # Observations to record (side effects)
└── metadata: map<string, any>              # Additional hook metadata
```

`event` carries the replacement payload for a "modify" result, and its type is
whatever the trigger passed in. Only BEFORE_BROADCAST passes a RoomEvent: the
TTS trigger receives a string, the bridge triggers receive media frames, and the
tool and generation triggers receive their own event types. Typing this field as
a RoomEvent would make "modify" unusable for every trigger but one, so consumers
MUST check the type they expect before substituting it.

**InjectedEvent:**

```
InjectedEvent
├── event: RoomEvent                        # The event to inject
└── target_channel_ids: list<string> | null # Deliver to specific channels (null = store only)
```

### 9.5 Hook Pipeline (BEFORE_BROADCAST)

```
Inbound Event
      │
      ▼
┌──────────────────────────────────────┐
│ Sync Hooks (ordered by priority)     │
│                                      │
│ [0] Hook A → allow / block / modify  │
│ [1] Hook B → allow / block / modify  │
│ [2] Hook C → allow / block / modify  │
└──────────────┬───────────────────────┘
               │
          blocked? ──yes──→ Store event (status=BLOCKED, blocked_by=hook_name)
               │              Deliver InjectedEvents to target channels
               │              Persist tasks and observations
               │
               ▼ (allowed, possibly modified)
         Event Router
         Broadcasts to channels
               │
               ▼
┌──────────────────────────────────────┐
│ Async Hooks (fire and forget)        │
│                                      │
│ [·] Audit Logger                     │
│ [·] Analytics                        │
│ [·] Webhook Notifier                 │
└──────────────────────────────────────┘
```

### 9.6 When to Use What

| | Sync Hook | Async Hook | Read-Only Channel |
|---|---|---|---|
| Can **block** events | Yes | No | No |
| Can **modify** events | Yes | No | No |
| Can **inject** targeted events | Yes (on block) | No | No |
| Can produce **tasks/observations** | Yes | Yes | Yes |
| Can produce **response messages** | No | No | No (read-only) |
| Runs | Before broadcast | After broadcast | During broadcast |
| Typical use | Rule-based filtering | Logging, analytics | AI-powered analysis |

---

## 10. Processing Pipelines

### 10.1 Inbound Pipeline

The inbound pipeline processes messages arriving from external sources.

```
process_inbound(message: InboundMessage, room_id: string | null) → InboundResult
```

**Step-by-step:**

```
1. RESOLVE CHANNEL
   ├── Look up registered channel by message.channel_id
   └── Fail if channel not registered

2. ROUTE TO ROOM
   ├── If room_id provided → use it
   ├── Otherwise → call InboundRoomRouter.route(channel_id, channel_type, sender_id)
   │   ├── Router returns existing room → use it
   │   └── Router returns null → create new room
   └── If new room created → attach channel, fire ON_ROOM_CREATED hook

3. BUILD CONTEXT
   ├── Fetch room state
   ├── Fetch all bindings
   ├── Fetch all participants
   └── Fetch recent events (for AI context)

4. CHANNEL PROCESSES INBOUND
   └── channel.handle_inbound(message, context) → RoomEvent

5. IDENTITY RESOLUTION (if resolver configured and the sender has an address
   left to resolve — §11.6 skips a channel that names its own senders, and a
   sender the room has already identified)
   ├── Call resolver.resolve(message, context) with timeout
   ├── Handle result:
   │   ├── IDENTIFIED → create/update identified participant
   │   ├── AMBIGUOUS → fire ON_IDENTITY_AMBIGUOUS hook
   │   ├── UNKNOWN → fire ON_IDENTITY_UNKNOWN hook
   │   └── CHALLENGE_SENT → deliver challenge, block processing
   └── Stamp participant_id on event

6. ACQUIRE ROOM LOCK, THEN CHECK THE ROOM STILL ACCEPTS EVENTS
   ├── Re-read the room's status under the lock (§5.1)
   ├── If the status refuses new events (CLOSED, ARCHIVED):
   │   └── Return InboundResult(blocked=true, reason=room_closed)
   │       # Nothing is stored: a refused event is not appended to the
   │       # timeline, not even as BLOCKED (§5.1)
   └── Otherwise → continue
       # Under the lock because close_room() takes the same one. Checked
       # earlier, the answer can be stale by the time the event commits.

7. IDEMPOTENCY CHECK
   ├── If idempotency_key exists and was seen → return blocked result
   └── Otherwise → continue

8. ASSIGN EVENT INDEX
   └── event.index = room.event_count

9. RUN BEFORE_BROADCAST SYNC HOOKS
   ├── Execute hooks in priority order
   └── Collect result: allow / block / modify

10. IF BLOCKED BY HOOK:
    ├── Store event with status=BLOCKED, blocked_by=hook_name
    ├── Deliver injected events from hook result
    ├── Persist tasks and observations from hook result
    └── Return InboundResult(blocked=true)

11. CHECK SOURCE CAN WRITE
    ├── If source_binding.access ∉ {READ_WRITE, WRITE_ONLY} OR source_binding.muted:
    │   ├── Store event with status=BLOCKED,
    │   │   blocked_by = source_read_only | source_muted
    │   ├── Persist tasks and observations (side effects ALWAYS collected, §7.5)
    │   └── Return InboundResult(blocked=true)
    └── Otherwise → continue
        # A source that cannot write MUST NOT inject a DELIVERED event.

12. COMMIT EVENT — the commit point (§13.6, §14.3):
    ├── For EDIT/DELETE: apply the target state update now (§10.3) — deferred
    │   to this point so a hook that blocks the edit/delete leaves the target
    │   unmutated
    ├── Commit atomically, as ONE logical transaction:
    │   ├── Store event with status=DELIVERED
    │   └── Update room state: latest_index = event.index; event_count += 1;
    │       timers.last_activity_at = now
    │   # After this transaction returns, the event is durably part of the
    │   # timeline. It MUST NOT be retroactively re-marked BLOCKED or FAILED
    │   # (e.g. by process_timeout, §13.6) — the timeline is authoritative.
    │   # No separate, non-atomic room-state write ever follows this commit:
    │   # the timeline and the counters can never diverge (§14.3).
    ├── Deliver any injected events
    ├── IF message.session is set:
    │   └── Call channel.connect_session(session, room_id, binding)
    │       # Connects the voice session (starts realtime AI, etc.)
    └── PLAN BROADCAST — resolve the event's delivery set under the lock:
        └── Eligible target bindings (access, mute, visibility — §7) and
            their capability snapshot, appended to the room's delivery
            lane (§10.2). Planning reads bindings under the lock, so the
            target set is consistent with the committed timeline;
            EXECUTION does not require the lock.

13. RELEASE ROOM LOCK
    # The lock covers steps 6–12: room-status gate, idempotency, index
    # assignment, hooks, permission, commit, broadcast planning. External
    # delivery executes outside it (§10.2 delivery lanes) — a slow
    # provider MUST NOT extend the room's critical section (§13.5).

14. EXECUTE DELIVERY LANE (§10.2) — per-room FIFO, after lock release:
    ├── An event's delivery set MUST complete before the next event's
    │   begins — per room, in index order. Executing delivery under the
    │   room lock (the pre-lane behavior) trivially satisfies this
    │   ordering and remains conformant.
    ├── Each target: transcode → rate limit → on_event() / deliver()
    │   with per-operation timeouts (§10.2)
    └── REENTRY: response events emitted here (intelligence channels)
        re-enter the pipeline's locked section (steps 6–12) as new
        passes — each response takes the room lock for ITS OWN commit
        (index assignment, chain depth §8.3, the same atomic shape as
        step 12), and its delivery set joins the same lane in FIFO order.
        # Relaxation vs pre-lane implementations: a concurrent inbound
        # event MAY commit between a trigger and its response. Ordering
        # guarantees are per-room index monotonicity and parent linkage —
        # never timeline adjacency.

15. PERSIST SIDE EFFECTS
    └── Store all tasks and observations from hooks + channels

16. RUN AFTER_BROADCAST ASYNC HOOKS
    └── After the event's delivery set completes — "all channels have
        processed the event" (§9.2) is unchanged; only the timing may be
        later than under pre-lane implementations. Non-blocking,
        exceptions swallowed (§9.3) — a slow observer hook MUST NOT hold
        the room lock.

17. EMIT FRAMEWORK EVENTS
    └── event_processed, delivery_succeeded/failed, etc.

18. RETURN InboundResult
    └── The caller observes its event's delivery-set completion, so
        delivery_results reports executed deliveries. An implementation
        MAY additionally offer detached completion; the outbox model
        (§13.6) then governs crash recovery.
```

**InboundResult:**

```
InboundResult
├── event: RoomEvent | null                 # The processed event (null if blocked)
├── blocked: bool                           # Whether the event was blocked
├── reason: string | null                   # Block reason
└── delivery_results: map<string, DeliveryResult>
```

### 10.2 Broadcast Pipeline

The broadcast pipeline routes an event to all eligible channels in a room.

```
broadcast(event, source_binding, context) → BroadcastResult
```

**Planning vs execution — delivery lanes.** Broadcast splits at the room
lock boundary (§10.1 steps 12–14). *Planning* — resolving the delivery set
(steps 1–2 below) — MUST run under the room lock, against binding state
consistent with the committed timeline. *Execution* — the per-target work of
step 3 — is NOT required to hold the room lock; it MUST instead preserve
**per-room order**: events execute their delivery sets in index order, one
event's set completing before the next event's begins (a *delivery lane*
per room). Executing under the room lock trivially satisfies this ordering
and remains conformant — the lane model exists so that a slow provider or a
long AI generation does not extend the room's critical section (§13.5),
which is what serializes multi-process deployments. Response events
re-enter the pipeline as their own commit passes (§10.1 step 14) rather
than being drained inside the trigger's lock tenure.

**Step-by-step:**

```
1. CHECK SOURCE CAN WRITE
   ├── source_binding.access must be READ_WRITE or WRITE_ONLY
   └── source_binding.muted must be false
       (if muted: suppress events but collect side effects)

2. DETERMINE TARGET CHANNELS
   ├── Get all bindings in room
   ├── Exclude source channel
   ├── Exclude channels with access = WRITE_ONLY or NONE
   ├── Exclude OUTBOUND-only channels
   └── Apply visibility filter from source_binding.visibility

3. FOR EACH TARGET CHANNEL (concurrently):
   │
   ├── a. TRANSCODE CONTENT
   │      └── Convert event content to target's supported media types
   │
   ├── b. ENFORCE MAX LENGTH
   │      └── Truncate text if target.capabilities.max_length exceeded
   │
   ├── c. CALL on_event() (all readable channels)
   │      ├── Intelligence channels: only those solicited (§19.3)
   │      └── Collect ChannelOutput (response events, tasks, observations)
   │
   ├── d. CALL deliver() (transport channels only)
   │      ├── Apply rate limiter
   │      ├── Check circuit breaker
   │      ├── Call provider
   │      ├── On failure → apply retry policy
   │      └── Record delivery result
   │
   └── e. COLLECT RESULTS
          ├── Response events → queue for reentry
          ├── Tasks and observations → accumulate
          └── Errors → record per-channel

4. HANDLE MUTED CHANNELS
   ├── Muted channels STILL receive on_event()
   ├── Response events from muted channels are SUPPRESSED
   └── Tasks and observations from muted channels are COLLECTED

5. RETURN BroadcastResult
```

**BroadcastResult:**

```
BroadcastResult
├── outputs: map<string, ChannelOutput>         # on_event() results per channel
├── delivery_outputs: map<string, ChannelOutput> # deliver() results per channel
├── reentry_events: list<RoomEvent>             # Response events for reentry loop
├── tasks: list<Task>                           # Accumulated tasks
├── observations: list<Observation>             # Accumulated observations
├── metadata_updates: map<string, any>          # Room metadata to update
├── blocked_events: list<RoomEvent>             # Chain-depth-blocked events
└── errors: map<string, string>                 # Per-channel error messages
```

**Solicitation.** Step 3c asks a channel to act. For transport channels that
is unconditional; for intelligence channels the set is narrowed by the
event's address and by the room's agent-response policy (§19.3). Narrowing
solicitation MUST NOT narrow *visibility*: the two filters are independent,
and an event hidden from a channel by §7.3 is hidden whether or not it was
addressed to it. Whether an unsolicited intelligence channel is nevertheless
called at step 3c — delivered without being asked — is left to the
implementation by this version (§19.3.2).

### 10.3 Edit and Delete Processing

When an inbound event has type EDIT or DELETE, the framework MUST perform
additional validation and state updates before broadcasting.

**Validation:**

1. The framework MUST verify that `target_event_id` (from `EditContent` or
   `DeleteContent`) references an existing event in the same room.
2. For `DeleteContent` with `delete_type = SENDER` or `EditContent` with
   `edit_source = "sender"`, the framework MUST verify that the inbound sender
   is the original author of the target event.
3. For `DeleteContent` with `delete_type = ADMIN`, the framework MUST verify
   that the sender has administrative authority (e.g., via permissions or role).
4. For `DeleteContent` with `delete_type = SYSTEM`, the event SHOULD originate
   from a SYSTEM channel or a hook.
5. If validation fails, the framework MUST reject the event and SHOULD return
   an error to the source channel.

**State updates** (applied only after BEFORE_BROADCAST hooks allow the event —
a hook that blocks the EDIT/DELETE MUST leave the target event unmutated):

1. On successful EDIT: the framework SHOULD call `update_event()` to replace the
   original event's content with `EditContent.new_content` and set
   `metadata.edited = true`. The EDIT event itself MUST be stored in the timeline.
2. On successful DELETE: the framework SHOULD call `update_event()` to set
   `metadata.deleted = true` on the original event. The DELETE event itself MUST
   be stored in the timeline.

**Mutation triggers:** After a successful EDIT the framework MUST fire
`ON_EVENT_UPDATED` with the mutated target event; after a successful DELETE it
MUST fire `ON_EVENT_DELETED`. Firings follow the async-hook locking rule of
§10.1 (deferred until the room lock is released). A blocked EDIT/DELETE MUST
NOT fire either trigger. These triggers let observers (e.g. maintainers of
denormalized projections over the timeline) see every stored-state change
regardless of origin.

**Direct mutation (host-owned):** The framework SHOULD also expose direct
APIs — `update_event(room_id, event_id, content|source|metadata)` and
`delete_event(room_id, event_id, cascade_replies)` — for host applications
that own authorization on their own surfaces. Direct `update_event()` replaces
the provided fields wholesale and adds no `edited` marker; direct
`delete_event()` is a HARD delete that MUST cascade to thread replies by
default (no self-referential FK protects them) and MUST return the deleted
event IDs. Both MUST serialise against inbound processing via the room lock
and MUST fire the corresponding mutation trigger after the lock is released;
a target that does not exist in the room MUST be a no-op that fires nothing.

**Broadcast behavior:**

During broadcast, for each target channel:

1. If the target channel's `capabilities.supports_edit` is true (for EDIT events)
   or `capabilities.supports_delete` is true (for DELETE events), the framework
   SHOULD deliver the event natively.
2. If the target channel does NOT support the operation, the framework MUST
   apply transcoding fallback (see Section 6.6).

### 10.4 Inbound Room Routing

When an inbound message arrives without a pre-determined room_id, the framework
MUST route it to an appropriate room.

```
InboundRoomRouter (interface)
└── route(channel_id, channel_type, sender_id, metadata) → Room | null
```

**Default routing strategy:**

1. Find the latest ACTIVE room where a participant with the same sender address
   is connected via the same channel type.
2. If found → return that room.
3. Otherwise, if the channel is bound to exactly **one** ACTIVE room → return
   that room.
4. If not found → return null (framework creates a new room).

Step 3 is what routes a channel dedicated to a single conversation, where no
participant has spoken yet. It is deliberately narrower than "the channel is
bound to some room".

**A router MUST NOT guess.** When the inputs it was given match more than one
ACTIVE room, it MUST return null rather than choose among them. Returning any
one of several candidates delivers a message into a conversation it does not
belong to, and — because the room it lands in is where the message is stored,
broadcast to that room's channels, and read back as context by that room's
agent — the disclosure is durable, not transient. Null is the safe answer: the
framework creates a new room, which is recoverable, whereas a wrong room is
not.

This is not a hypothetical configuration. An implementation that lets a
channel be shared across rooms (§19, delegation) creates it as a matter of
course, and a channel re-attached after its room closed accumulates the same
shape over time. An integrator whose deployment genuinely needs a shared
channel routed by something else MUST name the room explicitly (§10.1 step 2)
or supply a custom strategy.

**Routing MUST be deterministic.** The same inputs against the same stored
state MUST select the same room, whatever the storage backend. An
implementation whose answer depends on insertion order in one store and on the
query planner in another does not satisfy this, and its behaviour cannot be
reasoned about from the specification.

Implementations MUST allow integrators to provide a custom routing strategy.

### 10.5 Direct Event Injection

Integrators MAY inject events into a room directly, without an inbound channel
message (e.g., from a REST API or MCP tool call):

```
send_event(room_id, channel_id, content, event_type, ...) → RoomEvent
```

The injected event traverses the SAME pipeline as an inbound message
(Section 10.1): index assignment, BEFORE_BROADCAST hooks, the source
write-permission gate, EDIT/DELETE handling, persistence and broadcast
planning under the room lock, then its delivery lane, reentry passes, and
AFTER_BROADCAST hooks. A blocking hook therefore yields a `BLOCKED` event
and suppresses delivery, exactly as for an inbound message.

---

## 11. Identity Resolution

### 11.1 Identity Resolver Interface

```
IdentityResolver (interface)
└── resolve(message: InboundMessage, context: RoomContext) → IdentityResult
```

**IdentityResult:**

```
IdentityResult
├── status: IdentificationStatus            # IDENTIFIED, AMBIGUOUS, UNKNOWN, PENDING, CHALLENGE_SENT, REJECTED
├── identity: Identity | null               # Resolved identity (if IDENTIFIED)
├── candidates: list<Identity>              # Candidate identities (if AMBIGUOUS)
└── metadata: map<string, any>              # Resolution metadata
```

### 11.2 Resolution Pipeline

```
Inbound arrives (channel_type, sender_address)
      │
      ▼
IdentityResolver.resolve(message, context)
      │
      ▼
Returns IdentityResult
      │
      ├── IDENTIFIED (1 match)
      │   └── Create participant with identity_id set
      │
      ├── AMBIGUOUS (N matches)
      │   ├── Fire ON_IDENTITY_AMBIGUOUS hook
      │   └── Hook returns:
      │       ├── resolved(identity) → use that identity
      │       ├── pending(candidates) → create pending participant
      │       ├── challenge(inject) → send challenge, block processing
      │       └── reject() → reject the message
      │
      └── UNKNOWN (0 matches)
          ├── Fire ON_IDENTITY_UNKNOWN hook
          └── Hook returns:
              ├── create(new_identity) → create identity and participant
              ├── pending() → create pending participant
              ├── challenge(inject) → send challenge, block processing
              └── reject() → reject the message
```

### 11.3 Identity Hook Result

```
IdentityHookResult
├── action: "resolved" | "pending" | "challenge" | "reject" | "create"
├── identity: Identity | null               # For "resolved" action
├── candidates: list<Identity>              # For "pending" action
├── injected_events: list<InjectedEvent>    # For "challenge" action
├── new_identity: Identity | null           # For "create" action
└── reason: string | null                   # For "reject" action
```

### 11.4 Channel Type Filtering

Implementations SHOULD support configuring which channel types trigger identity
resolution. Not all channels carry meaningful identity information (e.g., an
internal WebSocket may not need identity resolution).

### 11.5 Timeout Handling

If identity resolution exceeds the configured timeout, the implementation MUST:

1. Treat the result as UNKNOWN.
2. Emit an `identity_timeout` framework event.
3. Continue processing the inbound message (do not block).

### 11.6 Senders With Nothing To Resolve

A resolver maps an **address** — a number, an email, a handle — to an Identity.
Two senders carry no such question, and an implementation MUST NOT run
resolution for them:

1. **The channel names its own senders.** A channel MAY declare that its
   inbound `sender_id` is a room `Participant.id` rather than an address. A
   conference is the case this exists for (Section 12.10.4): its utterances
   carry the identity a track was published under, and resolving that is the
   "resolve on the opaque identity" Section 12.10.2 rule 3 rules out.
2. **The room has already identified the sender.** Where the event's
   `participant_id` names a Participant of the room whose `identification` is
   IDENTIFIED, the question has been answered and the answer is on the roster.

Case 1 is not the conference alone. The test is where the `sender_id` comes
from. A channel that reads it off the wire carries whatever the remote network
put there, and is not this case. A channel the implementation itself names the
sender of — an interactive terminal, whose sender is a Participant the
implementation chose rather than a party that reached it from outside — is the
same case as the conference, and declares it for the same reason. A channel
whose `sender_id` is supplied by the integrator is neither: it may carry an
address or it may not, which is why Section 11.4 leaves that one to
configuration rather than to the channel.

`PENDING` and `AMBIGUOUS` participants are deliberately not in case 2: a
participant the room *has* is not a participant the room has *identified*, a
resolver may still be what settles it, and the identity hooks of Section 11.2
may still want to challenge or refuse it.

This is not an optimisation. Re-resolving a sender the room has already
identified produces UNKNOWN — no resolver matches a framework identifier — so
`ON_IDENTITY_UNKNOWN` fires per message, and the refusal pattern Section 11.2
provides for (`reject`) then blocks every message from a participant the
implementation itself identified. Skipping it is what keeps that pattern
composable with channels that name their own participants.

When resolution is skipped, the event's `participant_id` MUST be left as the
channel set it, and no participant record is created or modified: the sender is
either already a participant or deliberately unattributed.

---

## 12. Voice and Realtime Media

### 12.1 Architecture Overview

RoomKit supports four real-time media architectures:

```
Architecture 1: STT/TTS Pipeline (VoiceChannel)
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌─────┐     ┌──────────┐
│ Client   │────→│Audio Pipeline│────→│   STT    │────→│Room │────→│   TTS    │────→ Client
│ (audio)  │     │(denoise/VAD/ │     │Provider  │     │Kit  │     │Provider  │
└──────────┘     │ diarization) │     └──────────┘     └─────┘     └──────────┘
                 └──────────────┘

Architecture 2: Speech-to-Speech (RealtimeVoiceChannel)
┌──────────┐     ┌──────────────┐     ┌──────────────────────────┐     ┌──────────┐
│ Client   │────→│Audio Pipeline│────→│ Speech-to-Speech API     │────→│ Client   │
│ (audio)  │     │  (optional)  │     │ (OpenAI Realtime, etc.)  │     │ (audio)  │
└──────────┘     └──────────────┘     └────────────┬─────────────┘     └──────────┘
                  denoise, diarize                  │
                                              transcriptions
                                              tool calls
                                                    │
                                                    ▼
                                               ┌─────────┐
                                               │ RoomKit │
                                               │ (events)│
                                               └─────────┘
```

**Choosing between architectures:**

| Criterion | VoiceChannel (STT/TTS) | RealtimeVoiceChannel (Speech-to-Speech) | VoiceChannel (Bridge) | ConferenceChannel (SFU) |
|---|---|---|---|---|
| **Latency** | Moderate (~500-800ms TTFA with streaming) | Lower — end-to-end streaming | Lowest — direct audio forwarding | Low — SFU forwards media directly between clients |
| **Control** | Full — choose STT, LLM, TTS | Limited — provider bundles all | Full pipeline, no AI required | Control plane only — media plane is external |
| **Text access** | Always — utterances become RoomEvents | Optional — if transcription configured | Optional — if STT configured | Per-track STT, attributed per participant |
| **Multi-channel** | Native — text routes to any channel | Requires transcription | Requires STT for text routing | Native — transcripts are RoomEvents |
| **AI involvement** | Required (generates responses) | Required (speech-to-speech) | Optional (observer/monitor) | Optional (bot participant) |
| **Voice quality** | Depends on TTS provider | Native speech generation | Original voice preserved | Original voice preserved |
| **Pipeline control** | Full audio pipeline (all stages) | Pipeline optional | Full pipeline (all stages) | Per-track inbound lanes (no AEC/diarization) |
| **Use when** | AI voice agent with text in the loop | Lowest latency AI with native voice | Human-to-human calls, conferencing, call center | Multi-party video conferences, AI in meetings |

All four architectures MAY coexist in the same room. For example, a room could
have a VoiceChannel for a human participant (PSTN/SIP) and a RealtimeVoiceChannel
for the AI agent, with text events bridging them. Or two VoiceChannels in bridge
mode for a human-to-human call with optional AI observation.

```
Architecture 3: Audio Bridge (VoiceChannel with bridge=True)
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ Client A │────→│Audio Pipeline│────→│ Audio Bridge  │────→│Audio Pipeline│────→│ Client B │
│ (audio)  │     │  (inbound)   │     │ (forward/mix) │     │  (outbound)  │     │ (audio)  │
└──────────┘     └──────────────┘     └───────┬───────┘     └──────────────┘     └──────────┘
                                              │
                                         (optional)
                                       STT transcription
                                              │
                                              ▼
                                         ┌─────────┐
                                         │ RoomKit │
                                         │ (events)│
                                         └─────────┘
```

```
Architecture 4: SFU Conference (ConferenceChannel — Section 12.10)
┌──────────┐           ┌─────────────────┐           ┌──────────┐
│ Client A │◄─────────►│                 │◄─────────►│ Client B │
│ (browser)│   media   │  External SFU   │   media   │ (browser)│
└──────────┘           │  (media plane)  │           └──────────┘
                       └────────┬────────┘
                                │ bot participant
                                │ (subscribed tracks, published TTS)
                                ▼
                       ┌─────────────────┐
                       │     RoomKit     │
                       │ per-track STT,  │
                       │ vision, TTS bot │
                       │ (control plane) │
                       └─────────────────┘
```

### 12.2 Voice Channel (STT/TTS Pipeline)

The Voice Channel processes audio through a pipeline of STT and TTS providers,
converting speech to text events and text responses back to speech.

**Required components:**

| Component | Interface | Purpose |
|---|---|---|
| VoiceBackend | See below | Real-time audio transport (WebRTC, WebSocket) |
| STTProvider | See below | Speech-to-text conversion |
| TTSProvider | See below | Text-to-speech synthesis |

**VoiceBackend interface:**

```
VoiceBackend (interface)
├── connect(room_id, participant_id, channel_id) → VoiceSession
├── disconnect(session) → void
├── send_audio(session, audio_chunks) → void
├── cancel_audio(session) → void            # Cancel current playback (if supported)
├── send_dtmf(session, digit, duration_ms) → void  # Send outbound DTMF (RFC 4733)
│
│   # Raw audio callback:
├── on_audio_received(callback) → void      # Raw inbound audio frames from client
│
│   # Barge-in (transport-level detection):
├── on_barge_in(callback) → void            # Client audio detected during playback
│
│   # Session lifecycle:
├── on_session_ready(callback) → void       # Audio path is live, ready for send/receive
├── on_transport_disconnect(callback) → void  # Detect transport-level disconnect
│
│   # Server-side session acceptance:
├── accept(request) → VoiceSession          # Accept an inbound session (SIP/PSTN/WebRTC offer)
│
│   # Protocol tracing:
├── set_trace_emitter(emitter | null) → void  # Set callback for emitting ProtocolTraces
│
│   # Properties:
├── name: string                            # Backend identifier for attribution and logging
├── auto_connect: bool                      # Auto-create session when channel is attached to a room
│
├── capabilities() → VoiceCapability        # What the backend supports
└── close() → void
```

**Note:** `on_speech_start`, `on_speech_end`, `on_vad_silence`, and
`on_vad_audio_level` are removed from VoiceBackend. These events are now emitted
by the audio pipeline's VAD provider (Section 12.3). `on_partial_transcription`
is emitted by the STT provider. `on_barge_in` remains on VoiceBackend as it is a
transport-level concern (detecting client audio during active playback).

**VoiceCapability** flags:

| Flag | Description |
|---|---|
| INTERRUPTION | Can cancel TTS playback |
| BARGE_IN | Detect user audio during TTS playback |
| NATIVE_AEC | Backend provides built-in echo cancellation (skip pipeline AEC) |
| NATIVE_AGC | Backend provides built-in gain control (skip pipeline AGC) |
| DTMF_INBAND | Backend receives in-band DTMF tones in audio stream |
| DTMF_SIGNALING | Backend sends and receives DTMF via signaling (RFC 4733) |
| NATIVE_BRIDGE | Backend can bridge audio at the transport level (RTP relay) |

When a VoiceBackend declares `NATIVE_AEC` or `NATIVE_AGC`, the pipeline MUST
skip the corresponding stage automatically, even if a provider is configured in
`AudioPipelineConfig`. This prevents double processing.

When a VoiceBackend declares `DTMF_SIGNALING`, DTMF events arrive via the
signaling layer (not the audio stream). The pipeline's DTMFDetector handles
in-band detection only. Implementations MUST merge both sources into the same
ON_DTMF hook.

**VoiceSession:**

```
VoiceSession
├── id: string                              # Session identifier
├── room_id: string                         # Associated room
├── participant_id: string                  # Associated participant
├── channel_id: string                      # Associated voice channel
├── state: VoiceSessionState                # Current session state
├── created_at: datetime                    # Session start time
└── metadata: map<string, any>              # Session-specific data
```

**VoiceSessionState** enumeration:

| Value | Meaning |
|---|---|
| CONNECTING | Session is being established (transport handshake, provider init) |
| ACTIVE | Audio is flowing bidirectionally |
| PAUSED | Session temporarily suspended (e.g., hold, mute) |
| ENDED | Session terminated — no further audio |

**Transitions:**

- CONNECTING → ACTIVE: Transport connected and provider ready.
- ACTIVE → PAUSED: Integrator pauses session (e.g., call hold).
- PAUSED → ACTIVE: Integrator resumes session.
- ACTIVE → ENDED: Session terminated (user hangup, timeout, integrator call).
- CONNECTING → ENDED: Connection failed.
- PAUSED → ENDED: Session terminated while paused.

Implementations MUST NOT allow transitions from ENDED to any other state. A new
session MUST be created if the participant reconnects.

**STTProvider interface:**

```
STTProvider (interface)
├── name: string
├── transcribe(audio_chunk) → TranscriptionResult
└── transcribe_stream(audio_stream) → async_iterator<TranscriptionResult>

TranscriptionResult
├── text: string
├── is_final: bool
├── confidence: float | null
└── language: string | null
```

**TTSProvider interface:**

```
TTSProvider (interface)
├── name: string
├── supports_streaming_input: bool (default false)
│       # Whether this TTS accepts streaming text input
├── synthesize(text, voice: string | null) → AudioContent
│       # Returns AudioContent (Section 5) with url, mime_type, transcript, duration_seconds
├── synthesize_stream(text, voice: string | null) → async_iterator<AudioChunk>
│       # Stream audio from a complete text string
└── synthesize_stream_input(text_stream, voice: string | null) → async_iterator<AudioChunk>
        # Stream audio from streaming text chunks (requires supports_streaming_input = true)
        # Accepts an async iterator of text strings (e.g., sentences from a sentence splitter)
        # Used by VoiceChannel for streaming AI → TTS
```

`synthesize()` returns an `AudioContent` (Section 5) rather than raw bytes.
This allows the result to carry metadata (transcript, duration, MIME type) and
supports both inline data URLs and remote storage URLs. For streaming,
`synthesize_stream()` yields `AudioChunk` objects as they become available.
`synthesize_stream_input()` is the streaming-input variant: it accepts an async
iterator of text chunks (typically sentences) and yields audio as each chunk is
synthesized. This enables the streaming AI → TTS pipeline where LLM tokens are
buffered into sentences and fed to TTS incrementally.

**Audio processing flow:**

```
1. Client sends audio stream → VoiceBackend
2. VoiceBackend emits raw frames → Audio Pipeline (Section 12.3)
3. Pipeline: [Resampler] → [AEC] → [AGC] → [Denoiser] → [VAD] → [Diarization]
   (DTMF detection runs in parallel from resampled stream)
   (Recorder captures inbound after resampler)
4. VAD detects speech end → ON_SPEECH_END hook fires
5. STT transcribes captured audio → TranscriptionResult
6. Fire ON_TRANSCRIPTION hook (can modify transcript)
7. If TurnDetector configured → evaluate turn completion
   ├── Complete → Create RoomEvent
   └── Incomplete → accumulate, wait for next speech

--- Standard path (non-streaming) ---
8. Route through normal inbound pipeline
9. Room broadcasts → AI or other channels respond
10. Response event arrives at Voice channel via deliver()
11. If TextContent → Fire BEFORE_TTS hook → TTS synthesizes → AudioChunk stream

--- Streaming AI → TTS path (framework-native, when AIProvider supports streaming) ---
8s. Route through normal inbound pipeline → Room broadcasts to AIChannel
9s. AIChannel.on_event() returns ChannelOutput(response_stream=generate_stream())
10s. Framework detects response_stream in broadcast result
11s. Framework finds streaming delivery targets (channels with supports_streaming_delivery)
12s. Framework pipes stream → VoiceChannel.deliver_stream():
     a. Sentence splitter buffers tokens → yields at sentence boundaries (.!?)
        (min_chunk_chars threshold prevents very short TTS fragments)
     b. tts.synthesize_stream_input(sentences) → AudioChunk stream (~200ms TTS TTFB)
        First audio reaches speaker ~500-800ms after speech end (vs ~2-3s standard)
13s. Framework accumulates full text from stream → stores AI response event
14s. Framework re-broadcasts complete event to non-streaming channels (exclude_delivery
     skips channels that already received streaming content)
15s. Fire AFTER_TTS hook (BEFORE_TTS skipped — cannot block mid-stream)

--- Common outbound path ---
12. AudioChunk stream → [PostProcessors] → [Recorder] → [Resampler] → Transport
    (TTS emits variable-size AudioChunks; pipeline stages that require fixed-size
     AudioFrames MUST buffer and re-chunk the stream internally)
13. AEC reference: Transport feeds AEC.feed_reference() at playback time (local hw)
    or pipeline feeds it in the outbound path (network transports) — see 12.3.4
14. If barge-in detected → InterruptionConfig determines response
```

The streaming path flows through the framework's normal routing infrastructure.
AIChannel returns a streaming handle, the framework pipes it to streaming-capable
transport channels, accumulates the full text, stores the complete event, and
re-broadcasts to non-streaming channels. This preserves multi-channel delivery,
hooks, tool calling (falls back to non-streaming), and keeps VoiceChannel as
pure transport with no AIProvider reference.

#### 12.2.1 Packet Loss Handling (Lossy Transports)

Backends carrying audio over lossy transports (RTP/SIP, datagram-based) are the
only layer that can observe packet loss: sequence numbers exist at the
transport, and the pipeline above sees only PCM frames. A backend that silently
drops lost packets compresses the delivered timeline — recordings shorten, AEC
reference alignment drifts — and no downstream stage can detect or repair it.

Packet loss concealment (PLC) is OPTIONAL for Level 3 conformance and
RECOMMENDED for RTP-based backends.

**Detection.** A backend implementing PLC:

- MUST distinguish packets that have not yet arrived (reordering) from packets
  confirmed lost, using sequence-number analysis with a bounded reordering
  window. Packets the jitter buffer can still deliver MUST NOT trigger
  concealment.
- MUST NOT treat sender-side transmission pauses as loss. Discontinuous
  transmission (VAD suppression, comfort noise) advances the RTP timestamp
  without consuming sequence numbers; only sequence-number gaps indicate loss.
- MUST account for non-media packets filtered out of the audio path before
  loss detection. RFC 4733 telephone-events consume sequence numbers from the
  same RTP stream: a receiver that filters them upstream of its jitter buffer
  MUST mark those sequence numbers as received, so the filtered slots are
  neither confirmed as loss nor concealed.

**Concealment.** On confirmed loss, the backend:

- MUST deliver a temporally continuous stream: the lost duration is replaced
  with concealment audio so the frames emitted to the pipeline preserve
  timeline alignment. Downstream stages (AEC, recorder, STT) require no loss
  awareness.
- SHOULD use codec-native concealment when the negotiated codec provides it
  (e.g., libopus PLC). For codecs without native concealment (G.711, G.722,
  L16), the backend MUST fall back to a generic concealer that at minimum
  repeats the last received frame with progressive attenuation.
- MUST bound synthetic audio: a generic concealer MUST decay to silence within
  `max_conceal_ms` (RECOMMENDED 60 ms) of consecutive concealment and fill the
  remaining lost duration with silence. Codec-native concealment with built-in
  energy decay (e.g., libopus PLC) satisfies this requirement as-is. Either
  way, alignment is preserved without generating artifacts on long bursts.

**Observability.** A backend implementing PLC MUST expose, per session:

- `packets_lost` — count of packets confirmed lost.
- `concealed_frames` — count of frames synthesized by concealment.

Emitted concealed frames SHOULD be annotated (`metadata.concealed = true` on
the AudioFrame) so that pipeline stages MAY treat them differently — e.g., the
recorder journaling concealed ranges, or STT adjusting confidence.

### 12.3 Audio Processing Pipeline

The audio processing pipeline is a configurable layer between the transport and
the conversation engine. The transport delivers raw audio frames; the pipeline
processes them before they reach STT or speech-to-speech providers. All stages
are optional — configure what the use case requires. A symmetric outbound
pipeline processes audio before it reaches the transport.

This design ensures that audio processing capabilities (VAD, denoising,
diarization) are available regardless of the transport choice (FastRTC, WebSocket,
SIP, or any custom transport) and regardless of the voice architecture
(STT/TTS or speech-to-speech).

**Inbound (preprocessing):**

```
Transport → [Resampler] → [Recorder ◉] → [AEC] → [AGC] → [Denoiser] → [VAD] → [Diarization] → STT
             (normalize)   (capture raw)  (echo)  (volume)   (clean)    (detect)  (who speaks)
                                 │
                           [DTMF Detector]
                           (parallel from resampled stream)

◉ Recorder taps the stream (non-blocking copy), does not modify frames.
```

**Note on ordering rationale:**

| Position | Stage | Why here |
|---|---|---|
| 1 | Resampler | All downstream stages expect a consistent format (e.g., 16kHz mono PCM). Must run first. |
| 1b | Recorder (inbound tap) | Capture raw user audio in consistent format before any processing — compliance requires unmodified signal. |
| 2 | AEC | Needs clean format but must run before denoiser — echo is not "noise", it's a known reference signal. |
| 3 | AGC | Normalize volume before denoiser and VAD — both are amplitude-sensitive. |
| 4 | Denoiser | Remove environmental noise from volume-normalized, echo-cancelled audio. |
| 5 | VAD | Detect speech in clean audio. |
| 6 | Diarization | Identify speaker from clean speech segments. |
| — | DTMF | Runs in parallel on the resampled stream — DTMF tones would be destroyed by denoiser/AGC. |

**Outbound (postprocessing):**

```
TTS / Speech-to-Speech Provider → [PostProcessors] → [Recorder ◉] → [AEC ref †] → [Resampler] → Transport
                                   (normalize, etc.)  (capture final)  (feed AEC)   (match format)

◉ Recorder taps outbound stream after postprocessors (what the user actually hears).

† AEC reference feeding: for network transports, the pipeline feeds AEC.feed_reference() here.
  For local hardware transports, the transport itself feeds reference from the speaker output
  callback for precise time alignment (see Section 12.3.4). The pipeline skips this step when
  the transport handles AEC reference feeding directly.
```

**Pipeline symmetry with text hooks:**

| Text Pipeline | Audio Pipeline |
|---|---|
| BEFORE_BROADCAST (sync hooks) | Inbound audio preprocessing (resampler → AEC → AGC → denoiser → VAD) |
| AFTER_BROADCAST (async hooks) | Outbound audio postprocessing (postprocessors → recorder → resampler) |
| ON_TRANSCRIPTION hook | Post-STT hook (exists in Section 12.5) |
| BEFORE_TTS hook | Pre-synthesis hook (exists in Section 12.5) |
| — | Turn detection (post-STT, pre-room event) |
| — | Interruption handling (barge-in → backchannel detection) |

**Note on subsection ordering:** The subsections below (12.3.1–12.3.14) are
organized by concern (configuration, then inbound stages, then outbound stages,
then frame format, then post-STT stages, then execution flow) — NOT by pipeline
execution order. For execution order, see the inbound/outbound diagrams above
and the Pipeline Execution Flow (Section 12.3.14).

#### 12.3.1 Pipeline Configuration

```
AudioPipelineConfig
├── resampler: ResamplerConfig | null        # OPTIONAL format normalization (RECOMMENDED)
├── aec: AECProvider | null                  # OPTIONAL echo cancellation
├── agc: AGCProvider | null                   # OPTIONAL automatic gain control
├── denoiser: DenoiserProvider | null        # OPTIONAL noise reduction
├── vad: VADProvider | null                  # OPTIONAL voice activity detection
├── diarization: DiarizationProvider | null  # OPTIONAL speaker identification
├── dtmf: DTMFDetector | null               # OPTIONAL DTMF tone detection
├── turn_detector: TurnDetector | null       # OPTIONAL semantic turn detection (post-STT)
├── recorder: AudioRecorder | null           # OPTIONAL bidirectional recording
├── postprocessors: list<AudioPostProcessor> # OPTIONAL outbound processing chain
├── vad_config: VADConfig | null             # OPTIONAL VAD tuning parameters
├── interruption: InterruptionConfig | null  # OPTIONAL barge-in behavior (default: CONFIRMED)
└── debug_taps: PipelineDebugTaps | null     # OPTIONAL diagnostic stage capture (Section 12.3.15)
```

All stages are OPTIONAL. At least one provider SHOULD be configured for the
pipeline to be useful. Typical configurations:

- **Voice Channel (STT/TTS):** VAD (required for speech detection) + optional
  denoiser, AEC, AGC, and diarization.
- **Realtime Voice Channel (speech-to-speech):** Denoiser, AEC, and/or diarization
  only — the AI provider handles turn detection, so VAD is not needed.
- **PSTN/SIP integration:** Resampler (RECOMMENDED) + DTMF + recorder + VAD.

```
VADConfig
├── silence_threshold_ms: int = 500          # Silence duration to trigger speech_end
├── speech_pad_ms: int = 300                 # Padding around speech segments
└── min_speech_duration_ms: int = 250        # Minimum speech duration to emit event
```

The audio pipeline is configured per Voice Channel or per Realtime Voice Channel.
Different channels in the same room MAY have different pipeline configurations.

**Pipeline format contract:**

```
AudioPipelineContract
├── internal_format: AudioFormat             # All stages operate on this format
├── transport_inbound_format: AudioFormat    # Format received from transport
└── transport_outbound_format: AudioFormat   # Format expected by transport

AudioFormat
├── sample_rate: int                         # Sample rate in Hz
├── channels: int                            # Channel count
├── sample_width: int                        # Bytes per sample
└── codec: string                            # Encoding (e.g., "pcm_s16le", "opus", "mulaw")
```

When the pipeline starts, implementations MUST validate that all configured
stages are compatible with the internal format. If a stage requires a different
format (e.g., a specific VAD requires 16kHz), the implementation MUST either:
- Configure the resampler to match, or
- Raise a configuration error at startup (fail fast).

**Stream identity contract:**

One `AudioPipeline` serves many audio streams. A Voice Channel bridging
participants carries one stream per session; a conference carries one per lane.
These are different speakers sharing one set of stage instances.

Every stage therefore receives a **stream key** and MUST keep its state under
it:

```
process(audio_frame: AudioFrame, stream: string) → ...
reset(stream: string) → void
close() → void
```

The stream key is an opaque identifier chosen by the caller — a session id, a
lane id — and is stable for the life of that stream. Implementations MUST NOT
share adaptive state between streams: VAD hangover and speech buffers, denoiser
history, AGC gain, AEC adaptive filters and delay estimates, and diarization
accumulators are all per stream. Sharing them makes one speaker's silence close
another speaker's utterance.

`stream` MUST be a required parameter with **no default value**. A default
would let an implementation accept the argument, ignore it, satisfy the
interface, and mix streams silently — which is the failure this contract exists
to prevent. A conformance check SHOULD verify that a stream's output sequence is
unchanged when a second stream is interleaved with it.

For providers backed by a native SDK, the model and the adaptive state
typically live in the same object (SpeexDSP's `SpeexEchoState`, RNNoise's
`DenoiseState`, WebRTC's `AudioProcessing`). Per-stream state then means one
native instance per stream; these SDKs offer no way to share the model alone.
Implementations SHOULD create it lazily on the stream's first frame.

State that is **not** per stream stays on the instance: immutable
configuration, process-level resources, and shared registries such as a
diarization provider's enrolled-speaker set — enrolment belongs to the room, not
to a speaker's current stream.

**Session lifecycle contract:**

Implementations MUST call `reset(stream)` on every configured stage when that
stream ends, releasing its state. Omitting this leaks one speaker's worth of
buffers — and, for native providers, C memory — for every stream a long-running
room ever had.

Implementations MUST also call `reset(stream)` before the first audio frame of a
new stream, so a reused key never inherits adaptive state (denoiser filter
coefficients, VAD speech buffers, AGC gain history, diarization accumulators)
from a previous stream with the same id.

`close()` remains global and MUST release every stream's state.

#### 12.3.2 Denoiser Provider

The denoiser removes background noise from inbound audio before VAD and STT
process it. Running the denoiser first improves accuracy of all downstream stages.

```
DenoiserProvider (interface)
├── name: string                             # Provider name (e.g., "sherpa_onnx", "rnnoise")
├── process(audio_frame: AudioFrame, stream: string) → AudioFrame
│       # Process one frame of `stream`, return cleaned frame
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

Implementations SHOULD provide at least one built-in denoiser (e.g., sherpa-onnx).

#### 12.3.3 Resampler

The resampler normalizes audio format at pipeline entry (inbound) and exit
(outbound). All pipeline stages operate on a consistent internal format,
eliminating format mismatches between transport, STT, TTS, and VAD.

```
ResamplerConfig
├── internal_sample_rate: int = 16000       # Pipeline-internal sample rate (Hz)
├── internal_channels: int = 1              # Pipeline-internal channel count (mono)
├── internal_sample_width: int = 2          # Pipeline-internal bytes per sample (16-bit)
└── codec: string | null                    # Codec hint for transport negotiation (e.g., "opus", "pcm")
```

**Behavior:**

- **Inbound:** After receiving a raw AudioFrame from transport, the resampler
  converts it to the internal format before passing to downstream stages.
- **Outbound:** After postprocessors, the resampler converts from internal format
  to the transport's expected format (sample rate, channels, codec).

The resampler MUST preserve `AudioFrame.timestamp_ms` accurately through
conversion. The resampler MUST add `metadata.original_sample_rate` and
`metadata.original_channels` to the frame for audit purposes.

Implementations SHOULD use high-quality resampling (e.g., libsamplerate,
sox-quality) to avoid introducing artifacts that degrade VAD and STT accuracy.

When no resampler is configured, all pipeline stages MUST accept the transport's
native format. Implementations SHOULD log a warning if the transport format
differs from the expected format of downstream stages.

#### 12.3.4 Echo Canceller (AEC)

The echo canceller removes acoustic echo — the bot's own TTS audio picked up
by the user's microphone. Without AEC, the VAD triggers on the bot's speech,
causing false speech detections and feedback loops.

```
AECProvider (interface)
├── name: string                             # Provider name (e.g., "speex_aec", "webrtc_aec3")
├── process(audio_frame: AudioFrame, stream: string) → AudioFrame
│       # Remove echo from `stream`'s inbound frame using its buffered reference
├── feed_reference(audio_frame: AudioFrame, stream: string) → void
│       # Feed `stream`'s outbound audio as its echo reference
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

**Integration with outbound path:**

The AEC requires a reference signal — the audio being played back to the user.
The AEC provider manages the reference internally via `feed_reference()`, so
`process()` operates on the inbound frame alone — this avoids callers having to
track and pass the reference signal. The bidirectional dependency is:

```
Reference: Speaker output → AEC.feed_reference(frame, stream)
Inbound:   Transport → [resampler] → AEC.process(frame, stream) → [AGC] → ...
```

Both calls MUST carry the same stream key. Each stream owns its echo canceller,
so an unkeyed reference could not reach the right one; in a conference every
lane hears a different mix, and feeding one lane's output into another lane's
canceller models an echo that never occurred.

**Reference feeding strategies:**

Implementations MUST call `AECProvider.feed_reference()` with the outbound audio
and the stream key that audio is being played to.
The point at which this call is made has a critical impact on echo cancellation
quality. Two strategies are defined:

1. **Transport-level feeding (RECOMMENDED for local hardware).** When the
   transport has direct access to the playback hardware (e.g., a local speaker
   via PortAudio), the transport SHOULD feed reference audio from within the
   speaker output callback — at the exact moment audio is written to the DAC.
   This provides the best time alignment between reference and echo. The
   `VoiceBackend` accepts an optional `AECProvider` and feeds reference
   internally; the pipeline's outbound path does not call `feed_reference()`.

2. **Pipeline-level feeding (for network transports).** When the transport sends
   audio over a network (WebRTC, SIP, WebSocket), the pipeline's outbound path
   calls `AECProvider.feed_reference()` after postprocessors and recorder:

   ```
   TTS → [postprocessors] → [recorder] → AEC.feed_reference(frame, stream) → [resampler] → Transport
   ```

   In this scenario the remote client's playback latency is handled by the AEC
   provider's internal ring buffer (e.g., SpeexDSP's split API).

Implementations MUST NOT feed reference from both levels simultaneously for the
same AEC instance — this would double-feed and corrupt the adaptive filter.

**Important considerations:**

- AEC effectiveness depends on accurate time alignment between the reference
  signal and the echo in the inbound stream. Transport-level feeding provides
  the best alignment for local hardware; pipeline-level feeding is sufficient
  for network transports where latency is inherently variable.
- The reference and capture (inbound) audio MUST have the same sample rate and
  frame size. When the transport uses different sample rates for input and
  output, the implementation MUST either resample the reference to match the
  inbound rate, or require matching rates when AEC is enabled.
- When the VoiceBackend declares `NATIVE_AEC` capability, the pipeline MUST skip
  the AEC stage automatically, even if an AECProvider is configured, to avoid
  double processing.
- AEC MUST run before the denoiser — echo is a known signal to subtract, not
  random noise to filter.

AEC SHOULD add `metadata.echo_cancelled = true` to processed frames for
observability.

#### 12.3.5 Automatic Gain Control (AGC)

The AGC normalizes input audio volume to a consistent level. Users on different
devices, at different distances from their microphone, or in different
environments produce widely varying audio levels. AGC ensures that the VAD
and STT receive audio at a predictable amplitude.

```
AGCProvider (interface)
├── name: string                             # Provider name (e.g., "webrtc_agc", "simple_agc")
├── process(audio_frame: AudioFrame, stream: string) → AudioFrame
│       # Apply gain control to `stream`, return normalized frame
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

```
AGCConfig
├── target_level_dbfs: float = -3.0         # Target audio level in dBFS
├── max_gain_db: float = 30.0               # Maximum gain to apply
├── attack_ms: float = 10.0                 # Attack time (how fast gain increases)
└── release_ms: float = 100.0               # Release time (how fast gain decreases)
```

The AGC algorithm is well-standardized. Implementations MUST provide at least
one built-in AGCProvider (e.g., based on WebRTC's AGC). Custom AGCProvider
implementations MAY be registered for specialized requirements.

AGC MUST run after AEC (to avoid amplifying echo) and before the denoiser
(to give the denoiser consistent input levels).

When the VoiceBackend declares `NATIVE_AGC` capability, the pipeline MUST skip
the AGC stage automatically, even if an AGCProvider is configured.

AGC SHOULD add `metadata.gain_applied_db` to processed frames for observability.

#### 12.3.6 DTMF Detector

The DTMF detector identifies telephone keypad tones (0-9, *, #, A-D) in the
audio stream. This is essential for IVR (Interactive Voice Response) scenarios,
call transfers, and PSTN/SIP integrations where users interact via keypad.

```
DTMFDetector (interface)
├── name: string                             # Provider name (e.g., "goertzel", "webrtc_dtmf")
├── process(audio_frame: AudioFrame, stream: string) → DTMFEvent | null
│       # Detect DTMF tone, return event if detected, null otherwise
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

```
DTMFEvent
├── digit: string                            # Detected digit ("0"-"9", "*", "#", "A"-"D")
├── duration_ms: float                       # Tone duration
└── confidence: float | null                 # Detection confidence [0.0, 1.0]
```

**Critical: DTMF runs in parallel, not in series.**

DTMF tones are sinusoidal signals that would be destroyed or distorted by the
denoiser, AGC, or AEC. The DTMF detector MUST process audio from the resampled
stream *before* AEC/AGC/denoiser stages, in parallel with the main pipeline:

```
Transport → [Resampler] → ┬─→ [AEC] → [AGC] → [Denoiser] → [VAD] → ...
                           │
                           └─→ [DTMF Detector] (parallel)
```

Implementations MAY alternatively run DTMF detection on the raw (pre-resampler)
stream if the detector supports the transport's native format, since the Goertzel
algorithm does not require a specific sample rate.

When a DTMF tone is detected, the framework MUST fire the ON_DTMF hook
(Section 9.2). Implementations MAY optionally suppress the DTMF audio from the
main pipeline to prevent the tone from being transcribed as speech.

**Outbound DTMF.** VoiceBackend exposes `send_dtmf(session, digit, duration_ms)`
for sending DTMF digits to the remote party via RFC 4733 telephone-events. This
is essential for AI agents navigating IVR menus, entering PINs, or interacting
with phone systems programmatically. Valid digits are `'0'-'9'`, `'*'`, `'#'`,
and `'A'-'D'`. The default duration is 160 ms. Only backends with the
`DTMF_SIGNALING` capability support this method; others MUST raise
`NotImplementedError`. VoiceChannel provides the public entry point with input
validation (digit set, duration range 1–10000 ms, session state).

#### 12.3.7 Audio Recorder

The audio recorder captures bidirectional audio for compliance, audit, quality
assurance, and training purposes. In regulated industries (financial services,
healthcare), call recording is often mandatory.

**Scope.** This interface records a VoiceSession, and everything about it says
so: the handle names a session, and both the mode and the channel mode are
expressed in terms of two directions. That is the shape of a call, not of a
meeting. Recording a room's many participants is Section 12.11, and a
conference records through that (Section 12.10.8) rather than through this.

```
AudioRecorder (interface)
├── name: string                             # Recorder name
├── start(session: VoiceSession, config: RecordingConfig) → RecordingHandle
│       # Start recording for a voice session
├── record_inbound(handle: RecordingHandle, frame: AudioFrame) → void
│       # Record an inbound (user) audio frame
├── record_outbound(handle: RecordingHandle, frame: AudioFrame) → void
│       # Record an outbound (bot/TTS) audio frame
├── stop(handle: RecordingHandle) → RecordingResult
│       # Stop recording, finalize file(s)
└── close() → void
        # Release resources
```

```
RecordingHandle
├── id: string                               # Unique handle identifier
├── session_id: string                       # Associated VoiceSession
├── started_at: datetime                     # When recording started
└── state: string                            # "recording" or "stopped"
```

The `RecordingHandle` is an opaque token returned by `start()` and passed to
all subsequent recorder calls. Implementations MAY extend it with
provider-specific fields.

```
RecordingConfig
├── format: string = "wav"                   # Output format ("wav", "mp3", "ogg", "flac")
├── mode: RecordingMode                      # What to record
├── channels: RecordingChannelMode           # How to mix audio
├── storage: string                          # Storage backend identifier (integrator-defined)
├── retention_days: int | null               # Auto-delete after N days (null = indefinite)
└── metadata: map<string, any>               # Recording metadata (room_id, participant_id, etc.)
```

The `storage` field is an integrator-defined identifier resolved by the
implementation at runtime — similar to how provider names reference registered
providers. Implementations MUST document which storage backends they support
(e.g., "local", "s3", "gcs") and MUST raise a configuration error if an
unknown identifier is provided.

**RecordingMode** enumeration:

| Value | Description |
|---|---|
| INBOUND_ONLY | Record user audio only |
| OUTBOUND_ONLY | Record bot/TTS audio only |
| BOTH | Record both directions |

**RecordingChannelMode** enumeration:

| Value | Description |
|---|---|
| MIXED | Single file, both directions mixed |
| STEREO | Single file, user on left channel, bot on right channel |
| SEPARATE | Two separate files, one per direction |

```
RecordingResult
├── recording_id: string                     # Unique recording identifier
├── urls: list<string>                       # Storage URLs for recording file(s)
├── duration_seconds: float                  # Total recording duration
├── format: string                           # Output format used
├── mode: RecordingChannelMode               # Channel mode used
└── metadata: map<string, any>               # Recording metadata
```

**Recording position in the pipeline:**

The recorder captures audio at two points:
- **Inbound:** After resampler (raw user audio, consistent format) — before any
  processing, to preserve the original signal for compliance.
- **Outbound:** After postprocessors (final bot audio) — what the user actually
  heard.

Implementations MAY provide a configuration option to record at different
pipeline positions (e.g., after denoiser for cleaner recordings).

```
Inbound:  Transport → [Resampler] → recorder.record_inbound() → [AEC] → [AGC] → ...
Outbound: [PostProcessors] → recorder.record_outbound() → [Resampler] → Transport
```

When recording starts, the framework SHOULD fire ON_RECORDING_STARTED hook.
When recording stops, the framework SHOULD fire ON_RECORDING_STOPPED hook with
the RecordingResult.

#### 12.3.8 VAD Provider

The VAD provider detects speech activity in audio frames and emits events that
drive the voice pipeline. VAD events are the source for the ON_SPEECH_START,
ON_SPEECH_END, ON_VAD_SILENCE, and ON_VAD_AUDIO_LEVEL hooks defined in
Section 9.2.

**Note:** VAD is OPTIONAL in the `AudioPipelineConfig` schema to support
speech-to-speech architectures where the AI provider handles turn detection.
However, for Voice Channels (STT/TTS pipeline), VAD is effectively required —
without it, the pipeline has no way to detect speech boundaries for STT.

```
VADProvider (interface)
├── name: string                             # Provider name (e.g., "silero", "ten_vad", "webrtc")
├── process(audio_frame: AudioFrame, stream: string) → VADEvent | null
│       # Process a frame, return event if state changed, null otherwise
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

```
VADEvent
├── type: VADEventType                       # What was detected
├── audio_bytes: bytes | null                # Captured speech audio (on SPEECH_END)
├── confidence: float | null                 # Detection confidence [0.0, 1.0]
├── duration_ms: float | null                # Duration of speech or silence
└── level_db: float | null                   # Audio level in dB (on AUDIO_LEVEL)
```

**VADEventType** enumeration:

| Value | Description |
|---|---|
| SPEECH_START | Speech activity began |
| SPEECH_END | Speech activity ended — `audio_bytes` contains captured segment |
| SILENCE | Silence duration exceeded `silence_threshold_ms` |
| AUDIO_LEVEL | Periodic audio level report |

**Relationship with speech-to-speech providers:**

When using a speech-to-speech provider (Section 12.4), the provider manages its
own turn detection internally. The audio pipeline acts as a **preprocessor** —
denoising audio before it reaches the provider and running diarization to
identify speakers. VAD MAY be configured for observational purposes (activity
logging, audio level monitoring for UI) but does NOT control turn-taking — that
responsibility belongs to the provider.

#### 12.3.9 Diarization Provider

The diarization provider identifies which speaker produced each audio segment.
This is particularly relevant in multi-participant voice rooms or when multiple
speakers share a single audio stream (e.g., speakerphone).

```
DiarizationProvider (interface)
├── name: string                             # Provider name
├── process(audio_frame: AudioFrame, stream: string) → DiarizationResult | null
│       # Identify speaker, return result if determined, null otherwise
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

```
DiarizationResult
├── speaker_id: string                       # Identified speaker label
├── confidence: float | null                 # Identification confidence [0.0, 1.0]
└── is_new_speaker: bool                     # True if this speaker was not previously seen
```

When diarization detects a speaker change, the framework MUST fire the
ON_SPEAKER_CHANGE hook (Section 9.2).

**Speaker-to-Participant mapping:** `DiarizationResult.speaker_id` is a
provider-assigned label (e.g., "speaker_0", "speaker_1"), not a RoomKit
`Participant.id`. Mapping diarization labels to participants is an
integrator concern — typically resolved via the ON_SPEAKER_CHANGE hook,
where the integrator can match speaker labels to known participants using
voice enrollment, channel metadata, or heuristics (e.g., the participant
who owns the voice channel is always "speaker_0").

#### 12.3.10 Audio Post-Processor

Audio post-processors form an ordered chain on the outbound path. Each processor
receives an audio frame and returns a (possibly modified) frame. Common use cases
include volume normalization, audio watermarking (for compliance), and recording.

```
AudioPostProcessor (interface)
├── name: string                             # Processor name
├── process(audio_frame: AudioFrame, stream: string) → AudioFrame
│       # Process `stream`'s outbound audio frame
├── reset(stream: string) → void
│       # Drop this stream's state when the stream ends
└── close() → void
        # Release resources
```

Multiple post-processors are executed in the order they appear in the
`postprocessors` list. Each processor receives the output of the previous one.

#### 12.3.11 Audio Frame

The common data structure passed through the pipeline:

```
AudioFrame
├── data: bytes                              # Raw audio samples
├── sample_rate: int                         # Sample rate in Hz (e.g., 16000, 48000)
├── channels: int                            # Number of audio channels (1 = mono, 2 = stereo)
├── sample_width: int                        # Bytes per sample (2 = 16-bit)
├── timestamp_ms: float | null               # Frame timestamp relative to session start
└── metadata: map<string, any>               # Pipeline metadata (accumulated by stages)
```

**AudioChunk** is a distinct type, not an alias:

```
AudioChunk
├── data: bytes                              # Audio samples
├── sample_rate: int                         # Sample rate in Hz
├── channels: int                            # Number of audio channels
├── format: string                           # Sample encoding (default "pcm_s16le")
├── timestamp_ms: int | null                 # Chunk timestamp
└── is_final: bool                           # Last chunk of the stream
```

The two exist because inbound and outbound audio are not the same problem.
Inbound audio is a stream to be *analysed*: an AudioFrame is a standalone unit
that accumulates stage annotations in `metadata` as it descends the pipeline —
the VAD records that speech was present, diarization records which speaker —
and it is validated on construction, because a misaligned frame breaks the
stages that consume it.

Outbound audio is a stream to be *finished*: TTS emits a sequence of chunks and
must be able to say which one is last, so the transport knows when an utterance
has ended, can drain its buffers, and can hand control back to barge-in
handling. `is_final` carries that, and AudioFrame has no equivalent because a
live microphone has no last frame. Nothing annotates an outbound chunk, so it
carries no metadata and no validation.

Implementations MUST NOT merge the two. Doing so means either dragging
`is_final` and `format` into the pipeline type, where they are meaningless, or
losing stream termination on the TTS path.

Conversion is one-directional and lossy by design: an AudioFrame becomes an
AudioChunk by dropping its pipeline metadata; the reverse requires validating
alignment and starting a fresh annotation record.

#### 12.3.12 Turn Detector

The turn detector determines whether the user has finished their conversational
turn. This is distinct from VAD, which detects acoustic silence. A user may
pause mid-sentence (VAD triggers silence) but not be done speaking. Conversely,
a user may finish a question without a long pause.

**Note:** Unlike the frame-level stages above (denoiser, AEC, AGC, VAD), the
turn detector operates on **transcripts** (text from STT), not audio frames.
It does not implement `process(AudioFrame)`. It sits between STT output and the
room event pipeline, making it a post-STT stage rather than an audio-frame
processor. It is included in the audio pipeline configuration for convenience,
as it is integral to the voice processing flow.

```
TurnDetector (interface)
├── name: string                             # Detector name (e.g., "llm_turn", "heuristic", "hybrid")
├── evaluate(context: TurnContext) → TurnDecision
│       # Evaluate whether the user's turn is complete
├── reset() → void
│       # Reset internal state
└── close() → void
        # Release resources
```

```
TurnContext
├── transcript: string                       # Current accumulated transcript (from STT)
├── is_final: bool                           # Whether STT transcript is final
├── silence_duration_ms: float               # Current silence duration (from VAD)
├── speech_duration_ms: float                # Duration of the speech segment
├── conversation_history: list<TurnEntry> | null  # Recent turns for context
└── metadata: map<string, any>               # Additional context

TurnEntry
├── role: string                             # "user" or "assistant"
└── text: string                             # Transcript text of the turn
```

```
TurnDecision
├── is_complete: bool                        # Whether the turn is considered complete
├── confidence: float                        # Decision confidence [0.0, 1.0]
├── reason: string | null                    # Why (e.g., "question_mark", "long_pause", "semantic_complete")
└── suggested_wait_ms: float | null          # If not complete, how long to wait before re-evaluating
```

**Turn detection modes:**

| Mode | Description | Latency | Accuracy |
|---|---|---|---|
| VAD-only | Use VAD silence threshold (current behavior) | Low | Low — triggers on pauses |
| Heuristic | Punctuation, sentence structure, silence combo | Low | Medium |
| LLM-based | Send transcript to fast LLM for completion check | Medium | High |
| Hybrid | VAD for fast path, LLM for ambiguous cases | Adaptive | High |

**Integration point:**

The turn detector sits between STT and the room event pipeline. It replaces the
simple "VAD silence → send to STT → route event" flow with a more nuanced path:

```
VAD SPEECH_END → STT transcribes → TurnDetector.evaluate(context)
                                          │
                                    is_complete?
                                    ├── YES → Create RoomEvent, route normally
                                    └── NO  → Wait (suggested_wait_ms), accumulate
                                              next speech, re-evaluate
```

When no TurnDetector is configured, the pipeline falls back to VAD-only behavior
(current default).

The turn detector MUST NOT add more than 200ms latency in the fast path. For
LLM-based detection, implementations SHOULD use a small, fast model or cache
common patterns.

#### 12.3.13 Interruption Strategy

When the user speaks while the bot is responding (barge-in), the framework needs
a configurable strategy to handle the interruption. Not all speech during bot
playback is a genuine interruption — backchannels ("mmhmm", "ok", "yes") are
acknowledgments, not requests to stop.

```
InterruptionConfig
├── strategy: InterruptionStrategy = CONFIRMED  # How to handle barge-in
├── min_speech_ms: int = 300                 # Minimum user speech duration to trigger interruption
├── backchannel_detector: BackchannelDetector | null  # OPTIONAL backchannel filter
├── flush_partial_tts: bool = true           # Whether to discard unplayed TTS audio on interrupt
└── keep_partial_transcript: bool = true     # Whether to store bot's partial response in timeline
```

**InterruptionStrategy** enumeration:

| Value | Description |
|---|---|
| IMMEDIATE | Cancel TTS as soon as VAD detects speech (v1 behavior). Fast but aggressive. |
| CONFIRMED | Wait for `min_speech_ms` of sustained speech before cancelling. Tolerates brief sounds. Default. |
| SEMANTIC | Use backchannel detector to decide — only interrupt on non-backchannel speech. Most natural. |
| DISABLED | Never interrupt — user speech is queued until bot finishes. For non-interactive playback. |

**BackchannelDetector interface:**

```
BackchannelDetector (interface)
├── name: string                             # Detector name
├── classify(context: BackchannelContext) → BackchannelDecision
│       # Classify whether speech is a backchannel or genuine interruption
├── reset() → void
│       # Reset internal state (e.g., on session start)
└── close() → void
        # Release resources
```

```
BackchannelContext
├── audio_bytes: bytes | null                # Short audio segment (if available)
├── transcript: string | null                # Partial transcript of the speech (if STT fast enough)
├── speech_duration_ms: float                # How long the user has been speaking
├── bot_speech_progress: float               # How far into the bot's response (0.0 to 1.0)
└── metadata: map<string, any>               # Additional context
```

```
BackchannelDecision
├── is_backchannel: bool                     # True = acknowledgment, False = real interruption
├── confidence: float                        # Decision confidence [0.0, 1.0]
└── label: string | null                     # Classification label (e.g., "agreement", "filler", "question")
```

**Timing constraint:** In the SEMANTIC strategy, the `BackchannelContext.transcript`
field may be null or incomplete if STT has not yet produced a result for the
speech segment. In practice, the classifier will often operate on `audio_bytes`
and `speech_duration_ms` alone, falling back to transcript-based classification
only when streaming STT provides partial results fast enough. Implementations
SHOULD design backchannel detectors to work with audio features alone and treat
transcript availability as a bonus signal.

**Interruption flow:**

```
User speaks during TTS playback
      │
      ▼
VoiceBackend fires on_barge_in
      │
      ▼
Check InterruptionStrategy:
      │
      ├── IMMEDIATE → Cancel TTS immediately
      │
      ├── CONFIRMED → Start timer
      │   ├── Speech continues > min_speech_ms → Cancel TTS
      │   └── Speech stops before threshold → Ignore, resume TTS
      │
      ├── SEMANTIC → Run BackchannelDetector
      │   ├── is_backchannel = true → Ignore, resume TTS
      │   │   └── Fire ON_BACKCHANNEL hook (async)
      │   └── is_backchannel = false → Cancel TTS
      │       └── Fire ON_BARGE_IN hook (async)
      │
      └── DISABLED → Ignore speech, queue for after TTS completes
```

**When TTS is cancelled:**

1. If `flush_partial_tts = true`: discard all unplayed audio in the TTS buffer.
2. If `keep_partial_transcript = true`: store the bot's partial response in the
   timeline with `metadata.interrupted = true` and `metadata.played_percentage`.
3. Process the user's speech normally through the inbound pipeline.

#### 12.3.14 Pipeline Execution Flow

**Session start (once per VoiceSession):**

```
1. VoiceSession transitions to ACTIVE
2. Call reset() on all configured pipeline stages (in pipeline order)
3. Backend fires on_session_ready callback when audio path is live
   └── VoiceChannel fires ON_SESSION_STARTED hook (dual-signal: requires
       both bind_session() and backend ready, in either order)
4. IF recorder configured:
   ├── handle = recorder.start(session, recording_config)
   └── Fire ON_RECORDING_STARTED hook
```

**Session end (once per VoiceSession):**

```
1. VoiceSession transitions to ENDED
2. IF recorder configured AND recording active:
   ├── result = recorder.stop(handle)
   └── Fire ON_RECORDING_STOPPED hook with RecordingResult
3. Call close() on pipeline stages only if the channel is being destroyed
   (not on session end — stages are reused across sessions)
```

**Inbound flow (per audio frame):**

```
1. Transport emits raw AudioFrame for stream `stream` (session id, or lane id
   in a conference)
2. IF resampler configured:
   └── frame = resample(frame, internal_format)
       └── frame.metadata.original_sample_rate = original_rate
3. IF recorder configured:
   └── recorder.record_inbound(handle, frame)
4. IF dtmf configured (PARALLEL with steps 5-9):
   ├── dtmf_event = dtmf.process(frame, stream)
   └── IF dtmf_event is not null:
       └── Fire ON_DTMF hook
5. IF aec configured AND NOT backend.NATIVE_AEC:
   └── frame = aec.process(frame, stream)
6. IF agc configured AND NOT backend.NATIVE_AGC:
   └── frame = agc.process(frame, stream)
7. IF denoiser configured:
   └── frame = denoiser.process(frame, stream)
8. IF vad configured:
   ├── vad_event = vad.process(frame, stream)
   └── IF vad_event is not null:
       ├── Fire corresponding hook (ON_SPEECH_START, ON_SPEECH_END, etc.)
       └── IF vad_event.type == SPEECH_END:
           ├── STT transcribes audio_bytes → TranscriptionResult
           ├── Fire ON_TRANSCRIPTION hook (can modify transcript)
           └── IF turn_detector configured:
               ├── decision = turn_detector.evaluate(context)
               ├── IF decision.is_complete:
               │   ├── Fire ON_TURN_COMPLETE hook
               │   └── Create RoomEvent, route to Room
               └── ELSE:
                   ├── Fire ON_TURN_INCOMPLETE hook
                   └── Accumulate, wait for next speech segment
           └── ELSE (no turn detector):
               └── Create RoomEvent, route to Room (v1 behavior)
9. IF diarization configured:
   ├── result = diarization.process(frame, stream)
   └── IF result.is_new_speaker:
       └── Fire ON_SPEAKER_CHANGE hook

10. WHEN the stream ends:
   └── FOR EACH configured stage: stage.reset(stream)
       (Releases that speaker's state. Skipping it leaks one stream's buffers —
        and native memory for SDK-backed stages — per speaker the room ever had.)
```

**Outbound flow (per audio frame / chunk):**

```
1. TTS emits AudioChunk stream (variable-size); speech-to-speech emits AudioFrame
   (Stages that require fixed-size AudioFrames MUST buffer and re-chunk internally)
2. FOR EACH postprocessor in order:
   └── frame = postprocessor.process(frame, stream)
3. IF recorder configured:
   └── recorder.record_outbound(handle, frame)
4. IF aec configured AND transport does NOT handle AEC reference feeding:
   └── aec.feed_reference(frame, stream)
   (When the transport feeds reference from its speaker output callback — e.g.,
    local audio hardware — the pipeline MUST skip this step to avoid double-feeding.
    See Section 12.3.4 for reference feeding strategies.)
5. IF resampler configured:
   └── frame = resample(frame, transport_format)
6. Transport sends processed frame to client
   (For local hardware transports, the speaker output callback feeds
    aec.feed_reference() here with that stream's key, time-aligned with actual
    playback.)
```

#### 12.3.15 Pipeline Debug Taps

Pipeline Debug Taps provide lightweight diagnostic audio capture at every
stage boundary in the processing pipeline. Unlike the production AudioRecorder
(Section 12.3.7) — which captures raw audio for compliance and audit — debug
taps capture audio at every processing stage, allowing developers to compare
the signal before and after each transformation.

This is invaluable for debugging audio quality issues: "Is the denoiser
removing too much signal?", "What does the VAD actually hear?", "Is AEC
effective?". Without debug taps, these questions require custom instrumentation.

**Configuration:**

```
PipelineDebugTaps
├── output_dir: string                      # Directory for debug WAV files (REQUIRED)
├── stages: list<string> | "all" = "all"    # Which stages to capture
├── session_scoped: bool = true             # Prefix files with session ID + timestamp
└── sample_rate: int | null                 # Override sample rate for output files (null = use internal format)
```

When `stages` is `"all"`, taps are inserted at every stage boundary. When a
list is provided, only the named stages are captured. Valid stage names:

| Stage name | Capture point | What it reveals |
|---|---|---|
| `raw` | After resampler, before AEC | What the pipeline receives from transport |
| `post_aec` | After AEC | Echo cancellation effectiveness |
| `post_agc` | After AGC | Volume normalization result |
| `post_denoiser` | After denoiser | Noise reduction quality — what VAD sees |
| `post_vad_speech` | On SPEECH_END event | Accumulated speech audio bytes sent to STT |
| `outbound_raw` | Before postprocessors | TTS output before processing |
| `outbound_final` | After postprocessors, before resampler | Final audio sent to transport |

**Output files:**

Files are named with a numeric prefix reflecting pipeline order, making it
easy to compare stages side by side in any audio editor:

```
{output_dir}/
  {session_id}_01_raw.wav
  {session_id}_02_post_aec.wav
  {session_id}_03_post_agc.wav
  {session_id}_04_post_denoiser.wav
  {session_id}_05_post_vad_speech.wav
  {session_id}_06_outbound_raw.wav
  {session_id}_07_outbound_final.wav
```

When `session_scoped` is false, files omit the session prefix (useful for
quick single-session debugging).

Files are opened lazily on first write and closed on session end. Each file
uses the pipeline's internal AudioFormat (from the AudioPipelineContract),
unless `sample_rate` is overridden.

**Integration with pipeline config:**

```
AudioPipelineConfig
├── ... (existing fields)
└── debug_taps: PipelineDebugTaps | null    # OPTIONAL diagnostic capture (default: null)
```

**Behavior:**

- Debug taps MUST NOT modify audio frames — they are read-only observers.
  Tap processing is a non-blocking copy of the frame data.
- Tap writes SHOULD be non-blocking. Implementations MAY buffer frames and
  flush to disk asynchronously to avoid adding latency to the audio pipeline.
- When `debug_taps` is null, the pipeline MUST NOT perform any tap-related
  processing (zero overhead when disabled).
- The `post_vad_speech` tap captures the `vad_event.audio_bytes` blob — the
  accumulated speech segment that would be sent to STT. This is written as a
  separate WAV file per speech segment (appending a segment counter:
  `{session_id}_05_post_vad_speech_001.wav`, etc.).
- Implementations SHOULD log a warning at startup when debug taps are enabled,
  as the disk I/O and storage cost is not intended for production.

**Session lifecycle:**

```
1. On session_active:
   ├── Create output_dir if it does not exist
   └── Initialize per-stage WAV writers (lazily, on first frame)

2. On each inbound/outbound frame:
   └── IF stage is in configured stages:
       └── writer.write(frame.data)  # non-blocking copy

3. On SPEECH_END event (for post_vad_speech stage):
   └── Write audio_bytes to a new segment file

4. On session_ended:
   ├── Flush and close all WAV writers
   └── Finalize WAV headers with correct data sizes
```

**Relationship to AudioRecorder:**

Pipeline Debug Taps and AudioRecorder serve different purposes and MAY be
used simultaneously:

| | AudioRecorder | PipelineDebugTaps |
|---|---|---|
| Purpose | Compliance, audit, QA | Development and debugging |
| Capture points | Raw inbound + final outbound | Every stage boundary |
| Production use | Yes | No (SHOULD warn) |
| Modifies frames | No | No |
| Output | Single/stereo recording file | Multiple per-stage WAV files |
| Configuration | `recorder` + `recording_config` | `debug_taps` |

### 12.4 Realtime Voice Channel (Speech-to-Speech)

The Realtime Voice Channel wraps speech-to-speech APIs (e.g., OpenAI Realtime,
Gemini Live) that handle audio processing natively, bypassing STT/TTS.

**RealtimeVoiceProvider interface:**

```
RealtimeVoiceProvider (interface)
├── connect(session, system_prompt, voice, tools, temperature) → void
├── disconnect(session) → void
├── send_audio(session, audio_chunk) → void
├── inject_text(session, text, role) → void  # Insert text into conversation context
├── submit_tool_result(session, call_id, result) → void  # Return tool result to provider
├── interrupt(session) → void               # Signal user interruption to provider
├── close() → void                          # Release all resources
│
│   # Callback registration:
├── on_audio(callback) → void               # AI-generated audio
├── on_transcription(callback) → void       # User/AI speech transcript
├── on_speech_start(callback) → void
├── on_speech_end(callback) → void
├── on_tool_call(callback) → void           # AI requests a tool call
├── on_response_start(callback) → void
├── on_response_end(callback) → void
└── on_error(callback) → void
```

**RealtimeVoiceProvider callback → hook mapping:**

| Provider Callback | Hook Fired | Notes |
|---|---|---|
| `on_audio` | — | Audio frames routed to transport; no hook (too high frequency) |
| `on_transcription` | ON_TRANSCRIPTION | User and AI transcripts emitted as RoomEvents |
| `on_speech_start` | ON_SPEECH_START | Provider-detected speech start |
| `on_speech_end` | ON_SPEECH_END | Provider-detected speech end |
| `on_tool_call` | ON_REALTIME_TOOL_CALL | Tool execution request from AI |
| `on_response_start` | — | Internal lifecycle; no hook (use ON_SPEECH_START for AI speech) |
| `on_response_end` | — | Internal lifecycle; no hook (use AFTER_BROADCAST for response tracking) |
| `on_error` | ON_ERROR | Mapped to the global ON_ERROR hook (Section 9.2) |

**Note:** `on_response_start` and `on_response_end` are internal provider
lifecycle callbacks used for audio routing and session bookkeeping. They do not
map to hooks because they don't represent events the integrator needs to act on.
Integrators who need response-level tracking SHOULD use AFTER_BROADCAST on the
transcription events emitted by the provider.

**Text injection** refers to programmatically inserting text into a realtime
session's conversation context (e.g., system messages, tool results, or context
updates) rather than sending audio. This is provider-specific: for OpenAI
Realtime, this maps to `conversation.item.create` with text content; for Gemini
Live, this maps to injecting text turns. The ON_REALTIME_TEXT_INJECTED hook fires
after such an injection, allowing integrators to log or react to context changes.

**RealtimeAudioTransport interface:**

```
RealtimeAudioTransport (interface)
├── name: string                             # Transport name (e.g., "websocket", "webrtc")
├── accept(session, connection) → void
├── send_audio(session, audio_chunk) → void
├── send_message(session, message) → void   # Send control/data message to client
├── on_audio_received(callback) → void      # Push-based audio reception
├── on_client_disconnected(callback) → void
├── set_trace_emitter(emitter | null) → void  # Set callback for emitting ProtocolTraces
├── disconnect(session) → void              # Disconnect a client session
└── close() → void                          # Release resources
```

Audio reception uses a push-based model via `on_audio_received(callback)` rather
than a pull-based async iterator. This aligns with the transport pattern used by
`VoiceBackend` and avoids the complexity of managing iterator lifecycles across
session boundaries.

**Session lifecycle:**

```
1. Client connects → RealtimeAudioTransport.accept()
2. start_session(room_id, participant_id, connection, metadata)
   ├── Create RealtimeSession
   ├── Connect provider with system_prompt, voice, tools
   └── Wire callbacks: transport audio → provider, provider audio → transport
3. Audio flows bidirectionally: Client ↔ Transport ↔ Provider
4. Transcriptions emitted as RoomEvents (if configured)
5. Tool calls handled via:
   ├── Async tool handler function (if provided)
   └── ON_REALTIME_TOOL_CALL hook (fallback)
6. end_session() → disconnect provider and transport
```

**Audio pipeline in speech-to-speech mode:**

When using a speech-to-speech provider, the audio pipeline (Section 12.3) MAY be
configured as an optional preprocessor. In this mode the pipeline sits between
the transport and the provider:

```
Client → Transport → [Resampler] → [AEC] → [AGC] → [Denoiser] → [Diarization] → Provider
```

Typical use cases:

- **Resampling** — normalize format for the provider's expected input
- **AEC** — prevent the provider from hearing its own output
- **AGC** — consistent volume for the provider's speech detection
- **Denoising** — cleaner audio improves AI recognition accuracy
- **Diarization** — identify which speaker is talking in multi-party calls
- **Audio level monitoring** (via optional VAD) — for UI indicators
- **Activity logging and metrics** — for observability

VAD is OPTIONAL in this mode. When configured, it runs purely for observation —
it does NOT control when the speech-to-speech provider responds. Turn-taking is
fully managed by the provider.

The `RealtimeVoiceChannel` accepts an `AudioPipelineConfig` in the same way as
`VoiceChannel`. When a pipeline is configured, inbound audio frames are processed
through the pipeline before being forwarded to the provider.

### 12.5 Voice Hooks

Voice-specific hooks allow integrators to customize the voice pipeline:

| Hook | Type | Use Case | Source |
|---|---|---|---|
| ON_SPEECH_START | ASYNC | Show "listening" indicator | Audio Pipeline (VAD) |
| ON_SPEECH_END | ASYNC | Log speech duration | Audio Pipeline (VAD) |
| ON_TRANSCRIPTION | SYNC | Fix STT errors, redact content | STT Provider |
| BEFORE_TTS | SYNC | Select voice, modify text | Voice Channel |
| AFTER_TTS | ASYNC | Log synthesis metrics, cache | Voice Channel |
| ON_BARGE_IN | ASYNC | Track interruptions | VoiceBackend (transport) |
| ON_TTS_CANCELLED | ASYNC | Log cancellation reason | Voice Channel |
| ON_PARTIAL_TRANSCRIPTION | ASYNC | Show real-time captions | STT Provider |
| ON_VAD_SILENCE | ASYNC | Trigger silence timeout | Audio Pipeline (VAD) |
| ON_VAD_AUDIO_LEVEL | ASYNC | Audio level visualization | Audio Pipeline (VAD) |
| ON_INPUT_AUDIO_LEVEL | ASYNC | VU meter for mic input | Audio Pipeline |
| ON_OUTPUT_AUDIO_LEVEL | ASYNC | VU meter for speaker output | VoiceBackend |
| ON_SPEAKER_CHANGE | ASYNC | Identify speaker switch | Audio Pipeline (Diarization) |
| ON_DTMF | ASYNC | IVR navigation, call transfer | Audio Pipeline (DTMF Detector) |
| ON_TURN_COMPLETE | ASYNC | Log turn-taking metrics | Audio Pipeline (Turn Detector) |
| ON_TURN_INCOMPLETE | ASYNC | Debug turn detection | Audio Pipeline (Turn Detector) |
| ON_BACKCHANNEL | ASYNC | Track user engagement | Audio Pipeline (Backchannel Detector) |
| ON_SESSION_STARTED | ASYNC | Send greeting, start telemetry | VoiceBackend / Inbound pipeline |
| ON_RECORDING_STARTED | ASYNC | Notify participants of recording | Audio Pipeline (Recorder) / Conference Channel |
| ON_RECORDING_STOPPED | ASYNC | Store recording reference in timeline | Audio Pipeline (Recorder) / Conference Channel |
| ON_REALTIME_TOOL_CALL | SYNC | Execute tool and return result | Realtime Provider |
| ON_REALTIME_TEXT_INJECTED | ASYNC | Log text injections | Realtime Voice Channel |
| ON_PROTOCOL_TRACE | ASYNC | Log/inspect transport protocol traces (SIP, RTP) | Channel (via emit_trace) |
| BEFORE_BRIDGE_AUDIO | SYNC | Filter/modify audio before bridging (mute, gain) | AudioBridge (Section 12.7) |

**Audio level hooks (ON_INPUT_AUDIO_LEVEL, ON_OUTPUT_AUDIO_LEVEL):**

These hooks provide real-time audio level (RMS in dB) for building VU meters and
audio visualizations. Unlike ON_VAD_AUDIO_LEVEL (which requires VAD and includes
speech classification), these fire independently of VAD for all processed audio.

Implementations SHOULD throttle ON_INPUT_AUDIO_LEVEL and ON_OUTPUT_AUDIO_LEVEL
to at most 10 events per second per session (default interval: 100ms). Without
throttling, per-frame firing at typical 20ms frame sizes would produce 50
events/sec per direction, each requiring a context build and store query.

The event payload is an `AudioLevelEvent` containing `session`, `level_db`
(typically -60 to 0 dBFS), and `timestamp`.

### 12.6 Barge-In and Interruption Handling

Barge-in occurs when a user speaks while TTS is playing. The framework supports
configurable interruption strategies (Section 12.3.13 — InterruptionConfig)
ranging from immediate cancellation to semantic backchannel detection.

**Default behavior (CONFIRMED strategy):**

1. The VoiceBackend fires `on_barge_in` callback.
2. The pipeline checks `InterruptionConfig.strategy`:
   - IMMEDIATE: Cancel TTS immediately.
   - CONFIRMED: Wait for `min_speech_ms` of sustained speech.
   - SEMANTIC: Run BackchannelDetector to classify.
   - DISABLED: Ignore, queue speech for after TTS completes.
3. If interruption is confirmed:
   a. Cancel current TTS playback (if backend supports INTERRUPTION).
   b. If `flush_partial_tts = true`: discard unplayed audio buffer.
   c. If `keep_partial_transcript = true`: store partial bot response in timeline
      with `metadata.interrupted = true`.
   d. Fire ON_BARGE_IN hook.
4. If classified as backchannel:
   a. Fire ON_BACKCHANNEL hook.
   b. TTS continues uninterrupted.
5. The user's speech is processed normally through the audio pipeline.

Implementations SHOULD support a configurable `barge_in_threshold_ms` — minimum
TTS playback duration before barge-in detection activates. This prevents
interruption at the very start of a response.

**Relationship between VoiceBackend barge-in and VAD:**

`VoiceBackend.on_barge_in` and VAD are two separate detection systems:

- **`on_barge_in`** is a transport-level signal — the backend detects that the
  client is sending audio while outbound audio is playing. It fires immediately
  and is the entry point for the interruption strategy. Not all backends support
  this (requires `BARGE_IN` capability).
- **VAD** is a pipeline-level signal — it detects speech activity in the audio
  stream regardless of whether TTS is playing. VAD continues to process inbound
  frames during TTS playback.

When both are active during TTS playback:

1. `on_barge_in` fires first (transport-level, lowest latency).
2. The interruption strategy determines whether to act on the barge-in.
3. Meanwhile, VAD processes the same audio through the pipeline normally.
4. If the interruption is confirmed, the voice channel cancels TTS and the VAD's
   speech segment is routed to STT as usual.
5. If the interruption is rejected (backchannel or too short), the VAD speech
   segment is still captured but the pipeline SHOULD discard it (or queue it
   if `InterruptionStrategy = DISABLED`).

When the backend does NOT support `BARGE_IN`, the pipeline MAY use VAD's
`SPEECH_START` event during TTS playback as a fallback barge-in trigger. In this
mode, the VAD effectively replaces the transport-level detection, but with higher
latency (audio must traverse the full inbound pipeline before VAD fires).

### 12.7 Audio Bridging

Audio bridging enables human-to-human voice communication within a room by
forwarding audio frames directly between voice sessions, bypassing the
STT → text → TTS roundtrip. This is essential for use cases like SIP/RTP
phone calls between participants, call center agent bridging, and
multi-party conferencing.

#### 12.7.1 Design Principles

1. **Audio bridging is a parallel path, not a replacement.** Bridge mode adds
   a direct audio forwarding path alongside the existing STT/TTS path.
   STT MAY still run concurrently for transcription, recording, or AI
   monitoring. The two paths are independent.

2. **Audio bypasses the RoomEvent broadcast system.** Real-time audio at 50
   frames/second cannot traverse the async hook pipeline, store, and
   broadcast loop without unacceptable latency. Bridged audio flows directly
   from inbound pipeline output to outbound pipeline input, never becoming a
   RoomEvent.

3. **Pipeline stages still apply.** Inbound audio passes through the full
   pipeline (resampler, AEC, AGC, denoiser) before being forwarded.
   Outbound bridged audio passes through the outbound pipeline (resampler,
   recorder tap, AEC reference feeding) before reaching the transport.

4. **The bridge is a concrete component, not an ABC.** Unlike STT/TTS/VAD
   providers, there are no genuinely different "bridge implementations" to
   swap. Variations (2-party forwarding vs N-party mixing) are configuration
   options on a single `AudioBridge` class.

#### 12.7.2 AudioBridge

```
AudioBridge
├── config: AudioBridgeConfig
├── add_session(session, room_id, backend) → void
│       # Register a session for bridging
├── remove_session(session_id) → void
│       # Unregister a session
├── forward(session, audio_frame) → void
│       # Forward audio from this session to all other sessions in the room
│       # For 2 sessions: direct forwarding
│       # For N>2 sessions: mix audio from all other sessions
└── close() → void
        # Clean up all sessions
```

```
AudioBridgeConfig
├── enabled: bool = true
├── max_participants: int = 10         # Maximum sessions per room
└── mixing_strategy: "forward" | "mix" = "forward"
        # "forward": optimized 2-party direct forwarding (errors if >2)
        # "mix": N-party additive mixing with clipping protection
```

**Session management:** Sessions are added and removed as participants join and
leave the room. The bridge tracks sessions grouped by `room_id`. When a session
is added and the room already has other bridged sessions, audio forwarding
begins immediately.

**Audio forwarding:** When `forward()` is called with an audio frame from
session A, the bridge sends that frame to all other sessions in the same room
via `VoiceBackend.send_audio()`. For the `"forward"` strategy (2-party), this
is a direct send to the single other session. For the `"mix"` strategy
(N-party), the bridge MUST mix audio from all other active sessions and send
each participant a mix of everyone else's audio (excluding their own, to
prevent echo).

**Thread safety:** `forward()` is called from audio callback threads (same
context as `on_audio_received`). All bridge operations MUST be thread-safe.

#### 12.7.3 VoiceChannel Integration

VoiceChannel gains an optional `bridge` parameter:

```python
VoiceChannel(
    "voice",
    backend=sip_backend,
    pipeline=pipeline,
    bridge=True,              # Enable bridging (AudioBridgeConfig defaults)
    # bridge=AudioBridgeConfig(mixing_strategy="mix"),  # Explicit config
    stt=deepgram,             # Optional: transcription alongside bridge
)
```

**Inbound audio flow with bridge enabled:**

```
Backend → on_audio_received → Pipeline inbound chain
    ├──→ AudioBridge.forward()       # Parallel: forward to other sessions
    └──→ VAD → STT (if configured)  # Parallel: transcription path (optional)
```

When bridge mode is enabled and audio exits the inbound pipeline, the
VoiceChannel MUST feed the processed frame to `AudioBridge.forward()` in
addition to the normal VAD/STT path. The bridge path and the STT path
operate in parallel — neither blocks the other.

**Outbound bridged audio flow:**

```
AudioBridge.forward() → Pipeline outbound chain → Backend.send_audio()
    [Recorder tap] → [AEC reference] → [Resampler] → Transport
```

Bridged audio sent to a session MUST pass through the outbound pipeline
before reaching the transport. This ensures recording captures both sides
and AEC reference is fed correctly.

**Session lifecycle:**

- When `bind_session()` is called with bridge enabled, the VoiceChannel
  MUST register the session with the AudioBridge via `add_session()`.
- When `unbind_session()` is called, the VoiceChannel MUST remove the
  session via `remove_session()`.
- The bridge does NOT manage session state transitions — that remains the
  responsibility of VoiceBackend and VoiceChannel.

**Interaction with STT/TTS:**

| Configuration | Behavior |
|---|---|
| `bridge=True, stt=None, tts=None` | Pure audio bridge — human-to-human only |
| `bridge=True, stt=provider` | Bridge + live transcription (for recording, compliance, AI monitoring) |
| `bridge=True, stt=provider, tts=provider` | Bridge + AI can speak into the call via `say()` (TTS audio mixed with bridge audio) |
| `bridge=False` (default) | Current behavior — STT/TTS pipeline only |

When both bridge and TTS are active, TTS audio from AI responses and bridged
audio from other participants are both sent to the session. The bridge does NOT
suppress TTS — both audio streams coexist. If audio mixing is needed (e.g.,
AI speaking while another participant is speaking), the backend handles
concurrent `send_audio()` calls.

#### 12.7.4 Sample Rate Handling

Voice sessions MAY have different sample rates (e.g., SIP at 8kHz, WebRTC at
48kHz). When forwarding audio between sessions with different rates, the
outbound pipeline's resampler MUST convert the audio to the target session's
native rate. Implementations SHOULD track each session's sample rate at
registration time and apply resampling per-target in the outbound path.

#### 12.7.5 N-Party Mixing

For rooms with more than 2 voice sessions, the bridge MUST mix audio so each
participant hears all others but not themselves.

**Mixing algorithm (additive with clipping protection):**

1. For each target session T, collect audio frames from all other sessions.
2. Sum PCM samples (as signed 16-bit integers promoted to 32-bit to prevent
   overflow).
3. Apply soft clipping or normalization to prevent distortion:
   - Simple: clamp to [-32768, 32767]
   - Recommended: apply headroom scaling (e.g., divide by sqrt(N-1))
4. Convert back to 16-bit PCM and forward to session T.

**Silence handling:** If a session has no audio frame available in the current
mixing window, it contributes silence (zero samples). The bridge SHOULD NOT
forward silence-only mixes to save bandwidth.

#### 12.7.6 Hooks

Audio bridging introduces one new hook and reuses existing hooks:

| Hook | Type | Use Case | Source |
|---|---|---|---|
| BEFORE_BRIDGE_AUDIO | SYNC | Filter or modify audio before forwarding (e.g., gain, muting) | AudioBridge |

**BEFORE_BRIDGE_AUDIO** fires for each frame before it is forwarded to other
sessions. The hook receives the audio frame and context (source session,
target room). Returning `HookResult.block()` drops the frame (effectively
muting the speaker for that frame). Returning a modified frame applies the
modification before forwarding.

Existing hooks that fire normally during bridge mode:
- `ON_SPEECH_START`, `ON_SPEECH_END` — VAD still runs on bridged audio
- `ON_TRANSCRIPTION` — if STT is configured
- `ON_RECORDING_STARTED`, `ON_RECORDING_STOPPED` — recorder captures bridge audio
- `ON_SESSION_STARTED` — session lifecycle unchanged

**Note:** BEFORE_BRIDGE_AUDIO is a SYNC hook that runs in the audio callback
path. Implementations MUST ensure hook handlers complete quickly (< 1ms) to
avoid audio glitches. Long-running operations MUST NOT be performed in this
hook.

#### 12.7.7 Capability Flag

```
VoiceCapability.NATIVE_BRIDGE
```

When a VoiceBackend declares `NATIVE_BRIDGE`, it can bridge audio at the
transport level (e.g., RTP relay, SIP re-INVITE for direct media). The
VoiceChannel MAY delegate bridging to the backend instead of using the
AudioBridge when this capability is present. Native bridging provides lower
latency and reduced CPU usage but bypasses pipeline stages.

Implementations that use native bridging MUST still fire session lifecycle
hooks and MUST support fallback to AudioBridge when pipeline processing
(recording, AEC, transcription) is required.

#### 12.7.8 Conformance

Audio bridging is part of **Conformance Level 3 (Real-Time Media)** and is
OPTIONAL.

Implementations that support audio bridging MUST:
- Forward post-pipeline audio frames between sessions in the same room.
- Support at least 2-party direct forwarding.
- Apply outbound pipeline processing to bridged audio.
- Register/unregister sessions on bind/unbind.
- Ensure thread-safe operation of `forward()`.

Implementations SHOULD:
- Support N-party mixing for rooms with more than 2 voice sessions.
- Handle cross-rate bridging via the outbound resampler.
- Support concurrent bridge + STT operation.

### 12.8 Video Pipeline

The video subsystem mirrors the audio pipeline in structure. Video processing
uses the same pluggable stage architecture, session model, and hook pattern
as audio.

#### 12.8.1 Architecture Overview

```
┌────────┐     ┌──────────────────────────────────────┐     ┌────────────┐
│ Video  │────→│          Video Pipeline               │────→│   Vision   │
│Backend │     │ Decode → Resize → Transform → Filter  │     │  Provider  │
└────────┘     └──────────────────────────────────────┘     └────────────┘
                              │                                    │
                         ┌────┴────┐                      ┌───────┴───────┐
                         │Recorder │                      │ AI Integration│
                         └─────────┘                      │ (inject into  │
                              │                           │  AIChannel)   │
                         ┌────┴─────┐                     └───────────────┘
                         │  Bridge  │
                         │(forward) │
                         └──────────┘
```

**Three video channel variants:**

| Channel | Base Class | Purpose |
|---|---|---|
| VideoChannel | (standalone) | Video-only with vision analysis |
| AudioVideoChannel | VoiceChannel | Combined STT/TTS + video pipeline + avatar |
| RealtimeAudioVideoChannel | RealtimeVoiceChannel | Speech-to-speech + video |

#### 12.8.2 Video Data Models

**VideoFrame** — inbound video frame:

```
VideoFrame
├── data: bytes                             # Encoded NAL units OR raw pixels
├── codec: string                           # h264, vp8, vp9, av1 (encoded) or raw_rgb24, raw_bgr24, raw_yuv420p, raw_nv12 (raw)
├── width: int                              # Frame width in pixels
├── height: int                             # Frame height in pixels
├── timestamp_ms: float                     # Relative to session start
├── keyframe: bool                          # Whether this is a keyframe
├── sequence: int                           # Monotonically increasing per session
├── metadata: map<string, any>              # Accumulated by pipeline stages
│
├── is_encoded: bool (derived)              # True when codec in {h264, vp8, vp9, av1}
└── is_raw: bool (derived)                  # True when codec in {raw_rgb24, raw_bgr24, ...}
```

**VideoChunk** — outbound encoded video:

```
VideoChunk
├── data: bytes                             # Encoded frame data
├── codec: string                           # h264, vp8, vp9, av1 only
├── width: int
├── height: int
├── timestamp_ms: float | null
├── keyframe: bool
└── is_final: bool                          # Signals end of stream
```

**VideoSession** — active video connection:

```
VideoSession
├── id: string
├── room_id: string
├── participant_id: string
├── channel_id: string
├── state: VideoSessionState                # CONNECTING → ACTIVE → PAUSED → ENDED
├── provider_session_id: string | null      # Backend-specific identifier
├── created_at: datetime
└── metadata: map<string, any>
```

**VideoCapability** flags:

| Flag | Description |
|---|---|
| SIMULCAST | Multiple resolution streams |
| SVC | Scalable Video Coding layers |
| SCREEN_SHARE | Separate screen-share track |
| RECORDING | Server-side recording support |
| BANDWIDTH_ESTIMATION | Adaptive bitrate |

#### 12.8.3 VideoBackend Interface

```
VideoBackend (interface)
├── name: string (property)                 # Backend identifier
│
│   # Session lifecycle:
├── connect(room_id, participant_id, channel_id, metadata) → VideoSession
├── accept(request) → VideoSession          # Server-side session acceptance
├── disconnect(session) → void
├── get_session(session_id) → VideoSession | null
├── list_sessions(room_id) → list<VideoSession>
│
│   # Video transport:
├── send_video(session, video) → void       # Send VideoChunk or async stream
├── send_video_sync(session, frame) → void  # Synchronous send (for callbacks)
├── request_keyframe(session) → void        # Request PLI/FIR for keyframe recovery
├── set_video_passthrough(session_id, enabled) → void  # Bridge mode toggle
│
│   # Callbacks:
├── on_video_received(callback) → void      # Raw inbound video frames
├── on_session_ready(callback) → void       # Video path is live
├── on_client_disconnected(callback) → void # Transport disconnect
│
├── capabilities: VideoCapability           # What the backend supports
└── close() → void
```

**Required implementations:**

| Backend | Transport | Use Case |
|---|---|---|
| LocalVideoBackend | OpenCV webcam | Development, testing |
| ScreenCaptureBackend | mss screen capture | Screen sharing, monitoring |

**Optional backends:**

Implementations MAY provide additional backends for WebRTC (FastRTC),
RTP, SIP video, or WebSocket transport.

#### 12.8.4 Video Processing Pipeline

The video pipeline processes inbound frames through ordered stages:

```
VideoPipelineConfig
├── decoder: VideoDecoderProvider | null     # Decode h264 → raw_rgb24
├── resizer: VideoResizerProvider | null     # Scale to target dimensions
├── transforms: list<VideoTransformProvider> # Pixel effects (chained)
├── filters: list<VideoFilterProvider>       # Inspect/replace frames (chained)
├── vision: VisionProvider | null            # Periodic frame analysis
├── recorder: VideoRecorder | null           # Save to file
└── recording_config: VideoRecordingConfig   # Recording parameters
```

**VideoPipeline** orchestrator:

```
VideoPipeline
├── process_inbound(session_id, frame) → VideoFrame | null
│       # Synchronous frame processing:
│       # 1. Decode (if frame.is_encoded)
│       # 2. Resize (if frame.is_raw and resizer configured)
│       # 3. Transforms (chained, pixel modifications)
│       # 4. Filters (chained, with FilterContext)
│       # Returns processed frame or null (dropped)
│
├── process_vision(session_id, frame) → VisionResult | null
│       # Async vision analysis (throttled by vision_interval_ms)
│
├── drain_events(session_id) → list<FilterEvent>
│       # Collect filter events for hook dispatch
│
├── update_filter_context(session_id, result) → void
│       # Sync vision results to active filter contexts
│
├── reset(session_id) → void
└── close() → void
```

**Inbound processing flow:**

```
Backend emits VideoFrame
  │
  ├─ [1] Decoder (if frame.is_encoded)
  │     VideoDecoderProvider.decode(frame) → raw_rgb24 frame
  │
  ├─ [2] Resizer (if frame.is_raw)
  │     VideoResizerProvider.resize(frame) → scaled frame
  │
  ├─ [3] Transforms (chained)
  │     For each VideoTransformProvider:
  │       transform(frame) → modified frame
  │     (grayscale, blur, color adjustment, etc.)
  │
  ├─ [4] Filters (chained, with FilterContext)
  │     For each VideoFilterProvider:
  │       filter(frame, context) → frame or replacement
  │     (censor, watermark, YOLO detection, face detection)
  │
  ├─ Vision Analysis (async, periodic)
  │     VisionProvider.analyze_frame(frame) → VisionResult
  │     Updates FilterContext for subsequent frames
  │     Fires ON_VISION_RESULT hook
  │     Injects description into AI channel context
  │
  └─ Recorder tap (if recording active)
```

#### 12.8.5 Pipeline Stage Providers

**VideoDecoderProvider:**

```
VideoDecoderProvider (interface)
├── name: string
├── decode(frame: VideoFrame) → VideoFrame | null  # Decode encoded → raw
├── reset() → void
└── close() → void
```

Implementations: PyAV (FFmpeg-based, H.264/VP8/VP9/AV1), Mock.

**VideoResizerProvider:**

```
VideoResizerProvider (interface)
├── name: string
├── resize(frame: VideoFrame) → VideoFrame
└── close() → void
```

Implementations: PyAV (FFmpeg scaling), Mock.

**VideoEncoderProvider:**

```
VideoEncoderProvider (interface)
├── name: string
├── encode(frame: VideoFrame) → list<bytes>  # Raw → encoded NAL units
├── flush() → list<bytes>                    # Drain buffered frames
├── reset() → void
└── close() → void
```

Implementations: PyAV (H.264/H.265, optional NVIDIA GPU acceleration).

**VideoTransformProvider:**

```
VideoTransformProvider (interface)
├── name: string
├── transform(frame: VideoFrame) → VideoFrame
├── reset() → void
└── close() → void
```

Transforms modify pixels without changing frame dimensions. Multiple
transforms are chained in order. Example: grayscale, blur, color effects.

**VideoFilterProvider:**

```
VideoFilterProvider (interface)
├── name: string
├── filter(frame: VideoFrame, context: FilterContext) → VideoFrame
├── reset() → void
└── close() → void
```

Filters inspect frames (using vision context) and MAY replace them.
They receive a `FilterContext` with the latest vision analysis results.

**FilterContext:**

```
FilterContext
├── session_id: string
├── last_vision_result: VisionResult | null  # Updated by vision analysis
├── labels_detected: set<string>             # Flattened from vision result
├── censoring: bool                          # Whether active censoring
├── metadata: map<string, any>               # Arbitrary state
└── events: list<FilterEvent>                # Detection events for hook dispatch
```

**Built-in filter implementations:**

| Filter | Purpose |
|---|---|
| CensorVideoFilter | Replaces frames when blocked labels detected (black/solid frame) |
| YOLODetectorFilter | YOLO object detection, updates labels, optional bounding boxes |
| WatermarkFilter | Adds watermark overlay to frames |
| FaceDetectionFilter | Face detection with bounding boxes |

#### 12.8.6 Overlay System

Overlays render text, images, and rich content on top of video frames:

```
Overlay
├── id: string                              # Unique overlay identifier
├── content: string                         # Text, image URL, or markup
├── overlay_type: string                    # "text", "image", "rich", "subtitle"
├── position: OverlayPosition              # Predefined or CUSTOM with x/y
├── x: int (default 0)                     # X offset (for CUSTOM position)
├── y: int (default 0)                     # Y offset (for CUSTOM position)
├── z_order: int (default 0)               # Stacking order (higher = on top)
├── opacity: float (default 1.0)           # 0.0 to 1.0
├── style: map<string, any>                # Renderer-specific styling
└── version: int (default 0)               # Cache invalidation
```

**OverlayPosition** enumeration: TOP_LEFT, TOP_CENTER, TOP_RIGHT,
CENTER_LEFT, CENTER, CENTER_RIGHT, BOTTOM_LEFT, BOTTOM_CENTER,
BOTTOM_RIGHT, CUSTOM.

**OverlayRenderer** (interface):

```
OverlayRenderer (interface)
├── overlay_type: string (property)         # Which overlay type this renders
├── render(canvas, overlay, frame_width, frame_height) → canvas
├── invalidate_cache(overlay_id) → void
└── clear_cache() → void
```

Implementations: TextOverlayRenderer, ImageOverlayRenderer,
RichOverlayRenderer, SubtitleOverlayRenderer. The `OverlayFilterProvider`
applies overlays to frames as a pipeline filter stage.

#### 12.8.7 VisionProvider

Vision providers analyze video frames and produce structured results:

```
VisionProvider (interface)
├── name: string (property)
├── analyze_frame(frame, prompt) → VisionResult
│       # Analyze a single frame (async)
│
├── analyze_stream(frames, interval_ms, assumed_fps) → async_iterator<VisionResult>
│       # Streaming analysis at configurable intervals
│
├── supports_streaming: bool (property)
├── warmup() → void                         # Pre-load models
└── close() → void
```

**VisionResult:**

```
VisionResult
├── description: string                     # Natural language description
├── labels: list<string>                    # Detected objects/scenes
├── confidence: float                       # 0.0 to 1.0
├── faces: list<FaceDetection>             # Detected faces with bounding boxes
├── text: string | null                     # OCR text
└── metadata: map<string, any>              # Provider-specific data
```

**FaceDetection:**

```
FaceDetection
├── x: int                                  # Bounding box x
├── y: int                                  # Bounding box y
├── width: int
├── height: int
├── confidence: float
└── label: string | null                    # Optional identity label
```

**Implementations:**

| Provider | Backend | Description |
|---|---|---|
| OpenAIVisionProvider | GPT-4o, Ollama, vLLM | OpenAI-compatible vision API |
| GeminiVisionProvider | Google Gemini | Google Gemini vision |
| MockVisionProvider | — | Testing |

**AI integration:** `setup_video_vision(kit, room_id, ai_channel_id)` wires
vision results into the AIChannel's system prompt. On each VisionResult, the
description is injected so the AI can "see" what the video shows.

#### 12.8.8 AvatarProvider (Lip-Sync Video Generation)

Avatar providers generate lip-synced video from TTS audio:

```
AvatarProvider (interface)
├── name: string (property)
├── fps: float (property)                   # Output frame rate
├── is_async: bool (property)               # Whether delivery is callback-based
│
├── start(reference_image, width, height) → void
│       # Initialize with a reference face image
│
├── feed_audio(pcm_data, sample_rate) → list<VideoFrame>
│       # Feed TTS audio, return generated frames
│       # Sync mode: returns frames immediately
│       # Async mode: returns [], frames arrive via on_video() callback
│
├── on_video(callback) → void               # Register frame callback (async mode)
├── end_turn() → void                       # Signal end of TTS response
├── get_idle_frame() → VideoFrame | null    # Frame to display when TTS not playing
├── flush() → list<VideoFrame>              # Drain buffered frames
├── stop() → void
└── close() → void
```

**Two delivery modes:**
- **Synchronous** (local models): `feed_audio()` returns frames immediately.
- **Asynchronous** (cloud APIs): `feed_audio()` returns empty list; frames
  arrive via the `on_video()` callback.

In AudioVideoChannel, the avatar is wired as an outbound audio tap.
TTS audio chunks are fed to the avatar, and the resulting video frames are
encoded and sent via the video backend.

#### 12.8.9 VideoBridge

The VideoBridge forwards video frames between sessions in the same room,
mirroring the AudioBridge pattern:

```
VideoBridgeConfig
├── enabled: bool (default true)
├── max_participants: int (default 10)
├── forwarding_strategy: "forward"          # Direct frame forwarding
└── keyframe_interval_s: float (default 5.0)  # PLI request interval
```

```
VideoBridge
├── add_session(session, room_id, backend) → void
├── remove_session(session_id) → void
├── forward(session, frame) → void          # Forward to all other sessions in room
├── set_frame_filter(fn) → void             # Optional pre-forward filter (can drop)
├── set_frame_processor(fn) → void          # Optional per-target processor
├── get_participant_count(room_id) → int
├── get_bridged_sessions(room_id) → list<(VideoSession, VideoBackend)>
└── close() → void
```

**Key behaviors:**
- Keyframe buffering for late joiners.
- Periodic PLI (Picture Loss Indication) requests to ensure keyframe delivery.
- Delta frame gating — waits for a keyframe before forwarding delta frames
  to a new session.
- Thread-safe session registration and removal.
- `BEFORE_BRIDGE_VIDEO` sync hook fires before forwarding (can block/modify).

#### 12.8.10 Video Recording

```
VideoRecordingConfig
├── storage: string                         # Output directory
├── format: string (default "mp4")          # Container format
├── codec: string (default "auto")          # Video codec
├── fps: float (default 15.0)              # Output frame rate
└── metadata: map<string, any>
```

```
VideoRecorder (interface)
├── name: string (property)
├── start(session, config) → VideoRecordingHandle
├── stop(handle) → VideoRecordingResult
└── tap_frame(handle, frame) → void         # Feed frame to recorder
```

**VideoRecordingResult:**

```
VideoRecordingResult
├── id: string
├── url: string                             # File path or URL
├── duration_seconds: float
├── frame_count: int
├── format: string
├── size_bytes: int
└── metadata: map<string, any>
```

**Implementations:** PyAVVideoRecorder (H.264/H.265, NVIDIA GPU),
OpenCVVideoRecorder (MJPEG/XVID), MockVideoRecorder.

**Scope.** Like the audio recorder, this one records a session's video and is
handed one — a conference publishes N attributed video tracks and no session,
and records them through Section 12.11 instead (Section 12.10.8).

#### 12.8.11 Video Hooks

| Hook | Execution | When |
|---|---|---|
| ON_VIDEO_SESSION_STARTED | ASYNC | Video session became active |
| ON_VIDEO_SESSION_ENDED | ASYNC | Video session ended |
| ON_VIDEO_TRACK_ADDED | ASYNC | Video track added to session |
| ON_VIDEO_TRACK_REMOVED | ASYNC | Video track removed from session |
| ON_VISION_RESULT | ASYNC | VisionProvider returned analysis result |
| ON_VIDEO_DETECTION | ASYNC | Filter emitted a detection event (YOLO, face, etc.) |
| ON_SCREEN_SHARE_STARTED | ASYNC | Screen sharing started |
| ON_SCREEN_SHARE_STOPPED | ASYNC | Screen sharing stopped |
| BEFORE_BRIDGE_VIDEO | SYNC | Before frame forwarded via bridge — can block |

### 12.9 AI Generation Pipeline

The AI generation subsystem mirrors the audio and video pipelines in structure.
Text generation by an AIChannel flows through a pluggable stage architecture using
the same ABC + config composition pattern as Section 12.3 (Audio Pipeline) and
Section 12.8 (Video Pipeline).

This design ensures that cross-cutting generation concerns (gating, memory
retrieval, tool resolution, prompt assembly, response validation, caching,
content filtering) are expressed as composable stages rather than hardcoded
sequences inside the channel. New generation-time features become new stages,
not new hook triggers or new mixins.

#### 12.9.1 Architecture Overview

```
Inbound RoomEvent (arrives at AIChannel.on_event)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AI Generation Pipeline                          │
│                                                                      │
│  PreContextGate  ──►  MemoryRetrieval  ──►  ToolResolution  ──►     │
│  (cheap gates)        (history, RAG)         (skills, policy)        │
│                                                                      │
│  PromptAssembly  ──►  PreGeneration    ──►  Generation      ──►     │
│  (system prompt)      (final gate)           (provider call)         │
│                                                                      │
│  PostGeneration  ──►  Emission                                       │
│  (validate, cache)    (emit events)                                  │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
Response events → conversation store + broadcast
```

**Choosing between hook and stage:**

| Criterion | Hook | Stage |
|---|---|---|
| **Ad-hoc gate in one project** | Preferred | Overkill |
| **Reusable logic across projects** | Hard to package | Preferred |
| **Replaces a default behavior** | Cannot | Preferred |
| **Needs fine-grained position** | Limited to trigger points | Any stage position |
| **Modifies AIContext in place** | Supported (BEFORE_AI_GENERATION) | Supported (any stage) |
| **Multiple instances at same point** | Supported via priority | Supported via list slots |

Hooks remain the simpler mechanism for most cases. Stages are the right
abstraction when logic is reusable, needs a specific position in the pipeline,
or replaces a default behavior (e.g., a custom memory retrieval strategy).

#### 12.9.2 Default Stage Ordering (NORMATIVE)

Implementations MUST execute the default AI generation pipeline in the
following order:

```
[*gates, memory, tool_resolution, prompt_assembly, pre_generation,
 generation, *post_generation, emission]
```

**Stage positions:**

| Position | Stage | Default Behavior | Hook Trigger |
|---|---|---|---|
| 1 | gates (list) | Fire BEFORE_AI_CONTEXT_BUILD hooks, respect block | BEFORE_AI_CONTEXT_BUILD |
| 2 | memory | Call MemoryProvider.retrieve() | — |
| 3 | tool_resolution | Resolve skills, apply ToolPolicy, apply eviction | — |
| 4 | prompt_assembly | Compose system prompt (channel + binding + skill preambles) | — |
| 5 | pre_generation | Fire BEFORE_AI_GENERATION hooks, respect block/modify | BEFORE_AI_GENERATION |
| 6 | generation | Call AIProvider.generate() or generate_stream(); run tool loop | ON_AI_THINKING, ON_TOOL_CALL |
| 7 | post_generation (list) | Response validation, caching, output filtering (default: no-op) | — |
| 8 | emission | Emit response events, fire AFTER_RESPONSE | ON_AI_RESPONSE |

**Ordering rationale:**

| Position | Stage | Why here |
|---|---|---|
| 1 | gates | Cheapest gate point. Blocks before any expensive work (memory retrieval, summarization, tool resolution). Required for features with side effects that must not run when generation is blocked (e.g., observation queues, token accounting). |
| 2 | memory | Needed before prompt assembly (memory contents affect prompt length and tool policy). Must run after gates to avoid wasted retrieval and possible summarization LLM calls. |
| 3 | tool_resolution | Needs memory results to apply budget-aware policy (tools count against context budget). |
| 4 | prompt_assembly | Combines channel defaults, binding overrides, skill preambles, sandbox preambles. Runs after tool resolution so tool descriptions are finalized. |
| 5 | pre_generation | Final modification opportunity before provider call. Hooks can mutate AIContext in place (system prompt injection, dynamic tool addition). |
| 6 | generation | Provider invocation + tool loop. The expensive step. |
| 7 | post_generation | Inspect/modify the response before emission (caching lookup/store, output content filter, safety guardrails with optional regeneration). |
| 8 | emission | Final step. Emit response events, fire AFTER_RESPONSE hook, trigger broadcast pipeline. |

Stages MUST NOT be reordered by integrators. Insertion is allowed only at the
multi-stage slots (`gates`, `post_generation`).

#### 12.9.3 AIStage Interface

```
AIStage (interface)
├── name: string (property)                  # Stage identifier (defaults to class name)
├── process(ctx: AIPipelineContext)
│     → AIPipelineContext                    # Transform context, return it
└── close() → void                           # Release resources
```

**Abort semantics:**

A stage MAY abort the pipeline by setting `ctx.aborted = True`, populating
`ctx.abort_reason` and `ctx.abort_stage`, and returning the context. All
subsequent stages MUST be skipped when `ctx.aborted` is true. Emission stage
MUST NOT emit response events from an aborted pipeline.

**Error handling:**

If a stage raises an exception, the pipeline engine MUST treat this as an
abort (set `ctx.aborted = True`, `ctx.abort_reason = "stage exception"`,
`ctx.abort_stage = <failing stage name>`). Exceptions MUST NOT propagate out
of the pipeline to AIChannel callers.

#### 12.9.4 Position-Specific Stage ABCs

Each stage position has a dedicated ABC subclass of AIStage:

| ABC | Position | Multi-Stage | Default Exists |
|---|---|---|---|
| PreContextGateStage | 1 | Yes (list) | Yes (hook runner) |
| MemoryRetrievalStage | 2 | No | Yes |
| ToolResolutionStage | 3 | No | Yes |
| PromptAssemblyStage | 4 | No | Yes |
| PreGenerationStage | 5 | No | Yes (hook runner) |
| GenerationStage | 6 | No | Yes |
| PostGenerationStage | 7 | Yes (list) | Yes (no-op) |
| EmissionStage | 8 | No | Yes |

An integrator-provided stage at a single-stage position replaces the default.
Integrator-provided stages at multi-stage positions are appended to the
pipeline in registration order alongside any built-in defaults.

#### 12.9.5 AIPipelineContext

Accumulating state that flows through all stages:

```
AIPipelineContext
├── event: RoomEvent                         # Triggering event
├── binding: ChannelBinding                  # AIChannel's room binding
├── room_context: RoomContext                # Room state (participants, recent events)
├── channel_id: string                       # AIChannel identifier
├── ai_context: AIContext | null             # Built by MemoryRetrievalStage + friends
├── response: AIResponse | null              # Built by GenerationStage
├── stage_metadata: map<string, any>         # Inter-stage communication
├── aborted: bool                            # Set by any stage to abort pipeline
├── abort_reason: string | null              # Human-readable abort reason
└── abort_stage: string | null               # Name of stage that aborted
```

**Field population timeline:**

- **Before stage 1:** only `event`, `binding`, `room_context`, `channel_id` are set
- **After stage 2 (memory):** `ai_context` is populated with historical messages
- **After stage 4 (prompt_assembly):** `ai_context.system_prompt` is finalized
- **After stage 6 (generation):** `response` is populated
- **After stage 8 (emission):** response events have been emitted

Stages MAY read any populated field. Stages MUST NOT read fields that are not
yet populated per the timeline above.

#### 12.9.6 AIPipelineConfig

Configuration model for composing an AI pipeline:

```
AIPipelineConfig
├── gates: list<PreContextGateStage>         # Default: []
├── memory: MemoryRetrievalStage | null      # Default: null → use built-in default
├── tool_resolution: ToolResolutionStage | null
├── prompt_assembly: PromptAssemblyStage | null
├── pre_generation: PreGenerationStage | null
├── generation: GenerationStage | null
├── post_generation: list<PostGenerationStage>  # Default: []
├── emission: EmissionStage | null
└── telemetry: TelemetryProvider | null      # Optional per-stage telemetry
```

**Composition algorithm (NORMATIVE):**

```
def build_pipeline(config: AIPipelineConfig) -> list[AIStage]:
    return [
        *config.gates,
        config.memory or DefaultMemoryRetrievalStage(),
        config.tool_resolution or DefaultToolResolutionStage(),
        config.prompt_assembly or DefaultPromptAssemblyStage(),
        config.pre_generation or DefaultPreGenerationStage(),
        config.generation or DefaultGenerationStage(),
        *config.post_generation,
        config.emission or DefaultEmissionStage(),
    ]
```

Multi-stage slots (`gates`, `post_generation`) preserve registration order.
Single-stage slots fall back to the built-in default when null.

#### 12.9.7 AIChannel Integration

AIChannel MUST accept an optional `pipeline: AIPipelineConfig | None` parameter,
mirroring the voice and video channels:

```
AIChannel(..., pipeline: AIPipelineConfig | null = null)
VoiceChannel(..., pipeline: AudioPipelineConfig | null = null)
VideoChannel(..., pipeline: VideoPipelineConfig | null = null)
```

When `pipeline` is null, AIChannel MUST construct a default pipeline using
`AIPipelineConfig()` (no custom stages; all slots use defaults).

AIChannel's `on_event()` implementation MUST:
1. Construct an AIPipelineContext from the event, binding, and room context
2. Invoke `AIPipeline.process(ctx)`
3. Return an empty ChannelOutput if `ctx.aborted` is true
4. Return the ChannelOutput built by EmissionStage otherwise

AIChannel MUST NOT call provider.generate() or memory.retrieve() directly
when a pipeline is in use. All such work MUST flow through the pipeline.

#### 12.9.8 Symmetry with Other Pipelines

| Concept | Audio Pipeline | Video Pipeline | AI Pipeline |
|---|---|---|---|
| Config dataclass | AudioPipelineConfig | VideoPipelineConfig | AIPipelineConfig |
| Engine | AudioPipeline | VideoPipeline | AIPipeline |
| Stage ABC | (per-stage: VADProvider, AECProvider, ...) | (per-stage: Decoder, Resizer, ...) | AIStage + position-specific subclasses |
| Channel param | `pipeline=` | `pipeline=` | `pipeline=` |
| Default when null | Sensible defaults per stage | Sensible defaults per stage | Sensible defaults per stage |
| Multi-stage slots | `postprocessors: list[...]` | `filters: list[...]` | `gates: list[...]`, `post_generation: list[...]` |
| Normative ordering | Yes (12.3) | Yes (12.8.4) | Yes (12.9.2) |

#### 12.9.9 Hook Trigger to Stage Mapping

| Hook Trigger | Fires At Stage | Execution |
|---|---|---|
| BEFORE_AI_CONTEXT_BUILD | PreContextGateStage (default impl) | SYNC — can block |
| BEFORE_AI_GENERATION | PreGenerationStage (default impl) | SYNC — can block/modify |
| ON_AI_THINKING | GenerationStage | ASYNC — observability |
| ON_TOOL_CALL | GenerationStage (during tool loop) | SYNC — can intercept |
| ON_AI_RESPONSE | EmissionStage | ASYNC — observability |

Hook triggers are preserved as callback points fired by their stages. Existing
hook registrations MUST continue to function unchanged. Integrators MAY use
either hooks or custom stages depending on their use case.

#### 12.9.10 Observability

Pipeline implementations SHOULD emit a framework event per stage completion:

| Event | Payload |
|---|---|
| `ai_pipeline.stage_complete` | stage_name, latency_ms, aborted, abort_reason |
| `ai_pipeline.aborted` | stage_name, abort_reason, total_latency_ms |
| `ai_pipeline.completed` | stage_count, total_latency_ms |

This provides per-stage timing and abort visibility consistent with the voice
pipeline's `voice.pipeline.*` events.

#### 12.9.11 Conformance

**Level 0 (Core, REQUIRED):**
- AIChannel MUST implement the default pipeline with all 8 stages
- The normative stage ordering in Section 12.9.2 MUST be preserved
- Abort semantics in Section 12.9.3 MUST be honored
- `BEFORE_AI_CONTEXT_BUILD` and `BEFORE_AI_GENERATION` hook triggers MUST fire
  at their documented stages

**Level 1 (Extension, RECOMMENDED):**
- AIChannel SHOULD accept a `pipeline: AIPipelineConfig | null` parameter
- Integrators SHOULD be able to replace any single-stage slot with a custom
  implementation
- Integrators SHOULD be able to append to multi-stage slots (`gates`,
  `post_generation`)

**Level 2 (Advanced, OPTIONAL):**
- Pipelines MAY support PostGenerationStage regenerating by looping back to
  GenerationStage (e.g., safety guardrails retry)
- Pipelines MAY support per-binding pipeline overrides (per-room customization)
- Pipelines MAY expose per-stage telemetry via a TelemetryProvider

### 12.10 Conference (SFU Orchestration)

**Status: STABLE.** The interfaces in this section were validated on paper
against the published server APIs of multiple SFU implementations, then
revised against the first conforming production backend (LiveKit) as its
implementation landed — the revision window the PROVISIONAL status existed
for, now closed. The section follows normal stability rules, and every
other section referencing conference concepts follows them for those
references too.

A conference extends a Room with a multi-party real-time media session —
audio, video, and screen share among N participants. The defining
architectural decision is that **RoomKit does not own the conference media
plane**. An external SFU (Selective Forwarding Unit) routes media between
human participants; RoomKit orchestrates the conference and joins it as a
participant to provide intelligence: transcription, vision, AI voice,
recording, and cross-channel integration.

#### 12.10.1 Design Principles

1. **RoomKit orchestrates; the SFU transports.** Per-packet media routing
   between human participants — codec negotiation, simulcast layer
   selection, bandwidth estimation, NACK/PLI retransmission — is the SFU's
   responsibility. RoomKit MUST NOT sit in the media path between human
   participants. This is the scale boundary that the in-process AudioBridge
   (Section 12.7) cannot cross.

2. **The conference is the room.** Each conference maps 1:1 to a Room.
   Conference participants are Room participants. Transcriptions are
   RoomEvents. Hooks, permissions, and cross-channel broadcast apply with
   no conference-specific exceptions.

3. **Human clients connect directly to the SFU.** RoomKit mints access
   credentials (Section 12.10.3) and observes participant lifecycle through
   backend events; it never proxies client signaling or media. Client-side
   SDKs are provider-specific and out of scope for this specification —
   switching SFU providers implies switching the integrator's client SDK.

4. **RoomKit joins as a bot participant.** The framework's media access
   goes through one server-side connection per conference: subscribed
   tracks feed the audio/video pipelines (STT, vision, recording), and the
   AI's TTS output is published as a single bot track that the SFU
   distributes to everyone.

5. **Tracks are the unit of media identity.** Every media stream carries
   the identity of its publishing participant. Speaker attribution comes
   from track identity, so diarization is unnecessary. Server-side AEC is
   likewise unnecessary: clients perform their own echo cancellation and
   the SFU never mixes audio.

6. **The backend boundary is decoded frames and opaque credentials.** The
   ConferenceBackend delivers decoded PCM audio and raw (or encoded) video
   frames, and mints credentials the framework never inspects. SDP, ICE,
   codecs, simulcast layers, and bitrates do not appear in any framework
   interface.

#### 12.10.2 Data Models

**TrackKind** enumeration:

| Value | Description |
|---|---|
| AUDIO | Microphone audio |
| VIDEO | Camera video |
| SCREEN_SHARE | Screen share video |

**ConferenceTrack** — a single published media stream:

```
ConferenceTrack
├── id: string                          # Backend-scoped stable identifier
├── room_id: string                     # Owning conference room
├── participant_id: string              # Publishing participant
├── kind: TrackKind
├── muted: bool = false
└── metadata: map<string, any>          # Provider-specific (sid, source, ...)
```

`room_id` is what makes the frame callbacks routable: a single
ConferenceBackend instance serves many rooms, and `on_track_audio` /
`on_track_video` carry only a ConferenceTrack. Every ConferenceTrack a
backend emits MUST carry the room it belongs to.

**ConferenceParticipant** — a participant's media presence:

```
ConferenceParticipant
├── participant_id: string
├── display_name: string | null                 # Presentation, never identity
├── connected_at: datetime
├── tracks: list<ConferenceTrack>
├── metadata: map<string, any>                  # Provider-supplied participant attributes
└── asserted_metadata: map<string, any> | null  # The subset the SFU itself asserts
```

A backend MUST surface the provider's own participant attributes in
`metadata`. This is not decoration: for a participant the framework did not
name, those attributes are where the resolvable address lives — a PSTN
dial-in carries its caller number there, and that number is precisely what
identity resolution consumes (Section 5.6, `channel_addresses`). Dropping
them leaves the framework with an opaque identifier and no way to connect
the caller to a known Identity.

**Where those attributes came from (normative).** `metadata` says what the
provider surfaced; it does not say who put it there. On most SFUs one
attribute map carries two very different things: facts the server
established — the caller number a SIP trunk reported, a claim in a token it
authenticated, an attribute the integrator set through a server-side API —
and values a participant's own client supplied when it joined. Nothing in
the map's shape tells them apart, and the difference decides what may be
believed.

`asserted_metadata` is where a backend states the difference. It is the
subset of `metadata` the SFU itself asserts. Therefore:

1. A backend MUST NOT place an attribute in `asserted_metadata` unless its
   value was established by the SFU or by a server-side call: the SIP trunk,
   the admission it authenticated, its own API. Values a client supplied at
   join — directly, or through a token it was free to populate — MUST NOT
   appear there, whatever their key.
2. A backend that cannot tell the two apart MUST leave `asserted_metadata`
   null rather than fill it with everything it has. Null is a statement —
   "this backend does not distinguish" — and a consumer can act on it. A
   guess is indistinguishable from an assertion, and it is the assertion
   that decisions get made on.
3. An empty map is the other statement: this backend distinguishes, and the
   SFU asserts nothing about this participant.

The specification names the fact rather than the policy. What an
implementation may do with each of the two sets is stated where it consumes
them — for identity resolution, under *Resolving the participant the
framework did not name* below.

**ConferenceGrants** — least-privilege permissions encoded into access:

```
ConferenceGrants
├── publish_audio: bool = true
├── publish_video: bool = true
├── publish_screen_share: bool = true
├── subscribe: bool = true
├── moderate: bool = false              # Can mute/remove other participants
└── hidden: bool = false                # Invisible observer (bots, monitors)
```

**ConferenceAccess** — credentials for a human client to join:

```
ConferenceAccess
├── url: string                         # Endpoint the client connects to
├── token: string                       # Provider-specific credential
├── expires_at: datetime | null
└── provider_data: map<string, any>     # Additional provider-specific fields
```

The framework treats ConferenceAccess as **opaque**: the backend mints it,
the integrator returns it to the client application (e.g., via the REST
surface), and the provider's client SDK consumes it. Framework code MUST
NOT depend on its internal structure beyond the fields above.

**Participant identity correlation (normative).** Every attribution
guarantee in this section — transcription RoomEvents, Participant records,
interruption allowlists — depends on `participant_id` meaning the same
thing on both sides of the backend boundary. Therefore:

1. The framework MUST pass the Room `Participant.id` (Section 5.5) as the
   `participant_id` argument to `mint_access()`.
2. For a participant that joined with minted access, the backend MUST
   surface that same value as `ConferenceParticipant.participant_id` and as
   `ConferenceTrack.participant_id`. A backend whose SFU cannot carry a
   caller-supplied identity MUST maintain the mapping internally and
   translate at the boundary.
3. For a participant the framework did not mint — SIP/PSTN dial-in
   (Section 12.10.9), or admission arranged out of band — the backend MUST
   surface its own stable identity for the lifetime of that participant's
   connection, and MUST populate `metadata` with the provider's participant
   attributes. The channel MUST then create a Participant with that
   identity as `external_id` and `identification: UNKNOWN`, and MUST pass
   any resolvable address the SFU asserts — a caller number above all — to
   identity resolution (Section 11) rather than resolving on the opaque
   identity alone. A phone participant joining a conference SHOULD reach
   the same Identity it would have reached over the SMS or Voice channel.
4. Identities MUST NOT be reused across participants within a room's
   lifetime.

**Resolving the participant the framework did not name.** Rule 3 says the
address must reach identity resolution; when it does so, and what becomes of
the answer, decide whether the rest of the section still holds.

Resolution MUST run when the participant **arrives**, not when it first
speaks. A conference participant may listen for an hour without publishing a
word, and one that stays unidentified until it does is unidentified to every
hook, roster read and disclosure obligation in the meantime — which is the
opposite of what rule 3 exists for. It also means resolution runs for a
participant that never speaks at all.

The answer MUST be recorded on the Participant rule 3 created, whose `id`
remains the backend's identity: the resolved Identity is carried by
`identity_id` (and `display_name`), and the participant MUST NOT be re-keyed
to the Identity's own id. Re-keying would break rule 2 in the one place it
matters most — transcription RoomEvents would be attributed to the Identity
while the recording's `RecordingTrack.participant_id` (Section 12.10.8), the
interruption allowlist (Section 12.10.5) and the roster stayed on the
backend's identity, leaving one human under two identifiers in one room. One
participant record, one identifier, an Identity linked to it.

What counts as a resolvable address is provider-specific, so an
implementation MUST document the participant-attribute keys it reads and
SHOULD let an integrator override them — a provider whose key is not on the
list is a configuration matter, not a reason to fork the framework. The
number a caller *dialled* is not the caller: keys carrying the trunk or
destination number (`sip.trunkPhoneNumber` and equivalents) MUST NOT be
taken for the caller's address. Where no resolvable address is found, the
channel MUST leave the participant `UNKNOWN` rather than resolving on the
opaque identity, which is the case rule 3 rules out.

**An address is only as good as its provenance.** Which key carries the
address is the second question; the first is who put the value there. An
attribute a participant's own client supplied is a claim about itself: a
caller that writes its own `phone_number` and is resolved on it reaches
whatever Identity that number belongs to — someone else's — and the
Participant then carries the victim's `identity_id`, on the record every
later attribution reads. Therefore an implementation MUST resolve identity
only on addresses found in `asserted_metadata`, and MUST NOT take an
attribute the backend did not assert for an address. A null
`asserted_metadata` asserts nothing: a backend that does not distinguish
(preceding subsection, point 2) yields no resolvable address at all, and its
participants stay `UNKNOWN`.

Provenance outranks specificity. An asserted attribute on a generic key is
believed over an unasserted one on the provider's own key, because the
attacker chooses the key and never the provenance.

This is a default, not a prohibition. An integrator whose deployment has its
own reason to trust unasserted attributes — a closed client fleet, a backend
whose provenance the integrator establishes elsewhere — MAY widen it, and an
implementation SHOULD offer that as configuration rather than leave forking
as the only route. What an implementation MUST NOT do is widen it silently:
the safe reading is the one that holds unconfigured. Where an implementation
carries the provider's attributes into resolution as context, the ones it
did not vouch for MUST remain distinguishable from the ones it did, so that
a resolver reading them does so knowingly.

**What the Participant record keeps of them.** Provider attributes are worth
persisting — they are how an integrator finds out that a participant dialled
in, on what trunk, under which SIP call id. But a Participant's `metadata`
(Section 5.5) is the integrator's own map, and a conference is a place where
strangers write into it. An implementation that records provider attributes
on a Participant MUST therefore:

- keep them under a single dedicated key rather than merged flat, so that no
  provider attribute can overwrite a field the integrator put there;
- keep the provenance split of the preceding subsection intact in the
  record, so that what an identity was founded on remains auditable after
  the fact;
- bound what is persisted — the number of attributes and the size of each —
  since on a conference open to dial-in, their content is chosen by whoever
  connects.

**An arrival is not an inbound message**, and the parts of Section 11 that
act on one do not apply to it: there is nothing to hold, nothing to reject and
nowhere to inject a challenge, so an arrival MUST NOT fire the
`ON_IDENTITY_*` hooks or run the challenge and rejection flows — those
belong to the inbound pipeline, and the participant's first utterance
reaches it normally. An AMBIGUOUS or PENDING result SHOULD be recorded as a
pending identification carrying its candidates; UNKNOWN, REJECTED and
CHALLENGE_SENT leave the participant `UNKNOWN`. Section 11.5 applies to the
call: on timeout the implementation MUST treat the result as UNKNOWN, emit
`identity_timeout`, and let the participant join regardless. A resolver that
raises MUST NOT keep a participant out of the conference.

**BotSession** — the framework's own connection to a conference:

```
BotSession
├── id: string
├── room_id: string
├── identity: string                    # Display identity in the conference
├── joined_at: timestamp                # When the bot connected; MUST be timezone-aware
└── metadata: map<string, any>
```

`joined_at` is what `conference_ended`'s `duration_ms` is measured from
(Section 8.2). It defaults to the moment the session is constructed, which
is when a backend builds the one it returns from `join_as_bot()`; a backend
holding a more accurate figure — one the SFU reports — SHOULD set it
instead. It MUST be timezone-aware: a naive value cannot be subtracted from
an aware clock, and the failure surfaces during teardown where it costs the
conference its end announcement rather than the duration alone.
Implementations SHOULD settle the timezone when the session is recorded, so
that a backend's omission is reported at the boundary it came from rather
than raised from the teardown.

**ConferenceCapability** flags:

| Flag | Description |
|---|---|
| SCREEN_SHARE | Separate screen-share tracks |
| EGRESS_RECORDING | Server-side (SFU) recording/export |
| SIP_GATEWAY | PSTN/SIP participants can dial into the conference |
| ACTIVE_SPEAKER | Dominant-speaker change events |
| CONNECTION_QUALITY | Per-participant quality reports |
| VIDEO_PUBLISH | Bot can publish video tracks (avatar) |
| REMOTE_UNMUTE | A moderator can unmute another participant's track |
| BOT_GRANT_UPDATE | A connected bot session's grants can be changed in place |
| E2EE | End-to-end encryption between clients |

REMOTE_UNMUTE is a capability rather than an assumed operation because
unmuting someone else's microphone is a privacy decision, not a technical
one: SFUs commonly refuse it by default and require an explicit server-side
opt-in. Muting is always available; unmuting is not.

BOT_GRANT_UPDATE says the SFU can change what a *connected* session may
do without reconnecting it — a server-side participant update (LiveKit's
UpdateParticipant is the informative example). It is a capability because
many SFUs can only set permissions at admission: against those, the one
way to change a live bot's grants is to replace the session, and Section
12.10.4 (**Hot-plugging intelligence**) specifies exactly that fallback.
What the capability buys is continuity — a re-permission with the
session, its subscriptions and the event bridge intact.

**E2EE and framework media access (normative).** E2EE is the one
capability that constrains rather than extends what the framework can do:
when it is active, the bot receives ciphertext it cannot decode, so STT
lanes, vision analysis, framework recording, and SFU egress recording all
become unavailable.

The flag above states only that a backend *supports* E2EE. Whether a given
conference *uses* it is per-conference state, requested through the
channel's `e2ee` field (Section 12.10.4) and passed to `ensure_room()`;
setting it on a backend without the E2EE capability MUST raise a
configuration error. An implementation offering E2EE MUST then do one of:

- admit the bot as a key holder in the conference's key exchange, so
  subscribed tracks decode normally; or
- run the conference without framework media intelligence, and raise a
  configuration error when STT, vision, or recording is configured on a
  channel with `e2ee` set.

Silently delivering undecodable frames to a lane is NOT conforming.

#### 12.10.3 ConferenceBackend Interface

```
ConferenceBackend (interface)
├── name: string (property)             # Backend identifier
├── capabilities: ConferenceCapability
│
│   # Control plane:
├── ensure_room(room_id, metadata) → void
│       # Idempotent: create the conference room if absent
├── close_room(room_id) → void
├── mint_access(room_id, participant_id, grants, display_name?) → ConferenceAccess
├── list_participants(room_id) → list<ConferenceParticipant>
├── remove_participant(room_id, participant_id) → void
├── mute_track(room_id, track_id) → void     # Moderation mute
├── unmute_track(room_id, track_id) → void   # Requires REMOTE_UNMUTE
│
│   # Bot participant (framework media access):
├── join_as_bot(room_id, identity, grants) → BotSession
├── leave(bot) → void
├── update_bot_grants(bot, grants) → void         # Requires BOT_GRANT_UPDATE
├── subscribe_track(bot, track_id) → void
├── unsubscribe_track(bot, track_id) → void
├── publish_audio(bot, chunk: AudioChunk) → void
├── stop_playback(bot) → void                      # Barge-in: discard queued bot audio
├── publish_video(bot, frame: VideoFrame) → void   # Requires VIDEO_PUBLISH
│
│   # Callbacks:
├── on_participant_joined(callback)     # (room_id, ConferenceParticipant)
├── on_participant_left(callback)       # (room_id, ConferenceParticipant)
├── on_track_published(callback)        # (room_id, ConferenceTrack)
├── on_track_unpublished(callback)      # (room_id, ConferenceTrack)
├── on_track_muted(callback)            # (room_id, ConferenceTrack)
├── on_track_unmuted(callback)          # (room_id, ConferenceTrack)
├── on_track_audio(callback)            # (ConferenceTrack, AudioFrame)
├── on_track_video(callback)            # (ConferenceTrack, VideoFrame)
├── on_active_speaker_changed(callback) # (room_id, participant_id)
├── on_connection_quality(callback)     # (room_id, participant_id, quality)
├── on_bot_session_ended(callback)      # (BotSession, reason)
└── close() → void
```

**Presence is observable only through a connection (normative):** the
participant, track, audio and speaker callbacks describe a conference that
a bot session of this backend is connected to. Before the first
`join_as_bot()` — and between a reported end and a re-join — a backend is
not required to deliver any of them, and against most SFUs it cannot: the
server reports a room's events to the connections in it, and the framework
does not hold one. A backend with a server-side view of its own — webhooks,
a polling loop — MAY report presence for a room no session is connected to,
but a channel MUST NOT depend on such reports for anything correctness
rests on, the first join above all (Section 12.10.4): a channel whose only
bootstrap is a presence callback waits on an event that only the join it
is waiting to make would let the backend observe.

What a newly joined session is owed is the present, not the past. A lazily
joining bot enters a meeting already underway, and the participants and
tracks it finds there may never have been reported — there was no
connection to report them through. On `join_as_bot()`, a backend MUST
therefore catch the channel up: every participant currently in the room
and every track currently published that it has not already reported is
delivered through the ordinary joined and published callbacks — the
catch-up the reported-discontinuity rules below lean on. A backend that
observed the room without a connection may have nothing left to say; one
that could not observe it reports everything it finds. What ended before
the join — an arrival that left again, a track unpublished — is not
recoverable, exactly as across a reported discontinuity.

**The bot's own connection (normative):** an SFU can end the bot's session
without a `leave()` — the connection drops, a moderator evicts the bot, the
room is deleted under it. A backend that observes such an end MUST report
it through `on_bot_session_ended`, naming the session and a human-readable
reason, MUST forget the session (a later `leave()` for it is a no-op), and
MUST NOT accept further media calls for it. The channel MUST treat the
report as the session's end in fact: the session comes off the books —
`bot_present` stops answering yes for a connection that is gone —
`conference_ended` is announced, the session's lanes are closed and its
recordings finalized, and the next need re-joins lazily, exactly as the
first one did. Without this report a dropped bot is a session the channel
reports present forever and a conference that has silently lost its
transcription; a backend that genuinely cannot observe the loss has
nothing to report, and inherits that failure mode knowingly.

The report is also the honest exit for a session whose *view* of the
conference can no longer be trusted — an event bridge that overflowed, a
state divergence the backend detects. A backend MUST NOT drop a
participant or track lifecycle event silently: past whatever bound it
keeps, it ends the session with a reason naming the loss instead. When
the session being ended still has a live connection — an overflow is not
a dropped link — the end MUST NOT be reported until the backend has
actually disconnected it: the report empties the registry and seats a
re-joined replacement, and issued early it puts two bots in one meeting.
A session whose disconnect cannot be completed is kept — registered,
reported present, refusing a replacement — and a later `leave()` retries.

Such an end is a **reported discontinuity**, and this specification is
explicit about what it does and does not recover. The events queued and
undelivered at the end are discarded, counted, and named in the reason;
the re-join's catch-up announces the conference's *current* state. What
happened entirely inside the outage window — a participant who joined
and left while the consumer was stalled — is not recoverable, by the
catch-up or by anything else. The per-participant lifecycle obligations
of this section apply to the events the backend delivered; across a
reported discontinuity, an implementation with disclosure or admission
obligations (Section 17.7) MUST treat the window as *unaccounted* rather
than as observed-and-empty — the reason string is the signal to do so.

A channel SHOULD attempt a bounded, backed-off re-join after any
reported end while the room remains attached and collecting — the ended
session was what received the frames and events, so no backend event can
produce the lazy join's "next need"; a later mint or delivery could, but
mid-meeting there may never be another of either.

**Frame delivery requirements:**

- `on_track_audio` MUST deliver decoded PCM as AudioFrames with a declared
  sample rate. The backend owns decoding (Opus, etc.).
- `on_track_video` SHOULD deliver raw frames. Backends MAY deliver encoded
  frames; the channel's VideoPipeline decoder stage (Section 12.8.4) then
  applies, reusing the existing `is_encoded` mechanic.
- Frames MUST be attributable: the ConferenceTrack passed with each frame
  carries the publishing `participant_id` and `room_id`.

**Frame publishing requirements:**

- `publish_audio` takes an AudioChunk (Section 12.3.11) — the outbound stream
  type, carrying decoded PCM rather than an encoded payload. AudioChunk names
  its own encoding in `format`, and a conference backend MUST reject a chunk
  that is not PCM rather than forwarding it to the SFU: encoding belongs to the
  backend, and a caller choosing the wire format would defeat the abstraction
  boundary below.
- `publish_video` takes a **raw** VideoFrame (`is_raw` true). The backend
  owns encoding, symmetrically with the decoding it owns on the inbound
  side. A backend MUST NOT require the framework to supply an encoded
  VideoChunk: not because the framework cannot encode — VideoEncoderProvider
  (Section 12.8.5) exists for VideoChannel's own transport path — but
  because deciding *which* codec to hand an SFU would put codec selection
  back into a framework interface, which the abstraction boundary below
  forbids. Avatar and other bot-video producers therefore emit raw frames.

Inbound tolerates encoded frames while outbound does not, and the asymmetry
is deliberate: an encoded inbound frame is self-describing and the
VideoPipeline decoder stage handles whatever arrives, whereas an encoded
outbound frame requires choosing a codec the SFU will accept before any
frame exists.

**Stopping playback (normative):** `stop_playback()` is the barge-in
gesture — the one call that says the room asked for silence *now*, rather
than at the end of whatever the transport has buffered. A participant who
cut the bot off is not asking for the queue to finish playing.

- A backend MUST immediately discard the bot-track audio it has accepted
  through `publish_audio()` but not yet delivered for playout. Audio that
  has already left the backend — buffered in the SFU or at clients — is
  beyond recall; a backend that queues locally SHOULD keep that queue
  small enough that the residue still reads as responsive.
- The call does NOT end the utterance. `is_final` remains the only
  boundary (Section 12.10.4): the closing chunk still follows, and a
  backend MUST accept it after the stop rather than treating the stop as
  having closed the utterance itself.
- The bot's track MUST remain usable: the next utterance publishes
  normally.
- A stop for a session the backend no longer holds — left, evicted,
  dropped — is a no-op, not an error: the silence the call asks for is
  already true of a session that is gone. This is deliberately unlike
  `publish_audio`, which refuses media for a session that is out; a
  refusal there protects a track from writes, and there is no track left
  to protect.
- There is deliberately no capability flag for this call. Every backend
  can discard at least what it still holds, and one that holds nothing —
  publishing synchronously into the SFU — simply returns. What varies
  between backends is the residue, not the meaning of the call.

**Mute transitions (normative):** `ConferenceTrack.muted` is the
publisher's own state, and a backend able to observe it change MUST keep
the record true to it and SHOULD report each transition through
`on_track_muted` / `on_track_unmuted`, with the record already updated
when the callback runs. The transitions are presence, not media — most
clients express "camera off" as a muted VIDEO track rather than an
unpublish, so a mute is often the only signal a camera toggle produces —
and they are subject to the same rule as every other callback here:
observable only through a connection.

**Track subscription:** the framework's subscription set is authoritative.
`subscribe_track()` / `unsubscribe_track()` are the only mechanism by which
the bot begins or stops receiving a track's frames, and a backend MUST NOT
deliver `on_track_audio` / `on_track_video` for a track the bot has not
subscribed to. Backends whose SDK auto-subscribes by default MUST disable
that behaviour for the bot session. The channel's subscription policy is
specified in Section 12.10.4.

**Bot grants:** `join_as_bot()` takes ConferenceGrants like `mint_access()`
does, because the bot's own permissions vary by AI participation pattern
(Section 12.10.6): a speaking bot needs `publish_audio`, an Observer bot is
`subscribe`-only with `hidden` set. A backend MUST apply them to the bot
session rather than assuming full permissions.

Where the permissive ConferenceGrants defaults are right for humans — whose
needs the framework cannot know — they are wrong for the bot, whose
behaviour the framework configured and therefore knows. An implementation
that derives the bot's grants SHOULD derive every one of them, `subscribe`
included: a channel with nothing to consume the tracks it would receive
subscribes to none (**Selective subscription**), and the grant is then
permission to receive every participant's media for nobody to read.

With BOT_GRANT_UPDATE, `update_bot_grants()` replaces a connected
session's grants in place: same session, same connection, subscriptions
and callbacks undisturbed — the SFU changes what the session may do,
which is what lets a hot-plugged voice speak without a re-join (Section
12.10.4, **Hot-plugging intelligence**). Calling it on a backend without
the capability MUST raise a configuration error rather than fail silently
or appear to succeed — the `unmute_track()` rule, for the same reason. A
backend MUST treat the grants it is given as the session's whole grant
set, not a delta.

`hidden` rides the grant set like every other field, and its two
directions are not equals. A backend SHOULD deliver a session's
hidden-to-visible transition to the clients already connected — LiveKit
announces the participant to them as newly joined, which is the
behaviour the channel's reveal path leans on (Section 12.10.4). No
backend is expected to retract a participant its SFU already announced:
there is no interface for un-telling a client, so the channel never
asks — a visible-to-hidden transition replaces the session instead
(Section 12.10.4).

**Display names:** `mint_access()` MAY be given the participant's
`display_name`, and a channel with a roster SHOULD pass the one on record.
It is presentation, never identity: attribution rides `participant_id`
alone, and a backend MUST NOT let a name stand in for it. A backend
SHOULD carry the name into the credential so the SFU's own clients render
the participant as the room named them, and SHOULD report it back on
`ConferenceParticipant.display_name`. A channel SHOULD use a reported
name to fill a roster record that has none — never to overwrite one the
integrator set — which is what returns names to a roster rebuilt from the
join's catch-up after a restart (Section 12.10.4 step 1): the credential
outlives the process that minted it, and the name rides the credential.

**Moderation:** `mute_track()` is always available. `unmute_track()` requires
the REMOTE_UNMUTE capability; calling it on a backend without that
capability MUST raise a configuration error rather than failing silently or
appearing to succeed. Implementations MUST NOT assume the two operations
are symmetric, and SHOULD surface the asymmetry to the integrator — a
moderation UI that offers unmute against a backend that refuses it is a
worse outcome than one that never offers it.

**Abstraction boundary (normative):** the interface deliberately omits SDP
negotiation, ICE, codec selection, simulcast/SVC layer control, and bitrate
management. A backend MUST NOT require the integrator or the framework to
handle any of these; they are internal to the SFU and its client SDKs.

**Required implementations:**

| Backend | Purpose |
|---|---|
| MockConferenceBackend | Unit testing with scripted participant/track event sequences |

Implementations MAY provide backends for any SFU whose server API can
satisfy this interface (e.g., LiveKit, Janus, Daily — informative).

#### 12.10.4 ConferenceChannel

The ConferenceChannel orchestrates a conference for a room. It owns the
ConferenceBackend, demultiplexes tracks into the existing audio and video
pipelines, and represents the AI's voice in the conference.

```
ConferenceChannel
├── channel_type: CONFERENCE
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── backend: ConferenceBackend
├── stt: STTProvider | null             # Per-track transcription
├── tts: TTSProvider | null             # AI voice via bot track
├── vision: VisionProvider | null       # Video/screen-share analysis
├── interruption: ConferenceInterruptionConfig
├── recording: ConferenceRecordingConfig | null   # Section 12.10.8
├── bot_identity: string                # Bot's display identity
├── bot_grants: ConferenceGrants        # Grants for join_as_bot()
├── default_grants: ConferenceGrants    # Grants minted for participants
├── e2ee: bool = false                  # Request E2EE (requires E2EE capability)
├── close_room_on_detach: bool = false  # Whether detach calls close_room()
└── speak_text_events: bool = false     # Speak inbound text from other channels
```

**Lifecycle:**

1. When the channel is attached to a room, the channel MUST call
   `ensure_room()`. It SHOULD call `join_as_bot(room_id, bot_identity,
   bot_grants)` lazily — on the first successful `mint_access()`, the
   first delivery, or the first participant or track event a backend able
   to observe one reports — and MUST fire `ON_SESSION_STARTED` and emit
   `conference_started` once the bot connection is live. Whatever the set
   of triggers, it MUST include at least one signal that does not depend
   on the backend's callbacks, and the first successful `mint_access()`
   is that signal: presence is observable only through a connection
   (Section 12.10.3), so a channel whose first join waits on an arrival
   is waiting on a callback that only the join itself would unlock — the
   bot never enters, and a meeting where humans speak and the AI is
   meant to listen is never transcribed. A mint is the framework's own
   advance notice that a human is about to connect, and it reaches the
   channel without the backend's help. The join it starts MUST NOT delay
   the mint's answer and MUST NOT fail the mint when the join itself
   fails: the credential belongs to the participant regardless of
   whether the framework got its own session into the room.

   The mint bootstraps a conference nobody has yet been admitted to; it
   cannot resume one already underway. An attach can land over a live
   conference — a channel restarted mid-meeting re-attaches above
   participants an earlier life admitted — and every trigger above is
   then out of reach: any re-join supervisor died with the process, no
   callback can arrive without a connection, and the humans already in
   the room may never mint again nor be delivered to. The trigger set
   MUST therefore also cover the conference's present occupancy at
   attach: after `ensure_room()`, the channel asks whether the
   conference already holds participants other than its own bot —
   `list_participants()` is the control-plane answer that requires no
   connection (Section 12.10.3); a persistent roster whose conference
   participants are still active MAY stand in for it or add to it — and
   a non-empty answer is a first need like any other. The probe and the
   join it may start MUST NOT delay the attach's answer, and their
   failure MUST NOT fail an attach the backend accepted: the lazy join
   remains behind them. Laziness is preserved — an empty conference
   stays unjoined, and a room nobody confers in costs one control-plane
   call per attach and nothing more. Without this trigger, a restart
   over a running meeting leaves it unheard for as long as nobody new
   is admitted, and the unaccounted window of Section 17.7 stretches
   without bound.

   The join exists for the intelligence. The bot's session is the
   framework's media access (Section 12.10.1 principle 4): subscribed
   tracks feed the pipelines through it, and the AI's voice is
   published on it. First need is therefore only a need when something
   configured on the channel consumes media — stt, vision, recording —
   or can speak — tts. A channel configured with none of these MUST
   NOT join on a mint, an arrival, or the occupancy probe, and SHOULD
   NOT make the probe at all: the join is the only consequence a probe
   can have. A delivery needs no guard of its own — without tts there
   is nothing to speak it with. An explicit `bot_grants` creates no
   need either: grants say what the SFU would let the bot do, not what
   the channel was configured to do, and a session justified by its
   privileges alone is a participant with no function — one server
   connection per conference, an unexplained name on the meeting's
   roster, and a Section 17.7 disclosure surface reporting a bot that
   collects nothing. Everything that is not the join stands:
   `ensure_room()` is still called, `mint_access()` still admits, and
   the participant records of step 2 are still written — the channel
   remains the room's admission gate and roster, which is exactly what
   a pure-transport deployment asks of it. The price is stated rather
   than hidden: the bot's connection is the event bridge (Section
   12.10.3), so with a backend that observes presence only through a
   connection, a conference this channel never joins produces no
   participant, track, speaker or quality callbacks, and the
   unaccounted window of Section 17.7 spans the whole meeting. An
   integrator whose obligations require attendance MUST configure a
   consumer or track attendance through its own client surface —
   joining a bot with nothing to consume just to keep the callbacks is
   the silent observer Section 17.7 exists to surface, and this
   specification declines to make it a mode. The standing-down is a
   state, not a sentence: the configuration it is read from can change
   while the channel runs, and **Hot-plugging intelligence** (below) is
   how a need arrives mid-meeting — bringing the join, the probe and the
   grants with it.
2. `on_participant_joined` MUST create or update the corresponding Room
   Participant record (Section 5.5, correlated per Section 12.10.2) and
   fire `ON_CONFERENCE_PARTICIPANT_JOINED`.
3. `on_track_published` MUST fire `ON_CONFERENCE_TRACK_PUBLISHED`, and MUST
   start a per-track processing lane (below) for tracks the channel
   subscribes to — an unsubscribed track never yields a frame, so it gets
   no lane (see **Selective subscription**). For SCREEN_SHARE tracks,
   `ON_SCREEN_SHARE_STARTED` fires additionally.
4. `on_track_unpublished` MUST tear down the lane, unsubscribe if
   subscribed, and fire the corresponding hooks.
5. When the channel is detached, the channel MUST call `leave()` and emit
   `conference_ended` **if a bot session is active** — the lazy join of
   step 1 may never have run — and MUST call `close_room()` when
   `close_room_on_detach` is set, whether or not a bot ever joined.

The SFU's own signals about the conference are relayed on their hooks
while the bot's session is connected: `on_active_speaker_changed` fires
`ON_ACTIVE_SPEAKER_CHANGED`, `on_connection_quality` fires
`ON_CONNECTION_QUALITY_CHANGED`, and `on_track_muted` /
`on_track_unmuted` fire `ON_CONFERENCE_TRACK_MUTED` /
`ON_CONFERENCE_TRACK_UNMUTED` — each naming the participant, and the
mute pair the track and its kind, since a muted VIDEO track is how most
clients say "camera off". None of these is collection — no media is read
to relay them — so none is gated by the binding's collection state, and
the bot's own tracks are excluded exactly as they are from every other
track event.

**One conference per room (normative):** principle 2's mapping is 1:1 in
both directions, and the attachment is where that is enforceable:
implementations MUST refuse to attach a conference channel to a room that
already has a channel of type CONFERENCE attached. A second conference
channel is a second bot session, a second transcription of every utterance
and a second AI voice speaking the same deliveries — duplicates the
roster, the transcript and the meeting have no way to express.
Re-attaching the *same* conference channel is not a second conference; it
remains an ordinary attach over a live attachment.

The reservation outlives the binding. A detach removes the binding at its
start and takes the bot out at its end, and a teardown can be deferred
past the detach that asked for it — so a check that reads only the
bindings admits a second conference while the first one's bot is still in
the meeting. The refusal MUST therefore hold for as long as the previous
conference channel still *holds* the room — a session active or on its
books, a teardown still running — not merely while its binding exists.
And it is a refusal, not a wait: the attach may be issued from inside the
very announcement the teardown is deferred behind, where waiting is a
deadlock. The caller retries once the teardown has ended.

**Bot self-exclusion (normative):** the bot is itself a conference
participant, and some backends report it back through
`on_participant_joined` or echo its published track. The channel MUST
ignore participant and track events whose participant identity matches the
active BotSession, MUST NOT create a Participant record for it, and MUST
NOT subscribe to a track it published. Without this rule the bot's own TTS
returns through a lane, the STT transcribes the AI's own speech, and the
AIChannel answers itself — a feedback loop the chain depth limit (Section
8.3) would only bound, not prevent.

**Closing and shared state (normative):** a conference channel's bookkeeping
lives in resources it does not own — the conversation store and the room lock
manager belong to the framework, which releases them after the channels
close. That order faces both ways, and each direction carries an obligation.

The channel's: `close()` MUST NOT wait without bound on anything the channel
does not own. Its own media plane comes first — admission closed, playbacks
stopped, the bot out of the conference, the backend closed — under bounded
budgets throughout, and the media calls are no exception: `leave()`, the
backend's own close and a lane's recogniser all end in code the channel
does not own, so each is cancelled past its budget, given a bounded grace
to unwind, and then abandoned and reported rather than waited for again.
Nothing an abandoned call was using is freed on its account, and past the
budgets the bookkeeping is not the channel's to wait for either. The
framework closes channels in sequence, so a channel waiting without bound
is not spending its own time: it is holding every channel behind it in its
conference, which is the failure the budgets exist to prevent.

There is one logical shutdown per channel. A `close()` that overlaps
another MUST join the shutdown already running rather than start a second:
concurrent callers await one shared attempt, and a caller being cancelled
cancels only its own wait — never the shutdown, whose steps the other
callers and the channel's own invariants still depend on. Once the
shutdown reaches its terminal result, that result is the channel's answer
for good: after a success, later calls MUST return immediately; after a
failure, later calls MUST reproduce the same terminal failure rather than
run the steps again. `close()` is a report of what the one shutdown
achieved, not a retry of it — retrying what failed (removing a session an
SFU refuses to release) is the operator's task the failure names.

Departures are exact-once. A session has at most one `leave()` in flight,
whatever path asked for it — a detach, an abandoned join, the channel's
close: a path that finds a departure already running MUST join that
attempt instead of issuing a second `leave()` for the same session. Two
concurrent `leave()` calls for one session ask the backend to remove a
participant twice, and whichever answer arrives second is about a session
that no longer exists.

An operation the shutdown abandons keeps what it was using. Every
resource an abandoned operation holds — the backend under a `leave()`
that swallowed its cancellation, the pipeline and recogniser under a
lane's recogniser call, the recorder under a finalisation — MUST stay
open until the operation has genuinely ended, however long past the
budget that is; the resource is closed then, off the shutdown's clock.
The current `close()` does not wait for it: the resource is reported as
retained and the close fails explicitly, because a close that neither
freed a resource nor said so has misreported the channel's state.

A close has succeeded only when all of the following hold: no session
remains on the channel's books; no operation the channel admitted is
still running; every resource the channel owns is closed; and every
failure met along the way was surfaced in the close's result rather than
in a log alone. A close missing any of these MUST fail, whatever its
steps individually reported.

Failing to remove a session is failing to close. A session still on the
channel's books when every step has run — a `leave()` the SFU refused, or
one a budget had to cancel — MUST be raised, by name, at the very end of
`close()`, not summarised into a log: a close that returns cleanly while a
bot may still be listening to a meeting misstates the one thing the roster
exists to answer. The channel goes on reporting the session, and removing
it is an operator's task. For the same reason a channel whose `close()` fails MUST NOT
prevent the channels after it from closing — and MUST NOT be reported as
a success either. The failure is surfaced to the caller once the shutdown
has run to completion: a channel that failed to close may still be
holding its media — a bot possibly still in a meeting, listening — and a
shutdown that returns cleanly over that turns a logged error into an
operational and disclosure risk.

The framework's: `close()` MUST NOT release the store or the lock manager
while an operation issued through them is still in flight. An operation a
shared resource has been given cannot be taken back, and releasing the
resource underneath it does not stop the work — it arranges a failure for a
write that was already accepted. So the wait for such operations belongs to
the owner of the resources, and it comes after every channel has closed and
every channel's media is released, where a slow store costs the shutdown its
latency and nothing else. There it is bounded by nothing, because there is
no third option: giving up on the wait *is* releasing the resource under the
operation.

Two boundaries keep that promise finite. It covers the operations the
framework and its channels start of their own accord — participant
callbacks, roster bookkeeping, announcements — which never suspend in
integrator code while holding the resources, so the wait terminates. An
operation the *integrator* starts through the public API is the
integrator's to order against `close()`, as with any resource-owning
library: the framework does not hold its shutdown open for a call the
caller left suspended across it. And the wait has an end: once it
concludes, the resources are sealed. Work that was suspended somewhere the
shutdown could not see — a callback parked in a backend past every closing
budget — and that resumes afterwards MUST be refused with an error naming
the shutdown, never run against a resource being released.

**Admitting participants:** the channel exposes `mint_access()` for a
participant of the room, applying `default_grants` unless the caller
overrides them. The integrator delivers the resulting ConferenceAccess to
the client application through its own surface (Section 16); the framework
does not serve it. ConferenceGrants defaults are permissive so the common
case works unconfigured; narrowing them is the integrator's call and is
RECOMMENDED wherever a role does not need to publish — a listener-only
attendee SHOULD receive grants without publish permissions (Section 17.7).

`mint_access()` MUST NOT issue a credential for a room the channel is no
longer attached to, and the check MUST hold across every await the call
makes. Minting is not a read: the token is honoured by the SFU, the
ConferenceBackend contract offers no revocation, and a check that was true
before a roster lookup and false after it has already handed out admission
to a conference the framework has left. Implementations MUST therefore
treat the mint as work a detach cannot land in the middle of — the
in-flight-work discipline of Section 12.10.4 — rather than as a precondition
tested once.

A bounded drain does not satisfy this on its own. Every other kind of
in-flight work degrades gracefully past the deadline — a chunk arrives late,
an event lands out of order — and a credential does not: it stays valid for
as long as it says it does, against a conference the framework has left. So
a mint still in flight when the deadline passes MUST be taken back rather
than left behind: implementations MUST cancel the outstanding backend
request, and MUST re-read the attachment when a request that survived
cancellation returns, refusing to hand the credential on. Refusing is not
revocation, and implementations SHOULD say so — the backend may have
recorded a credential nobody received, and only the operator can decide
whether it needs revoking there. `close()` carries the same obligation
before it closes the backend.

**Per-track audio lanes:**

```
on_track_audio (one lane per AUDIO track)
  → Resampler → [AGC] → [Denoiser] → VAD → STT (streaming)
  → transcription RoomEvents attributed to the publishing participant
```

The lane preserves the inbound stage ordering of Section 12.3, minus the
stages a conference makes unnecessary: AEC (no server-side echo path) and
Diarization (track identity already attributes speech).

A transcription enters the inbound pipeline under the identity its track was
published under, which is a room `Participant.id` and not an address. Identity
resolution therefore MUST NOT run per utterance (Section 11.6, case 1): a
conference resolves when a participant *arrives* and the address its provider
attached is there to resolve (Section 12.10.2), and speaking again asks nothing
new. Running it anyway resolves on the backend's opaque identity — what rule 3
rules out — and fails as rule 3 says it would: UNKNOWN every time, so
`ON_IDENTITY_UNKNOWN` fires per utterance and an implementation refusing
unknown senders there discards the transcripts of a participant it identified
on arrival.

Each AUDIO track gets its own lane, holding its stage state under the stream
identity contract of Section 12.3 with the track as the stream key. That
independence is a property of the **state**, not of the instances: one
pipeline serves every lane. Instantiating a pipeline per track buys no
isolation the stream key does not already provide, and costs a denoiser
model loaded once per participant.

Within a lane:

- Format normalisation MUST run before the other stages. Participants
  negotiate their own formats with the SFU, so tracks arrive in whatever
  each publisher sent, while every stage downstream assumes one format.
  This is the Resampler position of Section 12.3.
- VAD MUST be present. It is what divides the stream into utterances, and
  without it the lane has no utterance to speak of: it calls the recognizer
  once per frame, spending a round trip per 20 ms and producing a transcript
  cut at frame boundaries instead of at turns. An implementation given a
  recognizer and no VAD MUST refuse the configuration rather than degrade to
  per-frame recognition.
- AEC MUST NOT be required (no server-side echo path — Section 12.10.1).
- Diarization MUST NOT be required (track identity provides attribution).
- AGC and Denoiser MAY apply per lane.
- `ON_TRANSCRIPTION` fires per lane; the hook context identifies the track
  and participant.
- `ON_SPEECH_START` and `ON_SPEECH_END` fire per lane at the VAD's own
  utterance boundaries, naming the publishing participant and track. They
  are the real-time answer to "who is speaking right now": the
  dominant-speaker signal cannot say that nobody is (its interface carries
  one identity), and the transcription arrives only after the recognizer's
  round trip. An unsubscribed track has no lane and therefore no speech
  events — this is collection, and the binding's gate applies.

**Lane isolation:** processing one track MUST NOT delay frame delivery for
any other. A backend hands frames to its subscribers in sequence, so a lane
that does its work — speech recognition above all — inside the delivery
callback makes one provider's latency into every participant's latency, and
one slow track stalls the whole conference. A lane therefore accepts a frame
and returns, doing its work on its own schedule.

This is what separates a lane from a callback, and unlike the stage list it
is observable from outside: an implementation can be checked by delaying
recognition on one track and measuring frame delivery on another.

**Overload:** a lane accepting frames faster than it processes them MUST
bound what it holds. An unbounded backlog turns a slow recognizer into
unbounded memory and a lag behind the live conversation that only grows.

Which audio to discard is a genuine trade-off, and this specification does
not settle it. Dropping the oldest frames keeps the lane near live at the
cost of a gap mid-utterance; dropping the utterance in progress and
resynchronising loses more audio but never emits a transcript stitched
across a hole. Implementations MUST document which they do, and MUST expose
how much was discarded — an integrator who cannot see the loss will read a
damaged transcript as a bad recognizer.

**Per-track video lanes:**

VIDEO and SCREEN_SHARE tracks route through the VideoPipeline (Section
12.8.4) — decoder (if needed), transforms, filters, vision analysis.
VisionResults are attributed to the publishing participant and feed
`setup_video_vision()` AI integration unchanged.

**Selective subscription:** the channel MUST call `subscribe_track()` only
for tracks it consumes, and MUST NOT rely on backend auto-subscription
(Section 12.10.3). AUDIO tracks are subscribed when STT, recording, or
speech-to-speech composition is configured. VIDEO and SCREEN_SHARE tracks
MUST NOT be subscribed unless a VisionProvider or framework-side video
recording is configured — otherwise no video frame ever reaches the
framework process. Tracks published by the bot itself are never subscribed
(**Bot self-exclusion** above). Backends MAY subscribe to a reduced
simulcast layer for vision analysis; this is provider-internal.

Subscription is re-evaluated when configuration changes at runtime: adding
a VisionProvider to a live conference MUST subscribe the already-published
video tracks, and removing the last consumer of a track MUST
`unsubscribe_track()` it.

**Hot-plugging intelligence (normative):** the configuration first need is
read from — stt, tts, recording, and vision where an implementation
carries it — is not fixed at construction. Implementations MUST let each
be plugged into and unplugged from a running channel, as explicit
per-kind operations rather than bare attribute assignment: a plug can put
a bot into a live meeting and an unplug can take one out, and an
operation with consequences of that order needs a surface whose refusals
and effects have somewhere to land. This is principle 7 (Section 18)
reaching the conference's intelligence, and it is the other half of the
pure-transport contract of step 1: a meeting can begin purely human and
gain its notetaker when the host asks for one — the explicit gesture a
consent obligation wants (Section 17.7) — and lose it again the same
way, without the channel being rebuilt around either.

Plugging a need is a first need. The lazy-join triggers of step 1 answer
"has the conference started to matter"; a plug answers "has the channel
started to care", and the two compose: if the channel is attached and
holds no session, the occupancy probe of step 1 MUST be re-run at the
plug — the join is once more a consequence a probe can have, so the
probe's justification returns with the need — and a conference already
holding participants is joined at once. An empty conference stays
unjoined: laziness is preserved, and the mint, delivery and arrival
triggers stand ready as on any configured channel. The join a plug
starts follows the discipline of every trigger before it: its failure
MUST NOT fail the plug — the configuration stands, and the lazy join
remains behind it. What a plug refuses, it refuses for the reasons
construction does, held identically at runtime: the E2EE exclusions
(Section 12.10.2) gate a plugged stt or recording exactly as a
constructed one, and a recording plugged without a recorder is refused
wherever it is asked. A plug into a slot already holding a provider MUST
be refused rather than replace it: a swap of streaming intelligence is a
teardown and a rebuild whatever single verb offers it, and the
observation gap belongs in the open — unplug, then plug. Unplugging an
empty slot is a no-op: the state the caller asked for already holds.
Configuration changes are serialised per channel: implementations MUST
NOT let two interleave, since everything below — the grants derived, the
subscriptions re-evaluated, the join or leave decided — is read from the
configuration as a whole.

A plugged consumer reaches back. **Selective subscription**'s runtime
clause is the mechanism: an stt or recording plugged mid-meeting MUST
subscribe the already-published tracks it consumes, and their lanes open
as for any subscription — the meeting is transcribed from the plug
forward, not from the next publication. An unplug re-evaluates the same
way: lanes close and tracks are unsubscribed when nothing else consumes
them, recordings are finalized and announced exactly as a detach
finalizes them, and an utterance in flight when the voice is unplugged
is ended as a live conference ends one — `stop_playback()` and a
terminal chunk (**One utterance at a time**), since the bot is still in
the meeting and the turn genuinely ended. Who closes an unplugged
provider follows the channel's one provider-ownership rule, the same
that governs its `close()`.

Unplugging the last need takes the bot out. A session kept past the last
consumer and the last voice is the participant with no function step 1
declines to admit — the silent observer of Section 17.7, now with a
connection it was given back when it had a purpose — so the channel MUST
leave, with `conference_ended` announced, and stand down exactly as a
channel constructed pure-transport: triggers quiet, probe unmade, the
admission gate and roster still on duty. The round trip is the point:
transport-only to intelligent and back is a lifecycle the channel
serves, not two deployments.

The session's grants MUST cover the configured needs, at the join and
across every change. Derived grants (Section 12.10.3, **Bot grants**)
are derived from the configuration in force at the join, not at
construction. A plug that widens what a live session must be able to
do — a voice plugged onto a listening bot needs `publish_audio`; a
consumer plugged onto a speaking bot needs `subscribe` — MUST bring the
session's grants in line before reporting the plug complete: through
`update_bot_grants()` where the backend declares BOT_GRANT_UPDATE — the
session, its subscriptions and the event bridge all survive — and
otherwise by re-joining, a `leave()` and a `join_as_bot()`, each
announced as the session event it is, because a session the SFU will not
re-permission can only be replaced. An unplug that narrows the needs
SHOULD narrow the grants in place where the backend can, and MAY leave
them standing where it cannot: an unused privilege against a cut in the
event bridge is a trade this specification settles for continuity.
Explicit `bot_grants` are never rewritten by a plug or an unplug — the
caller who set them took coverage on themselves (Section 12.10.3), and
that holds at runtime exactly as at construction.

**Runtime ownership of explicit grants (normative):** that the plugs
never rewrite an explicit `bot_grants` does not make the grant set
immutable — it makes it *owned*. The owner is the caller who set it, and
implementations MUST give that caller a runtime operation that replaces
the explicit grant set on a running channel, serialised with the plugs
under the same configuration-change discipline. Replacing an explicit
set with another explicit set carries the construction-time bargain
forward unchanged: the caller took coverage of the configured needs on
themselves, so a replacement that does not cover them — `subscribe`
withdrawn under a plugged recognizer — is accepted exactly as
construction would accept it, not refused. The coverage rule of this
section binds *derived* grants only, at the setter as at the join.
Replacing the explicit set with nothing returns the channel to
derivation: from there the grants follow the configuration in force,
exactly as on a channel that never had an explicit set — the round trip
is available here as everywhere else in this section. Grants remain
channel-wide in this revision, as the rest of the channel's
configuration is; per-conference grants are not modelled. An explicit
set still creates no need (step 1): a set on a channel with no consumer
and no voice changes what the next session would be allowed, and joins
nothing.

The setter is an instruction, not a hint. Where the alignment a plug
makes may leave a narrowing standing — an unused privilege traded for
continuity — the setter's change MUST be applied in full: through
`update_bot_grants()` where the backend declares BOT_GRANT_UPDATE, and
by the announced re-join otherwise or when the in-place update fails,
whatever the direction of the change. A privilege the caller asked to
withdraw is not an unused privilege; it is an ignored order. A caller
who prefers continuity to the change expresses that by not calling. An
implementation MUST let the caller learn *before* calling whether the
change will be applied in place or cost the event bridge a re-join —
the capability is consultable on the backend, and the channel's
disclosure surface SHOULD answer it directly.

Visibility is the one grant the SFU's clients are told about, and it
does not move symmetrically (verified against LiveKit): an SFU that can
announce a newly visible participant to the clients already connected
delivers a *reveal* in place, but no interface exists to un-tell them —
a session re-hidden in place stays on the roster of every client that
saw it. A hidden-to-visible transition is therefore applied like any
other change: in place where the backend can (Section 12.10.3). A
visible-to-hidden transition MUST be applied by replacing the session,
whatever the backend's capabilities: the announced leave *is* the
retraction, and it is the only one every backend can deliver.

When a connected session's effective grants change — in place, or
carried by the replacement session of the re-join — the implementation
MUST emit `conference_bot_grants_changed` (Section 12.10.7): with an
in-place update nothing else says anything happened, and the code that
asked for the change and the code that renders the room are rarely the
same component. A set that changes nothing emits nothing.

The disclosure surface follows the configuration, not the constructor.
Section 17.7 already requires that whether STT, vision or recording is
active be observable at any time; with hot-plugging the *configured*
half of the answer moves too, and an implementation's surface MUST
report the configuration in force, not the construction — a meeting that
gained a transcriber mid-way reads as transcribed from that moment, and
one that lost it reads as clean.

**Outbound (deliver):**

When a broadcast event reaches the conference binding and TTS is
configured, the channel MUST synthesize once (BEFORE_TTS / AFTER_TTS hooks
apply) and publish the audio on the bot track via `publish_audio()`. The
SFU distributes it to all participants. Targeted per-participant audio is
NOT supported in this revision: one bot track, heard by all.

**One utterance at a time (normative):** the channel MUST NOT interleave the
chunks of two utterances on the bot track. There is one track and the SFU
mixes nothing for it, so two utterances published together do not arrive as
two voices — they arrive as one stream that is intelligible as neither.
Nothing upstream guarantees this on the channel's behalf: an implementation
whose broadcast pipeline serialises per room (Section 10.1) may still
consume a streaming response outside that serialisation, so the single track
is the channel's own to protect. Whether a second utterance waits for the
first or replaces it is left to the implementation — both are defensible, and
they differ in whether an answer the AI produced may go unheard.

Every utterance the channel publishes MUST end with a chunk whose `is_final`
is set, **including one cut short by a barge-in** (Section 12.10.5). This is
what makes `is_final` a boundary a backend can rely on rather than a hint:
without it, an interrupted utterance leaves the SFU believing the bot is
still mid-sentence. The closing chunk MAY carry no audio (`data` empty) —
there is nothing left to play, only an end to declare — and backends MUST
accept one.

The closing chunk is a boundary, not a flush. An utterance cut short and
one that ended by itself close identically, so a backend MUST NOT discard
queued audio on `is_final` — a synthesizer whose real ending is already
queued behind an empty final chunk would lose it. What silences the room is
`stop_playback()` (Section 12.10.3): when an interruption lands, the
channel MUST call it on the session the utterance is publishing on, so the
audio the transport already holds is discarded rather than played out to
the end of whatever buffer holds it. The call and the closing chunk are two
different statements — the gesture that stops the sound, and the boundary
that ends the turn — and the channel owes the backend both. No ordering is
required between them: the closing chunk of an interrupted utterance
carries nothing a flush could truncate.

There is exactly one exception, and it is the end of the session rather than
the end of an utterance: an utterance the channel abandons because it has
**left the conference** — a detach, or the channel closing — MUST NOT be
closed with a terminal chunk. The bot session that chunk would name is on its
way out of the conference and may already be gone, so publishing into it is
either a write to a session the framework has left or a race with `leave()`.
The framework cannot honour the guarantee here in any case: the process may
also have crashed, the network may have dropped, and no in-band marker
survives either. So a backend MUST treat `leave()`, and a session's
disconnection by any other means, as terminating whatever utterance was in
flight on it — the same way it already has to treat the connection dropping.
An utterance interrupted by a participant is not this case and is still
closed: the conference is live, the bot is in it, and the turn genuinely
ended.

By default only AI/agent responses are spoken. When `speak_text_events` is
true, inbound text events from other channels (SMS, WebSocket, ...) are
also spoken into the conference.

This default deliberately diverges from VoiceChannel, which speaks every
TextContent it receives (Section 12.3). A 1:1 voice session has one
listener who is the conversation's subject; a conference is a multi-party
meeting where unrelated channel traffic read aloud is disruptive to
everyone at once. The restrictive default is therefore normative, not a
convention: implementations MUST NOT speak non-AI text events unless
`speak_text_events` is set.

#### 12.10.5 Multi-Party Interruption Policy

In a 1:1 voice session, any user speech may interrupt TTS playback
(Section 12.6). In a conference, *who* can interrupt the AI is policy:

```
ConferenceInterruptionConfig
├── strategy: InterruptionStrategy = IMMEDIATE   # Section 12.6 semantics
├── scope: "any" | "none" | "allowlist" = "any"
└── allowlist: list<participant_id> = []
```

- `"any"` — speech detected (VAD) on any audio track interrupts bot
  playback, subject to the configured InterruptionStrategy.
- `"none"` — the bot always finishes speaking (presentation/IVR style).
- `"allowlist"` — only listed participants can interrupt (moderator
  pattern).

Backchannel detection (Section 12.6) applies per track before
interruption evaluation. An interruption that lands is more than the chunk
stream stopping: the channel calls `stop_playback()` so the audio the
transport already holds is discarded instead of playing on over the
participant (Sections 12.10.3 and 12.10.4). `ON_BARGE_IN` fires with the
interrupting participant identified.

#### 12.10.6 AI Participation Patterns

**STT/TTS (default).** Per-track STT lanes produce attributed
transcription RoomEvents; an AIChannel in the room responds through the
normal broadcast pipeline; the response is spoken via the bot track. The
AI requires no conference-specific mechanics and sees a fully attributed
multi-speaker transcript.

**Speech-to-speech (OPTIONAL).** A RealtimeVoiceProvider (Section 12.4)
may be composed with a conference: subscribe to all AUDIO tracks, mix
N→1, feed the provider, and publish its audio output on the bot track.
Section 12.10.12 specifies the composition — the mixing rule, where
attribution ends, how the provider's voice meets the utterance contract,
and how it crosses the interruption policy. Per-speaker attribution is
lost at the provider boundary; implementations SHOULD run per-track STT
lanes in parallel when transcripts are required.

**Observer.** A bot joined with `bot_grants` set to subscribe-only and
`hidden`, with STT lanes but no TTS — transcription, compliance
monitoring, or meeting summarization without a voice presence. Whether a
silent transcribing bot may stay invisible to participants is a legal
question, not a framework one; this specification does not restrict
`hidden`, and Section 17.7 sets out what the framework exposes so the
integrator can meet the disclosure rules that apply to it.

#### 12.10.7 Conference State Events

**Hooks** (Section 9.2): `ON_CONFERENCE_PARTICIPANT_JOINED`,
`ON_CONFERENCE_PARTICIPANT_LEFT`, `ON_CONFERENCE_TRACK_PUBLISHED`,
`ON_CONFERENCE_TRACK_UNPUBLISHED`, `ON_ACTIVE_SPEAKER_CHANGED`.
Screen-share track publication additionally fires the existing
`ON_SCREEN_SHARE_STARTED` / `ON_SCREEN_SHARE_STOPPED`.

The track triggers carry the `CONFERENCE_` prefix to keep them distinct
from `ON_VIDEO_TRACK_ADDED` / `ON_VIDEO_TRACK_REMOVED` (Section 12.8),
which describe tracks within a single VideoChannel session rather than
publications by other participants in a conference.

**Ephemeral events** (Section 8.4): high-frequency media state MUST NOT be
stored as RoomEvents; implementations SHOULD publish it via the
RealtimeBackend instead:

- `conference_track_muted` / `conference_track_unmuted`
- `conference_active_speaker`
- `conference_connection_quality`

**Framework events** (Section 8.2), with their emission points:

| Event | Emitted when |
|---|---|
| `conference_started` | `join_as_bot()` completes and the bot connection is live — the same point as `ON_SESSION_STARTED` |
| `conference_ended` | `leave()` completes on channel detach |
| `conference_participant_joined` | A Participant record is created or reactivated from `on_participant_joined` |
| `conference_participant_left` | `on_participant_left` is processed |
| `conference_bot_grants_changed` | A connected session's effective grants changed (Section 12.10.4): replaced in place through `update_bot_grants()`, or carried in by the replacement session of the announced re-join. Carries `bot_session_id` and the session's `hidden` status |

`conference_started` tracks the framework's own media presence, not the
existence of the SFU room: `ensure_room()` MAY have run much earlier, and
human participants MAY be conferring before the bot joins.

`conference_ended` MUST carry the `bot_session_id` of the session that left.
A detach whose destructive half is deferred (Section 12.10.4) can complete
after the room has been re-attached and a second bot has been announced, so
the end is not always the last conference event a room emits; without the
session identifier an observer cannot tell which conference it is the end
of. The same identifier appears on `conference_started`, and pairing them is
the only ordering guarantee available in that case.

#### 12.10.8 Recording

```
ConferenceRecordingConfig
├── mode: "framework" | "egress" = "framework"
├── storage: string                     # Integrator-defined identifier
├── format: string (default "wav" for audio, "mp4" for composed video)
└── metadata: map<string, any>
```

- **framework** (default) — bot-subscribed tracks are recorded through the
  room media recorder interface (Section 12.11), one recording per track.
  This is the path that always works: it needs no
  backend capability, it functions against MockConferenceBackend, and the
  recording is written wherever the implementation writes it, which matters
  where data residency is constrained. Since audio tracks are already
  subscribed for STT (Section 12.10.4), recording them adds a file write and
  no additional media subscription.
- **egress** (OPTIONAL) — recording is delegated to the SFU, and requires
  EGRESS_RECORDING. Configuring it on a backend without the capability MUST
  raise a configuration error. This mode exists for one reason: a
  **composed** video recording — grid or active-speaker layout — cannot be
  produced by the framework without subscribing every video track, decoding
  all of them, compositing and re-encoding, which is exactly the media-plane
  work Section 12.10.1 forbids. Delegating it is the only conforming way to
  obtain it.

Egress carries **no unified result contract**. The framework does not
promise a RecordingResult or `ON_RECORDING_STOPPED` for a delegated
recording: the SFU announces completion out of band — typically a webhook to
an endpoint the framework does not host — and reaching back into that flow
would require either provider-specific payloads inside the backend interface
or polling the SFU's job API. An integrator that opts into egress collects
its output through the provider's own mechanism. Switching between the two
modes is therefore not a transparent configuration change, and
implementations SHOULD document it as such.

**Recorder mapping.** AudioRecorder (Section 12.3.7) and VideoRecorder
(Section 12.8.10) are specified around a session: `record_inbound` /
`record_outbound`, an INBOUND_ONLY | OUTBOUND_ONLY | BOTH mode, a handle
carrying a `session_id`. A conference has no session and no single inbound
direction — it has N attributed tracks plus one bot track — so neither
interface applies to it, and neither changes on its account. Framework-mode
conference recording binds to MediaRecorder (Section 12.11) instead, which
is addressed by track and already carries the attribution.

An implementation recording a conference in framework mode MUST:

- Open **one recording per subscribed track**: one `on_recording_start()`
  carrying exactly that track. A conference gains participants while it
  runs, and a recording that admits its tracks only at the start cannot
  record a late arrival — MP4, the usual container, refuses a new stream
  once muxing has begun. Per-track recordings also make "who said what" a
  property of the output rather than of a mixing decision.
- Attribute every track: `RecordingTrack.participant_id` carries the
  publishing participant as Section 12.10.2 resolved it, and `channel_id`
  the conference channel.
- Declare the format that track actually carries — `codec`, `sample_rate` and
  `channels` describing the frames the backend delivered, not the format the
  framework normalizes to elsewhere. Section 12.10.3 obliges a backend to
  deliver decoded PCM with a declared sample rate; it obliges no two
  participants to agree, so a conference of three may carry three formats,
  and the first frame of a track is where its own is known.
- Record the bot's published track as **its own attributed track**, never
  mixed into a participant's. The bot track is the only one that resembles
  an outbound direction, and treating it as one would make the framework mix
  media it was given separately. What the AI said is part of what was said.
- End a track's recording when that track ends — unpublished, unsubscribed,
  or the conference left — without ending the others.
- Stop recording when the room binding stops permitting collection, on the
  same gate as transcription (Section 12.10.4). Recording is collection.

**A recording is opened on a format.** That declaration is made once, on the
frame that opens the track's recording, and a container fixes its streams at
the first write — so a later frame in another format has no honest place in
it. An implementation MUST NOT write one anyway: it is discarded, reported
through the same loss the overload bound owes below, and said in the log. A
recording missing the seconds where a publisher renegotiated has a defect
anyone can see; one that wrote them is a file that opens and lies.

**Writing is not the callback's work.** Recording a track MUST NOT delay
frame delivery for any other. This is the lane isolation rule of Section
12.10.4, and it applies to the recorder for the same reason it applies to
the recogniser: the backend hands frames to its subscribers in sequence, so
an encode and a file write performed where the frame arrives makes one
track's storage latency into every participant's delivery latency. That the
recorder interface is synchronous (Section 12.11) does not exempt it — it is
what makes the obligation bite, since a caller cannot await its way out of a
blocking write and MUST therefore get it off the delivery path altogether.

An implementation MUST bound what it holds for a track whose writes fall
behind, MUST document which audio it discards when that bound is reached, and
MUST expose how much it discarded — the same three obligations Section
12.10.4 places on a lane's backlog, and for the same reason: a recording with
a hole in it that nothing reports reads as a defective recorder.

What is still queued when a track's recording ends MUST be written before the
recording is finalized, within a bounded budget. A container closed over
frames that were still in flight is not a truncated recording but a
misleading one — it ends early and says nothing about it — and a budget is
what keeps a recorder that has stopped draining from holding the teardown, and
with it the bot, in the conference. What the budget could not write is loss,
and is reported as such.

**Reporting the result.** A framework-mode recording ends with a
`MediaRecordingResult` naming where it was written, and the framework SHOULD
report it: `ON_RECORDING_STARTED` when a track's recording opens,
`ON_RECORDING_STOPPED` when it ends, carrying that result — the same pair
Section 12.3.7 fires for a session. Without it an integrator has files on a
disk and no programmatic way to learn their paths: the recorder's return
value stops inside the framework, and a log line is not an interface.

Per track, not per conference. The recording *is* a track, and the tracks of
one meeting do not end together — a participant who leaves halfway through
has a finished recording while the meeting continues. A single report at the
end would have to hold every earlier result until then, and would arrive
after the point where an observer could have acted on it. An integrator
wanting the meeting's full list accumulates it by room, which is state it
was going to keep anyway.

The report carries the attribution the result alone need not: the room, the
track, and the participant publishing it as Section 12.10.2 resolved it.
Both hooks are ASYNC — a recording already written is a fact, not a decision,
and nothing about it is a hook's to block. A track subscribed but never
published on reports nothing at all: the recording opens on the first frame,
so silence produces no file and no pair of hooks describing one. Egress mode
fires neither, for the reason given above — it promises no result contract.

How many files come out is the recorder implementation's decision: the
framework guarantees attribution, not file layout. A recorder MAY write one
file per track or mux several — it is handed the tracks separately and
attributed, so either remains open to it.

Video tracks take the same shape where an implementation records them
(`RecordingTrack.kind` distinguishes them), which is per-track and therefore
never a composed recording. A grid or active-speaker layout stays egress
territory, for the reason given above.

#### 12.10.9 Cross-Channel Integration

Because the conference is a room, integration with other channels requires
no new mechanism:

- **Transcripts broadcast everywhere.** Transcription RoomEvents flow
  through the broadcast pipeline (Section 10.2) to every bound channel — a
  WebSocket or messaging binding receives a live, attributed meeting
  transcript for free.
- **Text can be voiced in.** With `speak_text_events`, a message arriving
  from any channel is spoken into the conference by the bot.
- **AI is just an AIChannel.** Responding to transcripts, summarizing on
  close (ON_ROOM_CLOSED), or steering via hooks all use existing
  primitives.
- **SIP/PSTN interop (OPTIONAL).** Backends with SIP_GATEWAY MAY admit
  phone participants directly. Alternatively, an implementation MAY bridge
  an existing VoiceChannel SIP session into the conference by republishing
  its audio as an additional bot participant (audio-only gateway). A phone
  participant admitted by the SFU is the canonical case of a participant
  the framework did not name: its caller number arrives in
  `ConferenceParticipant.metadata` and MUST reach identity resolution
  (Section 12.10.2), so that dialling into a conference identifies the
  caller as reliably as messaging the room would. A gateway is also where
  the provenance rule earns its keep: the number the trunk reported is a
  fact the SFU established, and a backend admitting phone participants
  SHOULD say so through `asserted_metadata` — otherwise the one address the
  framework can act on is indistinguishable from one a client typed.

#### 12.10.10 Relationship to Audio Bridging (Section 12.7)

| Criterion | AudioBridge (12.7) | Conference (12.10) |
|---|---|---|
| Media plane | In-process (framework forwards/mixes) | External SFU |
| Media types | Audio only | Audio + video + screen share |
| Scale | Small rooms (default max 10) | SFU-bound (typically dozens+) |
| Infrastructure | None | SFU deployment required |
| Participants | Any VoiceBackend session (SIP, RTP, ...) | SFU-native clients (+ SIP gateway) |
| Use when | Phone bridging, call center, small audio conf | Video conferences, AI in meetings |

Both MAY coexist in one implementation. They do not share interfaces:
AudioBridge operates on VoiceSessions; conferences operate on
ConferenceTracks.

#### 12.10.11 Conformance

Conference support is part of **Conformance Level 3 (Real-Time Media)**
and is OPTIONAL. It is STABLE (see the status note above).

Implementations that support conferencing MUST:

- Implement the ConferenceBackend interface with a Mock implementation.
- Map each conference 1:1 to a Room.
- Keep the framework out of the human-to-human media path.
- Deliver decoded, participant-attributed, room-attributed PCM audio per
  track.
- Correlate `participant_id` across the backend boundary per Section
  12.10.2, including the `external_id` fallback for participants the
  framework did not mint, and surface provider participant attributes so
  their resolvable addresses reach identity resolution — on arrival rather
  than on first utterance, with the answer linked to the participant by
  `identity_id` rather than re-keying it.
- State which participant attributes the SFU itself asserts, leaving
  `asserted_metadata` null where the backend cannot tell, and resolve
  identity only on those — never on an attribute a client supplied, unless
  an integrator configured that explicitly (Section 12.10.2).
- Record provider attributes on the Participant under a dedicated key rather
  than merged into the integrator's own `metadata`, keeping their provenance
  and bounding what is persisted (Section 12.10.2).
- Gate `unmute_track()` on the REMOTE_UNMUTE capability, raising a
  configuration error rather than failing silently where it is unsupported.
- Subscribe explicitly: consume only tracks passed to `subscribe_track()`,
  and never auto-subscribe the bot session.
- Exclude the bot's own participant and tracks from Participant records,
  lanes, and subscriptions.
- Run per-track STT lanes emitting attributed transcription RoomEvents, one
  per utterance rather than one per frame (Section 12.10.4).
- Keep lanes independent: no track's processing delays frame delivery for
  another.
- Bound each lane's backlog, document what it discards under overload, and
  expose how much it discarded.
- Publish AI TTS as a single bot track (synthesize once, publish once).
- Publish bot media as decoded frames — PCM AudioChunk, raw VideoFrame —
  leaving encoding to the backend.
- Where framework-mode recording is offered, record one attributed recording
  per track — the bot's own included, unmixed — describing the format that
  track actually carries, and stop it on the same collection gate as
  transcription (Section 12.10.8).
- Keep those recordings off the delivery path: write outside the frame
  callback, bound each track's write backlog, document what it discards and
  expose how much, and flush what is queued before finalizing (Section
  12.10.8).
- Fire conference lifecycle hooks and create/update Participant records
  from conference events.
- Treat ConferenceAccess as opaque.
- Either admit the bot to E2EE key exchange or refuse media-intelligence
  configuration on E2EE conferences (Section 12.10.2).
- Expose bot presence, `hidden` status, and whether STT/vision/recording is
  active, so integrators can satisfy their own disclosure obligations
  (Section 17.7). The specification mandates no disclosure policy.

Implementations SHOULD:

- Support vision analysis on VIDEO and SCREEN_SHARE tracks.
- Surface active speaker and connection quality as ephemeral events.
- Record conferences through the framework recorder path by default,
  treating SFU egress as an optional delegation with no result contract
  (Section 12.10.8).
- Report each framework-mode recording where it opens and where it ends —
  its result, its track and its participant — rather than leaving the
  integrator to find the files (Section 12.10.8).
- Enforce ConferenceInterruptionConfig scope.

Implementations MAY:

- Publish bot video (avatar embodiment, requires VIDEO_PUBLISH).
- Compose speech-to-speech providers via N→1 mixing (Section 12.10.12).
- Bridge SIP sessions into conferences.

Implementations that compose speech-to-speech providers (Section
12.10.12) MUST:

- Feed the provider a single stream mixed per Section 12.7.5, and
  forward no silence-only window.
- Discard the provider's user-role transcriptions rather than store or
  attribute them.
- Emit the provider's final assistant transcriptions as RoomEvents
  attributed to the channel, and never back into the conference's own
  voice path.
- Refuse a configuration holding both a synthesizer and a
  speech-to-speech provider.
- Publish provider audio under the utterance contract of Section
  12.10.4, terminal chunk included.
- Keep the per-lane VAD as the interruption sensor and enforce
  ConferenceInterruptionConfig scope on it.
- Run per-track VAD whenever a speech-to-speech provider is composed.

#### 12.10.12 Speech-to-Speech Composition

A conference MAY compose a RealtimeVoiceProvider (Section 12.4) as its
intelligence: the participants' voices reach one realtime session, and
the provider's voice is the bot's. This is the sub-second, natively
turn-taking agent in a multi-party meeting — the speech-to-speech
pattern of Section 12.10.6 — and it is OPTIONAL within Conformance
Level 3. This section binds only implementations that offer it.

The composition changes no boundary it crosses. The provider keeps the
interface of Section 12.4 — one session, one audio input, no notion of
a conference. The backend keeps the interface of Section 12.10.3 —
tracks in, one bot track out. The channel between them keeps every
contract of Sections 12.10.4 and 12.10.5. What this section specifies
is the crossing itself.

**N→1: the provider hears a mix (normative).** Implementations MUST
feed the provider one stream mixed from every subscribed AUDIO track,
using the additive algorithm of Section 12.7.5: samples promoted and
summed per mixing window, headroom-scaled by the square root of the
number of tracks contributing to that window, clamped back to the
sample width. A track with no audio in the window contributes silence;
a window to which no track contributed MUST NOT be forwarded. The
mixed stream is resampled to the provider's declared input rate before
it is sent.

Routing the active speaker instead is not an admissible narrowing. It
reads better on paper — the provider hears one clean voice — but
ACTIVE_SPEAKER is an optional capability (Section 12.10.2), so the
routing would not survive a backend change; the switch lands
mid-syllable, so every hand-over chops a phoneme; and overlapping
speech — the thing a meeting has that a 1:1 call does not — is audible
in a mix and lost in a switch. The mix is the one complete signal every
backend can produce. The mixer itself stays private: the *algorithm* of
Section 12.7.5 is reusable, the AudioBridge interface is not (Section
12.10.10), and this specification defines no mixer provider interface —
an implementation MAY factor one out privately.

**Attribution ends at the provider boundary (normative).** A mix
carries no speaker identity, so nothing downstream of it can. The
provider's user-role transcriptions MUST NOT be stored as RoomEvents
and MUST NOT be attributed to a participant by inference — correlating
them with active-speaker events or lane VAD timing is a guess wearing
attribution's clothes, and principle 5 places identity on tracks
precisely so that no component has to guess. Implementations MUST
discard user-role transcriptions; they MAY surface them to
observability, unattributed. The attributed transcript is the one the
conference already has: per-track STT lanes (Section 12.10.4), running
in parallel with the mix, each event carrying its speaker. A deployment
that needs the meeting transcribed configures stt beside the provider;
the two consume the same lanes and do not contend.

The provider's assistant-role transcriptions are the other half, and
they are kept: they are the only record of what the AI said, because
no AIChannel generation stands behind this voice for the store to
hold. Final assistant transcriptions MUST be emitted as RoomEvents
attributed to the channel — no participant is their author — and MUST
NOT be delivered back into the conference's own voice path: the words
were already heard once, on the bot track.

**One voice per bot (normative).** A channel MUST refuse a
configuration holding both a synthesizer (tts) and a speech-to-speech
provider, at construction and at the plugs alike. There is one bot
track and one floor; two components that each answer the room would
answer over each other, and no floor discipline turns two
intelligences into one voice. A deployment that wants to trade the
STT/TTS pattern for the realtime one does it through the plugs —
unplug one, plug the other — and never holds both.

**The provider's voice is an utterance (normative).** Provider audio
reaches the conference through the outbound contract of Section
12.10.4 unchanged: a response takes the floor and opens an utterance,
its audio deltas are the utterance's chunks, and its end closes the
utterance with `is_final` — as does a barge-in, and a leave abandons
it with no terminal chunk, exactly as written there. One utterance at
a time holds: a second response waits for the floor. BEFORE_TTS and
AFTER_TTS do not fire — they are text-synthesis hooks and no text
precedes this synthesis. ON_BARGE_IN fires as always, though its
`interrupted_text` MAY be empty when the interruption lands before the
first assistant transcript delta has arrived.

**Interruption has one sensor and two effects (normative).** Section
12.10.5 stays the policy authority, and the per-lane VAD stays its
sensor: ON_BARGE_IN MUST identify the interrupting participant, and
only track identity can — the provider's own speech detection hears
the mix and can name no one, so it MUST NOT trigger the interruption
path. An interruption that lands does what Section 12.10.5 says —
`stop_playback()`, the latch, ON_BARGE_IN — and additionally SHOULD
signal the provider to cancel the response in flight, where the
provider can: cancellation is best-effort, since Section 12.4
providers exist whose sessions cannot cancel a response, and it is
`stop_playback()` that silences the room either way.

The provider brings its own turn-taking, and the two authorities can
disagree: a provider whose native detection halts generation on any
speech in the mix will fall silent for a speaker the configured scope
would not admit — no barge-in fires, the bot simply trails off.
Implementations SHOULD align the provider's own interruption
behaviour with the configured scope where the provider exposes it
(Section 12.4 provider configuration), and MUST NOT substitute the
provider's detection for the policy: scope enforcement,
`stop_playback()` and ON_BARGE_IN remain the framework's, whatever the
provider does with its generation.

**The session follows the bot (normative).** One provider session
serves one conference, scoped within the lifetime of the bot session
whose track it speaks on. Speech-to-speech is a first need under
Hot-plugging intelligence (Section 12.10.4): it consumes AUDIO tracks
and it is a voice, so its derived grants carry both `subscribe` and
`publish_audio`, and plugging and unplugging it follow every rule of
that section — the occupancy probe re-runs at the plug, an occupied
slot refuses a second provider, and unplugging the last need takes the
bot out. Connecting the provider is lazy: the session is established
when there is something for it to hear or say, and a connect failure
MUST NOT fail the join or the plug, exactly as a lazy join's own
failure does not (Section 12.10.4) — the configuration stands, and
implementations SHOULD retry with a cooldown rather than on every
mixing window. When the bot session ends — detach, unplug,
backend-side loss, close — the provider session is disconnected with
it.

**The lanes stay on.** Composing a provider suspends none of the
per-track machinery: VAD, speech edges, recording, and STT lanes where
configured all run as before. The pipeline requirement of Section
12.10.4 extends accordingly: a conference composing speech-to-speech
MUST run per-track VAD even when no STT is configured — without it the
interruption policy of Section 12.10.5 has no sensor, and the bot
cannot be interrupted at all.

### 12.11 Room Media Recording

Sections 12.3.7 and 12.8.10 each record a *session*: one participant, one
medium, in the two directions a session has. A room is not a session. It holds
several participants, each of which may publish more than one kind of media,
and they arrive and leave across the room's lifetime rather than all at its
start. Room media recording is the interface for that shape, and it is what
conference recording binds to (Section 12.10.8).

```
MediaRecorder (interface)
├── name: string                                          # Recorder name
├── on_recording_start(config: MediaRecordingConfig) → MediaRecordingHandle
│       # Open one recording
├── on_track_added(handle, track: RecordingTrack) → void
│       # Declare a track this recording carries
├── on_track_removed(handle, track: RecordingTrack) → void
│       # The track ended — flush what it holds
├── on_data(handle, track: RecordingTrack, data: bytes,
│           timestamp_ms: float | null) → void
│       # Media for one of the recording's tracks
├── on_recording_stop(handle) → MediaRecordingResult
│       # Close the recording, finalize output
└── close() → void
        # Release resources
```

```
RecordingTrack
├── id: string                        # Track identifier
├── kind: string                      # "audio" | "video" | "screen_share"
├── channel_id: string                # Channel the media came through
├── participant_id: string | null     # Who published it
├── codec: string
├── sample_rate: int | null           # Audio
├── channels: int | null              # Audio
├── width: int | null                 # Video
└── height: int | null                # Video
```

```
MediaRecordingConfig                  MediaRecordingResult
├── storage: string                   ├── id: string
├── format: string = "mp4"            ├── url: string
├── video_codec: string               ├── duration_seconds: float
├── video_fps: int                    ├── tracks: list<RecordingTrack>
├── audio_codec: string               ├── format: string
├── audio_sample_rate: int            └── size_bytes: int
└── metadata: map<string, any> = {}
```

```
MediaRecordingHandle                  RoomRecorderBinding
├── id: string                        ├── recorder: MediaRecorder
├── room_id: string                   ├── config: MediaRecordingConfig
├── state: string                     ├── enabled: bool = true
├── started_at: datetime              └── name: string
└── path: string
```

The unit is the **handle**, not the room: a handle is one recording, and how
many a room opens is the caller's decision. A room that records its channels
into a single file opens one and adds every track to it; a conference opens
one per track (Section 12.10.8). Both are the same interface used at
different granularities, which is why the interface names a track on every
call rather than assuming one.

`participant_id` is what makes an output answerable to "who said what", and
it is the recorder's only source for it: the interface carries no session and
no direction. An implementation MUST populate it wherever the framework knows
the publisher.

**A track describes its own media.** `codec`, `sample_rate` and `channels`
are how a recorder learns to interpret the bytes it is then handed: `on_data`
carries none of it, and PCM in particular is indistinguishable from any other
PCM by inspection. A caller MUST therefore describe what it will actually
deliver rather than what the framework normally carries, and MUST NOT deliver
media in a format other than the one it declared. The obligation is a caller's
because the failure is silent: a recorder told 16-bit mono and handed stereo
writes a file that opens, plays at the wrong speed, and reports no error at
all. A recorder MAY refuse a declaration it cannot honour, and MUST say so.

`storage` is an integrator-defined identifier resolved by the implementation
at runtime, as in Section 12.3.7. Implementations MUST document which storage
backends they support and MUST raise a configuration error for an unknown
identifier. A storage path MUST NOT be allowed to escape its configured
directory.

A recorder MAY refuse a track declared after it has begun writing — a
container that fixes its streams at the first write cannot honour a late one
— and MUST say so rather than silently dropping the media. A caller that
cannot predict its tracks opens one recording per track instead, which is why
a conference does.

**Which thread calls it.** Every call in this interface is synchronous, and
what they do — encode a frame, write a container, close a file — blocks for
as long as the storage takes. An implementation MAY therefore call a recorder
outside the thread its event loop runs on, and one recording media as it
arrives will have to: Section 12.10.8 forbids a write that delays another
track's delivery, and a blocking call made on the loop delays everything on
it. A recorder MUST NOT assume it is called on the loop thread, and MUST NOT
assume the calling thread is the same one across calls.

What an implementation owes in return is serialization **per handle**: the
calls belonging to one recording are ordered and never overlap, so a
recorder's per-recording state needs no locking of its own and its media
arrives in the order the framework received it. Different handles carry no
such promise and may be written concurrently, which is what lets one track's
slow storage stay one track's problem.

There is one call that may overlap, and only one: a write that has exhausted
the budget of Section 12.10.8 cannot be taken back — a call made on another
thread runs to completion whatever the framework does about it — and holding
the close until it returns would let a wedged recorder hold a teardown, and
with it a bot, in a conference indefinitely. An implementation MAY therefore
finalize a recording whose write has passed that budget and is still running,
and MUST report it when it does. Recorders are not asked to make that case
safe; they are told it exists, because the alternative reading is that it
cannot happen.

**Every wait is bounded, the close included.** The budget of Section 12.10.8
covers what a recording holds *before* it is finalized; `on_track_removed()`
and `on_recording_stop()` are calls into the same recorder and block the same
way, and a conference teardown waits for them before its bot leaves. An
implementation MUST therefore bound the finalization too, and MUST report a
recording it stopped waiting for — the result is unknown, so where the media
was written goes unreported rather than guessed. Recorders MUST NOT read the
absence of a further call as permission to discard: what they were told to
close is still theirs to close.

**A recorder is not released while a call is running in it.** `close()` frees
whatever the recorder holds, and freeing the context a call is executing inside
is not an error a recorder can return — for one wrapping a native muxer it is a
crash. So an implementation MUST NOT call `close()` while any call it stopped
waiting for is still outstanding, and this wait is separate from the ones
above: those belong to a teardown with a bot waiting behind them, this one
belongs to releasing a provider and has nothing queued behind it. An
implementation that still cannot settle them MUST leave the recorder unreleased
and MUST say so. Leaking a recorder is a bounded cost; calling into a freed one
is not.

---

## 13. Resilience and Error Handling

### 13.1 Circuit Breaker

Each channel SHOULD have an associated circuit breaker to prevent cascading
failures.

**States:**

| State | Behavior |
|---|---|
| CLOSED | Normal operation — deliveries proceed |
| OPEN | Fail-fast — deliveries immediately return error |
| HALF_OPEN | Probe — allow one delivery to test recovery |

**Transitions:**

- CLOSED → OPEN: After N consecutive delivery failures (configurable).
- OPEN → HALF_OPEN: After a configurable cooldown period.
- HALF_OPEN → CLOSED: Probe delivery succeeds.
- HALF_OPEN → OPEN: Probe delivery fails.

When a circuit breaker opens, implementations MUST emit a `circuit_breaker_opened`
framework event.

### 13.2 Retry Policy

```
RetryPolicy
├── max_retries: int                        # Maximum retry attempts
├── base_delay_seconds: float               # Initial delay
├── exponential_base: float                 # Multiplier per attempt (default: 2.0)
├── max_delay_seconds: float                # Maximum delay cap
└── retryable_errors: list<string> | null   # Error codes eligible for retry
```

Retry delay formula: `delay = min(base_delay * exponential_base ^ attempt, max_delay)`

Retry policies are configured per-channel-binding. Only errors marked as
`retryable = true` in the DeliveryError SHOULD trigger retries.

### 13.3 Rate Limiting

```
RateLimit
├── max_per_second: float | null            # Maximum events per second
├── max_per_minute: float | null            # Maximum events per minute
└── burst: int | null                       # Burst allowance
```

Implementations SHOULD use a token bucket algorithm. When rate-limited,
deliveries MUST be queued (not dropped).

### 13.4 Idempotency

If an InboundMessage carries an `idempotency_key`, the framework MUST:

1. Check under a room-level lock whether the key has been seen.
2. If seen → return the original result without reprocessing.
3. If not seen → process normally and record the key.

### 13.5 Room-Level Locking

All event processing within a room MUST be serialized. Implementations MUST
provide a locking mechanism that prevents concurrent processing of events in
the same room.

**Serialization scope.** The room lock MUST cover the locked pre-commit
section, the commit point, and broadcast planning (§10.1 steps 6–12):
everything that reads room state to decide, assigns the index, writes the
timeline, or resolves the delivery set. External delivery execution (§10.2 step 3) is
NOT required to run under the room lock — it MUST preserve per-room order
(the delivery lane, §10.2), which holding the lock trivially satisfies.
Implementations SHOULD NOT extend the room's critical section with external
I/O (provider calls, AI generation): under a distributed lock manager, lock
tenure is what serializes the whole deployment, and every await spent under
the lock is paid by every other worker waiting on that room.

```
RoomLockManager (interface)
├── acquire(room_id) → lock
└── release(lock) → void
```

For single-process deployments, an in-memory lock manager (per-room async mutex)
is sufficient. When a persistent store is shared across multiple processes an
in-memory lock manager is **NOT** sufficient — per-process locks do not
coordinate, so concurrent writers on the same room can interleave. Such
deployments MUST either use a distributed lock manager (e.g. Redis or a
PostgreSQL advisory lock) or rely on storage-layer atomicity for the operations
that require it (index assignment, §8.1). Implementations SHOULD ship at least
one distributed lock manager, and SHOULD detect the unsafe combination of a
shared persistent store with an in-memory lock manager and warn (or refuse) at
initialization.

### 13.6 Processing Timeout

Implementations SHOULD support a configurable `process_timeout`. Its semantics
are defined **relative to the commit point** (§10.1 step 12) — the atomic
transaction that stores the event as DELIVERED and updates the room counters:

- **Pre-commit phase** (§10.1 steps 3–11: context build, identity resolution,
  BEFORE_BROADCAST hooks, write-permission check, index assignment). This phase
  performs no durable write of the inbound event. `process_timeout` MUST bound
  this phase. On expiry the implementation MUST abort **before** the commit
  point, leaving no partial durable state, and return
  `InboundResult(blocked=true, reason=process_timeout)`. The event MUST NOT
  appear in the timeline.

- **Commit point** (§10.1 step 12). Once the DELIVERED transaction has
  committed, the event is authoritative. `process_timeout` MUST NOT cancel,
  block, or re-mark it. An implementation MUST NOT wrap the commit and the
  subsequent broadcast in a single cancellable unit whose expiry could leave a
  committed event reported as blocked/failed.

- **Post-commit phase** (§10.1 steps 14–17: delivery-lane execution,
  reentry passes, side effects, async hooks). Slowness here MUST NOT
  invalidate the committed event.
  Bound external delivery with **per-operation** timeouts (§10.2) and report
  failures per channel via `delivery_failed` framework events — never by
  changing the source event's status or the returned result to blocked/failed.
  A degraded broadcast SHOULD surface as `broadcast_partial_failure`, with the
  source event remaining DELIVERED.

Implementations MAY additionally model outbound delivery with an explicit
`PENDING → COMMITTED | FAILED` state and an outbox, plus recovery of events
left PENDING, so that a crash between commit and delivery is recoverable. Such
a state applies to **delivery**, not to the committed timeline event.

---

## 14. Storage Interface

### 14.1 Conversation Store

Implementations MUST provide a pluggable storage backend via the following
interface:

```
ConversationStore (interface)
│
├── Rooms
│   ├── create_room(organization_id, metadata) → Room
│   ├── get_room(room_id) → Room | null
│   ├── update_room(room_id, updates) → Room
│   ├── delete_room(room_id) → void
│   ├── list_rooms(filters) → list<Room>
│   ├── find_room(filters) → Room | null
│   └── find_latest_room(filters) → Room | null
│
├── Events
│   ├── add_event(room_id, event) → RoomEvent
│   ├── get_event(event_id) → RoomEvent | null
│   ├── list_events(room_id, filters) → list<RoomEvent>
│   └── update_event(event_id, updates) → RoomEvent
│
├── Bindings
│   ├── create_binding(room_id, binding) → ChannelBinding
│   ├── get_binding(room_id, channel_id) → ChannelBinding | null
│   ├── delete_binding(room_id, channel_id) → void
│   └── list_bindings(room_id) → list<ChannelBinding>
│
├── Participants
│   ├── create_participant(room_id, participant) → Participant
│   ├── get_participant(participant_id) → Participant | null
│   ├── update_participant(participant_id, updates) → Participant
│   ├── delete_participant(participant_id) → void
│   └── list_participants(room_id) → list<Participant>
│
├── Identity
│   ├── store_identity(identity) → Identity
│   ├── get_identity(identity_id) → Identity | null
│   └── resolve_by_address(channel_type, address, organization_id) → Identity | null
│
├── Tasks
│   ├── create_task(room_id, task) → Task
│   └── list_tasks(room_id, filters) → list<Task>
│
└── Observations
    ├── create_observation(room_id, observation) → Observation
    └── list_observations(room_id, filters) → list<Observation>
```

### 14.2 Required Implementations

| Implementation | Purpose | Conformance |
|---|---|---|
| In-Memory Store | Testing, prototyping, single-process | MUST provide |
| Persistent Store | Production (SQL, document DB) | SHOULD provide |

### 14.3 Consistency Requirements

- Event index assignment MUST be atomic within a room. For a persistent store
  that may be accessed by more than one process, this atomicity MUST be enforced
  at the storage layer — a single transaction plus a `UNIQUE(room_id, index)`
  constraint (§8.1) — not by an in-process lock alone.
- Room state updates MUST be consistent with event storage. Specifically,
  storing an event as DELIVERED and bumping the room's `event_count` /
  `latest_index` form a **single atomic commit** (§10.1 step 12): an observer
  MUST never see a DELIVERED event that is not reflected in the room counters,
  nor counters that count an event absent from the timeline.
- Once committed (DELIVERED), an event MUST NOT be retroactively re-marked
  BLOCKED or FAILED. A processing timeout or a delivery failure after the
  commit point (§13.6) MUST NOT alter the event's committed status.
- Idempotency key checks MUST be performed under the room lock.

### 14.4 Returned-Object Ownership

- Committed events are immutable (§4). An event object returned by a read
  (`get_event`, `list_events`, conversation reads) is a snapshot of the
  committed record: the caller MUST treat it as frozen and MUST NOT mutate
  it. A store MAY return the same object to multiple readers (an in-memory
  store sharing its stored objects) or a fresh object per read (a SQL store
  deserialising rows) — both are conformant, and a portable caller can rely
  on neither aliasing nor isolation.
- A store MUST own its stored representation from the moment a write
  returns: a caller's later mutation of an object it passed to `add_event` /
  `update_event` MUST NOT alter stored state (copy-in and serialisation both
  satisfy this).
- Rooms, bindings and participants returned by reads are caller-owned:
  mutating a returned object MUST NOT affect stored state — changes are
  applied through the write interface.

---

## 15. Observability

### 15.1 Logging

Implementations MUST use structured logging with named loggers. The following
logger hierarchy is RECOMMENDED:

```
roomkit
├── roomkit.core.framework
├── roomkit.core.router
├── roomkit.core.hooks
├── roomkit.core.locks
├── roomkit.channels.sms
├── roomkit.channels.email
├── roomkit.channels.websocket
├── roomkit.channels.ai
├── roomkit.channels.whatsapp
├── roomkit.channels.voice
├── roomkit.channels.voice.pipeline
├── roomkit.providers.sms.*
├── roomkit.providers.email.*
├── roomkit.providers.ai.*
├── roomkit.providers.voice.*
├── roomkit.identity
└── roomkit.store
```

### 15.2 Log Levels

| Level | What to Log |
|---|---|
| DEBUG | Full pipeline trace, raw payloads, hook decisions |
| INFO | Room created, event stored, channel attached, participant resolved |
| WARNING | Delivery failed (retryable), hook timeout, chain depth approaching limit |
| ERROR | Provider error (non-retryable), circuit breaker opened, store failure |

### 15.3 Structured Log Context

Each log entry SHOULD include structured context:

```
{
    "room_id": "room_8f3a",
    "event_id": "evt_abc",
    "channel_id": "sms_customer",
    "provider": "twilio",
    "chain_depth": 0,
    "status": "sent",
    "latency_ms": 245
}
```

### 15.4 Voice Pipeline Observability

Voice pipeline stages SHOULD emit structured metrics for monitoring and
debugging. The following metrics are RECOMMENDED:

| Metric | Source | Description |
|---|---|---|
| `pipeline.stage_latency_ms` | All stages | Processing time per stage per frame |
| `pipeline.stt_latency_ms` | STTProvider | Time from speech end to final transcript |
| `pipeline.tts_latency_ms` | TTSProvider | Time from text to first audio frame |
| `pipeline.vad_speech_duration_ms` | VAD | Duration of detected speech segments |
| `pipeline.vad_false_positive_rate` | VAD | Speech detections that produced no transcript |
| `pipeline.aec_convergence` | AEC | Echo cancellation effectiveness (0.0 to 1.0) |
| `pipeline.agc_gain_db` | AGC | Current applied gain |
| `pipeline.dtmf_detected` | DTMF | Count of DTMF digits detected per session |
| `pipeline.recording_duration_s` | Recorder | Active recording duration |
| `pipeline.turn_detector_latency_ms` | TurnDetector | Time to reach turn decision |
| `pipeline.backchannel_rate` | BackchannelDetector | Ratio of backchannels to interruptions |
| `pipeline.barge_in_count` | InterruptionConfig | Count of barge-in events per session |
| `pipeline.debug_tap_bytes_written` | PipelineDebugTaps | Total bytes written to debug tap files |
| `transport.packets_lost` | VoiceBackend | Count of packets confirmed lost per session (Section 12.2.1) |
| `transport.concealed_frames` | VoiceBackend | Count of frames synthesized by packet loss concealment per session |

Voice pipeline logs SHOULD use the `roomkit.channels.voice.pipeline` logger
with the following structured context fields: `session_id`, `room_id`,
`stage_name`, `latency_ms`, and `frame_timestamp_ms`.

### 15.5 Framework Events for Monitoring

See Section 8.2 for the complete list of framework events. These MUST be
emittable and subscribable by integrators for monitoring dashboards, alerting,
and integration purposes.

### 15.6 Protocol Trace Infrastructure

Channels that interact with transport-level protocols (SIP, RTP, SMTP, etc.)
SHOULD emit `ProtocolTrace` records (Section 5.14) for significant protocol
events. The framework provides a layered trace infrastructure that routes these
traces to integrator-registered hooks at the room level.

**Channel-level trace API:**

```
Channel (trace extensions)
├── emit_trace(trace: ProtocolTrace) → void
│       # Emit a trace to all registered handlers
│       # Called by backend/transport implementations
│
├── on_trace(callback, protocols: list<string> | null) → void
│       # Register a user-level trace callback
│       # If protocols is set, only traces matching the filter are forwarded
│
├── trace_enabled: bool (read-only)
│       # True if any trace handler is registered (user or framework)
│
└── resolve_trace_room(session_id: string | null) → string | null
        # Resolve a room_id from a session_id via session bindings
        # Default: null (override in voice channels)
```

`emit_trace()` invokes all registered handlers: user-level callbacks (registered
via `on_trace()`), and the framework handler (set during `register_channel()`).
Handlers MAY be sync or async — async handlers MUST be scheduled as tasks and
MUST NOT block the caller.

**Trace bridging for voice channels:**

Voice channels (VoiceChannel, RealtimeVoiceChannel) bridge traces from their
underlying backend or transport to the channel's `emit_trace()`. This is done via
`set_trace_emitter()` on the backend/transport:

```
VoiceChannel:
    # Calls backend.set_trace_emitter(self.emit_trace) when trace is enabled

RealtimeVoiceChannel:
    # Calls transport.set_trace_emitter(self.emit_trace) when trace is enabled
    # Transport MAY forward to underlying backend (e.g., SIPRealtimeTransport → SIPVoiceBackend)
```

The bridge is activated lazily — only when `trace_enabled` becomes true (via
`on_trace()` registration or framework handler assignment).

**Framework-level trace routing:**

When a channel is registered via `register_channel()`, the framework sets a
framework trace handler on the channel. This handler:

1. Resolves the `room_id` for the trace:
   - Uses `trace.room_id` if set directly.
   - Falls back to `channel.resolve_trace_room(trace.session_id)` to look up
     the room via session bindings.
2. Fires the `ON_PROTOCOL_TRACE` hook for the resolved room.

**Pre-room trace buffering:**

Transport-level traces (e.g., SIP INVITE) often fire before `process_inbound()`
creates the room. Since hooks require a room context, these traces cannot be
delivered immediately. The framework MUST buffer such traces and replay them
when the room is created and the channel is attached:

```
1. Backend emits trace (e.g., SIP INVITE accepted)
2. Framework handler tries to fire ON_PROTOCOL_TRACE hook
3. Room does not exist yet → buffer trace in _pending_traces[room_id]
4. process_inbound() creates room, attaches channel
5. attach_channel() calls _flush_pending_traces(room_id)
6. Buffered traces are replayed as ON_PROTOCOL_TRACE hooks
```

This ensures that no protocol traces are lost, even for the initial signaling
messages that precede room creation.

### 15.7 Telemetry Provider

Implementations SHOULD provide a pluggable telemetry provider abstraction for
distributed tracing and metrics collection:

```
TelemetryProvider (interface)
├── start_span(name, attributes, parent) → Span
│       # Begin a new trace span for an operation
│
├── record_metric(name, value, attributes) → void
│       # Record a numeric metric value
│
├── record_event(name, attributes) → void
│       # Record a discrete event within the current trace
│
└── close() → void
        # Flush pending data and release resources
```

**Required implementations:**

| Provider | Description |
|---|---|
| OpenTelemetryProvider | Industry-standard distributed tracing (OTLP export) |
| ConsoleTelemetryProvider | Human-readable console output for development |
| NoopTelemetryProvider | No-op implementation (telemetry disabled) |

Implementations SHOULD instrument the following operations with spans:
`process_inbound`, `broadcast`, `hook_execution`, `deliver`, `ai_generate`,
`stt_transcribe`, `tts_synthesize`, `identity_resolve`, and `store_event`.

Each span SHOULD include structured attributes: `room_id`, `channel_id`,
`event_id`, `provider`, and `latency_ms`.

**SIP trace examples:**

A SIP voice backend SHOULD emit the following traces:

| Event | Direction | Protocol | Summary | Raw |
|---|---|---|---|---|
| Call received | inbound | sip | `INVITE from +1555... to +1666...` | Serialized SIP INVITE request |
| Call accepted | outbound | sip | `200 OK (codec=16000Hz, ...)` | SDP answer body |
| Remote hangup | inbound | sip | `BYE from +1555...` | Serialized SIP BYE request |
| Local hangup | outbound | sip | `BYE (local hangup)` | null (library may not expose serialized form) |

### 15.8 Audit System

RoomKit provides a two-tier auditing architecture for compliance, debugging,
and monitoring: **tool auditing** captures individual tool calls, and
**session auditing** captures the full conversation timeline.

#### 15.8.1 Tool Auditing

Tool auditing records every tool call with input, output, timing, and status.

**ToolAuditEntry:**

```
ToolAuditEntry
├── ts: string                              # ISO 8601 timestamp
├── agent_id: string                        # Which agent made the call
├── tool_name: string                       # Tool function name
├── arguments: map<string, any>             # Input arguments
├── result: string                          # Tool output (truncated to 500 chars)
├── status: string                          # "ok", "failed", or "error"
├── duration_ms: float                      # Execution time in milliseconds
└── metadata: map<string, any>              # Optional extra data
```

**Status detection:**
- `"ok"` — default for successful execution.
- `"failed"` — auto-detected if tool returns `{"status": "failed"}`.
- `"error"` — set when the tool handler raises an exception.

**ToolAuditor** (interface):

```
ToolAuditor (interface)
├── record(entry: ToolAuditEntry) → void    # Record a tool execution
├── entries: list<ToolAuditEntry> (property) # All recorded entries
├── summary() → string                     # Human-readable summary
└── print_summary() → void                 # Log summary via logger
```

**Built-in implementations:**

| Implementation | Persistence | Description |
|---|---|---|
| JSONLToolAuditor | JSONL file | Appends one JSON line per call; maintains in-memory list |
| ConsoleToolAuditor | Logger | Real-time logging via Python logging module |

**Handler wrapper:**

The `audit_tool_handler(handler, auditor, agent_id)` function wraps any tool
handler to automatically record audit entries. It:

1. Measures execution time.
2. Catches exceptions and marks status as `"error"`.
3. Auto-detects `"failed"` from JSON response.
4. Truncates results to 500 characters.
5. Returns the original handler result unchanged.

Integrators MAY implement custom `ToolAuditor` backends (e.g., Datadog,
Elasticsearch) by implementing the interface.

#### 15.8.2 Session Auditing

Session auditing captures the full conversation timeline: speech turns, tool
calls, vision events, interruptions, and session lifecycle.

**SessionAuditEntry:**

```
SessionAuditEntry
├── ts: string                              # ISO 8601 timestamp
├── type: string                            # Event type (see below)
├── role: string | null                     # "user", "assistant", or "system"
├── content: string                         # Text, transcription, or description
├── duration_ms: float | null               # For timed events (tool calls)
└── metadata: map<string, any>              # Extra data (tool_name, args, status, etc.)
```

**Session audit event types:**

| Type | Role | Trigger | Content |
|---|---|---|---|
| speech | user/assistant | ON_TRANSCRIPTION hook | Transcribed speech text |
| tool_call | assistant | Manual `record_tool()` | Tool result |
| vision | system | ON_VISION_RESULT hook | Frame description |
| barge_in | user | ON_BARGE_IN hook | "User interrupted" |
| session | system | ON_SESSION_STARTED hook | "Session started" |
| error | system | Application-specific | Error message |

**SessionAuditor** (interface):

```
SessionAuditor (interface)
├── record(entry: SessionAuditEntry) → void
├── entries: list<SessionAuditEntry> (property)
├── summary() → string
├── print_summary() → void
│
│   # ToolAuditor compatibility bridge:
├── record_tool(entry: ToolAuditEntry) → void  # Convert tool entry to session entry
├── tool_auditor: ToolAuditor (property)        # Bridge adapter
│
│   # Hook auto-registration:
└── attach(kit: RoomKit) → void                # Register hooks for automatic capture
```

**Hook auto-registration:** When `attach(kit)` is called, the session auditor
registers hooks for `ON_TRANSCRIPTION`, `ON_BARGE_IN`, `ON_SESSION_STARTED`,
and `ON_VISION_RESULT` to capture conversation events automatically.

**ToolAuditor bridge:** The `tool_auditor` property returns a bridge adapter
that converts `ToolAuditEntry` records into `SessionAuditEntry` records. This
allows a single `SessionAuditor` to capture both tool calls and conversation
events in a unified timeline.

**Built-in implementation:** `JSONLSessionAuditor` — writes entries to a JSONL
file and maintains an in-memory chronological list.

#### 15.8.3 Audit Data Format

Both auditors use JSONL (JSON Lines) for persistence — one JSON object per
line, independently parseable:

```
{"ts":"...","agent_id":"exec","tool_name":"search","arguments":{"q":"roomkit"},"result":"...","status":"ok","duration_ms":1234.5,"metadata":{}}
{"ts":"...","type":"speech","role":"user","content":"Open Chrome","duration_ms":null,"metadata":{}}
```

JSONL files are append-only. Implementations MUST create parent directories
automatically. Write errors MUST be logged but MUST NOT propagate exceptions
to the caller.

---

## 16. Integration Surfaces

The RoomKit core MUST NOT depend on any specific web framework. Integration
surfaces are thin wrappers that expose core functionality.

### 16.1 REST API (RECOMMENDED)

A conforming REST API implementation SHOULD provide the following endpoints:

**Rooms:**

```
POST   /rooms                                   # Create room
GET    /rooms/{id}                              # Get room
PATCH  /rooms/{id}                              # Update room
DELETE /rooms/{id}                              # Delete room
GET    /rooms?organization_id=X&status=active   # List rooms
```

**Channels:**

```
POST   /rooms/{id}/channels                     # Attach channel
DELETE /rooms/{id}/channels/{cid}               # Detach channel
PATCH  /rooms/{id}/channels/{cid}               # Update binding (access, visibility)
POST   /rooms/{id}/channels/{cid}/mute          # Mute channel
POST   /rooms/{id}/channels/{cid}/unmute        # Unmute channel
GET    /rooms/{id}/channels                     # List bindings
GET    /channels                                # List registered channels
```

**Events & Timeline:**

```
POST   /rooms/{id}/events                       # Inject event
GET    /rooms/{id}/timeline                     # Get timeline (supports pagination, visibility filter)
```

**Participants:**

```
POST   /rooms/{id}/participants                 # Add participant
DELETE /rooms/{id}/participants/{pid}            # Remove participant
GET    /rooms/{id}/participants                 # List participants
POST   /rooms/{id}/participants/{pid}/resolve   # Resolve pending identity
```

**Tasks & Observations:**

```
GET    /rooms/{id}/tasks                        # List tasks for room
PATCH  /tasks/{id}                              # Update task status
GET    /rooms/{id}/observations                 # List observations for room
```

**Identity:**

```
POST   /identities                              # Create identity
GET    /identities/resolve?channel=sms&address=+1... # Resolve identity
PATCH  /identities/{id}                         # Update identity
```

**Webhooks:**

```
POST   /webhooks/{channel_type}/{provider}          # Inbound webhook
POST   /webhooks/{channel_type}/{provider}/status   # Delivery status webhook
```

**WebSocket:**

```
WS     /ws/{room_id}                            # Real-time room connection
```

### 16.2 MCP Server (RECOMMENDED)

For AI agents to interact with rooms natively via the Model Context Protocol:

**MCP Tools (actions):**

| Tool | Description |
|---|---|
| send_message | Send a message to a room |
| create_task | Create a task in a room |
| add_observation | Record an observation |
| attach_channel | Attach a channel to a room |
| detach_channel | Detach a channel |
| mute_channel | Mute a channel |
| unmute_channel | Unmute a channel |
| set_channel_visibility | Change visibility |
| update_room_metadata | Update room metadata |
| resolve_identity | Resolve an identity |
| escalate_to_human | Escalate to a human agent |

**MCP Resources (data):**

| Resource | Description |
|---|---|
| room://{room_id} | Room state |
| room://{room_id}/timeline | Room timeline |
| room://{room_id}/participants | Room participants |
| room://{room_id}/channels | Room channel bindings |
| room://{room_id}/tasks | Room tasks |
| identity://{identity_id} | Identity details |

### 16.3 Surface Independence

Both REST and MCP surfaces MUST call the same core methods. No business logic
should live in the integration surface layer.

---

## 17. Security Considerations

### 17.1 Input Validation

- All inbound payloads MUST be validated before processing.
- Webhook signatures SHOULD be verified when the provider supports them.
- Event content SHOULD be sanitized to prevent injection attacks.

### 17.2 Multi-Tenant Isolation

- Rooms are scoped by `organization_id`.
- Implementations MUST ensure that room operations are isolated per organization.
- Identity resolution MUST be scoped to the organization.

### 17.3 Sensitive Data

- `raw_payload` MAY contain sensitive data. Implementations SHOULD support
  configurable redaction or encryption at rest.
- Hook-based PII scanning (e.g., SIN/SSN detection) SHOULD be used to prevent
  sensitive data from traversing channels.
- Blocked events are stored for audit but their content SHOULD be handled
  according to the organization's data retention policy.

### 17.4 Rate Limiting

- Per-channel rate limits prevent abuse of external provider APIs.
- Implementations SHOULD support per-organization rate limits.

### 17.5 Chain Depth

- The chain depth limit prevents resource exhaustion from unbounded AI ↔ AI loops.
- Implementations MUST enforce the limit and MUST NOT allow it to be disabled.

### 17.6 Voice and Audio Security

**Recording consent and compliance:**

- Implementations that support audio recording MUST provide a mechanism for
  recording consent management. In many jurisdictions (TCPA, GDPR, PIPEDA),
  recording requires explicit consent from all parties.
- The framework SHOULD fire ON_RECORDING_STARTED before any audio is captured,
  giving integrators the opportunity to notify participants.
- Implementations SHOULD support configurable consent modes: `SINGLE_PARTY`
  (one party consents), `ALL_PARTY` (all parties must consent), or `NONE`
  (integrator manages consent externally).

**Audio data handling:**

- Audio recordings MUST be encrypted at rest. Implementations MUST support
  configurable encryption for stored recordings.
- Audio streams in transit SHOULD use encrypted transport (TLS, SRTP, DTLS).
- STT and TTS provider calls transmit audio to external services.
  Implementations SHOULD document which providers receive audio data and
  SHOULD support configurable provider selection based on data residency
  requirements.
- Voice session metadata (transcripts, recordings, DTMF digits) MUST follow
  the same data retention and redaction policies as other room events.

**DTMF sensitivity:**

- DTMF digits MAY contain sensitive data (credit card numbers, PINs, account
  numbers). Implementations MUST support configurable DTMF redaction — the
  ability to mask DTMF digits in stored events and logs (e.g., replacing
  "4111111111111111" with "4111********1111").
- When DTMF redaction is enabled, raw digits MUST NOT appear in `raw_payload`,
  transcripts, or log output.

**Voice model privacy:**

- Audio recordings and transcripts MUST NOT be used for model training without
  explicit integrator and end-user consent.
- Implementations SHOULD provide a configuration flag to disable any data
  sharing with STT/TTS/speech-to-speech providers beyond what is required for
  the API call.

---

### 17.7 Conference Access Security

ConferenceAccess tokens are credentials:

- Tokens SHOULD be minted per participant with least-privilege grants
  (e.g., hidden observers receive subscribe-only grants). ConferenceGrants
  (Section 12.10.2) defaults to permissive values so that the common case
  works unconfigured; narrowing them for a given participant is the
  integrator's call, and is RECOMMENDED wherever a role does not need to
  publish.
- Tokens SHOULD be short-lived (`expires_at`) and MUST NOT be logged.
- Moderation operations (`remove_participant`, `mute_track`,
  `unmute_track`) MUST only be reachable through integrator-controlled code
  paths, never exposed unauthenticated.

**Bot disclosure.** Whether a recording or transcribing bot must be
announced to human participants — and how — is set by the jurisdiction the
deployment operates in, and those rules differ by country and by sector.
This specification therefore mandates no disclosure behaviour and no
restriction on `hidden` observers (Section 12.10.6). It requires instead
that the framework give the integrator what it needs to comply with
whatever applies to it:

- The bot's presence, its `identity`, and its `hidden` status MUST be
  observable to integrator code — the status in force *on the session*,
  not the one it was configured or admitted with: grants can change
  while a session runs (Section 12.10.4), and a surface reporting the
  construction answers a different question than the one a disclosure
  obligation asks.
- Whether STT, vision, or recording is active on a conference MUST be
  observable at any time, not only at configuration time.
- `ON_CONFERENCE_PARTICIPANT_JOINED` MUST fire for every human participant
  the backend delivered, giving the integrator the point at which to
  announce an active bot, gate entry on consent, or record that disclosure
  was made. Across a *reported discontinuity* (Section 12.10.3) that
  guarantee cannot reach the participants whose whole presence fell inside
  the outage window: the discontinuity is the signal that the window is
  unaccounted, and an integrator whose obligations require complete
  attendance MUST treat it so rather than as observed-and-empty.

Implementations SHOULD document this responsibility rather than assume a
default. Deployments in regulated sectors typically do need visible bot
identification; the specification's role is to make that implementable, not
to decide it.

---

## 18. Design Principles

These principles define the conceptual architecture of RoomKit:

1. **The Room is the truth.** All state lives in the Room. The timeline records
   everything.

2. **Everything is a Channel.** SMS, browser, AI, observer — same interface.
   No special cases.

3. **Primitives, not opinions.** The framework provides access, mute, and
   visibility. Business logic decides when to use them.

4. **Two output paths.** Room events are subject to permissions. Side effects
   always flow. Muting silences the voice, not the brain.

5. **Providers are swappable.** Channel type ≠ provider. Twilio and Sinch both
   provide SMS. Anthropic and OpenAI both provide AI.

6. **Hooks intercept.** Sync hooks block and modify. Async hooks observe and
   react. Pipeline architecture.

7. **Channels are dynamic.** Attach, detach, mute, unmute, reconfigure at any
   time during a conversation.

8. **Channel awareness at generation.** AI knows target constraints and media
   types before generating — not after.

9. **Three layers of metadata.** Channel.info (instance), ChannelBinding.metadata
   (per-room), EventSource.channel_data (per-event). Never lose data.

10. **Direction declares capability.** Channels declare inbound/outbound/bidirectional.
    Permissions restrict per room.

11. **Two event levels.** Room events (per-room, stored) and framework events
    (global, for subscribers).

12. **Media types are first-class.** Text, audio, video — route to compatible
    channels. Ready for the future.

13. **Chain depth safety.** Event chains are bounded by a configurable depth
    limit. Uses existing blocked mechanism — no new concepts.

14. **Voice is a channel.** Real-time voice follows the same Room/Channel/Event
    model. STT/TTS are providers. No special "voice API."

15. **Sources complement webhooks.** Persistent connections (WhatsApp Personal,
    SSE) push events. Webhooks pull events. Both feed the same inbound pipeline.

16. **Framework-agnostic core.** No web framework dependency. Integration surfaces
    are thin wrappers. Any language, any framework.

17. **Audio pipeline is transport-independent.** Resampler, AEC, AGC, denoiser,
    VAD, diarization, DTMF, turn detection, and recording run as a pluggable
    pipeline between transport and conversation engine. The transport delivers
    raw frames. The pipeline processes them. Stages are optional and composable.
    Same pattern as text hooks: preprocessing inbound, postprocessing outbound.

18. **Video pipeline mirrors audio.** Decoder, resizer, transforms, filters,
    overlays, vision, and recording run as a pluggable pipeline between the
    video transport and the conversation engine. Same stage pattern as audio:
    pluggable providers, optional stages, session-scoped state. Vision results
    feed back into AI channels and filter contexts.

20. **Agents are channels.** Multi-agent orchestration uses the same
    Room/Channel/Event model. Agents are intelligence channels with identity
    metadata. Routing, handoff, and coordination happen through existing
    primitives — no special agent API.

21. **Orchestration through primitives.** Multi-agent routing, handoff, and
    state management are built on existing Room/Channel/Event/Hook primitives.
    The router is a BEFORE_BROADCAST hook. State lives in room metadata.
    Handoffs are tool calls. No new core abstractions required.

22. **Memory is pluggable.** AI context construction is a swappable strategy,
    not a hardcoded sliding window. Implementations choose how to build
    conversation history: recent events, summarized history, vector retrieval,
    or token-budget-aware truncation.

23. **Audit is two-tiered.** Tool auditing captures every tool call (input,
    output, timing, status). Session auditing captures the full conversation
    timeline (speech, tools, vision, interruptions). Both use pluggable
    backends — same extensibility pattern as providers and stores.

24. **The conference media plane is external.** RoomKit orchestrates
    conferences — rooms, access, participant lifecycle, AI participation —
    but never forwards media between human participants. An external SFU
    owns packet routing; RoomKit joins it as one participant among many.
    Same boundary as storage: the framework defines the interface, the
    deployment provides the infrastructure.

---

## 19. Multi-Agent Orchestration

Multi-agent orchestration enables multiple AI agents to collaborate within a
single room. Agents are intelligence channels with identity metadata. Routing,
handoff, and state management use existing Room/Channel/Event primitives.

### 19.1 Overview

An **Agent** is an AIChannel subclass with structured identity:

```
Agent (extends AIChannel)
├── role: string | null                     # "Senior Engineer", "Triage Agent"
├── description: string | null              # Agent capabilities description
├── scope: string | null                    # "Backend systems", "Billing"
├── voice: string | null                    # TTS voice identifier
├── greeting: string | null                 # Auto-greeting text on session start
├── language: string | null                 # Preferred language
├── auto_greet: bool (default true)         # Play greeting on voice session start
│
├── is_config_only: bool (read-only)        # True when no AI provider (speech-to-speech mode)
└── build_identity_block(language) → string # Generate identity context for system prompt
```

When `is_config_only` is true, the Agent has no AI provider and serves as a
configuration container for speech-to-speech channels (voice, greeting, language
metadata). A null provider MUST be accepted — no generation calls are made.

Multiple Agents MAY be attached to a single room. The orchestration system
determines which Agent handles each event, unless the event names its
recipients itself (§19.3).

### 19.2 ConversationState

Each room MAY have a `ConversationState` stored in room metadata:

```
ConversationState
├── phase: string | null                    # Current conversation phase ("triage", "specialist")
├── active_agent_id: string | null          # Agent currently handling the conversation
├── language: string | null                 # Detected participant language
└── metadata: map<string, any>              # Custom state (intent, escalation level, etc.)
```

Phase transitions MUST be explicit — either via handoff or programmatic update.
The framework fires `ON_PHASE_TRANSITION` hooks on state changes.

`active_agent_id` MAY be written by the host, not only by a handoff: a
console that switches which agent it is talking to is a legitimate writer of
this field. Implementations SHOULD expose a supported way to set it —
reaching into room metadata from application code is not one.

### 19.3 Addressing

Routing rules answer *which agent handles this kind of event*. Addressing
answers a different question, asked per message by whoever sends it:
**which agents are being asked to act, right now**. A room where a human
types `@codex review hello.py` needs the second question, and no rule
expresses it.

An event MAY carry an address:

```
RoomEvent
└── addressed_to: list<channel_id> | null    # null = unaddressed
```

**Addressing is not visibility.** Visibility (§7.3) is configured on a
binding and answers who may *see* what a source produces. Addressing is set
on an event by its sender and answers who is *asked to act*. The two are
orthogonal: addressing one agent MUST NOT hide the event from any channel
visibility would have shown it to.

Normative rules:

1. Addressing constrains **intelligence** channels only. Delivery to
   transport channels MUST NOT be affected — a message addressed to one
   agent still reaches the humans in the room.
2. When `addressed_to` is non-null, the channels it names are the only
   intelligence channels solicited for that event. Named ids not bound to
   the room are ignored; if none of them is bound, no intelligence channel
   is solicited.
3. An empty list addresses nobody: the event is stored and delivered, and no
   agent is asked to respond.
4. `addressed_to` is part of the stored event, so a transcript can show who
   was asked and a replay reproduces the same solicitation.

**Unaddressed events** (`addressed_to = null`) keep the behaviour of earlier
versions: the router decides (§19.4), and with no router installed every
eligible intelligence channel is solicited.

**Conformance.** Addressing itself is Level 0 — the field exists on every
event and MUST be honoured when set, which an implementation without
intelligence channels satisfies trivially. The router precedence (§19.4,
step 0) and the named policies below belong to Level 2 with the rest of this
section.

#### 19.3.1 Agent-sourced events

An agent's own output is an event like any other, and by default it solicits
the other agents in the room — the chaining Appendix B.4 describes, bounded
by `max_chain_depth`. That is a feature for a pipeline (analyst → writer)
and a hazard for a room of independent agents, where two agents answer each
other until the depth limit stops them.

Implementations MUST provide both policies, selectable per room:

| Policy | An agent's output solicits |
|---|---|
| `AGENT_CHAIN` | every eligible intelligence channel — the behaviour of earlier versions |
| `ADDRESSED_ONLY` | only the channels named in `addressed_to`, if any |

`AGENT_CHAIN` MUST remain the default, so a room written against an earlier
version behaves unchanged. Under either policy an explicit address is
honoured: an agent MAY address another agent and be answered by it alone.

#### 19.3.2 Delivered versus solicited

A channel that is not solicited MUST NOT be asked to produce a response.
Whether it is nonetheless *delivered* the event — told that it happened,
without being asked to answer — is **not specified by this version**;
implementations MAY skip such a channel entirely.

The distinction is not academic. An agent whose context is rebuilt from the
room's timeline on every turn loses nothing by being skipped. An agent that
owns conversational state outside RoomKit — an ACP coding agent holding a
session in its own process — permanently lacks whatever it was not
delivered, so the two behaviours produce materially different rooms. A
future amendment will specify this; until then an implementation MUST
document which behaviour it provides.

### 19.4 ConversationRouter

The `ConversationRouter` selects which Agent processes each event. It is
installed as a `BEFORE_BROADCAST` sync hook.

```
ConversationRouter
├── rules: list<RoutingRule>                # Ordered by priority
├── default_agent_id: string | null         # Fallback when no rule matches
└── supervisor_id: string | null            # Always receives events (if set)
```

**RoutingRule:**

```
RoutingRule
├── agent_id: string                        # Target agent
├── conditions: RoutingConditions           # When this rule applies
└── priority: int (default 0)               # Lower = evaluated first
```

**RoutingConditions:**

```
RoutingConditions
├── phases: set<string> | null              # Match when ConversationState.phase is in set
├── channel_types: set<ChannelType> | null  # Match when source channel type is in set
├── intents: set<string> | null             # Match on detected intent
├── source_channel_ids: set<string> | null  # Match on specific source channels
└── custom: function | null                 # Arbitrary predicate (event, context, state) → bool
```

**Evaluation order:**

0. If the event is addressed (§19.3), the address decides. The router MUST
   NOT override it, and steps 1–3 are skipped.
1. If `ConversationState.active_agent_id` is set and no phase transition
   occurred, route to the active agent (sticky affinity).
2. Evaluate rules in priority order. First matching rule wins.
3. If no rule matches, use `default_agent_id`.
4. If `supervisor_id` is set, the supervisor ALWAYS receives the event
   (in addition to the selected agent, or to the addressed channels).

Step 0 exists because sticky affinity would otherwise swallow every explicit
request. With the active agent consulted first, a rule written to honour an
address is unreachable for as long as any agent holds the conversation — the
two mechanisms could not coexist. An address is a direct instruction from
the sender and outranks both the affinity and the rules.

The router stamps routing metadata on the event. The Event Router skips
non-targeted intelligence channels during broadcast.

### 19.5 ConversationPipeline

A `ConversationPipeline` generates `RoutingRule` entries from a linear stage
definition:

```
ConversationPipeline
├── stages: list<PipelineStage>
├── default_phase: string | null            # Initial phase (first stage if null)
└── supervisor_id: string | null            # Supervisor for all stages
```

**PipelineStage:**

```
PipelineStage
├── phase: string                           # Phase name ("triage", "specialist", "closing")
├── agent_id: string                        # Agent handling this phase
├── next: string | null                     # Next phase on handoff (null = terminal)
├── can_return_to: set<string>              # Phases this stage can return to
└── description: string | null              # Human-readable stage description
```

The pipeline generates one `RoutingRule` per stage with
`conditions.phases = {stage.phase}`.

**Allowed transitions:** An agent in phase P MAY hand off to:
- `stage.next` (forward progression)
- Any phase in `stage.can_return_to` (backward/lateral)
- Transitions to other phases MUST be rejected.

### 19.6 HandoffHandler

Agents request handoffs by calling the `handoff_conversation` tool:

**HandoffRequest:**

```
HandoffRequest
├── target_agent_id: string                 # Agent to hand off to
├── reason: string                          # Why the handoff is happening
├── summary: string                         # Context summary for the target agent
├── context: map<string, any>               # Additional handoff context
├── channel_escalation: string | null       # "same", "voice", "email", "sms" (channel switch)
└── urgent: bool (default false)            # Priority flag
```

**HandoffResult:**

```
HandoffResult
├── accepted: bool                          # Whether the handoff was accepted
├── new_agent_id: string | null             # Active agent after handoff
├── new_phase: string | null                # Phase after handoff
├── message: string                         # Human-readable result
└── reason: string                          # Rejection reason (if not accepted)
```

**Handoff protocol:**

1. Agent calls `handoff_conversation` tool with `HandoffRequest`.
2. `HandoffHandler` validates:
   - Target agent exists and is attached to the room.
   - Phase transition is allowed (per pipeline rules, if applicable).
3. If valid:
   - Update `ConversationState.phase` and `active_agent_id`.
   - Fire `ON_HANDOFF` hook.
   - Fire `ON_PHASE_TRANSITION` hook.
   - Return `HandoffResult(accepted=true)`.
4. If invalid:
   - Fire `ON_HANDOFF_REJECTED` hook.
   - Return `HandoffResult(accepted=false, reason=...)`.

The handoff summary is injected into the target agent's context so it
has continuity.

### 19.7 Orchestration Strategies

The following strategies are common patterns built on router and pipeline
primitives. Implementations SHOULD provide helpers for each.

#### 19.7.1 Pipeline

Agents are chained linearly. Each agent handles one phase and hands off to
the next:

```
Triage → Specialist → Resolution → Closing
```

The first agent is the entry point. Only forward transitions (and explicitly
allowed backward transitions) are permitted.

#### 19.7.2 Swarm

Every agent can hand off to every other agent. No linear ordering. Useful
for collaborative agent pools where any agent may be most appropriate:

```
Agent A ⇄ Agent B ⇄ Agent C
```

Sticky affinity keeps the conversation with the current agent until an
explicit handoff occurs.

#### 19.7.3 Supervisor

A supervisor agent talks to the user and delegates work to specialist agents.
Specialists run in isolated **child rooms** — their output is collected and
returned to the supervisor.

```
User ↔ Supervisor
              ├── delegates to → Worker A (child room)
              └── delegates to → Worker B (child room)
```

The supervisor MAY delegate sequentially or in parallel. Results are delivered
back via the delivery strategy system (Section 23).

#### 19.7.4 Loop

A single agent handles the conversation indefinitely, looping back for
refinement. Useful for iterative workflows (editing, code review, tutoring).

### 19.8 StatusBus

The `StatusBus` enables inter-agent coordination through status messages:

```
StatusBus (interface)
├── post(room_id, agent_id, status, metadata) → void
├── subscribe(room_id, callback) → unsubscribe_function
└── get_latest(room_id, agent_id) → Status | null
```

Status posts fire `ON_STATUS_POSTED` hooks. Agents MAY use the StatusBus to
signal completion, progress, or request attention without sending room events.

---

## 20. Memory System

The Memory System provides pluggable AI context construction. Instead of
always using a fixed sliding window of recent events, implementations MAY
choose different strategies for building conversation history.

### 20.1 MemoryProvider Interface

```
MemoryProvider (interface)
├── retrieve(room_id, current_event, context, channel_id) → MemoryResult
│       # Build conversation context for AI generation
│       # Called by AIChannel before each generation
│
└── close() → void
        # Release resources
```

A provider is handed history, it does not fetch it: the `context` it receives
MUST already be the requesting channel's view of the room (§7.5 rule 8). Making
each provider apply the visibility filter itself would put the rule in seven
places and leave every third-party provider outside it; making the caller apply
it once puts it in one, and a provider that summarizes what it is given can then
never summarize something the channel was not allowed to read.

### 20.2 MemoryResult

```
MemoryResult
├── messages: list<AIMessage>               # Pre-built AI messages (summaries, instructions)
└── events: list<RoomEvent>                 # Raw events for AIChannel to convert
```

When `messages` is non-empty, the AIChannel uses them directly as conversation
history. When `events` is provided, the AIChannel converts them to AI messages
using its standard conversion logic. Both MAY be combined — `messages` are
prepended before converted `events`.

### 20.3 Built-in Implementations

| Implementation | Strategy | Use Case |
|---|---|---|
| SlidingWindowMemory | Last N events | Default, simple conversations |
| CompactingMemory | Merges older events into compact summaries | Long conversations, reduce tokens |
| SummarizingMemory | AI-powered summarization of history | Complex multi-topic conversations |
| RetrievalMemory | Vector search for relevant past events | Large knowledge-heavy contexts |
| BudgetAwareMemory | Token-based truncation with priorities | Strict token budget enforcement |

**SlidingWindowMemory** is the default when no MemoryProvider is configured.
It returns the most recent `max_context_events` from the room timeline.

**SummarizingMemory** calls an AI provider to summarize older history,
keeping recent events intact. The summary is cached and refreshed
periodically or when the event count exceeds a threshold.

**RetrievalMemory** embeds events using a vector store and retrieves the
most semantically relevant past events for the current message. This enables
recall of earlier conversation topics without carrying the full history.

**BudgetAwareMemory** counts tokens and evicts oldest events when the total
exceeds `evict_threshold_tokens`. It prioritizes keeping system messages,
tool results, and recent events.

---

## 21. Tool Access Control

### 21.1 ToolPolicy

A `ToolPolicy` controls which tools an AI agent can invoke:

```
ToolPolicy
├── allow: list<string>                     # Glob patterns for allowed tools
├── deny: list<string>                      # Glob patterns for denied tools
└── role_overrides: map<string, RoleOverride>  # Per-role policy adjustments
```

**Resolution rules:**

1. If `deny` matches the tool name, the tool is DENIED (deny always wins).
2. If `allow` is non-empty and the tool name does NOT match any allow pattern,
   the tool is DENIED (whitelist mode).
3. Otherwise, the tool is ALLOWED.

Glob patterns support `*` (any characters) and `?` (single character).
Example: `allow: ["search_*", "get_*"]` permits all search and get tools.

**RoleOverride:**

```
RoleOverride
├── allow: list<string> | null              # Additional allow patterns
├── deny: list<string> | null               # Additional deny patterns
└── mode: "restrict" | "replace"            # Merge with base or replace entirely
```

When `mode` is `"restrict"`, the override's allow/deny lists are merged with
the base policy. When `"replace"`, the override completely replaces the base.

### 21.2 MCP Tool Provider

Implementations SHOULD support loading tools from MCP (Model Context Protocol)
servers via an `MCPToolProvider`:

```
MCPToolProvider
├── server_url: string                      # MCP server endpoint
├── tools() → list<ToolDefinition>          # Discover available tools
└── call(name, arguments) → string          # Execute a tool
```

MCP tools are subject to the same `ToolPolicy` as local tools.

### 21.3 AI Steering Directives

Steering directives allow dynamic mid-conversation control of AI behavior.
They are injected into the AI generation context:

| Directive | Effect |
|---|---|
| Cancel | Abort the current generation immediately |
| UpdateSystemPrompt | Append additional instructions to the system prompt |
| InjectMessage | Add a synthetic user or assistant message to the conversation history |

Steering directives are typically issued by orchestration logic (e.g.,
supervisor injecting context for a worker agent) or by hooks reacting to
events.

---

## 22. Delivery Strategies

Delivery strategies control how proactive content (background task results,
delegated agent output, scheduled messages) is delivered into a conversation.

### 22.1 DeliveryStrategy Interface

```
DeliveryStrategy (interface)
└── deliver(context: DeliveryContext) → void
```

**DeliveryContext:**

```
DeliveryContext
├── kit: RoomKit                            # Framework instance
├── room_id: string                         # Target room
├── content: EventContent                   # Content to deliver
├── channel_id: string                      # Source channel for attribution
└── metadata: map<string, any>              # Delivery metadata
```

### 22.2 Built-in Strategies

| Strategy | Behavior |
|---|---|
| Immediate | Deliver synchronously. May interrupt active voice playback. |
| WaitForIdle(buffer_seconds) | Wait until both AI generation and user input are idle for `buffer_seconds`, then deliver. Prevents interrupting active exchanges. |
| Queued(buffer_seconds) | Batch multiple delivery items, then deliver together after `buffer_seconds` of inactivity. |

**WaitForIdle** is RECOMMENDED for voice channels where interruptions are
disruptive. It monitors both the AI generation state and user speech activity
before injecting content.

### 22.3 Delivery Hooks

| Hook | Execution | When |
|---|---|---|
| BEFORE_DELIVER | SYNC | Before strategy executes — can block or modify content |
| AFTER_DELIVER | ASYNC | After delivery completes |

---

## 23. Task Delegation

Task delegation enables agents to offload background work to specialized
agents running in isolated child rooms. Results are collected and delivered
back to the parent conversation.

### 23.1 TaskRunner Interface

```
TaskRunner (interface)
├── run(task: DelegatedTask) → void
│       # Execute the task asynchronously
│
└── close() → void
        # Cancel in-flight tasks and release resources
```

Implementations MUST provide an `InMemoryTaskRunner` for single-process
deployments.

### 23.2 DelegatedTask

```
DelegatedTask
├── id: string                              # Unique task identifier
├── room_id: string                         # Parent room
├── agent_id: string                        # Agent to execute the task
├── task: string                            # Task description / instructions
├── notify: string | null                   # Channel to notify on completion
├── strategy: DeliveryStrategy | null       # How to deliver results (default: Immediate)
├── status: TaskStatus                      # PENDING, IN_PROGRESS, COMPLETED, FAILED
├── result: string | null                   # Task result (on completion)
├── error: string | null                    # Error message (on failure)
├── created_at: datetime
└── completed_at: datetime | null
```

### 23.3 Delegation Protocol

When `delegate(room_id, agent_id, task, notify, strategy)` is called:

1. Create a **child room** linked to the parent room.
2. Attach the specified agent as an INTELLIGENCE channel in the child room.
3. Share relevant channels from the parent (for context access).
4. Inject the task description as a system event in the child room.
5. The agent processes the task and generates a response.
6. Collect the agent's response as the task result.
7. Fire `ON_TASK_COMPLETED` hook in the parent room.
8. If `notify` is set, deliver the result to the specified channel using
   the delivery strategy.

### 23.4 Delegation Tools

Implementations SHOULD provide helpers for AI-driven delegation:

- `build_delegate_tool(agents)` — Creates an AI tool definition that lets
  an agent delegate work to other agents. The `agents` parameter lists
  available delegation targets with descriptions.

- `setup_delegation(agent, handler, tool)` — Wires the delegation tool into
  an agent, connecting it to the TaskRunner.

### 23.5 Delegation Hooks

| Hook | Execution | When |
|---|---|---|
| ON_TASK_DELEGATED | ASYNC | Task created and child room initialized |
| ON_TASK_COMPLETED | ASYNC | Task completed with result (or failed with error) |

---

## 24. Skills Framework

The Skills Framework enables agent capabilities to be defined as discoverable,
self-contained packages.

### 24.1 Skill Definition

A Skill is defined by a `SKILL.md` file with YAML frontmatter:

```
---
name: "web-search"
description: "Search the web for current information"
version: "1.0.0"
license: "MIT"
tools:
  - search_web
  - fetch_url
allowed_tools:
  - "search_*"
  - "fetch_*"
---

## Instructions

You are a web search specialist. When asked to find information...

## References

- [Search API docs](https://...)
```

### 24.2 SkillMetadata

```
SkillMetadata
├── name: string                            # Unique skill identifier
├── description: string                     # What the skill does
├── version: string | null                  # Semantic version
├── license: string | null                  # License identifier
├── tools: list<string>                     # Tools this skill provides
├── allowed_tools: list<string>             # Tool access patterns (ToolPolicy globs)
└── path: string                            # Filesystem path to skill directory
```

### 24.3 SkillRegistry

```
SkillRegistry
├── discover(*directories) → int            # Scan directories for SKILL.md files, return count
├── register(skill_dir) → SkillMetadata     # Register a single skill
├── get_metadata(name) → SkillMetadata | null  # Look up skill metadata
├── get_skill(name) → Skill | null          # Load full skill (metadata + instructions)
├── all_metadata() → list<SkillMetadata>    # List all registered skills
└── to_prompt_xml() → string               # Generate <available_skills> XML for AI context
```

Skills are injected into the AI agent's system prompt via `to_prompt_xml()`.
The agent can then select and apply skills based on the user's request.

---

## 25. Conformance Levels

### 25.1 Level 0: Core (REQUIRED)

A conforming implementation MUST support:

- Room model with lifecycle (ACTIVE, PAUSED, CLOSED, ARCHIVED), including
  refusing new events at every entry point once the status says so (Section 5.1)
- Room timers (auto-pause, auto-close)
- RoomEvent with all EventType values and all EventContent types
- Sequential event indexing
- Channel interface (handle_inbound, deliver, on_event, capabilities)
- ChannelBinding with access, mute, and visibility
- Permission enforcement (Section 7.5)
- Hook engine with SYNC and ASYNC execution
- BEFORE_BROADCAST and AFTER_BROADCAST hooks with HookResult
- InjectedEvent delivery on block
- Event chain depth tracking and limiting
- Inbound processing pipeline (Section 10.1)
- Broadcast pipeline (Section 10.2)
- Reentry passes (response events re-enter the pipeline as commit passes)
- Inbound room routing (pluggable)
- Room-level locking
- ConversationStore interface with in-memory implementation
- Content transcoding (at least text fallback)
- Framework events (Section 8.2)
- Structured logging
- Idempotency checking
- Event addressing: `RoomEvent.addressed_to`, honoured when set (Section 19.3)

### 25.2 Level 1: Transport (RECOMMENDED)

A Level 1 implementation SHOULD additionally support:

- At least one SMS provider
- At least one Email provider
- WebSocket channel
- HTTP/Webhook channel
- AI channel with at least one AI provider
- Agent class (AIChannel subclass with identity metadata)
- Provider abstraction (swappable per channel type)
- Identity resolution pipeline
- Identity hooks (ON_IDENTITY_AMBIGUOUS, ON_IDENTITY_UNKNOWN)
- Participant model with identification status
- Memory system with at least SlidingWindowMemory (Section 20)
- Circuit breaker
- Retry policy
- Rate limiting
- REST API (Section 16.1)
- Telemetry provider abstraction (Section 15.7)

### 25.3 Level 2: Rich (OPTIONAL)

A Level 2 implementation MAY additionally support:

- WhatsApp channel (Business and/or Personal)
- Messenger channel
- Teams channel
- Telegram channel
- RCS channel with SMS fallback
- Template content support
- Source providers (persistent connections)
- MCP Server (Section 16.2)
- ACP agent channel (Section 6.4)
- Realtime/ephemeral events backend
- Per-room hooks
- Multi-agent orchestration (Section 19):
  - ConversationRouter with routing rules, addresses taking precedence
    (Section 19.4, step 0)
  - Both agent-response policies, selectable per room (Section 19.3.1)
  - ConversationPipeline with stages
  - HandoffHandler with tool-based handoff protocol
  - At least Pipeline and Swarm strategies
- Tool access control with ToolPolicy (Section 21)
- Task delegation with child rooms (Section 23)
- Delivery strategies: Immediate, WaitForIdle, Queued (Section 22)
- Skills framework with SkillRegistry (Section 24)
- AI steering directives (Section 21.3)
- Advanced memory providers: Summarizing, Retrieval (Section 20)

### 25.4 Level 3: Real-Time Media (OPTIONAL)

A Level 3 implementation MAY additionally support audio and/or video real-time media:

#### Audio (Voice)

- Audio Processing Pipeline with:
  - AudioFrame and AudioFormat data models
  - AudioPipelineConfig with pipeline format contract
  - ResamplerConfig (RECOMMENDED)
  - VADProvider interface with at least one implementation (e.g., Silero) — REQUIRED for VoiceChannel, OPTIONAL for RealtimeVoiceChannel
  - DenoiserProvider interface (OPTIONAL, e.g., sherpa-onnx)
  - AECProvider interface (OPTIONAL, RECOMMENDED for non-WebRTC transports)
  - AGCProvider interface (OPTIONAL, built-in implementation REQUIRED)
  - DTMFDetector interface (OPTIONAL, RECOMMENDED for SIP/PSTN)
  - DiarizationProvider interface (OPTIONAL)
  - TurnDetector interface (OPTIONAL)
  - BackchannelDetector interface (OPTIONAL)
  - AudioRecorder interface (OPTIONAL, RECOMMENDED for regulated industries)
  - AudioPostProcessor interface (OPTIONAL)
  - InterruptionConfig
- Voice channel (STT/TTS pipeline)
- VoiceBackend interface with at least one implementation
- Packet loss concealment for lossy transports (OPTIONAL, RECOMMENDED for RTP backends — Section 12.2.1)
- STTProvider interface with at least one implementation
- TTSProvider interface with at least one implementation
- Voice hooks (ON_SPEECH_START through ON_RECORDING_STOPPED)
- Barge-in and interruption handling (InterruptionStrategy)
- Realtime Voice channel (speech-to-speech)
- RealtimeVoiceProvider interface
- RealtimeAudioTransport interface
- Realtime voice hooks (ON_REALTIME_TOOL_CALL, ON_PROTOCOL_TRACE)
- Protocol trace infrastructure (ProtocolTrace, emit_trace, on_trace, pre-room buffering)

#### Video

- Video data models:
  - VideoFrame — inbound frame container (encoded NAL units or raw pixels)
  - VideoChunk — outbound encoded frame container
  - VideoSession — active video connection state
  - VideoCapability flags (SIMULCAST, SVC, SCREEN_SHARE, RECORDING, BANDWIDTH_ESTIMATION)
- VideoBackend interface — transport abstraction (connect, disconnect, send_video, callbacks)
- VideoChannel — session-based channel orchestrator:
  - Session lifecycle with dual-signal ready mechanism (matching VoiceChannel pattern)
  - Hook triggers: ON_VIDEO_SESSION_STARTED, ON_VIDEO_SESSION_ENDED, ON_VIDEO_TRACK_ADDED, ON_VIDEO_TRACK_REMOVED, ON_SCREEN_SHARE_STARTED, ON_SCREEN_SHARE_STOPPED
  - Optional VisionProvider integration with configurable analysis interval
  - Vision results emitted as framework events (video_vision_result)
- VisionProvider interface — frame analysis abstraction:
  - analyze_frame(frame) → VisionResult (description, labels, confidence, faces, OCR text)
  - analyze_stream(frames, interval_ms) for streaming analysis
  - Implementations: OpenAI-compatible (GPT-4o, Ollama, vLLM), Gemini, Mock
- AI integration: setup_video_vision() wires vision descriptions into AIChannel system prompt
- Video and voice channels operate independently in the same room, enabling combined audio+video sessions where the AI can both hear (via STT) and see (via VisionProvider)

#### Conference (SFU) — PROVISIONAL

- Conference data models (ConferenceTrack, TrackKind, ConferenceParticipant,
  ConferenceGrants, ConferenceAccess, BotSession, ConferenceCapability)
- ConferenceBackend interface with MockConferenceBackend (Section 12.10.3)
- ConferenceChannel with per-track STT lanes and bot TTS publication
  (Section 12.10.4)
- Conference hooks (ON_CONFERENCE_PARTICIPANT_JOINED/LEFT,
  ON_CONFERENCE_TRACK_PUBLISHED/UNPUBLISHED, ON_ACTIVE_SPEAKER_CHANGED)
- Explicit track subscription, participant identity correlation, and bot
  self-exclusion (Sections 12.10.2–12.10.4)
- Multi-party interruption policy (ConferenceInterruptionConfig)
- Participant lifecycle integration (conference events create/update
  Participant records)
- Optional: vision on tracks, egress recording delegation, SIP gateway
  interop, bot video publication (avatar), speech-to-speech composition

---

## Appendix A: Channel Reference

### A.1 SMS Channel

```
SMSChannel
├── type: SMS
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, MEDIA]
├── capabilities:
│   ├── max_length: 1600
│   ├── supports_read_receipts: true
│   ├── supports_media: true
│   ├── supported_media_types: ["image/jpeg", "image/png", "image/gif"]
│   ├── supports_edit: false
│   └── supports_delete: false
├── provider_interface: SMSProvider
│   ├── send(event, to, from) → ProviderResult
│   ├── parse_webhook(payload) → InboundMessage
│   └── verify_signature(payload, signature, timestamp) → bool
└── binding_metadata:
    └── phone_number: string (recipient)
```

### A.2 Email Channel

```
EmailChannel
├── type: EMAIL
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA]
├── capabilities:
│   ├── max_length: null (unlimited)
│   ├── supports_threading: true
│   ├── supports_rich_text: true
│   ├── supports_media: true
│   ├── supports_edit: false
│   └── supports_delete: false
├── provider_interface: EmailProvider
│   ├── send(event, to, from, subject) → ProviderResult
│   └── parse_inbound(payload) → InboundMessage
└── binding_metadata:
    ├── email_address: string (recipient)
    └── subject: string | null
```

### A.3 WhatsApp Channel

```
WhatsAppChannel
├── type: WHATSAPP
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA, LOCATION, TEMPLATE]
├── capabilities:
│   ├── max_length: 4096
│   ├── supports_reactions: true
│   ├── supports_templates: true
│   ├── supports_buttons: true (max 3)
│   ├── supports_quick_replies: true
│   ├── supports_read_receipts: true
│   ├── supports_media: true
│   ├── supports_edit: true
│   └── supports_delete: true
├── provider_interface: WhatsAppProvider
│   ├── send(event, to) → ProviderResult
│   ├── send_template(template, to) → ProviderResult
│   └── send_reaction(chat, message_id, emoji) → ProviderResult
└── binding_metadata:
    └── phone_number: string (recipient)
```

### A.4 WhatsApp Personal Channel

```
WhatsAppPersonalChannel
├── type: WHATSAPP_PERSONAL
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA, AUDIO, VIDEO, LOCATION]
├── capabilities:
│   ├── max_length: 4096
│   ├── supports_reactions: true
│   ├── supports_typing: true
│   ├── supports_read_receipts: true
│   ├── supports_audio: true
│   ├── supports_video: true
│   ├── supports_media: true
│   ├── supports_edit: true
│   └── supports_delete: true
├── source: WhatsAppPersonalSourceProvider
│   └── Persistent multidevice connection via neonize or equivalent
├── provider_interface: WhatsAppPersonalProvider
│   ├── send_message(jid, text) → ProviderResult
│   ├── send_image(jid, data, caption) → ProviderResult
│   ├── send_audio(jid, data, ptt) → ProviderResult
│   ├── send_video(jid, data, caption) → ProviderResult
│   ├── send_document(jid, data, filename) → ProviderResult
│   ├── send_location(jid, lat, lon, name, address) → ProviderResult
│   └── send_reaction(chat, sender, message_id, emoji) → ProviderResult
└── binding_metadata:
    └── phone_number: string (recipient)
```

### A.5 Messenger Channel

```
MessengerChannel
├── type: MESSENGER
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA, TEMPLATE]
├── capabilities:
│   ├── max_length: 2000
│   ├── supports_buttons: true (max 3)
│   ├── supports_quick_replies: true
│   ├── supports_read_receipts: true
│   ├── supports_media: true
│   ├── supports_edit: false
│   └── supports_delete: true
├── provider_interface: MessengerProvider
│   ├── send(event, recipient_id) → ProviderResult
│   └── parse_webhook(payload) → InboundMessage
└── binding_metadata:
    └── facebook_user_id: string (recipient)
```

### A.6 Teams Channel

```
TeamsChannel
├── type: TEAMS
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH]
├── capabilities:
│   ├── max_length: 28000
│   ├── supports_threading: true
│   ├── supports_reactions: true
│   ├── supports_read_receipts: true
│   ├── supports_rich_text: true
│   ├── supports_edit: true
│   └── supports_delete: true
├── provider_interface: TeamsProvider
│   ├── send(event, conversation_reference) → ProviderResult
│   ├── parse_webhook(activity) → InboundMessage
│   └── save_conversation_reference(activity) → void
├── requires: ConversationReferenceStore
└── binding_metadata:
    └── teams_conversation_id: string
```

### A.7 RCS Channel

```
RCSChannel
├── type: RCS
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA]
├── capabilities:
│   ├── max_length: 8000
│   ├── supports_buttons: true
│   ├── supports_cards: true
│   ├── supports_quick_replies: true
│   ├── supports_read_receipts: true
│   ├── supports_typing: true
│   ├── supports_media: true
│   ├── supports_edit: false
│   └── supports_delete: false
├── provider_interface: RCSProvider
│   ├── send(event, to) → RCSDeliveryResult
│   ├── check_capability(phone) → bool
│   └── RCSDeliveryResult includes: channel_used, fallback flag
└── configuration:
    └── fallback: bool (auto-fallback to SMS when RCS unavailable)
```

### A.8 WebSocket Channel

```
WebSocketChannel
├── type: WEBSOCKET
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA, AUDIO, VIDEO, LOCATION]
├── capabilities:
│   ├── max_length: null (unlimited)
│   ├── supports_typing: true
│   ├── supports_read_receipts: true
│   ├── supports_reactions: true
│   ├── supports_buttons: true
│   ├── supports_cards: true
│   ├── supports_quick_replies: true
│   ├── supports_audio: true
│   ├── supports_video: true
│   ├── supports_media: true
│   ├── supports_edit: true
│   └── supports_delete: true
├── connection_registry: map<connection_id, send_function>
│   ├── register_connection(id, send_fn) → void
│   └── unregister_connection(id) → void
└── delivery: broadcasts to all registered connections
```

### A.9 AI Channel

```
AIChannel
├── type: AI
├── category: INTELLIGENCE
├── direction: BIDIRECTIONAL
├── media_types: [TEXT]
├── capabilities:
│   ├── supports_rich_text: true (provider-dependent)
│   ├── supports_edit: false
│   └── supports_delete: false
├── configuration:
│   ├── provider: AIProvider
│   ├── system_prompt: string | null
│   ├── temperature: float | null
│   ├── max_tokens: int | null
│   ├── max_context_events: int | null
│   ├── thinking_budget: int | null         # Token budget for extended thinking/reasoning
│   ├── max_tool_rounds: int (default 200)  # Maximum tool call iterations per generation
│   ├── tool_loop_timeout_seconds: float | null (default 300)  # Timeout for entire tool loop
│   ├── fallback_provider: AIProvider | null # Fallback if primary provider fails
│   ├── evict_threshold_tokens: int (default 5000)  # Token threshold for context eviction
│   ├── memory: MemoryProvider | null       # Pluggable context construction (Section 20)
│   ├── tool_policy: ToolPolicy | null      # Tool access control (Section 21)
│   └── skills: SkillRegistry | null        # Available skills (Section 24)
├── per_room_overrides (via binding metadata):
│   ├── system_prompt
│   ├── temperature
│   ├── max_tokens
│   ├── thinking_budget
│   └── tools
├── ai_response_model:
│   │   # AI responses consist of ordered parts:
│   ├── AITextPart                          # Generated text content
│   ├── AIThinkingPart                      # Chain-of-thought reasoning (preserved in history)
│   ├── AIToolCallPart                      # Function call with name and arguments
│   └── AIToolResultPart                    # Tool execution result
└── behavior:
    ├── on_event() builds conversation history + target capabilities
    ├── Calls provider.generate(messages, context)
    ├── Runs tool loop: generate → call tools → feed results → re-generate (up to max_tool_rounds)
    ├── Skips events from self (loop prevention)
    ├── Supports streaming via generate_stream() and deliver_stream()
    └── Returns ChannelOutput with response events + tasks + observations
```

### A.9.1 ACP Agent Channel

```
ACPChannel
├── type: AI
├── category: INTELLIGENCE
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH]
├── role: ACP client (external coding agent is the ACP server)
├── transport:
│   ├── stable default: stdio
│   ├── command: argument vector (never shell-expanded)
│   └── protocol_version: stable ACP version
├── sessions:
│   ├── one ACP connection per channel instance
│   ├── one ACP session per Room
│   └── prompts serialized per session
├── configuration:
│   ├── command: list<string>
│   ├── cwd: absolute path
│   ├── additional_directories: list<absolute path>
│   ├── environment: map<string, string> | null
│   ├── authentication_method: string | null
│   ├── mcp_servers: list<ACP MCPServer>
│   └── external_tool_handler: ExternalToolHandler | null
├── update_mapping:
│   ├── agent_message_chunk → text stream delta
│   ├── agent_thought_chunk → thinking stream marker + ephemeral event
│   ├── tool_call_start/progress → tool-call markers + ephemeral events
│   └── agent_plan_update → ephemeral custom event
└── safety:
    ├── filesystem/terminal client capabilities disabled by default
    ├── permission requests denied by default
    ├── cancellation forwarded to ACP session
    └── close releases sessions and process transport
```

### A.10 Voice Channel

```
VoiceChannel
├── type: VOICE
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [AUDIO]
├── requires:
│   ├── stt: STTProvider
│   ├── tts: TTSProvider
│   ├── backend: VoiceBackend
│   └── audio_pipeline: AudioPipelineConfig
├── configuration:
│   ├── streaming: bool (default true)
│   ├── enable_barge_in: bool (default false)
│   └── barge_in_threshold_ms: int (default 500)
├── streaming_delivery:
│   ├── supports_streaming_delivery: bool
│   │   # True when TTS supports streaming input AND backend is configured
│   └── deliver_stream(text_stream, event, binding, context) → ChannelOutput
│       # Pipes text stream → sentence_splitter → synthesize_stream_input → outbound → transport
│       # Fires AFTER_TTS hook after stream completes
├── session_management:
│   ├── bind_session(session, room_id, binding)
│   └── unbind_session(session)
└── delivery:
    ├── Standard path:
    │   ├── AudioContent → [postprocessors] → [recorder] → [resampler] → transport → [AEC ref †]
    │   ├── TextContent → TTS → AudioChunk stream → outbound pipeline → transport → [AEC ref †]
    │   └── Other → error
    ├── Streaming AI → TTS path (framework-native):
    │   └── Framework pipes AIChannel.response_stream → deliver_stream()
    │       → sentence_splitter → synthesize_stream_input() → outbound pipeline → transport
    └── † AEC ref fed at transport level (local hw) or pipeline level (network) — see 12.3.4
```

### A.11 Realtime Voice Channel

```
RealtimeVoiceChannel
├── type: REALTIME_VOICE
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [AUDIO]
├── requires:
│   ├── provider: RealtimeVoiceProvider
│   ├── transport: RealtimeAudioTransport
│   └── audio_pipeline: AudioPipelineConfig | null  # OPTIONAL in speech-to-speech mode
├── configuration:
│   ├── system_prompt: string | null
│   ├── voice: string | null
│   ├── tools: list<ToolDefinition>
│   ├── temperature: float | null
│   ├── input_sample_rate: int
│   ├── output_sample_rate: int
│   └── emit_transcription_events: bool
├── session_management:
│   ├── start_session(room_id, participant_id, connection, metadata)
│   └── end_session(session)
└── tool_handling:
    ├── async handler function (priority)
    └── ON_REALTIME_TOOL_CALL hook (fallback)
```

### A.12 Video Channel

```
VideoChannel
├── channel_type: VIDEO
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── requires:
│   ├── backend: VideoBackend
│   ├── vision: VisionProvider | null     # OPTIONAL
│   └── vision_interval_ms: int           # default 2000
├── session_lifecycle:
│   ├── connect_video(room_id, participant_id, channel_id)
│   ├── bind_session(session, room_id, binding)
│   ├── unbind_session(session)
│   └── disconnect_video(session)
├── hooks:
│   ├── ON_VIDEO_SESSION_STARTED — SessionStartedEvent
│   └── ON_VIDEO_SESSION_ENDED — SessionStartedEvent
├── framework_events:
│   ├── video_session_started
│   ├── video_session_ended
│   └── video_vision_result (description, labels, confidence, text, faces)
├── ai_integration:
│   └── setup_video_vision(kit, room_id, ai_channel_id) — injects vision
│       descriptions into AIChannel system prompt
└── backends:
    ├── LocalVideoBackend — OpenCV webcam capture (dev/testing)
    ├── MockVideoBackend — Unit testing with call tracking
    └── (future) WebRTC, SIP video backends
```

### A.13 Telegram Channel

```
TelegramChannel
├── type: TELEGRAM
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT, RICH, MEDIA, LOCATION]
├── capabilities:
│   ├── max_length: 4096
│   ├── supports_rich_text: true (HTML subset)
│   ├── supports_buttons: true (inline keyboards)
│   ├── supports_edit: true
│   ├── supports_delete: true
│   └── supports_typing: true
├── provider: TelegramBotProvider
│   ├── bot_token: string (secret)
│   ├── webhook_url: string | null
│   ├── parse_webhook(request) → InboundMessage
│   ├── verify_signature(request) → bool
│   └── send(chat_id, content, options) → DeliveryResult
└── delivery: sends via Telegram Bot API (sendMessage, sendPhoto, etc.)
```

### A.14 CLI Channel

```
CLIChannel
├── type: CLI
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── media_types: [TEXT]
├── capabilities:
│   ├── max_length: null (unlimited)
│   └── supports_rich_text: false
└── purpose: Development and testing via terminal stdin/stdout
```

---

### A.15 Conference Channel

```
ConferenceChannel
├── channel_type: CONFERENCE
├── category: TRANSPORT
├── direction: BIDIRECTIONAL
├── requires:
│   ├── backend: ConferenceBackend
│   ├── stt: STTProvider | null           # Per-track transcription
│   ├── tts: TTSProvider | null           # AI voice via bot track
│   ├── vision: VisionProvider | null     # OPTIONAL — video/screen tracks
│   ├── interruption: ConferenceInterruptionConfig
│   ├── recording: ConferenceRecordingConfig | null
│   ├── bot_identity: string              # Bot's display identity
│   ├── bot_grants: ConferenceGrants      # Grants for join_as_bot()
│   ├── default_grants: ConferenceGrants  # Grants minted for participants
│   ├── e2ee: bool                        # default false — requires E2EE cap
│   ├── close_room_on_detach: bool        # default false
│   └── speak_text_events: bool           # default false
├── lifecycle:
│   ├── attach → ensure_room() [+ lazy join_as_bot(…, bot_grants)]
│   ├── on_participant_joined → Participant record + hook (bot excluded)
│   ├── on_track_published → subscribe_track() if consumed → pipeline lane
│   ├── on_track_unpublished → lane teardown + unsubscribe_track()
│   └── detach → leave() [+ close_room() if close_room_on_detach]
├── hooks:
│   ├── ON_CONFERENCE_PARTICIPANT_JOINED / LEFT
│   ├── ON_CONFERENCE_TRACK_PUBLISHED / UNPUBLISHED
│   ├── ON_ACTIVE_SPEAKER_CHANGED
│   ├── ON_SCREEN_SHARE_STARTED / STOPPED
│   └── ON_TRANSCRIPTION — per track, participant-attributed
├── framework_events:
│   ├── conference_started / conference_ended
│   └── conference_participant_joined / conference_participant_left
└── backends:
    ├── MockConferenceBackend — unit testing with scripted event sequences
    └── (future) SFU providers (e.g., LiveKit)
```

## Appendix B: Complete Event Flow Examples

### B.1 Customer (SMS) + AI — Basic Conversation

```
1. Customer sends SMS "Bonjour" to +15559876543
   │
   ▼
2. Twilio webhook → parse_webhook() → InboundMessage
   {channel_id: "sms_main", sender_id: "+15551234567",
    content: TextContent{text: "Bonjour"}}
   │
   ▼
3. process_inbound(message)
   │
   ├── Route: no active room for +15551234567 → create new room
   │   └── Fire ON_ROOM_CREATED hook → attach AI channel
   │
   ├── Identity: resolve("+15551234567", SMS) → IDENTIFIED (Jean Tremblay)
   │
   ├── Create RoomEvent {
   │     type: MESSAGE, content: TextContent{text: "Bonjour"},
   │     source: {channel_id: "sms_main", participant_id: "p_jean"},
   │     index: 0, chain_depth: 0
   │   }
   │
   ├── BEFORE_BROADCAST hooks → allow
   │
   ├── Store event (index=0, status=DELIVERED)
   │
   ├── Broadcast to channels:
   │   └── AI channel.on_event()
   │       ├── Build history: [{role: "user", text: "Bonjour"}]
   │       ├── Target: SMS capabilities (max 1600 chars, text only)
   │       ├── Call provider.generate(history, context)
   │       └── Return ChannelOutput{events: [
   │             RoomEvent{content: TextContent{text: "Bonjour Jean! ..."}}
   │           ]}
   │
   ├── Reentry: AI response event
   │   ├── chain_depth = 1 (< max 5)
   │   ├── Store event (index=1)
   │   ├── Broadcast:
   │   │   └── SMS channel.deliver() → Twilio sends SMS to +15551234567
   │   └── No further responses
   │
   └── AFTER_BROADCAST hooks → audit log
```

### B.2 Sensitivity Scanning — Block and Inject

```
1. Customer on SMS sends: "Mon NAS est 123-456-789"
   │
   ▼
2. process_inbound → RoomEvent {
     content: TextContent{text: "Mon NAS est 123-456-789"},
     source: {channel_id: "sms_customer"}, index: 5
   }
   │
   ▼
3. BEFORE_BROADCAST sync hooks:
   │
   ├── [priority=0] sensitivity_scanner:
   │   ├── Detects SIN pattern: 123-456-789
   │   └── Returns HookResult.block(
   │         reason: "SIN detected",
   │         inject: [
   │           InjectedEvent{
   │             target: "sms_customer",
   │             content: TextContent{text: "Message blocked. Do not send SIN by SMS."}
   │           },
   │           InjectedEvent{
   │             target: "ws_advisor",
   │             content: TextContent{text: "Client attempted to send SIN. Blocked."}
   │           }
   │         ],
   │         observations: [
   │           Observation{type: "compliance_violation", data: {pattern: "SIN"}}
   │         ]
   │       )
   │
   ▼
4. Event stored: status=BLOCKED, blocked_by="sensitivity_scanner"
   │
   ▼
5. Injected events delivered:
   ├── SMS to customer: "Message blocked..."
   └── WebSocket to advisor: "Client attempted..."
   │
   ▼
6. Observation persisted: compliance_violation
```

### B.3 Ambiguous Identity — Shared Family Phone

```
1. SMS from +15551234567: "I need to check my account"
   │
   ▼
2. Identity resolution:
   resolver.resolve("+15551234567", SMS) → AMBIGUOUS
   candidates: [
     Identity{name: "Jean Tremblay", id: "id_jean"},
     Identity{name: "Marie Tremblay", id: "id_marie"},
     Identity{name: "Pierre Tremblay", id: "id_pierre"}
   ]
   │
   ▼
3. Fire ON_IDENTITY_AMBIGUOUS hook:
   Hook returns: pending(candidates=[id_jean, id_marie, id_pierre])
   │
   ▼
4. Create Participant {
     identification: PENDING,
     candidates: ["id_jean", "id_marie", "id_pierre"],
     display_name: "+15551234567"  (fallback)
   }
   │
   ▼
5. Event processed normally with pending participant.
   AI responds: "Welcome! Could you please tell me your name?"
   │
   ▼
6. Later: Advisor resolves via REST API:
   POST /rooms/{id}/participants/{pid}/resolve
   {identity_id: "id_marie"}
   │
   ▼
7. Participant updated: identification=IDENTIFIED, identity_id="id_marie"
   │
   ▼
8. PARTICIPANT_IDENTIFIED event added to timeline
```

### B.4 AI ↔ AI Multi-Agent with Chain Depth

This is the `AGENT_CHAIN` policy (§19.3.1), which is the default: an agent's
output solicits the other agents, and only the chain-depth limit ends the
exchange. A room of independent agents — each answering the human, none
meant to answer the others — selects `ADDRESSED_ONLY` instead.

```
1. Human sends message → Room with analyst_ai + writer_ai
   chain_depth = 0
   │
   ▼
2. Broadcast → analyst_ai.on_event()
   Returns: "Based on analysis, key findings are: ..."
   chain_depth = 1
   │
   ▼
3. Reentry → broadcast analyst response
   writer_ai.on_event()
   Returns: "Here is the report based on the analysis: ..."
   chain_depth = 2
   │
   ▼
4. Reentry → broadcast writer response
   analyst_ai.on_event()
   Returns: "Good report. One correction: ..."
   chain_depth = 3
   │
   ... continues until chain_depth reaches max_chain_depth ...
   │
   ▼
N. chain_depth = 5 (== max_chain_depth)
   Response BLOCKED: status=BLOCKED, blocked_by="event_chain_depth_limit"
   Framework event: chain_depth_exceeded
   Side effects from blocked channel: STILL collected
```

### B.5 Dynamic Channel Management — Advisor Joins

```
Timeline of a room with SMS customer + AI:

[0] customer→    "Bonjour"                          (chain_depth=0)
[1] ai→          "Bonjour! How can I help?"          (chain_depth=1)
[2] customer→    "I need help with my mortgage"      (chain_depth=0)
[3] ai→          "I can help with mortgage info..."   (chain_depth=1)

── Advisor joins ──
[4] CHANNEL_ATTACHED  ws_advisor (access=READ_WRITE, visibility=all)

── Integrator mutes AI, changes to assistant mode ──
[5] CHANNEL_MUTED     ai_support
[6] CHANNEL_UPDATED   ai_support (visibility → "ws_advisor" only)
[7] CHANNEL_UNMUTED   ai_support

── Now AI whispers only to advisor ──
[8] customer→    "What rate can I get?"               (chain_depth=0)
[9] ai→          "Suggest offering 4.5% based on..."  (visibility: ws_advisor only)
                  ↑ customer does NOT see this
[10] advisor→    "We can offer you 4.5% fixed."       (visibility: all)
                  ↑ customer sees this

── Advisor lets AI respond directly again ──
[11] CHANNEL_UPDATED  ai_support (visibility → "all")

[12] customer→   "What documents do I need?"          (chain_depth=0)
[13] ai→         "You'll need: 1. ID 2. Income..."    (visibility: all)
                  ↑ customer sees this directly
```

### B.6 Message Edit — Cross-Channel with Fallback

```
1. WhatsApp user edits message [index=3] from "I need 5000$" to "I need 50000$"
   │
   ▼
2. WhatsApp webhook → parse_webhook() → InboundMessage
   {channel_id: "wa_customer", sender_id: "+15551234567",
    content: EditContent{
      target_event_id: "evt_003",
      new_content: TextContent{text: "I need 50000$"},
      edit_source: "sender"
    },
    event_type: EDIT}
   │
   ▼
3. process_inbound(message)
   │
   ├── Validate: evt_003 exists in room → ✓
   ├── Validate: sender is original author → ✓
   │
   ├── Update original event via update_event():
   │   evt_003.content = TextContent{text: "I need 50000$"}
   │   evt_003.metadata.edited = true
   │
   ├── Store EDIT event {
   │     type: EDIT, content: EditContent{...},
   │     source: {channel_id: "wa_customer"},
   │     index: 7
   │   }
   │
   ├── Broadcast to channels:
   │   │
   │   ├── WebSocket (supports_edit: true)
   │   │   └── deliver() native edit → client updates message in-place
   │   │
   │   ├── SMS (supports_edit: false)
   │   │   └── Transcode → TextContent{text: "Correction: I need 50000$"}
   │   │       └── deliver() → SMS sent as new message
   │   │
   │   └── AI channel.on_event()
   │       └── Updates conversation history with corrected text
   │
   └── AFTER_BROADCAST hooks → audit log
```

### B.7 Message Delete — Cross-Channel with Fallback

```
1. WhatsApp user deletes message [index=5]
   │
   ▼
2. WhatsApp webhook → parse_webhook() → InboundMessage
   {channel_id: "wa_customer", sender_id: "+15551234567",
    content: DeleteContent{
      target_event_id: "evt_005",
      delete_type: SENDER,
      reason: null
    },
    event_type: DELETE}
   │
   ▼
3. process_inbound(message)
   │
   ├── Validate: evt_005 exists in room → ✓
   ├── Validate: sender is original author (SENDER type) → ✓
   │
   ├── Mark original event as deleted via update_event():
   │   evt_005.metadata.deleted = true
   │
   ├── Store DELETE event {
   │     type: DELETE, content: DeleteContent{...},
   │     source: {channel_id: "wa_customer"},
   │     index: 8
   │   }
   │
   ├── Broadcast to channels:
   │   │
   │   ├── WebSocket (supports_delete: true)
   │   │   └── deliver() native delete → client removes message
   │   │
   │   ├── SMS (supports_delete: false)
   │   │   └── Transcode → TextContent{text: "[Message deleted]"}
   │   │       └── deliver() → SMS sent as new message
   │   │
   │   └── AI channel.on_event()
   │       └── Updates conversation history (removes or marks deleted)
   │
   └── AFTER_BROADCAST hooks → audit log
```

### B.8 SIP Call → Unified process_inbound with Protocol Traces

```
1. Incoming SIP INVITE from +15551234567
   │
   ├── SIPVoiceBackend auto-accepts, negotiates G.722 (16 kHz)
   ├── Creates VoiceSession {id: "sess-42", room_id: "room-abc",
   │     participant_id: "+15551234567", metadata: {caller, callee, ...}}
   │
   ├── Backend emits ProtocolTrace:
   │     {direction: "inbound", protocol: "sip",
   │      summary: "INVITE from +1555... to +1666...",
   │      raw: <serialized SIP INVITE>, session_id: "sess-42",
   │      room_id: "room-abc"}
   │
   ├── Backend emits ProtocolTrace:
   │     {direction: "outbound", protocol: "sip",
   │      summary: "200 OK (codec=16000Hz)",
   │      raw: <SDP answer>, session_id: "sess-42",
   │      room_id: "room-abc"}
   │
   │   Note: Both traces are BUFFERED — room does not exist yet
   │
   ▼
2. on_call callback fires
   │
   ├── parse_voice_session(session, channel_id="realtime-voice")
   │   → InboundMessage {
   │       channel_id: "realtime-voice",
   │       channel_type: REALTIME_VOICE,
   │       sender_id: "+15551234567",
   │       content: SystemContent{code: "session_started",
   │                 data: {caller: "+1555...", callee: "+1666..."}},
   │       session: <VoiceSession>,
   │       room_id: "room-abc"
   │     }
   │
   ▼
3. kit.process_inbound(message, room_id="room-abc")
   │
   ├── Resolve channel → RealtimeVoiceChannel "realtime-voice"
   ├── Route to room → create room "room-abc"
   ├── Attach channel → triggers _flush_pending_traces("room-abc")
   │   └── BUFFERED TRACES replayed as ON_PROTOCOL_TRACE hooks:
   │       ├── Hook receives: INVITE trace (with room context)
   │       └── Hook receives: 200 OK trace (with room context)
   │
   ├── channel.handle_inbound() → RoomEvent
   │     {type: MESSAGE, source: {channel_id: "realtime-voice",
   │      provider: "SIPRealtimeTransport"}, content: SystemContent{...}}
   │
   ├── BEFORE_BROADCAST hooks:
   │   └── gate_incoming() checks caller against blocklist → ALLOW
   │
   ├── Store event (status=DELIVERED)
   ├── channel.connect_session(session, room_id, binding)
   │   └── Starts realtime AI session (Gemini Live, OpenAI Realtime, etc.)
   │
   ├── Broadcast (no other channels need delivery)
   └── AFTER_BROADCAST hooks → log with provider="SIPRealtimeTransport"
   │
   ▼
4. Audio flows bidirectionally
   │
   ├── Caller speaks → Transport → Provider → AI responds → Transport → Caller
   ├── ON_TRANSCRIPTION hooks fire for user and AI speech
   └── Events emitted with source.provider = "SIPRealtimeTransport"
   │
   ▼
5. Remote hangup (SIP BYE)
   │
   ├── Backend emits ProtocolTrace:
   │     {direction: "inbound", protocol: "sip",
   │      summary: "BYE from +1555...",
   │      raw: <serialized SIP BYE>, session_id: "sess-42"}
   │
   ├── ON_PROTOCOL_TRACE hook fires immediately (room exists)
   │
   ├── on_call_disconnected callback:
   │   ├── realtime.end_session(session)
   │   └── kit.close_room("room-abc")
   │
   └── Room closed, resources released
```

### B.9 Multi-Agent Pipeline — Triage → Specialist → Resolution

```
1. Customer sends SMS "My internet is down since yesterday"
   │
   ▼
2. process_inbound(message)
   │
   ├── Route: create new room
   ├── Attach channels:
   │   ├── "sms_main" (TRANSPORT, customer)
   │   ├── "triage" (INTELLIGENCE, Agent: role="Triage", phase="triage")
   │   ├── "network-specialist" (INTELLIGENCE, Agent: role="Network Engineer", phase="specialist")
   │   └── "closer" (INTELLIGENCE, Agent: role="Resolution", phase="closing")
   │
   ├── ConversationState initialized:
   │     {phase: "triage", active_agent_id: "triage"}
   │
   ├── ConversationRouter installed as BEFORE_BROADCAST hook:
   │     rules: [
   │       {agent: "triage", conditions: {phases: {"triage"}}},
   │       {agent: "network-specialist", conditions: {phases: {"specialist"}}},
   │       {agent: "closer", conditions: {phases: {"closing"}}},
   │     ]
   │
   ├── BEFORE_BROADCAST: router stamps event metadata → target: "triage"
   ├── Broadcast: only "triage" agent processes event
   │
   └── Triage agent responds:
       ├── Generates: "I'll connect you with our network specialist."
       ├── Calls tool: handoff_conversation(target="network-specialist",
       │     reason="network outage", summary="Customer reports internet down since yesterday")
       │
       ├── HandoffHandler processes:
       │   ├── Validates: "triage" → "specialist" transition is allowed
       │   ├── Updates ConversationState:
       │   │     {phase: "specialist", active_agent_id: "network-specialist"}
       │   ├── Fires ON_HANDOFF hook
       │   └── Fires ON_PHASE_TRANSITION hook
       │
       └── Response events broadcast to SMS customer
   │
   ▼
3. Customer sends "Yes, the router lights are blinking red"
   │
   ├── BEFORE_BROADCAST: router evaluates
   │   ├── ConversationState.phase = "specialist"
   │   ├── Route → "network-specialist"
   │
   ├── Network specialist agent processes:
   │   ├── Has handoff context: original issue + triage summary
   │   ├── Generates diagnostic steps
   │   ├── Delegates background task:
   │   │     kit.delegate(room_id, "diagnostics-bot",
   │   │       task="Check network status for customer area",
   │   │       notify="network-specialist",
   │   │       strategy=WaitForIdle(buffer=5.0))
   │   │
   │   ├── ON_TASK_DELEGATED hook fires
   │   └── Responds: "Let me check your area's network status..."
   │
   ▼
4. Delegated task completes
   │
   ├── ON_TASK_COMPLETED hook fires
   ├── WaitForIdle strategy waits for conversation pause
   ├── BEFORE_DELIVER hook fires
   ├── Result injected: "Network status: area outage confirmed, ETA 2 hours"
   │
   ▼
5. Specialist resolves and hands off to closer
   │
   ├── Calls: handoff_conversation(target="closer",
   │     reason="resolved", summary="Area outage confirmed, ETA communicated")
   │
   ├── ConversationState:
   │     {phase: "closing", active_agent_id: "closer"}
   │
   └── Closer agent summarizes resolution, asks for satisfaction
```

---

*End of RFC*
