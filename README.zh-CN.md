# herdr

<p align="center">
  <img src="assets/logo.png" alt="herdr" width="100" />
</p>

<p align="center">
  <a href="https://github.com/kuwa2005/herdr">本仓库</a>
  · <a href="#安装">安装</a>
  · <a href="https://herdr.dev/zh-cn/docs/quick-start/">快速开始</a>
  · <a href="https://herdr.dev/zh-cn/docs/">文档</a>
</p>

<p align="center">
  <a href="README.md">日本語</a> · <a href="README.en.md">English</a> · 简体中文
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-666666?labelColor=333333" alt="Apache 2.0 license" /></a>
  <a href="https://github.com/kuwa2005/herdr"><img src="https://img.shields.io/badge/fork-kuwa2005%2Fherdr-666666?labelColor=333333&logo=github" alt="kuwa2005/herdr" /></a>
  <a href="https://github.com/herdrdev/herdr"><img src="https://img.shields.io/badge/upstream-herdrdev%2Fherdr-666666?labelColor=333333&logo=github" alt="upstream herdrdev/herdr" /></a>
</p>

---

https://github.com/user-attachments/assets/043ec09f-4bdd-41d5-aee0-8fda6b83e267

**智能体复用器，住在你的终端里。**

本仓库（[`kuwa2005/herdr`](https://github.com/kuwa2005/herdr)）是 [herdrdev/herdr](https://github.com/herdrdev/herdr) 的**日语优先分支**。上游有用的更新会按需合入。

- **每个智能体一目了然**——`blocked`、`working`、`done`。真实的终端视图，而不是包装过的转述。
- **分离后工作继续运行**——关闭客户端或 SSH 断线后，后台服务器仍会保持终端运行。服务器或机器重启后，Herdr 会恢复已保存的布局，并可恢复受支持的智能体会话；原有进程不会保留。[会话状态 →](https://herdr.dev/zh-cn/docs/session-state/)
- **多台机器，一个窗口**——将本地工作和已保存的 SSH 机器放在一起，使用汇总的智能体列表，各连接独立重连。[远程机器 →](https://herdr.dev/zh-cn/docs/connecting-machines/)
- **智能体也能使用 herdr**——纯 socket api：智能体可以创建窗格、读取输出、互相等待。[智能体技能 →](https://herdr.dev/zh-cn/docs/agent-skill/)
- **键盘和鼠标都是一等公民**——tmux 风格的前缀键，*以及*点击、拖动、分割。按当下的场景选择，而不是被工具锁死。
- **插件**——扩展窗格和工作流。[浏览插件市场 →](https://herdr.dev/plugins/)
- **单个 rust 二进制，没有 electron**——运行在你已经在用的任何终端里。

---

## 安装

安装脚本从**本仓库**获取；发布二进制仍来自 upstream 公开 Release（本 fork 暂不单独发版）。`herdr update` 跟随 upstream 更新通道。

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.sh | sh
```

### Windows（PowerShell）

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.ps1 | iex"
```

安装后请打开**新的 PowerShell 窗口**，再运行 `herdr`。

需要传参时（例如指定通道）先保存再执行：

```powershell
irm https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Channel stable
Remove-Item .\install.ps1
```

### Windows（端点保护拦截 PowerShell 时）

在 **命令提示符（cmd）** 中：

```cmd
curl.exe -fsSLo install.cmd https://raw.githubusercontent.com/kuwa2005/herdr/master/distribution/install.cmd && install.cmd && del install.cmd
```

### 其他方式

`brew install herdr` · `mise use -g herdr` · [upstream 二进制](https://github.com/herdrdev/herdr/releases)

然后在工作所在的目录启动它：

```bash
herdr
```

运行你的智能体、分割窗格，然后安心离开。`ctrl+b q` 分离，`herdr` 重新连接。[快速开始 →](https://herdr.dev/zh-cn/docs/quick-start/)

## 文档

所有文档都在 [herdr.dev/docs](https://herdr.dev/zh-cn/docs/)：[快速开始](https://herdr.dev/zh-cn/docs/quick-start/) · [核心概念](https://herdr.dev/zh-cn/docs/concepts/) · [受支持的智能体](https://herdr.dev/zh-cn/docs/agents/) · [键盘](https://herdr.dev/zh-cn/docs/keyboard/) · [配置](https://herdr.dev/zh-cn/docs/configuration/) · [会话状态](https://herdr.dev/zh-cn/docs/session-state/) · [连接机器](https://herdr.dev/zh-cn/docs/connecting-machines/) · [远程访问](https://herdr.dev/zh-cn/docs/persistence-remote/) · [集成](https://herdr.dev/zh-cn/docs/integrations/) · [插件](https://herdr.dev/zh-cn/docs/plugins/) · [socket api](https://herdr.dev/zh-cn/docs/socket-api/)

## 致谢

[SPONSORS.md](./SPONSORS.md) 中列出的每一位支持者——谢谢 🐑

企业/合作：hey@herdr.dev

## 智能体须知

如果你是协助本仓库的 AI 智能体：在改动代码前阅读 [`AGENTS.md`](./AGENTS.md)，在创建 issue 或 PR 前阅读 [`CONTRIBUTING.md`](./CONTRIBUTING.md)。

## 开发

```bash
git clone https://github.com/kuwa2005/herdr
cd herdr
cargo build --release

just test
just check
```

## 许可证

herdr 基于 [Apache License 2.0](LICENSE) 许可证发布。
