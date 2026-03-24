import asyncio
import uuid
from pathlib import Path
from typing import Any, Union

from nicegui import app, ui

from skillmanager.config import REPOS_DIR, load_config, save_config
from skillmanager.models import Project, Source, SourceKind
from skillmanager.models import Skill
from skillmanager.operations import (
    add_project,
    clone_repo,
    detect_skills,
    make_dest_path,
    validate_local_path,
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
                    ui.icon("work_outline").classes("text-sm text-gray-500")
                    ui.label(project.display_name).classes("text-sm")
                r.on("click", lambda _e, row=r, p=project: select_item(row, p))  # type: ignore[misc]
            return r

        def _render_project_detail(panel: ui.column, project: Project) -> None:
            panel.clear()
            with panel:
                ui.label(project.display_name).classes("text-xl font-bold mb-2")
                ui.label(f"Path: {project.path}").classes("text-gray-600")
                ui.label(f"Skills dir: {project.skills_dir}").classes("text-gray-600")

        def _render_source_detail(panel: ui.column, source: Source) -> None:
            panel.clear()
            with panel:
                ui.label(source.display_name).classes("text-xl font-bold mb-2")
                ui.label(f"Kind: {source.kind.value}").classes("text-gray-600")
                ui.label(f"Path: {source.path}").classes("text-gray-600 mb-4")

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
                            Skill(name=rel_path, rel_path=rel_path, enabled=True)
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

        with ui.splitter(value=20).classes("w-full h-screen") as splitter:
            with splitter.before:
                with ui.column().classes("w-full p-2 gap-0"):
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
