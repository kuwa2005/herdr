#!/usr/bin/env python3
"""Tests for scripts/herdr_agent_turns.py."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from scripts import herdr_agent_turns as turns


class HerdrAgentTurnsTests(unittest.TestCase):
    def test_validate_turns_hard_cap(self) -> None:
        self.assertIsNone(turns.validate_turns(1))
        self.assertIsNone(turns.validate_turns(10))
        self.assertIsNotNone(turns.validate_turns(0))
        self.assertIsNotNone(turns.validate_turns(11))
        self.assertEqual(turns.MAX_TURNS, 10)

    def test_instruct_prompt_first_and_followup(self) -> None:
        notes = Path("/tmp/notes")
        first = turns.instruct_prompt(
            turn=1,
            turns=10,
            goal="evolve orchestration",
            workdir=Path("/repo"),
            notes_dir=notes,
            constraints=None,
            prev_review_path=None,
            prev_result_path=None,
        )
        self.assertIn("Turn 1/10 INSTRUCT", first)
        self.assertIn("TURN1_PLAN.md", first)
        self.assertIn("first turn", first.lower())

        follow = turns.instruct_prompt(
            turn=2,
            turns=10,
            goal="evolve orchestration",
            workdir=Path("/repo"),
            notes_dir=notes,
            constraints=None,
            prev_review_path=notes / "TURN1_REVIEW.md",
            prev_result_path=notes / "TURN1_RESULT.md",
        )
        self.assertIn("TURN1_REVIEW.md", follow)
        self.assertIn("TURN1_RESULT.md", follow)
        self.assertIn("STATUS: DONE", follow)

    def test_fix_and_review_prompts(self) -> None:
        notes = Path("/tmp/notes")
        fix = turns.fix_prompt(
            turn=1,
            turns=3,
            goal="goal",
            workdir=Path("/repo"),
            notes_dir=notes,
            constraints=None,
        )
        review = turns.review_prompt(
            turn=1,
            turns=3,
            goal="goal",
            workdir=Path("/repo"),
            notes_dir=notes,
        )
        apply = turns.apply_prompt(turn=1, turns=3, notes_dir=notes)
        self.assertIn("TURN1_PLAN.md", fix)
        self.assertIn("TURN1_RESULT.md", fix)
        self.assertIn("DONE:", fix)
        self.assertIn("VERDICT: APPROVE|REVISE|DONE", review)
        self.assertIn("IMPROVE:", review)
        self.assertIn("EFFECT:", review)
        self.assertIn("Do not edit repository source files", review)
        self.assertIn("TURN1_REVIEW.md", apply)

    def test_parse_verdict_and_plan_stop(self) -> None:
        self.assertEqual(
            turns.parse_verdict("# r\n\nVERDICT: REVISE\n\nfix X\n"),
            "REVISE",
        )
        self.assertEqual(turns.parse_verdict("verdict: done\n"), "DONE")
        self.assertIsNone(turns.parse_verdict("no verdict here"))
        self.assertTrue(turns.parse_plan_stop("STATUS: DONE\nreason: ok\n"))
        self.assertTrue(turns.parse_plan_stop("PLAN: STOP\n"))
        self.assertFalse(turns.parse_plan_stop("STATUS: CONTINUE\n"))

    def test_rejects_turns_above_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = turns.main(
                [
                    "--coder",
                    "coder",
                    "--reviewer",
                    "reviewer",
                    "--turns",
                    "11",
                    "--goal",
                    "x",
                    "--notes-dir",
                    str(Path(tmp) / "notes"),
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 2)

    def test_resolve_agent_in_pane(self) -> None:
        payload = {
            "result": {
                "agents": [
                    {"name": "coder", "pane_id": "w1:p1"},
                    {"pane_id": "w1:p2", "terminal_id": "t2"},
                ]
            }
        }
        with mock.patch.object(turns, "herdr_json", return_value=payload):
            self.assertEqual(turns.resolve_agent_in_pane("herdr", "w1:p1"), "coder")
            # name missing → pane_id before terminal_id (same as summarize_herdr_tabs)
            self.assertEqual(turns.resolve_agent_in_pane("herdr", "w1:p2"), "w1:p2")
            with self.assertRaises(RuntimeError):
                turns.resolve_agent_in_pane("herdr", "w1:p9")

    def test_resolve_roles_from_here_self_mode(self) -> None:
        args = turns.build_parser().parse_args(
            [
                "--from-here",
                "--goal",
                "g",
                "--dry-run",
            ]
        )
        with mock.patch.object(turns, "resolve_from_here", return_value="me"):
            planner, coder, reviewer = turns.resolve_roles(args)
        self.assertEqual((planner, coder, reviewer), ("me", "me", "me"))

    def test_resolve_roles_from_here_with_separate_reviewer(self) -> None:
        args = turns.build_parser().parse_args(
            [
                "--from-here",
                "--reviewer",
                "reviewer",
                "--goal",
                "g",
                "--dry-run",
            ]
        )
        with mock.patch.object(turns, "resolve_from_here", return_value="me"):
            planner, coder, reviewer = turns.resolve_roles(args)
        self.assertEqual((planner, coder, reviewer), ("me", "me", "reviewer"))

    def test_from_here_requires_herdr_pane_id(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "HERDR_PANE_ID"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                turns.resolve_from_here("herdr")
        self.assertIn("HERDR_PANE_ID", str(ctx.exception))

    def test_render_summary_includes_plan_and_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            plan = notes / "TURN1_PLAN.md"
            result = notes / "TURN1_RESULT.md"
            review = notes / "TURN1_REVIEW.md"
            plan.write_text(
                "STATUS: CONTINUE\nTASK: do X\nDONE_WHEN: tests pass\n",
                encoding="utf-8",
            )
            result.write_text(
                "DONE: did X\nVERIFIED: unit tests\n",
                encoding="utf-8",
            )
            review.write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: yes - X landed\n",
                encoding="utf-8",
            )
            rec = turns.TurnRecord(
                number=1,
                instruct_prompt="i",
                fix_prompt="f",
                review_prompt="r",
                apply_prompt=None,
                plan_path=plan,
                result_path=result,
                review_path=review,
                verdict="APPROVE",
                notes=["ok"],
            )
            summary = turns.render_summary(
                [rec],
                goal="大元ゴール",
                notes_dir=notes,
                max_turns=10,
                stop_reason=None,
            )
            self.assertIn("# 自己改善レポート（効果判定）", summary)
            self.assertIn("## 大元の指示", summary)
            self.assertIn("大元ゴール", summary)
            self.assertIn("**判定: 部分改善（継続余地あり）**", summary)
            self.assertIn("do X", summary)
            self.assertIn("did X", summary)
            self.assertIn("none", summary)
            self.assertIn("APPROVE", summary)

    def test_dry_run_from_here_self_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "herdr-turns-notes"
            code = turns.main(
                [
                    "--from-here",
                    "--coder",
                    "me",
                    "--turns",
                    "1",
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
            self.assertTrue((notes / "SUMMARY.md").exists())
            self.assertTrue((notes / "TURN1_PLAN.md").exists())
            reports = list(Path(tmp).glob("自己改善*.md"))
            self.assertEqual(len(reports), 1)
            self.assertRegex(reports[0].name, r"^自己改善\d{14}\.md$")
            report_text = reports[0].read_text(encoding="utf-8")
            self.assertIn("demo goal", report_text)
            self.assertIn("自己改善レポート（効果判定）", report_text)
            self.assertIn("大元の指示", report_text)

    def test_self_improve_report_filename(self) -> None:
        name = turns.self_improve_report_filename(
            datetime(2026, 10, 15, 10, 1, 23)
        )
        self.assertEqual(name, "自己改善20261015100123.md")

    def test_write_and_display_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "work"
            notes = Path(tmp) / "notes"
            workdir.mkdir()
            notes.mkdir()
            when = datetime(2026, 10, 15, 12, 34, 56)
            path = turns.write_and_display_summary(
                "# 自己改善レポート（効果判定）\n\n## 大元の指示\n\ng\n",
                workdir=workdir,
                notes_dir=notes,
                when=when,
            )
            self.assertEqual(path.name, "自己改善20261015123456.md")
            self.assertTrue(path.exists())
            self.assertTrue((notes / "SUMMARY.md").exists())
            self.assertTrue((notes / "自己改善20261015123456.md").exists())

    def test_default_notes_dir_from_here(self) -> None:
        args = turns.build_parser().parse_args(
            ["--from-here", "--goal", "g", "--dry-run"]
        )
        with mock.patch.object(Path, "cwd", return_value=Path("/work")):
            path = turns.default_notes_dir(args)
        self.assertEqual(path, Path("/work/herdr-turns-notes").resolve())

    def test_daemonize_prints_pid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            fake = mock.Mock()
            fake.pid = 4242
            with mock.patch.object(turns.subprocess, "Popen", return_value=fake) as popen:
                code = turns.daemonize(
                    ["--from-here", "--turns", "2", "--goal", "g", "--daemon"],
                    notes_dir=notes,
                )
            self.assertEqual(code, 0)
            self.assertTrue(popen.called)
            cmd = popen.call_args[0][0]
            self.assertNotIn("--daemon", cmd)
            self.assertIn("--notes-dir", cmd)


if __name__ == "__main__":
    unittest.main()
