# herdr

<p align="center">
  <img src="assets/logo.png" alt="herdr" width="100" />
</p>

<p align="center">
  <a href="https://github.com/kuwa2005/herdr">this fork</a>
  · <a href="#install">install</a>
  · <a href="https://herdr.dev/docs/quick-start/">quick start</a>
  · <a href="https://herdr.dev/docs/">docs</a>
</p>

<p align="center">
  <a href="README.md">日本語</a> · English · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-666666?labelColor=333333" alt="Apache 2.0 license" /></a>
  <a href="https://github.com/kuwa2005/herdr"><img src="https://img.shields.io/badge/fork-kuwa2005%2Fherdr-666666?labelColor=333333&logo=github" alt="kuwa2005/herdr" /></a>
  <a href="https://github.com/herdrdev/herdr"><img src="https://img.shields.io/badge/upstream-herdrdev%2Fherdr-666666?labelColor=333333&logo=github" alt="upstream herdrdev/herdr" /></a>
</p>

---

https://github.com/user-attachments/assets/043ec09f-4bdd-41d5-aee0-8fda6b83e267

**the runtime your coding agents live on.**

This repository ([`kuwa2005/herdr`](https://github.com/kuwa2005/herdr)) is a **Japanese-oriented fork** of [herdrdev/herdr](https://github.com/herdrdev/herdr). Useful upstream updates may be merged when needed. Internal workflow: [`FORK.md`](./FORK.md).

- **detach without stopping work** — herdr keeps terminals running in a background server when you close the client or lose your SSH connection. after a server or machine restart, herdr restores the saved layout and can resume supported agent sessions; the original processes do not survive. [session state →](https://herdr.dev/docs/session-state/)
- **several machines, one window** — keep local work and saved ssh machines together, with a combined agent list and independent reconnects. [remote machines →](https://herdr.dev/docs/connecting-machines/)
- **never hunt for the stuck one** — every pane is marked working, blocked, or idle. when an agent stops and needs an answer, herdr says so.
- **agent-native** — agents drive herdr through the cli and socket api: they can spawn panes, prompt each other, and wait until another agent is genuinely blocked. [agent skill →](https://herdr.dev/docs/agent-skill/)
- **runs what you already run** — claude code, codex, cursor, opencode, grok and the rest. herdr doesn't wrap or replace them; it owns their terminals.
- **keyboard and mouse, both first-class** — tmux-style prefix keys *and* click, drag, split. pick per moment, not per tool.
- **plugins** — extend panes and workflows. [browse the marketplace →](https://herdr.dev/plugins/)
- **one rust binary, no electron** — runs in whatever terminal you already use.

---

## install

Installers are fetched from **this repository**. Release binaries still come from upstream public releases (this fork does not publish its own assets). `herdr update` follows the upstream update channel.

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.sh | sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.ps1 | iex"
```

After install, open a **new PowerShell window**, then run `herdr`.

To pass installer arguments (for example channel):

```powershell
irm https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Channel stable
Remove-Item .\install.ps1
```

### Windows (endpoint-protected)

In **Command Prompt (cmd)**:

```cmd
curl.exe -fsSLo install.cmd https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.cmd && install.cmd && del install.cmd
```

### Other options

`brew install herdr` · `mise use -g herdr` · [upstream binaries](https://github.com/herdrdev/herdr/releases)

then start it where the work lives:

```bash
herdr
```

run your agents, split panes, walk away. `ctrl+b q` detaches, `herdr` reattaches. [quick start →](https://herdr.dev/docs/quick-start/)

## docs

everything lives at [herdr.dev/docs](https://herdr.dev/docs/): [quick start](https://herdr.dev/docs/quick-start/) · [concepts](https://herdr.dev/docs/concepts/) · [supported agents](https://herdr.dev/docs/agents/) · [keyboard](https://herdr.dev/docs/keyboard/) · [configuration](https://herdr.dev/docs/configuration/) · [session state](https://herdr.dev/docs/session-state/) · [connecting machines](https://herdr.dev/docs/connecting-machines/) · [remote](https://herdr.dev/docs/persistence-remote/) · [integrations](https://herdr.dev/docs/integrations/) · [plugins](https://herdr.dev/docs/plugins/) · [socket api](https://herdr.dev/docs/socket-api/)

## thanks

every past sponsor and backer is listed in [SPONSORS.md](./SPONSORS.md) — thank you 🐑

enterprise / partnership: hey@herdr.dev

## agent instructions

if you are an ai agent helping with this repository, read [`AGENTS.md`](./AGENTS.md) before making changes and read [`CONTRIBUTING.md`](./CONTRIBUTING.md) before opening issues or PRs.

## development

```bash
git clone https://github.com/kuwa2005/herdr
cd herdr
cargo build --release

just test
just check
```

## license

Herdr is licensed under the [Apache License 2.0](LICENSE).
