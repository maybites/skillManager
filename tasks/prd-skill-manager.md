# PRD: Skill Manager

## Introduction

Skill Manager is a desktop GUI application (Python + NiceGUI, launched via `uv`) for managing Claude Code skills. It solves the problem of manually tracking, updating, and symlinking skills from multiple git repositories into the correct Claude Code skill directories — either the personal skill folder (`~/.claude/skills/`) or per-project folders (`.claude/skills/` inside a managed project).

Users can add skill source repositories (by remote URL or local path), discover which folders are skills via `.md`-based auto-detection, confirm the skill set, and then use a checkbox matrix to symlink any skill to any combination of personal and project targets.

---

## Goals

- A user can add a skill repo and have its skills symlinked in under 2 minutes
- All symlink state is visible at a glance in a single checkbox matrix
- Manual git pulls keep repos up-to-date without risk of silent breakage
- Broken symlinks and missing project paths are surfaced and actionable, never silently ignored
- The app is well-behaved on macOS/Linux (XDG storage, system git, no auth UI required)

---

## User Stories

### US-001: Add a remote skill repository by URL
**Description:** As a user, I want to add a skill repository by pasting a git URL so that the app clones it into managed storage and I can start symlinking its skills.

**Acceptance Criteria:**
- [ ] "Add Source" button in the Skill Sources sidebar section opens an input dialog
- [ ] User can enter a git remote URL and an optional display name
- [ ] App clones the repo into `~/.local/share/skillmanager/repos/<repo-name>/` using the system `git` binary
- [ ] Clone errors (bad URL, auth failure, no network) are shown as an inline error message
- [ ] On success, the new source appears in the sidebar and detail panel opens

### US-002: Register a local skill repository by path
**Description:** As a user, I want to register an already-cloned local folder as a skill source so I can symlink skills I'm developing locally.

**Acceptance Criteria:**
- [ ] The "Add Source" dialog has a toggle between "Remote URL" and "Local Path"
- [ ] Local path mode shows a file-browser or text input for a directory path
- [ ] The path is registered in config as-is (no copy or clone)
- [ ] If the path does not exist on disk, an inline error is shown before saving
- [ ] On success, the source appears in the sidebar

### US-003: Auto-detect skills in a repository with user confirmation
**Description:** As a user, I want the app to suggest which folders in a repo are skills so I don't have to manually identify them, while still being able to override the detection.

**Acceptance Criteria:**
- [ ] After adding a source, the detail panel shows a list of candidate skill folders (any directory containing at least one `.md` file, excluding repo root)
- [ ] Each candidate has a checkbox defaulting to enabled
- [ ] User can uncheck false positives (e.g. `docs/`, `tests/`)
- [ ] A "Confirm Skills" button saves the selection to config
- [ ] The confirmed skill list is shown in the checkbox matrix (US-006)

### US-004: Add a managed project
**Description:** As a user, I want to register a project directory so I can symlink skills into its `.claude/skills/` folder.

**Acceptance Criteria:**
- [ ] "Add Project" button in the Projects sidebar section opens an input dialog
- [ ] User provides a filesystem path and a display name (defaults to folder name)
- [ ] If the path does not exist, an inline error is shown
- [ ] On success, the project appears in the sidebar and becomes a column in the checkbox matrix
- [ ] The app auto-creates `.claude/skills/` inside the project if it does not exist

### US-005: View and navigate skill sources and projects
**Description:** As a user, I want to see all my skill sources and projects in a sidebar so I can quickly navigate to any of them.

**Acceptance Criteria:**
- [ ] Sidebar has two collapsible sections: "Skill Sources" and "Projects"
- [ ] Each entry shows its display name
- [ ] Clicking an entry opens its detail panel on the right
- [ ] Detail panel for a source shows: repo path/URL, confirmed skills, last-updated timestamp, Update and Remove buttons
- [ ] Detail panel for a project shows: path, display name, symlink status summary, Edit and Remove buttons

### US-006: Symlink skills via checkbox matrix
**Description:** As a user, I want a grid showing all skills and all targets so I can enable or disable any symlink with a single click.

**Acceptance Criteria:**
- [ ] A "Symlinks" view (accessible from the main area) shows a matrix: rows = confirmed skills (grouped by source), columns = Personal + each managed project
- [ ] A checked cell means a symlink exists: `<target>/skills/<skill-name>` → `<source-repo>/<skill-folder>/`
- [ ] Checking a cell creates the symlink immediately; unchecking removes it
- [ ] Symlinks are always folder-level (symlink the skill directory, not individual files)
- [ ] Target skill directories (`~/.claude/skills/`, `.claude/skills/`) are auto-created if missing
- [ ] Checked state reflects actual filesystem state on app load (not just config)

### US-007: Resolve symlink conflicts
**Description:** As a user, I want to be notified when two sources provide a skill with the same folder name so I can decide which one wins for each target.

**Acceptance Criteria:**
- [ ] If two confirmed skills share the same folder name, a conflict indicator appears on both rows in the matrix
- [ ] Attempting to check a conflicting cell when another source already occupies that target shows a conflict dialog
- [ ] The conflict dialog identifies both sources and asks which should win
- [ ] Each target resolves its conflict independently (personal and each project are separate)
- [ ] Resolved conflicts are persisted in config

### US-008: Manually update a skill repository
**Description:** As a user, I want to pull the latest changes for a skill repo so my symlinked skills stay current.

**Acceptance Criteria:**
- [ ] Each remote source's detail panel has an "Update" button that runs `git pull` in the repo directory
- [ ] A top-level "Update All" button runs `git pull` on all remote sources sequentially
- [ ] Local-path sources show "Update" as disabled (greyed out with tooltip "Local path — manage updates manually")
- [ ] Pull output (stdout/stderr) is shown inline during and after the operation
- [ ] On completion, the app scans for broken symlinks (see US-009)

### US-009: Detect and resolve broken symlinks after update
**Description:** As a user, I want to know when a git pull has broken existing symlinks so I can fix them rather than silently having broken skills.

**Acceptance Criteria:**
- [ ] After every update (single or "Update All"), the app scans all managed symlinks for broken targets
- [ ] If broken symlinks are found, a warning banner or modal lists them (symlink path, expected target, source repo)
- [ ] Each broken symlink has two actions: "Remove symlink" and "Re-map" (opens skill picker for that target slot)
- [ ] If no broken symlinks are found, a brief success toast is shown

### US-010: Handle missing project paths
**Description:** As a user, I want to be warned when a registered project no longer exists on disk so I can update the path or remove the project.

**Acceptance Criteria:**
- [ ] On app launch, all registered project paths are validated
- [ ] Projects with missing paths are shown with a warning icon in the sidebar
- [ ] Their detail panel shows the missing path and two actions: "Update Path" (opens path input) and "Remove Project"
- [ ] Symlink matrix columns for missing projects are greyed out with a tooltip explaining why

### US-011: Remove a skill source
**Description:** As a user, I want to remove a skill source and clean up its symlinks so I don't have orphaned links.

**Acceptance Criteria:**
- [ ] Source detail panel has a "Remove" button
- [ ] Clicking shows a confirmation dialog listing all active symlinks that will be removed
- [ ] On confirm: all symlinks from that source are deleted, the source is removed from config
- [ ] Cloned repos (remote sources) are deleted from `~/.local/share/skillmanager/repos/`; local paths are only de-registered

### US-012: Launch the app
**Description:** As a user, I want to launch Skill Manager with a single command so I can access it quickly.

**Acceptance Criteria:**
- [ ] `uv run skillmanager` launches the NiceGUI app and opens it in the default browser
- [ ] `uv tool install .` installs `skillmanager` as a global command
- [ ] App binds to `localhost` only (not exposed on network interfaces)
- [ ] App title is "Skill Manager"

---

## Functional Requirements

- FR-1: Clone remote git repos using system `git` binary into `~/.local/share/skillmanager/repos/`
- FR-2: Register local paths without copying; validate existence on add and on launch
- FR-3: Auto-detect skill candidates as any subdirectory containing at least one `.md` file
- FR-4: Persist all state (sources, confirmed skills, projects, conflict resolutions) in `~/.config/skillmanager/config.toml`
- FR-5: Symlinks are always directory-level; target directories are auto-created if missing
- FR-6: Checkbox matrix reflects actual filesystem symlink state on every load
- FR-7: Manual `git pull` only; no auto-update on launch or on a schedule
- FR-8: Post-update broken symlink scan is always triggered after any pull
- FR-9: Conflicts are detected when two confirmed skills share the same folder name and target the same destination; resolved per-target
- FR-10: CLI entrypoint defined in `[project.scripts]` in `pyproject.toml`; app serves on localhost only

---

## Non-Goals

- No automatic/scheduled git pulls
- No HTTPS token or credential UI (system SSH keys only)
- No file-level symlinks (folder-level only)
- No skill search, tagging, or categorization
- No publishing or uploading skills to remote repos
- No Windows support (macOS/Linux only)
- No support for symlink targets outside `~/.claude/skills/` or `.claude/skills/` inside a managed project

---

## Design Considerations

- **Layout:** Sidebar (left, ~250px) + detail panel (right, flexible). Sidebar has two collapsible sections: "Skill Sources" and "Projects".
- **Symlinks view:** Full-width checkbox matrix, accessible from a top nav or button. Rows grouped by source, columns: Personal first, then projects in add-order.
- **NiceGUI components:** `ui.splitter` for sidebar/detail, `ui.table` or `ui.grid` for the checkbox matrix, `ui.dialog` for add/conflict/confirm flows, `ui.notify` for toasts.
- **Color conventions:** Broken/missing items use amber/red indicators; healthy symlinks use green checkmarks; disabled controls use grey.

---

## Technical Considerations

- **Runtime:** Python 3.11+, managed with `uv`
- **UI framework:** NiceGUI (latest stable)
- **Storage:** `~/.config/skillmanager/config.toml` (config), `~/.local/share/skillmanager/repos/` (cloned repos)
- **Git operations:** Subprocess calls to system `git`; capture stdout/stderr for display
- **Symlink operations:** `os.symlink`, `os.readlink`, `os.path.exists` (not `os.path.lexists`) for broken link detection
- **Config format:** TOML via `tomllib` (stdlib, Python 3.11+) for read, `tomli-w` for write
- **Entrypoint:** `[project.scripts] skillmanager = "skillmanager.main:run"` in `pyproject.toml`

---

## Success Metrics

- A user can add a new skill repo and have at least one skill symlinked in under 2 minutes from a cold start
- The checkbox matrix correctly reflects actual filesystem state after every launch
- No symlink is created or destroyed without explicit user action

---

## Open Questions

- Should the app support renaming a skill source's display name after initial setup?
- Should confirmed skill selections persist across repo updates, or re-prompt after a pull changes the folder structure?
- Is there a maximum number of projects or sources to design for in the matrix layout (scrolling vs. pagination)?
