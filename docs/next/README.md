# herdr

<p align="center">
  <img src="assets/logo.png" alt="herdr" width="100" />
</p>

<p align="center">
  <a href="https://github.com/kuwa2005/herdr">このリポジトリ</a>
  · <a href="#インストール">インストール</a>
  · <a href="https://herdr.dev/ja/docs/quick-start/">クイックスタート</a>
  · <a href="https://herdr.dev/ja/docs/">ドキュメント</a>
</p>

<p align="center">
  日本語 · <a href="README.en.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-666666?labelColor=333333" alt="Apache 2.0 license" /></a>
  <a href="https://github.com/kuwa2005/herdr"><img src="https://img.shields.io/badge/fork-kuwa2005%2Fherdr-666666?labelColor=333333&logo=github" alt="kuwa2005/herdr" /></a>
  <a href="https://github.com/herdrdev/herdr"><img src="https://img.shields.io/badge/upstream-herdrdev%2Fherdr-666666?labelColor=333333&logo=github" alt="upstream herdrdev/herdr" /></a>
</p>

---

https://github.com/user-attachments/assets/043ec09f-4bdd-41d5-aee0-8fda6b83e267

**コーディングエージェントが住むランタイム。**

このリポジトリ（[`kuwa2005/herdr`](https://github.com/kuwa2005/herdr)）は [herdrdev/herdr](https://github.com/herdrdev/herdr) の **日本語寄りフォーク**です。UI 言語（`en` / `ja` / `zh-cn`）やローカル向け修正を載せています。upstream の有用な更新は必要に応じて取り込みます。内部運用は [`FORK.md`](./FORK.md) を参照してください。

- **閉じても作業は止まらない** — クライアントを閉じたり SSH が切れても、バックグラウンドサーバー上でターミナルが動き続けます。サーバーやマシン再起動後は保存済みレイアウトを復元し、対応エージェントは再開できます（元プロセスは残りません）。[セッション状態 →](https://herdr.dev/ja/docs/session-state/)
- **複数マシンを一つの窓で** — ローカルと保存済み SSH を並べ、エージェント一覧をまとめ、接続ごとに独立して再接続できます。[リモートマシン →](https://herdr.dev/ja/docs/connecting-machines/)
- **止まっているエージェントを探し回らない** — 各ペインは working / blocked / idle。回答待ちになると Herdr が知らせます。
- **エージェントネイティブ** — CLI と socket API でペイン作成・相互プロンプト・本当に blocked になるまでの待機ができます。[エージェントスキル →](https://herdr.dev/ja/docs/agent-skill/)
- **いま使っているものをそのまま** — Claude Code、Codex、Cursor、OpenCode、Grok など。ラップせず、ターミナルを所有します。
- **キーボードもマウスも一等** — tmux 風プレフィックスと、クリック・ドラッグ・分割の両方。
- **プラグイン** — ペインとワークフローを拡張。[マーケットプレイス →](https://herdr.dev/plugins/)
- **Rust 単体バイナリ、Electron なし** — いつも使っている端末で動きます。

---

## インストール

インストーラは **このリポジトリ**（`kuwa2005/herdr`）から取得します。配布バイナリは upstream の公開リリースを参照します（fork 専用リリースを出していないため）。`herdr update` も upstream の更新チャネルに追従します。

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.sh | sh
```

### Windows（PowerShell）

PowerShell を開き、次を実行します。

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.ps1 | iex"
```

インストール後:

1. **新しい PowerShell ウィンドウ**を開く（PATH 反映のため）
2. `herdr` と入力して起動を確認する

チャネルを明示する／引数を付けたい場合は、いったん保存してから実行します。

```powershell
irm https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Channel stable
# プレビューの場合: -Channel preview
Remove-Item .\install.ps1
```

### Windows（エンドポイント保護で PowerShell がブロックされる場合）

**コマンドプロンプト（cmd）** で次を実行します。

```cmd
curl.exe -fsSLo install.cmd https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.cmd && install.cmd && del install.cmd
```

### その他の入手方法

| 方法 | コマンド / リンク |
| --- | --- |
| Homebrew | `brew install herdr` |
| mise | `mise use -g herdr` |
| バイナリ直リンク | [upstream Releases](https://github.com/herdrdev/herdr/releases) |
| ソースビルド | 下記「開発」 |

作業ディレクトリで起動:

```bash
herdr
```

エージェントを走らせ、ペインを分割し、離れても大丈夫です。`ctrl+b q` でデタッチ、`herdr` で再アタッチ。[クイックスタート →](https://herdr.dev/ja/docs/quick-start/)

UI を日本語にする例（`~/.config/herdr/config.toml`）:

```toml
[ui]
language = "ja" # en | ja | zh-cn
```

グローバルメニューの **language**、または設定の **language** タブからも切り替えられます。

## ドキュメント

公開ドキュメントは [herdr.dev/ja/docs](https://herdr.dev/ja/docs/) を参照してください。  
[クイックスタート](https://herdr.dev/ja/docs/quick-start/) · [概念](https://herdr.dev/ja/docs/concepts/) · [対応エージェント](https://herdr.dev/ja/docs/agents/) · [キーボード](https://herdr.dev/ja/docs/keyboard/) · [設定](https://herdr.dev/ja/docs/configuration/) · [セッション状態](https://herdr.dev/ja/docs/session-state/) · [マシン接続](https://herdr.dev/ja/docs/connecting-machines/) · [リモート](https://herdr.dev/ja/docs/persistence-remote/) · [連携](https://herdr.dev/ja/docs/integrations/) · [プラグイン](https://herdr.dev/ja/docs/plugins/) · [Socket API](https://herdr.dev/ja/docs/socket-api/)

## upstream について

- 製品本体・公式ドキュメント・リリースバイナリの本家は [herdrdev/herdr](https://github.com/herdrdev/herdr) / [herdr.dev](https://herdr.dev) です。
- この fork では日本語 UI やローカル向け修正を優先します。upstream の有用な更新は、必要に応じて取り込みます。
- 本家への実装 PR は、Herdr の貢献ポリシー（承認コントリビュータのみ）に従ってください。

スポンサー一覧は [SPONSORS.md](./SPONSORS.md)（upstream 由来）。企業・提携: hey@herdr.dev

## エージェント向け

このリポジトリを触る AI エージェントは、変更前に [`AGENTS.md`](./AGENTS.md) を、Issue / PR 前に [`CONTRIBUTING.md`](./CONTRIBUTING.md) を読んでください。

## 開発

```bash
git clone https://github.com/kuwa2005/herdr
cd herdr
cargo build --release

just test        # ユニットテスト
just check       # フォーマット・テスト・メンテ用チェック
```

upstream を取り込む例:

```bash
git remote add upstream https://github.com/herdrdev/herdr.git   # 初回のみ
git fetch upstream
git merge upstream/master   # または rebase。方針に合わせて選択
```

## ライセンス

Herdr は [Apache License 2.0](LICENSE) です。
