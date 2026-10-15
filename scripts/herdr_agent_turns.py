#!/usr/bin/env python3
"""Self-evolving instruct → fix → review loop via Herdr agent CLI.

Official multi-agent improvement workflow for this Herdr fork:

1. INSTRUCT — planner writes the next focused task (``TURN{n}_PLAN.md``)
2. FIX — coder implements that plan (``TURN{n}_RESULT.md``)
3. REVIEW — reviewer judges and writes instructions (``TURN{n}_REVIEW.md``)
4. Optional APPLY — coder applies review when verdict is ``REVISE``
5. Next turn's INSTRUCT reads the prior review and plans further improvement

Hard cap: at most ``MAX_TURNS`` (10). Infinite or huge turn counts are rejected.
Early stop when review verdict is ``DONE`` (goal met) or ``STOP``.

Typical in-session call (from a Herdr-managed agent pane):

    herdr-turns --from-here --daemon --turns 5 --goal "Improve error handling"

``--from-here`` uses the agent in ``$HERDR_PANE_ID`` for instruct/fix/review
(self mode). ``--daemon`` backgrounds the runner so the current agent can go
idle and receive the scripted prompts (avoids deadlock).

Explicit multi-agent mode still works with ``--coder`` / ``--reviewer``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


MAX_TURNS = 10
DEFAULT_TURNS = 10
DEFAULT_TIMEOUT_MS = 600_000
DEFAULT_POLL_SECONDS = 1.0
DEFAULT_IDLE_GRACE = 12
DEFAULT_DAEMON_IDLE_GRACE_MS = 15_000

VERDICT_RE = re.compile(
    r"(?im)^\s*VERDICT\s*:\s*(APPROVE|REVISE|DONE|STOP)\s*$"
)
STOP_PLAN_RE = re.compile(
    r"(?im)^\s*(?:STATUS|PLAN)\s*:\s*(DONE|STOP)\s*$"
)
# Structured fields for effectiveness reports (one line or indented block).
FIELD_RE = re.compile(
    r"(?im)^\s*(TASK|DONE|VERIFIED|IMPROVE|EFFECT)\s*:\s*(.+?)\s*$"
)
SKELETON_NOISE_RE = re.compile(r"(?im)^\s*(_\(pending\)_|#\s*Turn\b)")


@dataclass
class TurnRecord:
    number: int
    instruct_prompt: str
    fix_prompt: str
    review_prompt: str
    apply_prompt: str | None
    plan_path: Path
    result_path: Path
    review_path: Path
    verdict: str | None = None
    notes: list[str] = field(default_factory=list)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run up to 10 self-evolution turns "
            "(instruct → fix → review → next instruct) via herdr agent CLI, "
            "then print the summary and write "
            "自己改善yyyymmddhhmmss.md plus SUMMARY.md. "
            "Use --from-here while coding in a Herdr agent pane."
        )
    )
    p.add_argument(
        "--herdr",
        default=os.environ.get("HERDR_BIN_PATH") or "herdr",
        help="herdr binary (default: $HERDR_BIN_PATH or herdr)",
    )
    p.add_argument(
        "--from-here",
        action="store_true",
        help=(
            "Use the agent in $HERDR_PANE_ID as coder/planner/reviewer "
            "(self-improve from the current pane)"
        ),
    )
    p.add_argument(
        "--coder",
        default=None,
        help="Coder agent name or pane id (required unless --from-here)",
    )
    p.add_argument(
        "--reviewer",
        default=None,
        help=(
            "Reviewer agent name or pane id "
            "(default with --from-here: same as coder / self-review)"
        ),
    )
    p.add_argument(
        "--planner",
        default=None,
        help="Planner agent for self-instruction (default: same as --coder)",
    )
    p.add_argument(
        "--turns",
        type=int,
        default=DEFAULT_TURNS,
        help=f"Number of evolution turns (default: {DEFAULT_TURNS}, max: {MAX_TURNS})",
    )
    p.add_argument(
        "--goal",
        required=True,
        help="Overall improvement goal shared across turns",
    )
    p.add_argument(
        "--notes-dir",
        type=Path,
        default=None,
        help=(
            "Directory for TURN*_PLAN/RESULT/REVIEW.md and SUMMARY.md "
            "(default with --from-here: ./herdr-turns-notes). "
            "The timestamped 自己改善yyyymmddhhmmss.md is written under --workdir."
        ),
    )
    p.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Working directory mentioned in prompts (default: cwd)",
    )
    p.add_argument(
        "--constraints",
        type=Path,
        default=None,
        help="Optional constraints file path to mention in prompts",
    )
    p.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help=f"Per-step wait budget in ms (default: {DEFAULT_TIMEOUT_MS})",
    )
    p.add_argument(
        "--daemon",
        action="store_true",
        help=(
            "Start the runner in the background and exit immediately "
            "(required when the target agent launches this command itself)"
        ),
    )
    p.add_argument(
        "--daemon-idle-grace-ms",
        type=int,
        default=DEFAULT_DAEMON_IDLE_GRACE_MS,
        help=(
            "After --daemon reattach, wait this long for the launcher agent "
            f"to become idle before the first prompt (default: {DEFAULT_DAEMON_IDLE_GRACE_MS})"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned prompts and write skeleton notes without calling herdr",
    )
    return p


def validate_turns(turns: int) -> str | None:
    if turns < 1:
        return "--turns must be >= 1"
    if turns > MAX_TURNS:
        return f"--turns must be <= {MAX_TURNS} (hard cap; infinite loops are forbidden)"
    return None


def automation_target_for_agent(agent: dict[str, Any]) -> str | None:
    name = agent.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    pane_id = agent.get("pane_id")
    if isinstance(pane_id, str) and pane_id.strip():
        return pane_id.strip()
    terminal_id = agent.get("terminal_id")
    if isinstance(terminal_id, str) and terminal_id.strip():
        return terminal_id.strip()
    return None


def resolve_agent_in_pane(herdr: str, pane_id: str) -> str:
    payload = herdr_json(herdr, ["agent", "list"])
    agents = payload.get("result", {}).get("agents") or payload.get("agents") or []
    matches: list[str] = []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        if str(agent.get("pane_id") or "") != pane_id:
            continue
        target = automation_target_for_agent(agent)
        if target:
            matches.append(target)
    if not matches:
        raise RuntimeError(
            f"--from-here: no live agent in pane {pane_id!r} "
            "(start an agent in this pane, or pass --coder explicitly)"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"--from-here: multiple agents in pane {pane_id!r}: {matches}"
        )
    return matches[0]


def resolve_from_here(herdr: str) -> str:
    pane_id = os.environ.get("HERDR_PANE_ID", "").strip()
    if not pane_id:
        raise RuntimeError(
            "--from-here requires HERDR_PANE_ID "
            "(run inside a Herdr-managed pane, or pass --coder)"
        )
    return resolve_agent_in_pane(herdr, pane_id)


def resolve_roles(args: argparse.Namespace) -> tuple[str, str, str]:
    """Return (planner, coder, reviewer)."""
    coder = args.coder
    if args.from_here:
        here = resolve_from_here(args.herdr)
        coder = coder or here
    if not coder:
        raise RuntimeError("pass --coder or --from-here")
    planner = args.planner or coder
    reviewer = args.reviewer or coder
    return planner, coder, reviewer


def default_notes_dir(args: argparse.Namespace) -> Path:
    if args.notes_dir is not None:
        return args.notes_dir.expanduser().resolve()
    if args.from_here:
        return (Path.cwd() / "herdr-turns-notes").resolve()
    raise RuntimeError("--notes-dir is required unless --from-here")


def daemonize(argv: list[str], *, notes_dir: Path) -> int:
    """Re-exec without --daemon; return immediately with pid/log JSON."""
    ensure_notes_dir(notes_dir)
    log_path = notes_dir / "runner.log"
    child_argv = [a for a in argv if a != "--daemon"]
    # Ensure notes-dir is explicit for the child even if it was defaulted.
    if "--notes-dir" not in child_argv:
        child_argv.extend(["--notes-dir", str(notes_dir)])
    script = str(Path(__file__).resolve())
    cmd = [sys.executable, script, *child_argv]
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — kept by child
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_f.close()
    print(
        json.dumps(
            {
                "ok": True,
                "pid": proc.pid,
                "log": str(log_path),
                "notes_dir": str(notes_dir),
                "message": (
                    "self-evolve runner started in background; "
                    "go idle so it can prompt this agent"
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


def wait_until_idle(
    herdr: str,
    target: str,
    *,
    grace_ms: int,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> None:
    """Best-effort wait so a launcher agent can finish before first prompt."""
    if grace_ms <= 0:
        return
    deadline = time.monotonic() + (grace_ms / 1000.0)
    while time.monotonic() < deadline:
        try:
            status = agent_status(herdr, target)
        except RuntimeError:
            time.sleep(poll_seconds)
            continue
        if status in {"idle", "done"}:
            return
        time.sleep(poll_seconds)


def instruct_prompt(
    *,
    turn: int,
    turns: int,
    goal: str,
    workdir: Path,
    notes_dir: Path,
    constraints: Path | None,
    prev_review_path: Path | None,
    prev_result_path: Path | None,
) -> str:
    constraints_line = (
        f"Read and follow {constraints}."
        if constraints is not None
        else "Keep each turn small and verifiable."
    )
    if turn == 1 or prev_review_path is None:
        prior = (
            "This is the first turn. Derive ONE concrete next task from the goal."
        )
    else:
        prior = (
            f"Read the previous review {prev_review_path} "
            f"and previous result {prev_result_path}.\n"
            "Decide the ONE best next improvement. "
            "If the goal is already met, write a plan file whose first lines are:\n"
            "STATUS: DONE\n"
            "reason: ..."
        )
    plan_path = notes_dir / f"TURN{turn}_PLAN.md"
    return (
        f"Turn {turn}/{turns} INSTRUCT (self-instruction).\n"
        f"Workdir: {workdir}\n"
        f"Overall goal: {goal}\n"
        f"{constraints_line}\n"
        f"{prior}\n"
        f"Write {plan_path} using exactly these labeled lines "
        f"(needed later for effectiveness review):\n"
        f"STATUS: CONTINUE\n"
        f"TASK: <one concrete task this turn>\n"
        f"DONE_WHEN: <how we know it worked>\n"
        f"OUT_OF_SCOPE: <what not to touch>\n"
        f"If the overall goal is already met, use STATUS: DONE and TASK: none.\n"
        f"Do not edit repository source files. Do not commit."
    )


def fix_prompt(
    *,
    turn: int,
    turns: int,
    goal: str,
    workdir: Path,
    notes_dir: Path,
    constraints: Path | None,
) -> str:
    constraints_line = (
        f"Read and follow {constraints}."
        if constraints is not None
        else "Keep the change small and verifiable."
    )
    plan_path = notes_dir / f"TURN{turn}_PLAN.md"
    result_path = notes_dir / f"TURN{turn}_RESULT.md"
    return (
        f"Turn {turn}/{turns} FIX (self-correction / implement).\n"
        f"Workdir: {workdir}\n"
        f"Overall goal: {goal}\n"
        f"{constraints_line}\n"
        f"Read {plan_path} and implement ONLY that plan.\n"
        f"Write {result_path} using exactly these labeled lines "
        f"(needed later for effectiveness review):\n"
        f"DONE: <what you actually changed / delivered>\n"
        f"VERIFIED: <how you checked it>\n"
        f"FILES: <paths touched, or none>\n"
        f"Do not commit."
    )


def review_prompt(
    *,
    turn: int,
    turns: int,
    goal: str,
    workdir: Path,
    notes_dir: Path,
) -> str:
    plan_path = notes_dir / f"TURN{turn}_PLAN.md"
    result_path = notes_dir / f"TURN{turn}_RESULT.md"
    review_path = notes_dir / f"TURN{turn}_REVIEW.md"
    return (
        f"Turn {turn}/{turns} REVIEW (self-review).\n"
        f"Workdir: {workdir}\n"
        f"Overall goal: {goal}\n"
        f"Read {plan_path} and {result_path}. "
        f"Review the current uncommitted work (git diff / new files).\n"
        f"Write {review_path} using exactly these labeled lines "
        f"(needed later for effectiveness review):\n"
        f"VERDICT: APPROVE|REVISE|DONE\n"
        f"IMPROVE: <what must change next, or none>\n"
        f"EFFECT: <did this turn move the overall goal? yes/partial/no + one reason>\n"
        f"- APPROVE: acceptable; next instruct may still improve further\n"
        f"- REVISE: coder must apply IMPROVE this turn\n"
        f"- DONE: overall goal is met; stop the loop\n"
        f"Do not edit repository source files yourself."
    )


def apply_prompt(
    *,
    turn: int,
    turns: int,
    notes_dir: Path,
) -> str:
    return (
        f"Turn {turn}/{turns} APPLY (fix from review).\n"
        f"Read {notes_dir / f'TURN{turn}_REVIEW.md'} and apply IMPROVE fixes.\n"
        f"Update {notes_dir / f'TURN{turn}_RESULT.md'} labeled lines "
        f"(DONE / VERIFIED / FILES) after applying.\n"
        f"Do not commit."
    )


def parse_verdict(review_text: str | None) -> str | None:
    if not review_text:
        return None
    match = VERDICT_RE.search(review_text)
    if match is None:
        return None
    return match.group(1).upper()


def parse_plan_stop(plan_text: str | None) -> bool:
    if not plan_text:
        return False
    return STOP_PLAN_RE.search(plan_text) is not None


_FIELD_RE_CACHE: dict[str, re.Pattern[str]] = {}


def extract_labeled_field(text: str | None, label: str) -> str | None:
    """Extract ``LABEL: value`` (value may span until the next ALLCAPS label)."""
    if not text:
        return None
    key = label.upper()
    pattern = _FIELD_RE_CACHE.get(key)
    if pattern is None:
        pattern = re.compile(
            rf"(?ims)^\s*{re.escape(key)}\s*:\s*(.+?)(?=^\s*[A-Z][A-Z0-9_]*\s*:|\Z)"
        )
        _FIELD_RE_CACHE[key] = pattern
    match = pattern.search(text)
    if match is None:
        return None
    value = " ".join(match.group(1).strip().split())
    return value or None


def summarize_body(text: str | None, *, limit: int = 240) -> str:
    if not text:
        return "_(なし)_"
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("_("):
            continue
        if re.match(r"^(STATUS|TASK|DONE_WHEN|OUT_OF_SCOPE|DONE|VERIFIED|VERDICT|IMPROVE|EFFECT)\s*:", line, re.I):
            continue
        if line == "_(pending)_":
            continue
        lines.append(line)
    body = " ".join(lines).strip()
    if not body:
        return "_(記載なし)_"
    if len(body) > limit:
        return body[: limit - 1] + "…"
    return body


def turn_effect_rows(records: list[TurnRecord]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rec in records:
        plan = read_text(rec.plan_path)
        result = read_text(rec.result_path)
        review = read_text(rec.review_path)
        verdict = rec.verdict or parse_verdict(review) or "—"
        task = extract_labeled_field(plan, "TASK") or summarize_body(plan)
        done = extract_labeled_field(result, "DONE") or summarize_body(result)
        improve = extract_labeled_field(review, "IMPROVE") or summarize_body(review)
        effect = extract_labeled_field(review, "EFFECT") or "—"
        rows.append(
            {
                "turn": str(rec.number),
                "task": task,
                "done": done,
                "improve": improve,
                "verdict": verdict,
                "effect": effect,
            }
        )
    return rows


def judge_effectiveness(
    records: list[TurnRecord],
    *,
    max_turns: int,
    stop_reason: str | None,
) -> tuple[str, list[str]]:
    """Return (label, bullet reasons) for human effectiveness review."""
    if not records:
        return "効果なし", ["ターンが 1 回も完了していない"]

    verdicts = [(r.verdict or parse_verdict(read_text(r.review_path)) or "") for r in records]
    revise_n = sum(1 for v in verdicts if v == "REVISE")
    done_n = sum(1 for v in verdicts if v == "DONE")
    approve_n = sum(1 for v in verdicts if v == "APPROVE")
    reasons: list[str] = [
        f"完了ターン: {len(records)} / 予定上限 {max_turns}（ハードキャップ {MAX_TURNS}）",
        f"VERDICT 内訳: DONE={done_n}, APPROVE={approve_n}, REVISE={revise_n}",
    ]
    if stop_reason:
        reasons.append(f"早期終了: {stop_reason}")

    if done_n > 0 or (stop_reason and "DONE" in stop_reason.upper()):
        return "目標達成の見込み", reasons + [
            "レビューまたは planner が DONE を出した（大元の指示を満たした判定）"
        ]
    if revise_n > 0 and approve_n == 0 and done_n == 0:
        return "改善停滞の疑い", reasons + [
            "REVISE が続く一方で APPROVE/DONE がなく、効果が出ていない可能性"
        ]
    if revise_n > 0 and approve_n + done_n > 0:
        return "部分改善（レビュー反映あり）", reasons + [
            "REVISE による指摘適用を含み、前進はあったがゴール完了は未確認"
        ]
    if approve_n > 0:
        if len(records) >= max_turns:
            return "部分改善（継続余地あり）", reasons + [
                "全ターン消化したが DONE 未達。APPROVE のみで追加改善の余地が残る"
            ]
        return "部分改善（継続余地あり）", reasons + [
            "APPROVE があり前進は確認できるが、大元の指示への DONE は未達"
        ]
    return "判定保留", reasons + [
        "VERDICT 情報不足。各ターンの DONE / IMPROVE / EFFECT 行を確認すること"
    ]


def self_improve_report_filename(when: datetime | None = None) -> str:
    """Return ``自己改善yyyymmddhhmmss.md`` for local wall time."""
    stamp = (when or datetime.now()).strftime("%Y%m%d%H%M%S")
    return f"自己改善{stamp}.md"


def write_and_display_summary(
    summary: str,
    *,
    workdir: Path,
    notes_dir: Path,
    when: datetime | None = None,
) -> Path:
    """Write SUMMARY.md, timestamped report under workdir, and print to stdout."""
    summary_path = notes_dir / "SUMMARY.md"
    summary_path.write_text(summary, encoding="utf-8")

    report_name = self_improve_report_filename(when)
    report_path = workdir / report_name
    report_path.write_text(summary, encoding="utf-8")
    # Keep a copy next to turn artifacts for the daemon log directory.
    notes_copy = notes_dir / report_name
    if notes_copy.resolve() != report_path.resolve():
        notes_copy.write_text(summary, encoding="utf-8")

    banner = (
        f"======== 自己改善サマリー（効果判定） ========\n"
        f"画面表示 + ファイル:\n"
        f"  {report_path}\n"
        f"  {summary_path}\n"
        f"=========================================="
    )
    print(banner, flush=True)
    print(summary, flush=True)
    print(f"======== wrote {report_path} ========", flush=True)
    return report_path


def render_summary(
    records: list[TurnRecord],
    *,
    goal: str,
    notes_dir: Path,
    max_turns: int,
    stop_reason: str | None,
) -> str:
    """Build a Japanese effectiveness report for humans."""
    label, reasons = judge_effectiveness(
        records, max_turns=max_turns, stop_reason=stop_reason
    )
    rows = turn_effect_rows(records)

    lines = [
        "# 自己改善レポート（効果判定）",
        "",
        "## 大元の指示",
        "",
        goal.strip() or "_(未設定)_",
        "",
        "## 効果判定",
        "",
        f"**判定: {label}**",
        "",
    ]
    for reason in reasons:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            f"Notes: `{notes_dir}`",
            "",
            "## ターン一覧",
            "",
            "| ターン | このターンの指示 | できたこと | レビューで改善させたこと | VERDICT | 効果 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["turn"],
                    _md_cell(row["task"]),
                    _md_cell(row["done"]),
                    _md_cell(row["improve"]),
                    row["verdict"],
                    _md_cell(row["effect"]),
                ]
            )
            + " |"
        )
    lines.append("")

    for rec in records:
        plan = read_text(rec.plan_path) or f"_(missing TURN{rec.number}_PLAN.md)_"
        result = read_text(rec.result_path) or f"_(missing TURN{rec.number}_RESULT.md)_"
        review = read_text(rec.review_path) or f"_(missing TURN{rec.number}_REVIEW.md)_"
        lines.extend(
            [
                f"## ターン {rec.number} 詳細",
                "",
                f"VERDICT: {rec.verdict or parse_verdict(review) or '—'}",
                "",
                "### 指示（PLAN）",
                "",
                plan.rstrip(),
                "",
                "### できたこと（RESULT）",
                "",
                result.rstrip(),
                "",
                "### レビューで改善させたこと（REVIEW）",
                "",
                review.rstrip(),
                "",
            ]
        )
        if rec.notes:
            lines.append("### ランナーメモ")
            lines.append("")
            for note in rec.notes:
                lines.append(f"- {note}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def herdr_json(herdr: str, args: list[str]) -> dict[str, Any]:
    cmd = [herdr, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"`{' '.join(cmd)}` exited {proc.returncode}"
            + (f": {err}" if err else "")
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"invalid JSON from `{' '.join(cmd)}`: {err}") from err
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected JSON payload from `{' '.join(cmd)}`")
    error = payload.get("error")
    if error is not None:
        if isinstance(error, dict):
            code = error.get("code") or "error"
            message = error.get("message") or error
            raise RuntimeError(f"herdr API error ({code}): {message}")
        raise RuntimeError(f"herdr API error: {error}")
    return payload


def agent_status(herdr: str, target: str) -> str:
    payload = herdr_json(herdr, ["agent", "get", target])
    agent = payload.get("result", {}).get("agent") or {}
    status = agent.get("agent_status")
    if not isinstance(status, str):
        raise RuntimeError(f"agent get {target}: missing agent_status")
    return status


def agent_focus(herdr: str, target: str) -> None:
    herdr_json(herdr, ["agent", "focus", target])


def agent_send_keys(herdr: str, target: str, *keys: str) -> None:
    herdr_json(herdr, ["agent", "send-keys", target, *keys])


def prepare_agent(herdr: str, target: str) -> None:
    try:
        agent_focus(herdr, target)
    except RuntimeError:
        pass
    try:
        agent_send_keys(herdr, target, "esc")
    except RuntimeError:
        pass
    time.sleep(0.4)
    try:
        agent_focus(herdr, target)
    except RuntimeError:
        pass


def prompt_and_wait(
    herdr: str,
    target: str,
    text: str,
    *,
    timeout_ms: int,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> None:
    """Submit without --wait, then poll until working settles to idle/done.

    Avoids agent_prompt_stalled from --wait's short activity window.
    """
    prepare_agent(herdr, target)
    herdr_json(herdr, ["agent", "prompt", target, text])
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    saw_work = False
    idle_ticks = 0
    while time.monotonic() < deadline:
        status = agent_status(herdr, target)
        if status in {"working", "blocked"}:
            saw_work = True
            idle_ticks = 0
        elif status in {"idle", "done"}:
            if saw_work:
                prepare_agent(herdr, target)
                return
            idle_ticks += 1
            if idle_ticks == 8:
                try:
                    agent_send_keys(herdr, target, "enter")
                except RuntimeError:
                    pass
            if idle_ticks >= DEFAULT_IDLE_GRACE and not saw_work:
                prepare_agent(herdr, target)
                return
        time.sleep(poll_seconds)
    raise TimeoutError(
        f"timed out waiting for {target} after prompt "
        f"(saw_work={saw_work}, timeout_ms={timeout_ms})"
    )


def ensure_notes_dir(notes_dir: Path) -> None:
    notes_dir.mkdir(parents=True, exist_ok=True)


def write_skeleton(path: Path, title: str) -> None:
    if path.exists():
        return
    path.write_text(f"# {title}\n\n_(pending)_\n", encoding="utf-8")


def run_turns(args: argparse.Namespace) -> int:
    err = validate_turns(args.turns)
    if err is not None:
        print(err, file=sys.stderr)
        return 2

    workdir = (args.workdir or Path.cwd()).resolve()
    notes_dir = default_notes_dir(args)
    ensure_notes_dir(notes_dir)
    constraints = args.constraints.expanduser().resolve() if args.constraints else None

    if args.daemon and not args.dry_run:
        # Rebuild argv from sys.argv[1:] so flags stay faithful.
        return daemonize(sys.argv[1:], notes_dir=notes_dir)

    try:
        planner, coder, reviewer = resolve_roles(args)
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        return 2

    print(
        f"roles: planner={planner} coder={coder} reviewer={reviewer} "
        f"turns={args.turns} notes={notes_dir}",
        flush=True,
    )

    if args.from_here and not args.dry_run:
        wait_until_idle(
            args.herdr,
            coder,
            grace_ms=args.daemon_idle_grace_ms,
        )

    records: list[TurnRecord] = []
    stop_reason: str | None = None
    prev_review_path: Path | None = None
    prev_result_path: Path | None = None

    for turn in range(1, args.turns + 1):
        plan_path = notes_dir / f"TURN{turn}_PLAN.md"
        result_path = notes_dir / f"TURN{turn}_RESULT.md"
        review_path = notes_dir / f"TURN{turn}_REVIEW.md"
        rec = TurnRecord(
            number=turn,
            instruct_prompt=instruct_prompt(
                turn=turn,
                turns=args.turns,
                goal=args.goal,
                workdir=workdir,
                notes_dir=notes_dir,
                constraints=constraints,
                prev_review_path=prev_review_path,
                prev_result_path=prev_result_path,
            ),
            fix_prompt=fix_prompt(
                turn=turn,
                turns=args.turns,
                goal=args.goal,
                workdir=workdir,
                notes_dir=notes_dir,
                constraints=constraints,
            ),
            review_prompt=review_prompt(
                turn=turn,
                turns=args.turns,
                goal=args.goal,
                workdir=workdir,
                notes_dir=notes_dir,
            ),
            apply_prompt=None,
            plan_path=plan_path,
            result_path=result_path,
            review_path=review_path,
        )
        write_skeleton(plan_path, f"Turn {turn} plan")
        write_skeleton(result_path, f"Turn {turn} result")
        write_skeleton(review_path, f"Turn {turn} review")

        print(f"======== TURN {turn}/{args.turns}: instruct ========", flush=True)
        if args.dry_run:
            print(rec.instruct_prompt)
            rec.notes.append("dry-run: skipped herdr calls")
            plan_path.write_text(
                f"# Turn {turn} plan\n\nSTATUS: CONTINUE\n\nDry-run placeholder task.\n",
                encoding="utf-8",
            )
        else:
            prompt_and_wait(
                args.herdr,
                planner,
                rec.instruct_prompt,
                timeout_ms=args.timeout_ms,
            )

        if parse_plan_stop(read_text(plan_path)):
            rec.notes.append("planner STATUS: DONE/STOP — ending before fix")
            records.append(rec)
            stop_reason = f"planner stopped at turn {turn}"
            break

        print(f"======== TURN {turn}/{args.turns}: fix ========", flush=True)
        if args.dry_run:
            print(rec.fix_prompt)
        else:
            prompt_and_wait(
                args.herdr,
                coder,
                rec.fix_prompt,
                timeout_ms=args.timeout_ms,
            )

        print(f"======== TURN {turn}/{args.turns}: review ========", flush=True)
        if args.dry_run:
            print(rec.review_prompt)
            review_path.write_text(
                f"# Turn {turn} review\n\nVERDICT: APPROVE\n\nDry-run placeholder.\n",
                encoding="utf-8",
            )
        else:
            prompt_and_wait(
                args.herdr,
                reviewer,
                rec.review_prompt,
                timeout_ms=args.timeout_ms,
            )

        verdict = parse_verdict(read_text(review_path))
        rec.verdict = verdict
        if verdict is None:
            rec.notes.append("missing VERDICT line; treating as APPROVE")
            verdict = "APPROVE"
            rec.verdict = verdict

        if verdict == "REVISE":
            rec.apply_prompt = apply_prompt(
                turn=turn,
                turns=args.turns,
                notes_dir=notes_dir,
            )
            print(f"======== TURN {turn}/{args.turns}: apply ========", flush=True)
            if args.dry_run:
                print(rec.apply_prompt)
            else:
                prompt_and_wait(
                    args.herdr,
                    coder,
                    rec.apply_prompt,
                    timeout_ms=args.timeout_ms,
                )
        elif verdict in {"DONE", "STOP"}:
            rec.notes.append(f"review VERDICT: {verdict} — stopping loop")
            records.append(rec)
            stop_reason = f"reviewer verdict {verdict} at turn {turn}"
            break

        records.append(rec)
        prev_review_path = review_path
        prev_result_path = result_path

    summary = render_summary(
        records,
        goal=args.goal,
        notes_dir=notes_dir,
        max_turns=args.turns,
        stop_reason=stop_reason,
    )
    write_and_display_summary(
        summary,
        workdir=workdir,
        notes_dir=notes_dir,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    # When argv is provided (tests), temporarily replace sys.argv for --daemon.
    restore_argv = False
    if argv is not None:
        saved = sys.argv
        sys.argv = [sys.argv[0], *argv]
        restore_argv = True
    try:
        args = build_parser().parse_args(argv)
        try:
            return run_turns(args)
        except (RuntimeError, TimeoutError) as err:
            print(f"error: {err}", file=sys.stderr)
            return 1
    finally:
        if restore_argv:
            sys.argv = saved


if __name__ == "__main__":
    raise SystemExit(main())
