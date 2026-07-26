"""Admin routes for quickstart wizard."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

quickstart_bp = Blueprint('quickstart', __name__)


@quickstart_bp.route('/quickstart')
@admin_required
def quickstart():
    """Guided setup wizard for new installations."""
    from app.models import Setting
    
    steps = []
    
    # Step 1: Site configuration
    site_name = Setting.get('site_name', '')
    steps.append({
        'id': 1,
        'title': 'Site Configuration',
        'description': 'Set your site name and basic settings.',
        'completed': bool(site_name),
        'url': url_for('admin.edit_settings'),
    })
    
    # Step 2: LLM configuration (optional)
    llm_provider = Setting.get('llm_provider', '')
    steps.append({
        'id': 2,
        'title': 'AI Module Generation (Optional)',
        'description': 'Configure an LLM provider for AI module generation.',
        'completed': bool(llm_provider),
        'url': url_for('admin.edit_settings'),
    })
    
    # Step 3: SMTP configuration (optional)
    smtp_host = Setting.get('smtp_host', 'localhost')
    steps.append({
        'id': 3,
        'title': 'Email Configuration (Optional)',
        'description': 'Configure SMTP for sending emails from scripts.',
        'completed': smtp_host != 'localhost',
        'url': url_for('admin.edit_settings'),
    })
    
    # Step 4: Import demo module
    from app.models import Module
    demo_count = db.session.query(db.func.count(Module.id)).filter(Module.slug == 'demo').scalar()
    steps.append({
        'id': 4,
        'title': 'Import Demo Module',
        'description': 'Import a demo module to explore the platform.',
        'completed': bool(demo_count),
        'url': url_for('admin.new_module'),
    })
    
    # Step 5: Create first module
    module_count = db.session.query(db.func.count(Module.id)).scalar()
    steps.append({
        'id': 5,
        'title': 'Create Your First Module',
        'description': 'Start building your application.',
        'completed': module_count > 0,
        'url': url_for('admin.new_module'),
    })
    
    return render_admin('Quickstart Wizard', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Welcome to PythonAppFoundry!</h2>
  <p style="color:#666;margin-bottom:2rem;">This wizard will help you get started with the platform.</p>
  
  <div style="display:flex;flex-direction:column;gap:1rem;">
    {% for step in steps %}
    <div style="border:1px solid #ddd;border-radius:8px;padding:1rem;{% if step.completed %}background:#f0fff0;border-color:#080;{% endif %}">
      <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
        <span style="font-size:1.2em;">{% if step.completed %}✅{% else %}⬜{% endif %}</span>
        <h3 style="margin:0;">Step {{ step.id }}: {{ step.title }}</h3>
      </div>
      <p style="color:#666;margin:0 0 0.75rem 2rem;">{{ step.description }}</p>
      {% if not step.completed %}
      <a href="{{ step.url }}" style="display:inline-block;padding:0.5rem 1rem;background:#2563eb;color:#fff;text-decoration:none;border-radius:4px;">Get Started</a>
      {% else %}
      <span style="color:#080;font-weight:bold;">Completed</span>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  
  {% if steps|selectattr('completed')|list|length == steps|length %}
  <div style="margin-top:2rem;padding:1.5rem;background:#d4edda;border:1px solid #c3e6cb;border-radius:8px;text-align:center;">
    <h3 style="margin-top:0;color:#155724;">🎉 All Steps Complete!</h3>
    <p>You're ready to start building. Visit the <a href="{{ url_for('admin.list_modules') }}">Modules</a> page to begin.</p>
  </div>
  {% endif %}
</div>
''', steps=steps)
