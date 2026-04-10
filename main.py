from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import flet as ft

from cms_core import ENTRY_DEFINITIONS, build_pdf_asset_path, build_target_path, render_markdown, resolve_site_root, validate_values


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
    self.local_site_server = None
    self.local_site_server_root = None
    self.local_site_url = ""

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
    self.preview_button = ft.Button("Refresh Preview", on_click=self.handle_preview)
    self.preview_container = ft.Container(content=self.preview_field, col={"md": 6})
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
            self.preview_button,
            ft.Button("Save Entry", on_click=self.handle_save),
            ft.OutlinedButton("Clear Form", on_click=self.handle_clear),
            ft.OutlinedButton("Open Content Folder", on_click=self.handle_open_content),
            ft.OutlinedButton(
              "Local Site",
              tooltip="Build the site locally and open it on localhost in your default browser.",
              on_click=self.handle_build_and_open,
            ),
          ],
          spacing=12,
          wrap=True,
        ),
        self.status_text,
        ft.ResponsiveRow(
          controls=[
            ft.Container(content=self.form_column, col={"md": 6}, padding=ft.Padding.only(right=12)),
            self.preview_container,
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
          "Folder-based entries create or overwrite a file in the target collection directory.",
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
      control, value_control = self.make_control(field)
      self.field_controls[field["name"]] = value_control
      controls.append(control)

    has_markdown = any(field["type"] == "markdown" for field in entry["fields"])
    self.preview_button.visible = has_markdown
    self.preview_container.visible = has_markdown
    if not has_markdown:
      self.preview_field.value = ""

    self.form_column.controls = controls
    self.page.update()

  def make_control(self, field):
    if field["type"] == "boolean":
      control = ft.Checkbox(label=field["label"], value=bool(field.get("default", False)))
      return control, control

    if field["type"] == "pdf":
      value_field = ft.TextField(
        label=field["label"],
        hint_text=field.get("hint"),
        expand=True,
        read_only=True,
      )
      pick_button = ft.OutlinedButton(
        "Select PDF",
        on_click=lambda _event, field_name=field["name"]: self.handle_pick_pdf(field_name),
      )
      wrapper = ft.Column(
        controls=[value_field, pick_button],
        spacing=8,
      )
      return wrapper, value_field

    kwargs = {
      "label": field["label"],
      "hint_text": field.get("hint"),
      "multiline": field["type"] == "markdown",
      "min_lines": 10 if field["type"] == "markdown" else None,
      "max_lines": 18 if field["type"] == "markdown" else None,
      "expand": True,
      "on_change": self.handle_live_change,
    }

    control = ft.TextField(**kwargs)
    return control, control

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
      entry = ENTRY_DEFINITIONS[self.entry_dropdown.value]
      target_path = build_target_path(PROJECT_ROOT, self.site_root_field.value, self.entry_dropdown.value, values)

      if entry.get("pdf_embed"):
        pdf_target_path = build_pdf_asset_path(PROJECT_ROOT, self.site_root_field.value, self.entry_dropdown.value, values)
        selected_pdf = values.get("pdf_file", "").strip()
        source_text = selected_pdf if selected_pdf else "No PDF selected"
        self.preview_field.value = ""
        self.set_status(
          f"Source PDF: {source_text} | Target file: {target_path} | Embedded PDF: {pdf_target_path}",
          ft.Colors.BLUE_700,
        )
      elif any(field["type"] == "pdf" for field in entry["fields"]):
        selected_pdf = values.get("pdf_file", "").strip()
        source_text = selected_pdf if selected_pdf else "No PDF selected"
        self.preview_field.value = ""
        self.set_status(f"Source PDF: {source_text} | Target file: {target_path}", ft.Colors.BLUE_700)
      else:
        self.preview_field.value = render_markdown(self.entry_dropdown.value, values)
        self.set_status(f"Target file: {target_path}", ft.Colors.BLUE_700)
    except Exception as error:
      self.preview_field.value = ""
      self.set_status(str(error), ft.Colors.ORANGE_700)

    self.page.update()

  def handle_live_change(self, _event):
    self.refresh_preview()

  def handle_preview(self, _event):
    self.refresh_preview()

  def handle_pick_pdf(self, field_name):
    files = self.pick_local_pdf_file()
    control = self.field_controls.get(field_name)
    if control and files:
      control.value = files[0]
      self.refresh_preview()

  def pick_local_pdf_file(self):
    try:
      import tkinter as tk
      from tkinter import filedialog

      root = tk.Tk()
      root.withdraw()
      root.update()
      selected = filedialog.askopenfilename(
        title="Select PDF",
        filetypes=[("PDF files", "*.pdf")],
      )
      root.destroy()
      return [selected] if selected else []
    except Exception:
      pass

    # macOS fallback for environments where Tk is unavailable.
    script = (
      'POSIX path of (choose file with prompt "Select PDF" '
      'of type {"com.adobe.pdf"})'
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    selected = (result.stdout or "").strip()
    if result.returncode == 0 and selected:
      return [selected]

    return []

  def handle_save(self, _event):
    try:
      values = self.collect_values()
      errors = validate_values(self.entry_dropdown.value, values)
      if errors:
        raise ValueError(" ".join(errors))

      entry = ENTRY_DEFINITIONS[self.entry_dropdown.value]
      target_path = build_target_path(PROJECT_ROOT, self.site_root_field.value, self.entry_dropdown.value, values)
      target_path.parent.mkdir(parents=True, exist_ok=True)

      if entry.get("pdf_embed"):
        source_pdf = Path(values.get("pdf_file", "").strip())
        if source_pdf.suffix.lower() != ".pdf":
          raise ValueError("Selected file must be a PDF.")
        if not source_pdf.exists():
          raise ValueError("Selected PDF file does not exist.")

        pdf_target_path = build_pdf_asset_path(PROJECT_ROOT, self.site_root_field.value, self.entry_dropdown.value, values)
        pdf_target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pdf, pdf_target_path)

        render_values = dict(values)
        render_values["pdf_embed_src"] = f"./../../pdfs/{pdf_target_path.name}"
        content = render_markdown(self.entry_dropdown.value, render_values)
        target_path.write_text(content, encoding="utf-8")
        self.preview_field.value = content
      elif any(field["type"] == "pdf" for field in entry["fields"]):
        source_pdf = Path(values.get("pdf_file", "").strip())
        if source_pdf.suffix.lower() != ".pdf":
          raise ValueError("Selected file must be a PDF.")
        if not source_pdf.exists():
          raise ValueError("Selected PDF file does not exist.")

        shutil.copy2(source_pdf, target_path)
        self.preview_field.value = ""
      else:
        content = render_markdown(self.entry_dropdown.value, values)
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

  def handle_build_and_open(self, _event):
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
        candidates = [
          PROJECT_ROOT / "dist",
          PROJECT_ROOT.parent / "dist",
        ]
        output_dir = next((path for path in candidates if path.exists() and path.is_dir()), None)

        if not output_dir:
          self.set_status("Build completed, but no dist output folder was found.", ft.Colors.ORANGE_700)
        else:
          index_path = output_dir / "index.html"
          if index_path.exists():
            site_url = self.ensure_local_site_server(output_dir)
            subprocess.Popen(["open", site_url])
            self.set_status(f"Build completed and opened {site_url}", ft.Colors.GREEN_700)
          else:
            html_files = sorted(output_dir.rglob("*.html"))
            if html_files:
              site_url = self.ensure_local_site_server(output_dir)
              subprocess.Popen(["open", site_url])
              self.set_status(f"Build completed and opened {site_url}", ft.Colors.GREEN_700)
            else:
              self.set_status(
                "Build completed, but no rendered HTML files were generated.",
                ft.Colors.ORANGE_700,
              )
      else:
        self.set_status("Build failed. See output below.", ft.Colors.RED_700)
    except Exception as error:
      self.command_output.value = str(error)
      self.set_status(str(error), ft.Colors.RED_700)

    self.page.update()

  def ensure_local_site_server(self, output_dir):
    if (
      self.local_site_server is not None
      and self.local_site_server.poll() is None
      and self.local_site_server_root == output_dir
      and self.local_site_url
    ):
      return self.local_site_url

    if self.local_site_server is not None and self.local_site_server.poll() is None:
      self.local_site_server.terminate()

    port = self.find_free_port(8000)
    self.local_site_server = subprocess.Popen(
      [
        sys.executable,
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
        "--directory",
        str(output_dir),
      ],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
    )
    # Give the server a brief moment to bind before opening the browser.
    time.sleep(0.15)
    self.local_site_server_root = output_dir
    self.local_site_url = f"http://127.0.0.1:{port}/"
    return self.local_site_url

  def find_free_port(self, start_port):
    port = start_port
    while port < start_port + 100:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sock.connect_ex(("127.0.0.1", port)) != 0:
          return port
      port += 1

    raise RuntimeError("No available localhost port found for Local Site preview.")

  def set_status(self, message, color):
    self.status_text.value = message
    self.status_text.color = color


def main():
  ft.run(HatCmsApp)


if __name__ == "__main__":
  main()