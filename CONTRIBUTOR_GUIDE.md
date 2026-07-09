# Contributor Guide — PythonAppFoundry

This guide is for developers maintaining or extending the platform code itself. It covers code structure, key patterns, data flow, and common gotchas — the sort of detail you need when fixing bugs or adding features.

## File Inventory

### Entry & Config

| File | Lines | What It Does |
|---|---|---|
| `run.py` | 10 | Imports `create_app()`, reads `APP_PORT`/`APP_DEBUG` from env, calls `app.run()`. |
| `app/__init__.py` | 174 | Flask factory: creates app, inits extensions (db, login, migrate), registers 6 blueprints, defines template filters (`localtime`, `attr`), registers after-request admin bar injector, runs startup logic (create_all, scheduler init, route slug dedup). |
| `app/config.py` | 22 | `Config` class loaded from `.env` via python-dotenv. Only env-based settings live here — AI/SMTP settings are in the `Setting` DB table. |

### Routes

| File | Lines | Blueprint | Prefix | What It Does |
|---|---|---|---|---|
| `app/routes/admin.py` | ~2430 | `admin_bp` | `/__admin` | Full admin CRUD — dashboard, modules, routes, scripts, forms, tasks, triggers, users, groups, data browser, uploads, settings. Also defines `ADMIN_TEMPLATE`, `LIST_TEMPLATE`, `AttrProxy`, `render_admin()`, `list_view()`. |
| `app/routes/dynamic.py` | ~55 | `dynamic_bp` | (none) | Catch-all `/<path:slug>` — looks up slug in `Route` table, checks perms, executes script, fires after_route triggers. |
| `app/routes/auth.py` | ~110 | `auth_bp` | `/__auth` | Setup wizard, login/logout, registration, profile page. |
| `app/routes/api.py` | ~155 | `api_bp` | `/__api` | REST: module list/export/import, file upload, webhook receiver. |
| `app/routes/chat.py` | ~145 | `chat_bp` | `/__admin/chat` | AI Designer chat sessions (new, list, send message, import XML, refine). |
| `app/routes/bpmn.py` | ~120 | `bpmn_bp` | `/__admin/bpmn` | BPMN visual designer (load XML, convert diagram to module via LLM, import). |

### Services

| File | Lines | What It Does |
|---|---|---|
| `app/services/script_runner.py` | ~130 | The sandbox — compiles and `exec`s user scripts with safe builtins, injected globals, stdout capture, timeout via SIGALRM. The `_send_email()` helper lives here. |
| `app/services/scheduler.py` | ~120 | APScheduler `BackgroundScheduler` — registers `ScheduledTask` rows as cron jobs, wraps execution in threads with timeout, logs to `ExecutionLog`. |
| `app/services/triggers.py` | ~62 | Queries enabled `Trigger` rows by event_type + target_table and fires scripts synchronously. Called from `dynamic.py` (after_route) and `api.py` (webhook). |
| `app/services/ai_assistant.py` | ~160 | LLM integration — reads provider settings from `Setting` model, builds system prompt from `AI_GUIDE.md`, dispatches to llama.cpp or OpenAI, extracts XML from response. |
| `app/services/bundle.py` | ~170 | Module XML serialization/deserialization. `export_module()` walks model relationships and builds XML. `import_module()` parses XML, creates/updates module and all children, bumps version, detects dependencies. |
| `app/services/dependencies.py` | ~70 | Scans scripts for `url_for('other_slug.')`, `redirect('/other_slug/')`, and cross-module `script_id=` references. |
| `app/services/file_upload.py` | ~70 | Secure upload — random filename via `secrets.token_hex(12)`, stores in `instance/uploads/`, creates `Upload` record. |
| `app/services/versioning.py` | ~90 | Module version snapshots — exports module to XML, stores as `ModuleVersion` with auto-incremented patch version. Restore via `bundle.import_module()`. Diff via `difflib.unified_diff`. |

### Models

| File | Lines | What It Contains |
|---|---|---|
| `app/models.py` | 332 | 15 model classes + `DynamicModel` factory, `user_groups` association table. |

## Key Code Patterns

### No Template Files — All Inline Strings

There is no `app/templates/` directory. All HTML is rendered via `render_template_string()` (Flask's version of `string.Template` with Jinja2). Three patterns:

1. **`ADMIN_TEMPLATE`** (admin.py line ~13) — The base admin layout: sidebar, top bar, content area. Used via `render_admin()`.
2. **`LIST_TEMPLATE`** (admin.py line ~41) — Generic list view: sortable columns, module filter, CSV export, edit links.
3. **Inline strings** passed directly to `render_admin()` in each route. Example from `admin.py`:
   ```python
   return render_admin('Settings', '''
   <form method="POST">
     <label>Site Name <input name="site_name" value="{{ site_name }}"></label>
     ...
   </form>
   ''', site_name=site_name, ...)
   ```

**Gotcha:** Because templates are Python strings, `{{` / `}}` in CSS or JS inside admin routes must be escaped or avoided. The admin bar injector (`app/__init__.py`) uses `str.replace` on the HTML body — if you change the admin bar structure, make sure the injector still matches.

### `AttrProxy` and `list_view`

`AttrProxy` (admin.py line ~142) wraps ORM model instances for the generic `LIST_TEMPLATE`. It:
- Handles `_module_name` virtual attribute (looks up the related `Module.name`)
- Handles `cron_expression` — appends human-readable description
- Converts `datetime` objects to server-local time (strips tzinfo after `astimezone()`)
- Converts everything else to `str`

`list_view()` (admin.py line ~169) is a generic function that:
1. Queries the model (with optional module filter)
2. Sorts by the requested column
3. Returns CSV or renders `LIST_TEMPLATE`
4. Wraps each row in `AttrProxy`

**Gotcha:** The `_export_csv()` function (admin.py line ~173) reads raw model attributes, not going through `AttrProxy`. So CSV exports show raw UTC datetimes and raw cron expressions.

### `render_admin(title, content_template, **kwargs)`

A two-step render: first renders the content template (inline string) with kwargs, then renders that result into `ADMIN_TEMPLATE`. This means Jinja2 errors can occur in either step, and the error traceback may not clearly indicate which template the problem is in.

### `DynamicModel` Factory

`DynamicModel.get_or_create(name, columns)` generates SQLAlchemy model classes at runtime:

```python
MyTable = DynamicModel.get_or_create('my_table', [
    {'name': 'title', 'type': 'string'},
    {'name': 'count', 'type': 'integer'},
])
```

Internally it:
1. Checks if the table already exists in `db.metadata.tables`
2. If not, constructs a `Table` object with the given columns plus an auto-increment `id` PK
3. Creates the table in the database via `table.create(db.engine, checkfirst=True)`
4. Generates a dynamic model class with a `query` property

**Gotcha:** `DynamicModel` is rebuilt on every call — the table is only created once (SQLite's `IF NOT EXISTS` behavior). But columns added to an existing table's schema after its initial creation are ignored. To add columns later, you'd need raw `ALTER TABLE` SQL.

**Gotcha:** Dynamic tables are not automatically dropped when a module is deleted. The admin UI shows a checkbox "Drop associated database tables?" which does `table.drop(db.engine, checkfirst=True)`.

## admin.py Navigation

At ~2430 lines, `admin.py` is the largest file. It's organized as a flat list of route functions, grouped by entity. Key landmarks:

| Line ~ | Content |
|---|---|
| 1-10 | Imports |
| 13-78 | `ADMIN_TEMPLATE` and `LIST_TEMPLATE` strings |
| 81-100 | `admin_required` / `developer_or_admin_required` decorators |
| 103-112 | `create_auto_version()` helper |
| 116-161 | `_describe_cron()`, `AttrProxy`, `render_admin()`, `list_view()`, `_export_csv()` |
| 195-~395 | Module CRUD (list, new, edit, clone, delete, scan deps, view deps, import XML) |
| ~400-~475 | Module versions (list, create, restore, diff) |
| ~480-~560 | Route CRUD |
| ~565-~710 | Script CRUD (list, new, edit, debug) |
| ~715-~870 | Form CRUD (list, new, edit with live preview) |
| ~1048-~1110 | Scheduled Task CRUD |
| ~1115-~1175 | Trigger CRUD |
| ~1180-~1260 | User CRUD |
| ~1265-~1310 | Group CRUD |
| ~1315-~1650 | Data browser (table list, row CRUD, drop table) |
| ~1655-~1820 | File uploads |
| ~1865-~2100 | Settings (registration, LLM, SMTP, test email, script timeout, log retention) |
| ~2100-~2370 | Dashboard (system info, scheduler status, execution logs, module summary) |

**Gotcha:** The `edit_settings()` route at ~1920 does both display (GET) and save (POST). The SMTP settings are mixed into the same form as LLM settings, site name, registration settings, etc. All are saved in one POST handler. The test email button uses `formaction` to submit to a different endpoint while staying inside the same `<form>` element.

## Request Flow

```
Browser → HTTP request
  │
  ├─ /__auth/*       → auth.py
  ├─ /__admin/*      → admin.py / chat.py / bpmn.py
  ├─ /__api/*        → api.py
  ├─ /uploads/*      → app/__init__.py serve_upload()
  └─ /* (catch-all)  → dynamic.py
                        │
                        ├─ Route lookup in DB
                        ├─ Module enabled check
                        ├─ HTTP method check
                        ├─ Auth check (if route.auth_required)
                        ├─ Group access check (if route.allowed_groups)
                        ├─ execute_script(route.script, route=route)
                        │   ├─ Inject safe globals
                        │   ├─ Compile & exec user script
                        │   ├─ Capture stdout
                        │   └─ Log to ExecutionLog
                        ├─ fire_triggers('after_route', module_slug, context)
                        └─ Return _result or captured output
```

## Service Call Graph

```
admin.py ──> refresh_tasks() ──> scheduler.py
          ─> _send_email()    ──> script_runner.py
          ─> execute_script() ──> script_runner.py

dynamic.py ──> execute_script() ──> script_runner.py
          ──> fire_triggers()  ──> triggers.py ──> execute_script()

api.py ──> fire_webhook() ──> triggers.py ──> execute_script()
      ──> bundle.export_module() / import_module()
      ──> file_upload.upload_file()

scheduler.py ──> execute_script() ──> script_runner.py
            ──> register_task() ──> APScheduler

chat.py ──> ai_assistant.chat_completion()

bpmn.py ──> ai_assistant.chat_completion()
        ──> bundle.import_module()
```

## Common Gotchas & Bug Patterns

### 1. Flask Debug Reloader Double-Init

With `APP_DEBUG=true`, Flask's reloader spawns TWO processes (a file watcher parent + the actual app child). Both call `create_app()`, so `init_scheduler()` would run twice, creating two `BackgroundScheduler` instances both firing the same jobs. The guard `if _scheduler is not None: return` at the top of `init_scheduler()` prevents this — the module-level `_scheduler` global survives across the fork.

### 2. `refresh_tasks()` Must Be Called After Task CRUD

The `ScheduledTask` model stores task definitions in the DB, but APScheduler runs from in-memory job objects. After creating, editing, or deleting a task, you must call `refresh_tasks()` (scheduler.py:113) which removes all APS jobs and re-registers from the DB. Missing this call is the #1 cause of "scheduled task never runs" bugs.

### 3. Timezone Assumptions

- All datetimes in the database are stored as **naive UTC** (no tzinfo, but semantically UTC)
- `datetime.now(timezone.utc)` produces an aware datetime, but SQLite drops the tzinfo on read
- The `localtime` Jinja filter (`app/__init__.py:47`) handles both cases: if aware, calls `astimezone()`; if naive, assumes UTC and converts
- `BackgroundScheduler()` uses the **system local timezone** (not UTC) — cron expressions are evaluated in server local time
- The `AttrProxy.__getattr__` datetime formatting mirrors the `localtime` filter logic

### 4. `_send_email` Is In `script_runner.py`, Not A Service

The `_send_email()` function is defined in `script_runner.py` (not in its own service file) because it's injected into the script sandbox as `send_email`. It's also called directly from `admin.py` for the test email feature. The function reads SMTP settings from the `Setting` model on every call (not cached).

### 5. Template Rendering vs. String Building

The admin panel uses Jinja2 `render_template_string()` for all HTML. If you need to add dynamic HTML to admin pages, either:
- Pass it as a template variable and use `{{ variable }}` in the template string
- Or build the HTML as a Python string and insert it with `|safe` filter

**No raw HTML interpolation in template strings** — Jinja2 auto-escapes `{{ }}` output.

### 6. Script Auto-Wrapping

In `script_runner.py`, if a script uses `return` at the top level, Python's `compile()` raises `SyntaxError('return outside function')`. The runner detects this error, wraps the source in `def _script(): return (...)`, compiles again, and calls `_script()`. This means:
- The `_result` variable convention is a fallback — `return` works directly in most cases
- If both `return` and `_result` are used, `return` wins

### 7. APScheduler Job IDs

Job IDs are `'task_' + str(task.id)`. The `replace_existing=True` flag means re-registering a task with the same ID replaces the old job. This is critical for `refresh_tasks()` to work correctly.

### 8. Thread Safety

`run_task_wrapper()` in `scheduler.py` runs in APScheduler's background thread. It creates a new Flask app context via `with app.app_context():` for DB access. However, the actual script execution happens in yet another daemon thread (`threading.Thread(target=_run_script_in_app_context, ...)`). The `_app` module-level global must be set before any thread uses it.

## Database Schema Notes

- **16 platform tables** are created by `db.create_all()` on startup
- **Dynamic tables** are created by `DynamicModel.get_or_create()` — they're regular SQLAlchemy tables but not registered in `db.metadata` until first access
- **Migration strategy:** New columns on existing tables use raw `ALTER TABLE` SQL in `create_app()`. See the `routes.allowed_groups` migration at `app/__init__.py:150-155` as the pattern:
  ```python
  inspector = sa_inspect(db.engine)
  cols = {c['name'] for c in inspector.get_columns('routes')}
  if 'allowed_groups' not in cols:
      db.session.execute(text('ALTER TABLE routes ADD COLUMN ...'))
  ```
- **No Alembic migrations are set up** despite `flask-migrate` being installed. The `migrations/` directory exists but has no version scripts.

## Adding a DB Setting

To add a new platform-wide setting (like a new toggle or text config):

1. In `admin.py` `edit_settings()`, add the input to both the save block (reading `request.form`) and the display block (reading `Setting.get(...)`)
2. Add the HTML input in the settings template string
3. Pass the value in the `render_admin()` kwargs

The `Setting` model's `get()` and `set()` methods handle persistence automatically — no model changes needed.

## Adding a New Entity Type

If you need a new first-class entity (like `ScheduledTask` or `Trigger`):

1. Add the model class to `app/models.py` with appropriate FKs and relationships
2. Add CRUD routes to `app/routes/admin.py` — use `list_view()` for the list page, create inline templates for new/edit forms
3. Add to `bundle.py` if it should be importable/exportable as part of a module
4. Add to `ADMIN_TEMPLATE` sidebar links if it needs a top-level nav entry

## Security Boundaries

| Layer | Protection | Location |
|---|---|---|
| Route auth | `@admin_required`, `@developer_or_admin_required`, `@login_required` | admin.py, auth.py, api.py |
| Dynamic route auth | `Route.auth_required` flag + `Route.allowed_groups` | dynamic.py |
| Script sandbox | Safe builtins whitelist, no `os`/`subprocess`/`eval`/`open` | script_runner.py |
| Script timeout | SIGALRM (30s default, configurable) | script_runner.py |
| File upload | Random filename, stored outside web root | file_upload.py |
| Password storage | bcrypt hashing | auth.py / models.py |
| Webhook triggers | Public endpoint but script scope is limited | api.py / triggers.py |
