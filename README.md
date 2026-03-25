# Skill Manager

A GUI application for managing [Claude Code](https://claude.ai/claude-code) skills — clone skill repositories, symlink skills to personal and project-specific directories, and keep everything in sync.

![Skill Manager UI](docs/screenshot.png)

## Why?

Claude Code skills are markdown files that live in `~/.claude/skills/` (personal) or `<project>/.claude/skills/` (project-specific). As your skill collection grows across multiple repositories and projects, manually cloning repos, creating symlinks, and keeping track of which skills are active where becomes tedious and error-prone.

Skill Manager gives you a visual interface to manage all of this: add skill sources, register projects, and toggle skills on or off per target with a checkbox matrix. Conflicts between same-named skills from different sources are detected and resolved in one click.

## What are Claude Code Skills?

Skills are markdown files that extend Claude Code's capabilities with custom instructions, tools, and behaviors. They're loaded from:

- **Personal skills** (`~/.claude/skills/`) — available in every project
- **Project skills** (`<project>/.claude/skills/`) — scoped to a specific project

Skill Manager automates the symlink plumbing so you can focus on writing and using skills, not managing filesystem links.

## Installation

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Git

```bash
# Clone the repository
git clone <repo-url>
cd skillManager

# Run directly with uv
uv run skillmanager
```

The app launches a local web UI (typically at `http://localhost:8080`).

## Usage

### Core Concepts

- **Sources** — Git repositories or local directories containing skills. Remote repos are cloned to `~/.local/share/skillmanager/repos/`.
- **Projects** — Local directories where you want project-specific skills. Registering a project ensures its `.claude/skills/` directory exists.
- **Symlink Matrix** — A grid of skills (rows) vs. targets (columns: personal + each project). Check a box to create a symlink, uncheck to remove it.
- **Conflicts** — When multiple sources contain a skill with the same name, Skill Manager flags the conflict and lets you choose which source wins per target.

### What You Can Do

- **Add a skill source** — paste a Git URL or pick a local path; skills are auto-detected
- **Register a project** — point to a project directory to manage its skills
- **Toggle symlinks** — use the matrix view to enable/disable skills per target
- **Resolve conflicts** — choose which source wins when skill names collide
- **Update sources** — pull the latest changes from remote repos and re-map broken symlinks

## Configuration

All state is stored in a single TOML file following XDG conventions:

| Path                                  | Purpose                                 |
|---------------------------------------|---------------------------------------- |
| `~/.config/skillmanager/config.toml`  | Sources, projects, conflict resolutions |
| `~/.local/share/skillmanager/repos/`  | Cloned remote repositories              |

## Tech Stack

- **Python 3.11+** with type annotations
- **[NiceGUI](https://nicegui.io/)** — web-based UI framework (Vue.js under the hood)
- **TOML** — configuration persistence (`tomllib` + `tomli-w`)
- **Git** — source repository management via subprocess

## Running Tests

```bash
uv run pytest
```

Tests cover core operations (symlink management, git operations, skill detection) and configuration persistence.
