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

- リーダー 1 名 + 部下（reports）最大 7 名（合計最大 8 ペイン）
- **部下の役割は固定しない**（名前は身分だけ。毎回リーダーが会社組織図（下記）から `ROLE` を割り当てる）
- 流れ: 部下の TUI を読む → リーダーへ渡す → `NEXT` / `ROLE` / `MODE` / `INSTRUCTION` / `STATUS` → 指名した部下へ投入
- **書き込みは直列・読み取りは並列**: 1 ステップ（ウェーブ）内で、ファイルを編集する役割（開発部など）は**1 人ずつ順番に**、編集しない役割（レビュー・テスト実行・調査など）は**同時に**動く。例: 「agent-a が次の機能を実装」しながら「agent-b が前ステップの実装をレビュー」「agent-c が次タスクを調査」
- 1 ターンのステップ数は既定で `max(部下数, 4)`（`--steps-per-turn` で 1〜12）。部下数で頭打ちにならない
- ステップ 2 以降は直前ステップ（全メンバー分）の要約（prior handoff）を次へ渡す

```text
部下ペイン (最大7) -- read --> リーダー -- NEXT/ROLE/MODE/INSTRUCTION --> 部下
                                           書き込み役: 直列（1 人ずつ）
                                           読み取り役: 並列（書き込み役とも同時）
                                      \-- prior handoff (前ステップ要約) --/
```

### 会社組織図（ROLE に使うキー）

| 部署 | キー / 役割 | 種別 |
| --- | --- | --- |
| 経営企画部 | `plan.requirements` 要件定義 / `plan.breakdown` タスク分解 | 読み取り（並列） |
| 調査部 | `research.codebase` コード調査 / `research.root-cause` 原因調査 / `research.tech` 技術調査 | 読み取り（並列） |
| 設計部 | `design.architecture` アーキテクト / `design.interface` IF設計 / `design.ux` UI/UX設計 | 読み取り（並列） |
| 開発部 | `dev.implement` 実装 / `dev.bugfix` バグ修正 / `dev.refactor` リファクタ / `dev.test-impl` テスト実装 | **書き込み（直列）** |
| 品質保証部 | `qa.review` コードレビュー / `qa.test-run` テスト実行 / `qa.acceptance` 受け入れ確認 | 読み取り（並列） |
| セキュリティ室 | `sec.audit` セキュリティ監査 | 読み取り（並列） |
| 運用・インフラ部 | `ops.build` ビルド/CI確認 / `ops.perf` 性能計測 | 読み取り（並列） |
| ドキュメント部 | `docs.write` ドキュメント作成 | **書き込み（直列）** |
| ドキュメント部 | `docs.review` 文書校閲 | 読み取り（並列） |

`ROLE` はキーのほか役割名（`コードレビュー`）、`部署/役割`（`開発部/実装`）でも通じます。組織図にない自由記述の役割は、`MODE: read` を付けない限り**書き込み（直列）扱い**です（安全側）。組織図で書き込みの役割に `MODE: read` を付けても直列のままです。

読み取り役には「作業フォルダのファイルを編集しない」指示が付きます（ビルド・テスト実行は可）。編集が必要な作業は開発部の役割で割り当ててください。

**読み取り役のスナップショット**: 書き込み役と読み取り役が同じステップで動くとき、作業フォルダが git リポジトリなら、ステップ開始時点の状態（未コミットの変更と、.gitignore 対象外の未追跡ファイルを含む）を一時フォルダ（`$TMPDIR/herdr-turns-snapshots/`）に git worktree として作り、読み取り役にはそちらを見させます。書き込み役の編集途中の状態を読まずに済み、テストも安定します。ステップ終了時に削除します。無効にするには `--no-reader-snapshot`。

### 部下の報告と失敗の扱い

- 部下は結果を `hub-notes/TURN{n}_WORKER_{名前}_STEP{k}_REPORT.md` に書き、ランナーはそのファイルを優先して読みます（書かれなかった場合は画面の末尾）。画面から流れた結論を取りこぼしません。
- 部下がタイムアウト・エラーになってもハブは止まりません。その部下の結果は `(FAILED: …)` としてリーダーに渡り、リーダーが再割り当て・分割・中止を判断します。同じステップで後に控えていた書き込み役は `(SKIPPED …)` になり、実行されません。
- リーダー自身がタイムアウトした場合はハブを終了します。

### 停止と通知

- boss ペインの右クリック **ターン停止**（CLI: `herdr-turns turn-stop`）で実行中のハブを止めます。作業中の部下はそのまま残るので、必要なら各ペインで中断してください。
- ハブの開始（チーム起動）・終了・停止・エラー、「ターン制を開始...」の失敗は Herdr の通知で表示されます。

自己進化の `--from-here`（director/coder/reviewer ネスト）とは**別経路**です。

### いちばん簡単な始め方: 「ターン制を開始...」（チームを自動で作る）

1. 新しいタブ（ペイン 1 つ）でリーダーにしたい AI（Claude Code / Codex / Cursor など）を起動する
2. そのペインを右クリック → **ターン制を開始...**
3. 目的（goal）・ターン数（1〜10）・部下の人数（reports、1〜7）を入力して Enter

すると次を自動で行います。

- タブを `1 + 人数` 枚のペインに分割（2 段のグリッド）し、`boss` / `agent-a`〜 と命名
- 各部下ペインで**リーダーと同じ種類の AI** を `herdr agent start` で起動（並列）
- 全員の準備ができたら、そのままリーダーハブを開始（バックグラウンド）

部下に付く起動オプション（種類ごとの既定値。権限確認を省いて並列作業が止まらないようにするため）:

| AI | オプション |
| --- | --- |
| Cursor | `--yolo` |
| Claude Code | `--dangerously-skip-permissions` |
| Codex | `--full-auto`（サンドボックス内で自動承認） |
| Gemini / Qwen | `--yolo` |
| Copilot | `--allow-all-tools` |
| その他 | なし |

- これらは**確認なしでファイル操作やコマンド実行を行う**モードです。信頼できる作業フォルダでだけ使ってください。
- 初回起動時に AI 側の確認画面（フォルダの信頼、権限モードの同意など）が出た場合は、そのペインで手で答えてください。各部下は最大 5 分まで準備完了を待ちます。自動では承認しません。
- 準備できなかった部下がいるとハブは開始せず、作ったペイン（と起動した AI）を閉じて元の 1 ペインに戻し、通知で知らせます。経過とエラーは `hub-notes/TURN_SPAWN.log` に残ります。
- CLI では `herdr-turns turn-spawn 3,"目的" --reports 5`。`--agent-arg` を付けると既定オプションを置き換え、`--kind` で種類を指定できます。

### 手動で組む方法（右クリックメニュー）

スラッシュ付き `/turn-init` などはエージェントへの指示と誤解されやすいので、**ペイン右クリック**から起動してください。
右クリックに「自己進化ループ」は出ません（自己進化は CLI の `--from-here` のみ）。

1. **シングルペイン**のタブでペインを右クリック → **ターン制を初期化**
   - 2×2 分割 + 既定名 `boss, agent-a, agent-b, agent-c`
   - この段階では「ターン開始...」は出ません
2. 各ペインで AI を起動（命名は init 済み。`/turn-run` 相当は bind で揃える）
3. **boss** ペインだけ右クリック → **ターン開始...** → 目的とターン数を入力
   - agent-a/b/c にはターン開始も自己進化も出ません

CLI（スラッシュ無し）でも同じことができます:

```bash
herdr-turns turn-init
# boss ペインの環境で:
herdr-turns turn-run 3,"ここに目的"
```

### `/turn-init` — 分割と名前付け

| 項目 | 内容 |
| --- | --- |
| 前提 | **現在タブがシングルペインのみ** |
| 引数なし | `boss,agent-a,agent-b,agent-c` |
| 数字のみ | `turn-init 6` → `boss,agent-a`〜`agent-e`（2〜8） |
| 動作 | 名前数に合わせて 2 段のグリッドに分割（4 なら 2×2、6 なら 3×2、8 なら 4×2。列幅は均等）→ 視覚順（上→下・左→右）で `pane rename`（agent がいれば `agent rename` も） |
| dry-run | 分割・改名はしない |

```bash
herdr-turns /turn-init
herdr-turns turn-init boss,agent-a,agent-b      # 3 名にしたいとき
herdr-turns turn-init 8                         # boss + 部下 7 名（4×2）
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
| `--participant` | 部下プール（1〜7。リーダーは含めない） |
| `--order` | 訪問順のヒント（実順はリーダーの `NEXT` が優先） |
| `--steps-per-turn` | 1 ターンのリーダーステップ数（既定 `max(部下数, 4)`、上限 12） |

### リーダーが画面に出す形式

返答の 1 行目には、ランナーが指示するステップ識別行（例: `HUB-DIRECTIVE T1-S2`）を単独で書きます。ランナーは**この行より後ろだけ**を読むので、画面に残った前ステップの返答や、指示文に含まれる書式例を誤って拾いません。識別行がない場合は 1 回だけ書式の再送を求め、それでも無ければ画面全体から読み取ります（`TURN*_HUB.md` に `MARKER_MISSING` と記録）。

```text
HUB-DIRECTIVE T1-S2
NEXT: agent-a
ROLE: dev.implement
INSTRUCTION: 設計どおりに API ハンドラを実装する
NEXT: agent-b
ROLE: qa.review
INSTRUCTION: 前ステップで実装した認証処理をレビューする
NEXT: agent-c
ROLE: research.codebase
INSTRUCTION: 次に触る画面のコードを洗い出す
STATUS: CONTINUE
```

→ agent-a（書き込み）を実行しながら、agent-b と agent-c（読み取り）が同時に動きます。書き込み役が 2 人以上いれば、書いた順に 1 人ずつ実行されます。

| フィールド | 必須 | 意味 |
| --- | --- | --- |
| `NEXT` | 推奨 | report pool 内の名前。カンマ区切り（例: `agent-a, agent-b`）か NEXT ブロック複数でウェーブ。**省略時のみ** `--order` の default（1 人）。pool 外は 1 回再送、それでも不正なら **fail** |
| `ROLE` | 推奨 | 組織図のキー（`qa.review` など）または短い役割名。pane ラベルが `AI/役割(部署)` になる |
| `MODE` | 任意 | `read` / `write`。組織図にない役割で並列にしたいときに `read` を付ける |
| `INSTRUCTION` | 推奨 | そのステップの作業内容（複数行可） |
| `STATUS` | 推奨 | `CONTINUE` / `DONE`（目的達成、`COMPLETE.md` を書く）/ `STOP` / `ESCALATE`（`NEEDS_OWNER.md` を書く） |

### pane→agent bind

`/turn-init` は分割直後に **pane ラベル**を付ける（agent 未起動なら agent rename はスキップ）。各ペインで AI を起動したあと `/turn-run` が **bind** し、pane ラベルを生きている agent 名へ揃える。名前解決は agent 名優先、無ければ pane ラベル。

### 実行中のペイン表示名（AI/役割）

ハブ実行中、部下ペインの **pane ラベル**は検出された AI 種別に役割を付けた形になります（例: `cursor/検証役`、`claude/実装`）。

| 時点 | 表示 |
| --- | --- |
| turn-init / 待機中 | `agent-a` / `agent-b` / `agent-c`（boss は `boss`） |
| turn-run 開始直後 | まず `cursor` のように **AI 種別のみ** |
| リーダーが `ROLE:` を任命したステップ | `cursor/検証役` のように **AI/役割** |
| ハブ終了（成功・中断・例外） | 再び `agent-a` / `agent-b` / `agent-c`（と `boss`） |

- `NEXT:` は常にスロット名（`agent-a` など）。表示ラベルは変えてもルーティング名は変えない
- agent rename は英数字のみなので、スラッシュ付き表示は **pane ラベル**側に載せる

### 直前手渡し（prior handoff）

同じターンのステップ 2 以降、次の部下の assignment に直前ステップの全メンバーの名前・ROLE・MODE・画面末尾の要約を付ける（並列ウェーブでも最後の 1 人だけにならないよう、メンバーごとに均等に切り詰める）。ステップ 1 は `_(なし)_`。

`TURN*_HUB.md` はステップごとに書き出されるため、途中でタイムアウトしてもそこまでの記録が残ります。

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
| 操作 | 番号付き Yes なら `1`+Enter。`[Y/n]` なら `y`+Enter（Esc は送らない） |
| 自動承認しないもの | `rm -rf`、`git push --force`、`git reset --hard`、`git clean -f`、`DROP TABLE`、`sudo`、`--no-verify`、`terraform apply/destroy`、`kubectl delete` などを含む確認。ログに警告を出し、手動の回答を待つ |
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
| AI 起動済みの 1 ペインからチームを自動作成して開始 | 右クリック「ターン制を開始...」または `herdr-turns turn-spawn 3,"目的" --reports 3` |
| シングルペインから 2×2 + 命名（AI は手動起動） | 右クリック「ターン制を初期化」または `herdr-turns turn-init` |
| リーダーハブ開始 | boss 右クリック「ターン開始...」または `herdr-turns turn-run 3,"目的"` |
| リーダーハブ停止 | boss 右クリック「ターン停止」または `herdr-turns turn-stop` |
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
- 並列で動く読み取り役は作業フォルダを共有している。編集しない指示は AI への指示であり強制ではないため、編集を伴う作業は必ず開発部（書き込み）の役割で割り当てる。
- ランナーは作業中・確認待ちのエージェントに Esc を送らない（作業の中断や確認ダイアログの拒否を防ぐ）。
- 右クリックの「ターン開始...」は従来どおり `boss` という名前のペインにだけ出る。
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
