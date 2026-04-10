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

The local CMS currently supports these content targets:

- Events
- Posts
- Plans
- Documents
- Education
- Let's Moove page
- About page
- Calendar page
- Contact page

Folder-based content types generate filenames automatically from title and date data. Fixed pages write directly to their known markdown file path.

## Files

- `main.py` - Flet desktop-style CMS application
- `cms_core.py` - shared content definitions and markdown generation logic
- `run.sh` - local launcher
- `python-requirements.txt` - Python dependencies for the CMS app
- `site/` - Hugo site source
- `dist/` - generated static output after build and the artifact Amplify publishes

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