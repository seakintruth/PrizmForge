"""
Example Python Shiny app: canned report image gallery.

Run (from this directory):
  pip install shiny
  shiny run app.py

Place PNG/JPG/GIF files in report_images/ to display them.
"""
from __future__ import annotations

from pathlib import Path

from shiny import App, reactive, render, ui

IMG_DIR = Path(__file__).parent / "report_images"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def list_images() -> list[str]:
    if not IMG_DIR.is_dir():
        return []
    return sorted(
        p.name for p in IMG_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS and p.is_file()
    )


app_ui = ui.page_fluid(
    ui.h2("Canned Report Image Viewer"),
    ui.p(
        "Browse placeholder / canned report screenshots stored in ",
        ui.code("report_images/"),
        ".",
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select(
                "image",
                "Report image",
                choices=["(none)"] ,
            ),
            ui.input_action_button("refresh", "Refresh list"),
            ui.hr(),
            ui.help_text("Add .png/.jpg files under report_images/ then Refresh."),
        ),
        ui.output_ui("status"),
        ui.output_image("viewer", height="480px"),
    ),
)


def server(input, output, session):
    @reactive.calc
    def images():
        input.refresh()
        return list_images()

    @reactive.effect
    def _update_choices():
        choices = images() or ["(none)"]
        ui.update_select("image", choices=choices, selected=choices[0])

    @render.ui
    def status():
        imgs = images()
        if not imgs:
            return ui.div(
                ui.strong("No images found. "),
                f"Put canned report images in {IMG_DIR}",
            )
        return ui.div(f"{len(imgs)} image(s) available.")

    @render.image
    def viewer():
        name = input.image()
        if not name or name == "(none)":
            return None
        path = IMG_DIR / name
        if not path.is_file():
            return None
        return {"src": str(path), "alt": name}


app = App(app_ui, server)
