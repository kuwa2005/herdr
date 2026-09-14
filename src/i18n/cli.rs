//! CLI help string localization keyed by English source text.
//!
//! English remains the clap source of truth in `cli/spec.rs`. Non-English
//! languages replace about/help/after_help after the command tree is built.

use clap::Command;

use crate::config::UiLanguage;

/// Read `[ui].language` for CLI help. Missing/invalid config falls back to English.
pub fn cli_language() -> UiLanguage {
    crate::config::Config::load().config.ui.language
}

/// Translate a `'static` CLI help string. Missing translations keep English.
pub fn translate(lang: UiLanguage, english: &'static str) -> &'static str {
    match lang {
        UiLanguage::En => english,
        UiLanguage::Ja => ja(english).unwrap_or(english),
        UiLanguage::ZhCn => zh_cn(english).unwrap_or(english),
    }
}

fn lookup(lang: UiLanguage, english: &str) -> Option<&'static str> {
    match lang {
        UiLanguage::En => None,
        UiLanguage::Ja => ja(english),
        UiLanguage::ZhCn => zh_cn(english),
    }
}

/// Apply translations to a clap command tree (about, arg help, after_help, subcommands).
pub fn localize_command(cmd: Command, lang: UiLanguage) -> Command {
    if lang == UiLanguage::En {
        return cmd;
    }
    localize_command_rec(cmd, lang)
}

fn localize_command_rec(cmd: Command, lang: UiLanguage) -> Command {
    let about = cmd.get_about().map(|s| s.to_string());
    let after_help = cmd.get_after_help().map(|s| s.to_string());
    let arg_helps: Vec<(String, String)> = cmd
        .get_arguments()
        .filter_map(|arg| {
            let help = arg.get_help()?.to_string();
            Some((arg.get_id().to_string(), help))
        })
        .collect();

    let mut cmd = cmd;
    if let Some(about) = about.as_deref() {
        if let Some(translated) = lookup(lang, about) {
            cmd = cmd.about(translated);
        }
    }
    if let Some(after) = after_help.as_deref() {
        if let Some(translated) = lookup(lang, after) {
            cmd = cmd.after_help(translated);
        }
    }
    for (id, help) in &arg_helps {
        if let Some(translated) = lookup(lang, help) {
            cmd = cmd.mut_arg(id, |arg| arg.help(translated));
        }
    }
    cmd.mut_subcommands(|subcommand| localize_command_rec(subcommand, lang))
}

/// Print the top-level `herdr --help` text for the configured language.
pub fn print_root_help(
    out: &mut impl std::io::Write,
    config_path: &std::path::Path,
    log_summary: &str,
) -> std::io::Result<()> {
    let lang = cli_language();
    let t = |english: &'static str| translate(lang, english);

    writeln!(
        out,
        "{}",
        t("herdr — terminal workspace manager for AI coding agents")
    )?;
    writeln!(out)?;
    writeln!(out, "{}", t("Usage: herdr [options]"))?;
    writeln!(out, "       herdr --session <name> [options]")?;
    writeln!(out, "       herdr --machine <label-or-id> <command>")?;
    writeln!(out, "       herdr --remote <ssh-target> [--session <name>]")?;
    writeln!(out, "       herdr session attach <name>")?;
    writeln!(out, "       herdr completion zsh")?;
    writeln!(out, "       herdr update [--handoff]")?;
    writeln!(out, "       herdr channel set <stable|preview>")?;
    writeln!(out, "       herdr machine <subcommand> ...")?;
    writeln!(out, "       herdr server stop")?;
    writeln!(out, "       herdr server reload-config")?;
    writeln!(out, "       herdr api <subcommand> ...")?;
    writeln!(out, "       herdr completion <shell>")?;
    writeln!(out, "       herdr config <subcommand> ...")?;
    writeln!(out, "       herdr channel <subcommand> ...")?;
    writeln!(out, "       herdr workspace <subcommand> ...")?;
    writeln!(out, "       herdr worktree <subcommand> ...")?;
    writeln!(out, "       herdr tab <subcommand> ...")?;
    writeln!(out, "       herdr notification <subcommand> ...")?;
    writeln!(out, "       herdr agent <subcommand> ...")?;
    writeln!(out, "       herdr pane <subcommand> ...")?;
    writeln!(out, "       herdr session <subcommand> ...")?;
    writeln!(out, "       herdr integration <subcommand> ...")?;
    writeln!(out)?;
    writeln!(out, "{}", t("Common commands:"))?;
    for (command, description) in [
        ("herdr", "Launch or attach to the persistent session"),
        (
            "herdr status [server|client]",
            "Show local client and running server status",
        ),
        ("herdr update", "Download and install the latest version"),
        ("herdr completion zsh", "Generate shell completions for zsh"),
        (
            "herdr server stop",
            "Stop the running server via the API socket",
        ),
        (
            "herdr channel set <stable|preview>",
            "Choose the stable or preview update channel",
        ),
        (
            "herdr server reload-config",
            "Reload config.toml in the running server",
        ),
        (
            "herdr config reset-keys",
            "Back up config.toml and remove custom keybindings",
        ),
        (
            "herdr channel <subcommand>",
            "Manage the stable or preview update channel",
        ),
        ("herdr machine <subcommand>", "Manage saved SSH machines"),
        (
            "herdr api <subcommand>",
            "Inspect socket API metadata and live runtime state",
        ),
        (
            "herdr workspace <subcommand>",
            "Workspace helpers over the socket API",
        ),
        (
            "herdr worktree <subcommand>",
            "Git worktree helpers over the socket API",
        ),
        ("herdr tab <subcommand>", "Tab helpers over the socket API"),
        (
            "herdr notification <subcommand>",
            "Notification helpers over the socket API",
        ),
        (
            "herdr agent <subcommand>",
            "Agent/terminal helpers over the socket API",
        ),
        (
            "herdr pane <subcommand>",
            "Pane control helpers over the socket API",
        ),
        (
            "herdr session <subcommand>",
            "Manage named persistent sessions",
        ),
        (
            "herdr integration <subcommand>",
            "Manage built-in agent integrations",
        ),
    ] {
        writeln!(out, "  {command:<32} {}", t(description))?;
    }
    writeln!(out)?;
    writeln!(out, "{}", t("Advanced commands:"))?;
    writeln!(
        out,
        "  {:<32} {}",
        "herdr server",
        t("Run as headless server")
    )?;
    writeln!(out)?;
    writeln!(out, "{}", t("Options:"))?;
    writeln!(
        out,
        "  --session <name>    {}",
        t("Use or create a named persistent session")
    )?;
    writeln!(
        out,
        "  --machine <label-or-id>  {}",
        t("Run an API command on a saved SSH machine")
    )?;
    writeln!(
        out,
        "  --remote <target>   {}",
        t("Attach through SSH to a remote Herdr server")
    )?;
    writeln!(out, "  --remote-keybindings <local|server>")?;
    writeln!(
        out,
        "                      {}",
        t("Keybindings for --remote app attach (default: local)")
    )?;
    writeln!(
        out,
        "  --handoff           {}",
        t("Opt into live handoff for update or remote attach")
    )?;
    writeln!(
        out,
        "  --default-config    {}",
        t("Print default configuration and exit")
    )?;
    writeln!(
        out,
        "  --skill             {}",
        t("Print the agent skill file and exit")
    )?;
    writeln!(out, "  --version, -V       {}", t("Print version and exit"))?;
    writeln!(out, "  --help, -h          {}", t("Show this help"))?;
    writeln!(out)?;
    writeln!(out, "{} {}", t("Config:"), config_path.display())?;
    writeln!(out, "{}   {}", t("Logs:"), log_summary)?;
    writeln!(
        out,
        "{}    {}",
        t("Env:"),
        t("HERDR_CONFIG_PATH overrides config file path")
    )?;
    writeln!(out, "{}   https://herdr.dev", t("Home:"))?;
    writeln!(out)?;
    writeln!(
        out,
        "{}",
        t(concat!(
            "Are you an AI? Use these resources ONLY IF your task specifically asks you to:\n",
            "  Help a human understand or set up Herdr for the first time:\n",
            "    https://herdr.dev/agent-guide.md\n",
            "  Debug or investigate a problem with Herdr:\n",
            "    https://herdr.dev/llms.txt\n",
            "  Control Herdr panes, agents, or workspaces:\n",
            "    SKIP if a Herdr skill is already in your context. Otherwise run: herdr --skill"
        ))
    )?;
    Ok(())
}

fn ja(english: &str) -> Option<&'static str> {
    Some(match english {
        "Advanced commands:" => "上級コマンド:",
        "Agent/terminal helpers over the socket API" => "ソケット API 経由のエージェント/ターミナル操作",
        "Are you an AI? Use these resources ONLY IF your task specifically asks you to:\n  Help a human understand or set up Herdr for the first time:\n    https://herdr.dev/agent-guide.md\n  Debug or investigate a problem with Herdr:\n    https://herdr.dev/llms.txt\n  Control Herdr panes, agents, or workspaces:\n    SKIP if a Herdr skill is already in your context. Otherwise run: herdr --skill" => "AI ですか? 次のリソースは、タスクが特に求めている場合にのみ使ってください:\n  人が初めて Herdr を理解・セットアップする手伝い:\n    https://herdr.dev/agent-guide.md\n  Herdr の問題をデバッグ・調査する:\n    https://herdr.dev/llms.txt\n  Herdr のペイン・エージェント・ワークスペースを操作する:\n    すでに Herdr skill がコンテキストにある場合は SKIP。なければ: herdr --skill",
        "Attach directly to a terminal stream" => "ターミナルストリームに直接アタッチ",
        "Attach directly to an agent terminal" => "エージェントのターミナルに直接アタッチ",
        "Attach through SSH to a remote Herdr server" => "SSH 経由でリモート Herdr サーバーにアタッチ",
        "Attach to a session" => "セッションにアタッチ",
        "Attach to or observe raw terminal streams" => "生のターミナルストリームへアタッチまたは監視",
        "Back up config.toml and remove custom keybindings" => "config.toml をバックアップしてカスタムキーバインドを削除",
        "Choose local or server keybindings for remote attach" => "リモートアタッチのキーバインドを local または server から選択",
        "Choose the stable or preview update channel" => "stable または preview 更新チャネルを選択",
        "Choose the update channel" => "更新チャネルを選択",
        "Clear the outer terminal title" => "外側ターミナルのタイトルをクリア",
        "Close a pane" => "ペインを閉じる",
        "Close a plugin pane" => "プラグインペインを閉じる",
        "Close a tab" => "タブを閉じる",
        "Close a workspace" => "ワークスペースを閉じる",
        "Common commands:" => "よく使うコマンド:",
        "Config:" => "設定:",
        "Control a terminal stream" => "ターミナルストリームを制御",
        "Control and inspect agent panes" => "エージェントペインを制御・検査",
        "Control terminal panes" => "ターミナルペインを制御",
        "Create a tab" => "タブを作成",
        "Create a workspace" => "ワークスペースを作成",
        "Create and open a Git worktree" => "Git worktree を作成して開く",
        "Delete a stopped session" => "停止済みセッションを削除",
        "Disable a plugin" => "プラグインを無効化",
        "Disable a saved SSH machine" => "保存済み SSH マシンを無効化",
        "Download and install the latest version" => "最新版をダウンロードしてインストール",
        "Enable a plugin" => "プラグインを有効化",
        "Enable a saved SSH machine" => "保存済み SSH マシンを有効化",
        "Env:" => "環境変数:",
        "Existing pane at an interactive shell prompt" => "対話シェルプロンプト上の既存ペイン",
        "Explain agent detection state" => "エージェント検出状態を説明",
        "Fail after this many milliseconds" => "このミリ秒後に失敗する",
        "Fetch and reload agent detection manifests" => "エージェント検出マニフェストを取得して再読込",
        "Find a pane neighbor" => "隣接ペインを検索",
        "Focus a neighboring pane" => "隣接ペインにフォーカス",
        "Focus a plugin pane" => "プラグインペインにフォーカス",
        "Focus a tab" => "タブにフォーカス",
        "Focus a workspace" => "ワークスペースにフォーカス",
        "Focus an agent" => "エージェントにフォーカス",
        "Generate shell completion scripts" => "シェル補完スクリプトを生成",
        "Generate shell completions for zsh" => "zsh 用のシェル補完を生成",
        "Git worktree helpers over the socket API" => "ソケット API 経由の Git worktree 操作",
        "HERDR_CONFIG_PATH overrides config file path" => "HERDR_CONFIG_PATH は設定ファイルパスを上書きします",
        "Home:" => "ホーム:",
        "Inspect plugin command logs" => "プラグインコマンドのログを確認",
        "Inspect socket API metadata and live runtime state" => "ソケット API のメタデータと実行時状態を確認",
        "Install a plugin from GitHub" => "GitHub からプラグインをインストール",
        "Install an integration" => "インテグレーションをインストール",
        "Install and run workflow plugins" => "ワークフロープラグインをインストールして実行",
        "Invoke a plugin action" => "プラグインアクションを実行",
        "Keep ANSI escape sequences while matching" => "マッチ中も ANSI エスケープシーケンスを保持",
        "Keybindings for --remote app attach (default: local)" => "--remote アプリアタッチ用キーバインド（既定: local）",
        "Launch or attach to the persistent session" => "永続セッションを起動またはアタッチ",
        "Link a local plugin" => "ローカルプラグインをリンク",
        "List agents" => "エージェント一覧",
        "List installed plugins" => "インストール済みプラグイン一覧",
        "List or invoke plugin actions" => "プラグインアクションの一覧または実行",
        "List panes" => "ペイン一覧",
        "List plugin actions" => "プラグインアクション一覧",
        "List plugin command logs" => "プラグインコマンドログ一覧",
        "List saved SSH machines" => "保存済み SSH マシン一覧",
        "List sessions" => "セッション一覧",
        "List tabs" => "タブ一覧",
        "List workspaces" => "ワークスペース一覧",
        "List worktree workspaces" => "worktree ワークスペース一覧",
        "Logs:" => "ログ:",
        "Manage Git worktree-backed workspaces" => "Git worktree ベースのワークスペースを管理",
        "Manage built-in agent integrations" => "組み込みエージェント連携を管理",
        "Manage local configuration" => "ローカル設定を管理",
        "Manage named persistent sessions" => "名前付き永続セッションを管理",
        "Manage plugin-owned panes" => "プラグイン所有のペインを管理",
        "Manage saved SSH machines" => "保存済み SSH マシンを管理",
        "Manage stable and preview update channels" => "stable / preview 更新チャネルを管理",
        "Manage tabs over the socket API" => "ソケット API でタブを管理",
        "Manage the outer terminal title" => "外側ターミナルのタイトルを管理",
        "Manage the stable or preview update channel" => "stable または preview 更新チャネルを管理",
        "Manage workspaces over the socket API" => "ソケット API でワークスペースを管理",
        "Match a Rust regular expression" => "Rust 正規表現にマッチ",
        "Match a literal substring" => "リテラル部分文字列にマッチ",
        "Move a pane" => "ペインを移動",
        "Notification helpers over the socket API" => "ソケット API 経由の通知操作",
        "Observe a terminal stream" => "ターミナルストリームを監視",
        "Open a plugin pane" => "プラグインペインを開く",
        "Open an existing Git worktree" => "既存の Git worktree を開く",
        "Opt into live handoff for update or remote attach" => "更新またはリモートアタッチでライブハンドオフを有効化",
        "Options:" => "オプション:",
        "Pane control helpers over the socket API" => "ソケット API 経由のペイン制御",
        "Prepare the remote Herdr server and save an SSH machine" => "リモート Herdr サーバーを準備して SSH マシンを保存",
        "Print a plugin config directory" => "プラグイン設定ディレクトリを表示",
        "Print default configuration and exit" => "デフォルト設定を表示して終了",
        "Print or write the bundled API schema" => "同梱 API スキーマを表示または書き出し",
        "Print the agent skill file and exit" => "エージェント用 skill ファイルを表示して終了",
        "Print the configured update channel" => "設定中の更新チャネルを表示",
        "Print the live session snapshot" => "ライブセッションのスナップショットを表示",
        "Print version and exit" => "バージョンを表示して終了",
        "Read agent terminal output" => "エージェントのターミナル出力を読む",
        "Read pane terminal output" => "ペインのターミナル出力を読む",
        "Release pane agent lifecycle authority" => "ペインのエージェントライフサイクル権限を解放",
        "Reload config in the running server" => "実行中サーバーの設定を再読込",
        "Reload config.toml in the running server" => "実行中サーバーで config.toml を再読込",
        "Reload local agent detection manifest overrides" => "ローカルのエージェント検出マニフェスト上書きを再読込",
        "Remove a saved SSH machine" => "保存済み SSH マシンを削除",
        "Remove a worktree checkout" => "worktree チェックアウトを削除",
        "Rename a pane" => "ペイン名を変更",
        "Rename a saved SSH machine" => "保存済み SSH マシン名を変更",
        "Rename a tab" => "タブ名を変更",
        "Rename a workspace" => "ワークスペース名を変更",
        "Rename an agent" => "エージェント名を変更",
        "Report display-only pane metadata" => "表示専用のペインメタデータを報告",
        "Report display-only workspace metadata" => "表示専用のワークスペースメタデータを報告",
        "Report pane agent lifecycle state" => "ペインのエージェントライフサイクル状態を報告",
        "Report pane agent session identity" => "ペインのエージェントセッション識別子を報告",
        "Reset custom keybindings" => "カスタムキーバインドをリセット",
        "Resize a pane split" => "ペイン分割のサイズを変更",
        "Restrict the searched snapshot to N lines" => "検索するスナップショットを N 行に制限",
        "Run a command in a pane" => "ペインでコマンドを実行",
        "Run an API command on a saved SSH machine" => "保存済み SSH マシンで API コマンドを実行",
        "Run as headless server" => "ヘッドレスサーバーとして実行",
        "Run or control the headless server" => "ヘッドレスサーバーを実行または制御",
        "Send key presses to a pane" => "ペインにキー入力を送る",
        "Send key presses to an agent" => "エージェントにキー入力を送る",
        "Send literal text to a pane" => "ペインにリテラルテキストを送る",
        "Set an environment variable for the launched process" => "起動プロセスの環境変数を設定",
        "Set pane input routing" => "ペインの入力ルーティングを設定",
        "Set the explicit Herdr session on the remote machine" => "リモートマシン上の Herdr セッションを明示指定",
        "Set the machine label shown in the sidebar" => "サイドバーに表示するマシンラベルを設定",
        "Set the outer terminal title" => "外側ターミナルのタイトルを設定",
        "Shell to generate completions for" => "補完を生成するシェル",
        "Show Herdr notifications" => "Herdr 通知を表示",
        "Show a notification" => "通知を表示",
        "Show a pane" => "ペインを表示",
        "Show a tab" => "タブを表示",
        "Show a workspace" => "ワークスペースを表示",
        "Show active agent detection manifests" => "有効なエージェント検出マニフェストを表示",
        "Show an agent" => "エージェントを表示",
        "Show help" => "ヘルプを表示",
        "Show integration status" => "インテグレーション状態を表示",
        "Show local client and running server status" => "ローカルクライアントと実行中サーバーの状態を表示",
        "Show local client status" => "ローカルクライアントの状態を表示",
        "Show pane edge information" => "ペインのエッジ情報を表示",
        "Show pane layout information" => "ペインのレイアウト情報を表示",
        "Show pane process information" => "ペインのプロセス情報を表示",
        "Show running server status" => "実行中サーバーの状態を表示",
        "Show the current pane" => "現在のペインを表示",
        "Show this help" => "このヘルプを表示",
        "Split a pane" => "ペインを分割",
        "Start a supported interactive agent in an existing pane" => "既存ペインで対応する対話型エージェントを起動",
        "State to match after --wait; repeat for more than one state" => "--wait 後に待つ状態。複数指定可",
        "State to match; repeat for more than one state" => "待つ状態。複数指定可",
        "Stop a session" => "セッションを停止",
        "Stop the running server" => "実行中のサーバーを停止",
        "Stop the running server via the API socket" => "API ソケット経由で実行中サーバーを停止",
        "Submit a prompt to an agent" => "エージェントにプロンプトを送信",
        "Supported agent kind and canonical executable" => "対応エージェント種別と正規の実行ファイル",
        "Swap panes" => "ペインを入れ替え",
        "Tab helpers over the socket API" => "ソケット API 経由のタブ操作",
        "Terminal snapshot source (default: recent)" => "ターミナルスナップショットのソース（既定: recent）",
        "Toggle or set pane zoom" => "ペインのズームを切替または設定",
        "Try live handoff after installing" => "インストール後にライブハンドオフを試行",
        "Uninstall a plugin" => "プラグインをアンインストール",
        "Uninstall an integration" => "インテグレーションをアンインストール",
        "Unlink a local plugin" => "ローカルプラグインのリンクを解除",
        "Usage: herdr [options]" => "使い方: herdr [options]",
        "Use or create a named persistent session" => "名前付き永続セッションを使用または作成",
        "Validate config.toml and print diagnostics" => "config.toml を検証して診断を表示",
        "Wait for interactive readiness (default: 30000; max: 300000)" => "対話準備完了を待機（既定: 30000、最大: 300000）",
        "Wait for matching pane output" => "一致するペイン出力を待機",
        "Wait for the first matching state observed after submission" => "送信後に観測される最初の一致状態を待機",
        "Wait until an agent reaches one of the requested states" => "エージェントが指定状態のいずれかになるまで待機",
        "Work with terminal sessions" => "ターミナルセッションを操作",
        "Workspace helpers over the socket API" => "ソケット API 経由のワークスペース操作",
        "herdr — terminal workspace manager for AI coding agents" => "herdr — AI コーディングエージェント向けターミナルワークスペースマネージャー",
        "terminal workspace manager for AI coding agents" => "AI コーディングエージェント向けターミナルワークスペースマネージャー",
        _ => return None,
    })
}

fn zh_cn(english: &str) -> Option<&'static str> {
    Some(match english {
        "Advanced commands:" => "高级命令:",
        "Agent/terminal helpers over the socket API" => "通过 socket API 的智能体/终端辅助命令",
        "Are you an AI? Use these resources ONLY IF your task specifically asks you to:\n  Help a human understand or set up Herdr for the first time:\n    https://herdr.dev/agent-guide.md\n  Debug or investigate a problem with Herdr:\n    https://herdr.dev/llms.txt\n  Control Herdr panes, agents, or workspaces:\n    SKIP if a Herdr skill is already in your context. Otherwise run: herdr --skill" => "你是 AI 吗? 仅当任务明确要求时才使用下列资源:\n  帮助人类首次理解或配置 Herdr:\n    https://herdr.dev/agent-guide.md\n  调试或排查 Herdr 问题:\n    https://herdr.dev/llms.txt\n  控制 Herdr 窗格、智能体或工作区:\n    若上下文中已有 Herdr skill 则 SKIP。否则运行: herdr --skill",
        "Attach directly to a terminal stream" => "直接附加到终端流",
        "Attach directly to an agent terminal" => "直接附加到智能体终端",
        "Attach through SSH to a remote Herdr server" => "通过 SSH 附加到远程 Herdr 服务器",
        "Attach to a session" => "附加到会话",
        "Attach to or observe raw terminal streams" => "附加或观察原始终端流",
        "Back up config.toml and remove custom keybindings" => "备份 config.toml 并移除自定义快捷键",
        "Choose local or server keybindings for remote attach" => "为远程附加选择 local 或 server 快捷键",
        "Choose the stable or preview update channel" => "选择 stable 或 preview 更新通道",
        "Choose the update channel" => "选择更新通道",
        "Clear the outer terminal title" => "清除外部终端标题",
        "Close a pane" => "关闭窗格",
        "Close a plugin pane" => "关闭插件窗格",
        "Close a tab" => "关闭标签页",
        "Close a workspace" => "关闭工作区",
        "Common commands:" => "常用命令:",
        "Config:" => "配置:",
        "Control a terminal stream" => "控制终端流",
        "Control and inspect agent panes" => "控制和检查智能体窗格",
        "Control terminal panes" => "控制终端窗格",
        "Create a tab" => "创建标签页",
        "Create a workspace" => "创建工作区",
        "Create and open a Git worktree" => "创建并打开 Git worktree",
        "Delete a stopped session" => "删除已停止的会话",
        "Disable a plugin" => "禁用插件",
        "Disable a saved SSH machine" => "禁用已保存的 SSH 机器",
        "Download and install the latest version" => "下载并安装最新版本",
        "Enable a plugin" => "启用插件",
        "Enable a saved SSH machine" => "启用已保存的 SSH 机器",
        "Env:" => "环境变量:",
        "Existing pane at an interactive shell prompt" => "处于交互式 shell 提示符的现有窗格",
        "Explain agent detection state" => "解释智能体检测状态",
        "Fail after this many milliseconds" => "在这么多毫秒后失败",
        "Fetch and reload agent detection manifests" => "获取并重新加载智能体检测清单",
        "Find a pane neighbor" => "查找相邻窗格",
        "Focus a neighboring pane" => "聚焦相邻窗格",
        "Focus a plugin pane" => "聚焦插件窗格",
        "Focus a tab" => "聚焦标签页",
        "Focus a workspace" => "聚焦工作区",
        "Focus an agent" => "聚焦智能体",
        "Generate shell completion scripts" => "生成 shell 补全脚本",
        "Generate shell completions for zsh" => "生成 zsh 的 shell 补全",
        "Git worktree helpers over the socket API" => "通过 socket API 的 Git worktree 辅助命令",
        "HERDR_CONFIG_PATH overrides config file path" => "HERDR_CONFIG_PATH 会覆盖配置文件路径",
        "Home:" => "主页:",
        "Inspect plugin command logs" => "检查插件命令日志",
        "Inspect socket API metadata and live runtime state" => "检查 socket API 元数据和实时运行状态",
        "Install a plugin from GitHub" => "从 GitHub 安装插件",
        "Install an integration" => "安装集成",
        "Install and run workflow plugins" => "安装并运行工作流插件",
        "Invoke a plugin action" => "调用插件操作",
        "Keep ANSI escape sequences while matching" => "匹配时保留 ANSI 转义序列",
        "Keybindings for --remote app attach (default: local)" => "--remote 应用附加的快捷键（默认: local）",
        "Launch or attach to the persistent session" => "启动或附加到持久会话",
        "Link a local plugin" => "链接本地插件",
        "List agents" => "列出智能体",
        "List installed plugins" => "列出已安装插件",
        "List or invoke plugin actions" => "列出或调用插件操作",
        "List panes" => "列出窗格",
        "List plugin actions" => "列出插件操作",
        "List plugin command logs" => "列出插件命令日志",
        "List saved SSH machines" => "列出已保存的 SSH 机器",
        "List sessions" => "列出会话",
        "List tabs" => "列出标签页",
        "List workspaces" => "列出工作区",
        "List worktree workspaces" => "列出 worktree 工作区",
        "Logs:" => "日志:",
        "Manage Git worktree-backed workspaces" => "管理基于 Git worktree 的工作区",
        "Manage built-in agent integrations" => "管理内置智能体集成",
        "Manage local configuration" => "管理本地配置",
        "Manage named persistent sessions" => "管理命名持久会话",
        "Manage plugin-owned panes" => "管理插件拥有的窗格",
        "Manage saved SSH machines" => "管理已保存的 SSH 机器",
        "Manage stable and preview update channels" => "管理 stable 与 preview 更新通道",
        "Manage tabs over the socket API" => "通过 socket API 管理标签页",
        "Manage the outer terminal title" => "管理外部终端标题",
        "Manage the stable or preview update channel" => "管理 stable 或 preview 更新通道",
        "Manage workspaces over the socket API" => "通过 socket API 管理工作区",
        "Match a Rust regular expression" => "匹配 Rust 正则表达式",
        "Match a literal substring" => "匹配字面子串",
        "Move a pane" => "移动窗格",
        "Notification helpers over the socket API" => "通过 socket API 的通知辅助命令",
        "Observe a terminal stream" => "观察终端流",
        "Open a plugin pane" => "打开插件窗格",
        "Open an existing Git worktree" => "打开现有 Git worktree",
        "Opt into live handoff for update or remote attach" => "在更新或远程附加时启用实时交接",
        "Options:" => "选项:",
        "Pane control helpers over the socket API" => "通过 socket API 的窗格控制辅助命令",
        "Prepare the remote Herdr server and save an SSH machine" => "准备远程 Herdr 服务器并保存 SSH 机器",
        "Print a plugin config directory" => "打印插件配置目录",
        "Print default configuration and exit" => "打印默认配置并退出",
        "Print or write the bundled API schema" => "打印或写出内置 API schema",
        "Print the agent skill file and exit" => "打印智能体 skill 文件并退出",
        "Print the configured update channel" => "打印已配置的更新通道",
        "Print the live session snapshot" => "打印实时会话快照",
        "Print version and exit" => "打印版本并退出",
        "Read agent terminal output" => "读取智能体终端输出",
        "Read pane terminal output" => "读取窗格终端输出",
        "Release pane agent lifecycle authority" => "释放窗格智能体生命周期权限",
        "Reload config in the running server" => "在运行中的服务器中重新加载配置",
        "Reload config.toml in the running server" => "在运行中的服务器中重新加载 config.toml",
        "Reload local agent detection manifest overrides" => "重新加载本地智能体检测清单覆盖",
        "Remove a saved SSH machine" => "删除已保存的 SSH 机器",
        "Remove a worktree checkout" => "删除 worktree 检出",
        "Rename a pane" => "重命名窗格",
        "Rename a saved SSH machine" => "重命名已保存的 SSH 机器",
        "Rename a tab" => "重命名标签页",
        "Rename a workspace" => "重命名工作区",
        "Rename an agent" => "重命名智能体",
        "Report display-only pane metadata" => "上报仅用于显示的窗格元数据",
        "Report display-only workspace metadata" => "上报仅用于显示的工作区元数据",
        "Report pane agent lifecycle state" => "上报窗格智能体生命周期状态",
        "Report pane agent session identity" => "上报窗格智能体会话标识",
        "Reset custom keybindings" => "重置自定义快捷键",
        "Resize a pane split" => "调整窗格分屏大小",
        "Restrict the searched snapshot to N lines" => "将搜索的快照限制为 N 行",
        "Run a command in a pane" => "在窗格中运行命令",
        "Run an API command on a saved SSH machine" => "在已保存的 SSH 机器上运行 API 命令",
        "Run as headless server" => "作为无界面服务器运行",
        "Run or control the headless server" => "运行或控制无界面服务器",
        "Send key presses to a pane" => "向窗格发送按键",
        "Send key presses to an agent" => "向智能体发送按键",
        "Send literal text to a pane" => "向窗格发送字面文本",
        "Set an environment variable for the launched process" => "为启动的进程设置环境变量",
        "Set pane input routing" => "设置窗格输入路由",
        "Set the explicit Herdr session on the remote machine" => "在远程机器上显式设置 Herdr 会话",
        "Set the machine label shown in the sidebar" => "设置侧边栏显示的机器标签",
        "Set the outer terminal title" => "设置外部终端标题",
        "Shell to generate completions for" => "要生成补全的 shell",
        "Show Herdr notifications" => "显示 Herdr 通知",
        "Show a notification" => "显示通知",
        "Show a pane" => "显示窗格",
        "Show a tab" => "显示标签页",
        "Show a workspace" => "显示工作区",
        "Show active agent detection manifests" => "显示活动的智能体检测清单",
        "Show an agent" => "显示智能体",
        "Show help" => "显示帮助",
        "Show integration status" => "显示集成状态",
        "Show local client and running server status" => "显示本地客户端和运行中服务器状态",
        "Show local client status" => "显示本地客户端状态",
        "Show pane edge information" => "显示窗格边缘信息",
        "Show pane layout information" => "显示窗格布局信息",
        "Show pane process information" => "显示窗格进程信息",
        "Show running server status" => "显示运行中服务器状态",
        "Show the current pane" => "显示当前窗格",
        "Show this help" => "显示此帮助",
        "Split a pane" => "分屏窗格",
        "Start a supported interactive agent in an existing pane" => "在现有窗格中启动受支持的交互式智能体",
        "State to match after --wait; repeat for more than one state" => "--wait 后要匹配的状态；可重复指定",
        "State to match; repeat for more than one state" => "要匹配的状态；可重复指定",
        "Stop a session" => "停止会话",
        "Stop the running server" => "停止运行中的服务器",
        "Stop the running server via the API socket" => "通过 API socket 停止运行中的服务器",
        "Submit a prompt to an agent" => "向智能体提交提示",
        "Supported agent kind and canonical executable" => "受支持的智能体类型与规范可执行文件",
        "Swap panes" => "交换窗格",
        "Tab helpers over the socket API" => "通过 socket API 的标签页辅助命令",
        "Terminal snapshot source (default: recent)" => "终端快照来源（默认: recent）",
        "Toggle or set pane zoom" => "切换或设置窗格缩放",
        "Try live handoff after installing" => "安装后尝试实时交接",
        "Uninstall a plugin" => "卸载插件",
        "Uninstall an integration" => "卸载集成",
        "Unlink a local plugin" => "取消链接本地插件",
        "Usage: herdr [options]" => "用法: herdr [options]",
        "Use or create a named persistent session" => "使用或创建命名持久会话",
        "Validate config.toml and print diagnostics" => "验证 config.toml 并打印诊断信息",
        "Wait for interactive readiness (default: 30000; max: 300000)" => "等待交互就绪（默认: 30000；最大: 300000）",
        "Wait for matching pane output" => "等待匹配的窗格输出",
        "Wait for the first matching state observed after submission" => "等待提交后观察到的第一个匹配状态",
        "Wait until an agent reaches one of the requested states" => "等待智能体进入任一请求状态",
        "Work with terminal sessions" => "处理终端会话",
        "Workspace helpers over the socket API" => "通过 socket API 的工作区辅助命令",
        "herdr — terminal workspace manager for AI coding agents" => "herdr — 面向 AI 编程智能体的终端工作区管理器",
        "terminal workspace manager for AI coding agents" => "面向 AI 编程智能体的终端工作区管理器",
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn japanese_translates_root_about() {
        assert_eq!(
            translate(
                UiLanguage::Ja,
                "terminal workspace manager for AI coding agents"
            ),
            "AI コーディングエージェント向けターミナルワークスペースマネージャー"
        );
    }

    #[test]
    fn missing_key_falls_back_to_english() {
        assert_eq!(
            translate(UiLanguage::Ja, "definitely not a catalog key"),
            "definitely not a catalog key"
        );
    }
}
