//! Append-only markdown journal of session instructions and agent completions.
//!
//! Written to both:
//! - `{session_data_dir}/herdrlog.md` (for example `~/.config/herdr/herdrlog.md`)
//! - `{cwd}/herdrlog.md` (server process current directory)
//!
//! Instructions come from `agent.prompt` and from TUI typing in agent panes
//! (buffered until Enter). Writes are best-effort and never fail the caller.

use std::collections::HashMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

const COMPLETION_REPORT_MAX_CHARS: usize = 4_000;
const DRAFT_MAX_CHARS: usize = 8_000;
/// Fixed journal filename (not the session id — avoids `default.md` clutter).
pub const JOURNAL_FILENAME: &str = "herdrlog.md";

/// Per-pane draft buffer for TUI keystrokes until Enter submits them.
#[derive(Debug, Default)]
pub struct InstructionDrafts {
    by_pane: HashMap<String, String>,
}

impl InstructionDrafts {
    pub fn append(&mut self, pane_id: &str, text: &str) {
        if text.is_empty() {
            return;
        }
        let draft = self.by_pane.entry(pane_id.to_owned()).or_default();
        draft.push_str(text);
        if draft.len() > DRAFT_MAX_CHARS {
            let keep = draft
                .char_indices()
                .rev()
                .find_map(|(idx, _)| (draft.len() - idx <= DRAFT_MAX_CHARS).then_some(idx))
                .unwrap_or(0);
            draft.replace_range(..keep, "");
        }
    }

    pub fn backspace(&mut self, pane_id: &str) {
        let Some(draft) = self.by_pane.get_mut(pane_id) else {
            return;
        };
        draft.pop();
        if draft.is_empty() {
            self.by_pane.remove(pane_id);
        }
    }

    pub fn clear(&mut self, pane_id: &str) {
        self.by_pane.remove(pane_id);
    }

    /// Take the draft when the user submits (Enter). Empty/whitespace-only → None.
    pub fn take_submitted(&mut self, pane_id: &str) -> Option<String> {
        let draft = self.by_pane.remove(pane_id)?;
        let trimmed = draft.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed.to_owned())
        }
    }
}

/// Session id recorded in the journal header (`default` when unnamed).
pub fn session_id() -> String {
    crate::session::active_name().unwrap_or_else(|| crate::session::DEFAULT_SESSION_NAME.to_owned())
}

/// Path to `herdrlog.md` under the active session data directory.
pub fn journal_path() -> PathBuf {
    journal_path_in(&crate::session::data_dir())
}

/// Path to `herdrlog.md` under the server process current directory.
pub fn cwd_journal_path() -> Option<PathBuf> {
    let cwd = std::env::current_dir().ok()?;
    Some(journal_path_in(&cwd))
}

pub fn journal_path_in(dir: &Path) -> PathBuf {
    dir.join(JOURNAL_FILENAME)
}

/// Destinations that should receive the same journal append (deduped by path).
fn journal_destinations() -> Vec<PathBuf> {
    let mut paths = vec![journal_path()];
    if let Some(cwd_path) = cwd_journal_path() {
        let same = paths.iter().any(|p| paths_equal(p, &cwd_path));
        if !same {
            paths.push(cwd_path);
        }
    }
    paths
}

fn paths_equal(a: &Path, b: &Path) -> bool {
    if a == b {
        return true;
    }
    match (fs::canonicalize(a), fs::canonicalize(b)) {
        (Ok(ca), Ok(cb)) => ca == cb,
        _ => false,
    }
}

fn append_to_all(session_id: &str, block: &str, kind: &str) {
    for path in journal_destinations() {
        if let Err(err) = append_block(&path, session_id, block) {
            tracing::warn!(
                error = %err,
                path = %path.display(),
                kind,
                "session journal: failed to record entry"
            );
        }
    }
}

fn now_rfc3339() -> String {
    OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .unwrap_or_else(|_| {
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| format!("{}Z", d.as_secs()))
                .unwrap_or_else(|_| "unknown".into())
        })
}

fn ensure_header(path: &Path, session_id: &str) -> std::io::Result<()> {
    if path.exists() {
        return Ok(());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let header = format!(
        "# Session journal: {session_id}\n\n\
         指示（入力）とエージェント完了時のレポートを追記します。\n\n"
    );
    fs::write(path, header)
}

fn append_block(path: &Path, session_id: &str, block: &str) -> std::io::Result<()> {
    ensure_header(path, session_id)?;
    let mut file = OpenOptions::new().create(true).append(true).open(path)?;
    file.write_all(block.as_bytes())?;
    Ok(())
}

fn truncate_report(text: &str) -> String {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return "_(empty)_".to_owned();
    }
    let mut out = String::new();
    for ch in trimmed.chars() {
        if out.len() >= COMPLETION_REPORT_MAX_CHARS {
            out.push('…');
            break;
        }
        out.push(ch);
    }
    out
}

/// Format an instruction entry (unit-testable).
pub fn format_instruction_entry(
    when: &str,
    target: &str,
    pane_id: Option<&str>,
    text: &str,
) -> String {
    let pane = pane_id.unwrap_or("—");
    format!(
        "## 指示 · {when}\n\n\
         - target: `{target}`\n\
         - pane: `{pane}`\n\n\
         ```text\n\
         {text}\n\
         ```\n\n"
    )
}

/// Format a completion / finished report entry (unit-testable).
pub fn format_completion_entry(
    when: &str,
    agent_label: &str,
    pane_id: Option<&str>,
    previous_state: &str,
    state: &str,
    report: &str,
) -> String {
    let pane = pane_id.unwrap_or("—");
    let body = truncate_report(report);
    format!(
        "## 完了 · {when}\n\n\
         - agent: `{agent_label}`\n\
         - pane: `{pane}`\n\
         - transition: `{previous_state}` → `{state}`\n\n\
         ### レポート\n\n\
         ```text\n\
         {body}\n\
         ```\n\n"
    )
}

/// Append an instruction (agent.prompt / structured input) to the journal.
pub fn record_instruction(enabled: bool, target: &str, pane_id: Option<&str>, text: &str) {
    if !enabled || text.is_empty() {
        return;
    }
    let id = session_id();
    let block = format_instruction_entry(&now_rfc3339(), target, pane_id, text);
    append_to_all(&id, &block, "instruction");
}

/// Append a TUI/agent completion report when work settles to idle/done.
pub fn record_completion(
    enabled: bool,
    agent_label: &str,
    pane_id: Option<&str>,
    previous_state: &str,
    state: &str,
    report: &str,
) {
    if !enabled {
        return;
    }
    let id = session_id();
    let block = format_completion_entry(
        &now_rfc3339(),
        agent_label,
        pane_id,
        previous_state,
        state,
        report,
    );
    append_to_all(&id, &block, "completion");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("herdr-session-journal-{nanos}"));
        fs::create_dir_all(&dir).expect("mkdir");
        dir
    }

    #[test]
    fn journal_path_uses_fixed_herdrlog_filename() {
        let dir = PathBuf::from("/tmp/herdr-sess");
        assert_eq!(
            journal_path_in(&dir),
            PathBuf::from("/tmp/herdr-sess/herdrlog.md")
        );
        assert_eq!(JOURNAL_FILENAME, "herdrlog.md");
    }

    #[test]
    fn instruction_entry_contains_input() {
        let text = format_instruction_entry(
            "2026-10-15T10:00:00+09:00",
            "coder",
            Some("w1:p1"),
            "fix the bug",
        );
        assert!(text.contains("## 指示"));
        assert!(text.contains("`coder`"));
        assert!(text.contains("fix the bug"));
    }

    #[test]
    fn completion_entry_contains_report() {
        let text = format_completion_entry(
            "2026-10-15T10:01:00+09:00",
            "cursor",
            Some("w1:p1"),
            "working",
            "idle",
            "All tests passed",
        );
        assert!(text.contains("## 完了"));
        assert!(text.contains("working` → `idle"));
        assert!(text.contains("All tests passed"));
    }

    #[test]
    fn append_writes_header_once() {
        let dir = temp_dir();
        let path = journal_path_in(&dir);
        append_block(&path, "default", "## 指示 · t1\n\nhello\n").expect("first");
        append_block(&path, "default", "## 完了 · t2\n\ndone\n").expect("second");
        let body = fs::read_to_string(&path).expect("read");
        assert_eq!(body.matches("# Session journal: default").count(), 1);
        assert!(path.ends_with("herdrlog.md"));
        assert!(body.contains("## 指示 · t1"));
        assert!(body.contains("## 完了 · t2"));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn truncate_report_limits_size() {
        let long = "x".repeat(COMPLETION_REPORT_MAX_CHARS + 50);
        let out = truncate_report(&long);
        assert!(out.ends_with('…'));
        assert!(out.len() <= COMPLETION_REPORT_MAX_CHARS + 3);
    }

    #[test]
    fn paths_equal_matches_identical_paths() {
        let a = PathBuf::from("/tmp/herdr-a/herdrlog.md");
        assert!(paths_equal(&a, &a));
        assert!(!paths_equal(
            &a,
            &PathBuf::from("/tmp/herdr-b/herdrlog.md")
        ));
    }

    #[test]
    fn drafts_submit_on_take_after_append() {
        let mut drafts = InstructionDrafts::default();
        drafts.append("w1:p1", "fix ");
        drafts.append("w1:p1", "the bug");
        assert_eq!(
            drafts.take_submitted("w1:p1").as_deref(),
            Some("fix the bug")
        );
        assert!(drafts.take_submitted("w1:p1").is_none());
    }

    #[test]
    fn drafts_backspace_and_clear() {
        let mut drafts = InstructionDrafts::default();
        drafts.append("p", "ab");
        drafts.backspace("p");
        assert_eq!(drafts.take_submitted("p").as_deref(), Some("a"));
        drafts.append("p", "xy");
        drafts.clear("p");
        assert!(drafts.take_submitted("p").is_none());
    }
}
