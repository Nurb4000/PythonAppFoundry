# Admin Guide

## First Run

1. Start the app: `python3 run.py`
2. Visit `http://localhost:5000/` — you'll be redirected to the **Setup** page
3. Create the initial admin account (username + password)
4. You're now logged in as admin with the dark admin bar at the top

## Admin Bar

The dark bar at the top of every page (when logged in as admin) links to all admin sections:

| Link | Path | Purpose |
|------|------|---------|
| Modules | `/__admin/modules` | Manage AI-generated modules (view, edit, export, delete) |
| Routes | `/__admin/routes` | URL routes mapped to scripts and forms |
| Scripts | `/__admin/scripts` | Python scripts executed by routes |
| Forms | `/__admin/forms` | Form field definitions (JSON schema) |
| Tasks | `/__admin/tasks` | Scheduled cron tasks |
| Triggers | `/__admin/triggers` | Event-based triggers (on_insert, after_route, etc.) |
| Users | `/__admin/users` | Manage user accounts |
| Groups | `/__admin/groups` | Manage user groups for route access control |
| Data | `/__admin/data` | Browse and edit any database table |
| Queries | `/__admin/queries` | Saved SQL queries with charting, scheduling, and email reports |
| Credentials | `/__admin/credentials` | Encrypted API keys, tokens, and secrets (module-scoped) |
| Incoming | `/__admin/incoming-emails` | Emails received via IMAP polling |
| Packages | `/__admin/packages` | Manage Python packages (install, list, uninstall) |
| Uploads | `/__admin/uploads` | Upload files for use in pages |
| AI Designer | `/__admin/chat` | Chat interface to generate modules via AI |
| BPMN Designer | `/__admin/bpmn` | Visual BPMN workflow designer with AI module conversion |
| Integrations | `/__admin/integration-health` | Script/task execution health, errors, and latency |
| Settings | `/__admin/settings` | Registration, LLM, SMTP, IMAP, and script controls |
| Dashboard | `/__admin/dashboard` | System health overview, execution logs, and scheduler status |
| Backups | `/__admin/backups` | Database backup/restore management |
| Marketplace | `/__admin/marketplace` | Browse and install modules from the marketplace |

## Getting Started

### Workflow

1. **Generate a module** via AI Designer (`/__admin/chat`) — describe what you want
2. **Review the XML** that the AI returns, then click **Import Module**
3. The module, its routes, scripts, forms, tasks, and triggers are all created in the DB
4. Visit the route on your site to test it
5. **Refine** by using the "Refine in AI" button on the module edit page, or ask the AI to modify it

### AI Designer Tips

- Be specific about what tables, fields, and pages you need
- Describe the form fields you want (name, email, message, etc.)
- Mention authentication requirements (e.g., "auth required for admin pages")
- If the AI produces bad XML, tell it what's wrong and ask it to regenerate
- The XML preview lets you inspect before importing

### BPMN Designer Workflow

1. Open **BPMN Designer** (`/__admin/bpmn`) — a visual drag-and-drop workflow editor
2. **Design your process** using the palette (tasks, gateways, events, sequence flows)
   - Drag tools from the palette onto the canvas (double-click then drop if drag alone doesn't respond)
   - Connect elements by dragging from the green flow node on a shape to another shape
3. **Describe the workflow** in the sidebar — tell the LLM what each step should do, what data to collect, what auth to require, etc.
   - The description does NOT generate the BPMN diagram; you design that manually
   - The description tells the LLM what forms, tables, auth rules, and page content to generate
   - Example: _"A request approval workflow with a Request table (title, description, status), a submit form with title+description, an approve form with a comment field, and auth_required for all pages"_
4. Click **Convert to Module** — sends the BPMN diagram + description to the LLM
5. Click **Import Module** — the module is installed and you're taken to the edit page
6. Optionally **load existing BPMN files** (`.bpmn` XML) to convert processes designed externally (e.g., in bpmn.io, Camunda Modeler)

**Example workflow:** Click "Load Example" to load a request approval process (Submit → Approve/Reject) to test with.

Uses the same LLM settings configured in **Admin → Settings**. No additional setup needed.

## Admin Sections

### Modules
List of all imported modules. Each module is a self-contained bundle with routes, scripts, forms, etc.

- **Edit** — change name, slug, description, version, author, toggle enabled
- **Export XML** — download the module as XML (backup or share)
- **Refine in AI** — opens a new AI chat session pre-loaded with the module's XML
- **Scan** — scan the module's scripts for references to other modules and update dependency tracking
- **Delete** — removes the entire module and all its components
- **Deps column** — shows how many other modules reference this one (red number if > 0)

#### Module Dependencies

Modules can reference other modules' routes/scripts by slug. The system tracks these dependencies to prevent silent breakage:

- **Auto-detection**: When you import a module via AI Designer, BPMN, or XML upload, the system automatically scans scripts for references to other modules
- **Manual scan**: Click "Scan" in the Modules list to re-scan a module's dependencies
- **Delete protection**: If you try to delete a module that others depend on, you'll see a warning page listing all dependent modules before deletion is allowed
- **Dependency types**: route_reference (URL slug), script_reference (script ID)

This prevents the common issue of deleting a module and having other modules silently break because they reference deleted routes or scripts.

### Routes
URLs that the site responds to. Each route points to a script and optionally a form.

- Methods: GET, POST, PUT, DELETE, PATCH (comma-separated)
- Auth required: if checked, users must log in to access
- Form: optional form associated with the route (form fields auto-injected into scripts via `render_form()`)

### Scripts
Python code executed when a route is visited. Scripts run in a sandboxed environment with these variables available:

- `request` — Flask request object
- `session` — database session (alias for `db.session`)
- `db` — SQLAlchemy database instance
- `current_user` — logged-in user (or anonymous)
- `redirect()`, `url_for()`, `flash()`, `render()` — Flask helpers
- `jsonify()` — return JSON responses
- `send_email()` — send emails via configured SMTP (usage: `send_email(to, subject, body, html=False)`)
- `route` — the current Route object
- `form_fields` — list of form field dicts (if route has a form)
- `render_form()` — renders form HTML (if route has a form)

**Integration helpers:**
- `get_credential('name')` — retrieves a module-scoped, encrypted credential (API key, token, password) from the Credentials store. Only credentials belonging to the script's own module are accessible. Never hardcode secrets in scripts.
- `call_api(method, url, headers=None, json=None, data=None, timeout=30, retries=3, backoff=2)` — HTTP client with automatic retry on server errors (5xx) and network failures. Returns `{status_code, headers, body, elapsed_ms, error?}`. Auto-parses JSON responses.

**Script result** — end your script with either:
- `return redirect(...)`, `return render(...)`, `return jsonify(...)`
- Assigning `_result = <value>`

### Forms
JSON-based form field definitions. Each field has:
- `name` — field name (matches `request.form` key)
- `type` — text, email, password, number, textarea, select, checkbox, date, file
- `label` — display label
- `required` — true/false
- `placeholder` — placeholder text
- `options` — comma-separated (for select type)

The edit page has a **split-pane editor** with live preview:
- **Left pane**: JSON schema textarea with monospace font
- **Right pane**: Real-time rendered form that updates as you type (300ms debounce)
- Errors in JSON are shown immediately in the preview pane
- The **Full Preview Page** link opens the standalone preview with the same rendering logic

Field types supported: text, email, password, number, textarea, select, checkbox, date, file.

### Data Browser
Browse and edit any database table directly from the admin UI.

- Lists all tables with row counts, column types, and **owning module** (for dynamic tables created by modules)
- Module column is populated automatically by the `dynamic_table_registry` — no manual setup needed
- Filter tables by owning module using the dropdown
- Paginated row browsing (50 per page)
- Add new rows, edit existing rows, delete rows
- Input types auto-detect based on column type (text, number, boolean, datetime)
- Password columns are hidden for security

### Uploads (File Manager)
Manage files (images, PDFs, documents, etc.) for use in your pages.

**Location:** `/__admin/uploads`

**Features:**
- Drag-and-drop or click-to-browse upload form at the top
- Search files by name
- Filter by type: All Types, Images, Documents, Videos, Audio
- Preview thumbnails for images
- File type icons (📄 PDF, 🎥 Video, 🎵 Audio, 📎 Other)
- View, Download, and Delete actions per file
- Total file count and size summary

**Usage:**
1. Upload files via the admin UI or user-facing forms
2. Files are stored in `instance/uploads/` with random filenames for security
3. Accessible at `/uploads/<filename>` from any page
4. Use in HTML: `<img src="/uploads/photo.jpg">` or `<a href="/uploads/report.pdf">`

**User Form Integration:**
Forms can include file upload components using the built-in JavaScript component:
- Include `file-upload.js` and `file-upload.css` from `/static/`
- Add a div with `data-file-upload` attribute for drag-and-drop functionality
- Files are uploaded via POST to `/api/upload` (requires login)
- Returns JSON with file URL, size, and metadata

**API Endpoints:**
- `POST /api/upload` — Upload a file (returns JSON with file details)
- `GET /api/uploads` — List all uploads with pagination

### Users
Manage user accounts. Three roles with increasing permissions:

| Role | Access |
|------|--------|
| **user** | Can log in to auth-protected routes. Has a profile page. Sees a compact dark bar with Profile, View Site, and Logout. |
| **developer** | Can manage modules, routes, scripts, forms, uploads, and use the AI Designer. Cannot manage users, tasks, triggers, data browsing, or settings. Sees a dark bar with the developer subset of links. |
| **admin** | Full access to all admin features including user management, tasks, triggers, data browser, and settings. Sees the full admin bar. |

Status per user:
- **Active** — account can log in
- **Disabled** — account cannot log in (admin can re-enable)
- **Pending** — registered but awaiting admin approval

Admins can approve, disable, or re-enable users directly from the users list.

### Tasks
Scheduled cron tasks. Configuration:
- `schedule` — 5-field cron expression (`minute hour day month day_of_week`)
- Example: `0 3 * * *` runs daily at 3:00 AM

### Triggers
Event-based automation. Events:
- `on_insert` — fires when a row is inserted into a table
- `on_update` — fires when a row is updated
- `on_delete` — fires when a row is deleted
- `after_route` — fires after a route script executes
- `webhook` — fires when an external service POSTs to a webhook URL

### Webhooks
External services can trigger scripts via HTTP POST requests. Webhooks are configured as triggers with `event_type='webhook'`.

**Setting up a webhook:**

1. Go to **Triggers** (`/__admin/triggers`) → **New Trigger**
2. Configure:
   - **Event Type**: `webhook`
   - **Target Table**: A unique slug (e.g., `github-push`, `stripe-payment`)
   - **Script**: The script to execute when the webhook is called
3. Save the trigger

**Webhook URL format:**
```
POST /__api/webhook/{webhook-slug}
```

**Example — GitHub push webhook:**

1. Create a trigger with slug `github-push`
2. Script receives:
   - `webhook_slug` — the slug used in the URL
   - `webhook_payload` — JSON data from the POST body
3. Test with curl:
```bash
curl -X POST http://localhost:5000/__api/webhook/github-push \
  -H "Content-Type: application/json" \
  -d '{"action": "push", "repository": {"name": "my-repo"}, "sender": {"login": "user"}}'
```

**Security notes:**
- Webhooks are public endpoints (no authentication)
- Security is via obscurity — use unique, unpredictable slugs
- All webhook executions are logged to the dashboard
- Validate and sanitize payload data in your scripts

**Future: Webhook authentication:**
A planned enhancement will add an optional `auth_token` field to triggers. When set, the webhook endpoint will require `Authorization: Bearer <token>` in the request header. Triggers without a token remain public. This will enable secure cross-instance integration — one instance can call another's webhook with a shared secret, while still allowing public webhooks for services that don't support custom headers.

### Dashboard
System health overview at `/__admin/dashboard`. Shows:
- **Summary cards** — counts of modules, routes, scripts, forms, tasks, triggers, users, and uploads
- **System info** — Python/Flask versions, app uptime, scheduler status with running jobs and next run times
- **Recent executions** — last 20 script executions with source type (route/task/trigger/webhook), name, duration, status. Click **View Error** (red) or **View Output** (green) buttons to see full error messages or stdout in a modal popup
- **Database tables** — row counts for all tables
- **Module summary** — grid showing route/script/form/task/trigger counts per module

All executions are automatically logged. The dashboard is the quickest way to see if scheduled tasks ran successfully or if any routes are failing.

### Version History

Every module has a version history that tracks changes over time. Versions are stored as complete XML snapshots of the module state.

**How versioning works:**

1. **Manual changes** — Edits to forms, scripts, tasks, etc. are saved immediately but NOT versioned until you explicitly create a version
2. **Create version manually** — Click "Versions" on the module edit page, then "Create Version" to snapshot the current state with a comment
3. **AI Designer import** — When you use "Refine with LLM" and import changes, a new version is created automatically (you can add a comment in the text field before importing)
4. **BPMN import** — Same as AI Designer — imports create versions automatically

**Version workflow:**

```
Current state → [Manual edits] → Current state (unsaved to version history)
                         ↓
                  [Create Version] → Snapshot saved as v1.0.1
                         ↓
                    New changes tracked separately
```

**Why this matters:**

- Versions let you **rollback** to any previous state if something breaks
- Each version includes a **comment** explaining what changed
- You can **diff** between versions to see exactly what changed
- The "current" module state is always editable — versions are read-only snapshots

**Accessing version history:**

1. Go to **Modules** → click **Edit** on any module
2. Click the **Versions** link in the top navigation
3. View all versions with timestamps, comments, and version numbers
4. Click **Restore** to rollback to any version (creates a new current state)
5. Click **Diff** to compare two versions side-by-side

## LLM / AI Configuration

LLM settings are managed via **Admin → Settings** in the GUI. No server access needed.

| Key | Default | Description |
|-----|---------|-------------|
| Provider | `llamacpp` | `llamacpp` (local) or `openai` (OpenAI-compatible API) |
| API Endpoint URL | `http://localhost:8080` | Base URL of the API (llama.cpp or OpenAI) |
| API Key | *(empty)* | Required for OpenAI; optional for llama.cpp |
| Model | *(empty)* | OpenAI model name, e.g. `gpt-4o-mini` |
| Temperature | `0.3` | 0–2, lower = more deterministic |
| Max Tokens | `4096` | Maximum response length |
| Script Timeout | `30` | Max seconds a script can run before being terminated (0 = no timeout) |
| Log Retention | `0` | Days to keep execution logs (0 = forever). Old logs are deleted on dashboard load. |

## Environment Variables (`.env`)

```
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///data.db
```

LLM settings are now configured in the GUI instead of `.env`.

## Scaling Up: SQLite to PostgreSQL

SQLite is fine for development and single-user use, but for production with multiple users you'll want PostgreSQL.

### 1. Install the PostgreSQL driver

```bash
pip install psycopg2-binary
```

(Use `psycopg2` instead of `psycopg2-binary` if you have the system libpq library installed.)

### 2. Create the PostgreSQL database

```bash
psql -U postgres
CREATE DATABASE pythonappfoundry;
CREATE USER appfoundry WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE pythonappfoundry TO appfoundry;
\q
```

### 3. Update `.env`

```
DATABASE_URL=postgresql://appfoundry:your-password@localhost:5432/pythonappfoundry
```

### 4. Migrate your data (two options)

**Option A — Fresh start** (simplest, no existing data):
Just change `DATABASE_URL` and restart. The platform creates all tables on startup automatically via `db.create_all()`.

**Option B — Migrate existing SQLite data**:
```bash
# Dump SQLite data to SQL
sqlite3 instance/data.db .dump > data_dump.sql

# Edit the dump to remove SQLite-specific syntax:
#   - Remove PRAGMA lines
#   - Remove BEGIN/COMMIT if needed
#   - Change AUTOINCREMENT to SERIAL
#   - Remove sqlite_sequence references

# Import into PostgreSQL
psql -U appfoundry -d pythonappfoundry -f data_dump.sql
```

### Important notes

- **DynamicModel tables** (tables created by modules at runtime) are also recreated on startup — the Data Browser lets you verify they exist after migration.
- **Sequences and auto-increment**: SQLite's `AUTOINCREMENT` and PostgreSQL's `SERIAL` / `IDENTITY` differ. After migration, check that auto-incrementing IDs work by adding a test row in the Data Browser.
- **No Flask-Migrate needed**: The platform uses `db.create_all()` on every startup, so as long as your database URL points to PostgreSQL, all platform tables are created automatically. Schema changes to existing platform tables use raw `ALTER TABLE` in `app/__init__.py` — these run on PostgreSQL as well.

## Credentials (Encrypted Secrets)

Credentials (API keys, OAuth tokens, passwords) are stored encrypted at rest using Fernet (symmetric encryption with a key stored in `instance/credential.key`). Each credential belongs to a module and is only accessible to scripts within that module.

### Managing Credentials

1. Go to **Credentials** (`/__admin/credentials`) → **+ New Credential**
2. Select the **Module** that will use this credential
3. Enter a **Name** (e.g., `github_api_key`, `stripe_token`, `db_password`)
4. Select the **Type**:
   - `api_key` — generic API key or token
   - `oauth_token` — OAuth 2.0 access token
   - `basic_auth` — colon-separated `username:password` pair
   - `custom` — any other secret string
5. Enter the **Value** (shown plaintext in the form, encrypted before storage)
6. Click **Save**

### Usage in Scripts

```python
# Retrieve a credential (decrypted automatically, scoped to this module)
api_key = get_credential('github_api_key')

# Use with call_api
result = call_api('GET', 'https://api.github.com/user/repos',
    headers={'Authorization': 'Bearer ' + api_key, 'Accept': 'application/vnd.github.v3+json'})

if result['status_code'] == 200:
    repos = result['body']  # auto-parsed JSON list
    _result = f"Found {len(repos)} repositories"
else:
    _result = f"API error: {result.get('error', result['body'][:200])}"
```

### Security Notes

- Credentials are **encrypted at rest** — the raw value is never stored in the database
- The encryption key file (`instance/credential.key`) must be preserved across deployments. If lost, credentials cannot be recovered — delete and re-create them.
- Credentials are only accessible to scripts in the **same module**. Module A's scripts cannot access Module B's credentials.
- Never hardcode secrets in script source code — scripts are stored in the database in plaintext.
- The decrypted value is only available in memory during script execution and is not logged.

## Incoming Email (IMAP Polling)

The platform can poll an IMAP mailbox for incoming emails and store them in the `incoming_emails` table for module processing.

### Configuration

1. Go to **Settings** (`/__admin/settings`) → scroll to **Incoming Mail (IMAP)**
2. Configure:
   - **Enable IMAP polling** — enable the scheduler poll loop
   - **IMAP Host / Port** — your mail server (default 993 for SSL)
   - **Username / Password** — IMAP credentials
   - **Use SSL** — enable SSL/TLS (default on)
   - **Folder** — mailbox folder (default `INBOX`)
   - **Poll Interval** — minutes between checks (default 5)
   - **Mark as seen** — mark fetched messages as read on the server
   - **Email Retention** — days to keep processed emails (0 = forever). Cleanup runs on dashboard load.

### Module Processing

Modules claim and process incoming emails by querying the `incoming_emails` table:

```python
# Find unprocessed emails for this module
result = db.session.execute(db.text("""
    SELECT id, subject, from_address, body_text
    FROM incoming_emails
    WHERE processed = 0
      AND subject LIKE '%support%'
    ORDER BY created_at ASC
"""))
for row in result:
    email_id = row[0]
    # ... process the email ...

    # Mark as processed and claimed by this module
    db.session.execute(db.text("""
        UPDATE incoming_emails
        SET processed = 1, module_slug = 'your-module-slug',
            processed_at = datetime('now')
        WHERE id = :eid
    """), {'eid': email_id})
db.session.commit()
```

The demo module `demos/incoming_mail_demo.xml` shows a complete example — import it from **Modules → New Module → Import from XML**.

## Integration Health Dashboard

The Integration Health page (`/__admin/integration-health`) provides monitoring for all script and task executions:

- **Summary cards** — recent run count, error count with error rate percentage, average duration
- **Module filter** — filter by module to see only its scripts' logs
- **Execution logs** — sortable table with timestamp, script/task name, status, duration, and error detail viewer

This is useful for:
- Monitoring whether scheduled integration tasks are succeeding
- Debugging API call failures in scripts
- Spotting performance regressions (high latency or error rate)
- Verifying a specific module's scripts are healthy

## Python Packages

The Packages page (`/__admin/packages`) lets you install, list, and uninstall Python packages at runtime. No server restart is needed — packages are available to script executions immediately after installation.

- **Install**: Enter a package name (e.g., `requests`, `requests==2.31.0`, `pandas numpy` for multiple) and click Install. Output from `pip install` is shown.
- **Uninstall**: Enter a package name and click Uninstall (confirms first).
- **List**: Shows the full output of `pip list --format=columns`.

### Declaring Requirements in Module XML

Module XML bundles can include a `<requirements>` element to auto-install dependencies on import:

```xml
<requirements>
requests==2.31.0
pandas
# comments are ignored
</requirements>
```

When the module is imported (via AI Designer, BPMN, or XML import), each requirement is installed via `pip install` automatically. Failed installs are logged but do not block module import.

## SMTP / Email Configuration

Email settings are managed via **Admin → Settings** in the GUI. Scripts use `send_email(to, subject, body, html=False)` which reads these settings automatically — no credentials should ever be hardcoded in scripts.

| Key | Default | Description |
|-----|---------|-------------|
| SMTP Host | `localhost` | SMTP server address |
| SMTP Port | `587` | SMTP port (25, 465, 587) |
| Username | *(empty)* | SMTP login username |
| Password | *(empty)* | SMTP login password |
| From Address | `noreply@example.com` | Sender email address |
| Use TLS | `true` | Enable TLS encryption |

## Tips

- The first account created is always admin
- The setup page only appears when no routes exist AND no users exist
- Login redirects to the module list when no routes exist (admins see the site root if routes exist)
- Modules can be exported as XML and re-imported on another instance
- The AI_GUIDE.md file controls how the LLM generates modules — edit it to steer behavior
- **Script timeout**: Set `script_timeout` in Settings to limit how long scripts can run. Default is 30s. Set to `0` to disable (not recommended — a runaway script can hang the scheduler).
- **Log retention**: Set `log_retention_days` in Settings to auto-delete old execution logs. Cleanup runs on dashboard page load.
- **SMTP test**: Use the "Send Test Email" button in Settings to verify your SMTP config before relying on it in scripts.
- **Module cloning**: Use the "Clone" button on the Modules list to duplicate a module as a starting point. The clone gets "(copy)" appended to its name and slug.
- **Route group access**: When editing a route, you can restrict it to specific groups. Users must be logged in AND belong to at least one of the selected groups to access the route. Leave groups empty to allow any authenticated user.
- **Dependency viewer**: Click the red dependency count in the Modules list to see which modules reference a given module, including the type and value of each reference. Run "Scan" on the module first to detect its references to other modules.
- **System modules** — The **System Automation** module is auto-created on first start and cannot be deleted. Use it for platform-wide scripts, queries, and scheduled tasks. If you break it, use the **Reset** button (visible in the Modules list) to wipe all its resources back to empty.
- **Query reports are module-scoped** — Like routes and scripts, queries now belong to a module. Create queries under the **System Automation** module for platform-wide visibility, or under app modules for app-specific reporting.
- **Use `get_credential()` instead of hardcoding secrets** — Store API keys, tokens, and passwords in the Credentials admin page. They're encrypted at rest and module-scoped. Scripts call `get_credential('name')` to retrieve them — never put secrets in script source code.
- **Use `call_api()` for external HTTP calls** — The built-in client handles retries, timeouts, and JSON parsing consistently. Importing `urllib` directly in scripts is discouraged — `call_api()` logs errors to the execution log automatically and gives consistent return formatting.
- **Monitor integrations in the Health page** — The `/__admin/integration-health` page shows error rates, recent failures, and average latency per module. Visit it regularly to catch failing scripts early.

## Query Reports

Queries are **module-scoped**, just like routes, scripts, and forms. Each query belongs to a module and is bundled in the module's XML for export/import.

### Module Association

- When creating or editing a query, you select which **Module** it belongs to
- Platform-wide queries go in the **System Automation** module (auto-created, non-removable)
- Demo or app-specific queries belong to their respective module

### Creating a Query

1. Go to **Queries** (`/__admin/queries`) → **+ New Query**
2. Select the **Module** the query belongs to
3. Enter a **Name** and **SQL query** (any valid SQL against the database)
4. Optionally configure the **Chart Type** (bar, line, pie, doughnut, polar area, radar)
5. Set **Label Column** (X axis / category) and **Data Column(s)** (Y axis / value series)
6. Click **Save** to store the query
7. Click **Save & Run** to execute and preview results as table + chart

### Scheduling & Email

Open the **Schedule & Email** section on the edit page:

- **Cron Schedule** — standard 5-field cron expression (e.g. `0 8 * * 1` for every Monday at 8 AM)
- **Email To** — recipient address(es) for emailed results (sent as CSV)
- **Email Subject** — subject line for the report email

Scheduled queries run once per minute. Results are emailed only if both a cron schedule and email recipient are configured.

### Bundling in Modules

Queries are included in module XML under a `<query_reports>` section. When a module is exported, its queries are included. When imported, the queries are created as part of the module.

See `demos/sales_demo.xml` for a module that bundles a "Sales by Product and Region" query with a data-seeding script.

### System Automation Module

The **System Automation** module (`system-automation`) is a built-in system module that:
- Cannot be deleted
- Can be reset to empty via the **Reset** button on the Modules list
- Is the default location for platform-wide queries, scripts, and scheduled tasks
- Ships empty — import demo modules or create your own resources

### Charting in Module Scripts

Module scripts can render charts using the built-in `render_chart()` helper:

```python
labels = ['Widget', 'Gadget', 'Thing', 'Doohickey']
datasets = [
    {'label': 'Units Sold', 'data': [100, 200, 150, 75]},
    {'label': 'Revenue ($)', 'data': [5000, 12000, 8000, 3000]},
]
_result = render_chart('bar', labels, datasets, title='Sales Overview')
```

Supported chart types: `bar`, `line`, `pie`, `doughnut`, `polarArea`, `radar`.

The helper auto-loads Chart.js from `/static/chart.umd.min.js` if not already present on the page. Charts render inside a responsive container (max 600px width).

## Database Backup & Restore

Database backups are managed from `/__admin/backups` (admin only).

**Creating a backup:**
1. Go to **Backups** (`/__admin/backups`)
2. Click **Create New Backup**
3. The backup is stored in `instance/backups/database_YYYYMMDD_HHMMSS.db`

**Restoring a backup:**
1. Go to **Backups** and find the backup you want to restore
2. Click **Restore** next to the backup
3. The system creates an emergency backup of the current database before restoring
4. **Restart the application** after restoring to load the new database

**Downloading a backup:**
- Click **Download** to save the backup file locally

Backups are stored with `0600` permissions (owner read/write only).

## Script Testing

The script editor now includes a **Test Script** button that runs the script in a sandboxed environment and shows the result in a modal popup. This is useful for quick testing without navigating to the actual route.

1. Go to **Scripts** → edit any script
2. Click **Test Script** (green button)
3. View the result, output, or error in the modal

## AI-Powered Script Debugging

When a script fails, you can click **"Ask AI about this error"** to get the configured LLM to analyze the error and suggest a fix. This works across the platform wherever errors are displayed.

### Where It's Available

| Location | How It Works |
|----------|-------------|
| **Script Editor → Test Modal** | Click "Test Script" → if error, click "Ask AI about this error" → AI analyzes the error + your source code → "Apply Fix" populates the textarea with the corrected script |
| **Script Debug Page** | Click "Run Debug" → if error, click "Ask AI about this error" → AI analyzes the error + source code → "Copy Fix to Clipboard" button + link to editor |
| **Dashboard → Recent Logs** | Click "View Error" → if error, "Ask AI about this error" button appears → AI looks up the script source by name and analyzes it |
| **Integration Health** | Click "View Error" → same flow as dashboard |

### How It Works

1. Click "Ask AI about this error" — the button shows "Analyzing..." while the LLM processes
2. The LLM receives the error message, the full script source code, and a system prompt explaining the platform's sandbox constraints
3. The response includes:
   - **Root Cause** — what went wrong and why
   - **Corrected Script** — the full fixed script
   - **Explanation** — what the fix does and any sandbox-aware advice
4. If the LLM provides a corrected script:
   - **Apply Fix** (script editor only) — copies the fixed code into the source code textarea
   - **Copy Fix to Clipboard** — copies the fixed code to your clipboard

### Configuration

This feature uses the same LLM settings configured in **Admin → Settings** (Provider, Endpoint, API Key, Model, Temperature, Max Tokens). No additional setup is needed.

The LLM is given a system prompt that explains the platform's sandbox:
- Blocked imports (`os`, `subprocess`, `sys`, `socket`, etc.)
- Available globals (`db`, `request`, `DynamicModel`, `call_api`, `get_credential`, etc.)
- Script conventions (`return`/`_result` patterns, auto-wrapping)

This means the AI can suggest fixes that work within the sandbox rather than suggesting imports that would be blocked.

### Requirements

- LLM must be configured in Admin → Settings (Provider + Endpoint at minimum)
- User must have Developer or Admin role
- CSRF token is included automatically

## Audit Log

All administrative actions are automatically logged to the `audit_logs` table. This provides a traceable history of who changed what, when, and from where.

### What Gets Logged

| Action | Entity | Example |
|--------|--------|---------|
| `create` | module, script, form, route, task, trigger, group, credential, query, version, user | Module "my_app" created |
| `edit` | module, script, form, route, task, trigger, group, credential, query, user, settings | Module "my_app" updated |
| `delete` | module, group, credential, query, backup | Module "my_app" deleted |
| `import` | module | Module imported from AI chat or BPMN |
| `clone` | module | Module "my_app" cloned as "my_app_copy" |
| `reset` | module | System module "core" reset to defaults |
| `install` | package | Package "requests" installed |
| `uninstall` | package | Package "requests" uninstalled |
| `restore` | version, backup | Version 3 restored for module "my_app" |
| `create` | backup | Database backup created |
| `update` | settings | Settings changed: site_name, smtp_host |

### Log Entry Fields

Each audit log entry includes:

- **User** — who performed the action (name + ID)
- **Action** — what was done (create, edit, delete, import, etc.)
- **Entity Type** — what was affected (module, script, settings, etc.)
- **Entity ID** — database ID of the affected record
- **Entity Name** — human-readable name of the affected record
- **Details** — optional extra info (e.g., settings diff, import source)
- **IP Address** — client IP of the requester
- **Timestamp** — when the action occurred

### Viewing the Audit Log

Navigate to **Admin → Audit** (linked in the top admin bar). The list view supports:

- **Entity Type Filter** — show only modules, scripts, settings, etc.
- **User Filter** — show only actions by a specific user
- **Action Filter** — show only creates, deletes, edits, etc.

### Technical Details

- Model: `AuditLog` in `app/models.py`
- Helper: `log_audit(action, entity_type, entity_id, entity_name, details)` in `app/services/audit.py`
- Blueprint: `app/routes/admin_audit.py` registered at `/__admin/audit`
- Current user and IP are captured automatically from the Flask request context
- All admin CRUD routes across 17 blueprints are wired with `log_audit()` calls

## Database Templates

Templates let you store reusable Jinja2 HTML fragments in the database alongside scripts and forms. Instead of building HTML strings inline in scripts, you define templates once and render them with context variables.

### Creating a Template

1. Navigate to **Admin → Templates** (or **Dev → Templates**)
2. Click **+ New**
3. Fill in:
   - **Name** — identifier used to look up the template (e.g. `dashboard_layout`, `email_welcome`)
   - **Module** — which module this template belongs to
   - **Content Type** — `html` (default), `text`, or `json`
   - **Description** — what this template is for
   - **Template Body** — the Jinja2 source code
4. Click **Save**

### Template Syntax

Templates use standard Jinja2 syntax:

```html
<h1>Hello {{ name }}!</h1>

{% if items %}
<ul>
  {% for item in items %}
  <li>{{ item.title }} - {{ item.price }}</li>
  {% endfor %}
</ul>
{% else %}
<p>No items found.</p>
{% endif %}
```

**Key features available:**
- **Variables:** `{{ variable }}` — auto-HTML-escaped to prevent XSS
- **Conditionals:** `{% if condition %}...{% else %}...{% endif %}`
- **Loops:** `{% for item in items %}...{% endfor %}`
- **Filters:** `{{ name|upper }}`, `{{ items|length }}`, `{{ html|safe }}`
- **Raw blocks:** `{% raw %}<div>{{ CSS }}</div>{% endraw %}` — disables Jinja2 parsing for CSS/JS with curly braces

### Using Templates in Scripts

Scripts look up templates by name and pass the body to `render_db_template()`:

```python
from app.models import Template

# Look up the template
tpl = Template.query.filter_by(name='dashboard', module_id=module_id).first()
if tpl:
    # Render with context variables
    return render_db_template(tpl.body, title='Sales Report', rows=data)
return '<h1>No template found</h1>'
```

**Cross-module templates** — a script can render templates from other modules:

```python
tpl = Template.query.filter_by(name='base_layout').first()  # any module
return render_db_template(tpl.body, content=inner_html)
```

### `render_db_template()` Reference

```
render_db_template(template_body, **context)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_body` | str | The Jinja2 template source (from `Template.body`) |
| `**context` | any | Key-value pairs passed as template variables |

**Returns:** rendered string (HTML, text, or JSON depending on template content)

**Security:** Templates are rendered in an `ImmutableSandboxedEnvironment`:
- All variables are HTML-escaped by default (prevents XSS)
- Blocks `_`-prefixed attribute access (e.g. `__class__`, `__subclasses__`)
- Blocks mutating operations on passed objects (`.append()`, `.update()`)
- Blocks calling unsafe callables
- Missing variables raise `UndefinedError` (fail loud, not silent)

### Live Preview

The template edit page includes a **Preview** panel:

1. Enter the template body in the left editor
2. Optionally enter sample context as JSON (e.g. `{"name":"World","items":["a","b"]}`)
3. Click **Render** to see the output
4. The preview uses the same sandboxed renderer as production scripts

### XML Import/Export

Templates are included in module XML bundles:

```xml
<templates>
  <template name="welcome_email" content_type="html" description="Welcome email body">
    <body>
    <![CDATA[
      <h1>Welcome {{ user.name }}!</h1>
      <p>Your account is ready.</p>
    ]]>
    </body>
  </template>
</templates>
```

Templates are imported after scripts and forms, and are deleted on module update (cascade).

### Technical Details

- Model: `Template` in `app/models.py`
- Renderer: `render_db_template()` in `app/services/template_renderer.py`
- Blueprint: `app/routes/admin_templates.py` registered at `/__admin/templates`
- Preview endpoint: `POST /__admin/templates/preview` (AJAX, JSON body)
- `render_db_template` is injected into every script's globals

## XML Import Preview

Before importing a module XML, you can now preview what will be imported:

1. Go to **Modules** → **+ New**
2. Click **Import from XML**
3. Select an XML file and click **Preview Import**
4. See counts of scripts, routes, forms, tasks, and triggers that will be imported
5. Confirm the import if everything looks correct

## OpenAPI Specification

The platform auto-generates an OpenAPI 3.0 specification from all registered routes:

- **JSON spec:** `/__api/openapi.json` (requires login)
- **Swagger UI:** `/__api/swagger` (requires login)

This makes it easy to document your platform's API for external consumers or integrate with API testing tools.

## Module Marketplace

Share and discover modules via the built-in marketplace:

- **Browse:** `/__admin/marketplace`
- **Publish:** Use `app.services.marketplace.publish_module()` to add a module
- **Install:** Click **Install** on any marketplace entry

Marketplace entries are stored as JSON files in the `marketplace/` directory.

## Webhook Reliability

Webhooks now include automatic retry logic:

- **Retries:** Up to 3 attempts with exponential backoff
- **Dead letter queue:** Failed webhooks after all retries are logged to the dead letter queue
- **Monitoring:** Check `/__admin/integration-health` for webhook status

## Security Features

### Script Sandbox

Scripts run in a hardened sandbox:
- Cannot import `os`, `subprocess`, `sys`, `socket`, `http`, `urllib`, `requests`, etc.
- Custom `__import__` function blocks dangerous modules
- Timeout enforcement via SIGALRM (main thread) or threading (scheduled tasks)

### Webhook Rate Limiting

Webhooks are rate limited to prevent abuse:
- **30 calls/minute** per webhook slug per IP
- **600 calls/hour** per webhook slug per IP
- Exceeding limits returns HTTP 429

### Settings Access Control

Scripts cannot read sensitive settings:
- `smtp_password`, `llm_api_key`, `imap_password`, `secret_key`, `database_url` are blocked
- Use `get_setting('safe_key', 'default')` in scripts — sensitive keys return the default

### TLS Verification

`call_api()` now verifies SSL certificates by default:
- Uses `ssl.create_default_context()` for certificate validation
- Set `verify_ssl=False` to skip verification (not recommended)

## Structured Logging

Enable JSON-formatted structured logging for better monitoring:

```python
from app.services.structured_logging import setup_structured_logging
setup_structured_logging(app, level=logging.INFO)
```

Logs include: timestamp, level, logger name, message, module, function, line number, and extra context (script name, module ID, user ID, etc.).

## Multi-Tenant Support

Basic multi-tenant isolation is available:

- **Subdomain-based:** Configure tenants by subdomain (e.g., `acme.example.com`)
- **Path-based:** Configure tenants by path prefix (e.g., `/acme/...`)
- **Tenant selector:** Added as a before_request hook in `app/__init__.py`

To add a tenant:
```python
from app.services.tenant import _tenants, Tenant

_tenants['acme'] = Tenant(
    id=2,
    name='Acme Corp',
    slug='acme',
    config={'subdomain': 'acme', 'path_prefix': 'acme'}
)
```

## Health Check Endpoint

The `/healthz` endpoint now provides detailed health information:

```json
{
  "status": "ok",
  "database": "connected",
  "scheduler": "running (5 jobs)",
  "imap": "configured",
  "uptime_seconds": 3600.5
}
```

Returns HTTP 503 if any checks fail.

## Docker Deployment

PythonAppFoundry can be deployed using Docker and Docker Compose for easy setup and scaling.

### Quick Start with Docker

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Nurb4000/PythonAppFoundry
   cd PythonAppFoundry
   ```

2. **Configure environment:**
   ```bash
   cp .env.docker.example .env
   # Edit .env and set SECRET_KEY to a secure random value!
   ```

3. **Start the application:**
   ```bash
   docker compose up -d
   ```

4. **Access the application:**
   - Web UI: `http://localhost:5000/`
   - Health check: `http://localhost:5000/healthz`

### Using PostgreSQL (Production)

For production deployments, use PostgreSQL instead of SQLite:

1. **Edit `.env`:**
   ```bash
   DATABASE_URL=postgresql://appfoundry:your-password@db:5432/pythonappfoundry
   ```

2. **Start with PostgreSQL:**
   ```bash
   docker compose up -d
   ```

The `docker-compose.yml` includes a PostgreSQL service that will be automatically started.

### Using llama.cpp (Optional)

To enable AI module generation:

1. **Download a GGUF model** and place it in the `models/` directory:
   ```bash
   mkdir -p models
   # Download your model here, e.g., from Hugging Face
   ```

2. **Start with llama.cpp:**
   ```bash
   docker compose up -d llamacpp web
   ```

3. **Configure in Admin → Settings:**
   - Provider: `llamacpp`
   - Endpoint: `http://llamacpp:8080`

### Production Deployment

For production, use the provided `docker-compose.prod.yml.example`:

1. **Copy and customize:**
   ```bash
   cp docker-compose.prod.yml.example docker-compose.prod.yml
   # Edit with your secrets and configuration
   ```

2. **Set environment variables:**
   ```bash
   export SECRET_KEY=$(openssl rand -hex 32)
   export DB_PASSWORD=$(openssl rand -hex 16)
   ```

3. **Deploy:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

### Managing Data

**Backup:**
```bash
docker compose exec web python -m app.services.backup create_backup
```

**Restore:**
```bash
docker compose exec web python -m app.services.backup restore_backup /app/instance/backups/database_YYYYMMDD_HHMMSS.db
```

**Access volumes:**
- Application data: `./instance/`
- Marketplace: `./marketplace/`
- PostgreSQL: Named volume `postgres_data`

### Scaling

For high-availability deployments, you can run multiple web containers behind a load balancer:

```bash
docker compose up -d --scale web=3
```

Note: With SQLite, only one container should write to the database. Use PostgreSQL for multi-container setups.

### Troubleshooting

**Check logs:**
```bash
docker compose logs web
docker compose logs db
docker compose logs llamacpp
```

**Restart a service:**
```bash
docker compose restart web
```

**Stop all services:**
```bash
docker compose down
```

**Remove volumes (destroys data):**
```bash
docker compose down -v
```

### Security Notes

- **Always change `SECRET_KEY`** in production — generate a random 32-byte hex string
- **Use PostgreSQL** for production instead of SQLite
- **Enable HTTPS** with a reverse proxy (nginx, Caddy) in production
- **Regular backups** — use the backup feature or `pg_dump` for PostgreSQL
- **Keep images updated** — pull latest versions of Python, PostgreSQL, and llama.cpp images
