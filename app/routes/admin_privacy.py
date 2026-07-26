"""Admin routes for privacy policy."""
from flask import Blueprint, request, redirect, url_for, render_template_string

privacy_bp = Blueprint('privacy', __name__)


@privacy_bp.route('/privacy')
@admin_required
def privacy_page():
    """Display privacy policy information."""
    return render_admin('Privacy Policy', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Privacy Policy</h2>
  
  <div class="dash-card">
    <h3>Data Collection</h3>
    <p>PythonAppFoundry collects minimal data for platform functionality:</p>
    <ul style="margin:0;padding-left:1.5rem;">
      <li>User accounts (username, password hash, role)</li>
      <li>Module data (routes, scripts, forms, tasks)</li>
      <li>Execution logs (for monitoring and debugging)</li>
      <li>Upload metadata (filenames, sizes, MIME types)</li>
    </ul>
  </div>
  
  <div class="dash-card" style="margin-top:1rem;">
    <h3>Data Storage</h3>
    <p>All data is stored in the application database (SQLite or PostgreSQL). Backups can be created via the admin panel.</p>
  </div>
  
  <div class="dash-card" style="margin-top:1rem;">
    <h3>Credentials Security</h3>
    <p>Credentials (API keys, tokens) are encrypted at rest using Fernet encryption. The encryption key is stored in instance/credential.key with restricted permissions (0600).</p>
  </div>
  
  <div class="dash-card" style="margin-top:1rem;">
    <h3>User Responsibilities</h3>
    <p>Users are responsible for:</p>
    <ul style="margin:0;padding-left:1.5rem;">
      <li>Keeping their credentials secure</li>
      <li>Not sharing API keys or tokens</li>
      <li>Following platform security guidelines</li>
    </ul>
  </div>
</div>
''')
