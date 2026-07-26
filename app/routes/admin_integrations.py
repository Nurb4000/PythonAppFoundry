"""Admin routes for integration management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

integrations_bp = Blueprint('integrations', __name__)


@integrations_bp.route('/integrations')
@admin_required
def integrations():
    """Manage third-party integrations."""
    from app.models import Setting
    
    integrations = [
        {
            'name': 'Slack',
            'enabled': bool(Setting.get('slack_webhook_url', '')),
            'config_url': url_for('admin.notification_settings'),
        },
        {
            'name': 'Discord',
            'enabled': bool(Setting.get('discord_webhook_url', '')),
            'config_url': url_for('admin.notification_settings'),
        },
        {
            'name': 'SMTP Email',
            'enabled': bool(Setting.get('smtp_host', '')) and Setting.get('smtp_host') != 'localhost',
            'config_url': url_for('admin.edit_settings'),
        },
        {
            'name': 'IMAP Email',
            'enabled': Setting.get('imap_enabled', 'false') == 'true',
            'config_url': url_for('admin.edit_settings'),
        },
        {
            'name': 'LLM (AI)',
            'enabled': bool(Setting.get('llm_provider', '')),
            'config_url': url_for('admin.edit_settings'),
        },
    ]
    
    return render_admin('Integrations', '''
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(250px, 1fr));gap:1rem;">
  {% for integration in integrations %}
  <div class="dash-card">
    <h3 style="margin-top:0;">{{ integration.name }}</h3>
    <p>Status: <span class="{% if integration.enabled %}status-ok{% else %}status-err{% endif %}">{% if integration.enabled %}Enabled{% else %}Disabled{% endif %}</span></p>
    <a href="{{ integration.config_url }}" style="font-size:0.85em;">Configure &rarr;</a>
  </div>
  {% endfor %}
</div>
''', integrations=integrations)
