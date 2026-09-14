#!/usr/bin/env python3
"""Summarize what each Herdr tab is currently doing.

Reads workspace/tab/pane metadata via the herdr CLI, then builds a short
summary from Cursor agent transcripts (when available) and recent pane text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

USER_QUERY_RE = re.compile(
    r"<user_query>\s*(.*?)\s*</user_query>",
    re.DOTALL | re.IGNORECASE,
)
TIMESTAMP_RE = re.compile(r"<timestamp>.*?</timestamp>", re.DOTALL | re.IGNORECASE)
NOISE_LINE_RE = re.compile(
    r"""(?x)
    ^\s*(
        \$ |
        → |
        Tip: |
        Auto\s*· |
        Finished\b |
        Running\b |
        Used\b |
        Read\b |
        Grepped\b |
        Globbed\b |
        Searching\b |
        Responding\b |
        \d+\s+task |
        \d+\s+earlier\s+items |
        \.\.\.\s*\d+\s+(input|output)\s+lines |
        ctrl\+c\s+to\s+stop |
        ~/ |
        ubuntu@
    )
    """,
    re.IGNORECASE,
)
ASSISTANT_BLOCK_RE = re.compile(
    r"""(?x)
    ^(
        Finished\b |
        Running\b |
        Responding\b |
        Searching\b |
        Reading\b |
        Used\b |
        Issues?\s+を |
        .*完了済み |
        .*を\s*(実施|確認|作成|調査|洗い出|有効化)します |
        主要所見 |
        Cursor\s+Agent |
        Tip: |
        \d+\s+agent\s+completed |
        .*✓\s*Done |
        一覧: |
        fork\s+側のみ
    )
    """,
    re.IGNORECASE,
)
# Next-block boost: assistant starting work, not finished chrome.
FOLLOWED_BY_ASSISTANT_RE = re.compile(
    r"(?is)\A(?:Used|Running|Responding|Searching|Reading|\$ )\b"
)
USERISH_RE = re.compile(
    r"(?:して|ください|下さい|？|\?|て$|ろ$|よ$|か$)",
)
ACTIVITY_RE = re.compile(
    r"(?im)^\s*(?:Running(?:\s+subagent)?|Finished|Responding|Searching|Reading)\b.*$"
)


@dataclass
class PaneSummary:
    workspace_id: str
    tab_id: str
    tab_number: int | None
    tab_label: str
    pane_id: str
    title: str
    agent: str | None
    agent_status: str | None
    focused: bool
    cwd: str | None
    agent_session_id: str | None
    latest_user_query: str | None
    current_activity: str | None
    summary: str
    source: str


@dataclass
class WorkspaceSummary:
    workspace_id: str
    label: str | None
    focused: bool
    tabs: list[PaneSummary] = field(default_factory=list)


def main() -> int:
    args = parse_args()
    try:
        workspaces = collect_summaries(args)
    except RuntimeError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    if args.format == "json":
        payload = {
            "workspaces": [
                {
                    "workspace_id": ws.workspace_id,
                    "label": ws.label,
                    "focused": ws.focused,
                    "tabs": [asdict(tab) for tab in ws.tabs],
                }
                for ws in workspaces
            ]
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.format == "markdown":
        print(render_markdown(workspaces))
        return 0

    print(render_plain(workspaces))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize active work across Herdr tabs/panes."
    )
    parser.add_argument(
        "--herdr",
        default=os.environ.get("HERDR_BIN_PATH", "herdr"),
        help="herdr binary (default: $HERDR_BIN_PATH or herdr)",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        dest="workspaces",
        default=None,
        help="Limit to workspace id (repeatable). Default: all workspaces.",
    )
    parser.add_argument(
        "--format",
        choices=("plain", "markdown", "json"),
        default="plain",
        help="Output format (default: plain CLI layout)",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=120,
        help="Recent pane lines to read when transcripts are missing (default: 120)",
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=None,
        help="Cursor agent-transcripts directory (default: $AGENT_TRANSCRIPTS)",
    )
    parser.add_argument(
        "--include-shell",
        action="store_true",
        help="Include panes with no detected agent (default: agent panes only)",
    )
    return parser.parse_args()


def collect_summaries(args: argparse.Namespace) -> list[WorkspaceSummary]:
    workspace_payload = herdr_json(args.herdr, ["workspace", "list"])
    workspaces_raw = (
        workspace_payload.get("result", {}).get("workspaces")
        or workspace_payload.get("workspaces")
        or []
    )
    if not workspaces_raw:
        raise RuntimeError("no workspaces returned by `herdr workspace list`")

    selected = set(args.workspaces or [])
    transcripts_dir = resolve_transcripts_dir(args.transcripts_dir)
    out: list[WorkspaceSummary] = []

    for ws in workspaces_raw:
        workspace_id = str(ws.get("workspace_id") or "")
        if not workspace_id:
            continue
        if selected and workspace_id not in selected:
            continue

        tabs_payload = herdr_json(
            args.herdr, ["tab", "list", "--workspace", workspace_id]
        )
        panes_payload = herdr_json(
            args.herdr, ["pane", "list", "--workspace", workspace_id]
        )
        tabs = tabs_payload.get("result", {}).get("tabs") or tabs_payload.get("tabs") or []
        panes = (
            panes_payload.get("result", {}).get("panes")
            or panes_payload.get("panes")
            or []
        )
        panes_by_tab: dict[str, list[dict[str, Any]]] = {}
        for pane in panes:
            tab_id = str(pane.get("tab_id") or "")
            panes_by_tab.setdefault(tab_id, []).append(pane)

        summary = WorkspaceSummary(
            workspace_id=workspace_id,
            label=ws.get("label"),
            focused=bool(ws.get("focused")),
        )

        for tab in sorted(tabs, key=lambda t: int(t.get("number") or 0)):
            tab_id = str(tab.get("tab_id") or "")
            tab_panes = panes_by_tab.get(tab_id, [])
            if not tab_panes:
                summary.tabs.append(
                    PaneSummary(
                        workspace_id=workspace_id,
                        tab_id=tab_id,
                        tab_number=tab.get("number"),
                        tab_label=str(tab.get("label") or tab_id),
                        pane_id="",
                        title="",
                        agent=None,
                        agent_status=tab.get("agent_status"),
                        focused=bool(tab.get("focused")),
                        cwd=None,
                        agent_session_id=None,
                        latest_user_query=None,
                        current_activity=None,
                        summary="(ペインなし)",
                        source="metadata",
                    )
                )
                continue

            # Prefer focused pane, else first pane in the tab.
            tab_panes = sorted(
                tab_panes, key=lambda p: (not bool(p.get("focused")), str(p.get("pane_id")))
            )
            for pane in tab_panes:
                if not args.include_shell and not pane.get("agent"):
                    continue
                summary.tabs.append(
                    summarize_pane(
                        args=args,
                        workspace_id=workspace_id,
                        tab=tab,
                        pane=pane,
                        transcripts_dir=transcripts_dir,
                    )
                )

        out.append(summary)

    if not out:
        raise RuntimeError("no matching workspaces")
    return out


def summarize_pane(
    *,
    args: argparse.Namespace,
    workspace_id: str,
    tab: dict[str, Any],
    pane: dict[str, Any],
    transcripts_dir: Path | None,
) -> PaneSummary:
    pane_id = str(pane.get("pane_id") or "")
    title = str(
        pane.get("terminal_title_stripped")
        or pane.get("terminal_title")
        or pane.get("label")
        or ""
    )
    session_id = extract_session_id(pane)
    latest_user = None
    activity = None
    source = "metadata"

    transcript = load_transcript(transcripts_dir, session_id) if session_id else None
    if transcript is not None:
        latest_user = transcript_latest_user_query(transcript)
        activity = transcript_latest_assistant_text(transcript)
        source = "transcript"

    screen = ""
    if latest_user is None or activity is None:
        screen = read_pane_text(args.herdr, pane_id, args.lines)
        if latest_user is None:
            latest_user = screen_latest_user_query(screen)
            if latest_user:
                source = "screen" if source == "metadata" else source
        if activity is None:
            activity = screen_current_activity(screen)
            if activity and source == "metadata":
                source = "screen"

    summary = compose_summary(title=title, latest_user=latest_user, activity=activity)
    return PaneSummary(
        workspace_id=workspace_id,
        tab_id=str(tab.get("tab_id") or ""),
        tab_number=tab.get("number"),
        tab_label=str(tab.get("label") or tab.get("tab_id") or ""),
        pane_id=pane_id,
        title=title,
        agent=pane.get("agent"),
        agent_status=pane.get("agent_status") or tab.get("agent_status"),
        focused=bool(pane.get("focused") or tab.get("focused")),
        cwd=pane.get("foreground_cwd") or pane.get("cwd"),
        agent_session_id=session_id,
        latest_user_query=latest_user,
        current_activity=activity,
        summary=summary,
        source=source,
    )


def compose_summary(*, title: str, latest_user: str | None, activity: str | None) -> str:
    parts: list[str] = []
    if latest_user:
        parts.append(collapse_ws(latest_user))
    elif title:
        parts.append(f"タイトル: {title}")
    if activity:
        act = collapse_ws(activity)
        if not parts or act not in parts[0]:
            parts.append(f"いま: {act}")
    if not parts:
        return "(内容を推定できず)"
    return " / ".join(parts)


def extract_session_id(pane: dict[str, Any]) -> str | None:
    session = pane.get("agent_session")
    if isinstance(session, dict):
        value = session.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_transcripts_dir(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit.expanduser()
    env = os.environ.get("AGENT_TRANSCRIPTS")
    if env:
        return Path(env).expanduser()
    # Common Cursor layout inside Herdr/agent sessions.
    home = Path.home()
    candidates = [
        home / ".cursor" / "projects" / "home-ubuntu-workspace-herdr" / "agent-transcripts",
        home / ".cursor" / "projects",
    ]
    for path in candidates:
        if path.name == "agent-transcripts" and path.is_dir():
            return path
        if path.name == "projects" and path.is_dir():
            matches = sorted(path.glob("*/agent-transcripts"))
            if len(matches) == 1:
                return matches[0]
    return None


def load_transcript(transcripts_dir: Path | None, session_id: str | None) -> list[dict[str, Any]] | None:
    if transcripts_dir is None or not session_id:
        return None
    session_dir = transcripts_dir / session_id
    if not session_dir.is_dir():
        return None
    files = sorted(session_dir.glob("*.jsonl"))
    if not files:
        return None
    rows: list[dict[str, Any]] = []
    try:
        with files[0].open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    return rows or None


def transcript_latest_user_query(rows: list[dict[str, Any]]) -> str | None:
    for row in reversed(rows):
        if row.get("role") != "user":
            continue
        text = message_text(row)
        if not text:
            continue
        match = USER_QUERY_RE.search(text)
        raw = match.group(1) if match else TIMESTAMP_RE.sub("", text)
        cleaned = collapse_ws(raw)
        if cleaned:
            return cleaned
    return None


def transcript_latest_assistant_text(rows: list[dict[str, Any]]) -> str | None:
    for row in reversed(rows):
        if row.get("role") != "assistant":
            continue
        text = message_text(row)
        if not text:
            continue
        # Prefer the first non-empty paragraph (current plan/status).
        for paragraph in re.split(r"\n\s*\n", text):
            cleaned = collapse_ws(paragraph)
            if cleaned and not cleaned.startswith("{") and len(cleaned) >= 4:
                return truncate(cleaned, 160)
    return None


def message_text(row: dict[str, Any]) -> str:
    message = row.get("message")
    content: Any
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = row.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(parts)
    return ""


def screen_latest_user_query(screen: str) -> str | None:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", screen) if b.strip()]
    scored: list[tuple[int, str]] = []
    for index, block in enumerate(blocks):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if any(NOISE_LINE_RE.match(ln) for ln in lines[:2]):
            continue
        # Skip dense tool / code dumps.
        if sum(1 for ln in lines if ln.lstrip().startswith("$")) >= 1:
            continue
        if len(lines) > 8:
            continue
        text = collapse_ws(" ".join(lines))
        if len(text) < 8 or len(text) > 240:
            continue
        if ASSISTANT_BLOCK_RE.match(text):
            continue
        score = index
        # Prefer blocks immediately followed by assistant/tool activity.
        if index + 1 < len(blocks):
            nxt = collapse_ws(blocks[index + 1])
            if FOLLOWED_BY_ASSISTANT_RE.match(nxt) or (
                ASSISTANT_BLOCK_RE.match(nxt) and not nxt.lower().startswith("finished")
            ):
                score += 1000
        if USERISH_RE.search(text):
            score += 300
        # Deprioritize markdown bullets / tables leftovers.
        if text.startswith("•") or text.startswith("│") or text.startswith("┌"):
            score -= 500
        scored.append((score, text))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    return scored[-1][1]


def screen_current_activity(screen: str) -> str | None:
    matches = ACTIVITY_RE.findall(screen)
    if matches:
        return truncate(collapse_ws(matches[-1]), 140)
    # Fall back to last non-noise non-empty line above the footer.
    lines = [ln.rstrip() for ln in screen.splitlines() if ln.strip()]
    for line in reversed(lines):
        if NOISE_LINE_RE.match(line):
            continue
        if "Add a follow-up" in line:
            continue
        return truncate(collapse_ws(line), 140)
    return None


def read_pane_text(herdr: str, pane_id: str, lines: int) -> str:
    if not pane_id:
        return ""
    result = run_command(
        [
            herdr,
            "pane",
            "read",
            pane_id,
            "--source",
            "recent",
            "--format",
            "text",
            "--lines",
            str(lines),
        ]
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def herdr_json(herdr: str, args: list[str]) -> dict[str, Any]:
    result = run_command([herdr, *args])
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(err or f"`{herdr} {' '.join(args)}` failed")
    text = result.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        raise RuntimeError(f"`{herdr} {' '.join(args)}` returned empty output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"invalid JSON from `{herdr} {' '.join(args)}`: {err}") from err
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected JSON payload from `{herdr} {' '.join(args)}`")
    return payload


def run_command(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, capture_output=True, check=False)
    except FileNotFoundError as err:
        raise RuntimeError(f"command not found: {command[0]}") from err


def render_markdown(workspaces: list[WorkspaceSummary]) -> str:
    chunks: list[str] = []
    for ws in workspaces:
        focus = " (focused)" if ws.focused else ""
        label = ws.label or ws.workspace_id
        chunks.append(f"## {label} `{ws.workspace_id}`{focus}")
        chunks.append("")
        chunks.append("| タブ | ラベル / タイトル | やっていること | 状態 |")
        chunks.append("|------|-------------------|----------------|------|")
        for tab in ws.tabs:
            num = tab.tab_number if tab.tab_number is not None else "?"
            label_title = f"{tab.tab_label}"
            if tab.title and tab.title != tab.tab_label:
                label_title = f"{tab.tab_label} / {tab.title}"
            focus_mark = " ←" if tab.focused else ""
            status = tab.agent_status or "-"
            agent = tab.agent or "shell"
            chunks.append(
                f"| **{num}**{focus_mark} | {md_escape(label_title)} | "
                f"{md_escape(tab.summary)} | {agent}/{status} |"
            )
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


SEPARATOR = "#" * 80


def render_plain(workspaces: list[WorkspaceSummary]) -> str:
    lines: list[str] = []
    for ws_index, ws in enumerate(workspaces):
        if ws_index:
            lines.append("")
            lines.append("=" * 32)
            lines.append("")

        label = ws.label or ws.workspace_id
        focus = "  [focused]" if ws.focused else ""
        lines.append(f"workspace: {label} ({ws.workspace_id}){focus}")
        lines.append(SEPARATOR)

        for tab_index, tab in enumerate(ws.tabs):
            if tab_index:
                lines.append(SEPARATOR)

            num = tab.tab_number if tab.tab_number is not None else "?"
            focus_mark = "  <-- focused" if tab.focused else ""
            agent = tab.agent or "shell"
            status = tab.agent_status or "-"
            title = tab.title or "-"

            lines.append(f"tab {num}: {tab.tab_label}{focus_mark}")
            lines.append(f"title: {title}")
            lines.append(f"status: {agent}/{status}")
            if tab.pane_id:
                lines.append(f"pane: {tab.pane_id}")

            if tab.latest_user_query:
                lines.append("")
                lines.append("依頼:")
                lines.extend(wrap_cli_lines(tab.latest_user_query, indent="  "))

            if tab.current_activity:
                lines.append("")
                lines.append("いま:")
                lines.extend(wrap_cli_lines(tab.current_activity, indent="  "))

            if not tab.latest_user_query and not tab.current_activity:
                lines.append("")
                lines.append("内容:")
                lines.extend(wrap_cli_lines(tab.summary, indent="  "))

        lines.append(SEPARATOR)

    return "\n".join(lines).rstrip() + "\n"


def wrap_cli_lines(text: str, *, indent: str = "", width: int = 72) -> list[str]:
    cleaned = collapse_ws(text)
    if not cleaned:
        return [f"{indent}(なし)"]
    wrapped = textwrap.fill(
        cleaned,
        width=max(20, width - len(indent)),
        break_long_words=False,
        break_on_hyphens=False,
    )
    return [f"{indent}{line}" for line in wrapped.splitlines()]


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


if __name__ == "__main__":
    sys.exit(main())
