# npm-HAT-CMS

This repository now follows the same core pattern as `../Wieting-Website-CMS`:

- the CMS is a local application,
- the Hugo site is edited on disk,
- the built site is static output,
- deployment is handled by AWS Amplify from repository source.

Netlify and the browser-based Decap admin have been removed from this project.

## What Changed

The old approach depended on a hosted CMS UI and GitHub authentication flow. That made deployment and content editing tightly coupled to a platform-specific setup.

The new approach is local-first:

- `main.py` is a local Flet CMS app
- `cms_core.py` handles frontmatter generation and file naming
- `run.sh` creates a virtual environment and launches the CMS
- Hugo content is written directly into `site/content`
- `npm run build` still produces the deployable static site in `dist/`
- AWS Amplify can rebuild and publish this repository directly from source on each push

## Prerequisites

- Node.js 12+
- Python 3.9+
- npm dependencies installed with `npm install`

## Install

```bash
npm install
```

The Python CMS dependencies are installed automatically the first time you run the launcher.

## Run The CMS

```bash
./run.sh
```

The app opens a local content editor that writes markdown files directly into the Hugo site.

- The Markdown Preview panel has been removed.
- For Event entries, the `Body` editor is shown in the right-hand column.

## Build The Site

```bash
npm run build
```

The built site is written to `dist/`. In production, AWS Amplify should generate that output from repository source on each push.

Hugo-only commands also target the same folder:

```bash
npm run build:hugo
npm run start:hugo
```

Both now write to `dist/` (local repository), which matches the VS Code Local Site path.

## Default Workflow

1. Run `./run.sh`.
2. Create or update content in the local CMS app.
3. Save entries into `site/content`.
4. Run `npm run build`.
5. Commit and push your changes.
6. Let AWS Amplify rebuild and publish the site.

## AWS Deployment

This repository is configured for source-driven AWS Amplify deployment.

- Amplify config: [amplify.yml](/Users/mark/GitHub/npm-HAT-CMS/amplify.yml)
- Deployment flow: [DEPLOYMENT_FLOW.md](/Users/mark/GitHub/npm-HAT-CMS/DEPLOYMENT_FLOW.md)
- Setup guide: [DEPLOYMENT.md](/Users/mark/GitHub/npm-HAT-CMS/DEPLOYMENT.md)

Amplify should run `npm ci`, then `npm run build`, then publish `dist/`.

## Alternate Site Root

The CMS defaults to this repository's local Hugo site at `./site`.

If you still want to write directly into another Hugo repository, such as `../npm-HAT`, change the `Hugo Site Root` field in the app. The CMS will then write content into that target site instead.

That lets you use this repository as a local editor even if the real site source remains elsewhere.

## Supported Content Types

The local CMS currently has full UI support for:

- **Event (Markdown)** - dated folder-based entries with support for publish date, location, expiry date, and markdown body
- **Document (PDF)** - dated folder-based entries with embedded PDF support

Other content types (Posts, Plans, Education, Let's Moove page, About page, Calendar page, Contact page) are defined in `cms_core.py` but are disabled in the CMS UI pending full implementation.

### Content Type Details

**Event (Markdown)**
- Fields: Title, Publish Date, Event Date, Start Time, Location, Event Details (PDF), Expiry Date, Body, Filename Slug, Draft
- Filenames: auto-generated as `YYYY-MM-DD_slug.md` with date prefix
- Output: `site/content/event/`
- Optional Event Details PDF output: `site/static/pdfs/<event-stem>-details.pdf`
- Event frontmatter key for embedded details: `eventDetailsPdf`

**Document (PDF)**
- Fields: Title, Date, PDF File, Filename Slug, Draft
- Filenames: auto-generated as `YYYY-MM-DD_slug.md` and corresponding `YYYY-MM-DD_slug.pdf`
- Output: `site/content/document/` (markdown) and `site/static/pdfs/` (PDF)
- The date is automatically prepended to the filename, so titles should not include the date.
- PDFs are embedded in the markdown via `<embed>` tag

## Files

- `main.py` - Flet desktop-style CMS application
- `cms_core.py` - shared content definitions and markdown generation logic
- `run.sh` - local launcher
- `python-requirements.txt` - Python dependencies for the CMS app
- `site/` - Hugo site source
- `site/static/pdfs/` - PDF files for document embedding
- `site/static/webfonts/` - Font Awesome webfonts
- `dist/` - generated static output after build and the artifact Amplify publishes

## Features

### Date and Time Pickers

Event and Document entries with date/time fields use native Flet date and time picker controls:
- Date fields open a `DatePicker` dialog with calendar UI
- DateTime fields provide both date and time picker buttons
- Time fields open a `TimePicker` dialog
- Pickers are shared as instance variables and added to the page overlay for efficiency

### PDF Embedding

Document entries support embedded PDF viewing:
- Select a local PDF file via the file picker
- The PDF is copied to `site/static/pdfs/` with automatic naming
- Markdown content embeds the PDF via `<embed>` tag pointing to the relative path
- On build, PDFs are included in `dist/pdfs/` for serving

Event entries also support optional embedded PDF details:
- Select `Event Details (PDF)` in the Event form
- The PDF is copied to `site/static/pdfs/<event-stem>-details.pdf`
- Event frontmatter gets `eventDetailsPdf: /pdfs/<event-stem>-details.pdf`
- Event single pages render an embedded "Event Details" section when present

### Google Calendar Sync (Events)

Event saves can now create a Google Calendar event automatically.

- Sync target: the calendar currently embedded in `site/content/calendar.md` (auto-detected)
- Event status in Google Calendar: `confirmed`
- If `startTime` is provided, a timed event is created
- If no start time is provided, an all-day event is created
- Timed events default to a 1-hour duration when no end time is provided

Create credentials (API key is not enough for event creation):

1. Open Google Cloud Console and select/create a project.
2. Enable the Google Calendar API.
3. Create a Service Account and download its JSON key.
4. Share your Google Calendar with the service account email address and grant “Make changes to events”.
5. Place the JSON file at the project root as `google-service-account.json` (or set a custom path in `.env`).

Environment variables are read from `.env`:

```env
GOOGLE_CALENDAR_SYNC_ENABLED=1
GOOGLE_CALENDAR_TIMEZONE=America/Chicago
GOOGLE_SERVICE_ACCOUNT_FILE=google-service-account.json
# Optional override:
# GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
```

### Font Awesome Icons

The site includes Font Awesome 5.13.0 webfonts:
- Webfont files: `site/static/webfonts/fa-*.{eot,ttf,woff,woff2}`
- CSS: `site/assets/css/fontawesome-free-5.13.0-web-all.min.css`
- Icons can be used in layouts and content via `<i class="fas fa-icon-name">` markup

## Test

```bash
python -m unittest test_cms_core.py
```

## Notes

- The app is intentionally local and file-based. There is no hosted auth flow.
- `npm run build` remains the canonical local verification step for the deployable site output.
- In production, AWS Amplify should rebuild from source instead of consuming files manually uploaded from a local machine.
- If you point the CMS at a different site root, that affects where content is written, not how this repository's own `npm run build` behaves.
- If Local Site opens a blank page, rebuild with `npm run build:hugo` and refresh the localhost tab.