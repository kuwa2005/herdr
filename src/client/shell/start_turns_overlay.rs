use super::*;

pub(super) fn render_start_turns_overlay(
    b: &mut Buffer,
    start: &ClientStartTurnsOverlay,
    language: crate::config::UiLanguage,
    p: &Palette,
) -> Option<OverlayRender> {
    let title = crate::i18n::t(language, crate::i18n::Msg::CtxStartTurns)
        .trim_end_matches("...")
        .trim_end_matches('…');
    let popup = popup(b.area, 72, 14)?;
    let inner = panel(b, popup, p.accent, p.panel_bg)?;
    put_text(
        b,
        inner.x,
        inner.y,
        inner.width,
        &format!(" {title}"),
        Style::default()
            .fg(p.text)
            .bg(p.panel_bg)
            .add_modifier(Modifier::BOLD),
    );
    put_text(
        b,
        inner.x,
        inner.y + 2,
        inner.width,
        " goal",
        Style::default().fg(p.overlay0).bg(p.panel_bg),
    );
    let goal = Rect::new(inner.x, inner.y + 3, inner.width, 1);
    let goal_bg = if start.focused == ClientStartTurnsField::Goal {
        p.surface0
    } else {
        p.panel_bg
    };
    b.set_style(goal, Style::default().fg(p.text).bg(goal_bg));
    let goal_cursor = text_editor::render(
        b,
        Rect::new(goal.x + 1, goal.y, goal.width.saturating_sub(1), 1),
        &start.goal,
        Style::default().fg(p.text).bg(goal_bg),
    );
    put_text(
        b,
        inner.x,
        inner.y + 5,
        inner.width,
        " turns (1-10)",
        Style::default().fg(p.overlay0).bg(p.panel_bg),
    );
    let turns = Rect::new(inner.x, inner.y + 6, inner.width.min(12), 1);
    let turns_bg = if start.focused == ClientStartTurnsField::Turns {
        p.surface0
    } else {
        p.panel_bg
    };
    b.set_style(turns, Style::default().fg(p.text).bg(turns_bg));
    let turns_cursor = text_editor::render(
        b,
        Rect::new(turns.x + 1, turns.y, turns.width.saturating_sub(1), 1),
        &start.turns,
        Style::default().fg(p.text).bg(turns_bg),
    );
    put_text(
        b,
        inner.x,
        inner.y + 8,
        inner.width,
        &format!(" cwd {}", start.workdir),
        Style::default().fg(p.subtext0).bg(p.panel_bg),
    );
    if start.starting {
        put_text(
            b,
            inner.x,
            inner.y + 9,
            inner.width,
            " starting…",
            Style::default().fg(p.accent).bg(p.panel_bg),
        );
    } else if let Some(error) = start.error.as_deref() {
        put_text(
            b,
            inner.x,
            inner.y + 9,
            inner.width,
            &format!(" {error}"),
            Style::default().fg(p.red).bg(p.panel_bg),
        );
    } else {
        put_text(
            b,
            inner.x,
            inner.y + 9,
            inner.width,
            " tab field  ↵ start  esc cancel",
            Style::default().fg(p.overlay0).bg(p.panel_bg),
        );
    }
    let buttons = row(inner, &[16, 12], 2, 11);
    let [primary, cancel] = buttons.as_slice() else {
        return None;
    };
    button(
        b,
        *primary,
        " ↵ start ",
        Style::default()
            .fg(contrast(p))
            .bg(p.accent)
            .add_modifier(Modifier::BOLD),
    );
    button(
        b,
        *cancel,
        " esc cancel ",
        Style::default()
            .fg(p.text)
            .bg(p.surface0)
            .add_modifier(Modifier::BOLD),
    );
    let cursor = if start.starting {
        None
    } else {
        match start.focused {
            ClientStartTurnsField::Goal => goal_cursor,
            ClientStartTurnsField::Turns => turns_cursor,
        }
    };
    Some(OverlayRender {
        area: popup,
        primary: *primary,
        clear: Rect::default(),
        cancel: *cancel,
        start_turns_goal: goal,
        start_turns_turns: turns,
        cursor,
        ..OverlayRender::default()
    })
}
