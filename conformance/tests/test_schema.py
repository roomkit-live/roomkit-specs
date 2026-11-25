from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_nonstreaming_models_reject_stream_only_rounds(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/tasks/the-repeat-guard-holds-on-delegate-task-without-streaming.json"
        )
        scenario = json.loads(fixture.read_text())
        self.assertTrue(validator.is_valid(scenario))
        for field in (
            "deltas",
            "thinking",
            "stream",
            "done",
            "failure_after_calls",
            "failure_after_done",
        ):
            with self.subTest(field=field):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["model"]["rounds"][0][field] = (
                    False
                    if field in ("done", "failure_after_calls", "failure_after_done")
                    else []
                )
                self.assertFalse(validator.is_valid(scenario))
        for field, value in (
            ("fails", "broken"),
            ("refuses", {"status": 500, "message": "broken"}),
        ):
            with self.subTest(field=field):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["model"]["rounds"][0] = {
                    "whole_response": {},
                    field: value,
                }
                self.assertFalse(validator.is_valid(scenario))
        for flag in (None, 0, "false", []):
            with self.subTest(flag=flag):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["model"]["streaming"] = flag
                self.assertFalse(validator.is_valid(scenario))

    def test_metadata_patch_requires_a_text_room_id(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/tasks"
            / (
                "a-background-worker-keeps-its-turns-task-boundary-after-a-store-patch.json"
            )
        )
        for room_id in (7, None, [], {}, "call", "$r1"):
            with self.subTest(room_id=room_id):
                scenario = json.loads(fixture.read_text())
                patch = next(
                    step
                    for step in scenario["steps"]
                    if step.get("call") == "store.patch_room_metadata"
                )
                patch["room_id"] = room_id
                self.assertEqual(validator.is_valid(scenario), isinstance(room_id, str))

    def test_identity_store_calls_require_their_arguments(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/store"
            / "an-address-belongs-to-one-identity-of-an-organization-per-channel-type.json"
        )
        participants = (
            ROOT
            / "scenarios/store"
            / "a-participant-id-the-room-has-is-refused-and-an-update-rewrites-a-record.json"
        )
        for path in (fixture, participants):
            self.assertTrue(validator.is_valid(json.loads(path.read_text())))
        for call, required in (
            ("store.update_participant", ("participant",)),
            ("store.create_identity", ("identity",)),
            ("store.get_identity", ("identity_id",)),
            ("store.resolve_identity", ("channel_type", "address")),
            ("store.link_address", ("identity_id", "channel_type", "address")),
            ("store.unlink_address", ("identity_id", "channel_type", "address")),
        ):
            for argument in required:
                with self.subTest(call=call, argument=argument):
                    source = participants if call == "store.update_participant" else fixture
                    scenario = json.loads(source.read_text())
                    step = next(s for s in scenario["steps"] if s.get("call") == call)
                    del step[argument]
                    self.assertFalse(validator.is_valid(scenario))
        for error, valid in (
            ("address_linked", True),
            ("participant_exists", True),
            ("address_taken", False),
        ):
            with self.subTest(error=error):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0]["expect"] = {"error": error}
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_feature_requirements_are_known_nonempty_unique_names(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        scenario = {
            "id": "media/example",
            "title": "Example",
            "rules": ["§9.2"],
            "steps": [{"idle": True}],
        }
        self.assertTrue(validator.is_valid(scenario))
        for required, valid in (
            (["message_session", "protocol_trace"], True),
            (["scoring"], True),
            (["unknown"], False),
            (["voice", "voice"], False),
            ([], False),
            ("video", False),
        ):
            with self.subTest(required=required):
                candidate = {**scenario, "requires_features": required}
                self.assertEqual(validator.is_valid(candidate), valid)

    def test_requirements_cite_unique_unit_ids(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/orchestration"
            / "a-conversation-state-is-saved-only-in-a-room-the-store-holds.json"
        )
        for requirements, valid in (
            (["RK-10.4-003"], True),
            (["RK-10.4-003", "RK-A.2-001"], True),
            ([], False),
            (["RK-10.4-003", "RK-10.4-003"], False),
            (["§10.4"], False),
            (["RK-10.4-3"], False),
            ("RK-10.4-003", False),
        ):
            with self.subTest(requirements=requirements):
                scenario = json.loads(fixture.read_text())
                scenario["requirements"] = requirements
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_channel_on_its_type_s_addressing_takes_no_scripted_addresses(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/routing/a-number-written-with-plus-or-00-is-international.json"
        for extra, valid in (
            ({}, True),
            ({"addressing": {"country_code": "+33"}}, True),
            ({"recipient_key": "phone_number"}, False),
            ({"addresses": {}}, False),
            ({"model": {"rounds": []}}, False),
            ({"type": "host"}, False),
            ({"addressing": {"country_code": 33}}, False),
            ({"addressing": {"recipient_key": "phone_number"}}, False),
        ):
            with self.subTest(extra=extra):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][0].update(extra)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_addressing_of_normalize_names_a_type_and_an_address(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/rooms/a-country-code-that-is-none-is-refused.json"
        for drop, valid in ((None, True), ("channel_type", False), ("address", False)):
            with self.subTest(drop=drop):
                scenario = json.loads(fixture.read_text())
                step = next(
                    step
                    for step in scenario["steps"]
                    if step.get("call") == "addressing_of.normalize"
                )
                if drop is not None:
                    del step[drop]
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_an_mcp_tool_says_is_error_with_a_boolean(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT / "scenarios/mcp/an-is-error-result-is-a-failure-never-a-refusal-non-streaming.json"
        )
        for is_error, valid in ((True, True), (False, True), (None, True), ("yes", False)):
            with self.subTest(is_error=is_error):
                scenario = json.loads(fixture.read_text())
                tool = scenario["setup"]["channels"][1]["mcp_servers"][0]["tools"][0]
                tool.pop("is_error")
                if is_error is not None:
                    tool["is_error"] = is_error
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_report_claimed_before_its_gate_needs_the_gate(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/tools"
            / "a-call-cut-after-its-report-keeps-its-end-row-cancelled-non-streaming.json"
        )
        for mode, gate, valid in (
            ("claim_then_gate", "claimed", True),
            ("claim_then_gate", None, False),
            ("matching", None, True),
            ("claimed_first", "claimed", False),
        ):
            with self.subTest(mode=mode, gate=gate):
                scenario = json.loads(fixture.read_text())
                tool = scenario["setup"]["channels"][1]["tools"][0]
                tool["report_claim_probe"] = mode
                tool.pop("gate")
                if gate is not None:
                    tool["gate"] = gate
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_caller_and_reader_controls_require_their_labels_and_gates(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/streaming/a-gated-reader-leaves-while-its-pulled-call-runs.json"
        for step in (
            {"cancel": True},
            {"close_while_pending": "turn"},
            {"wait_for": "end", "pending": False},
            {"wait_for": "end", "after": ["tool"]},
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0] = step
                self.assertFalse(validator.is_valid(scenario))
        for missing in ("running", "closed"):
            with self.subTest(missing=missing):
                scenario = json.loads(fixture.read_text())
                reaction = scenario["setup"]["channels"][0]["deliver_stream"][0]
                del reaction["close_while_reading"][missing]
                self.assertFalse(validator.is_valid(scenario))

    def test_an_under_lock_step_names_its_room_and_waits_for_each_call(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/reentrancy"
            / "each-call-under-a-lock-the-host-holds-draws-on-a-budget-of-its-own.json"
        )
        call = {"call": "get_room", "room_id": "room-1"}
        for step, valid in (
            ({"under_lock": "room-1", "do": [call]}, True),
            ({"under_lock": "room-1", "do": []}, False),
            ({"under_lock": "room-1"}, False),
            ({"do": [call]}, False),
            ({"under_lock": "room-1", "do": [{**call, "background": True, "as": "x"}]}, False),
            ({"under_lock": "room-1", "do": [call], "waiters": 1}, False),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0] = step
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_store_fault_names_store_operations_and_fails_or_holds(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/inbound"
            / "a-set-s-record-the-store-fails-to-write-changes-nothing-the-call-reports.json"
        )
        for step, valid in (
            ({"store_fault": "commit_event", "fail": "down"}, True),
            ({"store_fault": "commit_event", "gate": "g"}, True),
            ({"store_fault": "commit_event", "gate": "g", "fail": "down"}, True),
            ({"store_fault": ["room_exists", "load_room_context"], "gate": "g"}, True),
            ({"store_fault": "get_room", "room_id": "$r1", "gate": "g"}, True),
            ({"store_fault": "add_participant", "gate": "g", "in_place": True}, True),
            ({"store_fault": "add_participant", "in_place": True}, False),
            ({"store_fault": "add_participant", "gate": "g", "fail": "x", "in_place": True}, False),
            ({"store_fault": "add_participant", "gate": "g", "in_place": False}, False),
            ({"store_fault": "commit_event"}, False),
            ({"store_fault": "commit_event", "fail": ""}, False),
            ({"store_fault": "find_room_ids_by_channel", "gate": "g"}, False),
            ({"store_fault": ["room_exists"], "gate": "g"}, False),
            ({"store_fault": ["get_room", "get_room"], "gate": "g"}, False),
            ({"store_fault": "commit_event", "fail": "down", "times": 2}, False),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0] = step
                self.assertEqual(validator.is_valid(scenario), valid)
        scenario = json.loads(fixture.read_text())
        scenario["setup"]["kit"]["store_faults"] = False
        self.assertFalse(validator.is_valid(scenario))

    def test_a_hook_is_named_or_labelled_and_left_unnamed(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/hooks"
            / "two-hooks-registered-without-a-name-take-names-unique-among-the-kit-s.json"
        )
        for members, valid in (
            ({"as": "first"}, True),
            ({"name": "first"}, True),
            ({"name": "first", "as": "first"}, False),
            ({}, False),
            ({"as": "First-hook"}, False),
        ):
            with self.subTest(members=members):
                scenario = json.loads(fixture.read_text())
                hook = scenario["setup"]["hooks"][0]
                del hook["as"]
                hook.update(members)
                self.assertEqual(validator.is_valid(scenario), valid)
                room = json.loads(
                    (
                        ROOT
                        / "scenarios/hooks"
                        / "two-room-hooks-registered-without-a-name-take-names-unique-among-the-room-s.json"
                    ).read_text()
                )
                added = room["steps"][0]["hook"]
                del added["as"]
                added.update(members)
                self.assertEqual(validator.is_valid(room), valid)

    def test_a_spawned_task_takes_a_gate_a_delay_actions_and_an_after_gate(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/reentrancy"
            / "a-locked-hook-s-task-calling-while-its-body-runs-commits-ahead-of-the-event.json"
        )
        for extra, valid in (
            ({}, True),
            ({"delay_ms": 0}, True),
            ({"delay_ms": -1}, False),
            ({"fail": "boom"}, False),
            ({"after_turn": []}, False),
            ({"do": [{"call": "no_such_call"}]}, False),
        ):
            with self.subTest(extra=extra):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["hooks"][0]["reactions"][0]["spawn"].update(extra)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_an_on_tool_call_hook_returns_a_bare_missing_payload_alone(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/tools/a-modify-with-no-tool-call-event-keeps-the-previous-hook-s-rewrite.json"
        )
        for invalid, extra, valid in (
            ({"kind": "missing_payload"}, {}, True),
            ({"kind": "no_result"}, {}, False),
            ({"kind": "missing_payload", "tasks": []}, {}, False),
            ({"kind": "missing_payload"}, {"execution": "async"}, False),
            ({"kind": "missing_payload"}, {"trigger": "before_tool_use"}, False),
        ):
            with self.subTest(invalid=invalid, extra=extra):
                scenario = json.loads(fixture.read_text())
                hook = next(h for h in scenario["setup"]["hooks"] if h["name"] == "broken")
                hook["reactions"][0]["invalid_result"] = invalid
                hook.update(extra)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_hook_below_the_kit_names_its_room_and_its_hook(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/hooks/a-hook-registered-below-the-kit-ends-with-the-room-s-creation.json"
        )
        for call in ("hook_engine.add_room_hook", "kit_executor.add_owner_room_hook"):
            for drop, valid in ((None, True), ("room_id", False), ("hook", False)):
                with self.subTest(call=call, drop=drop):
                    scenario = json.loads(fixture.read_text())
                    step = next(s for s in scenario["steps"] if s.get("call") == call)
                    if drop is not None:
                        del step[drop]
                    self.assertEqual(validator.is_valid(scenario), valid)

    def test_predicate_workers_cannot_also_advertise_hosts(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/executors/owners-use-a-predicate-worker-only-on-its-process.json"
        scenario = json.loads(fixture.read_text())
        self.assertTrue(validator.is_valid(scenario))
        worker = scenario["setup"]["executors"][0]
        worker["hosts"] = ["coder"]
        self.assertFalse(validator.is_valid(scenario))
        del worker["host_predicate"]
        self.assertTrue(validator.is_valid(scenario))
        del worker["hosts"]
        self.assertTrue(validator.is_valid(scenario))

    def test_an_executor_s_hook_is_named(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/executors/a-channel-call-runs-on-the-executor-holding-the-room.json"
        for member in ("hooks", "room_hooks"):
            for label, valid in (("name", True), ("as", False)):
                with self.subTest(member=member, label=label):
                    scenario = json.loads(fixture.read_text())
                    hook = {label: "audit", "trigger": "on_tool_call"}
                    scenario["setup"]["executors"][0][member] = [hook]
                    self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_scripted_video_detection_names_its_frame(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = ROOT / "scenarios/video/a-frame-filter-reports-its-detection.json"
        scenario = json.loads(fixture.read_text())
        self.assertTrue(validator.is_valid(scenario))
        del scenario["steps"][0]["detections"][0]["frame_sequence"]
        self.assertFalse(validator.is_valid(scenario))

    def test_a_scripted_recognizer_replaces_the_transcripts_and_scripts_its_streams(
        self,
    ) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = (
            ROOT
            / "scenarios/voice/a-kept-stream-carries-turn-after-turn-until-the-provider-ends-it.json"
        )
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        changes = (
            lambda step: step.update(transcripts=["hello"]),
            lambda step: step["stt"]["streams"][0].update(then="close"),
            lambda step: step["stt"]["streams"][0]["results"][0].pop("text"),
            lambda step: step["stt"]["streams"][0]["results"][0].update(
                segments=[{"text": "who"}]
            ),
            lambda step: step["stt"].update(supports_streaming=True),
            lambda step: step.update(turns=[True], turn_decisions=[{"is_complete": True}]),
            lambda step: step.update(turn_decisions=[{"suggested_wait_ms": 10}]),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                scenario = json.loads(fixture.read_text())
                change(scenario["steps"][0])
                self.assertFalse(validator.is_valid(scenario))

    def test_a_diarization_result_attributes_the_audio_to_nobody_as_null(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = ROOT / "scenarios/voice/a-stage-result-naming-nobody-changes-no-speaker.json"
        scenario = json.loads(fixture.read_text())
        self.assertIn(None, [s["speaker_id"] for s in scenario["steps"][0]["speakers"]])
        self.assertTrue(validator.is_valid(scenario))
        scenario["steps"][0]["speakers"][0]["speaker_id"] = 7
        self.assertFalse(validator.is_valid(scenario))

    def test_the_kit_s_close_grace_is_a_positive_whole_number_of_ms(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/delivery"
            / "a-turn-still-open-once-the-close-s-grace-is-over-is-given-up.json"
        )
        for grace, valid in ((200, True), (1, True), (0, False), (1.5, False), ("200", False)):
            with self.subTest(grace=grace):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["kit"]["close_grace_ms"] = grace
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_the_kit_s_close_is_cut_at_a_gate_and_its_store_has_an_owner(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/kit-close"
            / "a-close-after-its-shutdown-was-cut-says-the-shutdown-did-not-finish.json"
        )
        for step, valid in (
            ({"close_cut_at": "closing"}, True),
            ({"close_cut_at": ""}, False),
            ({"close_cut_at": "closing", "as": "x"}, False),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0] = step
                self.assertEqual(validator.is_valid(scenario), valid)
        for owner, valid in (("kit", True), ("integrator", True), ("nobody", False), (True, False)):
            with self.subTest(owner=owner):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["kit"] = {"store_owner": owner}
                self.assertEqual(validator.is_valid(scenario), valid)
        for closes, valid in (
            (["held"], True),
            ({"$unordered": ["held"]}, True),
            ({"$unordered": "held"}, False),
            ("held", False),
        ):
            with self.subTest(closes=closes):
                scenario = json.loads(fixture.read_text())
                scenario["expect"]["channel_closes"] = closes
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_scripted_source_needs_its_feature_and_a_channel(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/kit-close"
            / "every-source-s-task-is-cut-whatever-its-stop-does.json"
        )
        scenario = json.loads(fixture.read_text())
        self.assertTrue(validator.is_valid(scenario))
        for change, valid in (
            (lambda s: s.pop("requires_features"), False),
            (lambda s: s.update(requires_features=["conference"]), False),
            (lambda s: s["setup"]["sources"][0].pop("channel_id"), False),
            (lambda s: s["setup"]["sources"][0].update(restart_delay_ms=0), False),
            (lambda s: s["setup"]["sources"][0].update(health=[]), False),
        ):
            with self.subTest(change=change):
                candidate = json.loads(fixture.read_text())
                change(candidate)
                self.assertEqual(validator.is_valid(candidate), valid)

    def test_a_turn_s_cleanup_and_an_action_on_its_own_task_make_actions(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/kit-close"
            / "a-turn-s-cleanup-closing-the-kit-the-close-cut-joins-that-close.json"
        )
        close = {"call": "close", "as": "cleanup"}
        for reaction, valid in (
            ({"gate": "turn", "on_cut": [close]}, True),
            ({"gate": "turn", "on_cut": [{**close, "own_task": True}]}, True),
            ({"gate": "turn", "on_cut": []}, False),
            ({"gate": "turn", "on_cut": [{**close, "own_task": False}]}, False),
        ):
            with self.subTest(reaction=reaction):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["on_event"][0] = reaction
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_turn_s_end_is_held_at_a_named_gate(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/delivery"
            / "a-cancel-past-its-bound-reports-the-cleanup-incomplete-and-lets-it-run.json"
        )
        for gate, valid in (("end-owed", True), (1, False), (True, False), ({}, False)):
            with self.subTest(gate=gate):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][2]["holds_end"] = gate
                self.assertEqual(validator.is_valid(scenario), valid)
        for ends, valid in (({"agent": []}, True), ({"agent": "cut"}, False), ([], False)):
            with self.subTest(ends=ends):
                scenario = json.loads(fixture.read_text())
                scenario["expect"]["turn_ends"] = ends
                self.assertEqual(validator.is_valid(scenario), valid)
        for name, valid in (("cleanup_incomplete", True), ("cleanup_unfinished", False)):
            with self.subTest(name=name):
                scenario = json.loads(fixture.read_text())
                step = next(s for s in scenario["steps"] if s.get("call") == "delivery.cancel")
                step["expect"] = {"error": name}
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_an_owner_is_killed_and_a_turn_holds_its_cpu_apart(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        killed = ROOT / (
            "scenarios/executors/a-turn-whose-owner-was-killed-is-cut-owner-lost-on-its-executor.json"
        )
        for call, valid in (("owner.kill", True), ("owner.stop", False)):
            with self.subTest(call=call):
                scenario = json.loads(killed.read_text())
                step = next(s for s in scenario["steps"] if s.get("call") == "owner.kill")
                step["call"] = call
                self.assertEqual(validator.is_valid(scenario), valid)
        for frames, valid in ((["heartbeat"], True), ([1], False), ("heartbeat", False)):
            with self.subTest(frames=frames):
                scenario = json.loads(killed.read_text())
                scenario["expect"]["killed_owner_frames"] = frames
                self.assertEqual(validator.is_valid(scenario), valid)
        busy = ROOT / (
            "scenarios/executors"
            "/a-turn-busy-with-its-cpu-on-an-executor-in-a-process-of-its-own-still-beats.json"
        )
        for held, valid in ((1500, True), (0, False), ("1500", False)):
            with self.subTest(held=held):
                scenario = json.loads(busy.read_text())
                scenario["setup"]["channels"][1]["on_event"][0]["holds_cpu_ms"] = held
                self.assertEqual(validator.is_valid(scenario), valid)
        for apart, valid in ((True, True), ("yes", False)):
            with self.subTest(apart=apart):
                scenario = json.loads(busy.read_text())
                scenario["setup"]["executors"][0]["own_process"] = apart
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_an_acp_agent_acts_after_its_reply(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = ROOT / (
            "scenarios/executors/a-hook-on-an-executor-fired-by-an-acp-agent-between-prompts"
            "-reads-the-last-turn-s-context-and-changes-nothing.json"
        )
        for after, valid in (
            ({"gate": "later", "updates": []}, True),
            ({"gate": "later", "prompt": "again"}, False),
            ({"permission_steps": {}}, False),
        ):
            with self.subTest(after=after):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["acp"]["agent"]["prompts"][0]["after_reply"] = after
                self.assertEqual(validator.is_valid(scenario), valid)
        for call, valid in (("current_turn_host", True), ("current_turn_hosts", False)):
            with self.subTest(call=call):
                scenario = json.loads(fixture.read_text())
                hook = scenario["setup"]["executors"][0]["hooks"][0]
                hook["reactions"][1]["do"][0]["call"] = call
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_round_ends_on_a_stop_reason_of_the_contract_and_never_a_vendor_s(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = ROOT / "scenarios/tools/a-malformed-call-is-told-and-tried-again-on-the-first-round.json"
        for finish_reason, valid in (
            ("stop", True),
            ("tool_calls", True),
            ("length", True),
            ("content_filter", True),
            ("refusal", True),
            ("malformed_call", True),
            ("unexpected_call", True),
            ("error", True),
            (None, True),
            ("end_turn", False),
            ("MAX_TOKENS", False),
            ("MALFORMED_FUNCTION_CALL", False),
            ("Stop", False),
        ):
            with self.subTest(finish_reason=finish_reason):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["model"]["rounds"][0]["finish_reason"] = finish_reason
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_chat_dialect_states_the_core_s_options_and_names_no_vendor(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = ROOT / "scenarios/reasoning/a-named-thinking-field-carries-a-round-s-reasoning.json"
        for dialect, valid in (
            ({}, True),
            ({"thinking_field": "reasoning_content"}, True),
            (
                {
                    "thinking_field": "reasoning",
                    "names_tool_results": True,
                    "flattens_text": True,
                    "round_thinking_required": True,
                    "round_thinking_placeholder": " ",
                },
                True,
            ),
            ("default", False),
            ({"thinking_field": ""}, False),
            ({"thinking_field": None}, False),
            ({"names_tool_results": "yes"}, False),
            ({"round_thinking_placeholder": 1}, False),
            ({"dialect": "default"}, False),
            ({"round_thinking_required": True}, False),
            ({"thinking_field": "reasoning", "round_thinking_required": False}, True),
            ({"thinking_field": "reasoning", "round_thinking_placeholder": " "}, False),
            (
                {
                    "thinking_field": "reasoning",
                    "round_thinking_required": False,
                    "round_thinking_placeholder": " ",
                },
                False,
            ),
            ({"thinking_field": "reasoning", "round_thinking_placeholder": ""}, True),
        ):
            with self.subTest(dialect=dialect):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][1]["model"]["chat_dialect"] = dialect
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_voice_session_scripts_its_interruption_synthesis_and_outbound_calls(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "scenario.schema.json").read_text()))
        fixture = ROOT / "scenarios/voice/a-reply-walks-the-outbound-stages-in-their-order.json"
        for member, value, valid in (
            ("interruption", {"strategy": "confirmed", "min_speech_ms": 1}, True),
            ("interruption", {"strategy": "polite"}, False),
            ("interruption", {"echo_guard_ms": -1}, False),
            ("interruption", {"backchannel_detector": "phrases"}, False),
            ("max_sentences", 2, True),
            ("max_sentences", 0, False),
            ("backchannel_decisions", [{"is_backchannel": False, "pending": True}], True),
            ("backchannel_decisions", [{"pending": True}], False),
            ("backchannel_decisions", [{"transcript": "Ou", "is_backchannel": False, "pending": True}], True),
            ("stt", {"streams": [{"results": [{"text": "Ou", "final": False, "gate": "words"}]}]}, True),
            ("stt", {"streams": [{"results": [{"text": "Ou", "gate": 1}]}]}, False),
            ("tts", {"context_level": "audio", "word_ms": 1, "gates": [None, "g"]}, True),
            ("tts", {"context_level": "prosody"}, False),
            ("tts", {"voices": [{"id": "v", "language": None}], "max_dialogue_speakers": 2}, True),
            ("tts", {"voices": [{"name": "nameless"}]}, False),
            ("tts", {"vendor": "any"}, False),
            ("tts_context", {"include_audio": True, "max_audio_seconds": 0.5}, True),
            ("tts_context", {"max_turns": 0}, False),
            ("playback_gates", [None, "playing"], True),
            ("playback_gates", [], False),
            ("playback_fails", ["alice"], True),
            ("playback_fails", "alice", False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        scenario = json.loads(fixture.read_text())
        scenario["steps"][0]["playback_gate"] = "playing"
        scenario["steps"][0]["playback_gates"] = ["playing"]
        self.assertFalse(validator.is_valid(scenario))
        for step, valid in (
            ({"call": "voice.send_dtmf", "channel_id": "phone", "participant_id": "alice", "digit": "#"}, True),
            ({"call": "voice.send_dtmf", "channel_id": "phone", "participant_id": "alice", "digit": "1", "duration_ms": 80}, True),
            ({"call": "voice.send_dtmf", "channel_id": "phone", "participant_id": "alice"}, False),
            ({"call": "voice.play", "channel_id": "phone", "participant_id": "alice", "audio": "UklGRg=="}, True),
            ({"call": "voice.play", "channel_id": "phone", "participant_id": "alice"}, False),
            ({"call": "voice.list_voices", "channel_id": "phone", "language": "fr", "query": "warm"}, True),
            ({"call": "voice.list_voices", "language": "fr"}, False),
            (
                {
                    "call": "voice.synthesize_dialogue",
                    "channel_id": "phone",
                    "turns": [{"speaker": "a", "text": "Hi."}],
                    "voices": {"a": "v"},
                },
                True,
            ),
            (
                {
                    "call": "voice.synthesize_dialogue",
                    "channel_id": "phone",
                    "turns": [{"speaker": "a"}],
                    "voices": {"a": "v"},
                },
                False,
            ),
            (
                {
                    "call": "voice.send_dtmf",
                    "channel_id": "phone",
                    "participant_id": "alice",
                    "digit": "1",
                    "expect": {"error": {"name": "session_ended"}},
                },
                True,
            ),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)
        scenario = json.loads(fixture.read_text())
        scenario["expect"] = {"voice_events": {"r1": [{"event": "tts_error"}]}}
        self.assertTrue(validator.is_valid(scenario))

    def test_a_voice_pipeline_states_its_stages_transport_and_sessions(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/voice/a-reply-walks-the-outbound-stages-in-their-order.json"
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        for member, value, valid in (
            ("capabilities", ["native_aec", "dtmf_signaling"], True),
            ("capabilities", ["echo_cancelling"], False),
            ("session_ids", {"alice": ""}, False),
            ("aec", {"output": 5}, False),
            ("agc", {"gain": 2}, False),
            ("postprocessors", [{"output": "AQI="}], False),
            ("recorder", {"mode": "inbound_only"}, True),
            ("recorder", {"mode": "stereo"}, False),
            ("recorder", {"trigger": "always"}, False),
            ("vad_config", {"silence_threshold_ms": 300}, True),
            ("vad_config", {"threshold": 0.5}, False),
            ("contract", {"internal_format": {"sample_rate": 8000}}, True),
            ("contract", {"internal_format": {"codec": "opus"}}, False),
            ("reference_continues", True, False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        for step, valid in (
            ({"call": "voice.join", "channel_id": "phone", "participant_id": "alice"}, True),
            ({"call": "voice.join", "channel_id": "phone", "session_id": "s"}, False),
            ({"call": "voice.leave", "channel_id": "phone", "participant_id": "alice"}, True),
            (
                {
                    "call": "voice.dtmf_received",
                    "channel_id": "phone",
                    "participant_id": "alice",
                    "digit": "#",
                    "duration_ms": 120,
                },
                True,
            ),
            (
                {
                    "call": "voice.dtmf_received",
                    "channel_id": "phone",
                    "participant_id": "alice",
                    "duration_ms": 120,
                },
                False,
            ),
            (
                {
                    "call": "voice.feed",
                    "channel_id": "phone",
                    "participant_id": "alice",
                    "frames": ["AQI="],
                    "sample_rate": 8000,
                    "channels": 2,
                    "timestamp_ms": 40,
                },
                True,
            ),
            (
                {
                    "call": "voice.feed",
                    "channel_id": "phone",
                    "participant_id": "alice",
                    "frames": ["AQI="],
                    "sample_rate": "8k",
                },
                False,
            ),
            ({"call": "voice.read", "channel_id": "phone", "stages": "aec"}, False),
            ({"call": "voice.read", "channel_id": "phone", "calls": ["process"]}, True),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_realtime_channel_states_its_tools_policy_and_backend(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/realtime/a-backend-reads-each-call-s-outcome.json"
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        agent = {"id": "a", "type": "ai", "model": {"rounds": [{"text": "x"}]}}
        for member, value, valid in (
            ("tool_policy", {"deny": ["secret"]}, True),
            ("tool_policy", {"block": ["secret"]}, False),
            ("tool_result_max_length", 100, True),
            ("tool_result_max_length", 0, False),
            ("tool_handler", False, True),
            ("tool_handler", True, False),
            ("reasoning", {"agent": agent}, True),
            ("reasoning", {"agent_of": "helper"}, False),
            ("reasoning", {"runs": [[{"call": "lookup", "via": "execute"}]]}, False),
            ("reasoning", {"runs": [[{"say": "x", "loud": True}]]}, False),
            ("reasoning", {"runs": [[{"delegate": {"agent_id": "w"}}]]}, False),
            ("reasoning", {"agent": agent, "runs": [[]]}, False),
            ("reasoning_timeout_ms", 0, False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][0]["realtime"][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        for tool, valid in (
            ({"fails": "down"}, True),
            ({"action": "end_session", "in_task": "awaited", "after_gate": "g", "result": "x"}, True),
            ({"action": "detach", "result": "x"}, False),
            ({"in_task": "unawaited", "result": "x"}, False),
            ({"gate": "g"}, False),
            ({"parameters": {"type": "object"}, "result": "x"}, True),
            ({"action": "end_session", "delay_ms": 300, "result": "x"}, True),
            ({"delay_ms": 0, "result": "x"}, False),
        ):
            with self.subTest(tool=tool):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][0]["realtime"]["tools"]["broken"] = tool
                self.assertEqual(validator.is_valid(scenario), valid)
        call = {"call": "realtime.tool_call", "channel_id": "rt", "call_id": "c", "name": "n"}
        for step, valid in (
            ({**call, "arguments_text": "[1]"}, True),
            ({**call, "arguments_text": "[1]", "arguments": {}}, False),
            ({**call, "arguments_text": {}}, False),
            ({"call": "realtime.configure", "channel_id": "rt", "tools": ["lookup"]}, True),
            ({"call": "realtime.configure", "channel_id": "rt"}, False),
            (
                {
                    "call": "realtime.start",
                    "channel_id": "rt",
                    "room_id": "r1",
                    "participant_id": "p",
                    "tools": ["lookup"],
                },
                True,
            ),
            ({"call": "telemetry.spans", "site": "owner", "kind": "realtime.session"}, True),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_realtime_session_states_its_traits_audio_and_answers(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/realtime/a-full-duplex-session-fires-no-barge-in.json"
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        for member, value, valid in (
            ("full_duplex", True, True),
            ("full_duplex", "yes", False),
            ("supports_tools", False, True),
            ("supports_mid_session_reconfigure", False, True),
            ("inject_result", None, True),
            ("inject_result", {"status": "not_sent", "reason": "busy", "retryable": True}, True),
            ("inject_result", {"status": "queued"}, False),
            ("inject_result", {"reason": "busy"}, False),
            ("submit_gate", "sending", True),
            ("submit_error", 5, False),
            ("mute_on_tool_call", True, True),
            ("pipeline", {"vad": [{"type": "speech_start"}], "denoiser": {"output": "AQI="}}, True),
            ("pipeline", {"recorder": {}}, True),
            ("pipeline", {"postprocessors": []}, False),
            ("pipeline", {"aec": {"gain": 2}}, False),
            ("server_vad", False, False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][0]["realtime"][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        for step, valid in (
            ({"call": "realtime.start", "channel_id": "turns", "room_id": "r1",
              "participant_id": "alice", "gate": "connecting", "fail": "refused"}, True),
            ({"call": "realtime.start", "channel_id": "turns", "room_id": "r1",
              "participant_id": "alice", "gate": 1}, False),
            ({"call": "realtime.transcribe", "channel_id": "turns", "text": "Hi",
              "role": "assistant", "is_final": False}, True),
            ({"call": "realtime.transcribe", "channel_id": "turns", "text": "Hi",
              "role": "system"}, False),
            ({"call": "realtime.speech", "channel_id": "turns", "edge": "start"}, True),
            ({"call": "realtime.speech", "channel_id": "turns", "edge": "middle"}, False),
            ({"call": "realtime.audio", "channel_id": "turns", "source": "transport",
              "frames": ["AQI="]}, True),
            ({"call": "realtime.audio", "channel_id": "turns", "source": "client",
              "frames": ["AQI="]}, False),
            ({"call": "realtime.audio", "channel_id": "turns", "source": "provider",
              "frames": []}, False),
            ({"call": "realtime.response", "channel_id": "turns", "edge": "end"}, True),
            ({"call": "realtime.response", "channel_id": "turns"}, False),
            ({"call": "realtime.wait_idle", "channel_id": "turns", "room_id": "r1",
              "timeout_ms": 100}, True),
            ({"call": "realtime.wait_idle", "channel_id": "turns", "room_id": "r1",
              "timeout_ms": 0}, False),
            ({"call": "realtime.read", "channel_id": "turns", "stages": ["recorder"],
              "calls": ["tap_outbound"]}, True),
            ({"call": "realtime.read", "channel_id": "turns", "stages": "recorder"}, False),
            ({"call": "realtime.start", "channel_id": "turns", "room_id": "r1",
              "participant_id": "alice", "expect": {"error": "provider_failed"}}, True),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_realtime_session_states_its_configuration_and_usage(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/realtime/reconfiguring-a-session-changes-that-session-only.json"
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        for member, value, valid in (
            ("system_prompt", "Be brief", True),
            ("system_prompt", None, False),
            ("voice", "calm", True),
            ("on_usage", {}, True),
            ("on_usage", {"gate": "billing", "fails": "down"}, True),
            ("on_usage", {"gate": 1}, False),
            ("on_usage", {"blocks": True}, False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["setup"]["channels"][0]["realtime"][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        start = {"call": "realtime.start", "channel_id": "rt", "room_id": "r1", "participant_id": "p"}
        usage = {"call": "realtime.usage", "channel_id": "rt", "input_tokens": 3, "output_tokens": 4}
        for step, valid in (
            ({**start, "system_prompt": "Own", "voice": "own"}, True),
            ({**start, "voice": 3}, False),
            ({"call": "realtime.reconfigure", "channel_id": "rt"}, True),
            (
                {
                    "call": "realtime.reconfigure",
                    "channel_id": "rt",
                    "room_id": "r2",
                    "system_prompt": "Handoff",
                    "voice": "other",
                    "tools": ["lookup"],
                },
                True,
            ),
            ({"call": "realtime.reconfigure", "channel_id": "rt", "tools": "lookup"}, False),
            (
                {"call": "realtime.configure", "channel_id": "rt", "tools": [], "voice": "v"},
                True,
            ),
            ({"call": "realtime.configure", "channel_id": "rt", "system_prompt": "x"}, False),
            (usage, True),
            ({**usage, "details": {"cached_tokens": 2}}, True),
            ({**usage, "input_tokens": -1}, False),
            ({"call": "realtime.usage", "channel_id": "rt", "input_tokens": 3}, False),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_conference_bot_is_read_plugged_granted_and_reported(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/conference/each-kind-is-plugged-and-unplugged-on-a-running-channel.json"
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        for step, valid in (
            ({"call": "conference.read", "channel_id": "conf"}, True),
            ({"call": "conference.read", "channel_id": "conf", "calls": ["leave"]}, True),
            ({"call": "conference.read", "channel_id": "conf", "calls": "leave"}, False),
            ({"call": "conference.read", "channel_id": "conf", "calls": ["leave", "leave"]}, False),
            ({"call": "conference.read", "channel_id": "conf", "calls": ["leaves"]}, False),
            ({"call": "conference.ensure_bot", "channel_id": "conf", "room_id": "r1"}, True),
            ({"call": "conference.ensure_bot", "channel_id": "conf"}, False),
            ({"call": "conference.plug", "channel_id": "conf", "kind": "stt"}, True),
            ({"call": "conference.plug", "channel_id": "conf", "kind": "vision"}, False),
            ({"call": "conference.plug", "channel_id": "conf", "kind": "tts", "tts": {}}, True),
            (
                {"call": "conference.plug", "channel_id": "conf", "kind": "tts",
                 "tts": {"gates": [None, "g"]}},
                True,
            ),
            ({"call": "conference.plug", "channel_id": "conf", "kind": "tts", "tts": None}, False),
            ({"call": "conference.plug", "channel_id": "conf", "kind": "stt", "tts": {}}, False),
            (
                {"call": "conference.plug", "channel_id": "conf", "kind": "recording",
                 "recorder": "rec"},
                True,
            ),
            (
                {"call": "conference.plug", "channel_id": "conf", "kind": "recording",
                 "recorder": None},
                True,
            ),
            ({"call": "conference.plug", "channel_id": "conf", "kind": "recording"}, False),
            (
                {"call": "conference.plug", "channel_id": "conf", "kind": "stt", "recorder": "r"},
                False,
            ),
            ({"call": "conference.unplug", "channel_id": "conf", "kind": "realtime"}, True),
            ({"call": "conference.unplug", "channel_id": "conf"}, False),
            (
                {"call": "conference.set_bot_grants", "channel_id": "conf",
                 "grants": {"subscribe": False, "hidden": True}},
                True,
            ),
            ({"call": "conference.set_bot_grants", "channel_id": "conf", "grants": None}, True),
            (
                {"call": "conference.set_bot_grants", "channel_id": "conf",
                 "grants": {"vision": True}},
                False,
            ),
            ({"call": "conference.set_bot_grants", "channel_id": "conf"}, False),
            ({"call": "conference.bot_lost", "channel_id": "conf", "room_id": "r1"}, True),
            (
                {"call": "conference.bot_lost", "channel_id": "conf", "room_id": "r1",
                 "reason": "gone"},
                True,
            ),
            ({"call": "conference.bot_lost", "channel_id": "conf"}, False),
            (
                {"call": "conference.echo", "channel_id": "conf", "room_id": "r1",
                 "track_id": "b1"},
                True,
            ),
            ({"call": "conference.echo", "channel_id": "conf", "room_id": "r1"}, False),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_voice_bridge_states_its_configuration_and_transports(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/voice/each-session-is-served-by-its-own-transport.json"
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        for member, value, valid in (
            ("bridge", True, True),
            ("bridge", {"mixing_strategy": "mix", "max_participants": 3}, True),
            ("bridge", {"enabled": False}, True),
            ("bridge", {"mixing_strategy": "sum"}, False),
            ("bridge", {"max_participants": 0}, False),
            ("bridge", {"mixer": "numpy"}, False),
            ("tts", None, True),
            ("tts", False, False),
            ("sample_rates", {"bob": {"input_sample_rate": 8000}}, True),
            ("sample_rates", {"bob": {"rate": 8000}}, False),
            ("sample_rates", {"bob": {"output_sample_rate": 0}}, False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        for step, valid in (
            ({"call": "voice.add_backend", "channel_id": "phone", "backend": "line"}, True),
            (
                {
                    "call": "voice.add_backend",
                    "channel_id": "phone",
                    "backend": "line",
                    "capabilities": ["native_aec"],
                    "sample_rates": {"caller": {"input_sample_rate": 8000}},
                },
                True,
            ),
            ({"call": "voice.add_backend", "channel_id": "phone", "backend": "primary"}, False),
            ({"call": "voice.add_backend", "channel_id": "phone"}, False),
            ({"call": "voice.connect", "channel_id": "phone", "participant_id": "caller"}, True),
            ({"call": "voice.connect", "channel_id": "phone", "backend": "line"}, False),
            (
                {"call": "voice.client_disconnected", "channel_id": "phone", "participant_id": "c"},
                True,
            ),
            ({"call": "voice.client_disconnected", "channel_id": "phone"}, False),
            (
                {
                    "call": "voice.join",
                    "channel_id": "phone",
                    "participant_id": "carol",
                    "room_id": "r2",
                    "backend": "line",
                    "push": True,
                },
                True,
            ),
            (
                {"call": "voice.join", "channel_id": "phone", "participant_id": "c", "push": 1},
                False,
            ),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)

    def test_a_conference_states_its_media_arrivals_and_recordings(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = (
            ROOT
            / "scenarios/conference/a-lane-s-utterance-is-one-room-event-attributed-to-its-publisher.json"
        )
        self.assertTrue(validator.is_valid(json.loads(fixture.read_text())))
        for member, value, valid in (
            ("vad", [None, {"type": "speech_end"}], True),
            ("vad", [{"type": "loud"}], False),
            ("stt", None, True),
            ("stt", {"streams": [{"results": [{"text": "Hi"}], "gate": "held"}]}, True),
            ("stt", "Hi", False),
            ("agc", {"output": "AQI="}, True),
            ("denoiser", {"gain": 2}, False),
            ("recording", {}, True),
            ("recording", {"format": "flac", "encryption": "vault", "write_gates": {"mic": "w"}}, True),
            ("recording", {"write_gates": {"mic": 1}}, False),
            ("recording", {"recorder": "named"}, False),
            ("max_queued_frames", 2, True),
            ("max_queued_frames", 0, False),
            ("address_keys", ["caller_number"], True),
            ("address_keys", "caller_number", False),
        ):
            with self.subTest(member=member, value=value):
                scenario = json.loads(fixture.read_text())
                scenario["steps"][0][member] = value
                self.assertEqual(validator.is_valid(scenario), valid)
        for step, valid in (
            ({"call": "conference.join", "channel_id": "conf", "participant_id": "d1",
              "display_name": "Dial-in", "metadata": {"phone_number": "+15550101"},
              "client_metadata": {}, "asserts_provenance": False}, True),
            ({"call": "conference.join", "channel_id": "conf", "participant_id": "d1",
              "asserts_provenance": "no"}, False),
            ({"call": "conference.feed", "channel_id": "conf", "track_id": "mic",
              "frames": ["AQA="], "sample_rate": 48000, "channels": 2, "repeat": 3}, True),
            ({"call": "conference.feed", "channel_id": "conf", "track_id": "mic"}, False),
            ({"call": "conference.feed", "channel_id": "conf", "track_id": "mic",
              "frames": ["AQA="], "sample_rate": 0}, False),
            ({"call": "conference.settle", "channel_id": "conf", "track_ids": ["mic"]}, True),
            ({"call": "conference.settle", "channel_id": "conf", "track_ids": []}, False),
            ({"call": "conference.read", "channel_id": "conf"}, True),
            ({"call": "conference.read"}, False),
            ({"call": "recording.read", "channel_id": "conf"}, True),
            ({"call": "recording.read", "recorder": "named"}, True),
            ({"call": "recording.read", "recorder": "named", "channel_id": "conf"}, False),
            ({"call": "recording.read"}, False),
        ):
            with self.subTest(step=step):
                scenario = json.loads(fixture.read_text())
                scenario["steps"].append(step)
                self.assertEqual(validator.is_valid(scenario), valid)
