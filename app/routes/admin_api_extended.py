"""Admin routes for extended API functionality."""
from flask import Blueprint, request, redirect, url_for, jsonify

api_extended_bp = Blueprint('api_extended', __name__)


@api_extended_bp.route('/api/modules/<slug>/export')
@login_required
def api_export_module(slug):
    """Export a module as XML via API."""
    from app.models import Module
    from app.services.bundle import export_module
    
    module = db.session.query(Module).filter_by(slug=slug).first()
    if not module:
        return jsonify({'error': 'Module not found'}), 404
    
    xml_str = export_module(module)
    
    from flask import Response
    return Response(
        xml_str,
        mimetype='application/xml',
        headers={'Content-Disposition': f'attachment; filename="{module.slug}.xml"'}
    )


@api_extended_bp.route('/api/modules/import', methods=['POST'])
@login_required
def api_import_module():
    """Import a module via API."""
    from app.services.bundle import import_module
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    xml_file = request.files['file']
    if not xml_file.filename:
        return jsonify({'error': 'Empty filename'}), 400
    
    try:
        xml_str = xml_file.read().decode('utf-8')
        module = import_module(xml_str)
        return jsonify({
            'message': f'Module "{module.name}" imported successfully',
            'slug': module.slug,
            'id': module.id,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_extended_bp.route('/api/modules')
@login_required
def api_list_modules():
    """List all modules via API."""
    from app.models import Module
    
    modules = db.session.query(Module).all()
    
    return jsonify([{
        'id': m.id,
        'name': m.name,
        'slug': m.slug,
        'version': m.version,
        'author': m.author,
        'enabled': m.enabled,
        'created_at': m.created_at.isoformat() if m.created_at else None,
        'updated_at': m.updated_at.isoformat() if m.updated_at else None,
    } for m in modules])


@api_extended_bp.route('/api/health')
def api_health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})
