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

    def test_default_agent_args_include_yolo(self) -> None:
        self.assertEqual(turns.DEFAULT_AGENT_KIND, "cursor")
        self.assertEqual(turns.DEFAULT_AGENT_ARGS, ["--yolo"])
        args = turns.build_parser().parse_args(
            ["--from-here", "--goal", "g", "--dry-run"]
        )
        self.assertIsNone(args.agent_args)

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
                    agent_args=["--yolo"],
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
