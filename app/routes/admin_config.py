"""Admin routes for configuration validation."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

config_bp = Blueprint('config', __name__)


@config_bp.route('/config-check')
@admin_required
def config_check():
    """Check configuration and display warnings."""
    import os
    
    warnings = []
    info = []
    
    # Check SECRET_KEY
    secret_key = os.environ.get('SECRET_KEY', '')
    if not secret_key or secret_key == 'change-this-in-production':
        warnings.append('SECRET_KEY is using the default value. Set a strong random SECRET_KEY in your .env file for production.')
    else:
        info.append('SECRET_KEY is configured.')
    
    # Check DATABASE_URL
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        warnings.append('DATABASE_URL not set. Using default SQLite.')
    elif 'postgresql' in db_url:
        info.append('Using PostgreSQL database.')
    else:
        info.append(f'Database URL configured: {db_url[:50]}...')
    
    # Check LLM settings
    llm_provider = Setting.get('llm_provider', 'llamacpp')
    if llm_provider == 'openai':
        llm_api_key = Setting.get('llm_api_key', '')
        if not llm_api_key:
            warnings.append('OpenAI provider selected but API key not configured.')
        else:
            info.append('OpenAI API key configured.')
    elif llm_provider == 'llamacpp':
        llm_endpoint = Setting.get('llm_endpoint', '')
        if not llm_endpoint:
            warnings.append('llama.cpp endpoint not configured.')
        else:
            info.append(f'llama.cpp endpoint: {llm_endpoint}')
    
    # Check SMTP settings
    smtp_host = Setting.get('smtp_host', 'localhost')
    if smtp_host == 'localhost':
        warnings.append('SMTP host is localhost. Configure a valid SMTP server for production.')
    else:
        info.append(f'SMTP host: {smtp_host}')
    
    # Check IMAP settings
    imap_enabled = Setting.get('imap_enabled', 'false')
    if imap_enabled == 'true':
        imap_host = Setting.get('imap_host', '')
        if not imap_host:
            warnings.append('IMAP enabled but host not configured.')
        else:
            info.append(f'IMAP host: {imap_host}')
    
    return render_admin('Configuration Check', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;">
  <div>
    <h3>Warnings</h3>
    {% if warnings %}
    {% for w in warnings %}
    <div style="background:#fff3cd;border:1px solid #ffc107;padding:0.75rem;border-radius:4px;margin-bottom:0.5rem;">
      {{ w }}
    </div>
    {% endfor %}
    {% else %}
    <p style="color:#888;">No warnings.</p>
    {% endif %}
  </div>
  
  <div>
    <h3>Information</h3>
    {% if info %}
    {% for i in info %}
    <div style="background:#d4edda;border:1px solid #c3e6cb;padding:0.75rem;border-radius:4px;margin-bottom:0.5rem;">
      {{ i }}
    </div>
    {% endfor %}
    {% else %}
    <p style="color:#888;">No information available.</p>
    {% endif %}
  </div>
</div>
''', warnings=warnings, info=info)
