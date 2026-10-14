#!/usr/bin/env python3
"""Run a coder/reviewer turn loop through Herdr agent CLI, then write a summary.

Official multi-agent improvement workflow for this Herdr install:

1. For each turn: coder implements → reviewer reviews → coder applies
2. After all turns: write ``SUMMARY.md`` describing each turn

Requires two live agents already started and named (for example via
``herdr agent start coder ...`` / ``herdr agent start reviewer ...``).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_TURNS = 3
DEFAULT_TIMEOUT_MS = 600_000
DEFAULT_POLL_SECONDS = 1.0
DEFAULT_IDLE_GRACE = 12
DEFAULT_WORK_DEADLINE = 180


@dataclass
class TurnRecord:
    number: int
    implement_prompt: str
    review_prompt: str
    apply_prompt: str
    result_path: Path
    review_path: Path
    notes: list[str] = field(default_factory=list)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run N coder/reviewer improvement turns via herdr agent CLI, "
            "then write SUMMARY.md."
        )
    )
    p.add_argument(
        "--herdr",
        default=os.environ.get("HERDR_BIN_PATH") or "herdr",
        help="herdr binary (default: $HERDR_BIN_PATH or herdr)",
    )
    p.add_argument("--coder", required=True, help="Coder agent name or pane id")
    p.add_argument("--reviewer", required=True, help="Reviewer agent name or pane id")
    p.add_argument(
        "--turns",
        type=int,
        default=DEFAULT_TURNS,
        help=f"Number of improvement turns (default: {DEFAULT_TURNS})",
    )
    p.add_argument(
        "--goal",
        required=True,
        help="Overall improvement goal shared across turns",
    )
    p.add_argument(
        "--notes-dir",
        type=Path,
        required=True,
        help="Directory for TURN*_RESULT.md, TURN*_REVIEW.md, SUMMARY.md",
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
        "--dry-run",
        action="store_true",
        help="Print planned prompts and write skeleton notes without calling herdr",
    )
    return p


def implement_prompt(
    *,
    turn: int,
    turns: int,
    goal: str,
    workdir: Path,
    notes_dir: Path,
    constraints: Path | None,
) -> str:
    constraints_line = (
        f"Read and follow {constraints}." if constraints is not None else "Keep the change small and verifiable."
    )
    return (
        f"Turn {turn}/{turns} IMPLEMENT.\n"
        f"Workdir: {workdir}\n"
        f"Overall goal: {goal}\n"
        f"{constraints_line}\n"
        f"Make ONE focused improvement toward the goal "
        f"(different from earlier turns if any).\n"
        f"Verify somehow. Write {notes_dir / f'TURN{turn}_RESULT.md'} "
        f"(what/why/how verified). Do not commit."
    )


def review_prompt(
    *,
    turn: int,
    turns: int,
    goal: str,
    workdir: Path,
    notes_dir: Path,
) -> str:
    return (
        f"Turn {turn}/{turns} REVIEW.\n"
        f"Workdir: {workdir}\n"
        f"Overall goal: {goal}\n"
        f"Review the current uncommitted work (git diff / new files).\n"
        f"Write concrete fix/improvement instructions to "
        f"{notes_dir / f'TURN{turn}_REVIEW.md'} (under 20 lines).\n"
        f"Do not edit repository files yourself."
    )


def apply_prompt(
    *,
    turn: int,
    turns: int,
    notes_dir: Path,
) -> str:
    return (
        f"Turn {turn}/{turns} APPLY.\n"
        f"Read {notes_dir / f'TURN{turn}_REVIEW.md'} and apply needed fixes.\n"
        f"Update {notes_dir / f'TURN{turn}_RESULT.md'} with verification.\n"
        f"Do not commit."
    )


def render_summary(records: list[TurnRecord], *, goal: str, notes_dir: Path) -> str:
    lines = [
        "# Agent turns summary",
        "",
        f"Goal: {goal}",
        f"Turns: {len(records)}",
        f"Notes: {notes_dir}",
        "",
    ]
    for rec in records:
        lines.append(f"## Turn {rec.number}")
        lines.append("")
        result = read_text(rec.result_path) or "_(missing TURN{n}_RESULT.md)_".replace(
            "{n}", str(rec.number)
        )
        review = read_text(rec.review_path) or "_(missing TURN{n}_REVIEW.md)_".replace(
            "{n}", str(rec.number)
        )
        lines.append("### Implement / apply result")
        lines.append("")
        lines.append(result.rstrip())
        lines.append("")
        lines.append("### Review instructions")
        lines.append("")
        lines.append(review.rstrip())
        lines.append("")
        if rec.notes:
            lines.append("### Runner notes")
            lines.append("")
            for note in rec.notes:
                lines.append(f"- {note}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
            # Prompt may have been accepted but status stayed idle briefly.
            if idle_ticks == 8:
                try:
                    agent_send_keys(herdr, target, "enter")
                except RuntimeError:
                    pass
            if idle_ticks >= DEFAULT_IDLE_GRACE and not saw_work:
                # Re-focus and accept idle completion for already-done UIs.
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
    if args.turns < 1:
        print("--turns must be >= 1", file=sys.stderr)
        return 2

    workdir = (args.workdir or Path.cwd()).resolve()
    notes_dir = args.notes_dir.expanduser().resolve()
    ensure_notes_dir(notes_dir)
    constraints = args.constraints.expanduser().resolve() if args.constraints else None

    records: list[TurnRecord] = []
    for turn in range(1, args.turns + 1):
        rec = TurnRecord(
            number=turn,
            implement_prompt=implement_prompt(
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
            apply_prompt=apply_prompt(
                turn=turn,
                turns=args.turns,
                notes_dir=notes_dir,
            ),
            result_path=notes_dir / f"TURN{turn}_RESULT.md",
            review_path=notes_dir / f"TURN{turn}_REVIEW.md",
        )
        write_skeleton(rec.result_path, f"Turn {turn} result")
        write_skeleton(rec.review_path, f"Turn {turn} review")

        print(f"======== TURN {turn}/{args.turns}: implement ========", flush=True)
        if args.dry_run:
            print(rec.implement_prompt)
            rec.notes.append("dry-run: skipped herdr calls")
        else:
            prompt_and_wait(
                args.herdr,
                args.coder,
                rec.implement_prompt,
                timeout_ms=args.timeout_ms,
            )

        print(f"======== TURN {turn}/{args.turns}: review ========", flush=True)
        if args.dry_run:
            print(rec.review_prompt)
        else:
            prompt_and_wait(
                args.herdr,
                args.reviewer,
                rec.review_prompt,
                timeout_ms=args.timeout_ms,
            )

        print(f"======== TURN {turn}/{args.turns}: apply ========", flush=True)
        if args.dry_run:
            print(rec.apply_prompt)
        else:
            prompt_and_wait(
                args.herdr,
                args.coder,
                rec.apply_prompt,
                timeout_ms=args.timeout_ms,
            )

        records.append(rec)

    summary_path = notes_dir / "SUMMARY.md"
    summary = render_summary(records, goal=args.goal, notes_dir=notes_dir)
    summary_path.write_text(summary, encoding="utf-8")
    print(f"======== SUMMARY written: {summary_path} ========", flush=True)
    print(summary)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_turns(args)
    except (RuntimeError, TimeoutError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
