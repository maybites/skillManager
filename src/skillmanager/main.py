from nicegui import ui, app


def run() -> None:
    app.title = "Skill Manager"
    ui.label("Skill Manager")
    ui.run(host="127.0.0.1", title="Skill Manager", reload=False)
