# PythonAppFoundry

> **Warning:** This is a work in progress. Core functionality is up and working but we are still working out bugs and the LLM documentation.

This is a restart of a 15-year-old project to create an "embedded database" web app platform for Python and HTML. The intent is that all scripts, HTML, scheduled tasks, processes — everything — goes into a database, and the platform reads out what it needs on demand to run the application. Not a unique concept now, but 15+ years ago it was rather rare.

For the most part the database is fed by XML imports. The original plan was to create graphical designer tools that would export (and import for edits) XML to be sent to the DB to run. But this is 2026 — so instead of GUI design tools, LLMs are used to create and edit the XML for you. More GUI/code builder tools may come later.

## Features

- **Module system** — Think of modules as applications. Each module is a self-contained bundle of routes, scripts, forms, scheduled tasks, triggers, and optional BPMN workflow data. Multiple modules run side-by-side, each with their own URL endpoints.
- **AI Module Generation** — An embedded chat interface (AI Designer) generates complete modules from natural language prompts. The actual LLM is external via API calls — supports llama.cpp and OpenAI endpoints. Your results will vary greatly depending on how good your LLM is at both coding and following directions.
- **BPMN Workflow Designer** — A visual drag-and-drop process designer (powered by bpmn-js) for more complex workflows. You still describe your intent and data needs, but the structured diagram makes it easier to manage modules with moving parts. Convert diagrams to runnable modules with one click.
- **Dynamic Tables** — Scripts create and query database tables on the fly via `DynamicModel.get_or_create()` — no migrations, no schema changes.
- **Sandboxed Script Runner** — Python scripts execute in a restricted environment with safe builtins and documented helpers (`send_email`, `render_form`, etc.).
- **Role-Based Access** — Three roles: **Admin** (full system control), **Developer** (create/manage modules, routes, scripts, forms — can't manage users or settings), and **User** (can log in to auth-protected routes only).
- **Full Admin Panel** — CRUD for modules, routes, scripts, forms, tasks, triggers, users, groups, data tables, settings, and file uploads. All list views include column sorting, module filtering, and CSV export.
- **Bundle Import/Export** — Modules export as XML for backup or transfer between instances. Import XML to create or update modules.
- **SMTP Email** — Platform-wide SMTP settings; `send_email()` is available in all scripts.
- **CSV Export** — Every list view and data table supports CSV download.
- **Module Versioning** — Automatic version snapshots on every import (AI Designer, BPMN) and manual version creation. Rollback to any previous state with one click, diff between versions, and add comments to track changes over time.
- **Module Dependency Tracking** — Automatically detects when modules reference other modules' routes or scripts. Shows dependency warnings before deletion to prevent silent breakage. Manual "Scan" button to re-detect dependencies.
- **System Dashboard** — Health overview at `/__admin/dashboard` showing module/route/script counts, system info (Python/Flask versions, uptime), recent execution logs with View Error/Output buttons for full details, database table sizes, and per-module summaries. All script executions are automatically logged.
- **Webhook Support** — External services can trigger scripts via HTTP POST to `/__api/webhook/{slug}`. Configure webhooks as triggers with `event_type='webhook'`. Scripts receive the payload data for processing.
- **Group-Based Route Access** — Restrict routes to specific user groups. Users must be logged in and belong to at least one allowed group to access the route.
- **Script Debug Mode** — Run scripts directly from the editor with "Run Debug" to see source code, line numbers, output, and execution timing.
- **Module Cloning** — One-click duplicate of any module from the admin list to use as a starting point.
- **Cron Validation** — Invalid cron expressions are caught on save, preventing silent task failures.
- **Log Retention** — Auto-cleanup of old execution logs configurable from Settings.
- **Email Test Button** — Verify SMTP configuration with a single click from the Settings page.
- **Demo Modules** — Import `demos/guestbook.xml` for a working example of forms, DynamicModel data collection, and rendered output at the site root. Import `demos/pixel_art_gallery.xml` for a visual showcase of retro pixel art with a styled grid layout.

## Quick Start

```bash
git clone https://github.com/Nurb4000/PythonAppFoundry && cd PythonAppFoundry
pip install -r requirements.txt
cp .env.example .env 2>/dev/null || touch .env   # defaults work for SQLite
python3 run.py
```

Visit `http://localhost:5000/` — you'll be redirected to the Setup page to create the initial admin account.

## Requirements

- Python 3.10+
- SQLite (default) or PostgreSQL (via SQLAlchemy)

It starts with SQLite for development, but uses SQLAlchemy so you can expand to larger database engines if needed.

## Configuration

| Setting | Location | Description |
|---------|----------|-------------|
| `SECRET_KEY`, `DATABASE_URL` | `.env` | Flask secret key and database connection |
| LLM provider, endpoint, API key, model | Admin → Settings | AI provider (llama.cpp or OpenAI), configured via GUI |
| SMTP host, port, credentials | Admin → Settings | Email sending for scripts |
| Registration controls | Admin → Settings | Disable registration, require admin approval |

## Guides

Two guides are included in the repo:

- **`ADMIN_GUIDE.md`** — How to get started working with the system: first run, admin bar, workflow instructions, LLM/AI configuration, SMTP setup.
- **`AI_GUIDE.md`** — A guide for the LLM itself. It explains the structure of the platform, the XML bundle format, available helpers and builtins, and how to generate proper code. This is very much a moving target — as we all know how stubborn LLMs can be.

## Architecture

```
run.py → create_app() (Flask factory)
  ├── app/routes/auth.py     — Setup, login/logout, registration
  ├── app/routes/admin.py    — Admin CRUD for all entity types
  ├── app/routes/dynamic.py  — Catch-all route handler (serves user modules)
  ├── app/routes/chat.py     — AI Designer chat sessions
  ├── app/routes/bpmn.py     — BPMN visual designer
  └── app/routes/api.py      — REST API (export, import, list modules, webhooks)
  ├── app/services/script_runner.py  — Sandboxed Python execution
  ├── app/services/ai_assistant.py   — LLM integration
  ├── app/services/bundle.py         — Module XML import/export
  ├── app/services/scheduler.py      — APScheduler cron task runner
  ├── app/services/triggers.py       — Event and webhook trigger firing
  ├── app/services/versioning.py     — Module version snapshots, rollback, diff
  ├── app/services/dependencies.py   — Cross-module dependency detection
  └── app/services/file_upload.py    — Secure file upload handling
```

### Key design decisions

- **Everything in the database** — Routes, scripts, forms, tasks, triggers all live in DB tables, not on the filesystem. The dynamic route handler catches undefined slugs and looks them up at runtime.
- **Scripts are auto-wrapped** — `return` works at the top level of any script. The `_result` variable provides a fallback.
- **Dynamic tables are flat** — No foreign key relationships. Scripts use explicit queries and joins.
- **Module → table lifecycle is decoupled** — Deleting a module doesn't automatically drop its DynamicModel tables (opt-in via checkbox).
- **AI settings in the DB** — All LLM and SMTP configuration is managed through the admin GUI, not environment variables.

## Models

| Model | Purpose |
|-------|---------|
| User | Authentication, roles (admin/developer/user), group membership |
| Group | Role-based user groups for access control |
| Module | Container bundling routes, scripts, forms, tasks, triggers; stores BPMN source data |
| Route | URL slug → script + form mapping with method and auth constraints |
| Script | Python source code executed by routes, tasks, or triggers |
| Form | JSON schema defining form fields rendered by `render_form()` |
| ScheduledTask | Cron-triggered script execution via APScheduler |
| Trigger | Event-based hooks (on_insert, after_route, webhook) |
| DynamicModel | Factory that creates/retrieves SQLAlchemy table models at runtime |
| Setting | Key-value store for platform configuration |
| Upload | File upload metadata |
| ChatSession / ChatMessage | AI Designer conversation history |

## Scripting

Scripts have these variables available without imports:

```
request, session, db, current_user
redirect, url_for, flash, render, jsonify
send_email(to, subject, body, html=False)
render_form(action, method, submit_label, fields=form_fields)
form_fields                    # list of parsed field dicts (when route has a form)
DynamicModel                  # factory for dynamic database tables
datetime, timezone            # from datetime module
```

Builtins available: `int`, `str`, `list`, `dict`, `len`, `range`, `enumerate`, `zip`, `sorted`, `min`, `max`, `sum`, `any`, `all`, `isinstance`, `type`, `hasattr`, `getattr`, `setattr`, `dir`, `print`, common exception types. The sandbox deliberately excludes `os`, `subprocess`, `eval`, and `open` to prevent system access. Imports work normally (`import` / `from ... import`).

## Dependencies

- Flask 3.0, Flask-SQLAlchemy, Flask-Login, Flask-Migrate
- bcrypt, APScheduler, python-slugify, python-dotenv

## License

MIT — see [LICENSE](LICENSE).

Copyright 2026 IDS


## Some screenhots to give you an idea of its layout

<img width="1011" height="694" alt="Build" src="https://github.com/user-attachments/assets/58934cf2-30c5-40f4-8d84-41939f957294" />
<img width="1387" height="532" alt="Edit Module" src="https://github.com/user-attachments/assets/970d5ff1-648b-4a38-8c32-e1e2d77f95c8" />
<img width="1379" height="365" alt="Route List" src="https://github.com/user-attachments/assets/24153de4-3f21-4271-adf1-8565636efded" />
<img width="1399" height="564" alt="Database Tables" src="https://github.com/user-attachments/assets/034b3fef-7f77-49dd-840d-9e49120a82dc" />
<img width="1392" height="581" alt="Table Edit" src="https://github.com/user-attachments/assets/08b1091b-1849-4416-82c7-11dcd93d662f" />
<img width="1386" height="676" alt="Manual Script Edit" src="https://github.com/user-attachments/assets/d55cf9d3-edde-4a23-a84b-6b37892c0775" />
<img width="1392" height="692" alt="BPMN" src="https://github.com/user-attachments/assets/3642e844-a4aa-4aa8-a985-52954e670cfc" />
