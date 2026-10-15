use super::*;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

pub(super) const START_TURNS_DEFAULT: u32 = 5;
pub(super) const START_TURNS_MIN: u32 = 1;
pub(super) const START_TURNS_MAX: u32 = 10;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct StartTurnsLaunch {
    pub(super) program: String,
    pub(super) args: Vec<String>,
    pub(super) env: Vec<(String, String)>,
    pub(super) workdir: PathBuf,
}

pub(super) fn validate_start_turns_form(goal: &str, turns: &str) -> Result<(String, u32), String> {
    let goal = goal.trim();
    if goal.is_empty() {
        return Err("goal is required".into());
    }
    let turns = turns.trim();
    if turns.is_empty() {
        return Err(format!(
            "turns must be {START_TURNS_MIN}-{START_TURNS_MAX}"
        ));
    }
    let parsed: u32 = turns
        .parse()
        .map_err(|_| format!("turns must be {START_TURNS_MIN}-{START_TURNS_MAX}"))?;
    if !(START_TURNS_MIN..=START_TURNS_MAX).contains(&parsed) {
        return Err(format!(
            "turns must be {START_TURNS_MIN}-{START_TURNS_MAX}"
        ));
    }
    Ok((goal.to_owned(), parsed))
}

pub(super) fn build_start_turns_launch(
    pane_id: &str,
    workdir: &Path,
    goal: &str,
    turns: u32,
    program: &str,
) -> StartTurnsLaunch {
    StartTurnsLaunch {
        program: program.to_owned(),
        args: vec![
            "--from-here".into(),
            "--daemon".into(),
            "--turns".into(),
            turns.to_string(),
            "--goal".into(),
            goal.to_owned(),
            "--workdir".into(),
            workdir.display().to_string(),
        ],
        env: vec![
            ("HERDR_ENV".into(), "1".into()),
            ("HERDR_PANE_ID".into(), pane_id.to_owned()),
        ],
        workdir: workdir.to_path_buf(),
    }
}

fn spawn_start_turns_launch(launch: &StartTurnsLaunch) -> Result<(), String> {
    let mut command = Command::new(&launch.program);
    command
        .args(&launch.args)
        .envs(launch.env.iter().cloned())
        .current_dir(&launch.workdir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    command
        .spawn()
        .map(|_| ())
        .map_err(|err| format!("failed to start {}: {err}", launch.program))
}

impl ClientShellState {
    pub(super) fn open_start_turns_overlay(&mut self, pane_id: String) {
        let workdir = self
            .snapshot
            .as_deref()
            .and_then(|snapshot| {
                snapshot
                    .panes
                    .iter()
                    .find(|pane| pane.pane_id == pane_id)
                    .and_then(|pane| {
                        pane.foreground_cwd
                            .clone()
                            .or_else(|| pane.cwd.clone())
                    })
            })
            .or_else(|| {
                self.snapshot.as_deref().and_then(|snapshot| {
                    let workspace_id = snapshot
                        .panes
                        .iter()
                        .find(|pane| pane.pane_id == pane_id)
                        .map(|pane| pane.workspace_id.as_str())?;
                    snapshot
                        .workspaces
                        .iter()
                        .find(|workspace| workspace.workspace_id == workspace_id)
                        .map(|workspace| workspace.new_workspace_cwd.clone())
                        .filter(|cwd| !cwd.is_empty())
                })
            })
            .unwrap_or_else(|| {
                std::env::current_dir()
                    .map(|path| path.display().to_string())
                    .unwrap_or_else(|_| ".".into())
            });
        self.overlay = Some(ClientShellOverlay::StartTurns(ClientStartTurnsOverlay {
            pane_id,
            workdir,
            goal: TextEditor::default(),
            turns: TextEditor::new(&START_TURNS_DEFAULT.to_string(), true),
            focused: ClientStartTurnsField::Goal,
            error: None,
            starting: false,
        }));
    }

    pub(super) fn insert_start_turns_overlay_text(&mut self, text: &str) -> bool {
        let Some(ClientShellOverlay::StartTurns(start)) = self.overlay.as_mut() else {
            return false;
        };
        if start.starting {
            return true;
        }
        match start.focused {
            ClientStartTurnsField::Goal => {
                start.goal.insert(text);
            }
            ClientStartTurnsField::Turns => {
                start.turns.insert(text);
            }
        }
        start.error = None;
        true
    }

    pub(super) fn route_start_turns_overlay_key(
        &mut self,
        key: &crate::input::TerminalKey,
        outcome: &mut ClientShellInput,
    ) -> bool {
        let Some(ClientShellOverlay::StartTurns(_)) = self.overlay.as_ref() else {
            return false;
        };
        let starting = matches!(
            self.overlay,
            Some(ClientShellOverlay::StartTurns(ClientStartTurnsOverlay {
                starting: true,
                ..
            }))
        );
        if !starting {
            if let Some(ClientShellOverlay::StartTurns(start)) = self.overlay.as_mut() {
                let editor = match start.focused {
                    ClientStartTurnsField::Goal => &mut start.goal,
                    ClientStartTurnsField::Turns => &mut start.turns,
                };
                if let Some(content_changed) = editor.handle_key(key) {
                    if content_changed {
                        start.error = None;
                    }
                    outcome.repaint = true;
                    return true;
                }
            }
        }
        let (code, _modifiers) = crate::config::normalize_key_combo((key.code, key.modifiers));
        match code {
            KeyCode::Esc if !starting => {
                self.overlay = None;
                outcome.repaint = true;
            }
            KeyCode::Tab if !starting => {
                if let Some(ClientShellOverlay::StartTurns(start)) = self.overlay.as_mut() {
                    start.focused = match start.focused {
                        ClientStartTurnsField::Goal => ClientStartTurnsField::Turns,
                        ClientStartTurnsField::Turns => ClientStartTurnsField::Goal,
                    };
                }
                outcome.repaint = true;
            }
            KeyCode::Enter => self.submit_start_turns(outcome),
            _ => {}
        }
        true
    }

    pub(super) fn focus_start_turns_field(&mut self, field: ClientStartTurnsField) {
        if let Some(ClientShellOverlay::StartTurns(start)) = self.overlay.as_mut() {
            if !start.starting {
                start.focused = field;
            }
        }
    }

    pub(super) fn submit_start_turns(&mut self, outcome: &mut ClientShellInput) {
        let Some(ClientShellOverlay::StartTurns(start)) = self.overlay.as_mut() else {
            return;
        };
        if start.starting {
            return;
        }
        let goal = start.goal.to_string();
        let turns = start.turns.to_string();
        let pane_id = start.pane_id.clone();
        let workdir = PathBuf::from(&start.workdir);
        match validate_start_turns_form(&goal, &turns) {
            Ok((goal, turns)) => {
                let launch =
                    build_start_turns_launch(&pane_id, &workdir, &goal, turns, "herdr-turns");
                start.starting = true;
                start.error = None;
                outcome.repaint = true;
                match spawn_start_turns_launch(&launch) {
                    Ok(()) => {
                        self.overlay = None;
                        outcome.repaint = true;
                    }
                    Err(error) => {
                        if let Some(ClientShellOverlay::StartTurns(start)) = self.overlay.as_mut() {
                            start.starting = false;
                            start.error = Some(error);
                        }
                        outcome.repaint = true;
                    }
                }
            }
            Err(error) => {
                start.error = Some(error);
                outcome.repaint = true;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_rejects_empty_goal_and_out_of_range_turns() {
        assert!(validate_start_turns_form("", "5").is_err());
        assert!(validate_start_turns_form("goal", "").is_err());
        assert!(validate_start_turns_form("goal", "0").is_err());
        assert!(validate_start_turns_form("goal", "11").is_err());
        assert!(validate_start_turns_form("goal", "abc").is_err());
        assert_eq!(
            validate_start_turns_form("  fix it  ", "5").unwrap(),
            ("fix it".into(), 5)
        );
    }

    #[test]
    fn build_launch_includes_daemon_flags_and_pane_env() {
        let launch = build_start_turns_launch(
            "w1:p1",
            Path::new("/repo"),
            "improve turns UX",
            3,
            "herdr-turns",
        );
        assert_eq!(launch.program, "herdr-turns");
        assert_eq!(
            launch.args,
            vec![
                "--from-here",
                "--daemon",
                "--turns",
                "3",
                "--goal",
                "improve turns UX",
                "--workdir",
                "/repo",
            ]
        );
        assert!(launch
            .env
            .iter()
            .any(|(k, v)| k == "HERDR_ENV" && v == "1"));
        assert!(launch
            .env
            .iter()
            .any(|(k, v)| k == "HERDR_PANE_ID" && v == "w1:p1"));
        assert_eq!(launch.workdir, PathBuf::from("/repo"));
    }
}
