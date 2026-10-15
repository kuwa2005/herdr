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
# ターン制ランナー（任意）
install -m 755 scripts/herdr-turns ~/.local/bin/herdr-turns
```

稼働中サーバーは古いプロセスのままなので、付け直しまたは再起動が必要。

## エージェント向け

1. まず [`AGENTS.md`](./AGENTS.md) とこのファイルを読む。
2. 認証アカウントが `kuwa2005` で、リモートが `kuwa2005/herdr` なら、**この fork 上の**実装・コミット・push は所有者作業として進めてよい。
3. `herdrdev/herdr` への実装 PR・機能 Issue は開かない（CONTRIBUTING / AGENTS の外部貢献ガードを維持）。
4. upstream 由来の再現バグを本家に報告する場合だけ、人間が CONTRIBUTING のバグテンプレート手順に従う。

## マルチエージェント自動化（自己進化）

Herdr 本体に「A→B 自動パイプ」はない。この fork の公式ワークフローは **最大 10 ターンの自己進化ループ**。

### 1 ターンの流れ

1. **INSTRUCT** — `TURN{n}_PLAN.md`（`STATUS` / `TASK` / `DONE_WHEN`）
2. **FIX** — `TURN{n}_RESULT.md`（`DONE` / `VERIFIED` / `FILES`）
3. **REVIEW** — `TURN{n}_REVIEW.md`（`VERDICT` / `IMPROVE` / `EFFECT`）
4. **APPLY** — `VERDICT: REVISE` のときだけ
5. 次ターンの INSTRUCT が直前レビューを読み、さらなる指示を出す

制約: `--turns` は **1〜10**（既定 10）。`VERDICT: DONE` または `STATUS: DONE` で早期終了。

### 想定 UX: 「ここから N ターン自己改善して」

```bash
# Herdr 管理ペイン内（$HERDR_ENV=1 / $HERDR_PANE_ID）
herdr-turns --from-here --daemon --turns 5 --goal "エラー処理を改善する" --workdir "$PWD"
```

| フラグ | 意味 |
| --- | --- |
| `--from-here` | 現在ペインのエージェントを planner/coder/reviewer に使う |
| `--daemon` | バックグラウンド起動（前景待ちはデッドロックする） |
| `--reviewer NAME` | レビュー役を分ける（省略時は自己レビュー） |

エージェント向け手順: [`.agents/skills/herdr-self-evolve/SKILL.md`](./.agents/skills/herdr-self-evolve/SKILL.md)

### 終了時の効果判定レポート

画面表示に加え、作業ディレクトリへ:

- **`自己改善yyyymmddhhmmss.md`**
- `notes-dir/SUMMARY.md`（同内容）

レポート構成:

1. **大元の指示**（`--goal`）
2. **効果判定**（DONE/APPROVE/REVISE から自動ラベル）
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
