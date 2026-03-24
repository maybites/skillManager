from typing import Any, Union

from nicegui import app, ui

from skillmanager.config import load_config
from skillmanager.models import Project, Source

ItemType = Union[Source, Project]


def run() -> None:
    app.title = "Skill Manager"

    @ui.page("/")
    def index() -> None:
        config = load_config()
        selected_row: dict[str, ui.row | None] = {"ref": None}
        detail_ref: dict[str, ui.column | None] = {"panel": None}

        def _last_segment(val: str) -> str:
            seg = val.rstrip("/").rsplit("/", 1)[-1]
            return seg.removesuffix(".git") if seg else ""

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

                def on_mode_change(e: Any) -> None:
                    is_remote = e.value == "remote"
                    url_col.visible = is_remote
                    path_col.visible = not is_remote

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

                with ui.row().classes("w-full justify-end mt-4 gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button(
                        "Add",
                        on_click=lambda: ui.notify(
                            "Clone / path validation coming in US-005"
                        ),
                    ).props("color=primary")

            dialog.open()

        def select_item(row: ui.row, item: ItemType) -> None:
            prev = selected_row["ref"]
            if prev is not None:
                prev.classes(remove="bg-blue-100 font-semibold")
            row.classes(add="bg-blue-100 font-semibold")
            selected_row["ref"] = row

            panel = detail_ref["panel"]
            if panel is None:
                return
            panel.clear()
            with panel:
                if isinstance(item, Source):
                    ui.label(item.display_name).classes("text-xl font-bold mb-2")
                    ui.label(f"Kind: {item.kind.value}").classes("text-gray-600")
                    ui.label(f"Path: {item.path}").classes("text-gray-600")
                else:
                    ui.label(item.display_name).classes("text-xl font-bold mb-2")
                    ui.label(f"Path: {item.path}").classes("text-gray-600")

        with ui.splitter(value=20).classes("w-full h-screen") as splitter:
            with splitter.before:
                with ui.column().classes("w-full p-2 gap-0"):
                    with ui.expansion("Skill Sources", icon="folder").classes("w-full"):
                        for source in config.sources:
                            r = ui.row().classes(
                                "cursor-pointer w-full px-3 py-1 rounded items-center gap-2"
                            )
                            with r:
                                ui.icon("folder_open").classes("text-sm text-gray-500")
                                ui.label(source.display_name).classes("text-sm")
                            r.on("click", lambda _e, row=r, s=source: select_item(row, s))  # type: ignore[misc]
                        ui.button(
                            "+ Add",
                            on_click=open_add_source_dialog,
                        ).props("flat dense color=primary").classes("w-full mt-1")

                    with ui.expansion("Projects", icon="work").classes("w-full"):
                        for project in config.projects:
                            r = ui.row().classes(
                                "cursor-pointer w-full px-3 py-1 rounded items-center gap-2"
                            )
                            with r:
                                ui.icon("work_outline").classes("text-sm text-gray-500")
                                ui.label(project.display_name).classes("text-sm")
                            r.on("click", lambda _e, row=r, p=project: select_item(row, p))  # type: ignore[misc]
                        ui.button(
                            "+ Add",
                            on_click=lambda: ui.notify("Add project dialog — coming soon"),
                        ).props("flat dense color=primary").classes("w-full mt-1")

            with splitter.after:
                detail_col = ui.column().classes("w-full p-6")
                detail_ref["panel"] = detail_col
                with detail_col:
                    ui.label("Select an item to see details").classes(
                        "text-gray-400 text-lg"
                    )

    ui.run(host="127.0.0.1", title="Skill Manager", reload=False)
