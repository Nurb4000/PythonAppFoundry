from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import Module, Route, Script, Form, ScheduledTask, Trigger
from app.services.bundle import export_module, import_module

api_bp = Blueprint('api', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role != 'admin':
            return jsonify({'error': 'Admin required'}), 403
        return f(*a, **kw)
    return wrapper


@api_bp.route('/modules/<slug>/export', methods=['GET'])
@admin_required
def api_export(slug):
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


@api_bp.route('/modules/import', methods=['POST'])
@admin_required
def api_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    xml_file = request.files['file']
    if not xml_file.filename:
        return jsonify({'error': 'Empty filename'}), 400
    try:
        module = import_module(xml_file.read().decode('utf-8'))
        return jsonify({
            'message': f'Module "{module.name}" imported',
            'slug': module.slug,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/modules', methods=['GET'])
@login_required
def api_list_modules():
    modules = db.session.query(Module).all()
    return jsonify([{
        'id': m.id,
        'name': m.name,
        'slug': m.slug,
        'version': m.version,
        'author': m.author,
        'enabled': m.enabled,
        'routes': [{'slug': r.slug, 'methods': r.methods} for r in m.routes],
        'scripts': [s.name for s in m.scripts],
        'forms': [f.name for f in m.forms],
    } for m in modules])
