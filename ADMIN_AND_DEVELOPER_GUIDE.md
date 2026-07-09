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
| Data | `/__admin/data` | Browse and edit any database table |
| Uploads | `/__admin/uploads` | Upload files for use in pages |
| Settings | `/__admin/settings` | Registration controls (disable, require approval) |
| AI Designer | `/__admin/chat` | Chat interface to generate modules via AI |
| BPMN Designer | `/__admin/bpmn` | Visual BPMN workflow designer with AI module conversion |
| Dashboard | `/__admin/dashboard` | System health overview, execution logs, and scheduler status |

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

- Lists all tables with row counts and column types
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
