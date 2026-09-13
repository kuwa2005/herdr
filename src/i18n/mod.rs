//! Client UI language catalog for Herdr chrome (menus, settings, overlays).
//!
//! Language is TUI presentation state persisted in `[ui].language`. Missing
//! translations fall back to English. Additional locales can be added by
//! extending [`crate::config::UiLanguage`] and the match arms below.

pub mod cli;

use crate::config::UiLanguage;

/// Stable message identifiers for translated client chrome.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Msg {
    // Global menu
    MenuSettings,
    MenuLanguage,
    MenuKeybinds,
    MenuReloadConfig,
    MenuUpdateReady,
    MenuWhatsNew,
    MenuDetach,

    // Settings chrome
    SettingsTitle,
    SettingsTabTheme,
    SettingsTabIndicators,
    SettingsTabSound,
    SettingsTabToasts,
    SettingsTabLanguage,
    SettingsTabIntegrations,
    SettingsApply,
    SettingsInstall,
    SettingsClose,
    SettingsHint,
    SettingsIndicatorsTitle,
    SettingsIndicatorsHelp,
    SettingsIndicatorsDots,
    SettingsIndicatorsSymbols,
    SettingsSoundTitle,
    SettingsSoundHelp,
    SettingsSoundOn,
    SettingsSoundOff,
    SettingsToastTitle,
    SettingsToastHelp,
    SettingsToastOff,
    SettingsToastHerdr,
    SettingsToastTerminal,
    SettingsToastSystem,
    SettingsLanguageTitle,
    SettingsLanguageHelp,

    // Context menu — workspace / tab / pane
    CtxRename,
    CtxClose,
    CtxCloseGroup,
    CtxNewWorktree,
    CtxOpenWorktree,
    CtxRemoveWorktree,
    CtxExpand,
    CtxCollapse,
    CtxNewTab,
    CtxRenamePane,
    CtxClearPaneName,
    CtxSwapWithFocused,
    CtxSplitRight,
    CtxSplitDown,
    CtxZoom,
    CtxUseHerdrRightClick,
    CtxSendRightClicksToPane,
    CtxClosePane,
}

/// Look up a translated string. Always returns a non-empty static string.
pub fn t(lang: UiLanguage, msg: Msg) -> &'static str {
    match lang {
        UiLanguage::En => en(msg),
        UiLanguage::Ja => ja(msg).unwrap_or_else(|| en(msg)),
        UiLanguage::ZhCn => zh_cn(msg).unwrap_or_else(|| en(msg)),
    }
}

fn en(msg: Msg) -> &'static str {
    match msg {
        Msg::MenuSettings => "settings",
        Msg::MenuLanguage => "language",
        Msg::MenuKeybinds => "keybinds",
        Msg::MenuReloadConfig => "reload config",
        Msg::MenuUpdateReady => "update ready",
        Msg::MenuWhatsNew => "what's new",
        Msg::MenuDetach => "detach",
        Msg::SettingsTitle => " settings",
        Msg::SettingsTabTheme => "theme",
        Msg::SettingsTabIndicators => "indicators",
        Msg::SettingsTabSound => "sound",
        Msg::SettingsTabToasts => "toasts",
        Msg::SettingsTabLanguage => "language",
        Msg::SettingsTabIntegrations => "integrations",
        Msg::SettingsApply => " ↵ apply ",
        Msg::SettingsInstall => " ↵ install ",
        Msg::SettingsClose => " esc close ",
        Msg::SettingsHint => " ↑↓ select  tab section",
        Msg::SettingsIndicatorsTitle => "agent status indicators",
        Msg::SettingsIndicatorsHelp => "choose color dots or distinct symbols for each state",
        Msg::SettingsIndicatorsDots => "color dots  ● ● ● ○ ·",
        Msg::SettingsIndicatorsSymbols => "distinct symbols  × ◐ ✓ ○ ·",
        Msg::SettingsSoundTitle => "sound alerts",
        Msg::SettingsSoundHelp => "play sounds when agents change state in background",
        Msg::SettingsSoundOn => "on",
        Msg::SettingsSoundOff => "off",
        Msg::SettingsToastTitle => "notification popups",
        Msg::SettingsToastHelp => "choose where background popup notifications should appear",
        Msg::SettingsToastOff => "off",
        Msg::SettingsToastHerdr => "inside herdr",
        Msg::SettingsToastTerminal => "via terminal",
        Msg::SettingsToastSystem => "via system",
        Msg::SettingsLanguageTitle => "interface language",
        Msg::SettingsLanguageHelp => "language for Herdr menus, settings, and overlays",
        Msg::CtxRename => "Rename",
        Msg::CtxClose => "Close",
        Msg::CtxCloseGroup => "Close group",
        Msg::CtxNewWorktree => "New worktree",
        Msg::CtxOpenWorktree => "Open worktree...",
        Msg::CtxRemoveWorktree => "Delete worktree checkout...",
        Msg::CtxExpand => "Expand",
        Msg::CtxCollapse => "Collapse",
        Msg::CtxNewTab => "New tab",
        Msg::CtxRenamePane => "Rename pane",
        Msg::CtxClearPaneName => "Clear pane name",
        Msg::CtxSwapWithFocused => "Swap with focused pane",
        Msg::CtxSplitRight => "Split right",
        Msg::CtxSplitDown => "Split down",
        Msg::CtxZoom => "Zoom",
        Msg::CtxUseHerdrRightClick => "Use Herdr right-click menu",
        Msg::CtxSendRightClicksToPane => "Send right-clicks to pane",
        Msg::CtxClosePane => "Close pane",
    }
}

fn ja(msg: Msg) -> Option<&'static str> {
    Some(match msg {
        Msg::MenuSettings => "設定",
        Msg::MenuLanguage => "言語",
        Msg::MenuKeybinds => "キーバインド",
        Msg::MenuReloadConfig => "設定を再読込",
        Msg::MenuUpdateReady => "更新の準備完了",
        Msg::MenuWhatsNew => "新着情報",
        Msg::MenuDetach => "デタッチ",
        Msg::SettingsTitle => " 設定",
        Msg::SettingsTabTheme => "テーマ",
        Msg::SettingsTabIndicators => "インジケータ",
        Msg::SettingsTabSound => "サウンド",
        Msg::SettingsTabToasts => "トースト",
        Msg::SettingsTabLanguage => "言語",
        Msg::SettingsTabIntegrations => "連携",
        Msg::SettingsApply => " ↵ 適用 ",
        Msg::SettingsInstall => " ↵ インストール ",
        Msg::SettingsClose => " esc 閉じる ",
        Msg::SettingsHint => " ↑↓ 選択  tab セクション",
        Msg::SettingsIndicatorsTitle => "エージェント状態インジケータ",
        Msg::SettingsIndicatorsHelp => "色付きドットか状態ごとの記号を選べます",
        Msg::SettingsIndicatorsDots => "カラードット  ● ● ● ○ ·",
        Msg::SettingsIndicatorsSymbols => "記号  × ◐ ✓ ○ ·",
        Msg::SettingsSoundTitle => "サウンド通知",
        Msg::SettingsSoundHelp => "バックグラウンドでエージェント状態が変わったときに音を鳴らす",
        Msg::SettingsSoundOn => "オン",
        Msg::SettingsSoundOff => "オフ",
        Msg::SettingsToastTitle => "通知ポップアップ",
        Msg::SettingsToastHelp => "バックグラウンド通知の表示先を選びます",
        Msg::SettingsToastOff => "オフ",
        Msg::SettingsToastHerdr => "Herdr 内",
        Msg::SettingsToastTerminal => "ターミナル経由",
        Msg::SettingsToastSystem => "システム経由",
        Msg::SettingsLanguageTitle => "表示言語",
        Msg::SettingsLanguageHelp => "メニュー・設定・オーバーレイの言語",
        Msg::CtxRename => "名前変更",
        Msg::CtxClose => "閉じる",
        Msg::CtxCloseGroup => "グループを閉じる",
        Msg::CtxNewWorktree => "新しい worktree",
        Msg::CtxOpenWorktree => "worktree を開く...",
        Msg::CtxRemoveWorktree => "worktree チェックアウトを削除...",
        Msg::CtxExpand => "展開",
        Msg::CtxCollapse => "折りたたむ",
        Msg::CtxNewTab => "新しいタブ",
        Msg::CtxRenamePane => "ペイン名を変更",
        Msg::CtxClearPaneName => "ペイン名をクリア",
        Msg::CtxSwapWithFocused => "フォーカス中のペインと入れ替え",
        Msg::CtxSplitRight => "右に分割",
        Msg::CtxSplitDown => "下に分割",
        Msg::CtxZoom => "ズーム",
        Msg::CtxUseHerdrRightClick => "Herdr の右クリックメニューを使う",
        Msg::CtxSendRightClicksToPane => "右クリックをペインに送る",
        Msg::CtxClosePane => "ペインを閉じる",
    })
}

fn zh_cn(msg: Msg) -> Option<&'static str> {
    Some(match msg {
        Msg::MenuSettings => "设置",
        Msg::MenuLanguage => "语言",
        Msg::MenuKeybinds => "快捷键",
        Msg::MenuReloadConfig => "重新加载配置",
        Msg::MenuUpdateReady => "更新就绪",
        Msg::MenuWhatsNew => "新功能",
        Msg::MenuDetach => "分离",
        Msg::SettingsTitle => " 设置",
        Msg::SettingsTabTheme => "主题",
        Msg::SettingsTabIndicators => "指示器",
        Msg::SettingsTabSound => "声音",
        Msg::SettingsTabToasts => "通知",
        Msg::SettingsTabLanguage => "语言",
        Msg::SettingsTabIntegrations => "集成",
        Msg::SettingsApply => " ↵ 应用 ",
        Msg::SettingsInstall => " ↵ 安装 ",
        Msg::SettingsClose => " esc 关闭 ",
        Msg::SettingsHint => " ↑↓ 选择  tab 分区",
        Msg::SettingsIndicatorsTitle => "智能体状态指示器",
        Msg::SettingsIndicatorsHelp => "选择彩色圆点或各状态的独立符号",
        Msg::SettingsIndicatorsDots => "彩色圆点  ● ● ● ○ ·",
        Msg::SettingsIndicatorsSymbols => "独立符号  × ◐ ✓ ○ ·",
        Msg::SettingsSoundTitle => "声音提醒",
        Msg::SettingsSoundHelp => "后台智能体状态变化时播放声音",
        Msg::SettingsSoundOn => "开",
        Msg::SettingsSoundOff => "关",
        Msg::SettingsToastTitle => "通知弹窗",
        Msg::SettingsToastHelp => "选择后台弹窗通知的显示位置",
        Msg::SettingsToastOff => "关",
        Msg::SettingsToastHerdr => "Herdr 内",
        Msg::SettingsToastTerminal => "通过终端",
        Msg::SettingsToastSystem => "通过系统",
        Msg::SettingsLanguageTitle => "界面语言",
        Msg::SettingsLanguageHelp => "Herdr 菜单、设置和浮层所用的语言",
        Msg::CtxRename => "重命名",
        Msg::CtxClose => "关闭",
        Msg::CtxCloseGroup => "关闭分组",
        Msg::CtxNewWorktree => "新建 worktree",
        Msg::CtxOpenWorktree => "打开 worktree...",
        Msg::CtxRemoveWorktree => "删除 worktree 检出...",
        Msg::CtxExpand => "展开",
        Msg::CtxCollapse => "折叠",
        Msg::CtxNewTab => "新建标签页",
        Msg::CtxRenamePane => "重命名窗格",
        Msg::CtxClearPaneName => "清除窗格名称",
        Msg::CtxSwapWithFocused => "与焦点窗格交换",
        Msg::CtxSplitRight => "向右分屏",
        Msg::CtxSplitDown => "向下分屏",
        Msg::CtxZoom => "缩放",
        Msg::CtxUseHerdrRightClick => "使用 Herdr 右键菜单",
        Msg::CtxSendRightClicksToPane => "将右键发送到窗格",
        Msg::CtxClosePane => "关闭窗格",
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_msg_has_english() {
        for msg in [
            Msg::MenuSettings,
            Msg::MenuLanguage,
            Msg::SettingsTabLanguage,
            Msg::CtxClosePane,
        ] {
            assert!(!t(UiLanguage::En, msg).is_empty());
        }
    }

    #[test]
    fn japanese_and_chinese_differ_from_english_for_menus() {
        assert_ne!(
            t(UiLanguage::Ja, Msg::MenuSettings),
            t(UiLanguage::En, Msg::MenuSettings)
        );
        assert_ne!(
            t(UiLanguage::ZhCn, Msg::MenuSettings),
            t(UiLanguage::En, Msg::MenuSettings)
        );
        assert_eq!(t(UiLanguage::Ja, Msg::MenuLanguage), "言語");
        assert_eq!(t(UiLanguage::ZhCn, Msg::MenuLanguage), "语言");
    }
}
