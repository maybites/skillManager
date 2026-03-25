# PRD: Copy Skills to Project Vaults

## Introduction

The Skill Manager currently manages skills exclusively through symlinks — skills in project vaults (`.claude/skills/`) are symbolic links back to source repositories. While symlinks auto-propagate updates and save disk space, they require the source repo to remain on disk and accessible. This breaks portability: projects handed off to colleagues, moved to other machines, or used in CI environments lose their skills.

This feature adds the ability to create **complete copies** of skill folders into project vaults alongside the existing symlink mechanism. The user chooses per-cell in the matrix whether a skill should be symlinked or copied, giving fine-grained control over portability vs. auto-update tradeoffs.

---

## Goals

- Users can create portable, self-contained copies of skills into any project vault
- The matrix view clearly distinguishes copies from symlinks at a glance
- After a `git pull`, drifted copies (source has changed since copy was made) are visually flagged
- The interaction model is explicit: no hidden defaults, no accidental mode switches
- Copies are independent snapshots — no sync-back, no auto-update, no version tracking

---

## User Stories

### US-015: Copy a skill into a project vault
**Description:** As a user, I want to copy a skill folder into a project's `.claude/skills/` directory so that the project is self-contained and portable without requiring the source repo on disk.

**Acceptance Criteria:**
- [ ] Each matrix cell shows two small icons side-by-side: a link icon (🔗) and a copy icon (📋)
- [ ] Clicking the copy icon on an empty cell performs a recursive copy (`shutil.copytree`) of the skill folder into the target skills directory
- [ ] After copying, the copy icon is highlighted/colored and the link icon is disabled (grayed out)
- [ ] The copied skill folder contains all files from the source skill folder
- [ ] Verify in browser that the split-icon cell renders correctly

### US-016: Remove a copied skill
**Description:** As a user, I want to remove a previously copied skill from a project vault so I can clean up skills I no longer need.

**Acceptance Criteria:**
- [ ] Clicking the highlighted copy icon on an active-copy cell removes the copied folder (`shutil.rmtree`)
- [ ] After removal, the cell returns to empty state with both icons enabled
- [ ] A notification is shown if the removal fails (e.g., permission error)
- [ ] Verify in browser that the cell state resets correctly

### US-017: Visual distinction between symlinks and copies in the matrix
**Description:** As a user, I want to see at a glance which skills are symlinked and which are copied so I can understand the portability status of each project.

**Acceptance Criteria:**
- [ ] Symlinked cells show a highlighted link icon (🔗) in blue/primary color
- [ ] Copied cells show a highlighted copy icon (📋) in green or distinct color
- [ ] Empty cells show both icons in a dimmed/neutral state, both clickable
- [ ] When one icon is active, the other icon is visually disabled (grayed out, not clickable)
- [ ] The existing symlink creation via the link icon works identically to the current checkbox behavior
- [ ] Verify in browser that all three states (empty, symlinked, copied) are visually distinct

### US-018: Detect drifted copies after source update
**Description:** As a user, I want to be notified when a copied skill's source has been updated so I know the copy is outdated and can choose to re-copy.

**Acceptance Criteria:**
- [ ] After `git pull` (Update or Update All), the app computes SHA-256 hashes for all files in each copied skill and its corresponding source skill
- [ ] If hashes differ (files added, removed, or content changed), the copy icon shows an amber badge/dot overlay
- [ ] Hovering the amber badge shows a tooltip: "Source has been updated since this copy was made"
- [ ] The drift indicator persists until the user removes and re-copies the skill
- [ ] Copies from sources that were not updated are not re-checked (optimization)
- [ ] Verify in browser that the amber drift badge is visible and tooltip works

### US-019: Convert between symlink and copy modes
**Description:** As a user, I want to switch a skill from symlinked to copied (or vice versa) by removing it first and then re-adding it in the other mode.

**Acceptance Criteria:**
- [ ] When a cell has an active symlink, clicking the active link icon removes the symlink (cell becomes empty)
- [ ] When a cell has an active copy, clicking the active copy icon removes the copy (cell becomes empty)
- [ ] After removal, both icons become enabled and the user can pick either mode
- [ ] There is no direct in-place conversion — the user must remove first, then re-add
- [ ] Conflict detection still works when creating a symlink via the link icon (existing behavior preserved)

### US-020: Source removal leaves copies untouched
**Description:** As a user, I want copies to survive when I remove a skill source, since copies are independent snapshots not tied to the source.

**Acceptance Criteria:**
- [ ] When removing a source, only symlinks pointing into that source are found and removed
- [ ] Copied skill folders are not affected by source removal (they are regular directories, not symlinks)
- [ ] The source removal confirmation dialog continues to list only symlinks that will be removed
- [ ] After source removal, copied skills remain functional in their project vaults

### US-021: Copy skill operations module
**Description:** As a developer, I need backend operations for copying skills, detecting copies, computing drift, and removing copies.

**Acceptance Criteria:**
- [ ] `copy_skill(src: Path, dst: Path) -> OperationResult` — performs `shutil.copytree(src, dst)` with parent directory creation
- [ ] `remove_copy(dst: Path) -> OperationResult` — performs `shutil.rmtree(dst)` with error handling
- [ ] `is_copy(path: Path) -> bool` — returns `True` if path exists and is not a symlink (regular directory)
- [ ] `compute_drift(source_skill: Path, copied_skill: Path) -> bool` — returns `True` if file content hashes differ between source and copy
- [ ] All functions have corresponding unit tests
- [ ] Typecheck passes

---

## Functional Requirements

- FR-1: Each matrix cell must display two small icons (link and copy) instead of a single checkbox
- FR-2: Clicking the link icon on an empty cell creates a symlink (preserving existing behavior)
- FR-3: Clicking the copy icon on an empty cell creates a recursive copy via `shutil.copytree`
- FR-4: When one mode is active, the other icon must be disabled (grayed out, non-interactive)
- FR-5: Clicking an active icon removes the symlink or copy and returns the cell to empty state
- FR-6: Cell state is derived from the filesystem: `os.path.islink()` = symlink, `os.path.exists() and not os.path.islink()` = copy
- FR-7: After `git pull`, compute SHA-256 file content hashes to detect drift between source and copied skills
- FR-8: Drifted copies display an amber badge overlay on the copy icon with an explanatory tooltip
- FR-9: Drift detection only runs for sources that were just updated (not on every render)
- FR-10: Source removal only cleans up symlinks; copies are left untouched
- FR-11: Conflict detection (existing behavior) applies only to symlink creation, not copies
- FR-12: The matrix header title should update from "Symlink Matrix" to "Skill Matrix" to reflect both modes

---

## Non-Goals (Out of Scope)

- **No sync-back** — Edits to copied skills are never pushed back to the source
- **No versioning** — No tracking of "this copy is from commit X"
- **No partial copy** — No picking individual files within a skill folder
- **No diff view** — No comparing copy vs source content side-by-side
- **No auto-update of copies** — Copies are frozen snapshots; only drift notification is provided
- **No bulk operations** — No "copy all" or "symlink all" buttons; cell-by-cell only
- **No config changes for state tracking** — Copy vs symlink state is derived from filesystem, not stored in config

---

## Design Considerations

### Matrix Cell Layout

```
┌─────────────────────────────────────────────────┐
│  Empty cell:     [🔗] [📋]    both enabled      │
│  Symlinked:      [🔗] [📋]    link highlighted,  │
│                                copy disabled     │
│  Copied:         [🔗] [📋]    copy highlighted,  │
│                                link disabled     │
│  Copied+drifted: [🔗] [📋●]   copy highlighted   │
│                                with amber badge  │
└─────────────────────────────────────────────────┘
```

### Icon Implementation
- Use NiceGUI `ui.icon()` with Material Icons: `link` for symlink, `content_copy` for copy
- Active state: primary color (blue for link, green for copy) with full opacity
- Disabled state: gray color, reduced opacity, `pointer-events: none`
- Drift badge: small amber dot positioned as an overlay via CSS

### Interaction Flow
1. User clicks 🔗 on empty cell → symlink created, 📋 becomes disabled
2. User clicks 📋 on empty cell → `shutil.copytree` runs, 🔗 becomes disabled
3. User clicks active icon → removes symlink/copy, cell returns to empty
4. To convert mode: remove (step 3) → pick other mode (step 1 or 2)

### Drift Detection Flow
1. User clicks "Update" or "Update All" → `git pull` runs
2. Post-pull: for each copied skill from the updated source, hash all files in source and copy
3. If any hash differs or file lists don't match → mark as drifted
4. Drifted cells show amber badge until user removes and re-copies

---

## Technical Considerations

- **Filesystem as source of truth:** No model or config changes. `os.path.islink()` distinguishes symlinks from copies. This avoids config/filesystem desync.
- **Hash computation:** Use `hashlib.sha256` on file contents. Walk both directory trees, compare sorted file lists and their hashes. Skill folders are small (handful of markdown files), so performance is negligible.
- **Drift state lifetime:** Drift indicators are computed post-pull and held in memory for the current session. Re-navigating to the matrix re-derives state from filesystem (no drift shown until next pull).
- **Existing conflict resolution:** Only applies to symlink creation. Copies don't trigger conflict dialogs since they don't create symlinks that can be traced back to a source via `find_owning_source()`.
- **Cell width:** The split-icon cell needs slightly more horizontal space than the current checkbox. May need to adjust `min-width` from `120px` to `140px`.

---

## Success Metrics

- Users can copy a skill into a project vault in a single click
- Copy vs symlink state is immediately visible without hovering or clicking
- Drifted copies are flagged after `git pull` without user action
- Existing symlink workflows continue to work identically

---

## Open Questions

- Should the "linked count" in source group headers (e.g., "3/5 linked") also count copies, or show separate counts like "2 linked, 1 copied"?
- Should drift state persist across app restarts (e.g., store last-checked hashes), or is session-only sufficient?
