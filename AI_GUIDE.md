# AI Module Generation Guide

This document describes the XML bundle format for generating application modules. Provide this to any AI to have it generate valid, importable modules.

## XML Schema

```xml
<?xml version="1.0" encoding="UTF-8"?>
<module name="My App" slug="my-app" version="1.0.0" author="AI">
  <description>A human-readable description of what this module does.</description>

  <routes>
    <!-- Each route maps a URL path to a script (and optionally a form).
         method: GET, POST, GET,POST, PUT, DELETE, etc.
         auth_required: "true" or "false"
         script: must match a <script name=""> in this bundle
         form: must match a <form name=""> in this bundle (optional)
         IMPORTANT: slug must be an exact URL path. Flask URL converters
         like <int:project_id> are NOT supported and will break XML parsing.
         Use query parameters instead: /project?project_id=1 -->
    <route slug="/" method="GET" script="do_home" auth_required="false" title="Home Page"/>
    <route slug="/items" method="GET" script="list_items" auth_required="true" title="Items"/>
    <route slug="/items/add" method="GET,POST" script="add_item" form="item_form" auth_required="true" title="Add Item"/>
  </routes>

  <scripts>
    <!-- Each script is Python code that runs when its route is hit.
         language must be "python". -->
    <script name="do_home" language="python"><![CDATA[
# Available variables in every script:
#   request       - Flask request object
#   session       - SQLAlchemy session (db.session)
#   db            - SQLAlchemy db instance
#   current_user  - Flask-Login current_user (AnonymousUserMixin if not logged in)
#   redirect()    - flask.redirect
#   url_for()     - flask.url_for
#   flash()       - flask.flash
#   render()      - flask.render_template_string (render HTML inline)
#   jsonify()     - flask.jsonify
#   route         - the Route model object for this route

# Scripts must either:
#   1. Call redirect(), render(), jsonify() directly (these return a response)
#   2. Assign a return value to _result:  _result = "some string"
#   3. Print output (will be captured as the response body)

from app.models import Module  # All models importable
modules = session.query(Module).all()
output = "<ul>"
for m in modules:
    output += f"<li>{m.name} (v{m.version})</li>"
output += "</ul>"
_result = output
]]></script>

    <script name="list_items" language="python"><![CDATA[
# Example with a dynamic table called "Item" (created on first use)
from app.models import DynamicModel

Item = DynamicModel.get_or_create("Item", {
    'title': db.String(200),
    'done': db.Boolean,
})

items = session.query(Item).all()
_result = render("<ul>{% for i in items %}<li>{{ i.title }}</li>{% endfor %}</ul>",
                  items=items)
]]></script>

    <script name="add_item" language="python"><![CDATA[
from app.models import DynamicModel

Item = DynamicModel.get_or_create("Item", {
    'title': db.String(200),
    'done': db.Boolean,
})

if request.method == 'POST':
    item = Item(title=request.form['title'], done=False)
    session.add(item)
    session.commit()
    flash("Item added")
    return redirect("/items")

# GET shows the form — form is rendered automatically by the engine
# If no form is defined, this script handles rendering
_result = "<h2>Add Item</h2><form method=POST>..."
]]></script>
  </scripts>

  <forms>
    <!-- Forms define HTML form fields via JSON schema.
         Each field object:
           name:       field name (matches request.form key)
            type:       text, password, email, number, textarea, select, checkbox, date, file
           label:      display label
           required:   true/false
           options:    comma-separated (for type=select)
           placeholder: placeholder text -->
    <form name="item_form">[
  {"name":"title","type":"text","label":"Title","required":true,"placeholder":"Enter item title"},
  {"name":"priority","type":"select","label":"Priority","required":false,"options":"low,medium,high"},
  {"name":"done","type":"checkbox","label":"Mark complete","required":false}
]</form>
  </forms>

  <scheduled_tasks>
    <!-- Tasks run on a cron schedule.
         script: must match a <script name=""> in this bundle
         schedule: standard 5-field cron expression -->
    <task name="cleanup_old_items" script="cleanup_items" schedule="0 3 * * *"/>
  </scheduled_tasks>

  <triggers>
    <!-- Triggers fire automatically on database events.
         event: on_insert, on_update, on_delete, after_route
         table: table name (the target table for DB events; module slug for after_route)
         script: must match a <script name=""> in this bundle -->
    <trigger name="notify_new_item" event="on_insert" table="Item" script="send_notification"/>
  </triggers>
</module>
```

## Dynamic Models (Tables)

Scripts can create and use database tables dynamically with `DynamicModel`:

```python
from app.models import DynamicModel

# This creates (or retrieves) a table with the given columns.
# Call it once per script; subsequent calls return the same model.
Todo = DynamicModel.get_or_create("Todo", {
    'title': db.String(200),
    'completed': db.Boolean,
    'priority': db.Integer,
    'created_at': db.DateTime,
})

# Now use it like a regular SQLAlchemy model
items = session.query(Todo).filter_by(completed=False).all()
new_item = Todo(title="Buy milk", completed=False)
session.add(new_item)
session.commit()
```

**Critical: DynamicModel only auto-adds an `id` column.** It does NOT add `created_at`, `updated_at`, or any other automatic column. Every column you use in a query, filter, or ORDER BY must be explicitly defined in the `get_or_create()` columns dict. If you need `created_at`, add `'created_at': db.DateTime` to the dict — otherwise queries like `ORDER BY created_at` will crash.

Supported column types: `db.String(n)`, `db.Integer`, `db.Boolean`, `db.Float`,
`db.DateTime`, `db.Text`, `db.Date`, `db.LargeBinary`.

## Render Helper

`render(template_string, **kwargs)` renders a Jinja2 template string. Usage:

```python
_result = render("<h1>Hello {{ name }}</h1>", name="World")
```

**Important:** `render()` uses Jinja2. If your template contains CSS or JavaScript with curly braces `{}`, they must be wrapped in `{% raw %}...{% endraw %}` blocks to prevent Jinja2 from trying to parse them:

```python
_result = render("""
{% raw %}
<style>
  body { background: #f00; }
</style>
{% endraw %}
<h1>Hello {{ name }}</h1>
""", name="World")
```

If the template has NO Jinja2 variables, skip `render()` entirely and assign the HTML string directly to `_result`:

## JavaScript in Templates

When embedding JavaScript in HTML strings returned by scripts:

- **Do NOT use escaped quotes** like `alert(\'text\')` — this breaks JavaScript syntax. Use `JSON.stringify('text')` instead for strings in alerts/confirmations.
- Wrap JS with curly braces `{}` in `{% raw %}...{% endraw %}` blocks if using `render()`, since Jinja2 will try to parse them as template variables.
- Keep inline scripts simple. For complex interactivity, consider separate `.js` files or the AI Designer to generate them.

## Forms vs Scripts

**Forms** are JSON schema definitions stored separately from scripts. Use the `<forms>` XML section to define form fields, then reference them in routes:

```xml
<forms>
  <form name="contact_form">[
    {"name":"email","type":"email","label":"Email","required":true},
    {"name":"message","type":"textarea","label":"Message","required":true}
  ]</form>
</forms>

<scripts>
  <script name="show_contact"><![CDATA[
# Use render_form() to render the form — do NOT write inline HTML for form fields
_result = render("<h2>Contact Us</h2>" + render_form(action='/contact/submit'))
]]></script>
</scripts>
```

**Key points:**
- Form field definitions go in `<forms>` as JSON arrays (name, type, label, required, options, placeholder)
- Scripts use `render_form('form_name')` to render the form HTML automatically
- Do NOT write inline HTML `<input>` tags in scripts when a Form entity can handle it — the form builder and live preview editor work with Form schemas, not inline HTML
- `render_form()` accepts: `action`, `method`, `submit_label`, `fields` (optional override)

## `_result` Convention

Always end a script by either:
- Returning a response directly (`return redirect(...)`, `return render(...)`, `return jsonify(...)`)
- Assigning `_result = <value>` for the script engine to return
- Printing output (captured as response body — not recommended for structured content)

## JSON Response

```python
return jsonify({"status": "ok", "items": [...]})
```

## Common Patterns

### Auth-protected route
```xml
<route slug="/dashboard" method="GET" script="show_dashboard" auth_required="true"/>
```

### Form + script (POST to same URL)
```xml
<route slug="/profile/edit" method="GET,POST" script="edit_profile" form="profile_form" auth_required="true"/>
```

When a route has a form, the script has these automatically available:
- `form_fields` — list of field dicts parsed from the form's schema
- `render_form(action="", method="POST", submit_label="Submit", fields=form_fields)` — renders full form HTML

These are always available in every script (no import needed):
- `DynamicModel` — factory for dynamic database tables (`DynamicModel.get_or_create(...)`)
- `datetime`, `timezone` — from the `datetime` module (`datetime.now(timezone.utc)`)

Simple form handler pattern:
```python
if request.method == 'POST':
    # process submitted data
    name = request.form.get('name')
    # ... save to db, send email, etc.
    return redirect('/thank-you')

# GET request: display the form
return render_form(submit_label="Send Message", fields=form_fields)
```

For custom layouts, inspect `form_fields` directly:
```python
html = '<form method="POST">'
for f in form_fields:
    html += f'<p>{f["label"]}: <input name="{f["name"]}"></p>'
html += '<button>Submit</button></form>'
return html
```

### Sending Email

The `send_email(to, subject, body, html=False)` helper sends emails using the SMTP settings configured by the admin. Use it from any script:

```python
# Plain text
send_email('user@example.com', 'Welcome!', 'Your account has been created.')

# HTML email
send_email('user@example.com', 'Receipt', '<h1>Thanks</h1><p>Your order confirmed.</p>', html=True)

# Multiple recipients
send_email(['user1@example.com', 'user2@example.com'], 'Notice', 'System update.')
```

SMTP settings (host, port, credentials, TLS, from address) are managed by the admin via Settings and should never be hardcoded in scripts.

### Accessing Cross-Module Data

All DynamicModel tables are stored in the same SQLite database. Any script can access tables created by other modules by calling `DynamicModel.get_or_create()` with the same name and columns:

```python
from app.models import DynamicModel

# Access the "Project" table created by another module
# (get_or_create retrieves existing table if it exists)
Project = DynamicModel.get_or_create("Project", {
    'name': db.String(200),
    'description': db.Text,
})

projects = session.query(Project).all()
```

You can also query the platform's built-in tables directly:

```python
from app.models import User

# List all users
users = session.query(User).all()

# Filter by role
admins = session.query(User).filter_by(role='admin').all()
```

**Note:** When accessing a table from another module, you must list ALL its columns in the `get_or_create()` call — missing columns will not exist in the returned model. If unsure, inspect the table schema or define all columns you need.

### File Uploads

The platform provides file upload functionality for user forms. Files are stored securely with random filenames and tracked in the database.

#### Using the File Upload Component (Recommended)

Include the file upload JavaScript component in your form template:

```html
<!-- Include the file upload styles and script -->
<link rel="stylesheet" href="/static/file-upload.css">
<div id="file-upload-container" data-file-upload='{"maxFileSize": 5242880, "multiple": true}'></div>
<script src="/static/file-upload.js"></script>
```

The component provides:
- Drag-and-drop file selection
- Click to browse files
- File validation (size and type)
- Upload progress indication
- Multiple file support (optional)

#### Manual File Upload Handling

If you need custom upload handling, use the API endpoint:

```python
# Route configuration
<route slug="/upload" method="POST" script="handle_upload" auth_required="true"/>
```

```python
# Script: handle_upload
from app.models import Upload
import os
import secrets

if 'file' not in request.files:
    flash('No file selected', 'error')
    return redirect(request.url)

f = request.files['file']
if not f.filename:
    flash('No file chosen', 'error')
    return redirect(request.url)

# Generate secure random filename
ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
save_name = secrets.token_hex(12) + ('.' + ext if ext else '')

# Save to uploads directory
upload_dir = os.path.join(current_app.instance_path, 'uploads')
os.makedirs(upload_dir, exist_ok=True)
f.save(os.path.join(upload_dir, save_name))

# Create database record
upload = Upload(
    filename=save_name,
    original_name=f.filename,
    mime_type=f.content_type or 'application/octet-stream',
    size=os.path.getsize(os.path.join(upload_dir, save_name)),
)
db.session.add(upload)
db.session.commit()

flash(f'File "{upload.original_name}" uploaded successfully')
return redirect(request.url)
```

#### Accessing Uploaded Files in Scripts

```python
# List all uploads
from app.models import Upload
uploads = session.query(Upload).order_by(Upload.created_at.desc()).all()

for upload in uploads:
    print(f"{upload.original_name} - {upload.mime_type} - {upload.size} bytes")
    print(f"URL: /uploads/{upload.filename}")

# Filter by type
images = session.query(Upload).filter(Upload.mime_type.like('image/%')).all()
pdfs = session.query(Upload).filter(Upload.mime_type == 'application/pdf').all()

# Get file path for processing
import os
from flask import current_app
upload_dir = os.path.join(current_app.instance_path, 'uploads')
file_path = os.path.join(upload_dir, upload.filename)
```

#### File Upload API Endpoint

For AJAX uploads from custom forms:

```javascript
// JavaScript example
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('/__api/upload', {
    method: 'POST',
    body: formData,
    credentials: 'same-origin'
})
.then(response => response.json())
.then(data => {
    console.log('Upload successful:', data);
    // data.url contains the public URL: /uploads/{filename}
})
.catch(error => console.error('Upload failed:', error));
```

**Security Notes:**
- All uploaded files are stored with random filenames to prevent path traversal
- Files are stored in the `instance/uploads/` directory
- The platform does not validate file types by default — add your own validation if needed
- There is no built-in file size limit — configure `MAX_CONTENT_LENGTH` in `app/config.py` if needed

#### File Upload Best Practices

**Important: Pass template variables to render()**

When querying data in your script, you must pass those variables to the `render()` function for them to be available in the HTML template:

```python
# WRONG — recent_uploads won't be available in template
recent_uploads = db.session.query(Upload).order_by(Upload.created_at.desc()).limit(10).all()
_result = render('''...html using {{ recent_uploads }}...''')

# CORRECT — pass variables explicitly
recent_uploads = db.session.query(Upload).order_by(Upload.created_at.desc()).limit(10).all()
_result = render('''...html using {{ recent_uploads }}...''', recent_uploads=recent_uploads)
```

**Authentication checks:**

Always check `current_user.is_authenticated` before allowing uploads:

```python
if request.method == 'POST' and current_user.is_authenticated:
    # Process upload
else:
    flash('Please log in to upload files', 'error')
```

**Use the file upload service for security:**

The `upload_file()` service handles secure filename generation and storage automatically:

```python
from app.services.file_upload import upload_file

if 'file' in request.files:
    f = request.files['file']
    if f.filename and f.filename != 'undefined':
        upload = upload_file(f)
        flash(f'Uploaded {upload.original_name}')
```

### API endpoint
```xml
<route slug="/api/data" method="GET" script="api_data" auth_required="false"/>
```
```python
# script: api_data
data = [{"id": 1, "name": "test"}]
return jsonify(data)
```

### Webhooks

External services can POST to webhook endpoints to trigger scripts. Webhooks are configured via Triggers (event_type='webhook') in the admin panel at `/__admin/triggers`.

**Webhook URL format:**
```
POST /__api/webhook/{webhook-slug}
```

**Example: GitHub webhook integration**

```python
# Script: handle_github_push
# Trigger: event_type='webhook', target_table='github-push'

slug = webhook_slug  # 'github-push'
payload = webhook_payload  # JSON data from GitHub

# Access the payload data
repository = payload.get('repository', {}).get('name', 'unknown')
sender = payload.get('sender', {}).get('login', 'unknown')
action = payload.get('action', 'unknown')

# Process based on action
if action == 'push':
    # Handle push event
    pass
elif action == 'pull_request':
    # Handle PR event
    pass

_result = f'Processed {action} event from {sender} on {repository}'
```

**XML bundle example:**
```xml
<module name="GitHub Webhooks" slug="github-webhooks">
  <scripts>
    <script name="handle_github_push" language="python"><![CDATA[
# Script: handle_github_push
slug = webhook_slug
payload = webhook_payload

repository = payload.get('repository', {}).get('name', 'unknown')
sender = payload.get('sender', {}).get('login', 'unknown')
action = payload.get('action', 'unknown')

_result = f'Processed {action} from {sender} on {repository}'
    ]]></script>
  </scripts>
  <triggers>
    <trigger name="github_push_trigger" event="webhook" table="github-push" script="handle_github_push"/>
  </triggers>
</module>
```

**Testing webhooks manually:**
```bash
curl -X POST http://localhost:5000/__api/webhook/github-push \
  -H "Content-Type: application/json" \
  -d '{"action": "push", "repository": {"name": "my-repo"}, "sender": {"login": "user"}}'
```

**Security Notes:**
- Webhooks are secure by obscurity — the unique slug acts as a secret
- No authentication required (public endpoints)
- Log all webhook invocations in ExecutionLog for auditing
- Validate payload structure in your script before processing

**Future: Authenticated webhooks:**
A planned enhancement will add an optional `auth_token` field to trigger configurations. When a token is set, the webhook endpoint will require an `Authorization: Bearer <token>` header. Triggers without a token remain public as today. This enables secure cross-instance integration — one instance can call another's webhook with a shared secret.

## Critical: DynamicModel Has NO Relationships

`DynamicModel` tables are flat — columns only. **Do not use `.` dot-access to traverse foreign keys**. The following will **fail**:

```python
# WRONG — bug.project does not exist
for bug in session.query(Bug).all():
    name = bug.project.name
```

Instead, do explicit lookups or joins:

```python
# OPTION 1: Dict with explicit lookup
bugs_data = []
for bug in session.query(Bug).all():
    project = session.query(Project).get(bug.project_id)
    bugs_data.append({'bug': bug, 'project': project})
```

```python
# OPTION 2: Join and iterate
rows = session.query(Bug, Project).join(Project, Bug.project_id == Project.id).all()
bugs_data = [{'bug': b, 'project': p} for b, p in rows]
```

Then in a Jinja template use the dict key, not dot-chaining:
```
{% for item in bugs_data %}
  {{ item.project.name }}  {# OK — item is a dict #}
{% endfor %}
```

## Tips for AI Generation

1. **Always include CDATA** around script source code to avoid XML entity issues.
2. **Match script/form names exactly** between routes and their definitions.
3. **Keep scripts self-contained** — each script has its own execution context.
4. **Use `session`** (not `db.session`) for database operations inside scripts.
5. **Define every column you use** — `DynamicModel` only auto-adds `id`. If you query, filter, or sort by `created_at`, you must define `'created_at': db.DateTime` in the columns dict. Same for any other column.
6. **Use correct column types** — stick to `db.String(n)`, `db.Integer`, `db.Boolean`, `db.Float`, `db.DateTime`, `db.Text`, `db.Date`. SQLite does not support `db.Array`, `db.JSON`, or `db.Enum`.
7. **Use only `db.` prefixed types** — import `from app import db` and use `db.String(200)`. Do NOT import from `sqlalchemy` directly (`Column`, `Integer`, etc. will not work).
8. **Slug uniqueness** — module slugs must be unique. Suggest a slug based on the module name.
9. **Bundle standalone modules** — each XML file should be a complete, importable module.
10. **No dot-traversal across foreign keys** — DynamicModel has no relationships. Use explicit queries/joins instead.
11. **Image and file URLs** — use `/uploads/<filename>` paths. Files must be uploaded via `/__admin/uploads` first, then referenced in HTML/scripts as `<img src="/uploads/logo.png">`.
12. **No Flask URL converters** — route slugs must be exact paths like `/projects`, not `/project/<int:id>`. Use query parameters (`/project?project_id=1`) and read them in the script via `request.args.get('project_id')`. Never put `<` or `>` inside XML attribute values — they will break XML parsing.
13. **Scripts must produce output** — end every script with either `return redirect(...)`, `return jsonify(...)`, `_result = <value>`, or `render(...)`. A script that does nothing will render a blank page.
14. **Form field names must match** — `request.form.get('field_name')` in the script must match `"name":"field_name"` in the form's JSON schema exactly.
15. **Limit imports in scripts** — the script runner provides `session`, `db`, `request`, `current_user`, `redirect`, `url_for`, `flash`, `render`, `jsonify`, `send_email`, `render_form`, `DynamicModel`, `datetime`, and `timezone` already. **Do NOT import these from anywhere** — they are pre-injected into every script. There is no `app.helpers` module.
16. **Avoid Python syntax in Jinja2** — use `{% for item in items %}`, NOT `{% for i in range(len(items)) %}`. Use `{{ item.field }}`, NOT `{{ item["field"] }}`.
17. **Watch for typos** — `_result` not `_reult` or `_results`. `render` not `render_template`. `session` not `sesson`.
18. **Script runner provides common builtins** — `int`, `str`, `list`, `dict`, `len`, `range`, `enumerate`, `zip`, `sorted`, `min`, `max`, `sum`, `any`, `all`, `isinstance`, `type`, `hasattr`, `getattr`, `setattr`, `dir`, `print`, `ValueError`, `TypeError`, `KeyError`, `AttributeError` are all available. Do not import them.
19. **Only use documented helpers** — `render_form(action, method, submit_label, fields=form_fields)` renders the form with its defined fields. `form_fields` is automatically available and contains the parsed field definitions from the form's JSON schema. `send_email(to, subject, body, html=False)` sends email via admin-configured SMTP. Do not invent custom function names.
20. **No automatic timestamps** — DynamicModel tables have no `created_at` or `updated_at` unless you explicitly define them.
21. **Cross-module data** — use `DynamicModel.get_or_create("TableName", {...})` to access tables from other modules. List all columns you need. You can also query the `User` model directly: `from app.models import User` then `session.query(User).all()`.
22. **Execution timeout** — Scripts are terminated after 30 seconds by default (configurable via `script_timeout` setting). Long-running operations like bulk processing should be broken into smaller batches or designed to be idempotent so they can resume on retry. Admins can increase the timeout in Settings if needed.
23. **Route group access** — Routes can be restricted to specific user groups. When a route has groups set, the requesting user must be logged in and belong to at least one of the selected groups. If no groups are set, any authenticated user can access auth-protected routes. Use the Groups admin section to manage group membership.
24. **Debug mode** — Use the "Run Debug" button on the script edit page to execute a script and view its source code with line numbers, output, and timing. This is useful during development to test scripts without navigating to their route.
