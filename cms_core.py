from pathlib import Path
import re

import yaml


ENTRY_DEFINITIONS = {
  "event": {
    "label": "Event",
    "mode": "folder",
    "folder": "content/event",
    "filename_mode": "dated_slug",
    "date_field": "publishDate",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "filename_slug", "label": "Filename Slug", "type": "string", "required": False, "store": False, "hint": "Optional override for the generated filename slug."},
      {"name": "publishDate", "label": "Publish Date", "type": "datetime", "required": True, "hint": "Example: 2026-04-08T10:30:00-05:00"},
      {"name": "location", "label": "Location", "type": "string", "required": False},
      {"name": "expiryDate", "label": "Expiry Date", "type": "date", "required": False, "hint": "Example: 2026-12-31"},
      {"name": "draft", "label": "Draft", "type": "boolean", "required": False, "default": False, "always_write": True},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
  "post": {
    "label": "Post",
    "mode": "folder",
    "folder": "content/post",
    "filename_mode": "slug",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "filename_slug", "label": "Filename Slug", "type": "string", "required": False, "store": False},
      {"name": "publishdate", "label": "Publish Date", "type": "datetime", "required": True, "hint": "Example: 2026-04-08T10:30:00-05:00"},
      {"name": "author", "label": "Author", "type": "string", "required": False},
      {"name": "tags", "label": "Tags", "type": "list", "required": False, "hint": "Comma-separated values."},
      {"name": "categories", "label": "Categories", "type": "list", "required": False, "hint": "Comma-separated values."},
      {"name": "draft", "label": "Draft", "type": "boolean", "required": False, "default": False, "always_write": True},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
  "plan": {
    "label": "Plan",
    "mode": "folder",
    "folder": "content/plan",
    "filename_mode": "slug",
    "pdf_embed": True,
    "pdf_asset_folder": "pdfs",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "filename_slug", "label": "Filename Slug", "type": "string", "required": False, "store": False},
      {"name": "publishdate", "label": "Publish Date", "type": "datetime", "required": False, "hint": "Example: 2026-04-08T10:30:00-05:00"},
      {"name": "author", "label": "Author", "type": "string", "required": False},
      {"name": "tags", "label": "Tags", "type": "list", "required": False, "hint": "Comma-separated values."},
      {"name": "categories", "label": "Categories", "type": "list", "required": False, "hint": "Comma-separated values."},
      {"name": "weight", "label": "Weight", "type": "number", "required": False},
      {"name": "draft", "label": "Draft", "type": "boolean", "required": False, "default": False, "always_write": True},
      {"name": "pdf_file", "label": "PDF File", "type": "pdf", "required": True, "store": False, "hint": "Select a local PDF file."},
    ],
  },
  "document": {
    "label": "Document",
    "mode": "folder",
    "folder": "content/document",
    "filename_mode": "dated_slug",
    "date_field": "date",
    "pdf_embed": True,
    "pdf_asset_folder": "pdfs",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "filename_slug", "label": "Filename Slug", "type": "string", "required": False, "store": False},
      {"name": "date", "label": "Date", "type": "date", "required": True, "hint": "Example: 2026-04-08"},
      {"name": "draft", "label": "Draft", "type": "boolean", "required": False, "default": False, "always_write": True},
      {"name": "pdf_file", "label": "PDF File", "type": "pdf", "required": True, "store": False, "hint": "Select a local PDF file."},
    ],
  },
  "education": {
    "label": "Education",
    "mode": "folder",
    "folder": "content/education",
    "filename_mode": "slug",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "filename_slug", "label": "Filename Slug", "type": "string", "required": False, "store": False},
      {"name": "publishdate", "label": "Publish Date", "type": "datetime", "required": False, "hint": "Example: 2026-04-08T10:30:00-05:00"},
      {"name": "author", "label": "Author", "type": "string", "required": False},
      {"name": "tags", "label": "Tags", "type": "list", "required": False, "hint": "Comma-separated values."},
      {"name": "categories", "label": "Categories", "type": "list", "required": False, "hint": "Comma-separated values."},
      {"name": "draft", "label": "Draft", "type": "boolean", "required": False, "default": False, "always_write": True},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
  "moove_index": {
    "label": "Let's Moove Page",
    "mode": "fixed",
    "path": "content/moove/_index.md",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "author", "label": "Author", "type": "string", "required": False},
      {"name": "date", "label": "Date", "type": "date", "required": False, "hint": "Example: 2026-04-08"},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
  "about": {
    "label": "About Page",
    "mode": "fixed",
    "path": "content/about.md",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "date", "label": "Date", "type": "date", "required": False, "hint": "Example: 2026-04-08"},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
  "calendar": {
    "label": "Calendar Page",
    "mode": "fixed",
    "path": "content/calendar.md",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "date", "label": "Date", "type": "date", "required": False, "hint": "Example: 2026-04-08"},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
  "contact": {
    "label": "Contact Page",
    "mode": "fixed",
    "path": "content/contact.md",
    "fields": [
      {"name": "title", "label": "Title", "type": "string", "required": True},
      {"name": "date", "label": "Date", "type": "date", "required": False, "hint": "Example: 2026-04-08"},
      {"name": "body", "label": "Body", "type": "markdown", "required": False, "store": False},
    ],
  },
}


def slugify(value):
  text = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower())
  return text.strip("-") or "untitled"


def split_list_value(value):
  if not value:
    return []

  pieces = re.split(r"[,\n]", value)
  return [piece.strip() for piece in pieces if piece.strip()]


def extract_date_prefix(value):
  match = re.search(r"\d{4}-\d{2}-\d{2}", value or "")
  if not match:
    raise ValueError("A date in YYYY-MM-DD format is required to build the filename.")

  return match.group(0)


def resolve_site_root(project_root, site_root_value):
  site_root = Path(site_root_value or "site")
  if not site_root.is_absolute():
    site_root = Path(project_root) / site_root

  return site_root.resolve()


def validate_values(entry_key, values):
  entry = ENTRY_DEFINITIONS[entry_key]
  errors = []

  for field in entry["fields"]:
    if not field.get("required"):
      continue

    raw_value = values.get(field["name"])
    if field["type"] == "boolean":
      continue

    if raw_value is None or str(raw_value).strip() == "":
      errors.append(f"{field['label']} is required.")

  return errors


def build_frontmatter(entry_key, values):
  entry = ENTRY_DEFINITIONS[entry_key]
  frontmatter = {}

  for field in entry["fields"]:
    if field.get("store") is False or field["name"] == "body":
      continue

    raw_value = values.get(field["name"])
    field_type = field["type"]

    if field_type == "boolean":
      value = bool(raw_value)
      if field.get("always_write") or value:
        frontmatter[field["name"]] = value
      continue

    if raw_value is None:
      raw_text = ""
    else:
      raw_text = str(raw_value).strip()

    if raw_text == "":
      continue

    if field_type == "list":
      items = split_list_value(raw_text)
      if items:
        frontmatter[field["name"]] = items
      continue

    if field_type == "number":
      frontmatter[field["name"]] = int(raw_text)
      continue

    frontmatter[field["name"]] = raw_text

  return frontmatter


def build_target_path(project_root, site_root_value, entry_key, values):
  entry = ENTRY_DEFINITIONS[entry_key]
  site_root = resolve_site_root(project_root, site_root_value)
  extension = entry.get("extension", ".md")

  if entry["mode"] == "fixed":
    return site_root / entry["path"]

  title = str(values.get("title") or "").strip()
  requested_slug = str(values.get("filename_slug") or "").strip()
  slug_value = requested_slug or slugify(title)

  if entry["filename_mode"] == "dated_slug":
    date_prefix = extract_date_prefix(values.get(entry["date_field"], ""))
    filename = f"{date_prefix}_{slug_value}{extension}"
  else:
    filename = f"{slug_value}{extension}"

  return site_root / entry["folder"] / filename


def build_pdf_asset_path(project_root, site_root_value, entry_key, values):
  entry = ENTRY_DEFINITIONS[entry_key]
  if not entry.get("pdf_embed"):
    raise ValueError(f"{entry_key} does not support embedded PDF assets.")

  site_root = resolve_site_root(project_root, site_root_value)
  target_path = build_target_path(project_root, site_root_value, entry_key, values)
  pdf_folder = entry.get("pdf_asset_folder", "pdfs")
  return site_root / pdf_folder / f"{target_path.stem}.pdf"


def render_markdown(entry_key, values):
  errors = validate_values(entry_key, values)
  if errors:
    raise ValueError(" ".join(errors))

  frontmatter = build_frontmatter(entry_key, values)
  body = str(values.get("body") or "").rstrip()
  if ENTRY_DEFINITIONS[entry_key].get("pdf_embed"):
    embed_src = str(values.get("pdf_embed_src") or "").strip()
    if embed_src:
      embed_tag = f'<embed width=100% height=1000 src="{embed_src}"></embed>'
      body = f"{body}\n\n{embed_tag}".strip() if body else embed_tag

  yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=False).strip()

  if yaml_text:
    document = f"---\n{yaml_text}\n---"
  else:
    document = "---\n---"

  if body:
    return f"{document}\n\n{body}\n"

  return f"{document}\n"