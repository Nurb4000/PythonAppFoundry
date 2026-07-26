"""Admin routes for terms of service."""
from flask import Blueprint, request, redirect, url_for, render_template_string

terms_bp = Blueprint('terms', __name__)


@terms_bp.route('/terms')
@admin_required
def terms_page():
    """Display terms of service."""
    return render_admin('Terms of Service', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Terms of Service</h2>
  
  <div class="dash-card">
    <h3>Acceptance of Terms</h3>
    <p>By using PythonAppFoundry, you agree to these terms. If you do not agree, do not use the platform.</p>
  </div>
  
  <div class="dash-card" style="margin-top:1rem;">
    <h3>Use of Platform</h3>
    <p>You are responsible for:</p>
    <ul style="margin:0;padding-left:1.5rem;">
      <li>Complying with all applicable laws</li>
      <li>Securing your account and credentials</li>
      <li>Not using the platform for illegal activities</li>
      <li>Not attempting to compromise platform security</li>
    </ul>
  </div>
  
  <div class="dash-card" style="margin-top:1rem;">
    <h3>Intellectual Property</h3>
    <p>Modules and content created by users remain the property of their creators. The platform itself is licensed under MIT.</p>
  </div>
  
  <div class="dash-card" style="margin-top:1rem;">
    <h3>Limitation of Liability</h3>
    <p>The platform is provided "as is" without warranties. Users assume all risks associated with using the platform.</p>
  </div>
</div>
''')
