"""Admin routes for extended webhook functionality."""
from flask import Blueprint, request, redirect, url_for, render_template_string

webhook_extended_bp = Blueprint('webhook_extended', __name__)


@webhook_extended_bp.route('/webhooks')
@admin_required
def webhook_list():
    """List all configured webhooks."""
    from app.models import Trigger
    
    webhooks = db.session.query(Trigger).filter_by(event_type='webhook').all()
    
    return render_admin('Webhooks', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;">
  <a href="{{ url_for('admin.new_trigger') }}?event_type=webhook">+ New Webhook</a>
</div>
{% if webhooks %}
<div class="table-wrap">
<table>
<thead><tr>
  <th>Name</th>
  <th>Slug</th>
  <th>Module</th>
  <th>Auth Token</th>
  <th>Status</th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for w in webhooks %}
<tr>
  <td>{{ w.name }}</td>
  <td><code>/__api/webhook/{{ w.target_table }}</code></td>
  <td>{{ w.module.name if w.module else '—' }}</td>
  <td>{% if w.auth_token %}Configured{% else %}None{% endif %}</td>
  <td><span class="status-ok">Active</span></td>
  <td>
    <a href="{{ url_for('admin.edit_trigger', id=w.id) }}">Edit</a>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% else %}
<p style="color:#888;">No webhooks configured.</p>
{% endif %}''', webhooks=webhooks)
