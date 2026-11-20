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
