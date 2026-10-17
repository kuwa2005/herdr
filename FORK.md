# このフォーク（kuwa2005/herdr）の内部運用

[`CONTRIBUTING.md`](./CONTRIBUTING.md) は upstream（`herdrdev/herdr`）向けの貢献ポリシーです。  
**このリポジトリでは upstream へ実装 PR を出す予定はありません。** 有用な upstream 更新は、必要に応じてこちらへ取り込みます。

以下は CONTRIBUTING の精神を、fork 内部向けに落としたものです。

## 所有者

- GitHub: `kuwa2005`
- リモート: `https://github.com/kuwa2005/herdr`
- `.github/MAINTAINERS` / `.github/APPROVED_CONTRIBUTORS` に fork 所有者を含める（このリポジトリ上の PR ゲート用）。upstream のメンテナ権限にはならない。

## 方針

1. **コードを理解する** — 変更の意図・境界・テストが何を保証するかを説明できること。
2. **変更は焦点を絞る** — 1 コミット / 1 PR 相当で 1 問題。無関係な掃除やリファクタを混ぜない。
3. **検証する** — コミット前にフックとチェックを通す。
4. **ドキュメント** — ユーザー向けの未リリース説明は `docs/next/`。この fork ではルート `README.md` を日本語メインにしてよい（upstream 同期時は衝突しうる）。
5. **upstream へ送らない** — Issue / Discussion / 実装 PR を `herdrdev/herdr` に勝手に開かない。取り込むのは fetch / merge（または rebase）側。

## セットアップ（一度だけ）

```bash
just install-hooks
```

Windows 向けクロスチェックを使う場合（任意）:

```bash
cargo install xwin --locked
just setup-windows-cross --accept-license
```

## コミット前

```bash
just ci          # PR 相当のチェック
# または
just check       # より重い（Windows lint 含む）
```

コミットメッセージは lowercase conventional commits（英語）。Issue 参照は `refs #<n>`（closing keywords は使わない）。

例:

```text
fix: treat host bs byte as backspace

refs #3244
```

## upstream の取り込み

```bash
git remote add upstream https://github.com/herdrdev/herdr.git   # 初回のみ
git fetch upstream
git merge upstream/master   # または rebase。方針に合わせて選択
```

衝突しやすい箇所の例: `README.md`、`.github/MAINTAINERS`、`.github/APPROVED_CONTRIBUTORS`、`distribution/install.*`、`distribution/latest.json` / `preview.json`、この `FORK.md`。

リリースバイナリは [`kuwa2005/herdr` Releases](https://github.com/kuwa2005/herdr/releases) から配布する。全 OS（linux / macos / windows）のアセットはこのリポジトリの Releases を指す。

### リリース手順（簡略）

1. `Cargo.toml` の `version` を上げてコミットし、`master` に push する。
2. どちらか一方:
   - `git tag vX.Y.Z && git push origin vX.Y.Z`
   - または GitHub Actions の **Fork Release** を `workflow_dispatch` で実行（`version=X.Y.Z`）
3. ワークフロー `.github/workflows/fork-release.yml` が全プラットフォームをビルドし、Release にアップロードし、`distribution/latest.json` を更新して `master` へ push する。

upstream の `release.yml` は `herdrdev/herdr` 専用のまま。この fork では使わない。

## ローカルインストール（ソース）

```bash
# Zig 0.16.0 と rust-toolchain.toml の Rust が必要
export ZIG="$HOME/.local/share/zig-0.16.0/zig"   # 例
cargo build --release --locked
install -m 755 target/release/herdr ~/.local/bin/herdr
# ターン制ランナー（任意; 両方入れる）
install -m 755 scripts/herdr-turns ~/.local/bin/herdr-turns
install -m 755 scripts/herdr_agent_turns.py ~/.local/bin/herdr_agent_turns.py
```

稼働中サーバーは古いプロセスのままなので、付け直しまたは再起動が必要。

## エージェント向け

1. まず [`AGENTS.md`](./AGENTS.md) とこのファイルを読む。
2. 認証アカウントが `kuwa2005` で、リモートが `kuwa2005/herdr` なら、**この fork 上の**実装・コミット・push は所有者作業として進めてよい。
3. `herdrdev/herdr` への実装 PR・機能 Issue は開かない（CONTRIBUTING / AGENTS の外部貢献ガードを維持）。
4. upstream 由来の再現バグを本家に報告する場合だけ、人間が CONTRIBUTING のバグテンプレート手順に従う。

## セッションジャーナル（`herdrlog.md`）

`[session] journal = true`（既定）のとき、次の両方に同じ内容を追記します。

1. セッションデータディレクトリ
2. Herdr サーバプロセスのカレントディレクトリ（`./herdrlog.md`）

| セッション | データディレクトリ例 | カレント例 |
| --- | --- | --- |
| default | `~/.config/herdr/herdrlog.md` | `./herdrlog.md` |
| 名前付き `demo` | `~/.config/herdr/sessions/demo/herdrlog.md` | `./herdrlog.md` |

記録内容:

1. **指示** — `herdr agent prompt` のテキスト、およびエージェント認識済みペインでの TUI 入力（Enter 確定時）
2. **完了** — エージェントが working/blocked → idle になったときの検出バッファ（または直近出力）レポート

サーバを入れ替えたあとは `herdr server stop` のうえ再起動しないと新コードは効きません。

無効化:

```toml
[session]
journal = false
```

## マルチエージェント自動化（自己進化）

Herdr 本体に「A→B 自動パイプ」はない。この fork の公式ワークフローは **最大 10 ターンの自己進化ループ**。

### 1 ターンの流れ

1. **INSTRUCT**（director）— `TURN{n}_PLAN.md`（`STATUS` / `TASK` / `DONE_WHEN`）。`STATUS: DONE|STOP|ESCALATE` 可
2. **FIX**（coder）— `TURN{n}_RESULT.md`（`DONE` / `VERIFIED` / `FILES`）
3. **REVIEW**（reviewer）— `TURN{n}_REVIEW.md`（`VERDICT` / `IMPROVE` / `EFFECT`）。`VERDICT: APPROVE|REVISE|DONE|STOP|ESCALATE`
4. **APPLY**（coder）— `VERDICT: REVISE` のときだけ
5. 次ターンの INSTRUCT が直前レビューを読み、さらなる指示を出す

制約: `--turns` は **1〜10**（既定 10）。早期終了は `VERDICT: DONE|STOP|ESCALATE`、または planner の `STATUS: DONE|STOP|ESCALATE`。

**COMPLETE.md vs NEEDS_OWNER.md:** 成功終了（`VERDICT: DONE` / planner `STATUS: DONE`、または goal 達成を明示した `STOP`）では `notes-dir/COMPLETE.md` を書く（owner はまずこれを読む）。`ESCALATE`・stall（同じ TASK）・ターン上限のみでは **書かず**、判断待ちは従来どおり `NEEDS_OWNER.md`（goal / turn / why / resume 手順）。両者は排他。

**Missing VERDICT:** レビューに `VERDICT:` 行が無いとき、オーナー判断を示す文言（例: needs owner / human judgment / `STATUS: Needs decision`）があれば **ESCALATE** 扱い。それ以外の中立文は従来どおり **APPROVE**（`resolve_review_verdict`）。

**検証期待:** FIX の `VERIFIED` は具体コマンド必須（曖昧な「looks good」等は禁止。コード変更時は RESULT 前に該当テストを実行）。REVIEW は `DONE_WHEN` 未達や弱い/欠落 `VERIFIED` なら **REVISE** を優先。

### 想定 UX: 「ここから N ターン自己改善して」

```bash
# Herdr 管理ペイン内（$HERDR_ENV=1 / $HERDR_PANE_ID）
herdr-turns --from-here --daemon --turns 5 --goal "エラー処理を改善する" --workdir "$PWD"
```

既定（`--from-here`）:

1. 隣ペインにネスト Herdr（名前付きセッション `turns-YYYYMMDDHHMMSS`）を起動
2. ネスト内を 2x2 に分割し、`director` / `coder` / `reviewer` を起動（右下 spare はシェル。`--kind` 既定 `cursor`）
3. INSTRUCT→director、FIX/APPLY→coder、REVIEW→reviewer でターンを回す

| フラグ | 意味 |
| --- | --- |
| `--from-here` | ネスト Herdr + 2x2 director/coder/reviewer を立ち上げて回す |
| `--self` | 旧挙動: 現在ペインのエージェントだけで自己レビュー |
| `--daemon` | バックグラウンド起動（前景待ちはデッドロックする） |
| `--kind` / `--agent-arg` | ネストエージェントの種別と共有追加引数（既定: `cursor` + `--yolo`） |
| `--planner-arg` / `--coder-arg` / `--reviewer-arg` | ロール専用 argv（非空なら `--agent-arg` を**置き換え**。`-` 始まりは `--coder-arg=--yolo` 形式） |
| `--goal-file` / `--acceptance-file` / `--task-pack` | goal / 受け入れ基準をファイルから読む（CLI `--goal` が最優先） |
| `--test-command` | FIX 後に実行し、exit / 出力を `TURN{n}_STATE.txt` と REVIEW に添付 |
| `--constraints` / `--no-default-constraints` | 制約ファイル上書き / バンドル default 言及をオフ |
| `--notify-webhook` | 終端で JSON POST（環境変数 `HERDR_TURNS_WEBHOOK` 可。CLI 優先） |
| `--keep-nested` | 終了後もネストセッションを残す（既定は stop/delete + outer pane を閉じる） |
| `--resume` | 既存 `--notes-dir` から中断/ESCALATE 後に再開（`--notes-dir` 必須） |
| `--owner-reply` | resume 時のみ。オーナー補足を先頭ターンの INSTRUCT/FIX に一度だけ注入（`OWNER_REPLY.md` より優先） |

エージェント向け手順: [`.agents/skills/herdr-self-evolve/SKILL.md`](./.agents/skills/herdr-self-evolve/SKILL.md)

### ESCALATE と再開

人間の判断が必要なとき、reviewer は `VERDICT: ESCALATE`、planner は `STATUS: ESCALATE` でループを止め、`NEEDS_OWNER.md` を残す。

再開:

- `--resume --notes-dir <dir>` が必須。`--goal` は省略可（優先順: CLI → `notes-dir/run.json` → `NEEDS_OWNER.md` の `## Goal`）
- `--turns` は **再開後の開始ターンから** の上限（例: start=3, `--turns 2` → ターン 3–4）。絶対番号は `MAX_TURNS`（10）でクランプ
- 通常開始時に `run.json`（goal / workdir / max_turns など）を書く。resume 開始時は既存 `NEEDS_OWNER.md` を `NEEDS_OWNER.prev.md` へ退避
- 開始ターン: 完了済み（非スケルトン）`TURN{n}_REVIEW` の次。未完了ターン（PLAN/RESULT あり・REVIEW なし、planner ESCALATE 含む）は **同じ n を再実行**

```bash
herdr-turns --from-here --daemon --resume --notes-dir ./herdr-turns-notes --turns 3 --workdir "$PWD"
# オーナー補足を渡す例（CLI が notes-dir/OWNER_REPLY.md より優先）
herdr-turns --from-here --daemon --resume --notes-dir ./herdr-turns-notes --turns 3 \
  --workdir "$PWD" --owner-reply "Approach B; skip A"
```

### Wave 2 オーケストレータ hardening

無人ループ向けのランナー側ガード（プロンプト文言だけに頼らない）:

- **Owner reply on resume** — `notes-dir/OWNER_REPLY.md` を書くか `--owner-reply "..."` を渡す（CLI 優先。空/空白は無視）。再開セッションの **先頭ターン** の INSTRUCT+FIX に一度だけ注入。消費は `run.json` の `owner_reply_sha256` と、ファイルがある場合の `OWNER_REPLY.consumed.md` リネーム。同じ内容の再 resume では再注入しない
- **Weak VERIFIED soft-gate** — FIX 後、RESULT の `VERIFIED` が欠落/スケルトン/曖昧なら coder へ **最大1回** 再プロンプト。なお弱い場合は REVIEW 先頭に prefer-REVISE の orchestrator note を付ける（その後 REVIEW へ進む）
- **Stall detection** — 継続 PLAN の `TASK` が前ターンと正規化一致（strip / 小文字 / 空白畳み / 末尾句読点除去）なら FIX 前に停止し `NEEDS_OWNER.md` を書く（繰り返しタスクの説明付き）
- **REVIEW diff context** — Wave 2 時点では `git diff --stat` / `--name-status` のみ。Wave 3 では **state pack**（下記）に統合

### AI駆動・自己進化（wave 3）

cursor-dual-agent-loop の *ideas* を `herdr-turns` に移植した層。**`auto/orchestrator/dual_agent_loop.py` は埋め込まず・呼び出さない**（別ツールのまま）。

| dual-agent-loop idea | herdr-turns |
| --- | --- |
| Master は prose より成果物を見る | FIX 後に `collect_turn_review_pack` → `notes-dir/TURN{n}_STATE.txt`。REVIEW に pack 本文 + ファイルパスを注入（`--test-command` 任意） |
| `COMPLETE.md` on STOP | 成功終了で `COMPLETE.md`（ルールは上記 [COMPLETE.md vs NEEDS_OWNER.md](#マルチエージェント自動化自己進化)） |
| Task = instructions + acceptance | `--goal-file` / `--acceptance-file` / `--task-pack`（YAML `goal:`/`acceptance:` または Markdown `## Goal` / `## Acceptance`）。パスと内容 hash を `run.json` に保存 |
| Review に test 結果 | `--test-command "..."`（stdout/stderr + exit。resume 復元可） |
| Cheap coder / strong master | `--coder-arg=--yolo` など安価側、`--reviewer-arg=--model --reviewer-arg composer-2.5` など強め reviewer。未指定ロールは `--agent-arg` → 既定 `--yolo` |
| Write boundaries | バンドル [`scripts/herdr_turns_constraints.default.md`](./scripts/herdr_turns_constraints.default.md) を **always-on mention**（`--constraints` で上書き、`--no-default-constraints` でオフ） |
| Headless overnight | 下記 tmux / daemon レシピ + 任意 `--notify-webhook` / `HERDR_TURNS_WEBHOOK` |

**コスト分割の例:**

```bash
herdr-turns --from-here --daemon --turns 5 \
  --goal-file ./task-goal.md --acceptance-file ./acceptance.md \
  --test-command "python3 -m unittest scripts.test_herdr_agent_turns -q" \
  --coder-arg=--yolo \
  --reviewer-arg=--model --reviewer-arg composer-2.5 \
  --workdir "$PWD"
```

**Headless / overnight（server + tmux）:**

```bash
# 例: 長時間セッションを tmux に載せる
tmux new -s herdr-turns
# Herdr TUI / 管理ペイン内で:
herdr-turns --from-here --daemon --turns 8 \
  --task-pack ./task.yaml \
  --test-command "python3 -m unittest scripts.test_herdr_agent_turns -q" \
  --notify-webhook "https://example.invalid/hooks/herdr-turns" \
  --workdir "$PWD"
# detach して翌朝確認:
#   notes-dir/COMPLETE.md … 成功
#   notes-dir/NEEDS_OWNER.md … 判断待ち / stall
#   webhook JSON event: complete | escalate | stop
```

Webhook ペイロード概要: `event`, `goal`, `turn`, `verdict`, `stop_reason`, `notes_dir`, `workdir`。失敗は `warning:` のみ（ループは落とさない）。

### 終了時の効果判定レポート

画面表示に加え、作業ディレクトリへ:

- **`自己改善yyyymmddhhmmss.md`**
- `notes-dir/SUMMARY.md`（同内容）

レポート構成:

1. **大元の指示**（`--goal`）
2. **効果判定**（DONE/APPROVE/REVISE/ESCALATE から自動ラベル。ESCALATE 時は「オーナー判断待ち」）
3. **ターン一覧**（指示 / できたこと / レビュー改善 / VERDICT / 効果）
4. **各ターン詳細**（PLAN / RESULT / REVIEW 全文）

### 役割を分けて回す例

```bash
herdr agent start coder --kind cursor --pane <pane> -- --trust -f --model composer-2.5
herdr agent start reviewer --kind cursor --pane <pane> -- --trust -f --model composer-2.5

just agent-turns \
  --coder coder \
  --reviewer reviewer \
  --turns 10 \
  --goal "Improve multi-agent orchestration helpers" \
  --notes-dir /var/tmp/herdr-turns-notes \
  --workdir "$PWD"
```

補足:

- 対象名は `herdr agent rename` / `agent start <name>`。一覧は `python3 scripts/summarize_herdr_tabs.py` の **target** 列。
- `agent prompt --wait` が `agent_prompt_stalled` になるときは `--wait` なし＋状態ポーリング（本スクリプトは後者）。
- 実験は名前付きセッション（`herdr --session ...`）を推奨。

### 自己改善ループ（記録: 初期 3 ターン）

Cursor Agent（`composer-2.5`）の coder / reviewer で、この fork の要約スクリプトを 3 ターン改善した（当時の実装→レビュー→適用フロー）。

| ターン | 実装 | レビュー指摘 | 適用 |
| --- | --- | --- | --- |
| 1 | `automation_target` を plain / markdown / JSON に追加。`herdr_json` が `error` 付き JSON を失敗扱い | (1) agent list 失敗時は空 dict+警告 (2) docstring で target と `pane.agent` を区別 (3) 0.9.2 fixture テスト (4) markdown の pane 特定 (5) error 経路の単体テスト | (1)(2) を反映。残りは後続 |
| 2 | `scripts/fixtures/agent-list-v092.json` と fixture テスト | Turn 2 は合格。Turn 3 向け: A=`herdr_json` error テスト、B=`justfile` に unittest 登録 | B と markdown `` `name` (`pane_id`) `` 表示など |
| 3 | `test_herdr_json_raises_on_error_payload` ほか fallback / load-fixture テスト（計 10） | ブロッキング指摘なし。コミット時は fixture を含める | テスト緑を確認して完了 |

関連: `scripts/summarize_herdr_tabs.py`、`scripts/herdr_agent_turns.py`、`scripts/herdr-turns`、`justfile`（`agent-turns` / `maintenance-test`）。
