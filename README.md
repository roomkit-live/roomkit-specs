# RoomKit Specs

Protocol specifications and RFCs for [RoomKit](https://github.com/roomkit-live/roomkit).

## Documents

| Document | Description |
|---|---|
| [roomkit-rfc.md](roomkit-rfc.md) | RoomKit protocol specification — room model, event lifecycle, hook pipeline, channel bindings, identity resolution, realtime media (voice, video, SFU conferencing, recording), and the contracts for AI participation (orchestration, memory, tool access control, skills) |
| [conformance/](conformance/README.md) | The shared conformance suite: scenarios every implementation runs, as the executable form of the RFC's rules, with their schema and checker |

## Purpose

This repo contains language-agnostic specifications that define the RoomKit protocol. Implementations in any language should conform to these specs.

## Related Repos

- [roomkit](https://github.com/roomkit-live/roomkit) — Python library (reference implementation)
- [roomkit-docs](https://github.com/roomkit-live/roomkit-docs) — Documentation
- [roomkit-website](https://github.com/roomkit-live/roomkit-website) — Landing page
