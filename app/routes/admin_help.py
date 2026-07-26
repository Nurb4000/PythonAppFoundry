"""Admin routes for help and documentation."""
from flask import Blueprint, request, redirect, url_for, render_template_string

help_bp = Blueprint('help', __name__)


@help_bp.route('/help')
@developer_or_admin_required
def help_page():
    """Display help documentation and quick reference."""
    return render_admin('Help', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div>
    <h3>Quick Links</h3>
    <ul style="margin:0;padding-left:1.5rem;">
      <li><a href="{{ url_for('admin.list_modules') }}">Modules</a></li>
      <li><a href="{{ url_for('admin.list_routes') }}">Routes</a></li>
      <li><a href="{{ url_for('admin.list_scripts') }}">Scripts</a></li>
      <li><a href="{{ url_for('admin.list_forms') }}">Forms</a></li>
      <li><a href="{{ url_for('admin.list_tasks') }}">Tasks</a></li>
      <li><a href="{{ url_for('admin.list_triggers') }}">Triggers</a></li>
      <li><a href="{{ url_for('admin.list_users') }}">Users</a></li>
      <li><a href="{{ url_for('admin.list_groups') }}">Groups</a></li>
      <li><a href="{{ url_for('admin.list_tables') }}">Data Browser</a></li>
      <li><a href="{{ url_for('admin.list_uploads') }}">Uploads</a></li>
      <li><a href="{{ url_for('admin.list_queries') }}">Queries</a></li>
      <li><a href="{{ url_for('admin.list_credentials') }}">Credentials</a></li>
      <li><a href="{{ url_for('admin.list_incoming_emails') }}">Incoming Email</a></li>
      <li><a href="{{ url_for('admin.admin_packages') }}">Packages</a></li>
      <li><a href="{{ url_for('admin.edit_settings') }}">Settings</a></li>
      <li><a href="{{ url_for('admin.dashboard') }}">Dashboard</a></li>
    </ul>
  </div>
  
  <div>
    <h3>Documentation</h3>
    <ul style="margin:0;padding-left:1.5rem;">
      <li><a href="/__api/openapi.json" target="_blank">OpenAPI Spec (JSON)</a></li>
      <li><a href="/__api/swagger" target="_blank">Swagger UI</a></li>
      <li><a href="https://github.com/Nurb4000/PythonAppFoundry" target="_blank">GitHub Repository</a></li>
      <li><a href="/static/AI_GUIDE.md" target="_blank">AI Module Generation Guide</a></li>
      <li><a href="/static/ADMIN_AND_DEVELOPER_GUIDE.md" target="_blank">Admin & Developer Guide</a></li>
    </ul>
  </div>
</div>
''')
