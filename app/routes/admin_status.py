"""Admin routes for system status."""
from flask import Blueprint, request, redirect, url_for, render_template_string

status_bp = Blueprint('status', __name__)


@status_bp.route('/status')
@admin_required
def system_status():
    """Display system status and health information."""
    from app.services.scheduler import _scheduler
    
    status = {
        'app': 'running',
        'scheduler': 'stopped',
        'database': 'unknown',
        'imap': 'disabled',
    }
    
    # Check scheduler
    if _scheduler is not None:
        status['scheduler'] = f'running ({len(_scheduler.get_jobs())} jobs)'
    
    # Check database
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        status['database'] = 'connected'
    except Exception as e:
        status['database'] = f'error: {e}'
    
    # Check IMAP
    from app.models import Setting
    if Setting.get('imap_enabled', 'false') == 'true':
        status['imap'] = 'enabled'
    
    return render_admin('System Status', '''
<div style="max-width:600px;margin:0 auto;">
  <h2>System Status</h2>
  
  <div class="dash-card" style="margin-bottom:1rem;">
    <h3 style="margin-top:0;">Service Status</h3>
    <table style="width:100%;">
      <tr>
        <td style="padding:0.5rem;"><strong>Application</strong></td>
        <td style="padding:0.5rem;">{{ status.app }}</td>
      </tr>
      <tr>
        <td style="padding:0.5rem;"><strong>Scheduler</strong></td>
        <td style="padding:0.5rem;">{{ status.scheduler }}</td>
      </tr>
      <tr>
        <td style="padding:0.5rem;"><strong>Database</strong></td>
        <td style="padding:0.5rem;">{{ status.database }}</td>
      </tr>
      <tr>
        <td style="padding:0.5rem;"><strong>IMAP</strong></td>
        <td style="padding:0.5rem;">{{ status.imap }}</td>
      </tr>
    </table>
  </div>
  
  <div class="dash-card">
    <h3 style="margin-top:0;">Uptime</h3>
    <p style="margin:0;">Application has been running since startup.</p>
  </div>
</div>
''', status=status)
