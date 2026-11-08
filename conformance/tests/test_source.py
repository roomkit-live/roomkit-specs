from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traceability.source import check_history, extract, strip_annotations


def marked(text: str, identity: str = "RK-9.3-001", **changes: object) -> str:
    metadata = {"id": identity, "kind": "behavior", "applies": "SYNC hooks", **changes}
    return f"<!-- rfc: {json.dumps(metadata)} -->\n{text}\n<!-- /rfc -->\n"


class SourceTests(unittest.TestCase):
    def test_exact_clause_and_applicability_are_fingerprinted(self) -> None:
        first = extract("### 9.3 Hooks\n" + marked("The result MUST be kept."))
        requirement = first["requirements"][0]
        self.assertEqual(requirement["section"], "9.3")
        self.assertEqual(requirement["text"], "The result MUST be kept.")
        for changed in [
            marked("The result MUST NOT be kept."),
            marked("The result MUST be kept.", applies="ASYNC hooks"),
        ]:
            other = extract("### 9.3 Hooks\n" + changed)
            self.assertNotEqual(
                requirement["sha256"], other["requirements"][0]["sha256"]
            )

    def test_move_keeps_the_id_and_current_section_is_separate(self) -> None:
        result = extract("### 9.4 New location\n" + marked("Keep the event."))
        self.assertEqual(result["requirements"][0]["id"], "RK-9.3-001")
        self.assertEqual(result["requirements"][0]["section"], "9.4")

    def test_examples_do_not_create_headings_or_requirements(self) -> None:
        for fence in ["```", "~~~~"]:
            with self.subTest(fence=fence):
                text = (
                    "## 9. Hooks\n"
                    + fence
                    + "\n### 8.1 Fake\n"
                    + marked("MUST")
                    + fence
                    + "\n"
                )
                result = extract(text)
                self.assertEqual(result["requirements"], [])
                self.assertEqual(
                    [item["section"] for item in result["sections"]], ["9"]
                )
                self.assertEqual(result["sections"][0]["unannotated_keyword_lines"], [])

    def test_structural_code_is_preserved_inside_a_requirement(self) -> None:
        body = "```\ninterface Hook { timeout: float = 30 }\n```"
        result = extract("### 9.1 Hooks\n" + marked(body, kind="structural"))
        self.assertEqual(result["requirements"][0]["text"], body)

    def test_inline_table_annotations_preserve_the_row(self) -> None:
        metadata = json.dumps(
            {"id": "RK-9.2-001", "kind": "structural", "applies": "hooks"}
        )
        result = extract(
            "### 9.2 Table\n| Name | Mode |\n|---|---|\n"
            f"| <!-- rfc: {metadata} --> START | ASYNC <!-- /rfc --> |\n"
        )
        self.assertEqual(result["requirements"][0]["text"], "START | ASYNC")

    def test_unannotated_keywords_remain_visible(self) -> None:
        result = extract(
            "### 9.3 Hooks\nMUST not disappear.\n" + marked("MUST keep it.")
        )
        self.assertEqual(result["sections"][0]["unannotated_keyword_lines"], [2])

    def test_the_abstract_is_not_silently_lost(self) -> None:
        result = extract(
            "# RFC\n## Abstract\nAn implementation MAY choose its language.\n## 1. Terms\n"
        )
        self.assertEqual(result["sections"][0]["section"], "0")
        self.assertEqual(result["sections"][0]["unannotated_keyword_lines"], [3])

    def test_bad_boundaries_and_duplicate_ids_are_refused(self) -> None:
        cases = [
            marked("x") + marked("y"),
            marked(marked("x")),
            "<!-- /rfc -->",
            marked(""),
            marked("### 9.4 Another\nx"),
            marked("x").replace("<!-- /rfc -->", ""),
            '<!-- rfc: {"id": "RK-9.3-001"} -->x<!-- /rfc -->',
            marked("x", kind=[]),
            marked("x", applies=""),
        ]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ValueError):
                extract("### 9.3 Hooks\n" + body)

    def test_removed_ids_need_retirement_and_retired_ids_cannot_return(self) -> None:
        before = extract("### 9.3 Hooks\n" + marked("x"))
        after = extract("### 9.3 Hooks\n")
        self.assertIn("removed without retirement", check_history(after, before, [])[0])
        self.assertEqual(check_history(after, before, ["RK-9.3-001"]), [])
        self.assertIn(
            "retired ID reused", check_history(before, after, ["RK-9.3-001"])[0]
        )
        self.assertIn(
            "retirement removed", check_history(after, after, [], ["RK-9.3-001"])[0]
        )

    def test_annotations_do_not_change_the_normative_text(self) -> None:
        self.assertEqual(
            strip_annotations("## 9. Hooks\n" + marked("Keep it.")),
            "## 9. Hooks\nKeep it.\n",
        )
        with self.assertRaisesRegex(ValueError, "malformed"):
            extract("## 9. Hooks\n<!--rfc: broken -->\n")


if __name__ == "__main__":
    unittest.main()
