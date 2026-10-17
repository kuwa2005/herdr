#!/usr/bin/env python3
"""Tests for scripts/herdr_agent_turns.py."""

from __future__ import annotations

import json
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
        self.assertIn("director / planning", first)
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

    def test_parse_task_pack_yaml_and_markdown(self) -> None:
        yaml_text = (
            "goal: |\n"
            "  Improve the orchestrator\n"
            "  with task packs\n"
            "acceptance: \"tests green\"\n"
        )
        goal, acc = turns.parse_task_pack_text(yaml_text)
        self.assertIn("Improve the orchestrator", goal)
        self.assertIn("with task packs", goal)
        self.assertEqual(acc, "tests green")

        md_text = (
            "# Goal\n\n"
            "Ship wave 3 step 3\n\n"
            "## Acceptance criteria\n\n"
            "- unit tests pass\n"
            "- resume restores hashes\n"
        )
        goal2, acc2 = turns.parse_task_pack_text(md_text)
        self.assertEqual(goal2, "Ship wave 3 step 3")
        self.assertIsNotNone(acc2)
        assert acc2 is not None
        self.assertIn("unit tests pass", acc2)
        self.assertIn("resume restores hashes", acc2)

        # YAML goal key wins over a later ## Goal heading.
        mixed = "goal: from-yaml\n\n## Goal\n\nfrom-md\n"
        g3, _a3 = turns.parse_task_pack_text(mixed)
        self.assertEqual(g3, "from-yaml")

        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack.yaml"
            pack.write_text("goal: packed-goal\nacceptance: |\n  A\n  B\n", encoding="utf-8")
            loaded_g, loaded_a = turns.load_task_pack(pack)
            self.assertEqual(loaded_g, "packed-goal")
            self.assertEqual(loaded_a, "A\nB")

            empty = Path(tmp) / "empty.yaml"
            empty.write_text("acceptance: only\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                turns.load_task_pack(empty)

    def test_goal_acceptance_cli_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            goal_file = root / "goal.txt"
            goal_file.write_text("from-goal-file\n", encoding="utf-8")
            acc_file = root / "acc.txt"
            acc_file.write_text("from-acceptance-file\n", encoding="utf-8")
            pack = root / "pack.md"
            pack.write_text(
                "## Goal\n\nfrom-pack\n\n## Acceptance\n\npack-acc\n",
                encoding="utf-8",
            )
            notes = root / "notes"
            notes.mkdir()

            # --goal beats --goal-file and --task-pack
            args = turns.build_parser().parse_args(
                [
                    "--goal",
                    "from-cli",
                    "--goal-file",
                    str(goal_file),
                    "--task-pack",
                    str(pack),
                    "--acceptance-file",
                    str(acc_file),
                    "--coder",
                    "c",
                    "--turns",
                    "1",
                    "--notes-dir",
                    str(notes),
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args)
            self.assertEqual(args.goal, "from-cli")
            self.assertEqual(args.acceptance, "from-acceptance-file")

            # --goal-file beats --task-pack goal; pack acceptance when no acc file
            args2 = turns.build_parser().parse_args(
                [
                    "--goal-file",
                    str(goal_file),
                    "--task-pack",
                    str(pack),
                    "--coder",
                    "c",
                    "--turns",
                    "1",
                    "--notes-dir",
                    str(notes),
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args2)
            self.assertEqual(args2.goal, "from-goal-file")
            self.assertEqual(args2.acceptance, "pack-acc")

            # task-pack alone
            args3 = turns.build_parser().parse_args(
                [
                    "--task-pack",
                    str(pack),
                    "--coder",
                    "c",
                    "--turns",
                    "1",
                    "--notes-dir",
                    str(notes),
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args3)
            self.assertEqual(args3.goal, "from-pack")
            self.assertEqual(args3.acceptance, "pack-acc")

    def test_goal_acceptance_persist_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes = root / "notes"
            notes.mkdir()
            goal_file = root / "goal.txt"
            goal_file.write_text("persist-goal\n", encoding="utf-8")
            acc_file = root / "acc.txt"
            acc_file.write_text("persist-acceptance\n", encoding="utf-8")
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="persist-goal",
                workdir=root,
                max_turns=5,
                acceptance="persist-acceptance",
                goal_file=goal_file,
                acceptance_file=acc_file,
            )
            meta = turns.load_run_meta(notes)
            self.assertEqual(meta.get("goal"), "persist-goal")
            self.assertEqual(
                meta.get("goal_sha256"),
                turns.content_digest("persist-goal"),
            )
            self.assertEqual(meta.get("acceptance"), "persist-acceptance")
            self.assertEqual(
                meta.get("acceptance_sha256"),
                turns.content_digest("persist-acceptance"),
            )
            self.assertEqual(meta.get("goal_file"), str(goal_file.resolve()))
            self.assertEqual(
                meta.get("acceptance_file"), str(acc_file.resolve())
            )

            # Resume without CLI goal/files → re-read files
            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args)
            self.assertEqual(args.goal, "persist-goal")
            self.assertEqual(args.acceptance, "persist-acceptance")

            # Resume file-missing policy: fall back to meta text
            goal_file.unlink()
            acc_file.unlink()
            args2 = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args2)
            self.assertEqual(args2.goal, "persist-goal")
            self.assertEqual(args2.acceptance, "persist-acceptance")

    def test_instruct_and_review_include_acceptance(self) -> None:
        notes = Path("/tmp/notes")
        acceptance = "all new tests green\nno src/ edits"
        instruct = turns.instruct_prompt(
            turn=1,
            turns=2,
            goal="task-pack goal",
            workdir=Path("/repo"),
            notes_dir=notes,
            constraints=None,
            prev_review_path=None,
            prev_result_path=None,
            acceptance=acceptance,
        )
        self.assertIn("Acceptance criteria:", instruct)
        self.assertIn("all new tests green", instruct)
        self.assertIn("Align PLAN DONE_WHEN", instruct)

        review = turns.review_prompt(
            turn=1,
            turns=2,
            goal="task-pack goal",
            workdir=Path("/repo"),
            notes_dir=notes,
            acceptance=acceptance,
        )
        self.assertIn("Acceptance criteria:", review)
        self.assertIn("all new tests green", review)
        self.assertIn("Use acceptance criteria together with DONE_WHEN", review)

        bare = turns.instruct_prompt(
            turn=1,
            turns=1,
            goal="g",
            workdir=Path("/repo"),
            notes_dir=notes,
            constraints=None,
            prev_review_path=None,
            prev_result_path=None,
            acceptance=None,
        )
        self.assertNotIn("Acceptance criteria:", bare)

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
            diff_summary=None,
        )
        apply = turns.apply_prompt(turn=1, turns=3, notes_dir=notes)
        self.assertIn("TURN1_PLAN.md", fix)
        self.assertIn("TURN1_RESULT.md", fix)
        self.assertIn("DONE:", fix)
        self.assertIn("FILES:", fix)
        self.assertIn("Do not commit.", fix)
        self.assertIn("concrete command or check", fix)
        self.assertIn("looks good", fix)
        self.assertIn("manual review", fix)
        self.assertIn("should work", fix)
        self.assertIn("run the relevant test/check", fix)
        self.assertIn("before writing", fix)
        self.assertIn("VERDICT: APPROVE|REVISE|DONE|ESCALATE", review)
        self.assertIn("ESCALATE: human owner judgment is required", review)
        self.assertIn("DONE_WHEN", review)
        self.assertIn("prefer REVISE", review)
        self.assertIn("_(pending)_", review)
        self.assertIn("concrete command or check", review)
        self.assertIn("git diff", review)
        self.assertIn("DONE and FILES", review)
        self.assertIn("IMPROVE:", review)
        self.assertIn("EFFECT:", review)
        self.assertIn("Do not edit repository source files", review)
        self.assertIn("TURN1_REVIEW.md", apply)
        self.assertNotIn(turns.DIFF_SUMMARY_HEADER, review)

    def test_collect_workdir_diff_summary(self) -> None:
        workdir = Path("/repo")

        def _ok(args: list[str], **_kwargs: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 0
            if args[-1] == "--stat":
                out.stdout = " scripts/a.py | 2 +-\n 1 file changed\n"
            else:
                out.stdout = "M\tscripts/a.py\n"
            out.stderr = ""
            return out

        summary = turns.collect_workdir_diff_summary(workdir, runner=_ok)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertIn("scripts/a.py", summary)
        self.assertIn("1 file changed", summary)
        self.assertIn("M\tscripts/a.py", summary)

        prompt = turns.review_prompt(
            turn=1,
            turns=2,
            goal="g",
            workdir=workdir,
            notes_dir=Path("/tmp/notes"),
            diff_summary=summary,
        )
        self.assertTrue(prompt.startswith(turns.DIFF_SUMMARY_HEADER))
        self.assertIn("scripts/a.py", prompt)
        self.assertIn("Turn 1/2 REVIEW", prompt)

        def _fail(*_a: object, **_k: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 128
            out.stdout = ""
            out.stderr = "not a git repository"
            return out

        self.assertIsNone(
            turns.collect_workdir_diff_summary(workdir, runner=_fail)
        )
        self.assertIsNone(
            turns.collect_workdir_diff_summary(
                workdir,
                runner=mock.Mock(side_effect=FileNotFoundError("git")),
            )
        )

        def _empty(*_a: object, **_k: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 0
            out.stdout = "  \n"
            out.stderr = ""
            return out

        self.assertIsNone(
            turns.collect_workdir_diff_summary(workdir, runner=_empty)
        )
        self.assertNotIn(
            turns.DIFF_SUMMARY_HEADER,
            turns.review_prompt(
                turn=1,
                turns=1,
                goal="g",
                workdir=workdir,
                notes_dir=Path("/n"),
                diff_summary=None,
            ),
        )

        def _long(*_a: object, **_k: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 0
            out.stdout = "x" * 500
            out.stderr = ""
            return out

        truncated = turns.collect_workdir_diff_summary(
            workdir, max_chars=40, runner=_long
        )
        self.assertIsNotNone(truncated)
        assert truncated is not None
        self.assertLessEqual(len(truncated), 40)
        self.assertTrue(truncated.endswith("… (truncated)"))

    def test_collect_turn_review_pack_and_review_prompt(self) -> None:
        workdir = Path("/repo")
        notes = Path("/tmp/notes")

        def _git_runner(args: list[str], **_kwargs: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 0
            out.stderr = ""
            joined = " ".join(args)
            if args[-1] == "--short" or "status" in args:
                out.stdout = " M scripts/a.py\n?? new.txt\n"
            elif args[-1] == "--stat":
                out.stdout = " scripts/a.py | 2 +-\n 1 file changed\n"
            elif args[-1] == "--name-status":
                out.stdout = "M\tscripts/a.py\n"
            elif joined == "git diff" or args == ["git", "diff"]:
                out.stdout = "diff --git a/scripts/a.py b/scripts/a.py\n+" + (
                    "x" * 200
                )
            else:
                out.stdout = ""
            return out

        pack = turns.collect_turn_review_pack(
            workdir,
            max_diff_chars=80,
            runner=_git_runner,
        )
        self.assertIn("## git status --short", pack)
        self.assertIn("scripts/a.py", pack)
        self.assertIn("## diff summary (stat / name-status)", pack)
        self.assertIn("1 file changed", pack)
        self.assertIn("## git diff (truncated)", pack)
        self.assertIn("… (truncated)", pack)
        self.assertNotIn("## test_command", pack)

        def _test_ok(cmd: str, **_kwargs: object) -> mock.Mock:
            self.assertEqual(cmd, "echo ok")
            out = mock.Mock()
            out.returncode = 0
            out.stdout = "ok\n"
            out.stderr = ""
            return out

        pack_ok = turns.collect_turn_review_pack(
            workdir,
            test_command="echo ok",
            runner=_git_runner,
            test_runner=_test_ok,
        )
        self.assertIn("## test_command", pack_ok)
        self.assertIn("$ echo ok", pack_ok)
        self.assertIn("exit_code: 0", pack_ok)
        self.assertIn("ok", pack_ok)

        def _test_fail(cmd: str, **_kwargs: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 7
            out.stdout = "boom\n"
            out.stderr = "err detail\n"
            return out

        pack_fail = turns.collect_turn_review_pack(
            workdir,
            test_command="false",
            runner=_git_runner,
            test_runner=_test_fail,
        )
        self.assertIn("exit_code: 7", pack_fail)
        self.assertIn("boom", pack_fail)
        self.assertIn("err detail", pack_fail)

        def _status_fail(*_a: object, **_k: object) -> mock.Mock:
            out = mock.Mock()
            out.returncode = 128
            out.stdout = ""
            out.stderr = "fatal"
            return out

        pack_bad_status = turns.collect_turn_review_pack(
            workdir,
            runner=_git_runner,
            status_runner=_status_fail,
        )
        self.assertIn("(unavailable)", pack_bad_status)

        state_path = notes / "TURN1_STATE.txt"
        prompt = turns.review_prompt(
            turn=1,
            turns=2,
            goal="g",
            workdir=workdir,
            notes_dir=notes,
            state_pack=pack_ok,
            state_path=state_path,
        )
        self.assertIn(str(state_path), prompt)
        self.assertIn(turns.STATE_PACK_HEADER, prompt)
        self.assertIn("exit_code: 0", prompt)
        self.assertIn("scripts/a.py", prompt)
        self.assertIn("Turn 1/2 REVIEW", prompt)
        # Unified pack replaces legacy DIFF_SUMMARY_HEADER double-inject.
        self.assertNotIn(turns.DIFF_SUMMARY_HEADER, prompt)

        truncated_pack = turns.collect_turn_review_pack(
            workdir,
            max_pack_chars=60,
            runner=_git_runner,
        )
        self.assertLessEqual(len(truncated_pack), 60)
        self.assertTrue(truncated_pack.endswith("… (truncated)"))

    def test_write_turn_state_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            path = turns.write_turn_state_pack(notes, 3, "hello pack")
            self.assertEqual(path, notes / "TURN3_STATE.txt")
            self.assertEqual(
                path.read_text(encoding="utf-8"), "hello pack\n"
            )

    def test_test_command_persist_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            notes.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="from-run-json",
                workdir=Path(tmp),
                max_turns=5,
                test_command="python3 -m unittest scripts.test_herdr_agent_turns -q",
            )
            meta = turns.load_run_meta(notes)
            self.assertEqual(
                meta.get("test_command"),
                "python3 -m unittest scripts.test_herdr_agent_turns -q",
            )
            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args)
            self.assertEqual(
                args.test_command,
                "python3 -m unittest scripts.test_herdr_agent_turns -q",
            )

            # CLI --test-command overrides run.json on resume.
            args2 = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--test-command",
                    "echo cli-wins",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args2)
            self.assertEqual(args2.test_command, "echo cli-wins")

    def test_dry_run_writes_turn_state_pack(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "state-pack-dry",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            state = notes / "TURN1_STATE.txt"
            self.assertTrue(state.is_file())
            pack_text = state.read_text(encoding="utf-8")
            self.assertIn("## git status --short", pack_text)
            self.assertIn(str(state), out)
            self.assertIn(turns.STATE_PACK_HEADER, out)
            self.assertNotIn(turns.DIFF_SUMMARY_HEADER, out)
            meta = turns.load_run_meta(notes)
            self.assertNotIn("test_command", meta)

            # With --test-command, run.json stores it and STATE includes section.
            notes2 = Path(tmp) / "notes2"
            notes2.mkdir()
            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                code2 = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "state-pack-test-cmd",
                        "--notes-dir",
                        str(notes2),
                        "--workdir",
                        str(work),
                        "--test-command",
                        "echo pack-test",
                        "--dry-run",
                    ]
                )
            self.assertEqual(code2, 0)
            meta2 = turns.load_run_meta(notes2)
            self.assertEqual(meta2.get("test_command"), "echo pack-test")
            state2 = (notes2 / "TURN1_STATE.txt").read_text(encoding="utf-8")
            self.assertIn("## test_command", state2)
            self.assertIn("exit_code:", state2)

    def test_is_skeleton_verified(self) -> None:
        self.assertTrue(turns.is_skeleton_verified(None))
        self.assertTrue(turns.is_skeleton_verified(""))
        self.assertTrue(turns.is_skeleton_verified("_(pending)_"))
        self.assertTrue(turns.is_skeleton_verified("looks good"))
        self.assertTrue(turns.is_skeleton_verified("manual review"))
        self.assertTrue(turns.is_skeleton_verified("should work"))
        self.assertFalse(
            turns.is_skeleton_verified(
                "python3 -m unittest scripts.test_herdr_agent_turns -q"
            )
        )
        self.assertFalse(turns.is_skeleton_verified("just check"))

    def test_normalize_plan_task_and_stall(self) -> None:
        self.assertEqual(turns.normalize_plan_task("  Add Tests. "), "add tests")
        self.assertEqual(turns.normalize_plan_task("ADD   tests!"), "add tests")
        self.assertEqual(turns.normalize_plan_task("add tests"), "add tests")
        self.assertEqual(turns.normalize_plan_task(None), "")
        self.assertEqual(turns.normalize_plan_task("  "), "")

        prev = (
            "STATUS: CONTINUE\n"
            "TASK: add tests\n"
            "DONE_WHEN: green\n"
            "OUT_OF_SCOPE: none\n"
        )
        same = (
            "STATUS: CONTINUE\n"
            "TASK:  Add tests.\n"
            "DONE_WHEN: still green\n"
            "OUT_OF_SCOPE: docs\n"
        )
        different = (
            "STATUS: CONTINUE\n"
            "TASK: wire stall detection\n"
            "DONE_WHEN: unit tests\n"
        )
        self.assertTrue(turns.plan_tasks_stall(same, prev))
        self.assertFalse(turns.plan_tasks_stall(different, prev))
        self.assertFalse(turns.plan_tasks_stall(None, prev))
        self.assertFalse(turns.plan_tasks_stall(same, None))
        # Empty / missing TASK must not stall.
        self.assertFalse(
            turns.plan_tasks_stall(
                "STATUS: CONTINUE\nDONE_WHEN: x\n",
                "STATUS: CONTINUE\nDONE_WHEN: y\n",
            )
        )
        # DONE/STOP/ESCALATE current plans are not stall candidates.
        self.assertFalse(
            turns.plan_tasks_stall(
                "STATUS: DONE\nTASK: add tests\n",
                prev,
            )
        )
        self.assertFalse(
            turns.plan_tasks_stall(
                "STATUS: ESCALATE\nTASK: add tests\nreason: pick A\n",
                prev,
            )
        )

    def test_stall_repeated_task_dry_run(self) -> None:
        """Turn 2 same TASK as turn 1 → stop before FIX, write NEEDS_OWNER."""
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_PLAN.md").write_text(
                "STATUS: CONTINUE\n"
                "TASK: add tests\n"
                "DONE_WHEN: green\n"
                "OUT_OF_SCOPE: none\n",
                encoding="utf-8",
            )
            (notes / "TURN1_RESULT.md").write_text(
                "DONE: first pass\n"
                "VERIFIED: python3 -m unittest scripts.test_herdr_agent_turns -q\n"
                "FILES: none\n",
                encoding="utf-8",
            )
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: partial\n",
                encoding="utf-8",
            )
            # Pre-seed turn 2 plan so dry-run does not overwrite it.
            (notes / "TURN2_PLAN.md").write_text(
                "STATUS: CONTINUE\n"
                "TASK:  Add tests.\n"
                "DONE_WHEN: green\n"
                "OUT_OF_SCOPE: none\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes, goal="stall-demo", workdir=work, max_turns=5
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--resume",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--turns",
                        "1",
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("======== TURN 2/2: instruct ========", out)
            self.assertNotIn("======== TURN 2/2: fix ========", out)
            needs = notes / "NEEDS_OWNER.md"
            self.assertTrue(needs.exists())
            needs_text = needs.read_text(encoding="utf-8")
            self.assertIn("repeated TASK", needs_text)
            self.assertIn("add tests", needs_text.lower())
            self.assertFalse((notes / "COMPLETE.md").exists())
            summary = (notes / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("stall: repeated TASK", summary)
            self.assertIn("repeated TASK at turn 2", summary)

    def test_result_has_weak_verified_gate(self) -> None:
        self.assertTrue(
            turns.result_has_weak_verified(
                "DONE: changed x\nVERIFIED: looks good\nFILES: none\n"
            )
        )
        self.assertTrue(turns.result_has_weak_verified(None))
        self.assertTrue(
            turns.result_has_weak_verified("# Turn 1 result\n\n_(pending)_\n")
        )
        self.assertTrue(
            turns.result_has_weak_verified(
                "DONE: changed x\nVERIFIED: _(pending)_\nFILES: a.py\n"
            )
        )
        self.assertFalse(
            turns.result_has_weak_verified(
                "DONE: changed x\n"
                "VERIFIED: python3 -m unittest scripts.test_herdr_agent_turns -q\n"
                "FILES: a.py\n"
            )
        )
        reask = turns.weak_verified_reprompt(
            turn=2, turns=5, notes_dir=Path("/tmp/notes")
        )
        self.assertIn("weak VERIFIED re-ask", reask)
        self.assertIn("TURN2_RESULT.md", reask)
        self.assertIn("TURN2_PLAN.md", reask)
        self.assertIn("Do not commit", reask)

    def test_weak_verified_soft_gate_dry_run(self) -> None:
        """Post-FIX gate: weak → one re-ask; still weak → review note; strong → skip."""
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()

            # Default skeleton RESULT is weak → re-ask + review note.
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "soft-gate-weak",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("fix (weak VERIFIED re-ask)", out)
            self.assertIn("weak VERIFIED re-ask", out)
            self.assertIn(turns.WEAK_VERIFIED_REVIEW_NOTE, out)
            summary = (notes / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("weak-verified: re-asked once", summary)
            self.assertIn("weak-verified: still weak after re-ask", summary)

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            # Pre-write strong VERIFIED so write_skeleton does not overwrite.
            (notes / "TURN1_RESULT.md").write_text(
                "DONE: implemented gate\n"
                "VERIFIED: python3 -m unittest scripts.test_herdr_agent_turns -q\n"
                "FILES: scripts/herdr_agent_turns.py\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "soft-gate-strong",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertNotIn("fix (weak VERIFIED re-ask)", out)
            self.assertNotIn(turns.WEAK_VERIFIED_REVIEW_NOTE, out)
            summary = (notes / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertNotIn("weak-verified:", summary)

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_RESULT.md").write_text(
                "DONE: something\nVERIFIED: looks good\nFILES: none\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "soft-gate-vague",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("fix (weak VERIFIED re-ask)", out)
            # Still looks good after dry-run re-ask (file unchanged) → note.
            self.assertIn(turns.WEAK_VERIFIED_REVIEW_NOTE, out)

    def test_parse_verdict_and_plan_stop(self) -> None:
        self.assertEqual(
            turns.parse_verdict("# r\n\nVERDICT: REVISE\n\nfix X\n"),
            "REVISE",
        )
        self.assertEqual(turns.parse_verdict("verdict: done\n"), "DONE")
        self.assertEqual(turns.parse_verdict("VERDICT: ESCALATE\n"), "ESCALATE")
        self.assertEqual(turns.parse_verdict("verdict: escalate\n"), "ESCALATE")
        self.assertIsNone(turns.parse_verdict("no verdict here"))
        self.assertTrue(turns.parse_plan_stop("STATUS: DONE\nreason: ok\n"))
        self.assertTrue(turns.parse_plan_stop("PLAN: STOP\n"))
        self.assertFalse(turns.parse_plan_stop("STATUS: CONTINUE\n"))
        self.assertFalse(turns.parse_plan_stop("STATUS: ESCALATE\n"))
        self.assertTrue(turns.parse_plan_escalate("STATUS: ESCALATE\nreason: pick A/B\n"))
        self.assertTrue(turns.parse_plan_escalate("PLAN: escalate\n"))
        self.assertFalse(turns.parse_plan_escalate("STATUS: CONTINUE\n"))

    def test_resolve_review_verdict(self) -> None:
        explicit, notes = turns.resolve_review_verdict(
            "VERDICT: ESCALATE\nIMPROVE: none\n"
        )
        self.assertEqual(explicit, "ESCALATE")
        self.assertEqual(notes, [])

        owner_ask, owner_notes = turns.resolve_review_verdict(
            "Looks stuck.\nNeeds owner decision between approach A and B.\n"
        )
        self.assertEqual(owner_ask, "ESCALATE")
        self.assertTrue(any("ESCALATE" in n for n in owner_notes))

        needs_decision, nd_notes = turns.resolve_review_verdict(
            "STATUS: Needs decision\nWhich approach should the owner pick?\n"
        )
        self.assertEqual(needs_decision, "ESCALATE")
        self.assertTrue(nd_notes)

        # Missing VERDICT with neutral text falls back to APPROVE (legacy safe default).
        neutral, neutral_notes = turns.resolve_review_verdict(
            "Looks fine overall.\nIMPROVE: none\nEFFECT: yes - small polish\n"
        )
        self.assertEqual(neutral, "APPROVE")
        self.assertTrue(any("APPROVE" in n for n in neutral_notes))

        empty, empty_notes = turns.resolve_review_verdict(None)
        self.assertEqual(empty, "APPROVE")
        self.assertTrue(any("APPROVE" in n for n in empty_notes))

    def test_write_needs_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            path = turns.write_needs_owner(
                notes,
                goal="harden turns",
                turn=2,
                why="Reviewer asked for owner decision on A vs B.",
            )
            self.assertEqual(path, notes / "NEEDS_OWNER.md")
            text = path.read_text(encoding="utf-8")
            self.assertIn("## Goal", text)
            self.assertIn("harden turns", text)
            self.assertIn("## Turn", text)
            self.assertIn("2", text)
            self.assertIn("## Why", text)
            self.assertIn("owner decision", text)
            self.assertIn("## How to resume", text)
            self.assertIn("--resume", text)
            self.assertIn("OWNER_REPLY.md", text)
            self.assertIn("--owner-reply", text)

    def test_should_write_complete_and_write_complete_md(self) -> None:
        self.assertTrue(
            turns.should_write_complete(final_verdict="DONE")
        )
        self.assertTrue(
            turns.should_write_complete(plan_status="DONE")
        )
        self.assertFalse(
            turns.should_write_complete(final_verdict="STOP")
        )
        self.assertTrue(
            turns.should_write_complete(
                final_verdict="STOP",
                evidence_texts=("VERDICT: STOP\nEFFECT: goal met\n",),
            )
        )
        self.assertFalse(
            turns.should_write_complete(final_verdict="ESCALATE")
        )
        self.assertFalse(turns.should_write_complete())
        self.assertEqual(turns.parse_plan_stop_kind("STATUS: DONE\n"), "DONE")
        self.assertEqual(turns.parse_plan_stop_kind("PLAN: STOP\n"), "STOP")
        self.assertIsNone(turns.parse_plan_stop_kind("STATUS: CONTINUE\n"))

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            report = Path(tmp) / "自己改善20260101120000.md"
            path = turns.write_complete_md(
                notes,
                goal="ship complete marker",
                turn=2,
                stop_reason="reviewer verdict DONE at turn 2",
                final_verdict="DONE",
                summary_path=notes / "SUMMARY.md",
                report_path=report,
            )
            self.assertEqual(path, notes / "COMPLETE.md")
            text = path.read_text(encoding="utf-8")
            self.assertIn("## Goal", text)
            self.assertIn("ship complete marker", text)
            self.assertIn("## Outcome", text)
            self.assertIn("DONE", text)
            self.assertIn("## Artifacts", text)
            self.assertIn("SUMMARY.md", text)
            self.assertIn(str(report), text)
            self.assertIn("## Next steps", text)

    def test_resolve_notify_webhook_cli_over_env(self) -> None:
        args = turns.build_parser().parse_args(
            ["--goal", "g", "--coder", "c", "--notify-webhook", "https://cli.example/hook"]
        )
        with mock.patch.dict(
            os.environ,
            {turns.NOTIFY_WEBHOOK_ENV: "https://env.example/hook"},
            clear=False,
        ):
            self.assertEqual(
                turns.resolve_notify_webhook(args),
                "https://cli.example/hook",
            )
        args_env = turns.build_parser().parse_args(
            ["--goal", "g", "--coder", "c"]
        )
        with mock.patch.dict(
            os.environ,
            {turns.NOTIFY_WEBHOOK_ENV: "https://env.example/hook"},
            clear=False,
        ):
            self.assertEqual(
                turns.resolve_notify_webhook(args_env),
                "https://env.example/hook",
            )
        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure env key absent
            os.environ.pop(turns.NOTIFY_WEBHOOK_ENV, None)
            self.assertIsNone(turns.resolve_notify_webhook(args_env))

    def test_notify_webhook_events_and_failures(self) -> None:
        import io
        from contextlib import redirect_stdout
        import urllib.error

        def _run_done(notes: Path, work: Path, extra: list[str]) -> tuple[int, str]:
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: DONE\nIMPROVE: none\nEFFECT: yes - overall goal is met\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "hook-complete",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                        *extra,
                    ]
                )
            return code, buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            captured: list[object] = []

            def fake_urlopen(req: object, timeout: float = 0):
                captured.append((req, timeout))
                return mock.MagicMock(
                    __enter__=mock.Mock(return_value=mock.Mock()),
                    __exit__=mock.Mock(return_value=False),
                )

            with mock.patch.object(
                turns.urllib.request, "urlopen", side_effect=fake_urlopen
            ):
                code, _out = _run_done(
                    notes,
                    work,
                    ["--notify-webhook", "https://hooks.example/turns"],
                )
            self.assertEqual(code, 0)
            self.assertEqual(len(captured), 1)
            req, timeout = captured[0]
            self.assertEqual(timeout, turns.NOTIFY_WEBHOOK_TIMEOUT_S)
            self.assertEqual(req.full_url, "https://hooks.example/turns")
            body = json.loads(req.data.decode("utf-8"))
            self.assertEqual(body["event"], "complete")
            self.assertEqual(body["goal"], "hook-complete")
            self.assertEqual(body["verdict"], "DONE")
            self.assertEqual(body["notes_dir"], str(notes.resolve()))
            self.assertEqual(body["workdir"], str(work.resolve()))
            meta = turns.load_run_meta(notes)
            self.assertEqual(
                meta.get("notify_webhook"), "https://hooks.example/turns"
            )

        # No URL → urlopen not called
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            with mock.patch.object(
                turns.urllib.request, "urlopen", side_effect=AssertionError("no call")
            ):
                code, _out = _run_done(notes, work, [])
            self.assertEqual(code, 0)

        # ESCALATE → event=escalate
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: ESCALATE\nIMPROVE: none\nEFFECT: blocked\n",
                encoding="utf-8",
            )
            captured = []

            def fake_urlopen2(req: object, timeout: float = 0):
                captured.append(req)
                return mock.MagicMock(
                    __enter__=mock.Mock(return_value=mock.Mock()),
                    __exit__=mock.Mock(return_value=False),
                )

            with mock.patch.object(
                turns.urllib.request, "urlopen", side_effect=fake_urlopen2
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = turns.main(
                        [
                            "--from-here",
                            "--turns",
                            "1",
                            "--goal",
                            "hook-escalate",
                            "--notes-dir",
                            str(notes),
                            "--workdir",
                            str(work),
                            "--notify-webhook",
                            "https://hooks.example/esc",
                            "--dry-run",
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertEqual(len(captured), 1)
            body = json.loads(captured[0].data.decode("utf-8"))
            self.assertEqual(body["event"], "escalate")
            self.assertEqual(body["verdict"], "ESCALATE")

        # stall → event=stop (NEEDS_OWNER still written)
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_PLAN.md").write_text(
                "STATUS: CONTINUE\nTASK: add tests\nDONE_WHEN: green\n"
                "OUT_OF_SCOPE: none\n",
                encoding="utf-8",
            )
            (notes / "TURN1_RESULT.md").write_text(
                "DONE: first\nVERIFIED: python3 -m unittest -q\nFILES: none\n",
                encoding="utf-8",
            )
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            (notes / "TURN2_PLAN.md").write_text(
                "STATUS: CONTINUE\nTASK:  Add tests.\nDONE_WHEN: green\n"
                "OUT_OF_SCOPE: none\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes, goal="hook-stall", workdir=work, max_turns=5
            )
            captured = []

            def fake_urlopen3(req: object, timeout: float = 0):
                captured.append(req)
                return mock.MagicMock(
                    __enter__=mock.Mock(return_value=mock.Mock()),
                    __exit__=mock.Mock(return_value=False),
                )

            with mock.patch.object(
                turns.urllib.request, "urlopen", side_effect=fake_urlopen3
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = turns.main(
                        [
                            "--from-here",
                            "--resume",
                            "--notes-dir",
                            str(notes),
                            "--workdir",
                            str(work),
                            "--turns",
                            "1",
                            "--notify-webhook",
                            "https://hooks.example/stall",
                            "--dry-run",
                        ]
                    )
            self.assertEqual(code, 0)
            self.assertTrue((notes / "NEEDS_OWNER.md").exists())
            self.assertEqual(len(captured), 1)
            body = json.loads(captured[0].data.decode("utf-8"))
            self.assertEqual(body["event"], "stop")
            self.assertIn("repeated TASK", body.get("stop_reason") or "")

        # urlopen failure → warning, exit 0
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            with mock.patch.object(
                turns.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("down"),
            ):
                code, out = _run_done(
                    notes,
                    work,
                    ["--notify-webhook", "https://hooks.example/fail"],
                )
            self.assertEqual(code, 0)
            self.assertIn("warning: notify webhook failed", out)
            self.assertTrue((notes / "COMPLETE.md").exists())

    def test_notify_webhook_persist_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            notes.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="hook-resume",
                workdir=Path(tmp),
                max_turns=5,
                notify_webhook="https://hooks.example/saved",
            )
            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop(turns.NOTIFY_WEBHOOK_ENV, None)
                turns.prepare_run_context(args)
            self.assertEqual(
                args.notify_webhook, "https://hooks.example/saved"
            )

    def test_dry_run_verdict_done_writes_complete(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: DONE\n"
                "IMPROVE: none\n"
                "EFFECT: yes - overall goal is met\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "complete-via-done",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            complete = notes / "COMPLETE.md"
            self.assertTrue(complete.is_file())
            text = complete.read_text(encoding="utf-8")
            self.assertIn("complete-via-done", text)
            self.assertIn("SUMMARY.md", text)
            self.assertIn("DONE", text)
            self.assertFalse((notes / "NEEDS_OWNER.md").exists())

    def test_dry_run_planner_done_writes_complete(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_PLAN.md").write_text(
                "STATUS: DONE\n"
                "TASK: none\n"
                "DONE_WHEN: n/a\n"
                "OUT_OF_SCOPE: none\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "planner-already-done",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertNotIn("======== TURN 1/1: fix ========", out)
            complete = notes / "COMPLETE.md"
            self.assertTrue(complete.is_file())
            self.assertIn(
                "planner-already-done",
                complete.read_text(encoding="utf-8"),
            )
            self.assertFalse((notes / "NEEDS_OWNER.md").exists())

    def test_dry_run_escalate_no_complete(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: ESCALATE\n"
                "IMPROVE: none\n"
                "EFFECT: blocked - needs owner decision\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "escalate-no-complete",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertFalse((notes / "COMPLETE.md").exists())
            needs = notes / "NEEDS_OWNER.md"
            self.assertTrue(needs.is_file())
            self.assertIn("escalate-no-complete", needs.read_text(encoding="utf-8"))

    def test_dry_run_stop_goal_met_writes_complete(self) -> None:
        """VERDICT: STOP writes COMPLETE only with explicit goal-met language."""
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: STOP\n"
                "IMPROVE: none\n"
                "EFFECT: goal met — overall goal is complete\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "stop-goal-met",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue((notes / "COMPLETE.md").is_file())

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: STOP\n"
                "IMPROVE: none\n"
                "EFFECT: pause for now; goal not finished\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "stop-without-goal-met",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertFalse((notes / "COMPLETE.md").exists())
            self.assertFalse((notes / "NEEDS_OWNER.md").exists())

    def test_escalate_stop_writes_needs_owner_without_apply(self) -> None:
        """Pure-function path: resolve ESCALATE + write NEEDS_OWNER like run_turns."""
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            review = (
                "# Turn 1 review\n\n"
                "VERDICT: ESCALATE\n"
                "IMPROVE: none\n"
                "EFFECT: blocked - needs human judgment on API shape\n"
            )
            verdict, vnotes = turns.resolve_review_verdict(review)
            self.assertEqual(verdict, "ESCALATE")
            self.assertEqual(vnotes, [])
            # Same as DONE/STOP: no APPLY; stop and leave owner note.
            self.assertNotEqual(verdict, "REVISE")
            turns.write_needs_owner(
                notes,
                goal="choose API",
                turn=1,
                why=turns.escalate_why_excerpt(review),
            )
            needs = (notes / "NEEDS_OWNER.md").read_text(encoding="utf-8")
            self.assertIn("choose API", needs)
            self.assertIn("human judgment", needs.lower())
            self.assertIn("1", needs)

            plan_escalate = "STATUS: ESCALATE\nTASK: none\nreason: pick storage backend\n"
            self.assertTrue(turns.parse_plan_escalate(plan_escalate))
            turns.write_needs_owner(
                notes,
                goal="choose API",
                turn=3,
                why=turns.escalate_why_excerpt(plan_escalate),
            )
            needs3 = (notes / "NEEDS_OWNER.md").read_text(encoding="utf-8")
            self.assertIn("## Turn\n\n3\n", needs3)
            self.assertIn("storage backend", needs3)
            self.assertIn("--resume", needs3)
            self.assertNotIn("(coming)", needs3)

    def test_resolve_resume_start_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)

            def write(name: str, body: str) -> None:
                (notes / name).write_text(body, encoding="utf-8")

            # Empty notes → start at 1
            self.assertEqual(turns.resolve_resume_start_turn(notes), 1)

            write(
                "TURN1_REVIEW.md",
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: yes\n",
            )
            self.assertEqual(turns.resolve_resume_start_turn(notes), 2)

            write(
                "TURN2_REVIEW.md",
                "VERDICT: ESCALATE\nIMPROVE: none\nEFFECT: needs owner\n",
            )
            self.assertEqual(turns.resolve_resume_start_turn(notes), 3)

            # Planner ESCALATE before fix: plan ready, review skeleton → retry n
            write(
                "TURN3_PLAN.md",
                "STATUS: ESCALATE\nTASK: none\nreason: pick A or B\n",
            )
            write("TURN3_RESULT.md", "# Turn 3 result\n\n_(pending)_\n")
            write("TURN3_REVIEW.md", "# Turn 3 review\n\n_(pending)_\n")
            self.assertEqual(turns.resolve_resume_start_turn(notes), 3)

            # Clear turn 3 incomplete; result-without-review mid-crash → resume 4
            for suffix in ("PLAN", "RESULT", "REVIEW"):
                (notes / f"TURN3_{suffix}.md").unlink(missing_ok=True)
            write(
                "TURN3_REVIEW.md",
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
            )
            write(
                "TURN4_PLAN.md",
                "STATUS: CONTINUE\nTASK: do Y\nDONE_WHEN: tests\n",
            )
            write(
                "TURN4_RESULT.md",
                "DONE: did Y\nVERIFIED: unit tests\nFILES: a.py\n",
            )
            # no TURN4_REVIEW
            self.assertEqual(turns.resolve_resume_start_turn(notes), 4)

    def test_resolve_resume_start_turn_past_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            (notes / f"TURN{turns.MAX_TURNS}_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: done\n",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError) as ctx:
                turns.resolve_resume_start_turn(notes)
            self.assertIn("MAX_TURNS", str(ctx.exception))

    def test_resume_arg_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-notes"
            code = turns.main(
                [
                    "--resume",
                    "--notes-dir",
                    str(missing),
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 2)

            empty = Path(tmp) / "empty-notes"
            empty.mkdir()
            code = turns.main(
                [
                    "--resume",
                    "--notes-dir",
                    str(empty),
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 2)

            code = turns.main(
                [
                    "--resume",
                    "--coder",
                    "c",
                    "--dry-run",
                    "--goal",
                    "x",
                ]
            )
            self.assertEqual(code, 2)

    def test_resume_loads_goal_from_run_json_and_needs_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            notes.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="from-run-json",
                workdir=Path(tmp),
                max_turns=5,
            )
            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            workdir, notes_dir, _c, start, end = turns.prepare_run_context(args)
            self.assertEqual(args.goal, "from-run-json")
            self.assertEqual(notes_dir, notes.resolve())
            self.assertEqual(start, 2)
            self.assertEqual(end, 2)
            self.assertEqual(workdir, Path(tmp).resolve())

            # Without run.json, fall back to NEEDS_OWNER.md ## Goal
            (notes / turns.RUN_META_NAME).unlink()
            turns.write_needs_owner(
                notes,
                goal="from-needs-owner",
                turn=1,
                why="pick approach",
            )
            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args)
            self.assertEqual(args.goal, "from-needs-owner")

    def test_dry_run_resume_starts_at_next_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: ESCALATE\nIMPROVE: none\nEFFECT: owner needed\n",
                encoding="utf-8",
            )
            (notes / "TURN1_PLAN.md").write_text(
                "STATUS: CONTINUE\nTASK: first\nDONE_WHEN: ok\n",
                encoding="utf-8",
            )
            (notes / "TURN1_RESULT.md").write_text(
                "DONE: first\nVERIFIED: check\nFILES: none\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="resume-demo-goal",
                workdir=work,
                max_turns=5,
            )
            turns.write_needs_owner(
                notes,
                goal="resume-demo-goal",
                turn=1,
                why="owner needed",
            )
            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--resume",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--turns",
                        "1",
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("======== TURN 2/2: instruct ========", out)
            self.assertIn("resume: starting at turn 2", out)
            self.assertIn("resume-demo-goal", out)
            self.assertTrue((notes / "TURN2_PLAN.md").exists())
            self.assertTrue((notes / "SUMMARY.md").exists())
            # Prior turn artifacts kept; NEEDS_OWNER archived on resume start
            self.assertTrue((notes / "TURN1_REVIEW.md").exists())
            self.assertFalse((notes / "NEEDS_OWNER.md").exists())
            self.assertTrue((notes / "NEEDS_OWNER.prev.md").exists())

    def test_owner_reply_cli_wins_over_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            (notes / turns.OWNER_REPLY_NAME).write_text(
                "from-file\n", encoding="utf-8"
            )
            resolved = turns.load_owner_reply_for_resume(
                notes, cli_owner_reply="from-cli"
            )
            self.assertEqual(resolved, "from-cli")
            file_only = turns.load_owner_reply_for_resume(
                notes, cli_owner_reply=None
            )
            self.assertEqual(file_only, "from-file")
            whitespace_cli = turns.load_owner_reply_for_resume(
                notes, cli_owner_reply="   \n"
            )
            self.assertEqual(whitespace_cli, "from-file")
            empty_notes = Path(tmp) / "empty"
            empty_notes.mkdir()
            self.assertIsNone(
                turns.load_owner_reply_for_resume(empty_notes, cli_owner_reply=None)
            )

    def test_owner_reply_inject_once_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: ESCALATE\nIMPROVE: none\nEFFECT: owner needed\n",
                encoding="utf-8",
            )
            (notes / "TURN1_PLAN.md").write_text(
                "STATUS: CONTINUE\nTASK: first\nDONE_WHEN: ok\n",
                encoding="utf-8",
            )
            (notes / "TURN1_RESULT.md").write_text(
                "DONE: first\nVERIFIED: check\nFILES: none\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="owner-reply-goal",
                workdir=work,
                max_turns=5,
            )
            (notes / turns.OWNER_REPLY_NAME).write_text(
                "Prefer approach B; skip A.\n", encoding="utf-8"
            )
            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--resume",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--turns",
                        "1",
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn(turns.OWNER_REPLY_HEADER, out)
            self.assertIn("Prefer approach B; skip A.", out)
            self.assertIn("======== TURN 2/2: instruct ========", out)
            self.assertIn("======== TURN 2/2: fix ========", out)
            # Consumed: hash in run.json and/or file renamed
            meta = turns.load_run_meta(notes)
            self.assertEqual(
                meta.get(turns.OWNER_REPLY_META_KEY),
                turns.owner_reply_digest("Prefer approach B; skip A."),
            )
            self.assertFalse((notes / turns.OWNER_REPLY_NAME).exists())
            self.assertTrue((notes / turns.OWNER_REPLY_CONSUMED_NAME).exists())

            # Second resume with same reply material: no re-injection
            (notes / turns.OWNER_REPLY_NAME).write_text(
                "Prefer approach B; skip A.\n", encoding="utf-8"
            )
            # Dry-run wrote TURN2 review APPROVE; remove so resume stays at 2
            for suffix in ("PLAN", "RESULT", "REVIEW"):
                (notes / f"TURN2_{suffix}.md").unlink(missing_ok=True)
            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                code2 = turns.main(
                    [
                        "--from-here",
                        "--resume",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--turns",
                        "1",
                        "--dry-run",
                    ]
                )
            out2 = buf2.getvalue()
            self.assertEqual(code2, 0)
            self.assertNotIn(turns.OWNER_REPLY_HEADER, out2)
            self.assertNotIn("Prefer approach B; skip A.", out2)

    def test_owner_reply_cli_over_file_on_resume_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes, goal="cli-wins", workdir=work, max_turns=5
            )
            (notes / turns.OWNER_REPLY_NAME).write_text(
                "file-text\n", encoding="utf-8"
            )
            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--resume",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--turns",
                        "1",
                        "--owner-reply",
                        "cli-text-wins",
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("cli-text-wins", out)
            self.assertNotIn("file-text", out)
            meta = turns.load_run_meta(notes)
            self.assertEqual(
                meta.get(turns.OWNER_REPLY_META_KEY),
                turns.owner_reply_digest("cli-text-wins"),
            )

    def test_owner_reply_rejected_without_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = turns.main(
                [
                    "--coder",
                    "c",
                    "--reviewer",
                    "r",
                    "--goal",
                    "x",
                    "--notes-dir",
                    str(Path(tmp) / "notes"),
                    "--owner-reply",
                    "should fail",
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 2)

    def test_owner_reply_helpers_digest_and_skip(self) -> None:
        text = "use option C"
        digest = turns.owner_reply_digest(text)
        self.assertEqual(digest, turns.owner_reply_digest("  use option C\n"))
        self.assertTrue(turns.should_inject_owner_reply({}, text))
        self.assertFalse(
            turns.should_inject_owner_reply({turns.OWNER_REPLY_META_KEY: digest}, text)
        )
        self.assertFalse(turns.should_inject_owner_reply({}, None))
        self.assertFalse(turns.should_inject_owner_reply({}, "  \n"))
        prefix = turns.format_owner_reply_prefix(text)
        self.assertTrue(prefix.startswith(turns.OWNER_REPLY_HEADER))
        self.assertIn(text, prefix)
        self.assertTrue(prefix.endswith("\n\n"))

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
                "--self",
                "--goal",
                "g",
                "--dry-run",
            ]
        )
        with mock.patch.object(turns, "resolve_from_here", return_value="me"):
            planner, coder, reviewer = turns.resolve_roles(args)
        self.assertEqual((planner, coder, reviewer), ("me", "me", "me"))

    def test_wants_nested_pair_default_from_here(self) -> None:
        nested = turns.build_parser().parse_args(
            ["--from-here", "--goal", "g", "--dry-run"]
        )
        self.assertTrue(turns.wants_nested_pair(nested))
        self_mode = turns.build_parser().parse_args(
            ["--from-here", "--self", "--goal", "g", "--dry-run"]
        )
        self.assertFalse(turns.wants_nested_pair(self_mode))

    def test_default_constraints_path_exists(self) -> None:
        path = turns.default_constraints_path()
        self.assertTrue(path.is_file(), msg=str(path))
        self.assertEqual(path.name, turns.DEFAULT_CONSTRAINTS_FILENAME)
        text = path.read_text(encoding="utf-8")
        self.assertIn("Write boundaries", text)
        self.assertIn("Do **not** `git commit`", text)
        self.assertIn("src/", text)

    def test_resolve_effective_constraints_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            custom = Path(tmp) / "custom.md"
            custom.write_text("# custom\n", encoding="utf-8")

            # Always-on default when neither flag set
            args = turns.build_parser().parse_args(
                ["--from-here", "--goal", "g", "--dry-run"]
            )
            path, use_default = turns.resolve_effective_constraints(args)
            self.assertTrue(use_default)
            self.assertEqual(path, turns.default_constraints_path())

            # --no-default-constraints opts out
            args_off = turns.build_parser().parse_args(
                [
                    "--from-here",
                    "--goal",
                    "g",
                    "--no-default-constraints",
                    "--dry-run",
                ]
            )
            path_off, use_off = turns.resolve_effective_constraints(args_off)
            self.assertIsNone(path_off)
            self.assertFalse(use_off)

            # Explicit --constraints replaces default
            args_custom = turns.build_parser().parse_args(
                [
                    "--from-here",
                    "--goal",
                    "g",
                    "--constraints",
                    str(custom),
                    "--dry-run",
                ]
            )
            path_c, use_c = turns.resolve_effective_constraints(args_custom)
            self.assertEqual(path_c, custom.resolve())
            self.assertFalse(use_c)

            # --constraints wins over --no-default-constraints
            args_both = turns.build_parser().parse_args(
                [
                    "--from-here",
                    "--goal",
                    "g",
                    "--constraints",
                    str(custom),
                    "--no-default-constraints",
                    "--dry-run",
                ]
            )
            path_b, use_b = turns.resolve_effective_constraints(args_both)
            self.assertEqual(path_b, custom.resolve())
            self.assertFalse(use_b)

    def test_dry_run_prompts_mention_default_constraints(self) -> None:
        import io
        from contextlib import redirect_stdout

        default_path = str(turns.default_constraints_path())
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "constraints-default",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn(default_path, out)
            self.assertIn("Read and follow", out)
            meta = turns.load_run_meta(notes)
            self.assertTrue(meta.get("use_default_constraints"))
            self.assertEqual(meta.get("constraints"), default_path)

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "constraints-none",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--no-default-constraints",
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertNotIn(default_path, out)
            self.assertIn("Keep each turn small and verifiable", out)
            meta = turns.load_run_meta(notes)
            self.assertFalse(meta.get("use_default_constraints"))
            self.assertNotIn("constraints", meta)

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            work = Path(tmp) / "work"
            notes.mkdir()
            work.mkdir()
            custom = Path(tmp) / "my-constraints.md"
            custom.write_text("# mine\n", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = turns.main(
                    [
                        "--from-here",
                        "--turns",
                        "1",
                        "--goal",
                        "constraints-custom",
                        "--notes-dir",
                        str(notes),
                        "--workdir",
                        str(work),
                        "--constraints",
                        str(custom),
                        "--dry-run",
                    ]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn(str(custom.resolve()), out)
            self.assertNotIn(default_path, out)
            meta = turns.load_run_meta(notes)
            self.assertFalse(meta.get("use_default_constraints"))
            self.assertEqual(meta.get("constraints"), str(custom.resolve()))

    def test_constraints_persist_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            notes.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            default_path = turns.default_constraints_path()
            turns.write_run_meta(
                notes,
                goal="c-resume",
                workdir=Path(tmp),
                max_turns=5,
                constraints=default_path,
                use_default_constraints=True,
            )
            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            _workdir, _notes, constraints, _s, _e = turns.prepare_run_context(
                args
            )
            self.assertTrue(args.use_default_constraints)
            self.assertEqual(constraints, default_path)

            # Opt-out persisted
            turns.write_run_meta(
                notes,
                goal="c-resume",
                workdir=Path(tmp),
                max_turns=5,
                constraints=None,
                use_default_constraints=False,
            )
            args2 = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            _w2, _n2, c2, _s2, _e2 = turns.prepare_run_context(args2)
            self.assertFalse(args2.use_default_constraints)
            self.assertIsNone(c2)

            # Custom path persisted
            custom = Path(tmp) / "cust.md"
            custom.write_text("x\n", encoding="utf-8")
            turns.write_run_meta(
                notes,
                goal="c-resume",
                workdir=Path(tmp),
                max_turns=5,
                constraints=custom,
                use_default_constraints=False,
            )
            args3 = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            _w3, _n3, c3, _s3, _e3 = turns.prepare_run_context(args3)
            self.assertFalse(args3.use_default_constraints)
            self.assertEqual(c3, custom.resolve())

    def test_default_agent_args_include_yolo(self) -> None:
        self.assertEqual(turns.DEFAULT_AGENT_KIND, "cursor")
        self.assertEqual(turns.DEFAULT_AGENT_ARGS, ["--yolo"])
        args = turns.build_parser().parse_args(
            ["--from-here", "--goal", "g", "--dry-run"]
        )
        self.assertIsNone(args.agent_args)
        self.assertIsNone(args.planner_args)
        self.assertIsNone(args.coder_args)
        self.assertIsNone(args.reviewer_args)

    def test_resolve_role_agent_args_fallback_and_replace(self) -> None:
        # Default → all roles get DEFAULT_AGENT_ARGS
        args = turns.build_parser().parse_args(
            ["--from-here", "--goal", "g", "--dry-run"]
        )
        self.assertEqual(
            turns.resolve_role_agent_args(args),
            (["--yolo"], ["--yolo"], ["--yolo"]),
        )

        # Shared --agent-arg only (use = form so values may start with -)
        args_shared = turns.build_parser().parse_args(
            [
                "--from-here",
                "--goal",
                "g",
                "--agent-arg=--trust",
                "--dry-run",
            ]
        )
        self.assertEqual(
            turns.resolve_role_agent_args(args_shared),
            (["--trust"], ["--trust"], ["--trust"]),
        )

        # --coder-arg replaces shared for coder only (no merge)
        args_mix = turns.build_parser().parse_args(
            [
                "--from-here",
                "--goal",
                "g",
                "--agent-arg=--yolo",
                "--coder-arg=--trust",
                "--reviewer-arg=--model",
                "--reviewer-arg",
                "composer-2.5",
                "--dry-run",
            ]
        )
        planner, coder, reviewer = turns.resolve_role_agent_args(args_mix)
        self.assertEqual(planner, ["--yolo"])
        self.assertEqual(coder, ["--trust"])
        self.assertEqual(reviewer, ["--model", "composer-2.5"])

        # planner-arg only; others fall back to default
        args_planner = turns.build_parser().parse_args(
            [
                "--from-here",
                "--goal",
                "g",
                "--planner-arg=--verbose",
                "--dry-run",
            ]
        )
        self.assertEqual(
            turns.resolve_role_agent_args(args_planner),
            (["--verbose"], ["--yolo"], ["--yolo"]),
        )

    def test_resolve_roles_from_here_self_with_separate_reviewer(self) -> None:
        args = turns.build_parser().parse_args(
            [
                "--from-here",
                "--self",
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

    def test_session_cli_env_unsets_parent_ids(self) -> None:
        env = turns.session_cli_env("turns-demo")
        self.assertEqual(env["HERDR_SESSION"], "turns-demo")
        self.assertIsNone(env["HERDR_SOCKET_PATH"])
        self.assertIsNone(env["HERDR_PANE_ID"])

    def test_herdr_run_allows_empty_quiet_success(self) -> None:
        fake = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(turns.subprocess, "run", return_value=fake):
            self.assertIsNone(
                turns.herdr_run("herdr", ["pane", "run", "w1:p1", "true"], allow_empty=True)
            )
            with self.assertRaises(RuntimeError):
                turns.herdr_run("herdr", ["pane", "list"], allow_empty=False)

    def test_nested_launch_command_avoids_parent_session_flag(self) -> None:
        cmd = turns.nested_herdr_launch_command(
            "/bin/herdr",
            session="turns-demo",
            config_path=Path("/tmp/cfg.toml"),
        )
        self.assertIn("HERDR_SESSION=turns-demo", cmd)
        self.assertIn("HERDR_CONFIG_PATH=/tmp/cfg.toml", cmd)
        self.assertIn("/bin/herdr", cmd)
        # Parent `herdr pane run ... --session` would target a missing socket.
        self.assertNotIn("--session", cmd)
        # Must be one pane-run COMMAND (not bash -lc word-split).
        self.assertFalse(cmd.startswith("bash "))

    def test_nested_config_disables_onboarding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = turns.write_nested_config(Path(tmp))
            text = path.read_text(encoding="utf-8")
        self.assertIn("onboarding = false", text)
        self.assertIn("allow_nested = true", text)

    def test_launcher_summary_prompt_includes_report_paths(self) -> None:
        text = turns.launcher_summary_prompt(
            summary="# 自己改善レポート\n\nok\n",
            report_path=Path("/work/自己改善20261015120000.md"),
            notes_dir=Path("/work/herdr-turns-notes"),
        )
        self.assertIn("全ターンサマリー", text)
        self.assertIn("自己改善20261015120000.md", text)
        self.assertIn("SUMMARY.md", text)
        self.assertIn("# 自己改善レポート", text)

    def test_assign_nested_2x2_panes_layout(self) -> None:
        roles = turns.assign_nested_2x2_panes("p1", "p2", "p3", "p4")
        self.assertEqual(
            roles,
            {
                "director": "p1",
                "coder": "p2",
                "reviewer": "p3",
                "spare": "p4",
            },
        )

    def test_spawn_nested_builds_2x2_and_starts_director_team(self) -> None:
        calls: list[tuple[list[str], dict | None]] = []
        split_ids = iter(["outer", "coder-pane", "reviewer-pane", "spare-pane"])

        def fake_herdr_json(herdr: str, argv: list[str], env=None) -> dict:
            del herdr
            calls.append((list(argv), env))
            if argv[:2] == ["pane", "split"]:
                pane_id = next(split_ids)
                return {"result": {"pane": {"pane_id": pane_id}}}
            if argv[:2] == ["agent", "start"]:
                return {"ok": True}
            raise AssertionError(f"unexpected herdr_json {argv}")

        def fake_herdr_run(herdr: str, argv: list[str], *, env=None, allow_empty=False):
            del herdr, allow_empty
            calls.append((list(argv), env))
            return None

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            (notes / "launcher-pane").write_text("parent:p0\n", encoding="utf-8")
            (notes / "launcher-herdr-env").write_text("1\n", encoding="utf-8")
            with (
                mock.patch.object(turns, "herdr_json", side_effect=fake_herdr_json),
                mock.patch.object(turns, "herdr_run", side_effect=fake_herdr_run),
                mock.patch.object(
                    turns,
                    "wait_for_session_panes",
                    return_value=[{"pane_id": "root-pane"}],
                ),
                mock.patch.dict(os.environ, {"HERDR_ENV": "1"}, clear=False),
            ):
                nested = turns.spawn_nested_coder_reviewer(
                    "herdr",
                    workdir=Path(tmp),
                    kind="cursor",
                    planner_args=["--yolo"],
                    coder_args=["--yolo"],
                    reviewer_args=["--yolo"],
                    parent_pane_id="parent:p0",
                    notes_dir=notes,
                )

        self.assertEqual(nested.director, "director")
        self.assertEqual(nested.planner, "director")
        self.assertEqual(nested.coder, "coder")
        self.assertEqual(nested.reviewer, "reviewer")
        self.assertEqual(nested.spare_pane_id, "spare-pane")
        self.assertEqual(nested.outer_pane_id, "outer")

        agent_starts = [
            argv for argv, _env in calls if argv[:2] == ["agent", "start"]
        ]
        self.assertEqual(
            [argv[2] for argv in agent_starts],
            ["director", "coder", "reviewer"],
        )
        self.assertEqual(
            [argv[argv.index("--pane") + 1] for argv in agent_starts],
            ["root-pane", "coder-pane", "reviewer-pane"],
        )
        for argv in agent_starts:
            dash = argv.index("--")
            self.assertEqual(argv[dash + 1 :], ["--yolo"])
        renames = [
            argv for argv, _env in calls if argv[:2] == ["pane", "rename"]
        ]
        self.assertEqual(
            [(argv[2], argv[3]) for argv in renames],
            [
                ("root-pane", "director"),
                ("coder-pane", "coder"),
                ("reviewer-pane", "reviewer"),
                ("spare-pane", "spare"),
            ],
        )
        nested_splits = [
            argv
            for argv, env in calls
            if argv[:2] == ["pane", "split"] and env is not None
        ]
        self.assertEqual(
            [argv[argv.index("--direction") + 1] for argv in nested_splits],
            ["right", "down", "down"],
        )

    def test_spawn_nested_uses_distinct_per_role_args(self) -> None:
        calls: list[tuple[list[str], dict | None]] = []
        split_ids = iter(["outer", "coder-pane", "reviewer-pane", "spare-pane"])

        def fake_herdr_json(herdr: str, argv: list[str], env=None) -> dict:
            del herdr
            calls.append((list(argv), env))
            if argv[:2] == ["pane", "split"]:
                return {"result": {"pane": {"pane_id": next(split_ids)}}}
            if argv[:2] == ["agent", "start"]:
                return {"ok": True}
            if argv[:2] == ["pane", "rename"]:
                return {"ok": True}
            raise AssertionError(f"unexpected herdr_json {argv}")

        def fake_herdr_run(herdr: str, argv: list[str], *, env=None, allow_empty=False):
            del herdr, allow_empty
            calls.append((list(argv), env))
            return None

        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            (notes / "launcher-pane").write_text("parent:p0\n", encoding="utf-8")
            (notes / "launcher-herdr-env").write_text("1\n", encoding="utf-8")
            with (
                mock.patch.object(turns, "herdr_json", side_effect=fake_herdr_json),
                mock.patch.object(turns, "herdr_run", side_effect=fake_herdr_run),
                mock.patch.object(
                    turns,
                    "wait_for_session_panes",
                    return_value=[{"pane_id": "root-pane"}],
                ),
                mock.patch.dict(os.environ, {"HERDR_ENV": "1"}, clear=False),
            ):
                turns.spawn_nested_coder_reviewer(
                    "herdr",
                    workdir=Path(tmp),
                    kind="cursor",
                    planner_args=["--yolo"],
                    coder_args=["--trust"],
                    reviewer_args=["--model", "composer-2.5"],
                    parent_pane_id="parent:p0",
                    notes_dir=notes,
                )

        by_name = {
            argv[2]: argv
            for argv, _env in calls
            if argv[:2] == ["agent", "start"]
        }
        self.assertEqual(
            by_name["director"][by_name["director"].index("--") + 1 :],
            ["--yolo"],
        )
        self.assertEqual(
            by_name["coder"][by_name["coder"].index("--") + 1 :],
            ["--trust"],
        )
        self.assertEqual(
            by_name["reviewer"][by_name["reviewer"].index("--") + 1 :],
            ["--model", "composer-2.5"],
        )

        # Empty role list → no trailing "--"
        calls.clear()
        split_ids = iter(["outer", "coder-pane", "reviewer-pane", "spare-pane"])
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            (notes / "launcher-pane").write_text("parent:p0\n", encoding="utf-8")
            (notes / "launcher-herdr-env").write_text("1\n", encoding="utf-8")
            with (
                mock.patch.object(turns, "herdr_json", side_effect=fake_herdr_json),
                mock.patch.object(turns, "herdr_run", side_effect=fake_herdr_run),
                mock.patch.object(
                    turns,
                    "wait_for_session_panes",
                    return_value=[{"pane_id": "root-pane"}],
                ),
                mock.patch.dict(os.environ, {"HERDR_ENV": "1"}, clear=False),
            ):
                turns.spawn_nested_coder_reviewer(
                    "herdr",
                    workdir=Path(tmp),
                    kind="cursor",
                    planner_args=[],
                    coder_args=[],
                    reviewer_args=[],
                    parent_pane_id="parent:p0",
                    notes_dir=notes,
                )
        for argv, _env in calls:
            if argv[:2] == ["agent", "start"]:
                self.assertNotIn("--", argv)

    def test_role_agent_args_persist_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "notes"
            notes.mkdir()
            (notes / "TURN1_REVIEW.md").write_text(
                "VERDICT: APPROVE\nIMPROVE: none\nEFFECT: ok\n",
                encoding="utf-8",
            )
            turns.write_run_meta(
                notes,
                goal="role-args",
                workdir=Path(tmp),
                max_turns=5,
                planner_args=["--yolo"],
                coder_args=["--trust"],
                reviewer_args=["--model", "composer-2.5"],
            )
            meta = turns.load_run_meta(notes)
            self.assertEqual(meta.get("planner_args"), ["--yolo"])
            self.assertEqual(meta.get("coder_args"), ["--trust"])
            self.assertEqual(
                meta.get("reviewer_args"), ["--model", "composer-2.5"]
            )

            args = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args)
            self.assertEqual(args.planner_args, ["--yolo"])
            self.assertEqual(args.coder_args, ["--trust"])
            self.assertEqual(args.reviewer_args, ["--model", "composer-2.5"])
            self.assertEqual(
                turns.resolve_role_agent_args(args),
                (["--yolo"], ["--trust"], ["--model", "composer-2.5"]),
            )

            # CLI --coder-arg overrides meta coder only
            args2 = turns.build_parser().parse_args(
                [
                    "--resume",
                    "--notes-dir",
                    str(notes),
                    "--turns",
                    "1",
                    "--coder",
                    "c",
                    "--coder-arg=--fresh",
                    "--dry-run",
                ]
            )
            turns.prepare_run_context(args2)
            self.assertEqual(args2.coder_args, ["--fresh"])
            self.assertEqual(args2.planner_args, ["--yolo"])
            self.assertEqual(
                turns.resolve_role_agent_args(args2),
                (["--yolo"], ["--fresh"], ["--model", "composer-2.5"]),
            )

    def test_cleanup_nested_pair_stops_session_and_closes_pane(self) -> None:
        nested = turns.NestedPair(
            session="turns-demo",
            outer_pane_id="w2:p9",
            director="director",
            coder="coder",
            reviewer="reviewer",
            planner="director",
            spare_pane_id="w1:p4",
            config_path=Path("/tmp/cfg.toml"),
            work_root=Path("/tmp/work"),
        )
        calls: list[list[str]] = []

        def fake_herdr_json(_herdr: str, argv: list[str], env=None) -> dict:
            del env
            calls.append(list(argv))
            return {"ok": True}

        with mock.patch.object(turns, "herdr_json", side_effect=fake_herdr_json):
            turns.cleanup_nested_pair("herdr", nested)
        self.assertEqual(
            calls,
            [
                ["session", "stop", "turns-demo"],
                ["session", "delete", "turns-demo"],
                ["pane", "close", "w2:p9"],
            ],
        )

    def test_deliver_summary_to_caller_prompts_launcher_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            (notes / "launcher-pane").write_text("w2:p1\n", encoding="utf-8")
            prompted: list[tuple[str, str]] = []

            def fake_resolve(_herdr: str, pane_id: str) -> str:
                self.assertEqual(pane_id, "w2:p1")
                return "launcher-agent"

            def fake_prompt_and_wait(
                herdr: str,
                target: str,
                text: str,
                *,
                timeout_ms: int,
                poll_seconds: float = 1.0,
                env=None,
            ) -> None:
                del herdr, poll_seconds, env
                prompted.append((target, text))
                self.assertEqual(timeout_ms, 600_000)

            with (
                mock.patch.dict(os.environ, {"HERDR_PANE_ID": ""}, clear=False),
                mock.patch.object(
                    turns, "resolve_agent_in_pane", side_effect=fake_resolve
                ),
                mock.patch.object(
                    turns, "prompt_and_wait", side_effect=fake_prompt_and_wait
                ),
            ):
                turns.deliver_summary_to_caller(
                    "herdr",
                    "# summary body\n",
                    report_path=Path("/work/自己改善.md"),
                    notes_dir=notes,
                    timeout_ms=600_000,
                )
            self.assertEqual(len(prompted), 1)
            self.assertEqual(prompted[0][0], "launcher-agent")
            self.assertIn("# summary body", prompted[0][1])

    def test_persist_and_load_launcher_pane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp)
            with mock.patch.dict(os.environ, {"HERDR_PANE_ID": "w9:p9", "HERDR_ENV": "1"}):
                turns.persist_launcher_context(notes)
            self.assertEqual(
                (notes / "launcher-pane").read_text(encoding="utf-8").strip(),
                "w9:p9",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(turns.load_launcher_pane(notes), "w9:p9")

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

    def test_dry_run_from_here_nested_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / "herdr-turns-notes"
            code = turns.main(
                [
                    "--from-here",
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
