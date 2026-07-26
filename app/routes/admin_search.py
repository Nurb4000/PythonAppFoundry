"""Admin routes for search functionality."""
from flask import Blueprint, request, redirect, url_for, render_template_string

search_bp = Blueprint('search', __name__)


@search_bp.route('/search')
@developer_or_admin_required
def search():
    """Search across modules, routes, scripts, and forms."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return render_admin('Search', '''
<form method="GET" style="max-width:600px;margin:0 auto;">
  <div style="display:flex;gap:0.5rem;">
    <input type="text" name="q" placeholder="Search modules, routes, scripts..." style="flex:1;padding:0.75rem;border:1px solid #ddd;border-radius:4px;" autofocus>
    <button type="submit" style="padding:0.75rem 1.5rem;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Search</button>
  </div>
</form>
''')
    
    from app.models import Module, Route, Script, Form
    
    # Search modules
    modules = db.session.query(Module).filter(
        db.or_(
            Module.name.ilike(f'%{query}%'),
            Module.slug.ilike(f'%{query}%'),
            Module.description.ilike(f'%{query}%'),
        )
    ).all()
    
    # Search routes
    routes = db.session.query(Route).filter(
        db.or_(
            Route.slug.ilike(f'%{query}%'),
            Route.title.ilike(f'%{query}%'),
        )
    ).all()
    
    # Search scripts
    scripts = db.session.query(Script).filter(
        db.or_(
            Script.name.ilike(f'%{query}%'),
            Script.description.ilike(f'%{query}%'),
        )
    ).all()
    
    # Search forms
    forms = db.session.query(Form).filter(
        Form.name.ilike(f'%{query}%')
    ).all()
    
    return render_admin('Search Results', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Search Results for "{{ query }}"</h2>
  
  {% if modules %}
  <h3>Modules ({{ modules|length }})</h3>
  <div class="table-wrap">
  <table>
  <thead><tr><th>Name</th><th>Slug</th><th>Actions</th></tr></thead>
  <tbody>
  {% for m in modules %}
  <tr>
    <td>{{ m.name }}</td>
    <td><code>{{ m.slug }}</code></td>
    <td><a href="{{ url_for('admin.edit_module', id=m.id) }}">Edit</a></td>
  </tr>
  {% endfor %}
  </tbody></table>
  </div>
  {% endif %}
  
  {% if routes %}
  <h3>Routes ({{ routes|length }})</h3>
  <div class="table-wrap">
  <table>
  <thead><tr><th>Slug</th><th>Title</th><th>Module</th><th>Actions</th></tr></thead>
  <tbody>
  {% for r in routes %}
  <tr>
    <td><code>{{ r.slug }}</code></td>
    <td>{{ r.title }}</td>
    <td>{{ r.module.name if r.module else '—' }}</td>
    <td><a href="{{ url_for('admin.edit_route', id=r.id) }}">Edit</a></td>
  </tr>
  {% endfor %}
  </tbody></table>
  </div>
  {% endif %}
  
  {% if scripts %}
  <h3>Scripts ({{ scripts|length }})</h3>
  <div class="table-wrap">
  <table>
  <thead><tr><th>Name</th><th>Module</th><th>Actions</th></tr></thead>
  <tbody>
  {% for s in scripts %}
  <tr>
    <td>{{ s.name }}</td>
    <td>{{ s.module.name if s.module else '—' }}</td>
    <td><a href="{{ url_for('admin.edit_script', id=s.id) }}">Edit</a></td>
  </tr>
  {% endfor %}
  </tbody></table>
  </div>
  {% endif %}
  
  {% if forms %}
  <h3>Forms ({{ forms|length }})</h3>
  <div class="table-wrap">
  <table>
  <thead><tr><th>Name</th><th>Module</th><th>Actions</th></tr></thead>
  <tbody>
  {% for f in forms %}
  <tr>
    <td>{{ f.name }}</td>
    <td>{{ f.module.name if f.module else '—' }}</td>
    <td><a href="{{ url_for('admin.edit_form', id=f.id) }}">Edit</a></td>
  </tr>
  {% endfor %}
  </tbody></table>
  </div>
  {% endif %}
  
  {% if not modules and not routes and not scripts and not forms %}
  <p style="color:#888;">No results found.</p>
  {% endif %}
</div>
''', query=query, modules=modules, routes=routes, scripts=scripts, forms=forms)
