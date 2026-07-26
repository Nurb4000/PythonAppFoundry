"""Admin routes for extended route management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

route_extended_bp = Blueprint('route_extended', __name__)


@route_extended_bp.route('/routes/<int:id>/test')
@developer_or_admin_required
def test_route(id):
    """Test a route by visiting it."""
    from app.models import Route
    
    route = db.session.get(Route, id)
    if not route:
        flash('Route not found', 'error')
        return redirect(url_for('admin.list_routes'))
    
    # Visit the route
    with current_app.test_client() as client:
        response = client.get(route.slug)
        status_code = response.status_code
    
    flash(f'Route tested. Status: {status_code}')
    return redirect(url_for('admin.list_routes'))


@route_extended_bp.route('/routes/bulk-enable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_enable_routes():
    """Enable multiple routes at once."""
    from app.models import Route
    
    route_ids = request.form.getlist('route_ids')
    enabled = 0
    for rid in route_ids:
        route = db.session.get(Route, int(rid))
        if route and route.module:
            route.module.enabled = True
            enabled += 1
    
    db.session.commit()
    flash(f'Enabled {enabled} route(s)')
    return redirect(url_for('admin.list_routes'))


@route_extended_bp.route('/routes/bulk-disable', methods=['POST'])
@admin_required
@csrf_protect
def bulk_disable_routes():
    """Disable multiple routes at once."""
    from app.models import Route
    
    route_ids = request.form.getlist('route_ids')
    disabled = 0
    for rid in route_ids:
        route = db.session.get(Route, int(rid))
        if route and route.module and not route.module.is_system:
            route.module.enabled = False
            disabled += 1
    
    db.session.commit()
    flash(f'Disabled {disabled} route(s)')
    return redirect(url_for('admin.list_routes'))
