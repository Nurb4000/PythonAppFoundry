"""Admin routes for extended BPMN functionality."""
from flask import Blueprint, request, redirect, url_for, render_template_string

bpmn_extended_bp = Blueprint('bpmn_extended', __name__)


@bpmn_extended_bp.route('/bpmn/<int:module_id>/export')
@login_required
def export_bpmn(module_id):
    """Export BPMN XML for a module."""
    from app.models import Module
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    if not module.bpmn_xml:
        flash('No BPMN data for this module', 'error')
        return redirect(url_for('admin.list_modules'))
    
    from flask import Response
    return Response(
        module.bpmn_xml,
        mimetype='application/xml',
        headers={'Content-Disposition': f'attachment; filename="{module.slug}_workflow.bpmn"'}
    )


@bpmn_extended_bp.route('/bpmn/<int:module_id>/import', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def import_bpmn(module_id):
    """Import BPMN XML for a module."""
    from app.models import Module
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('admin.list_modules'))
    
    file = request.files['file']
    if not file.filename.endswith('.bpmn') and not file.filename.endswith('.xml'):
        flash('Invalid file format. Please upload a .bpmn or .xml file.', 'error')
        return redirect(url_for('admin.list_modules'))
    
    try:
        bpmn_xml = file.read().decode('utf-8')
        module.bpmn_xml = bpmn_xml
        db.session.commit()
        flash(f'BPMN data imported for {module.name}')
    except Exception as e:
        flash(f'Failed to import BPMN data: {e}', 'error')
    
    return redirect(url_for('admin.list_modules'))


@bpmn_extended_bp.route('/bpmn/<int:module_id>/delete', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def delete_bpmn(module_id):
    """Delete BPMN data for a module."""
    from app.models import Module
    
    module = db.session.get(Module, module_id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    module.bpmn_xml = ''
    db.session.commit()
    flash(f'BPMN data deleted for {module.name}')
    return redirect(url_for('admin.list_modules'))
