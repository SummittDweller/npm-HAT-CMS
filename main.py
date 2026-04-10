from pathlib import Path
import subprocess

import flet as ft

from cms_core import ENTRY_DEFINITIONS, build_target_path, render_markdown, resolve_site_root


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SITE_ROOT = PROJECT_ROOT / "site"


class HatCmsApp:
  def __init__(self, page):
    self.page = page
    self.page.title = "HAT CMS"
    self.page.padding = 20
    self.page.scroll = ft.ScrollMode.AUTO
    self.page.window.width = 1400
    self.page.window.height = 960

    self.field_controls = {}

    self.site_root_field = ft.TextField(
      label="Hugo Site Root",
      value=str(DEFAULT_SITE_ROOT),
      expand=True,
      hint_text="Defaults to ./site. You can point this at another Hugo site if needed.",
    )

    self.entry_dropdown = ft.Dropdown(
      label="Content Type",
      width=320,
      value="post",
      options=[
        ft.dropdown.Option(key=entry_key, text=entry["label"])
        for entry_key, entry in ENTRY_DEFINITIONS.items()
      ],
      on_select=self.handle_entry_change,
    )

    self.status_text = ft.Text(value="", selectable=True)
    self.preview_field = ft.TextField(
      label="Markdown Preview",
      multiline=True,
      min_lines=20,
      max_lines=28,
      expand=True,
      read_only=True,
      text_style=ft.TextStyle(font_family="Courier New"),
    )
    self.command_output = ft.TextField(
      label="Build Output",
      multiline=True,
      min_lines=8,
      max_lines=12,
      read_only=True,
    )

    self.form_column = ft.Column(spacing=12)

    self.build_form()
    self.page.add(self.build_layout())
    self.refresh_preview()

  def build_layout(self):
    return ft.Column(
      controls=[
        ft.Text("Local Hugo Content Manager", size=28, weight=ft.FontWeight.BOLD),
        ft.Text(
          "This app writes markdown files directly into the Hugo content tree. "
          "The generated site can then be built and deployed independently of the CMS.",
          size=14,
        ),
        ft.Row(
          controls=[self.site_root_field, self.entry_dropdown],
          spacing=16,
          vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        ft.Row(
          controls=[
            ft.ElevatedButton("Refresh Preview", on_click=self.handle_preview),
            ft.ElevatedButton("Save Entry", on_click=self.handle_save),
            ft.OutlinedButton("Clear Form", on_click=self.handle_clear),
            ft.OutlinedButton("Open Content Folder", on_click=self.handle_open_content),
            ft.OutlinedButton("Build Site", on_click=self.handle_build),
          ],
          spacing=12,
          wrap=True,
        ),
        self.status_text,
        ft.ResponsiveRow(
          controls=[
            ft.Container(content=self.form_column, col={"md": 6}, padding=ft.padding.only(right=12)),
            ft.Container(content=self.preview_field, col={"md": 6}),
          ]
        ),
        self.command_output,
      ],
      spacing=16,
    )

  def handle_entry_change(self, _event):
    self.build_form()
    self.refresh_preview()

  def build_form(self):
    self.field_controls = {}
    entry = ENTRY_DEFINITIONS[self.entry_dropdown.value]
    controls = [
      ft.Text(
        f"Editing: {entry['label']}",
        size=20,
        weight=ft.FontWeight.W_600,
      )
    ]

    if entry["mode"] == "folder":
      controls.append(
        ft.Text(
          "Folder-based entries create or overwrite a markdown file in the target collection directory.",
          size=12,
        )
      )
    else:
      controls.append(
        ft.Text(
          f"This entry writes directly to {entry['path']}.",
          size=12,
        )
      )

    for field in entry["fields"]:
      control = self.make_control(field)
      self.field_controls[field["name"]] = control
      controls.append(control)

    self.form_column.controls = controls
    self.page.update()

  def make_control(self, field):
    if field["type"] == "boolean":
      return ft.Checkbox(label=field["label"], value=bool(field.get("default", False)))

    kwargs = {
      "label": field["label"],
      "hint_text": field.get("hint"),
      "multiline": field["type"] == "markdown",
      "min_lines": 10 if field["type"] == "markdown" else None,
      "max_lines": 18 if field["type"] == "markdown" else None,
      "expand": True,
      "on_change": self.handle_live_change,
    }

    return ft.TextField(**kwargs)

  def collect_values(self):
    values = {}
    for name, control in self.field_controls.items():
      if isinstance(control, ft.Checkbox):
        values[name] = bool(control.value)
      else:
        values[name] = control.value or ""

    return values

  def refresh_preview(self):
    try:
      values = self.collect_values()
      self.preview_field.value = render_markdown(self.entry_dropdown.value, values)
      target_path = build_target_path(PROJECT_ROOT, self.site_root_field.value, self.entry_dropdown.value, values)
      self.set_status(f"Target file: {target_path}", ft.Colors.BLUE_700)
    except Exception as error:
      self.preview_field.value = ""
      self.set_status(str(error), ft.Colors.ORANGE_700)

    self.page.update()

  def handle_live_change(self, _event):
    self.refresh_preview()

  def handle_preview(self, _event):
    self.refresh_preview()

  def handle_save(self, _event):
    try:
      values = self.collect_values()
      target_path = build_target_path(PROJECT_ROOT, self.site_root_field.value, self.entry_dropdown.value, values)
      content = render_markdown(self.entry_dropdown.value, values)
      target_path.parent.mkdir(parents=True, exist_ok=True)
      target_path.write_text(content, encoding="utf-8")
      self.preview_field.value = content
      self.set_status(f"Saved {target_path}", ft.Colors.GREEN_700)
    except Exception as error:
      self.set_status(str(error), ft.Colors.RED_700)

    self.page.update()

  def handle_clear(self, _event):
    for control in self.field_controls.values():
      if isinstance(control, ft.Checkbox):
        control.value = False
      else:
        control.value = ""

    self.refresh_preview()

  def handle_open_content(self, _event):
    try:
      site_root = resolve_site_root(PROJECT_ROOT, self.site_root_field.value)
      content_root = site_root / "content"
      content_root.mkdir(parents=True, exist_ok=True)
      subprocess.Popen(["open", str(content_root)])
      self.set_status(f"Opened {content_root}", ft.Colors.BLUE_700)
    except Exception as error:
      self.set_status(str(error), ft.Colors.RED_700)

    self.page.update()

  def handle_build(self, _event):
    try:
      command = ["npm", "run", "build"]
      result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
      )
      output = (result.stdout + "\n" + result.stderr).strip()
      self.command_output.value = output or "Build completed with no output."

      if result.returncode == 0:
        self.set_status(f"Build completed. Output is in {PROJECT_ROOT / 'dist'}", ft.Colors.GREEN_700)
      else:
        self.set_status("Build failed. See output below.", ft.Colors.RED_700)
    except Exception as error:
      self.command_output.value = str(error)
      self.set_status(str(error), ft.Colors.RED_700)

    self.page.update()

  def set_status(self, message, color):
    self.status_text.value = message
    self.status_text.color = color


def main():
  ft.app(target=HatCmsApp)


if __name__ == "__main__":
  main()