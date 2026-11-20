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
