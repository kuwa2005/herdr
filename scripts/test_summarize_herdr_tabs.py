#!/usr/bin/env python3
"""Unit tests for scripts/summarize_herdr_tabs.py helpers."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.summarize_herdr_tabs import (
    PaneSummary,
    WorkspaceSummary,
    automation_target_for_agent,
    automation_targets_from_agent_list_payload,
    compose_summary,
    herdr_json,
    load_automation_targets_by_pane,
    render_plain,
    screen_current_activity,
    screen_latest_user_query,
    transcript_latest_assistant_text,
    transcript_latest_user_query,
)


class SummarizeHerdrTabsTests(unittest.TestCase):
    def test_transcript_extracts_latest_user_query(self) -> None:
        rows = [
            {
                "role": "user",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "<user_query>最初の依頼</user_query>",
                        }
                    ]
                },
            },
            {
                "role": "assistant",
                "message": {"content": [{"type": "text", "text": "調査します。"}]},
            },
            {
                "role": "user",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "<timestamp>t</timestamp> <user_query> セキュリティ監査を実施して。 </user_query>",
                        }
                    ]
                },
            },
        ]
        self.assertEqual(
            transcript_latest_user_query(rows),
            "セキュリティ監査を実施して。",
        )
        self.assertEqual(transcript_latest_assistant_text(rows), "調査します。")

    def test_screen_prefers_user_block_before_assistant(self) -> None:
        screen = """
  以前の雑談

  issueを有効化して、upstreamで入ったコミットをissueに取り込んで。
  その後、コミットを取り込むかどうか判断してフラグを付けて


  Issues を有効化し、upstream 差分コミットを Issue
  化して取り込み判断用のラベルを付けます。まず状態を確認します。

    Used triage

  Finished Create GitHub issues for 35 commits

  fork 側のみのコミットは 6 件（i18n・README・バイナリ配布など）で、Issue 化はしていません。

  35件の upstream コミット用 Issue 作成は完了済みです。
"""
        query = screen_latest_user_query(screen) or ""
        self.assertIn("issueを有効化して", query)
        self.assertNotIn("Issue 化はしていません", query)
        self.assertIn("Finished", screen_current_activity(screen) or "")

    def test_automation_target_prefers_agent_name(self) -> None:
        self.assertEqual(
            automation_target_for_agent(
                {
                    "name": "reviewer",
                    "pane_id": "w1:p9",
                    "terminal_id": "t1",
                }
            ),
            "reviewer",
        )
        self.assertEqual(
            automation_target_for_agent({"pane_id": "w1:p9", "terminal_id": "t1"}),
            "w1:p9",
        )
        self.assertEqual(
            automation_target_for_agent({"terminal_id": "t-only"}),
            "t-only",
        )

    def test_load_automation_targets_by_pane_indexes_agents(self) -> None:
        class FakeSummarize:
            payloads: dict[tuple[str, ...], dict] = {
                ("agent", "list"): {
                    "result": {
                        "agents": [
                            {"name": "coder", "pane_id": "w1:p1"},
                            {"pane_id": "w1:p2", "terminal_id": "t2"},
                        ]
                    }
                }
            }

        def fake_herdr_json(herdr: str, args: list[str]) -> dict:
            self.assertEqual(herdr, "herdr-test")
            key = tuple(args)
            return FakeSummarize.payloads[key]

        import scripts.summarize_herdr_tabs as mod

        original = mod.herdr_json
        mod.herdr_json = fake_herdr_json
        try:
            targets = load_automation_targets_by_pane("herdr-test")
        finally:
            mod.herdr_json = original

        self.assertEqual(
            targets,
            {"w1:p1": "coder", "w1:p2": "w1:p2"},
        )

    def _load_agent_list_v092_fixture(self) -> dict:
        fixture = (
            Path(__file__).resolve().parent / "fixtures" / "agent-list-v092.json"
        )
        return json.loads(fixture.read_text(encoding="utf-8"))

    def test_automation_targets_from_v092_agent_list_fixture(self) -> None:
        targets = automation_targets_from_agent_list_payload(
            self._load_agent_list_v092_fixture()
        )
        self.assertEqual(
            targets,
            {"w2:p1": "coder", "w2:p2": "reviewer"},
        )

    def test_load_automation_targets_by_pane_uses_agent_list_fixture(self) -> None:
        fixture_payload = self._load_agent_list_v092_fixture()

        def fake_herdr_json(herdr: str, args: list[str]) -> dict:
            self.assertEqual(herdr, "herdr-test")
            self.assertEqual(args, ["agent", "list"])
            return fixture_payload

        import scripts.summarize_herdr_tabs as mod

        original = mod.herdr_json
        mod.herdr_json = fake_herdr_json
        try:
            targets = load_automation_targets_by_pane("herdr-test")
        finally:
            mod.herdr_json = original

        self.assertEqual(
            targets,
            {"w2:p1": "coder", "w2:p2": "reviewer"},
        )

    def test_automation_targets_top_level_agents_fallback(self) -> None:
        payload = {
            "agents": [
                {"name": "alpha", "pane_id": "w9:p1"},
            ]
        }
        self.assertEqual(
            automation_targets_from_agent_list_payload(payload),
            {"w9:p1": "alpha"},
        )

    def test_herdr_json_raises_on_error_payload(self) -> None:
        def fake_run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
            body = json.dumps({"error": {"code": "foo", "message": "bar"}})
            return subprocess.CompletedProcess(command, 0, body.encode(), b"")

        with patch("scripts.summarize_herdr_tabs.run_command", fake_run):
            with self.assertRaises(RuntimeError) as ctx:
                herdr_json("herdr", ["workspace", "list"])
        msg = str(ctx.exception)
        self.assertIn("foo", msg)
        self.assertIn("bar", msg)

        def fake_run_scalar(command: list[str]) -> subprocess.CompletedProcess[bytes]:
            body = json.dumps({"error": "plain failure"})
            return subprocess.CompletedProcess(command, 0, body.encode(), b"")

        with patch("scripts.summarize_herdr_tabs.run_command", fake_run_scalar):
            with self.assertRaises(RuntimeError) as ctx:
                herdr_json("herdr", ["tab", "list"])
        self.assertIn("plain failure", str(ctx.exception))

    def test_compose_summary_joins_parts(self) -> None:
        text = compose_summary(
            title="t",
            latest_user="監査して",
            activity="Issue を作成します。",
        )
        self.assertEqual(text, "監査して / いま: Issue を作成します。")

    def test_render_plain_uses_dash_separators(self) -> None:
        ws = WorkspaceSummary(
            workspace_id="wB",
            label="herdr",
            focused=True,
            tabs=[
                PaneSummary(
                    workspace_id="wB",
                    tab_id="wB:t1",
                    tab_number=1,
                    tab_label="1",
                    pane_id="wB:p1",
                    automation_target="reviewer",
                    title="Demo",
                    agent="cursor",
                    agent_status="working",
                    focused=True,
                    cwd="/tmp",
                    agent_session_id=None,
                    latest_user_query="サマリを出して",
                    current_activity="レイアウトを直しています。",
                    summary="サマリを出して / いま: レイアウトを直しています。",
                    source="transcript",
                )
            ],
        )
        text = render_plain([ws])
        self.assertIn("#" * 32, text)
        self.assertIn("tab 1: 1  <-- focused", text)
        self.assertIn("target: reviewer", text)
        self.assertIn("依頼:", text)
        self.assertIn("いま:", text)
        self.assertNotIn("|------|", text)


if __name__ == "__main__":
    unittest.main()
