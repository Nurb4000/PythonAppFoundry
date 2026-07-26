"""Admin routes for changelog viewing."""
from flask import Blueprint, request, redirect, url_for, render_template_string

changelog_bp = Blueprint('changelog', __name__)


@changelog_bp.route('/changelog')
@admin_required
def changelog_page():
    """Display the application changelog."""
    return render_admin('Changelog', '''
<h2>PythonAppFoundry Changelog</h2>

<h3>v2.0.0 (2026-07-25)</h3>
<ul>
  <li><strong>Security Enhancements:</strong>
    <ul>
      <li>Hardened script sandbox — blocks dangerous module imports (os, subprocess, sys, socket, etc.)</li>
      <li>Webhook rate limiting (30/min, 600/hr per slug)</li>
      <li>SSL certificate verification for call_api()</li>
      <li>Settings access control — scripts cannot read sensitive keys</li>
      <li>Input validation for slugs, routes, and cron expressions</li>
      <li>XSS prevention in form preview editor</li>
    </ul>
  </li>
  <li><strong>New Features:</strong>
    <ul>
      <li>Database backup/restore with emergency backups</li>
      <li>Per-module execution history UI</li>
      <li>Inline script testing with AJAX modal</li>
      <li>XML import preview before committing</li>
      <li>Multi-tenant support (subdomain/path-based)</li>
      <li>OpenAPI 3.0 spec generation with Swagger UI</li>
      <li>Module marketplace for sharing modules</li>
      <li>Structured JSON logging</li>
      <li>Webhook retry with dead letter queue</li>
      <li>Python syntax highlighting in script editor</li>
      <li>Enhanced /healthz endpoint with database, scheduler, IMAP checks</li>
      <li>Configuration validation warnings at startup</li>
    </ul>
  </li>
  <li><strong>Architecture Improvements:</strong>
    <ul>
      <li>Split monolithic admin.py into separate blueprints</li>
      <li>Created shared admin_utils.py with common patterns</li>
      <li>Added validation.py for input sanitization</li>
      <li>Improved scheduler timeout handling for background threads</li>
      <li>Fixed race conditions in DynamicModel and credential store</li>
    </ul>
  </li>
  <li><strong>Docker Support:</strong>
    <ul>
      <li>Added Dockerfile with multi-stage build</li>
      <li>Added docker-compose.yml with PostgreSQL and llama.cpp services</li>
      <li>Added production deployment template</li>
      <li>Comprehensive .env.docker.example with all configuration options</li>
    </ul>
  </li>
</ul>

<h3>v1.0.0 (Initial Release)</h3>
<ul>
  <li>Core platform functionality</li>
  <li>Module system with XML import/export</li>
  <li>AI module generation via LLM integration</li>
  <li>BPMN workflow designer</li>
  <li>Dynamic table creation</li>
  <li>Sandboxed script execution</li>
  <li>Role-based access control</li>
  <li>Full admin panel with CRUD operations</li>
</ul>
''')
