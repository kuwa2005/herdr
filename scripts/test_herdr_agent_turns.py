#!/usr/bin/env python3
"""Tests for scripts/herdr_agent_turns.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import herdr_agent_turns as turns


class HerdrAgentTurnsTests(unittest.TestCase):
    def test_implement_prompt_mentions_turn_and_result_path(self) -> None:
        notes = Path("/tmp/notes")
        text = turns.implement_prompt(
            turn=2,
            turns=3,
            goal="improve orchestration",
            workdir=Path("/repo"),
            notes_dir=notes,
            constraints=None,
        )
        self.assertIn("Turn 2/3 IMPLEMENT", text)
        self.assertIn("improve orchestration", text)
        self.assertIn(str(notes / "TURN2_RESULT.md"), text)
        self.assertIn("Do not commit", text)

    def test_review_and_apply_prompts(self) -> None:
        notes = Path("/tmp/notes")
        review = turns.review_prompt(
            turn=1,
            turns=3,
            goal="goal",
            workdir=Path("/repo"),
            notes_dir=notes,
        )
        apply = turns.apply_prompt(turn=1, turns=3, notes_dir=notes)
        self.assertIn("TURN1_REVIEW.md", review)
        self.assertIn("Do not edit repository files", review)
        self.assertIn("TURN1_REVIEW.md", apply)
        self.assertIn("TURN1_RESULT.md", apply)

    def test_render_summary_includes_each_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            result = notes / "TURN1_RESULT.md"
            review = notes / "TURN1_REVIEW.md"
            result.write_text("# result\n\ndid the thing\n", encoding="utf-8")
            review.write_text("# review\n\nfix X\n", encoding="utf-8")
            rec = turns.TurnRecord(
                number=1,
                implement_prompt="i",
                review_prompt="r",
                apply_prompt="a",
                result_path=result,
                review_path=review,
                notes=["ok"],
            )
            summary = turns.render_summary([rec], goal="g", notes_dir=notes)
            self.assertIn("# Agent turns summary", summary)
            self.assertIn("## Turn 1", summary)
            self.assertIn("did the thing", summary)
            self.assertIn("fix X", summary)
            self.assertIn("ok", summary)

    def test_dry_run_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            code = turns.main(
                [
                    "--coder",
                    "coder",
                    "--reviewer",
                    "reviewer",
                    "--turns",
                    "2",
                    "--goal",
                    "demo goal",
                    "--notes-dir",
                    str(notes),
                    "--workdir",
                    tmp,
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 0)
            summary = (notes / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("demo goal", summary)
            self.assertIn("## Turn 1", summary)
            self.assertIn("## Turn 2", summary)
            self.assertTrue((notes / "TURN1_RESULT.md").exists())
            self.assertTrue((notes / "TURN2_REVIEW.md").exists())


if __name__ == "__main__":
    unittest.main()
