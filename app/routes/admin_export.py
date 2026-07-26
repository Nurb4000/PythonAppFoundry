"""Admin routes for module export functionality."""
from flask import Blueprint, request, redirect, url_for, Response

export_bp = Blueprint('export', __name__)


@export_bp.route('/export/<slug>')
@login_required
def export_module(slug):
    """Export a module as XML."""
    from app.models import Module
    from app.services.bundle import export_module
    
    module = db.session.query(Module).filter_by(slug=slug).first()
    if not module:
        return 'Module not found', 404
    
    xml_str = export_module(module)
    return Response(
        xml_str,
        mimetype='application/xml',
        headers={'Content-Disposition': f'attachment; filename="{module.slug}.xml"'}
    )


@export_bp.route('/export/all')
@login_required
def export_all_modules():
    """Export all modules as a ZIP file."""
    import zipfile
    import io
    from app.models import Module
    from app.services.bundle import export_module
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for module in db.session.query(Module).all():
            xml_str = export_module(module)
            zf.writestr(f'{module.slug}.xml', xml_str)
    
    zip_buffer.seek(0)
    return Response(
        zip_buffer.read(),
        mimetype='application/zip',
        headers={'Content-Disposition': 'attachment; filename="modules_export.zip"'}
    )
