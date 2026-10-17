---
name: herdr-self-evolve
description: >-
  Start an N-turn Herdr self-evolve loop (instruct → fix → review) from the
  current agent pane. Use when the user asks to self-improve for N turns,
  run agent turns from here, or ここからNターン自己改善.
---

# Herdr self-evolve from here

ユーザーが「ここから N ターン自己改善して」「from here, N turns of self-evolve」などと頼んだとき。

## 人間向け（UI）

ペインを右クリック → **ターン制を開始...** → goal / turns（既定 5）を入力して開始。  
ネスト session の 2x2 上で director / coder / reviewer が回り、終了後に呼び出し元へサマリーが届く。

## 前提（エージェント CLI）

```bash
test "${HERDR_ENV:-}" = 1
```

失敗したら Herdr 管理ペイン外である旨を伝えて停止。N は **1〜10**。それ以上や無制限は拒否。

## 既定動作（ネスト 2x2 + director/coder/reviewer）

`--from-here` は隣ペインにネスト Herdr を立ち上げ、その中を **2x2** に分割して **director**（計画）/ **coder**（実装）/ **reviewer**（レビュー）を起動する（右下 spare はシェルのみ）。

## 起動（デッドロック回避）

このエージェント自身を前景で同期実行しない。ランナーがプロンプトを送るため、待ち続けるとデッドロックする。

1. 会話から短い `--goal` を決める（不明なら一度だけ確認）。長い受け入れ条件は `--goal-file` / `--acceptance-file` / `--task-pack` を使う
2. バックグラウンド起動:

```bash
# 基本
herdr-turns --from-here --daemon --turns N --goal "SHORT GOAL" --workdir "$PWD"

# AI駆動例（task ファイル + テスト添付 + コスト分割）
herdr-turns --from-here --daemon --turns N \
  --goal-file ./goal.md --acceptance-file ./acceptance.md \
  --test-command "python3 -m unittest scripts.test_herdr_agent_turns -q" \
  --coder-arg=--yolo \
  --reviewer-arg=--model --reviewer-arg composer-2.5 \
  --workdir "$PWD"

# 既定: kind=cursor、共有 --agent-arg 未指定時は --yolo
# 任意: --agent-arg=--trust / --notify-webhook URL / --no-default-constraints
# ネストを残したいときだけ: --keep-nested
# 旧の同一ペイン自己レビュー: --self
```

3. JSON（`pid` / `log` / `notes_dir`）を読む
4. 開始したこと、進捗は `runner.log`、終了後は `自己改善yyyymmddhhmmss.md` / `COMPLETE.md` で効果判定できることを伝える
5. ネストセッション名はログの `nested session=` 行。終了後は呼び出し元エージェントへ全ターンサマリーを送り、ネスト session / outer pane は削除する（残す場合は `--keep-nested`）
6. **生成を止めて idle になる**（以降ランナーが INSTRUCT / FIX / REVIEW を送る）

## 各ターン

1. INSTRUCT → `TURN{n}_PLAN.md`（`TASK` / `DONE_WHEN` など）— director（`--planner` で上書き可）。`STATUS: ESCALATE` 可。acceptance があれば DONE_WHEN 整合を促す
2. FIX → `TURN{n}_RESULT.md`（`DONE` / `VERIFIED` / `FILES`）— coder。`VERIFIED` は具体コマンド必須（曖昧な「looks good」等は不可。コード変更時は RESULT 前に該当テストを実行）
3. REVIEW → `VERDICT` / `IMPROVE` / `EFFECT` — reviewer。`DONE_WHEN` 未達や弱い/欠落 `VERIFIED` なら **REVISE** 優先。オーナー判断が必要なら **`VERDICT: ESCALATE`**。FIX 後（weak VERIFIED re-ask 後含む）に **state pack**（`notes-dir/TURN{n}_STATE.txt`）を書き、REVIEW に注入（git status / diff 要約 / truncated diff / 任意の `--test-command` 出力）
4. `REVISE` のときだけ APPLY — coder
5. 次の INSTRUCT が直前レビューを読む

早期終了: `VERDICT: DONE|STOP|ESCALATE`、または planner の `STATUS: DONE|STOP|ESCALATE`。成功時（`DONE`、または goal 達成を明示した `STOP`）は `notes-dir/COMPLETE.md`（goal / outcome / SUMMARY・自己改善レポートへのポインタ）。`ESCALATE` 時は `notes-dir/NEEDS_OWNER.md`（goal / turn / why / resume 手順）。stall・ターン上限のみでは COMPLETE は書かない。

## オーケストレータ（wave 2 + wave 3）

ランナーが強制するガード（エージェントは意識しなくてよいが、止まる理由の判別に使う）:

- **Weak VERIFIED** — FIX 後に `VERIFIED` が弱いと coder へ最大1回再ask。なお弱いと REVIEW に prefer-REVISE note
- **Stall（同じ TASK）** — 前ターンと同じ正規化 `TASK` の継続 PLAN → FIX 前に停止 + `NEEDS_OWNER.md`（方針/goal の見直しが必要）
- **Owner reply** — ESCALATE 後の再開で補足を渡す（下記 Resume）
- **Default constraints（wave 3）** — `--constraints` 未指定時はバンドル `scripts/herdr_turns_constraints.default.md` を always-on で言及。オフは `--no-default-constraints`
- **Task pack（wave 3）** — `--task-pack`（YAML/md）または `--goal-file` + `--acceptance-file`。優先: `--goal` > `--goal-file` > pack の goal
- **Per-role args（wave 3）** — `--planner-arg` / `--coder-arg` / `--reviewer-arg` は共有 `--agent-arg` を置き換え（マージしない）
- **Webhook（wave 3）** — `--notify-webhook` または `HERDR_TURNS_WEBHOOK`。終端で `event`: `complete` | `escalate` | `stop`（失敗は warning のみ）

`NEEDS_OWNER.md` の Why が **repeated TASK / stall** なら「同じ作業の繰り返し」なので goal や方針を変える。単なる判断待ち（A vs B など）なら下記の owner reply で答えを渡して resume。

## Resume

オーナー判断後、同じ notes-dir から再開する。

- `--resume --notes-dir <dir>` が必須。`--goal` は省略可（`run.json` → `NEEDS_OWNER.md` の順）
- `--turns` は **再開後の開始ターンから** の上限（例: start=3, `--turns 2` → ターン 3–4）
- オーナー補足: `notes-dir/OWNER_REPLY.md` を書くか `--owner-reply "..."`（CLI 優先）。再開の先頭ターン INSTRUCT+FIX に一度だけ注入され、`run.json` の `owner_reply_sha256` / `OWNER_REPLY.consumed.md` で消費記録（同じ内容の再 resume では再注入しない）

```bash
herdr-turns --from-here --daemon --resume --notes-dir ./herdr-turns-notes --turns 3 --workdir "$PWD"
# 補足付き
herdr-turns --from-here --daemon --resume --notes-dir ./herdr-turns-notes --turns 3 \
  --workdir "$PWD" --owner-reply "Approach B; skip A"
```

## 効果判定レポート

終了時（画面 + ファイル）:

- `<workdir>/自己改善yyyymmddhhmmss.md`
- `<notes_dir>/SUMMARY.md`

含む内容: 大元の指示、自動効果判定（ESCALATE 時は「オーナー判断待ち」）、ターン一覧（指示 / できたこと / レビュー改善）、詳細。

進捗: `tail -f <notes_dir>/runner.log`。`COMPLETE.md` があれば goal 達成で終了（resume 不要）。`NEEDS_OWNER.md` があれば人間判断待ち（stall か判断待ちかは Why を読む）。
