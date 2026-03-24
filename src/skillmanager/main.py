from typing import Union

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
                            on_click=lambda: ui.notify("Add source dialog — coming soon"),
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
