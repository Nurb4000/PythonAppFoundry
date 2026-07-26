"""Admin routes for credential store management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

credential_store_bp = Blueprint('credential_store', __name__)


@credential_store_bp.route('/credential-store')
@admin_required
def credential_store_status():
    """View credential store status and encryption key info."""
    from app.services.credential_store import _get_key_path
    import os
    
    key_path = _get_key_path(current_app)
    key_exists = os.path.exists(key_path)
    key_permissions = None
    key_size = None
    
    if key_exists:
        stat = os.stat(key_path)
        key_permissions = oct(stat.st_mode)[-3:]
        key_size = stat.st_size
    
    return render_admin('Credential Store', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>Encryption Key</h3>
    <p><strong>Path:</strong> <code>{{ key_path }}</code></p>
    <p><strong>Exists:</strong> {% if key_exists %}Yes{% else %}No{% endif %}</p>
    {% if key_exists %}
    <p><strong>Permissions:</strong> {{ key_permissions }}</p>
    <p><strong>Size:</strong> {{ key_size }} bytes</p>
    {% endif %}
  </div>
  
  <div class="dash-card">
    <h3>Security Notes</h3>
    <ul style="margin:0;padding-left:1.5rem;">
      <li>The encryption key is stored in <code>instance/credential.key</code></li>
      <li>Key file permissions should be <code>600</code> (owner read/write only)</li>
      <li>If the key file is lost, all credentials become unrecoverable</li>
      <li>Back up the key file regularly along with your database</li>
    </ul>
  </div>
</div>
''', key_path=key_path, key_exists=key_exists, key_permissions=key_permissions, key_size=key_size)
