from pathlib import Path
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import date, datetime, time as dt_time, timedelta
from urllib.parse import parse_qs, unquote, urlparse

try:
  import tomllib
except ImportError:
  tomllib = None

import flet as ft

try:
  from dotenv import load_dotenv
except ImportError:
  load_dotenv = None

from cms_core import ENTRY_DEFINITIONS, build_pdf_asset_path, build_target_path, render_markdown, resolve_site_root, validate_values


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SITE_ROOT = PROJECT_ROOT / "site"
SITE_CONFIG_PATH = PROJECT_ROOT / "site" / "config.toml"
DEFAULT_HOME_CANVA_EMBED_URL = "https://www.canva.com/design/DAGgmfR_fO4/xE9UDOAcGfdVogOlKKv58Q/view?embed"

if load_dotenv is not None:
  load_dotenv(PROJECT_ROOT / ".env")


class HatCmsApp:
  def __init__(self, page):
    self.page = page
    self.page.title = "HAT CMS"
    self.page.theme_mode = ft.ThemeMode.LIGHT
    self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    self.page.bgcolor = ft.Colors.WHITE
    self.page.padding = 20
    self.page.scroll = ft.ScrollMode.AUTO
    self.page.window.width = 1400
    self.page.window.height = 960

    self.field_controls = {}
    self.field_definitions = {}
    self.local_site_server = None
    self.local_site_server_root = None
    self.local_site_url = ""
    self.google_calendar_sync_enabled = os.getenv("GOOGLE_CALENDAR_SYNC_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    self.google_calendar_timezone = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "America/Chicago").strip() or "America/Chicago"
    self.google_service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(PROJECT_ROOT / "google-service-account.json")).strip()
    self.google_calendar_id = self.detect_google_calendar_id()

    embed_enabled, embed_url = self.load_home_canva_embed_settings()
    self.home_canva_embed_enabled = ft.Checkbox(
      label="Show Home Page Canva Embed",
      value=embed_enabled,
      on_change=self.handle_home_canva_embed_toggle,
    )
    self.home_canva_embed_url = ft.TextField(
      label="Home Canva Embed URL",
      value=embed_url,
      width=640,
      hint_text="Paste Canva embed URL (for example: .../view?embed)",
      read_only=not embed_enabled,
    )

    self.site_root_field = ft.TextField(
      label="Hugo Site Root",
      value=str(DEFAULT_SITE_ROOT),
      expand=True,
      hint_text="Defaults to ./site. You can point this at another Hugo site if needed.",
    )

    _enabled_keys = {"event", "post", "document"}
    _ordered_keys = ["event", "post", "document"] + [
      k for k in ENTRY_DEFINITIONS if k not in _enabled_keys
    ]
    self.entry_dropdown = ft.Dropdown(
      label="Content Type",
      width=320,
      value="event",
      options=[
        ft.dropdown.Option(
          key=k,
          text=ENTRY_DEFINITIONS[k]["label"],
          disabled=k not in _enabled_keys,
        )
        for k in _ordered_keys
      ],
      on_select=self.handle_entry_change,
    )

    self.status_text = ft.Text(value="", selectable=True)
    self.command_output = ft.TextField(
      label="Build Output",
      multiline=True,
      min_lines=8,
      max_lines=12,
      read_only=True,
    )

    self.form_header = ft.Column(spacing=4)
    self.form_column = ft.Column(spacing=12)
    self.body_column = ft.Column(spacing=12)
    self.form_container = ft.Container(content=self.form_column, col={"md": 6}, padding=ft.Padding.only(right=12))
    self.body_container = ft.Container(content=self.body_column, col={"md": 6}, padding=ft.Padding.only(left=12), visible=False)

    # Shared pickers (Wieting pattern): created once, live in page.overlay permanently.
    self._picker_target_field = None
    self._picker_mode = "date"  # "date" or "datetime"
    self._date_picker = ft.DatePicker(
      on_change=self._on_date_picker_change,
      first_date=datetime(1990, 1, 1),
      last_date=datetime(2100, 12, 31),
    )
    self._time_picker = ft.TimePicker(
      on_change=self._on_time_picker_change,
    )
    self._simple_time_picker = ft.TimePicker(
      on_change=self._on_simple_time_picker_change,
    )

    self.build_form()
    self.page.add(self.build_layout())
    self.page.overlay.append(self._date_picker)
    self.page.overlay.append(self._time_picker)
    self.page.overlay.append(self._simple_time_picker)
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
          controls=[
            self.home_canva_embed_enabled,
            self.home_canva_embed_url,
            ft.OutlinedButton("Save Home Embed Settings", on_click=self.handle_save_home_embed_settings),
          ],
          spacing=12,
          vertical_alignment=ft.CrossAxisAlignment.END,
          wrap=True,
        ),
        ft.Row(
          controls=[self.site_root_field, self.entry_dropdown],
          spacing=16,
          vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        ft.Row(
          controls=[
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
        self.form_header,
        ft.ResponsiveRow(
          controls=[
            self.form_container,
            self.body_container,
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
    self.field_definitions = {}
    entry = ENTRY_DEFINITIONS[self.entry_dropdown.value]
    header_controls = [
      ft.Text(
        f"Editing: {entry['label']}",
        size=20,
        weight=ft.FontWeight.W_600,
      )
    ]
    controls = []

    if entry["mode"] == "folder":
      header_controls.append(
        ft.Text(
          "Folder-based entries create or overwrite a file in the target collection directory.",
          size=12,
        )
      )
    else:
      header_controls.append(
        ft.Text(
          f"This entry writes directly to {entry['path']}.",
          size=12,
        )
      )

    body_controls = []
    for field in entry["fields"]:
      control, value_control = self.make_control(field)
      self.field_controls[field["name"]] = value_control
      self.field_definitions[field["name"]] = field
      if field["type"] == "markdown":
        body_controls.append(control)
      else:
        controls.append(control)

    self.form_header.controls = header_controls
    self.form_column.controls = controls
    self.body_column.controls = body_controls
    self.body_container.visible = bool(body_controls)
    self.page.update()

  def make_control(self, field):
    if field["type"] == "time":
      default_value = str(field.get("default") or "00:00:00")
      value_field = ft.TextField(
        label=field["label"],
        hint_text=field.get("hint"),
        value=default_value,
        expand=True,
        read_only=True,
      )
      pick_button = ft.OutlinedButton(
        "Pick Time",
        on_click=lambda _event, field_name=field["name"]: self.handle_pick_time(field_name),
      )
      wrapper = ft.Row(
        controls=[value_field, pick_button],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.END,
        expand=True,
      )
      return wrapper, value_field

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
      wrapper = ft.Row(
        controls=[value_field, pick_button],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.END,
        expand=True,
      )
      return wrapper, value_field

    if field["type"] == "date":
      default_value = str(field.get("default") or date.today().isoformat())
      value_field = ft.TextField(
        label=field["label"],
        hint_text=field.get("hint"),
        value=default_value,
        expand=True,
        read_only=True,
      )
      pick_button = ft.OutlinedButton(
        "Pick Date",
        on_click=lambda _event, field_name=field["name"]: self.handle_pick_date(field_name),
      )
      wrapper = ft.Row(
        controls=[value_field, pick_button],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.END,
        expand=True,
      )
      return wrapper, value_field

    if field["type"] == "datetime":
      default_value = str(field.get("default") or self.current_datetime_iso())
      value_field = ft.TextField(
        label=field["label"],
        hint_text=field.get("hint"),
        value=default_value,
        expand=True,
        read_only=True,
      )
      pick_button = ft.OutlinedButton(
        "Pick Date",
        on_click=lambda _event, field_name=field["name"]: self.handle_pick_datetime(field_name),
      )
      time_button = ft.OutlinedButton(
        "Pick Time",
        on_click=lambda _event, field_name=field["name"]: self.handle_pick_datetime_time(field_name),
      )
      now_button = ft.TextButton(
        "Now",
        on_click=lambda _event, field_name=field["name"]: self.handle_set_datetime_now(field_name),
      )
      wrapper = ft.Row(
        controls=[value_field, pick_button, time_button, now_button],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.END,
        expand=True,
      )
      return wrapper, value_field

    kwargs = {
      "label": field["label"],
      "hint_text": field.get("hint"),
      "multiline": field["type"] == "markdown",
      "min_lines": 10 if field["type"] == "markdown" else None,
      "max_lines": 18 if field["type"] == "markdown" else None,
      "text_vertical_align": ft.VerticalAlignment.START if field["type"] == "markdown" else None,
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
        if selected_pdf:
          self.set_status(
            f"Source PDF: {selected_pdf} | Target file: {target_path} | Embedded PDF: {pdf_target_path}",
            ft.Colors.BLUE_700,
          )
        else:
          self.set_status("No PDF selected yet.", ft.Colors.BLUE_700)
      elif self.entry_dropdown.value == "event":
        selected_details = values.get("event_details_pdf", "").strip()
        if selected_details:
          details_target = self.get_event_details_pdf_target_path(values)
          self.set_status(
            f"Event Details PDF: {selected_details} | Target file: {target_path} | Embedded Details: {details_target}",
            ft.Colors.BLUE_700,
          )
        else:
          self.set_status(f"Target file: {target_path}", ft.Colors.BLUE_700)
      elif any(field["type"] == "pdf" for field in entry["fields"]):
        selected_pdf = values.get("pdf_file", "").strip()
        if selected_pdf:
          self.set_status(f"Source PDF: {selected_pdf} | Target file: {target_path}", ft.Colors.BLUE_700)
        else:
          self.set_status("No PDF selected yet.", ft.Colors.BLUE_700)
      else:
        # Render to validate form data and frontmatter generation, without displaying preview text.
        render_markdown(self.entry_dropdown.value, values)
        self.set_status(f"Target file: {target_path}", ft.Colors.BLUE_700)
    except Exception as error:
      self.set_status(str(error), ft.Colors.ORANGE_700)

    self.page.update()

  def handle_live_change(self, _event):
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
      elif self.entry_dropdown.value == "event":
        render_values = dict(values)
        source_details = Path(values.get("event_details_pdf", "").strip()) if values.get("event_details_pdf", "").strip() else None
        if source_details:
          if source_details.suffix.lower() != ".pdf":
            raise ValueError("Event Details must be a PDF file.")
          if not source_details.exists():
            raise ValueError("Selected Event Details PDF does not exist.")

          details_target_path = self.get_event_details_pdf_target_path(values)
          details_target_path.parent.mkdir(parents=True, exist_ok=True)
          shutil.copy2(source_details, details_target_path)
          render_values["eventDetailsPdf"] = f"/pdfs/{details_target_path.name}"

        content = render_markdown(self.entry_dropdown.value, render_values)
        target_path.write_text(content, encoding="utf-8")
      elif any(field["type"] == "pdf" for field in entry["fields"]):
        source_pdf = Path(values.get("pdf_file", "").strip())
        if source_pdf.suffix.lower() != ".pdf":
          raise ValueError("Selected file must be a PDF.")
        if not source_pdf.exists():
          raise ValueError("Selected PDF file does not exist.")

        shutil.copy2(source_pdf, target_path)
      else:
        content = render_markdown(self.entry_dropdown.value, values)
        target_path.write_text(content, encoding="utf-8")

      status_message = f"Saved {target_path}"
      status_color = ft.Colors.GREEN_700
      if self.entry_dropdown.value == "event":
        try:
          sync_note = self.sync_event_to_google_calendar(values)
          if sync_note:
            status_message = f"{status_message} | {sync_note}"
        except Exception as sync_error:
          short_error = str(sync_error).splitlines()[0].strip()
          status_message = f"{status_message} | Google Calendar sync failed: {short_error}"
          status_color = ft.Colors.ORANGE_700

      self.set_status(status_message, status_color)
    except Exception as error:
      self.set_status(str(error), ft.Colors.RED_700)

    self.page.update()

  def get_event_details_pdf_target_path(self, values):
    site_root = resolve_site_root(PROJECT_ROOT, self.site_root_field.value)
    target_path = build_target_path(PROJECT_ROOT, self.site_root_field.value, "event", values)
    return site_root / "static" / "pdfs" / f"{target_path.stem}-details.pdf"

  def handle_pick_date(self, field_name):
    control = self.field_controls.get(field_name)
    if not isinstance(control, ft.TextField):
      return
    try:
      self._date_picker.value = datetime.strptime((control.value or "").strip(), "%Y-%m-%d")
    except ValueError:
      self._date_picker.value = datetime.today()
    self._picker_target_field = field_name
    self._picker_mode = "date"
    self._date_picker.open = True
    self.page.update()

  def current_datetime_iso(self):
    return datetime.now().astimezone().replace(microsecond=0).isoformat()

  def parse_datetime_value(self, raw_value):
    text = (raw_value or "").strip()
    if text:
      try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
          parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return parsed.replace(microsecond=0)
      except ValueError:
        pass

    return datetime.now().astimezone().replace(microsecond=0)

  def handle_set_datetime_now(self, field_name):
    control = self.field_controls.get(field_name)
    if not isinstance(control, ft.TextField):
      return

    control.value = self.current_datetime_iso()
    self.refresh_preview()

  def handle_pick_datetime(self, field_name):
    control = self.field_controls.get(field_name)
    if not isinstance(control, ft.TextField):
      return
    current_dt = self.parse_datetime_value(control.value)
    self._date_picker.value = datetime(current_dt.year, current_dt.month, current_dt.day)
    self._picker_target_field = field_name
    self._picker_mode = "datetime"
    self._date_picker.open = True
    self.page.update()

  def handle_pick_datetime_time(self, field_name):
    control = self.field_controls.get(field_name)
    if not isinstance(control, ft.TextField):
      return
    current_dt = self.parse_datetime_value(control.value)
    self._time_picker.value = dt_time(
      hour=current_dt.hour,
      minute=current_dt.minute,
      second=current_dt.second,
    )
    self._picker_target_field = field_name
    self._time_picker.open = True
    self.page.update()

  def _on_date_picker_change(self, _event):
    if self._date_picker.value is None or self._picker_target_field is None:
      return
    control = self.field_controls.get(self._picker_target_field)
    if not isinstance(control, ft.TextField):
      return
    selected = self._date_picker.value
    selected_date = selected.date() if isinstance(selected, datetime) else selected
    if self._picker_mode == "date":
      control.value = selected_date.isoformat()
    else:
      current_dt = self.parse_datetime_value(control.value)
      updated = current_dt.replace(year=selected_date.year, month=selected_date.month, day=selected_date.day)
      control.value = updated.isoformat()
    self.refresh_preview()

  def _on_time_picker_change(self, _event):
    if self._time_picker.value is None or self._picker_target_field is None:
      return
    control = self.field_controls.get(self._picker_target_field)
    if not isinstance(control, ft.TextField):
      return
    selected = self._time_picker.value
    selected_time = selected.time() if isinstance(selected, datetime) else selected
    current_dt = self.parse_datetime_value(control.value)
    updated = current_dt.replace(
      hour=selected_time.hour,
      minute=selected_time.minute,
      second=selected_time.second,
    )
    control.value = updated.isoformat()
    self.refresh_preview()

  def handle_pick_time(self, field_name):
    control = self.field_controls.get(field_name)
    if not isinstance(control, ft.TextField):
      return
    try:
      self._simple_time_picker.value = datetime.strptime((control.value or "").strip(), "%H:%M:%S").time()
    except ValueError:
      self._simple_time_picker.value = dt_time(0, 0, 0)
    self._picker_target_field = field_name
    self._simple_time_picker.open = True
    self.page.update()

  def _on_simple_time_picker_change(self, _event):
    if self._simple_time_picker.value is None or self._picker_target_field is None:
      return
    control = self.field_controls.get(self._picker_target_field)
    if not isinstance(control, ft.TextField):
      return
    selected = self._simple_time_picker.value
    selected_time = selected.time() if isinstance(selected, datetime) else selected
    control.value = selected_time.isoformat()
    self.refresh_preview()

  def detect_google_calendar_id(self):
    configured = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
    if configured:
      return configured

    calendar_page = PROJECT_ROOT / "site" / "content" / "calendar.md"
    if not calendar_page.exists():
      return ""

    text = calendar_page.read_text(encoding="utf-8")
    iframe_matches = re.findall(r'https://calendar.google.com/calendar/embed\?[^"\']+', text)
    if not iframe_matches:
      return ""

    for url in reversed(iframe_matches):
      decoded_query = urlparse(url.replace("&amp;", "&")).query
      params = parse_qs(decoded_query)
      if params.get("src"):
        return unquote(params["src"][0])

    return ""

  def parse_time_text(self, raw_text):
    text = (raw_text or "").strip()
    if not text:
      return None

    normalized = text.lower().replace(" ", "")
    candidates = [
      "%H:%M:%S",
      "%H:%M",
      "%I:%M%p",
      "%I%p",
      "%I:%M %p",
      "%I %p",
    ]
    for fmt in candidates:
      try:
        return datetime.strptime(normalized if "%p" in fmt else text, fmt).time()
      except ValueError:
        continue

    return None

  def sync_event_to_google_calendar(self, values):
    if not self.google_calendar_sync_enabled:
      return "Google Calendar sync disabled in .env."

    if not self.google_calendar_id:
      raise ValueError("Missing GOOGLE_CALENDAR_ID and unable to detect one from site/content/calendar.md")

    credentials_path = Path(self.google_service_account_file)
    if not credentials_path.is_absolute():
      credentials_path = PROJECT_ROOT / credentials_path
    credentials_path = credentials_path.resolve()
    if not credentials_path.exists():
      raise ValueError(f"Missing Google service account file: {credentials_path}")

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/calendar.events"]
    credentials = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    event_date_text = str(values.get("date") or "").strip()
    if not event_date_text:
      publish = str(values.get("publishDate") or "")
      match = re.search(r"\d{4}-\d{2}-\d{2}", publish)
      if match:
        event_date_text = match.group(0)

    if not event_date_text:
      raise ValueError("Event date is required for Google Calendar sync")

    event_date = datetime.strptime(event_date_text, "%Y-%m-%d").date()
    start_time = self.parse_time_text(values.get("startTime"))
    end_time = self.parse_time_text(values.get("endTime"))

    event_payload = {
      "summary": str(values.get("title") or "Untitled Event").strip() or "Untitled Event",
      "location": str(values.get("location") or "").strip(),
      "description": str(values.get("body") or "").strip(),
      "status": "confirmed",
    }

    if start_time is None:
      event_payload["start"] = {"date": event_date.isoformat()}
      event_payload["end"] = {"date": (event_date + timedelta(days=1)).isoformat()}
    else:
      start_dt = datetime.combine(event_date, start_time)
      if end_time is None:
        end_dt = start_dt + timedelta(hours=1)
      else:
        end_dt = datetime.combine(event_date, end_time)
        if end_dt <= start_dt:
          end_dt = start_dt + timedelta(hours=1)

      event_payload["start"] = {
        "dateTime": start_dt.isoformat(),
        "timeZone": self.google_calendar_timezone,
      }
      event_payload["end"] = {
        "dateTime": end_dt.isoformat(),
        "timeZone": self.google_calendar_timezone,
      }

    service.events().insert(
      calendarId=self.google_calendar_id,
      body=event_payload,
      sendUpdates="none",
    ).execute()

    return "Google Calendar event created (confirmed)."

  def handle_clear(self, _event):
    for field_name, control in self.field_controls.items():
      field = self.field_definitions.get(field_name, {})
      if isinstance(control, ft.Checkbox):
        control.value = False
      else:
        if field.get("type") == "date":
          control.value = date.today().isoformat()
        elif field.get("type") == "datetime":
          control.value = self.current_datetime_iso()
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

  def sync_home_canva_controls(self):
    self.home_canva_embed_url.read_only = not bool(self.home_canva_embed_enabled.value)

  def handle_home_canva_embed_toggle(self, _event):
    self.sync_home_canva_controls()
    self.page.update()

  def load_home_canva_embed_settings(self):
    enabled = True
    url = DEFAULT_HOME_CANVA_EMBED_URL

    if SITE_CONFIG_PATH.exists():
      config_text = SITE_CONFIG_PATH.read_text(encoding="utf-8")

      if tomllib is not None:
        try:
          parsed = tomllib.loads(config_text)
          params = parsed.get("params", {})
          enabled = bool(params.get("homeCanvaEmbedEnabled", enabled))
          configured_url = self.extract_embed_url(str(params.get("homeCanvaEmbedUrl", "")).strip())
          if configured_url:
            url = configured_url
          return enabled, url
        except Exception:
          pass

      enabled_match = re.search(r"^\s*homeCanvaEmbedEnabled\s*=\s*(true|false)\s*$", config_text, flags=re.IGNORECASE | re.MULTILINE)
      if enabled_match:
        enabled = enabled_match.group(1).lower() == "true"

      url_match = re.search(r"^\s*homeCanvaEmbedUrl\s*=\s*\"([^\"]*)\"\s*$", config_text, flags=re.MULTILINE)
      if url_match and url_match.group(1).strip():
        url = self.extract_embed_url(url_match.group(1).strip())

    return enabled, url

  def upsert_config_param(self, config_text, key, value_literal):
    pattern = rf"^(\s*{re.escape(key)}\s*=\s*).*$"
    replacement = rf"\1{value_literal}"
    updated_text, count = re.subn(pattern, replacement, config_text, flags=re.MULTILINE)
    if count > 0:
      return updated_text

    params_match = re.search(r"^\[params\]\s*$", config_text, flags=re.MULTILINE)
    if not params_match:
      return config_text

    insert_at = params_match.end()
    return f"{config_text[:insert_at]}\n\t{key} = {value_literal}{config_text[insert_at:]}"

  def extract_embed_url(self, raw_value):
    text = (raw_value or "").strip()
    if not text:
      return ""

    iframe_src = re.search(r'src\s*=\s*["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
    if iframe_src:
      return iframe_src.group(1).strip()

    return text

  def handle_save_home_embed_settings(self, _event):
    try:
      if not SITE_CONFIG_PATH.exists():
        raise ValueError(f"Missing config file: {SITE_CONFIG_PATH}")

      embed_url = self.extract_embed_url(self.home_canva_embed_url.value)
      if not embed_url:
        raise ValueError("Home Canva Embed URL is required.")

      self.home_canva_embed_url.value = embed_url

      enabled_literal = "true" if bool(self.home_canva_embed_enabled.value) else "false"
      url_literal = f'"{embed_url.replace("\\", "\\\\").replace("\"", "\\\"")}"'

      config_text = SITE_CONFIG_PATH.read_text(encoding="utf-8")
      config_text = self.upsert_config_param(config_text, "homeCanvaEmbedEnabled", enabled_literal)
      config_text = self.upsert_config_param(config_text, "homeCanvaEmbedUrl", url_literal)
      SITE_CONFIG_PATH.write_text(config_text, encoding="utf-8")

      self.set_status("Saved home page Canva embed settings to site/config.toml.", ft.Colors.GREEN_700)
    except Exception as error:
      self.set_status(str(error), ft.Colors.RED_700)

    self.page.update()


def main():
  ft.run(HatCmsApp)


if __name__ == "__main__":
  main()