use super::*;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

pub(super) const START_TURNS_DEFAULT: u32 = 5;
pub(super) const START_TURNS_MIN: u32 = 1;
pub(super) const START_TURNS_MAX: u32 = 10;
pub(super) const SPAWN_REPORTS_DEFAULT: u32 = 3;
pub(super) const SPAWN_REPORTS_MIN: u32 = 1;
pub(super) const SPAWN_REPORTS_MAX: u32 = 7;

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
        return Err(format!("turns must be {START_TURNS_MIN}-{START_TURNS_MAX}"));
    }
    let parsed: u32 = turns
        .parse()
        .map_err(|_| format!("turns must be {START_TURNS_MIN}-{START_TURNS_MAX}"))?;
    if !(START_TURNS_MIN..=START_TURNS_MAX).contains(&parsed) {
        return Err(format!("turns must be {START_TURNS_MIN}-{START_TURNS_MAX}"));
    }
    Ok((goal.to_owned(), parsed))
}

pub(super) fn validate_spawn_reports(reports: &str) -> Result<u32, String> {
    let message = || format!("reports must be {SPAWN_REPORTS_MIN}-{SPAWN_REPORTS_MAX}");
    let parsed: u32 = reports.trim().parse().map_err(|_| message())?;
    if !(SPAWN_REPORTS_MIN..=SPAWN_REPORTS_MAX).contains(&parsed) {
        return Err(message());
    }
    Ok(parsed)
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

/// Build ``herdr-turns turn-run TURNS,goal`` without slash commands.
pub(super) fn build_hub_turn_run_launch(
    pane_id: &str,
    workdir: &Path,
    goal: &str,
    turns: u32,
    program: &str,
) -> StartTurnsLaunch {
    StartTurnsLaunch {
        program: program.to_owned(),
        args: vec![
            "turn-run".into(),
            format_turn_run_spec(turns, goal),
            "--notes-dir".into(),
            workdir.join("hub-notes").display().to_string(),
        ],
        env: vec![
            ("HERDR_ENV".into(), "1".into()),
            ("HERDR_PANE_ID".into(), pane_id.to_owned()),
        ],
        workdir: workdir.to_path_buf(),
    }
}

/// Build ``herdr-turns turn-spawn TURNS,goal --reports N``: split the lone
/// pane, start the same agent kind in N report panes, then run the hub.
pub(super) fn build_turn_spawn_launch(
    pane_id: &str,
    workdir: &Path,
    goal: &str,
    turns: u32,
    reports: u32,
    program: &str,
) -> StartTurnsLaunch {
    StartTurnsLaunch {
        program: program.to_owned(),
        args: vec![
            "turn-spawn".into(),
            format_turn_run_spec(turns, goal),
            "--reports".into(),
            reports.to_string(),
            "--notes-dir".into(),
            workdir.join("hub-notes").display().to_string(),
        ],
        env: vec![
            ("HERDR_ENV".into(), "1".into()),
            ("HERDR_PANE_ID".into(), pane_id.to_owned()),
        ],
        workdir: workdir.to_path_buf(),
    }
}

/// Build ``herdr-turns turn-stop --notes-dir <workdir>/hub-notes``.
pub(super) fn build_turn_stop_launch(
    pane_id: &str,
    workdir: &Path,
    program: &str,
) -> StartTurnsLaunch {
    StartTurnsLaunch {
        program: program.to_owned(),
        args: vec![
            "turn-stop".into(),
            "--notes-dir".into(),
            workdir.join("hub-notes").display().to_string(),
        ],
        env: vec![
            ("HERDR_ENV".into(), "1".into()),
            ("HERDR_PANE_ID".into(), pane_id.to_owned()),
        ],
        workdir: workdir.to_path_buf(),
    }
}

pub(super) fn build_turn_init_launch(
    pane_id: &str,
    workdir: &Path,
    program: &str,
) -> StartTurnsLaunch {
    StartTurnsLaunch {
        program: program.to_owned(),
        args: vec!["turn-init".into()],
        env: vec![
            ("HERDR_ENV".into(), "1".into()),
            ("HERDR_PANE_ID".into(), pane_id.to_owned()),
        ],
        workdir: workdir.to_path_buf(),
    }
}

/// Tab order; the report-count field only exists in spawn mode.
pub(super) fn next_start_turns_field(
    mode: ClientStartTurnsMode,
    field: ClientStartTurnsField,
) -> ClientStartTurnsField {
    match (field, mode) {
        (ClientStartTurnsField::Goal, _) => ClientStartTurnsField::Turns,
        (ClientStartTurnsField::Turns, ClientStartTurnsMode::Spawn) => {
            ClientStartTurnsField::Reports
        }
        (ClientStartTurnsField::Turns, _) | (ClientStartTurnsField::Reports, _) => {
            ClientStartTurnsField::Goal
        }
    }
}

fn format_turn_run_spec(turns: u32, goal: &str) -> String {
    // Prefer quoted form so commas in the goal stay inside the goal field.
    // Parser does not support escaped quotes; replace " with '.
    let safe = goal.replace('"', "'");
    format!("{turns},\"{safe}\"")
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

fn pane_workdir(state: &ClientShellState, pane_id: &str) -> String {
    state
        .snapshot
        .as_deref()
        .and_then(|snapshot| {
            snapshot
                .panes
                .iter()
                .find(|pane| pane.pane_id == pane_id)
                .and_then(|pane| pane.foreground_cwd.clone().or_else(|| pane.cwd.clone()))
        })
        .or_else(|| {
            state.snapshot.as_deref().and_then(|snapshot| {
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
        })
}

impl ClientShellState {
    pub(super) fn open_start_turns_overlay(&mut self, pane_id: String, mode: ClientStartTurnsMode) {
        let workdir = pane_workdir(self, &pane_id);
        let default_turns = match mode {
            ClientStartTurnsMode::FromHere => START_TURNS_DEFAULT,
            ClientStartTurnsMode::LeaderHub | ClientStartTurnsMode::Spawn => 3,
        };
        self.overlay = Some(ClientShellOverlay::StartTurns(ClientStartTurnsOverlay {
            pane_id,
            workdir,
            mode,
            goal: TextEditor::default(),
            turns: TextEditor::new(&default_turns.to_string(), true),
            reports: TextEditor::new(&SPAWN_REPORTS_DEFAULT.to_string(), true),
            focused: ClientStartTurnsField::Goal,
            error: None,
            starting: false,
        }));
    }

    pub(super) fn run_turn_init(&mut self, pane_id: String, outcome: &mut ClientShellInput) {
        let workdir = PathBuf::from(pane_workdir(self, &pane_id));
        let launch = build_turn_init_launch(&pane_id, &workdir, "herdr-turns");
        match spawn_start_turns_launch(&launch) {
            Ok(()) => {
                outcome.repaint = true;
            }
            Err(error) => {
                self.set_endpoint_error(error);
                outcome.repaint = true;
            }
        }
    }

    pub(super) fn run_turn_stop(&mut self, pane_id: String, outcome: &mut ClientShellInput) {
        let workdir = PathBuf::from(pane_workdir(self, &pane_id));
        let launch = build_turn_stop_launch(&pane_id, &workdir, "herdr-turns");
        if let Err(error) = spawn_start_turns_launch(&launch) {
            self.set_endpoint_error(error);
        }
        outcome.repaint = true;
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
            ClientStartTurnsField::Reports => {
                start.reports.insert(text);
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
                    ClientStartTurnsField::Reports => &mut start.reports,
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
                    start.focused = next_start_turns_field(start.mode, start.focused);
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
            if !start.starting
                && (field != ClientStartTurnsField::Reports
                    || start.mode == ClientStartTurnsMode::Spawn)
            {
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
        let mode = start.mode;
        let reports = if mode == ClientStartTurnsMode::Spawn {
            match validate_spawn_reports(&start.reports.to_string()) {
                Ok(reports) => reports,
                Err(error) => {
                    start.error = Some(error);
                    outcome.repaint = true;
                    return;
                }
            }
        } else {
            SPAWN_REPORTS_DEFAULT
        };
        match validate_start_turns_form(&goal, &turns) {
            Ok((goal, turns)) => {
                let launch = match mode {
                    ClientStartTurnsMode::FromHere => {
                        build_start_turns_launch(&pane_id, &workdir, &goal, turns, "herdr-turns")
                    }
                    ClientStartTurnsMode::LeaderHub => {
                        build_hub_turn_run_launch(&pane_id, &workdir, &goal, turns, "herdr-turns")
                    }
                    ClientStartTurnsMode::Spawn => build_turn_spawn_launch(
                        &pane_id,
                        &workdir,
                        &goal,
                        turns,
                        reports,
                        "herdr-turns",
                    ),
                };
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
        assert!(launch.env.iter().any(|(k, v)| k == "HERDR_ENV" && v == "1"));
        assert!(launch
            .env
            .iter()
            .any(|(k, v)| k == "HERDR_PANE_ID" && v == "w1:p1"));
        assert_eq!(launch.workdir, PathBuf::from("/repo"));
    }

    #[test]
    fn build_hub_turn_run_uses_turn_run_subcommand() {
        let launch = build_hub_turn_run_launch(
            "w1:p3",
            Path::new("/repo"),
            "ペイン間連携",
            3,
            "herdr-turns",
        );
        assert_eq!(launch.args[0], "turn-run");
        assert_eq!(launch.args[1], "3,\"ペイン間連携\"");
        assert!(launch.args.contains(&"--notes-dir".into()));
        assert!(launch
            .env
            .iter()
            .any(|(k, v)| k == "HERDR_PANE_ID" && v == "w1:p3"));
    }

    #[test]
    fn spawn_reports_validation_and_launch_args() {
        assert_eq!(validate_spawn_reports("3"), Ok(3));
        assert_eq!(validate_spawn_reports(" 7 "), Ok(7));
        assert!(validate_spawn_reports("0").is_err());
        assert!(validate_spawn_reports("8").is_err());
        assert!(validate_spawn_reports("x").is_err());
        let launch =
            build_turn_spawn_launch("w1:p1", Path::new("/repo"), "ship, it", 2, 5, "herdr-turns");
        assert_eq!(
            launch.args,
            vec![
                "turn-spawn".to_string(),
                "2,\"ship, it\"".to_string(),
                "--reports".to_string(),
                "5".to_string(),
                "--notes-dir".to_string(),
                "/repo/hub-notes".to_string(),
            ]
        );
        assert!(launch
            .env
            .contains(&("HERDR_PANE_ID".to_string(), "w1:p1".to_string())));
    }

    #[test]
    fn build_turn_stop_targets_hub_notes() {
        let launch = build_turn_stop_launch("w1:p1", Path::new("/repo"), "herdr-turns");
        assert_eq!(
            launch.args,
            vec![
                "turn-stop".to_string(),
                "--notes-dir".to_string(),
                "/repo/hub-notes".to_string(),
            ]
        );
    }

    #[test]
    fn tab_order_includes_reports_only_in_spawn_mode() {
        use ClientStartTurnsField::*;
        let spawn = ClientStartTurnsMode::Spawn;
        let hub = ClientStartTurnsMode::LeaderHub;
        assert_eq!(next_start_turns_field(spawn, Goal), Turns);
        assert_eq!(next_start_turns_field(spawn, Turns), Reports);
        assert_eq!(next_start_turns_field(spawn, Reports), Goal);
        assert_eq!(next_start_turns_field(hub, Turns), Goal);
    }

    #[test]
    fn build_turn_init_uses_subcommand_without_slash() {
        let launch = build_turn_init_launch("w1:p1", Path::new("/repo"), "herdr-turns");
        assert_eq!(launch.args, vec!["turn-init"]);
    }
}
