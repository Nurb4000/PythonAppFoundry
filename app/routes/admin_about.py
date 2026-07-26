"""Admin routes for about and system information."""
from flask import Blueprint, request, redirect, url_for, render_template_string

about_bp = Blueprint('about', __name__)


@about_bp.route('/about')
@admin_required
def about_page():
    """Display about information and system details."""
    import platform
    import sys
    
    return render_admin('About', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>System Information</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Python:</strong> {{ platform.python_version() }}</li>
      <li><strong>Platform:</strong> {{ platform.platform() }}</li>
      <li><strong>Flask:</strong> {{ flask.__version__ }}</li>
      <li><strong>SQLAlchemy:</strong> {{ sqlalchemy.__version__ }}</li>
      <li><strong>APScheduler:</strong> {{ apscheduler.__version__ }}</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>Application Info</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Version:</strong> 2.0.0</li>
      <li><strong>Built:</strong> 2026-07-25</li>
      <li><strong>License:</strong> MIT</li>
      <li><strong>Author:</strong> IDS</li>
    </ul>
  </div>
</div>
''', platform=platform, flask=__import__('flask'), sqlalchemy=__import__('sqlalchemy'), apscheduler=__import__('apscheduler'))
