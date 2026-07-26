"""Admin routes for extended query management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

query_extended_bp = Blueprint('query_extended', __name__)


@query_extended_bp.route('/queries/<int:id>/enable')
@developer_or_admin_required
def enable_query(id):
    """Enable a query report."""
    from app.models import QueryReport
    
    query = db.session.get(QueryReport, id)
    if not query:
        flash('Query not found', 'error')
        return redirect(url_for('admin.list_queries'))
    
    # Enable by setting schedule_cron if empty
    if not query.schedule_cron:
        query.schedule_cron = '*/5 * * * *'  # Every 5 minutes
        db.session.commit()
        flash(f'Query "{query.name}" enabled (scheduled every 5 minutes)')
    else:
        flash(f'Query "{query.name}" is already enabled')
    
    return redirect(url_for('admin.list_queries'))


@query_extended_bp.route('/queries/<int:id>/disable')
@developer_or_admin_required
def disable_query(id):
    """Disable a query report."""
    from app.models import QueryReport
    
    query = db.session.get(QueryReport, id)
    if not query:
        flash('Query not found', 'error')
        return redirect(url_for('admin.list_queries'))
    
    query.schedule_cron = ''
    db.session.commit()
    flash(f'Query "{query.name}" disabled')
    return redirect(url_for('admin.list_queries'))


@query_extended_bp.route('/queries/<int:id>/test')
@developer_or_admin_required
def test_query(id):
    """Test a query report."""
    from app.models import QueryReport
    
    query = db.session.get(QueryReport, id)
    if not query:
        flash('Query not found', 'error')
        return redirect(url_for('admin.list_queries'))
    
    try:
        result = db.session.execute(db.text(query.sql))
        columns = list(result.keys())
        rows = result.fetchall()
        flash(f'Query executed successfully. {len(rows)} row(s) returned.')
    except Exception as e:
        flash(f'Query failed: {e}', 'error')
    
    return redirect(url_for('admin.edit_query', id=id))
