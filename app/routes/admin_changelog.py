"""Admin routes for changelog."""
from flask import Blueprint, request, redirect, url_for, render_template_string

changelog_bp = Blueprint('changelog', __name__)


@changelog_bp.route('/changelog')
@admin_required
def changelog():
    """Display the application changelog."""
    return render_admin('Changelog', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Changelog</h2>
  
  <div class="dash-card" style="margin-bottom:1rem;">
    <h3>v2.0.0 (2026-07-25)</h3>
    <ul style="margin:0;padding-left:1.5rem;">
      <li><strong>Security:</strong> Hardened script sandbox, webhook rate limiting, TLS verification, settings access control</li>
      <li><strong>Features:</strong> Database backup/restore, per-module execution history, inline script testing, XML import preview, multi-tenant support, OpenAPI spec, module marketplace, structured logging, webhook retry/dead-letter, syntax highlighting</li>
      <li><strong>Architecture:</strong> Split admin.py into blueprints, added validation utilities, enhanced health check</li>
      <li><strong>Docker:</strong> Added Dockerfile, docker-compose.yml, production template, .env.example</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>v1.0.0 (Initial Release)</h3>
    <ul style="margin:0;padding-left:1.5rem;">
      <li>Core platform functionality</li>
      <li>Module system with XML import/export</li>
      <li>AI module generation via LLM integration</li>
      <li>BPMN workflow designer</li>
      <li>Dynamic table creation</li>
      <li>Sandboxed script execution</li>
      <li>Role-based access control</li>
      <li>Full admin panel with CRUD operations</li>
    </ul>
  </div>
</div>
''')
