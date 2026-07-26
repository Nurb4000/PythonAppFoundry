"""Admin routes for statistics."""
from flask import Blueprint, request, redirect, url_for, render_template_string

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/stats')
@admin_required
def statistics():
    """Display platform statistics and analytics."""
    from app.models import Module, Route, Script, Form, ScheduledTask, Trigger, User, Upload, ExecutionLog
    
    stats = {
        'modules': Module.query.count(),
        'enabled_modules': Module.query.filter_by(enabled=True).count(),
        'routes': Route.query.count(),
        'scripts': Script.query.count(),
        'forms': Form.query.count(),
        'tasks': ScheduledTask.query.count(),
        'enabled_tasks': ScheduledTask.query.filter_by(enabled=True).count(),
        'triggers': Trigger.query.count(),
        'enabled_triggers': Trigger.query.filter_by(enabled=True).count(),
        'users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True, is_approved=True).count(),
        'uploads': Upload.query.count(),
        'total_executions': ExecutionLog.query.count(),
        'successful_executions': ExecutionLog.query.filter_by(status='success').count(),
        'failed_executions': ExecutionLog.query.filter_by(status='error').count(),
    }
    
    return render_admin('Statistics', '''
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:1rem;">
  <div class="dash-card">
    <h3>Modules</h3>
    <div class="value">{{ stats.modules }}</div>
    <div class="sub">{{ stats.enabled_modules }} enabled</div>
  </div>
  <div class="dash-card">
    <h3>Routes</h3>
    <div class="value">{{ stats.routes }}</div>
  </div>
  <div class="dash-card">
    <h3>Scripts</h3>
    <div class="value">{{ stats.scripts }}</div>
  </div>
  <div class="dash-card">
    <h3>Forms</h3>
    <div class="value">{{ stats.forms }}</div>
  </div>
  <div class="dash-card">
    <h3>Scheduled Tasks</h3>
    <div class="value">{{ stats.tasks }}</div>
    <div class="sub">{{ stats.enabled_tasks }} enabled</div>
  </div>
  <div class="dash-card">
    <h3>Triggers</h3>
    <div class="value">{{ stats.triggers }}</div>
    <div class="sub">{{ stats.enabled_triggers }} enabled</div>
  </div>
  <div class="dash-card">
    <h3>Users</h3>
    <div class="value">{{ stats.users }}</div>
    <div class="sub">{{ stats.active_users }} active</div>
  </div>
  <div class="dash-card">
    <h3>Uploads</h3>
    <div class="value">{{ stats.uploads }}</div>
  </div>
  <div class="dash-card">
    <h3>Total Executions</h3>
    <div class="value">{{ stats.total_executions }}</div>
  </div>
  <div class="dash-card">
    <h3>Successful</h3>
    <div class="value" style="color:#080;">{{ stats.successful_executions }}</div>
  </div>
  <div class="dash-card">
    <h3>Failed</h3>
    <div class="value" style="color:#c00;">{{ stats.failed_executions }}</div>
  </div>
</div>
''', stats=stats)
