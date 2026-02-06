# RFC: RoomKit — Multi-Channel Conversation Framework

| | |
|---|---|
| **Status** | Draft |
| **Author** | Sylvain Boily |
| **Contributions** | TchatNSign, Angany AI |
| **Created** | 2026-01-27 |
| **Last Updated** | 2026-02-05 |
| **Supersedes** | roomkit-rfc.md (v12 Draft) |

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
19. [Conformance Levels](#19-conformance-levels)
20. [Appendix A: Channel Reference](#appendix-a-channel-reference)
21. [Appendix B: Complete Event Flow Examples](#appendix-b-complete-event-flow-examples)

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
 └────────┘└────────┘          └─────────┘└──────────┘
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

| Value | Meaning |
|---|---|
| ACTIVE | Room is active; channels can send and receive |
| PAUSED | Room is paused (e.g., after inactivity timer); can be resumed |
| CLOSED | Room is closed; no new events accepted |
| ARCHIVED | Room is archived; read-only historical access |

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
| CHANNEL_ATTACHED | Lifecycle | Channel was attached to room |
| CHANNEL_DETACHED | Lifecycle | Channel was detached from room |
| CHANNEL_MUTED | Lifecycle | Channel was muted |
| CHANNEL_UNMUTED | Lifecycle | Channel was unmuted |
| CHANNEL_UPDATED | Lifecycle | Channel binding was modified (access/visibility) |
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
├── provider: string | null                 # Provider name (twilio, anthropic, etc.)
├── raw_payload: map<string, any>           # Original provider payload — never lost
└── provider_message_id: string | null      # Provider's message identifier
```

Implementations MUST preserve `raw_payload` unmodified. This is the audit trail
and the source of truth for provider-specific data.

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
├── muted: bool                             # Temporarily silenced
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
└── metadata: map<string, any>              # Extra data
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
│
└── generate(messages: list<AIMessage>, context: AIContext) → AIResponse
        # Generate a response given conversation history and context

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
3. **Side effects:** Tasks and observations are ALWAYS collected regardless of
   access or mute status.
4. **Visibility filtering:** When broadcasting an event, the framework MUST
   check the source binding's visibility and deliver only to channels included
   in the visibility rule.
5. **Self-skip:** A channel MUST NOT receive its own events via `on_event()`.

---

## 8. Event System

### 8.1 Room Events

Room events are stored in the room's timeline. They have a sequential `index`
that is monotonically increasing within each room.

**Sequential indexing requirements:**

- The `index` MUST start at 0 for the first event in a room.
- Each subsequent event MUST have `index = previous_index + 1`.
- The `index` MUST be assigned atomically under a room-level lock.
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

**HookTrigger** enumeration:

| Trigger | Execution | When It Fires |
|---|---|---|
| BEFORE_BROADCAST | SYNC | Before event reaches channels — can block/modify |
| AFTER_BROADCAST | ASYNC | After all channels have processed the event |
| ON_CHANNEL_ATTACHED | ASYNC | Channel attached to a room |
| ON_CHANNEL_DETACHED | ASYNC | Channel detached from a room |
| ON_CHANNEL_MUTED | ASYNC | Channel muted in a room |
| ON_CHANNEL_UNMUTED | ASYNC | Channel unmuted in a room |
| ON_ROOM_CREATED | ASYNC | New room created |
| ON_ROOM_PAUSED | ASYNC | Room transitioned to PAUSED |
| ON_ROOM_CLOSED | ASYNC | Room transitioned to CLOSED |
| ON_IDENTITY_AMBIGUOUS | SYNC | Multiple identity candidates found |
| ON_IDENTITY_UNKNOWN | SYNC | No identity match found |
| ON_PARTICIPANT_IDENTIFIED | ASYNC | Participant identity resolved |
| ON_TASK_CREATED | ASYNC | A task was created |
| ON_DELIVERY_STATUS | ASYNC | Delivery status webhook from provider |
| ON_ERROR | ASYNC | An error occurred in the pipeline |
| ON_SPEECH_START | ASYNC | VAD detected speech start (voice) |
| ON_SPEECH_END | ASYNC | VAD detected speech end (voice) |
| ON_TRANSCRIPTION | SYNC | After STT transcription (voice) — can modify |
| BEFORE_TTS | SYNC | Before TTS synthesis (voice) — can modify text/voice |
| AFTER_TTS | ASYNC | After TTS synthesis (voice) |
| ON_BARGE_IN | ASYNC | User interrupted TTS playback (voice) |
| ON_TTS_CANCELLED | ASYNC | TTS was cancelled (voice) |
| ON_PARTIAL_TRANSCRIPTION | ASYNC | Streaming partial STT result (voice) |
| ON_VAD_SILENCE | ASYNC | VAD detected silence (voice) |
| ON_VAD_AUDIO_LEVEL | ASYNC | VAD audio level update (voice) |
| ON_REALTIME_TOOL_CALL | SYNC | Speech-to-speech API requests a tool call |
| ON_REALTIME_TEXT_INJECTED | ASYNC | Text injected into realtime session |

### 9.3 Hook Execution Modes

**SYNC hooks:**

- Run sequentially, ordered by priority (lower number = first).
- Each hook receives the event and room context.
- Each hook MUST return a HookResult.
- A BLOCK result stops the pipeline — no further hooks run.
- A MODIFY result replaces the event for subsequent hooks.
- If the hook exceeds its timeout, it MUST be treated as ALLOW with an error logged.

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
├── event: RoomEvent | null                 # The modified event (for "modify" action)
├── reason: string | null                   # Why blocked or modified
├── injected_events: list<InjectedEvent>    # Events to inject when blocking
├── tasks: list<Task>                       # Tasks to create (side effects)
├── observations: list<Observation>         # Observations to record (side effects)
└── metadata: map<string, any>              # Additional hook metadata
```

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

5. IDENTITY RESOLUTION (if resolver configured)
   ├── Call resolver.resolve(message, context) with timeout
   ├── Handle result:
   │   ├── IDENTIFIED → create/update identified participant
   │   ├── AMBIGUOUS → fire ON_IDENTITY_AMBIGUOUS hook
   │   ├── UNKNOWN → fire ON_IDENTITY_UNKNOWN hook
   │   └── CHALLENGE_SENT → deliver challenge, block processing
   └── Stamp participant_id on event

6. ACQUIRE ROOM LOCK

7. IDEMPOTENCY CHECK
   ├── If idempotency_key exists and was seen → return blocked result
   └── Otherwise → continue

8. ASSIGN EVENT INDEX
   └── event.index = room.event_count

9. RUN BEFORE_BROADCAST SYNC HOOKS
   ├── Execute hooks in priority order
   └── Collect result: allow / block / modify

10. IF BLOCKED:
    ├── Store event with status=BLOCKED, blocked_by=hook_name
    ├── Deliver injected events from hook result
    ├── Persist tasks and observations from hook result
    └── Return InboundResult(blocked=true)

11. IF ALLOWED (possibly modified):
    ├── Store event with status=DELIVERED
    ├── Deliver any injected events
    ├── Get source binding
    └── Call broadcast(event, source_binding, context)

12. REENTRY DRAIN LOOP
    ├── Collect response events from broadcast
    ├── For each response event:
    │   ├── Assign index, store
    │   ├── Check chain_depth < max_chain_depth
    │   │   └── If exceeded → block, emit framework event
    │   ├── Broadcast response event
    │   └── Collect further responses → queue for next iteration
    └── Repeat until no more responses

13. PERSIST SIDE EFFECTS
    └── Store all tasks and observations from hooks + channels

14. RUN AFTER_BROADCAST ASYNC HOOKS
    └── Fire and forget

15. UPDATE ROOM STATE
    ├── room.latest_index = event.index
    ├── room.event_count += 1
    └── room.timers.last_activity_at = now

16. RELEASE ROOM LOCK

17. EMIT FRAMEWORK EVENTS
    └── event_processed, delivery_succeeded/failed, etc.

18. RETURN InboundResult
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

**State updates:**

1. On successful EDIT: the framework SHOULD call `update_event()` to replace the
   original event's content with `EditContent.new_content` and set
   `metadata.edited = true`. The EDIT event itself MUST be stored in the timeline.
2. On successful DELETE: the framework SHOULD call `update_event()` to set
   `metadata.deleted = true` on the original event. The DELETE event itself MUST
   be stored in the timeline.

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
3. If not found → return null (framework creates a new room).

Implementations MUST allow integrators to provide a custom routing strategy.

### 10.5 Direct Event Injection

Integrators MAY inject events into a room without going through the inbound
pipeline (e.g., from a REST API or MCP tool call):

```
send_event(room_id, channel_id, content, event_type, ...) → RoomEvent
```

This creates an event with the specified source channel, stores it, and
broadcasts it through the normal broadcast pipeline (including hooks).

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

---

## 12. Voice and Realtime Media

### 12.1 Architecture Overview

RoomKit supports two voice architectures:

```
Architecture 1: STT/TTS Pipeline (VoiceChannel)
┌──────────┐     ┌─────┐     ┌──────────┐     ┌─────┐     ┌──────────┐
│ Client   │────→│ VAD │────→│   STT    │────→│Room │────→│   TTS    │────→ Client
│ (audio)  │     │     │     │Provider  │     │Kit  │     │Provider  │
└──────────┘     └─────┘     └──────────┘     └─────┘     └──────────┘

Architecture 2: Speech-to-Speech (RealtimeVoiceChannel)
┌──────────┐     ┌──────────────────────────────────┐     ┌──────────┐
│ Client   │────→│ Speech-to-Speech API             │────→│ Client   │
│ (audio)  │     │ (OpenAI Realtime, Gemini Live)   │     │ (audio)  │
└──────────┘     └────────────────┬─────────────────┘     └──────────┘
                                  │
                            transcriptions
                            tool calls
                                  │
                                  ▼
                             ┌─────────┐
                             │ RoomKit │
                             │ (events)│
                             └─────────┘
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
│
│   # VAD callback registration:
├── on_speech_start(callback) → void
├── on_speech_end(callback) → void          # Receives captured audio
├── on_partial_transcription(callback) → void
├── on_vad_silence(callback) → void
├── on_vad_audio_level(callback) → void
├── on_barge_in(callback) → void
│
├── capabilities() → VoiceCapability        # What the backend supports
└── close() → void
```

**VoiceCapability** flags:

| Flag | Description |
|---|---|
| INTERRUPTION | Can cancel TTS playback |
| PARTIAL_STT | Provides streaming transcription |
| VAD_SILENCE | Silence duration detection |
| VAD_AUDIO_LEVEL | Audio level events |
| BARGE_IN | Detect user interrupting TTS |

**VoiceSession:**

```
VoiceSession
├── id: string                              # Session identifier
├── room_id: string                         # Associated room
├── participant_id: string                  # Associated participant
├── channel_id: string                      # Associated voice channel
├── state: VoiceSessionState                # CONNECTING, ACTIVE, PAUSED, ENDED
├── created_at: datetime                    # Session start time
└── metadata: map<string, any>              # Session-specific data
```

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
├── synthesize(text, voice: string | null) → audio_bytes
└── synthesize_stream(text, voice: string | null) → async_iterator<AudioChunk>
```

**Audio processing flow:**

```
1. Client sends audio stream → VoiceBackend
2. VAD detects speech end → on_speech_end(audio_bytes)
3. STT transcribes audio → TranscriptionResult
4. Fire ON_TRANSCRIPTION hook (can modify transcript)
5. Create RoomEvent with TextContent or AudioContent
6. Route through normal inbound pipeline
7. Room broadcasts → AI or other channels respond
8. Response event arrives at Voice channel via deliver()
9. If TextContent → Fire BEFORE_TTS hook → TTS synthesizes → stream audio back
10. If AudioContent → stream audio directly back
```

### 12.3 Realtime Voice Channel (Speech-to-Speech)

The Realtime Voice Channel wraps speech-to-speech APIs (e.g., OpenAI Realtime,
Gemini Live) that handle audio processing natively, bypassing STT/TTS.

**RealtimeVoiceProvider interface:**

```
RealtimeVoiceProvider (interface)
├── connect(session, system_prompt, voice, tools, temperature) → void
├── disconnect(session) → void
├── send_audio(session, audio_chunk) → void
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

**RealtimeAudioTransport interface:**

```
RealtimeAudioTransport (interface)
├── accept(session, connection) → void
├── send_audio(session, audio_chunk) → void
├── receive_audio(session) → async_iterator<AudioChunk>
├── on_audio_received(callback) → void
└── on_client_disconnected(callback) → void
```

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

### 12.4 Voice Hooks

Voice-specific hooks allow integrators to customize the voice pipeline:

| Hook | Type | Use Case |
|---|---|---|
| ON_SPEECH_START | ASYNC | Show "listening" indicator |
| ON_SPEECH_END | ASYNC | Log speech duration |
| ON_TRANSCRIPTION | SYNC | Fix STT errors, redact content |
| BEFORE_TTS | SYNC | Select voice, modify text |
| AFTER_TTS | ASYNC | Log synthesis metrics, cache |
| ON_BARGE_IN | ASYNC | Track interruptions |
| ON_TTS_CANCELLED | ASYNC | Log cancellation reason |
| ON_PARTIAL_TRANSCRIPTION | ASYNC | Show real-time captions |
| ON_VAD_SILENCE | ASYNC | Trigger silence timeout |
| ON_VAD_AUDIO_LEVEL | ASYNC | Audio level visualization |
| ON_REALTIME_TOOL_CALL | SYNC | Execute tool and return result |
| ON_REALTIME_TEXT_INJECTED | ASYNC | Log text injections |

### 12.5 Barge-In

Barge-in occurs when a user speaks while TTS is playing. When detected:

1. The VoiceBackend fires `on_barge_in` callback.
2. Current TTS playback is cancelled (if backend supports INTERRUPTION).
3. The Voice Channel fires ON_BARGE_IN hook.
4. The user's new speech is processed normally.

Implementations SHOULD support a configurable `barge_in_threshold_ms` — minimum
TTS playback duration before barge-in detection activates.

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

```
RoomLockManager (interface)
├── acquire(room_id) → lock
└── release(lock) → void
```

For single-process deployments, an in-memory lock manager (per-room async mutex)
is sufficient. Distributed deployments require a distributed lock (e.g., Redis,
PostgreSQL advisory locks).

### 13.6 Processing Timeout

Implementations SHOULD support a configurable `process_timeout` — maximum time
for the entire inbound processing pipeline. If exceeded, the event SHOULD be
stored as FAILED.

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

- Event index assignment MUST be atomic within a room.
- Room state updates MUST be consistent with event storage.
- Idempotency key checks MUST be performed under the room lock.

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
├── roomkit.providers.sms.*
├── roomkit.providers.email.*
├── roomkit.providers.ai.*
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

### 15.4 Framework Events for Monitoring

See Section 8.2 for the complete list of framework events. These MUST be
emittable and subscribable by integrators for monitoring dashboards, alerting,
and integration purposes.

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

---

## 19. Conformance Levels

### 19.1 Level 0: Core (REQUIRED)

A conforming implementation MUST support:

- Room model with lifecycle (ACTIVE, PAUSED, CLOSED, ARCHIVED)
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
- Reentry drain loop
- Inbound room routing (pluggable)
- Room-level locking
- ConversationStore interface with in-memory implementation
- Content transcoding (at least text fallback)
- Framework events (Section 8.2)
- Structured logging
- Idempotency checking

### 19.2 Level 1: Transport (RECOMMENDED)

A Level 1 implementation SHOULD additionally support:

- At least one SMS provider
- At least one Email provider
- WebSocket channel
- HTTP/Webhook channel
- AI channel with at least one AI provider
- Provider abstraction (swappable per channel type)
- Identity resolution pipeline
- Identity hooks (ON_IDENTITY_AMBIGUOUS, ON_IDENTITY_UNKNOWN)
- Participant model with identification status
- Circuit breaker
- Retry policy
- Rate limiting
- REST API (Section 16.1)

### 19.3 Level 2: Rich (OPTIONAL)

A Level 2 implementation MAY additionally support:

- WhatsApp channel (Business and/or Personal)
- Messenger channel
- Teams channel
- RCS channel with SMS fallback
- Template content support
- Source providers (persistent connections)
- MCP Server (Section 16.2)
- Realtime/ephemeral events backend
- Per-room hooks

### 19.4 Level 3: Voice (OPTIONAL)

A Level 3 implementation MAY additionally support:

- Voice channel (STT/TTS pipeline)
- VoiceBackend interface with at least one implementation
- STTProvider interface with at least one implementation
- TTSProvider interface with at least one implementation
- Voice hooks (ON_SPEECH_START through ON_VAD_AUDIO_LEVEL)
- Barge-in detection
- Realtime Voice channel (speech-to-speech)
- RealtimeVoiceProvider interface
- RealtimeAudioTransport interface
- Realtime voice hooks (ON_REALTIME_TOOL_CALL)

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
│   └── max_context_events: int | null
├── per_room_overrides (via binding metadata):
│   ├── system_prompt
│   ├── temperature
│   ├── max_tokens
│   └── tools
└── behavior:
    ├── on_event() builds conversation history + target capabilities
    ├── Calls provider.generate(messages, context)
    ├── Skips events from self (loop prevention)
    └── Returns ChannelOutput with response events + tasks + observations
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
│   └── backend: VoiceBackend
├── configuration:
│   ├── streaming: bool (default true)
│   ├── enable_barge_in: bool (default false)
│   └── barge_in_threshold_ms: int (default 500)
├── session_management:
│   ├── bind_session(session, room_id, binding)
│   └── unbind_session(session)
└── delivery:
    ├── AudioContent → stream directly
    ├── TextContent → synthesize via TTS, then stream
    └── Other → error
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
│   └── transport: RealtimeAudioTransport
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

---

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

---

*End of RFC*
