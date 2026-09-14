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

衝突しやすい箇所の例: `README.md`、`.github/MAINTAINERS`、`.github/APPROVED_CONTRIBUTORS`、`distribution/install.cmd`、この `FORK.md`。

## エージェント向け

1. まず [`AGENTS.md`](./AGENTS.md) とこのファイルを読む。
2. 認証アカウントが `kuwa2005` で、リモートが `kuwa2005/herdr` なら、**この fork 上の**実装・コミット・push は所有者作業として進めてよい。
3. `herdrdev/herdr` への実装 PR・機能 Issue は開かない（CONTRIBUTING / AGENTS の外部貢献ガードを維持）。
4. upstream 由来の再現バグを本家に報告する場合だけ、人間が CONTRIBUTING のバグテンプレート手順に従う。
