# kuwa2005/herdr 独自機能ガイド

このドキュメントは、upstream [herdrdev/herdr](https://github.com/herdrdev/herdr) にはなく、本フォーク（[`kuwa2005/herdr`](https://github.com/kuwa2005/herdr)）が追加・拡張した機能の**使い方**です。運用メモの全体像は [`FORK.md`](./FORK.md) を参照してください。

対象ランナー: `scripts/herdr-turns` → `scripts/herdr_agent_turns.py`

```bash
# 推奨: 公式インストーラ（herdr 本体 + herdr-turns 一式）
curl -fsSL https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.sh | sh

# またはリポジトリ checkout から手動
install -m 755 scripts/herdr-turns ~/.local/bin/herdr-turns
install -m 755 scripts/herdr_agent_turns.py ~/.local/bin/herdr_agent_turns.py
install -m 644 scripts/herdr_turns_constraints.default.md ~/.local/bin/herdr_turns_constraints.default.md
```

Herdr 管理ペイン内では `HERDR_ENV=1` / `HERDR_PANE_ID` が付きます。ハブ系コマンドは原則その環境で実行します。

---

## 1. リーダーハブ（役割非固定の相互指示）

### 何ができるか

- リーダー 1 名 + 部下（reports）最大 3 名（合計最大 4）
- **部下の役割は固定しない**（名前は身分だけ。毎回リーダーが `ROLE` / `INSTRUCTION` で役割と作業を割り当てる）
- 流れ: 部下の TUI を読む → リーダーへ渡す → `NEXT` / `ROLE` / `INSTRUCTION` / `STATUS` → 指名した部下へ投入
- ステップ 2 以降は直前部下の要約（prior handoff）を次の部下へ渡す

```text
部下ペイン (最大3) -- read --> リーダー -- NEXT/ROLE/INSTRUCTION --> 次の部下
                                      \-- prior handoff (前ステップ要約) --/
```

自己進化の `--from-here`（director/coder/reviewer ネスト）とは**別経路**です。

### クイックスタート

1. **シングルペイン**のタブにいる（既に分割済みだと `/turn-init` は拒否）
2. 各ペインで使う AI は、分割後に手動起動してよい（命名は init が行う）
3. 初期化 → ハブ開始:

```bash
# シングルペインから 2x2 分割 + 既定名を付与
# 既定: boss, agent-a, agent-b, agent-c（左上→右下）
herdr-turns /turn-init

# リーダーペインにフォーカスした状態で
herdr-turns /turn-run 3,"ここに目的"
```

### `/turn-init` — 分割と名前付け

| 項目 | 内容 |
| --- | --- |
| 前提 | **現在タブがシングルペインのみ** |
| 引数なし | `boss,agent-a,agent-b,agent-c` |
| 動作 | 名前数に合わせて分割（4 なら 2×2）→ 視覚順（上→下・左→右）で `pane rename`（agent がいれば `agent rename` も） |
| dry-run | 分割・改名はしない |

```bash
herdr-turns /turn-init
herdr-turns turn-init boss,agent-a,agent-b      # 3 名にしたいとき
herdr-turns turn-init --dry-run                 # 確認のみ
```

### `/turn-run` — ハブ起動

リーダーペイン内で実行します。

| 自動割当 | 内容 |
| --- | --- |
| bind | 起動前に pane ラベル → 生きている agent へ `agent rename` を再適用 |
| `--leader` | 現在ペインの名前（agent 名、無ければ pane ラベル） |
| `--participant` | 同じタブの他ペイン（最大 3。agent 名優先、なければ pane ラベル） |
| `--turns` / `--goal` | 引数の `TURNS,"goal"` |
| その他既定 | `--daemon`、`--notes-dir ./hub-notes`、`--workdir "$PWD"` |

```bash
herdr-turns /turn-run 3,"リリース判定まで進める"
herdr-turns turn-run 3,"リリース判定まで進める"
herdr-turns /turn-run --dry-run 3,"demo"   # 割当確認のみ
```

長形式（同等）:

```bash
herdr-turns \
  --leader boss \
  --participant agent-a \
  --participant agent-b \
  --participant agent-c \
  --turns 3 \
  --goal "リリース判定まで進める" \
  --notes-dir ./hub-notes \
  --workdir "$PWD"
```

| フラグ | 意味 |
| --- | --- |
| `--leader` | ハブ役 |
| `--participant` | 部下プール（1〜3。リーダーは含めない） |
| `--order` | 訪問順のヒント（実順はリーダーの `NEXT` が優先） |

### リーダーが画面に出す形式

```text
NEXT: agent-b
ROLE: 検証役
INSTRUCTION: 差分を見て問題を列挙して
STATUS: CONTINUE
```

| フィールド | 必須 | 意味 |
| --- | --- | --- |
| `NEXT` | 推奨 | report pool 内の名前。**省略時のみ** `--order` の default を使う。pool 外の名前は **警告のうえ fail**（default へフォールバックしない） |
| `ROLE` | 任意 | 短い役割ラベル。worker prompt / `TURN*_HUB` / worker notes に記録。INSTRUCTION 先頭に役割が無ければ `ROLE: …` を前置して部下へ渡す |
| `INSTRUCTION` | 推奨 | そのステップの作業内容 |
| `STATUS` | 推奨 | `CONTINUE` / `DONE` / `STOP` / `ESCALATE` |

### pane→agent bind

`/turn-init` は分割直後に **pane ラベル**を付ける（agent 未起動なら agent rename はスキップ）。各ペインで AI を起動したあと `/turn-run` が **bind** し、pane ラベルを生きている agent 名へ揃える。名前解決は agent 名優先、無ければ pane ラベル。

### 直前手渡し（prior handoff）

同じターンのステップ 2 以降、次の部下の assignment に直前部下の名前・ROLE・要約（notes 優先、なければ画面）を付ける。ステップ 1 は `_(なし)_`。

成果物は `notes-dir` の `TURN*_HUB.md` / `TURN*_LEADER_STEP*.md` / `TURN*_WORKER_*` など。

---

## 2. `/auto-yes` — 確認ダイアログの自動 Yes

**既定はオフ。** 有効にすると、エージェントが次のような確認で止まったとき自動で Yes を選びます。

```text
Parser skipped input between top-level statements

Do you want to proceed?
❯ 1. Yes
  2. No
```

```bash
herdr-turns /auto-yes          # 有効化（バックグラウンド watcher）
herdr-turns /auto-yes          # もう一度で無効化
herdr-turns auto-yes status    # 状態確認
```

| 項目 | 内容 |
| --- | --- |
| 操作 | 番号付き Yes なら `1`+Enter。`[Y/n]` なら `y`+Enter |
| 状態ファイル | `~/.config/herdr/auto-yes.json` |
| ログ | `~/.config/herdr/auto-yes.log` |

リーダーハブや自己進化の実行中に確認で止まる場合に併用できます。不要になったら必ず OFF にしてください。

---

## 3. 自己進化ループ（`--from-here`）

ネスト Herdr を隣ペインに立ち上げ、2×2 で director / coder / reviewer を回す公式ワークフローです（最大 10 ターン）。

```bash
# Herdr 管理ペイン内
herdr-turns --from-here --daemon --turns 5 \
  --goal "エラー処理を改善する" \
  --workdir "$PWD"
```

- 進捗: `tail -f ./herdr-turns-notes/runner.log`
- 終了後: `自己改善yyyymmddhhmmss.md` / `notes-dir/SUMMARY.md`（成功時は `COMPLETE.md`）
- 再開: `--resume --notes-dir ...`

詳細（VERDICT、stall、constraints、webhook など）は [`FORK.md`](./FORK.md) の「マルチエージェント自動化」を参照。

---

## 4. よく使うコマンド早見表

| やりたいこと | コマンド |
| --- | --- |
| シングルペインから 2×2 + 命名 | `herdr-turns /turn-init` |
| リーダーハブ開始 | `herdr-turns /turn-run 3,"目的"` |
| 確認を自動 Yes | `herdr-turns /auto-yes` |
| auto-yes 状態 | `herdr-turns auto-yes status` |
| ネスト自己進化 | `herdr-turns --from-here --daemon --turns N --goal "..." --workdir "$PWD"` |
| 単体テスト | `python3 -m unittest scripts.test_herdr_agent_turns -q` |

---

## 5. 注意事項

- ペイン同士が直接チャットする配線はない。ランナーが `agent read` / `agent prompt` で仲介する（prior handoff もランナー経由）。
- `/turn-init` は**分割済みタブでは動かない**（シングルペイン専用）。
- `/turn-run` 前に各ペインで AI を起動する。bind が pane ラベルと agent 名を揃える（手動 `herdr agent rename` も可）。
- リーダーの `NEXT` は report pool 内のみ。未知名は fail（default NEXT へ落とさない）。
- 前景でリーダー自身を待ち続けるとデッドロックしやすい。`/turn-run` と `--from-here` は daemon 前提。
- upstream への機能 Issue / 実装 PR は出さない（フォーク所有者運用。詳細は `FORK.md` / `AGENTS.md`）。

---

## 関連ファイル

| パス | 役割 |
| --- | --- |
| `scripts/herdr-turns` | PATH 用ランチャー |
| `scripts/herdr_agent_turns.py` | 実装本体 |
| `scripts/test_herdr_agent_turns.py` | 単体テスト |
| `scripts/herdr_turns_constraints.default.md` | 自己進化の既定制約 |
| `FORK.md` | フォーク運用の総合メモ |
