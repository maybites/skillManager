import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Union

from nicegui import app, ui

from skillmanager.config import REPOS_DIR, load_config, save_config
from skillmanager.models import ConflictResolution, Project, Source, SourceKind
from skillmanager.models import Skill
from skillmanager.operations import (
    add_project,
    clone_repo,
    copy_skill,
    create_symlink,
    detect_skills,
    extract_skill_description,
    find_owning_source,
    find_source_symlinks,
    git_pull,
    make_dest_path,
    remove_copy,
    remove_source_repo,
    remove_symlink,
    scan_broken_symlinks,
    validate_local_path,
    validate_project_paths,
)

ItemType = Union[Source, Project]


def run() -> None:
    app.title = "Skill Manager"

    @ui.page("/")
    def index() -> None:
        config = load_config()
        selected_row: dict[str, ui.row | None] = {"ref": None}
        detail_ref: dict[str, ui.column | None] = {"panel": None}
        sources_container_ref: dict[str, ui.column | None] = {"col": None}
        projects_container_ref: dict[str, ui.column | None] = {"col": None}
        missing_project_ids: dict[str, set[str]] = {
            "ids": validate_project_paths(config.projects)
        }

        def _last_segment(val: str) -> str:
            seg = val.rstrip("/").rsplit("/", 1)[-1]
            return seg.removesuffix(".git") if seg else ""

        def _make_source_row(source: Source) -> ui.row:
            with sources_container_ref["col"]:  # type: ignore[arg-type,union-attr]
                r = ui.row().classes(
                    "cursor-pointer w-full px-3 py-1 rounded items-center gap-2"
                )
                with r:
                    ui.icon("folder_open").classes("text-sm text-gray-500")
                    ui.label(source.display_name).classes("text-sm")
                r.on("click", lambda _e, row=r, s=source: select_item(row, s))  # type: ignore[misc]
            return r

        def _make_project_row(project: Project) -> ui.row:
            with projects_container_ref["col"]:  # type: ignore[arg-type,union-attr]
                r = ui.row().classes(
                    "cursor-pointer w-full px-3 py-1 rounded items-center gap-2"
                )
                with r:
                    if project.id in missing_project_ids["ids"]:
                        ui.icon("warning").classes("text-sm text-amber-500")
                    else:
                        ui.icon("work_outline").classes("text-sm text-gray-500")
                    ui.label(project.display_name).classes("text-sm")
                r.on("click", lambda _e, row=r, p=project: select_item(row, p))  # type: ignore[misc]
            return r

        def _refresh_sources_sidebar() -> None:
            col = sources_container_ref["col"]
            if col is None:
                return
            col.clear()
            selected_row["ref"] = None
            for source in config.sources:
                _make_source_row(source)

        def _refresh_projects_sidebar() -> None:
            col = projects_container_ref["col"]
            if col is None:
                return
            col.clear()
            selected_row["ref"] = None
            for project in config.projects:
                _make_project_row(project)

        def _symlink_count(project: Project) -> int:
            sd = project.skills_dir
            if not sd.exists():
                return 0
            return sum(1 for p in sd.iterdir() if p.is_symlink())

        def _confirm_remove_project(project: Project) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Remove Project").classes("text-xl font-bold mb-4")
                ui.label(
                    f"Remove '{project.display_name}' from Skill Manager?"
                ).classes("text-gray-600 mb-4")
                ui.label(
                    "This will not delete any files — only the registration is removed."
                ).classes("text-gray-500 text-sm mb-4")

                def on_confirm_remove() -> None:
                    config.projects[:] = [
                        p for p in config.projects if p.id != project.id
                    ]
                    save_config(config)
                    missing_project_ids["ids"].discard(project.id)
                    dialog.close()
                    _refresh_projects_sidebar()
                    panel = detail_ref["panel"]
                    if panel:
                        panel.clear()
                        with panel:
                            ui.label("Select an item to see details").classes(
                                "text-gray-400 text-lg"
                            )

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Remove", on_click=on_confirm_remove).props(
                        "color=negative"
                    )
            dialog.open()

        def _open_update_path_dialog(project: Project) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Update Project Path").classes("text-xl font-bold mb-4")
                path_input = ui.input("New Path", value=project.path).classes("w-full")
                status_label = ui.label("").classes(
                    "text-red-600 text-sm min-h-[1.25rem] w-full"
                )

                def on_save_path() -> None:
                    raw = path_input.value.strip()
                    if not raw:
                        status_label.set_text("Please enter a path.")
                        return
                    expanded = str(Path(raw).expanduser())
                    new_p = Path(expanded)
                    if not new_p.exists():
                        status_label.set_text("Path does not exist.")
                        return
                    if not new_p.is_dir():
                        status_label.set_text("Path is not a directory.")
                        return
                    project.path = expanded
                    save_config(config)
                    missing_project_ids["ids"].discard(project.id)
                    dialog.close()
                    _refresh_projects_sidebar()
                    panel = detail_ref["panel"]
                    if panel:
                        _render_project_detail(panel, project)

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=on_save_path).props("color=primary")
            dialog.open()

        def _render_project_detail(panel: ui.column, project: Project) -> None:
            panel.clear()
            with panel:
                if project.id in missing_project_ids["ids"]:
                    # Missing path UI
                    ui.label(project.display_name).classes("text-xl font-bold mb-2")
                    ui.label("Project path not found").classes(
                        "text-amber-700 bg-amber-50 border border-amber-300 "
                        "rounded px-3 py-2 w-full mb-3"
                    )
                    ui.label(f"Path: {project.path}").classes(
                        "text-red-600 font-mono text-sm mb-4"
                    )
                    def on_update_path_click(
                        _e: Any, _p: Project = project
                    ) -> None:
                        _open_update_path_dialog(_p)

                    def on_remove_missing_click(
                        _e: Any, _p: Project = project
                    ) -> None:
                        _confirm_remove_project(_p)

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button(
                            "Update Path",
                            icon="edit",
                        ).props("color=primary flat").on(
                            "click", on_update_path_click  # type: ignore[misc]
                        )
                        ui.button(
                            "Remove Project",
                            icon="delete",
                        ).props("color=negative flat").on(
                            "click", on_remove_missing_click  # type: ignore[misc]
                        )
                    return

                # Header row: title + Edit Name button
                name_row = ui.row().classes("items-center gap-2 mb-2 w-full")
                with name_row:
                    name_label = ui.label(project.display_name).classes(
                        "text-xl font-bold"
                    )
                    edit_btn = ui.button(icon="edit").props("flat round dense size=sm")

                edit_row = ui.row().classes("items-center gap-2 mb-2 w-full")
                edit_row.visible = False
                with edit_row:
                    name_edit = ui.input(value=project.display_name).classes(
                        "text-xl font-bold"
                    )

                    def on_save_name() -> None:
                        new_name = name_edit.value.strip()
                        if new_name:
                            project.display_name = new_name
                            save_config(config)
                            name_label.set_text(new_name)
                        edit_row.visible = False
                        name_row.visible = True

                    ui.button("Save", on_click=on_save_name).props(
                        "color=primary dense"
                    )
                    def on_cancel_name() -> None:
                        edit_row.visible = False
                        name_row.visible = True

                    ui.button("Cancel", on_click=on_cancel_name).props("flat dense")

                def on_edit_name() -> None:
                    name_edit.set_value(project.display_name)
                    name_row.visible = False
                    edit_row.visible = True

                edit_btn.on("click", lambda _e: on_edit_name())  # type: ignore[misc]

                ui.label(f"Path: {project.path}").classes("text-gray-600")
                ui.label(f"Skills dir: {project.skills_dir}").classes("text-gray-600")

                count = _symlink_count(project)
                ui.label(f"Active symlinks: {count}").classes("text-gray-600 mb-4")

                def on_remove_project_click(_e: Any, _p: Project = project) -> None:
                    _confirm_remove_project(_p)

                with ui.row().classes("gap-2 mt-2"):
                    ui.button(
                        "Remove Project",
                        icon="delete",
                    ).props("color=negative flat").on(
                        "click", on_remove_project_click  # type: ignore[misc]
                    )

        def _all_target_dirs() -> list[Path]:
            personal_dir = Path.home() / ".claude" / "skills"
            return [personal_dir] + [p.skills_dir for p in config.projects]

        def _open_remap_dialog(link_path: Path, parent_dialog: ui.dialog) -> None:
            confirmed_skills = [
                (src, sk)
                for src in config.sources
                if src.confirmed
                for sk in src.skills
            ]
            with ui.dialog() as remap_dialog, ui.card().classes("w-96"):
                ui.label(f"Re-map: {link_path.name}").classes(
                    "text-xl font-bold mb-4"
                )
                ui.label("Choose a skill to link to this target:").classes(
                    "text-gray-600 mb-3"
                )
                if not confirmed_skills:
                    ui.label("No confirmed skills available.").classes(
                        "text-gray-500 italic"
                    )
                    with ui.row().classes("justify-end mt-4"):
                        ui.button("Close", on_click=remap_dialog.close).props("flat")
                else:
                    skill_options = {
                        f"{src.display_name} / {sk.name}": (src, sk)
                        for src, sk in confirmed_skills
                    }
                    default_key = list(skill_options.keys())[0]
                    skill_select = ui.select(
                        list(skill_options.keys()), value=default_key
                    ).classes("w-full")

                    def on_remap() -> None:
                        key = skill_select.value
                        if not key or key not in skill_options:
                            return
                        src, sk = skill_options[key]
                        new_src = Path(src.path) / sk.rel_path
                        if os.path.lexists(str(link_path)):
                            os.unlink(str(link_path))
                        op = create_symlink(new_src, link_path)
                        if op.success:
                            ui.notify(f"Re-mapped to {sk.name}", type="positive")
                            remap_dialog.close()
                            parent_dialog.close()
                        else:
                            ui.notify(f"Re-map failed: {op.message}", type="negative")

                    with ui.row().classes("w-full justify-end mt-4 gap-2"):
                        ui.button("Cancel", on_click=remap_dialog.close).props("flat")
                        ui.button("Re-map", on_click=on_remap).props("color=primary")
            remap_dialog.open()

        def _show_broken_symlinks_dialog(broken: list[Path]) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
                ui.label("Broken Symlinks Detected").classes(
                    "text-xl font-bold mb-2 text-amber-700"
                )
                ui.label(
                    "These symlinks point to targets that no longer exist:"
                ).classes("text-gray-600 mb-4")

                rows: dict[str, ui.row] = {}
                for link_path in broken:
                    with ui.row().classes(
                        "items-center gap-2 w-full border-b border-gray-200 py-2"
                    ) as row:
                        rows[str(link_path)] = row
                        ui.icon("warning").classes("text-amber-500 shrink-0")
                        ui.label(str(link_path)).classes(
                            "text-sm font-mono flex-1 break-all"
                        )

                        def on_remove(
                            _p: Path = link_path, _r: ui.row = row
                        ) -> None:
                            op = remove_symlink(_p)
                            if op.success:
                                _r.visible = False
                                ui.notify(f"Removed: {_p.name}", type="positive")
                            else:
                                ui.notify(
                                    f"Failed to remove: {op.message}", type="negative"
                                )

                        ui.button("Remove", on_click=on_remove).props(
                            "flat dense color=negative size=sm"
                        )
                        def on_remap_click(
                            _e: Any,
                            _p: Path = link_path,
                            _d: ui.dialog = dialog,
                        ) -> None:
                            _open_remap_dialog(_p, _d)

                        ui.button("Re-map").props("flat dense size=sm").on(
                            "click", on_remap_click  # type: ignore[misc]
                        )

                with ui.row().classes("justify-end mt-4"):
                    ui.button("Close", on_click=dialog.close).props("flat")
            dialog.open()

        def _confirm_remove_source(source: Source) -> None:
            active_links = find_source_symlinks(source, _all_target_dirs())
            with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
                ui.label("Remove Skill Source").classes("text-xl font-bold mb-2")
                ui.label(
                    f"Remove '{source.display_name}' from Skill Manager?"
                ).classes("text-gray-600 mb-2")
                if source.kind == SourceKind.REMOTE:
                    ui.label(
                        "The cloned repository folder will also be deleted from disk."
                    ).classes("text-amber-700 text-sm mb-2")
                if active_links:
                    ui.label(
                        f"The following {len(active_links)} symlink(s) will be deleted:"
                    ).classes("font-semibold text-sm mb-1")
                    for lp in active_links:
                        ui.label(str(lp)).classes("text-sm font-mono text-gray-600 ml-2")
                else:
                    ui.label("No active symlinks to clean up.").classes(
                        "text-gray-500 text-sm italic mb-2"
                    )

                def on_confirm_remove_source() -> None:
                    # Remove all symlinks
                    for lp in active_links:
                        remove_symlink(lp)
                    # Delete remote repo from disk
                    if source.kind == SourceKind.REMOTE:
                        remove_source_repo(source.path)
                    # Remove from config
                    config.sources[:] = [
                        s for s in config.sources if s.id != source.id
                    ]
                    save_config(config)
                    dialog.close()
                    _refresh_sources_sidebar()
                    panel = detail_ref["panel"]
                    if panel:
                        panel.clear()
                        with panel:
                            ui.label("Select an item to see details").classes(
                                "text-gray-400 text-lg"
                            )

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Remove", on_click=on_confirm_remove_source).props(
                        "color=negative"
                    )
            dialog.open()

        def _render_source_detail(panel: ui.column, source: Source) -> None:
            panel.clear()
            with panel:
                ui.label(source.display_name).classes("text-xl font-bold mb-2")
                kind_label = "Remote" if source.kind == SourceKind.REMOTE else "Local"
                ui.label(f"Kind: {kind_label}").classes("text-gray-600")
                if source.kind == SourceKind.REMOTE and source.url:
                    ui.label(f"URL: {source.url}").classes("text-gray-600")
                ui.label(f"Path: {source.path}").classes("text-gray-600")
                updated_text = source.last_updated if source.last_updated else "Never"
                last_updated_label = ui.label(
                    f"Last updated: {updated_text}"
                ).classes("text-gray-600 mb-4")

                if not source.confirmed:
                    ui.label("Confirm skills to enable symlinking").classes(
                        "text-amber-700 bg-amber-50 border border-amber-300 "
                        "rounded px-3 py-2 w-full mb-4"
                    )

                    candidates = detect_skills(source.path)
                    if not candidates:
                        ui.label("No skill folders detected.").classes(
                            "text-gray-500 italic"
                        )
                        return

                    ui.label("Detected skill folders:").classes(
                        "font-semibold mb-2"
                    )
                    checkboxes: dict[str, ui.checkbox] = {}
                    for rel_path, enabled in candidates:
                        cb = ui.checkbox(rel_path, value=enabled)
                        checkboxes[rel_path] = cb

                    def on_confirm_skills() -> None:
                        source.skills = [
                            Skill(
                                name=rel_path,
                                rel_path=rel_path,
                                enabled=True,
                                description=extract_skill_description(
                                    Path(source.path) / rel_path
                                ),
                            )
                            for rel_path, cb in checkboxes.items()
                            if cb.value
                        ]
                        source.confirmed = True
                        save_config(config)
                        _render_source_detail(panel, source)

                    ui.button(
                        "Confirm Skills", on_click=on_confirm_skills
                    ).props("color=primary").classes("mt-4")
                else:
                    if source.skills:
                        ui.label("Confirmed skills:").classes("font-semibold mb-2")
                        for skill in source.skills:
                            ui.label(f"• {skill.name}").classes("text-sm text-gray-700")
                    else:
                        ui.label("No skills confirmed.").classes(
                            "text-gray-500 italic"
                        )

                output_area = ui.label("").classes(
                    "text-sm font-mono bg-gray-100 rounded p-2 w-full "
                    "whitespace-pre-wrap mt-2"
                )
                output_area.visible = False

                update_btn_ref: dict[str, ui.button | None] = {"btn": None}

                async def on_update(
                    _source: Source = source,
                    _output: ui.label = output_area,
                    _ts_label: ui.label = last_updated_label,
                ) -> None:
                    btn = update_btn_ref["btn"]
                    if btn:
                        btn.disable()
                    _output.set_text("Running git pull…")
                    _output.visible = True

                    op = await asyncio.to_thread(git_pull, Path(_source.path))
                    _output.set_text(op.message)

                    if op.success:
                        _source.last_updated = datetime.now(timezone.utc).isoformat()
                        save_config(config)
                        _ts_label.set_text(f"Last updated: {_source.last_updated}")

                        broken = scan_broken_symlinks(_all_target_dirs())
                        if broken:
                            _show_broken_symlinks_dialog(broken)
                        else:
                            ui.notify(
                                "Update complete — no broken symlinks.",
                                type="positive",
                            )
                    else:
                        ui.notify("git pull failed", type="negative")

                    if btn:
                        btn.enable()

                with ui.row().classes("gap-2 mt-4"):
                    if source.kind == SourceKind.REMOTE:
                        update_btn_ref["btn"] = ui.button(
                            "Update",
                            icon="refresh",
                            on_click=on_update,
                        ).props("color=primary flat")
                    else:
                        disabled_btn = ui.button(
                            "Update",
                            icon="refresh",
                        ).props("flat")
                        disabled_btn.disable()
                        disabled_btn.tooltip(
                            "Update is only available for remote sources"
                        )
                    def on_remove_source_click(
                        _e: Any, _s: Source = source
                    ) -> None:
                        _confirm_remove_source(_s)

                    ui.button(
                        "Remove",
                        icon="delete",
                    ).props("color=negative flat").on(
                        "click", on_remove_source_click  # type: ignore[misc]
                    )

        def _show_conflict_dialog(
            skill: Skill,
            new_source: Source,
            existing_source: Source,
            dst: Path,
            new_src: Path,
            on_confirm: Callable[[], None],
            on_cancel: Callable[[], None] = lambda: None,
        ) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
                ui.label("Skill Conflict").classes(
                    "text-xl font-bold mb-2 text-amber-700"
                )
                ui.label(
                    f"The skill '{skill.name}' already has a symlink from "
                    f"'{existing_source.display_name}'. Choose which source wins "
                    f"for this target."
                ).classes("text-gray-600 mb-4")

                def on_choose_new() -> None:
                    op_rm = remove_symlink(dst)
                    if not op_rm.success:
                        ui.notify(
                            f"Failed to remove existing symlink: {op_rm.message}",
                            type="negative",
                        )
                        dialog.close()
                        return
                    op_cr = create_symlink(new_src, dst)
                    if op_cr.success:
                        config.conflict_resolutions = [
                            r
                            for r in config.conflict_resolutions
                            if not (
                                r.skill_name == skill.name
                                and r.target_id == str(dst.parent)
                            )
                        ]
                        config.conflict_resolutions.append(
                            ConflictResolution(
                                skill_name=skill.name,
                                target_id=str(dst.parent),
                                winner_source_id=new_source.id,
                            )
                        )
                        save_config(config)
                        ui.notify(
                            f"Resolved: '{new_source.display_name}' wins",
                            type="positive",
                        )
                        on_confirm()
                    else:
                        ui.notify(f"Failed: {op_cr.message}", type="negative")
                    dialog.close()

                def on_keep_existing() -> None:
                    on_cancel()
                    dialog.close()

                with ui.row().classes("w-full gap-2 mt-4"):
                    ui.button(
                        f"Use '{new_source.display_name}'",
                        on_click=on_choose_new,
                    ).props("color=primary")
                    ui.button(
                        f"Keep '{existing_source.display_name}'",
                        on_click=on_keep_existing,
                    ).props("flat")
            dialog.open()

        def _render_matrix_view(panel: ui.column) -> None:
            panel.clear()

            # Backfill descriptions for skills that lack them
            for src in config.sources:
                if not src.confirmed:
                    continue
                for sk in src.skills:
                    if not sk.description:
                        sk.description = extract_skill_description(
                            Path(src.path) / sk.rel_path
                        )

            with panel:
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.label("Skill Matrix").classes("text-2xl font-bold")
                    ui.button(
                        icon="refresh",
                        on_click=lambda: _render_matrix_view(panel),
                    ).props("flat dense round").tooltip("Refresh matrix")

                confirmed = [s for s in config.sources if s.confirmed and s.skills]
                if not confirmed:
                    ui.label(
                        "No confirmed skills yet. Add and confirm skill sources first."
                    ).classes("text-gray-400 italic text-lg")
                    return

                # Personal skills dir — auto-create if missing
                personal_dir = Path.home() / ".claude" / "skills"
                personal_dir.mkdir(parents=True, exist_ok=True)

                # Columns: (label, target_skills_dir, is_missing)
                targets: list[tuple[str, Path, bool]] = [
                    ("Personal\n(~/.claude/skills/)", personal_dir, False)
                ]
                for project in config.projects:
                    is_proj_missing = project.id in missing_project_ids["ids"]
                    targets.append(
                        (project.display_name, project.skills_dir, is_proj_missing)
                    )

                # Detect conflicting skill names (same name across different sources)
                skill_name_counts: dict[str, int] = {}
                for _src in confirmed:
                    for _sk in _src.skills:
                        skill_name_counts[_sk.name] = (
                            skill_name_counts.get(_sk.name, 0) + 1
                        )
                conflicting_names: set[str] = {
                    n for n, c in skill_name_counts.items() if c > 1
                }

                # Header row
                with ui.row().classes(
                    "items-center border-b-2 border-gray-300 pb-2 mb-2"
                ):
                    ui.label("Skill").classes("font-semibold text-sm").style(
                        "min-width: 200px"
                    )
                    for target_name, _, is_missing in targets:
                        col_classes = "font-semibold text-sm text-center"
                        if is_missing:
                            col_classes += " text-gray-400"
                        lbl = ui.label(target_name).classes(col_classes).style(
                            "min-width: 140px; white-space: pre-line"
                        )
                        if is_missing:
                            lbl.tooltip("Project path not found")

                # Rows grouped by source (collapsible)
                for source in confirmed:
                    linked_count = 0
                    for skill in source.skills:
                        for _, target_dir, is_missing in targets:
                            if not is_missing and os.path.exists(
                                str(target_dir / skill.name)
                            ):
                                linked_count += 1
                                break
                    total_count = len(source.skills)

                    with ui.row().classes(
                        "items-center bg-gray-100 px-2 py-1 rounded mt-3 "
                        "w-full cursor-pointer select-none gap-1"
                    ) as header_row:
                        chevron = ui.icon("chevron_right").classes(
                            "text-gray-500 text-sm"
                        ).style("transition: transform 0.2s ease-in-out")
                        ui.label(
                            f"{source.display_name} "
                            f"({linked_count}/{total_count} linked)"
                        ).classes("font-bold text-sm text-gray-700")

                    skills_container = ui.column().classes("w-full gap-0").style(
                        "overflow: hidden; max-height: 0; "
                        "transition: max-height 0.2s ease-in-out"
                    )

                    def _make_toggle(
                        _header: ui.row,
                        _chevron: ui.icon,
                        _container: ui.column,
                        _num_skills: int,
                    ) -> None:
                        _header._expanded = False  # type: ignore[attr-defined]

                        def _on_click() -> None:
                            _header._expanded = not _header._expanded  # type: ignore[attr-defined]
                            if _header._expanded:  # type: ignore[attr-defined]
                                expanded_height = _num_skills * 100 + 40
                                _container.style(
                                    replace=(
                                        "overflow: hidden; "
                                        f"max-height: {expanded_height}px; "
                                        "transition: max-height 0.2s ease-in-out"
                                    )
                                )
                                _chevron.style(
                                    replace=(
                                        "transform: rotate(90deg); "
                                        "transition: transform 0.2s ease-in-out"
                                    )
                                )
                            else:
                                _container.style(
                                    replace=(
                                        "overflow: hidden; "
                                        "max-height: 0; "
                                        "transition: max-height 0.2s ease-in-out"
                                    )
                                )
                                _chevron.style(
                                    replace=(
                                        "transform: rotate(0deg); "
                                        "transition: transform 0.2s ease-in-out"
                                    )
                                )

                        _header.on("click", _on_click)

                    _make_toggle(header_row, chevron, skills_container, total_count)

                    with skills_container:
                        for skill in source.skills:
                            with ui.column().classes("gap-0 w-full"):
                                # Main row: skill name + checkboxes (aligned)
                                with ui.row().classes(
                                    "items-center hover:bg-gray-50 rounded"
                                ):
                                    with ui.row().classes(
                                        "items-center gap-0"
                                        + (" cursor-pointer" if skill.description else "")
                                    ).style(
                                        "min-width: 200px"
                                    ) as skill_header:
                                        if skill.description:
                                            sk_chevron = ui.icon("chevron_right").classes(
                                                "text-gray-400 text-xs"
                                            ).style(
                                                "transition: transform 0.2s ease-in-out; "
                                                "font-size: 14px"
                                            )
                                        ui.label(skill.name).classes(
                                            "text-sm text-gray-600"
                                        )
                                        if skill.name in conflicting_names:
                                            ui.icon("warning").classes(
                                                "text-amber-500 text-sm"
                                            ).tooltip(
                                                "Conflict: another source has a "
                                                "skill with the same name"
                                            )
                                    for _, target_dir, is_missing in targets:
                                        symlink_path = target_dir / skill.name
                                        src_path = Path(source.path) / skill.rel_path
                                        is_symlink = os.path.islink(str(symlink_path))
                                        is_copied = (
                                            os.path.exists(str(symlink_path))
                                            and not is_symlink
                                        )
                                        with ui.element("div").style(
                                            "min-width: 140px; display: flex; "
                                            "justify-content: center; "
                                            "align-items: center; gap: 8px"
                                        ):
                                            # Link icon
                                            link_cls = (
                                                "text-xl cursor-pointer "
                                                + ("text-blue-500" if is_symlink else "text-gray-300")
                                            )
                                            link_icon = ui.icon("link").classes(link_cls)
                                            if is_missing:
                                                link_icon.style(
                                                    "pointer-events: none; opacity: 0.4"
                                                )
                                                link_icon.tooltip("Project path not found")
                                            elif is_copied:
                                                link_icon.style(
                                                    "pointer-events: none; opacity: 0.3"
                                                )

                                            # Copy icon
                                            copy_cls = (
                                                "text-xl cursor-pointer "
                                                + ("text-green-500" if is_copied else "text-gray-300")
                                            )
                                            copy_icon = ui.icon("content_copy").classes(copy_cls)
                                            if is_missing:
                                                copy_icon.style(
                                                    "pointer-events: none; opacity: 0.4"
                                                )
                                                copy_icon.tooltip("Project path not found")
                                            elif is_symlink:
                                                copy_icon.style(
                                                    "pointer-events: none; opacity: 0.3"
                                                )

                                            if not is_missing:
                                                cell_state = {
                                                    "is_symlink": is_symlink,
                                                    "is_copied": is_copied,
                                                }

                                                def _on_link_click(
                                                    _link: ui.icon = link_icon,
                                                    _copy: ui.icon = copy_icon,
                                                    _src: Path = src_path,
                                                    _dst: Path = symlink_path,
                                                    _source: Source = source,
                                                    _skill: Skill = skill,
                                                    _st: dict[str, bool] = cell_state,
                                                ) -> None:
                                                    if _st["is_symlink"]:
                                                        op = remove_symlink(_dst)
                                                        if not op.success:
                                                            ui.notify(op.message, type="negative")
                                                            return
                                                        _st["is_symlink"] = False
                                                        _link.classes(
                                                            remove="text-blue-500",
                                                            add="text-gray-300",
                                                        )
                                                        _copy.style(replace="")
                                                    else:
                                                        existing = find_owning_source(
                                                            _dst, config.sources
                                                        )
                                                        if existing and existing.id != _source.id:  # type: ignore[union-attr]
                                                            def _on_confirm(
                                                                __link: ui.icon = _link,
                                                                __copy: ui.icon = _copy,
                                                                __st: dict[str, bool] = _st,
                                                            ) -> None:
                                                                __st["is_symlink"] = True
                                                                __link.classes(
                                                                    remove="text-gray-300",
                                                                    add="text-blue-500",
                                                                )
                                                                __copy.style(
                                                                    replace="pointer-events: none; opacity: 0.3"
                                                                )
                                                            _show_conflict_dialog(
                                                                _skill,
                                                                _source,
                                                                existing,  # type: ignore[arg-type]
                                                                _dst,
                                                                _src,
                                                                _on_confirm,
                                                            )
                                                            return
                                                        op = create_symlink(_src, _dst)
                                                        if not op.success:
                                                            ui.notify(op.message, type="negative")
                                                            return
                                                        _st["is_symlink"] = True
                                                        _link.classes(
                                                            remove="text-gray-300",
                                                            add="text-blue-500",
                                                        )
                                                        _copy.style(
                                                            replace="pointer-events: none; opacity: 0.3"
                                                        )

                                                link_icon.on("click", _on_link_click)  # type: ignore[misc]

                                                def _on_copy_click(
                                                    _link: ui.icon = link_icon,
                                                    _copy: ui.icon = copy_icon,
                                                    _src: Path = src_path,
                                                    _dst: Path = symlink_path,
                                                    _st: dict[str, bool] = cell_state,
                                                ) -> None:
                                                    if _st["is_copied"]:
                                                        op = remove_copy(_dst)
                                                        if not op.success:
                                                            ui.notify(op.message, type="negative")
                                                            return
                                                        _st["is_copied"] = False
                                                        _copy.classes(
                                                            remove="text-green-500",
                                                            add="text-gray-300",
                                                        )
                                                        _link.style(replace="")
                                                    else:
                                                        op = copy_skill(_src, _dst)
                                                        if not op.success:
                                                            ui.notify(op.message, type="negative")
                                                            return
                                                        _st["is_copied"] = True
                                                        _copy.classes(
                                                            remove="text-gray-300",
                                                            add="text-green-500",
                                                        )
                                                        _link.style(
                                                            replace="pointer-events: none; opacity: 0.3"
                                                        )

                                                copy_icon.on("click", _on_copy_click)  # type: ignore[misc]

                                # Collapsible description below the row
                                if skill.description:
                                    desc_container = ui.element("div").style(
                                        "overflow: hidden; max-height: 0; "
                                        "transition: max-height 0.2s ease-in-out"
                                    )
                                    with desc_container:
                                        ui.label(skill.description).classes(
                                            "text-xs text-gray-400 pl-6"
                                        )

                                    def _make_skill_toggle(
                                        _hdr: ui.row,
                                        _chev: ui.icon,
                                        _cont: ui.element,
                                    ) -> None:
                                        _hdr._sk_expanded = False  # type: ignore[attr-defined]

                                        def _on_click() -> None:
                                            _hdr._sk_expanded = not _hdr._sk_expanded  # type: ignore[attr-defined]
                                            if _hdr._sk_expanded:  # type: ignore[attr-defined]
                                                _cont.style(replace=(
                                                    "overflow: hidden; "
                                                    "max-height: 200px; "
                                                    "transition: max-height 0.2s ease-in-out"
                                                ))
                                                _chev.style(replace=(
                                                    "transform: rotate(90deg); "
                                                    "transition: transform 0.2s ease-in-out; "
                                                    "font-size: 14px"
                                                ))
                                            else:
                                                _cont.style(replace=(
                                                    "overflow: hidden; "
                                                    "max-height: 0; "
                                                    "transition: max-height 0.2s ease-in-out"
                                                ))
                                                _chev.style(replace=(
                                                    "transform: rotate(0deg); "
                                                    "transition: transform 0.2s ease-in-out; "
                                                    "font-size: 14px"
                                                ))

                                        _hdr.on("click", _on_click)

                                    _make_skill_toggle(
                                        skill_header, sk_chevron, desc_container  # type: ignore[possibly-undefined]
                                    )

        def open_matrix_view() -> None:
            prev = selected_row["ref"]
            if prev is not None:
                prev.classes(remove="bg-blue-100 font-semibold")
                selected_row["ref"] = None
            panel = detail_ref["panel"]
            if panel is None:
                return
            _render_matrix_view(panel)

        def select_item(row: ui.row, item: ItemType) -> None:
            prev = selected_row["ref"]
            if prev is not None:
                prev.classes(remove="bg-blue-100 font-semibold")
            row.classes(add="bg-blue-100 font-semibold")
            selected_row["ref"] = row

            panel = detail_ref["panel"]
            if panel is None:
                return
            if isinstance(item, Source):
                _render_source_detail(panel, item)
            else:
                _render_project_detail(panel, item)

        def open_add_project_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Add Project").classes("text-xl font-bold mb-4")

                path_input = ui.input(
                    "Project Path",
                    placeholder="/path/to/my-project",
                ).classes("w-full")

                name_input = ui.input(
                    "Display Name",
                    placeholder="Optional — defaults to folder name",
                ).classes("w-full")

                status_label = ui.label("").classes(
                    "text-red-600 text-sm min-h-[1.25rem] w-full"
                )

                def on_path_change(e: Any) -> None:
                    seg = _last_segment(e.value or "")
                    if seg and not name_input.value:
                        name_input.set_value(seg)

                path_input.on_value_change(on_path_change)  # type: ignore[misc]

                def on_add_project() -> None:
                    raw_path = path_input.value.strip()
                    display = name_input.value.strip()
                    status_label.set_text("")

                    if not raw_path:
                        status_label.set_text("Please enter a project path.")
                        return

                    expanded = str(Path(raw_path).expanduser())
                    if any(p.path == expanded for p in config.projects):
                        status_label.set_text("This path is already registered.")
                        return

                    op = add_project(raw_path)
                    if not op.success:
                        status_label.set_text(op.message)
                        return

                    display = display or _last_segment(raw_path)
                    project = Project(
                        id=uuid.uuid4().hex,
                        display_name=display,
                        path=expanded,
                    )
                    config.projects.append(project)
                    save_config(config)
                    dialog.close()
                    new_row = _make_project_row(project)
                    select_item(new_row, project)

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Add", on_click=on_add_project).props("color=primary")

            dialog.open()

        def open_add_source_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Add Skill Source").classes("text-xl font-bold mb-4")

                mode_toggle = ui.toggle(
                    {"remote": "Remote URL", "local": "Local Path"}, value="remote"
                ).classes("mb-3")

                url_col = ui.column().classes("w-full gap-2")
                with url_col:
                    url_input = ui.input(
                        "Git URL",
                        placeholder="https://github.com/user/repo.git",
                    ).classes("w-full")

                path_col = ui.column().classes("w-full gap-2")
                with path_col:
                    path_input = ui.input(
                        "Directory Path",
                        placeholder="/path/to/skills",
                    ).classes("w-full")
                path_col.visible = False

                name_input = ui.input(
                    "Display Name",
                    placeholder="Optional — defaults to repo/folder name",
                ).classes("w-full")

                status_label = ui.label("").classes(
                    "text-red-600 text-sm min-h-[1.25rem] w-full"
                )

                def on_mode_change(e: Any) -> None:
                    is_remote = e.value == "remote"
                    url_col.visible = is_remote
                    path_col.visible = not is_remote
                    status_label.set_text("")

                def on_url_change(e: Any) -> None:
                    seg = _last_segment(e.value or "")
                    if seg and not name_input.value:
                        name_input.set_value(seg)

                def on_path_change(e: Any) -> None:
                    seg = _last_segment(e.value or "")
                    if seg and not name_input.value:
                        name_input.set_value(seg)

                mode_toggle.on_value_change(on_mode_change)  # type: ignore[misc]
                url_input.on_value_change(on_url_change)  # type: ignore[misc]
                path_input.on_value_change(on_path_change)  # type: ignore[misc]

                async def on_add() -> None:
                    mode = mode_toggle.value
                    raw_url = url_input.value.strip()
                    raw_path = path_input.value.strip()
                    display = name_input.value.strip()
                    status_label.set_text("")

                    if mode == "remote":
                        if not raw_url:
                            status_label.set_text("Please enter a Git URL.")
                            return
                        if any(s.url == raw_url for s in config.sources):
                            status_label.set_text("This URL is already registered.")
                            return
                        display = display or _last_segment(raw_url)
                        dest = make_dest_path(raw_url, REPOS_DIR)
                        status_label.set_text("Cloning… this may take a moment.")
                        status_label.classes(remove="text-red-600")
                        status_label.classes(add="text-blue-600")
                        add_btn.disable()
                        op = await asyncio.to_thread(clone_repo, raw_url, dest)
                        if not op.success:
                            status_label.classes(remove="text-blue-600")
                            status_label.classes(add="text-red-600")
                            status_label.set_text(op.message)
                            add_btn.enable()
                            return
                        source: Source = Source(
                            id=uuid.uuid4().hex,
                            display_name=display,
                            kind=SourceKind.REMOTE,
                            path=str(dest),
                            url=raw_url,
                        )
                    else:
                        if not raw_path:
                            status_label.set_text("Please enter a directory path.")
                            return
                        expanded = str(Path(raw_path).expanduser())
                        if any(s.path == expanded for s in config.sources):
                            status_label.set_text("This path is already registered.")
                            return
                        op = validate_local_path(raw_path)
                        if not op.success:
                            status_label.set_text(op.message)
                            return
                        display = display or _last_segment(raw_path)
                        source = Source(
                            id=uuid.uuid4().hex,
                            display_name=display,
                            kind=SourceKind.LOCAL,
                            path=expanded,
                        )

                    config.sources.append(source)
                    save_config(config)
                    dialog.close()
                    new_row = _make_source_row(source)
                    select_item(new_row, source)

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    add_btn = ui.button("Add", on_click=on_add).props("color=primary")

            dialog.open()

        async def on_update_all() -> None:
            remote_sources = [
                s for s in config.sources if s.kind == SourceKind.REMOTE
            ]
            if not remote_sources:
                ui.notify("No remote sources to update.", type="info")
                return
            ui.notify(
                f"Updating {len(remote_sources)} remote source(s)…", type="info"
            )
            failed: list[str] = []
            for src in remote_sources:
                op = await asyncio.to_thread(git_pull, Path(src.path))
                if op.success:
                    src.last_updated = datetime.now(timezone.utc).isoformat()
                else:
                    failed.append(f"{src.display_name}: {op.message}")
            save_config(config)
            if failed:
                ui.notify(
                    "Some updates failed:\n" + "\n".join(failed), type="negative"
                )
            broken = scan_broken_symlinks(_all_target_dirs())
            if broken:
                _show_broken_symlinks_dialog(broken)
            else:
                ui.notify("All remote sources updated successfully.", type="positive")

        with ui.splitter(value=20).classes("w-full h-screen") as splitter:
            with splitter.before:
                with ui.column().classes("w-full p-2 gap-0"):
                    ui.button(
                        "Symlinks",
                        icon="link",
                        on_click=lambda: open_matrix_view(),
                    ).props("flat dense").classes("w-full mb-1 justify-start")
                    ui.button(
                        "Update All",
                        icon="cloud_download",
                        on_click=on_update_all,
                    ).props("flat dense").classes("w-full mb-1 justify-start")
                    ui.separator()
                    with ui.expansion("Skill Sources", icon="folder").classes("w-full"):
                        sources_container = ui.column().classes("w-full gap-0")
                        sources_container_ref["col"] = sources_container
                        for source in config.sources:
                            _make_source_row(source)
                        ui.button(
                            "+ Add",
                            on_click=open_add_source_dialog,
                        ).props("flat dense color=primary").classes("w-full mt-1")

                    with ui.expansion("Projects", icon="work").classes("w-full"):
                        projects_container = ui.column().classes("w-full gap-0")
                        projects_container_ref["col"] = projects_container
                        for project in config.projects:
                            _make_project_row(project)
                        ui.button(
                            "+ Add",
                            on_click=open_add_project_dialog,
                        ).props("flat dense color=primary").classes("w-full mt-1")

            with splitter.after:
                detail_col = ui.column().classes("w-full p-6")
                detail_ref["panel"] = detail_col
                with detail_col:
                    ui.label("Select an item to see details").classes(
                        "text-gray-400 text-lg"
                    )

    ui.run(host="127.0.0.1", title="Skill Manager", reload=False)
