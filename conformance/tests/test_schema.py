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
