---
name: herdr-self-evolve
description: >-
  Start an N-turn Herdr self-evolve loop (instruct → fix → review) from the
  current agent pane. Use when the user asks to self-improve for N turns,
  run agent turns from here, or ここからNターン自己改善.
---

# Herdr self-evolve from here

ユーザーが「ここから N ターン自己改善して」「from here, N turns of self-evolve」などと頼んだとき。

## 前提

```bash
test "${HERDR_ENV:-}" = 1
```

失敗したら Herdr 管理ペイン外である旨を伝えて停止。N は **1〜10**。それ以上や無制限は拒否。

## 起動（デッドロック回避）

このエージェント自身を前景で同期実行しない。ランナーが同じペインへ `agent prompt` するため、待ち続けるとデッドロックする。

1. 会話から短い `--goal` を決める（不明なら一度だけ確認）
2. バックグラウンド起動:

```bash
herdr-turns --from-here --daemon --turns N --goal "SHORT GOAL" --workdir "$PWD"
# または: just agent-turns --from-here --daemon --turns N --goal "SHORT GOAL" --workdir "$PWD"
```

3. JSON（`pid` / `log` / `notes_dir`）を読む
4. 開始したこと、進捗は `runner.log`、終了後は `自己改善yyyymmddhhmmss.md` で効果判定できることを伝える
5. **生成を止めて idle になる**（以降ランナーが INSTRUCT / FIX / REVIEW を送る）

## 各ターン

1. INSTRUCT → `TURN{n}_PLAN.md`（`TASK` など）
2. FIX → `TURN{n}_RESULT.md`（`DONE` / `VERIFIED`）
3. REVIEW → `VERDICT` / `IMPROVE` / `EFFECT`
4. `REVISE` のときだけ APPLY
5. 次の INSTRUCT が直前レビューを読む

早期終了: `VERDICT: DONE` または `STATUS: DONE`

## 効果判定レポート

終了時（画面 + ファイル）:

- `<workdir>/自己改善yyyymmddhhmmss.md`
- `<notes_dir>/SUMMARY.md`

含む内容: 大元の指示、自動効果判定、ターン一覧（指示 / できたこと / レビュー改善）、詳細。

進捗: `tail -f <notes_dir>/runner.log`  
レビュー役を分ける: `--reviewer <name>`
