from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_metadata_patch_requires_a_text_room_id(self) -> None:
        schema = json.loads((ROOT / "scenario.schema.json").read_text())
        validator = Draft202012Validator(schema)
        fixture = ROOT / "scenarios/tasks" / (
            "a-background-worker-keeps-its-turns-task-boundary-after-a-store-patch.json"
        )
        for room_id in (7, None, [], {}, "call", "$r1"):
            with self.subTest(room_id=room_id):
                scenario = json.loads(fixture.read_text())
                patch = next(
                    step for step in scenario["steps"]
                    if step.get("call") == "store.patch_room_metadata"
                )
                patch["room_id"] = room_id
                self.assertEqual(validator.is_valid(scenario), isinstance(room_id, str))
