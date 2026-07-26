"""Admin routes for bulk export/import."""
from flask import Blueprint, request, redirect, url_for, Response, flash

export_import_bp = Blueprint('export_import', __name__)


@export_import_bp.route('/export/all')
@login_required
def export_all():
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
        headers={'Content-Disposition': 'attachment; filename="all_modules_export.zip"'}
    )


@export_import_bp.route('/import/bulk', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def import_bulk():
    """Import multiple modules from a ZIP file."""
    from app.services.bundle import import_module
    
    if 'files' not in request.files:
        flash('No files provided', 'error')
        return redirect(url_for('admin.list_modules'))
    
    files = request.files.getlist('files')
    imported = 0
    errors = 0
    
    for file in files:
        if not file.filename or not file.filename.endswith('.xml'):
            continue
        
        try:
            xml_str = file.read().decode('utf-8')
            module = import_module(xml_str)
            imported += 1
        except Exception as e:
            errors += 1
            flash(f'Failed to import {file.filename}: {e}', 'error')
    
    if imported > 0:
        flash(f'Successfully imported {imported} module(s)')
    if errors > 0:
        flash(f'{errors} module(s) failed to import')
    
    return redirect(url_for('admin.list_modules'))


@export_import_bp.route('/export/template')
@login_required
def export_template():
    """Download a module XML template."""
    template = '''<?xml version="1.0" encoding="UTF-8"?>
<module name="My Module" slug="my-module" version="1.0.0" author="">
  <description>A description of your module.</description>
  <routes>
    <route slug="/" method="GET" script="home" auth_required="false" title="Home"/>
  </routes>
  <scripts>
    <script name="home" language="python"><![CDATA[
# Your script here
_result = "<h1>Hello World</h1>"
]]></script>
  </scripts>
  <forms></forms>
  <scheduled_tasks></scheduled_tasks>
  <triggers></triggers>
  <query_reports></query_reports>
</module>'''
    
    return Response(
        template,
        mimetype='application/xml',
        headers={'Content-Disposition': 'attachment; filename="module_template.xml"'}
    )
