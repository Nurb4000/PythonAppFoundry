"""Admin routes for interactive tutorials."""
from flask import Blueprint, request, redirect, url_for, render_template_string

tutorial_bp = Blueprint('tutorial', __name__)


@tutorial_bp.route('/tutorial')
@developer_or_admin_required
def tutorial():
    """Interactive tutorial for new users."""
    steps = [
        {
            'title': 'Welcome to PythonAppFoundry!',
            'content': 'This platform lets you build web applications by creating modules with routes, scripts, and forms — all stored in a database.',
        },
        {
            'title': 'Step 1: Create a Module',
            'content': 'Modules are self-contained bundles of functionality. Each module has its own routes, scripts, and forms.',
            'action': url_for('admin.new_module'),
        },
        {
            'title': 'Step 2: Add a Route',
            'content': 'Routes map URL paths to scripts. For example, "/" could map to a home page script.',
            'action': url_for('admin.new_route'),
        },
        {
            'title': 'Step 3: Write a Script',
            'content': 'Scripts are Python code that runs when a route is visited. They can query databases, render HTML, and more.',
            'action': url_for('admin.new_script'),
        },
        {
            'title': 'Step 4: Test Your Module',
            'content': 'Once your module is set up, visit the route URL to see it in action!',
        },
    ]
    
    return render_admin('Tutorial', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Interactive Tutorial</h2>
  
  {% for step in steps %}
  <div style="border:1px solid #ddd;border-radius:8px;padding:1.5rem;margin-bottom:1rem;">
    <h3 style="margin-top:0;">{{ loop.index }}. {{ step.title }}</h3>
    <p style="color:#666;">{{ step.content }}</p>
    {% if step.action %}
    <a href="{{ step.action }}" style="display:inline-block;padding:0.5rem 1rem;background:#2563eb;color:#fff;text-decoration:none;border-radius:4px;">Go to {{ step.title.split(': ')[1] if ':' in step.title else 'Page' }}</a>
    {% endif %}
  </div>
  {% endfor %}
  
  <div style="text-align:center;margin-top:2rem;">
    <a href="{{ url_for('admin.list_modules') }}" style="padding:0.75rem 2rem;background:#6c757d;color:#fff;text-decoration:none;border-radius:4px;">Skip Tutorial</a>
  </div>
</div>
''', steps=steps)
