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
ネスト session 上で coder / reviewer が回り、終了後に呼び出し元へサマリーが届く。

## 前提（エージェント CLI）

```bash
test "${HERDR_ENV:-}" = 1
```

失敗したら Herdr 管理ペイン外である旨を伝えて停止。N は **1〜10**。それ以上や無制限は拒否。

## 既定動作（ネスト + coder/reviewer）

`--from-here` は隣ペインにネスト Herdr を立ち上げ、その中で **coder** と **reviewer** の 2 エージェントを起動してターンを回す。

## 起動（デッドロック回避）

このエージェント自身を前景で同期実行しない。ランナーがプロンプトを送るため、待ち続けるとデッドロックする。

1. 会話から短い `--goal` を決める（不明なら一度だけ確認）
2. バックグラウンド起動:

```bash
herdr-turns --from-here --daemon --turns N --goal "SHORT GOAL" --workdir "$PWD"
# 既定: kind=cursor、エージェント引数 --yolo
# 任意: --agent-arg=--trust
# ネストを残したいときだけ: --keep-nested
# 旧の同一ペイン自己レビュー: --self
```

3. JSON（`pid` / `log` / `notes_dir`）を読む
4. 開始したこと、進捗は `runner.log`、終了後は `自己改善yyyymmddhhmmss.md` で効果判定できることを伝える
5. ネストセッション名はログの `nested session=` 行。終了後は呼び出し元エージェントへ全ターンサマリーを送り、ネスト session / outer pane は削除する（残す場合は `--keep-nested`）
6. **生成を止めて idle になる**（以降ランナーが INSTRUCT / FIX / REVIEW を送る）

## 各ターン

1. INSTRUCT → `TURN{n}_PLAN.md`（`TASK` など）— planner（既定: coder）
2. FIX → `TURN{n}_RESULT.md`（`DONE` / `VERIFIED`）— coder
3. REVIEW → `VERDICT` / `IMPROVE` / `EFFECT` — reviewer
4. `REVISE` のときだけ APPLY — coder
5. 次の INSTRUCT が直前レビューを読む

早期終了: `VERDICT: DONE` または `STATUS: DONE`

## 効果判定レポート

終了時（画面 + ファイル）:

- `<workdir>/自己改善yyyymmddhhmmss.md`
- `<notes_dir>/SUMMARY.md`

含む内容: 大元の指示、自動効果判定、ターン一覧（指示 / できたこと / レビュー改善）、詳細。

進捗: `tail -f <notes_dir>/runner.log`
