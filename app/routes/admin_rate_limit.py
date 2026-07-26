"""Admin routes for rate limit monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string

rate_limit_bp = Blueprint('rate_limit', __name__)


@rate_limit_bp.route('/rate-limits')
@admin_required
def rate_limits():
    """View current rate limiting status."""
    from app.services.rate_limiter import _rate_limiter, _webhook_limiter
    
    auth_attempts = {}
    for key, timestamps in _rate_limiter.attempts.items():
        auth_attempts[key] = {
            'count': len(timestamps),
            'window': _rate_limiter.window_seconds,
            'max': _rate_limiter.max_attempts,
        }
    
    webhook_attempts = {}
    for key, timestamps in _webhook_limiter.recent.items():
        webhook_attempts[key] = {
            'minute_count': len(timestamps),
            'hourly_count': len(_webhook_limiter.hourly.get(key, [])),
            'max_per_minute': _webhook_limiter.max_per_minute,
            'max_per_hour': _webhook_limiter.max_per_hour,
        }
    
    return render_admin('Rate Limits', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div>
    <h3>Auth Endpoints</h3>
    {% if auth_attempts %}
    <div class="table-wrap">
    <table>
    <thead><tr>
      <th>Key</th>
      <th>Attempts</th>
      <th>Window</th>
      <th>Limit</th>
    </tr></thead>
    <tbody>
    {% for key, data in auth_attempts.items() %}
    <tr>
      <td><code>{{ key }}</code></td>
      <td>{{ data.count }}</td>
      <td>{{ data.window }}s</td>
      <td>{{ data.max }}</td>
    </tr>
    {% endfor %}
    </tbody></table>
    </div>
    {% else %}
    <p style="color:#888;">No recent auth attempts.</p>
    {% endif %}
  </div>
  
  <div>
    <h3>Webhook Endpoints</h3>
    {% if webhook_attempts %}
    <div class="table-wrap">
    <table>
    <thead><tr>
      <th>Key</th>
      <th>Min</th>
      <th>Hour</th>
      <th>Limit (min/hr)</th>
    </tr></thead>
    <tbody>
    {% for key, data in webhook_attempts.items() %}
    <tr>
      <td><code>{{ key }}</code></td>
      <td>{{ data.minute_count }}</td>
      <td>{{ data.hourly_count }}</td>
      <td>{{ data.max_per_minute }}/{{ data.max_per_hour }}</td>
    </tr>
    {% endfor %}
    </tbody></table>
    </div>
    {% else %}
    <p style="color:#888;">No recent webhook attempts.</p>
    {% endif %}
  </div>
</div>
''', auth_attempts=auth_attempts, webhook_attempts=webhook_attempts)
