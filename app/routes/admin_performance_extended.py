"""Admin routes for extended performance monitoring."""
from flask import Blueprint, request, redirect, url_for, render_template_string

performance_extended_bp = Blueprint('performance_extended', __name__)


@performance_extended_bp.route('/performance/slow-queries')
@admin_required
def slow_queries():
    """View slow database queries."""
    # This would typically track slow queries
    # For now, show a placeholder
    return render_admin('Slow Queries', '''
<p style="color:#666;">Slow query tracking is not yet implemented. This feature will identify and log slow database queries for optimization.</p>
''')


@performance_extended_bp.route('/performance/memory-usage')
@admin_required
def memory_usage():
    """View memory usage statistics."""
    import psutil
    
    memory = psutil.virtual_memory()
    
    return render_admin('Memory Usage', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>Memory Statistics</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Total:</strong> {{ '%.1f GB'|format(memory.total / 1073741824) }}</li>
      <li><strong>Used:</strong> {{ '%.1f GB'|format(memory.used / 1073741824) }}</li>
      <li><strong>Available:</strong> {{ '%.1f GB'|format(memory.available / 1073741824) }}</li>
      <li><strong>Percent Used:</strong> {{ memory.percent }}%</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>Recommendations</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li>If memory usage is consistently above 80%, consider optimizing your application.</li>
      <li>Monitor for memory leaks in long-running processes.</li>
      <li>Consider using a memory profiler for detailed analysis.</li>
    </ul>
  </div>
</div>
''', memory=memory)


@performance_extended_bp.route('/performance/cpu-usage')
@admin_required
def cpu_usage():
    """View CPU usage statistics."""
    import psutil
    
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    
    return render_admin('CPU Usage', '''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
  <div class="dash-card">
    <h3>CPU Statistics</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li><strong>Current Usage:</strong> {{ cpu_percent }}%</li>
      <li><strong>Core Count:</strong> {{ cpu_count }}</li>
    </ul>
  </div>
  
  <div class="dash-card">
    <h3>Recommendations</h3>
    <ul style="margin:0;padding-left:1.5rem;line-height:1.8;">
      <li>If CPU usage is consistently above 80%, consider optimizing your application.</li>
      <li>Monitor for CPU-intensive operations that could be offloaded.</li>
      <li>Consider using async processing for long-running tasks.</li>
    </ul>
  </div>
</div>
''', cpu_percent=cpu_percent, cpu_count=cpu_count)
