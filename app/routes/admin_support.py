"""Admin routes for support and contact."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash

support_bp = Blueprint('support', __name__)


@support_bp.route('/support')
@admin_required
def support_page():
    """Display support information and contact details."""
    return render_admin('Support', '''
<div style="max-width:600px;margin:0 auto;">
  <h2>Support</h2>
  
  <div class="dash-card" style="margin-bottom:1rem;">
    <h3 style="margin-top:0;">Documentation</h3>
    <ul style="margin:0;padding-left:1.5rem;">
      <li><a href="/__admin/help">Help Page</a></li>
      <li><a href="/__admin/faq">FAQ</a></li>
      <li><a href="/__admin/tutorial">Tutorial</a></li>
      <li><a href="https://github.com/Nurb4000/PythonAppFoundry" target="_blank">GitHub Repository</a></li>
    </ul>
  </div>
  
  <div class="dash-card" style="margin-bottom:1rem;">
    <h3 style="margin-top:0;">Getting Help</h3>
    <p>For issues, questions, or feature requests:</p>
    <ul style="margin:0;padding-left:1.5rem;">
      <li>Check the <a href="/__admin/faq">FAQ</a> first</li>
      <li>Review the <a href="https://github.com/Nurb4000/PythonAppFoundry/issues" target="_blank">GitHub Issues</a></li>
      <li>Contact the development team</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3 style="margin-top:0;">Reporting Issues</h3>
    <p>When reporting issues, please include:</p>
    <ol style="margin:0;padding-left:1.5rem;">
      <li>Description of the problem</li>
      <li>Steps to reproduce</li>
      <li>Expected vs actual behavior</li>
      <li>Environment details (Python version, OS, etc.)</li>
      <li>Relevant log output</li>
    </ol>
  </div>
</div>
''')
