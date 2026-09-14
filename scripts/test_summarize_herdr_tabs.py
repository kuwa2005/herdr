#!/usr/bin/env python3
"""Unit tests for scripts/summarize_herdr_tabs.py helpers."""

from __future__ import annotations

import unittest

from scripts.summarize_herdr_tabs import (
    PaneSummary,
    WorkspaceSummary,
    compose_summary,
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
        self.assertIn("----------------", text)
        self.assertIn("tab 1: 1  <-- focused", text)
        self.assertIn("依頼:", text)
        self.assertIn("いま:", text)
        self.assertNotIn("|------|", text)


if __name__ == "__main__":
    unittest.main()
