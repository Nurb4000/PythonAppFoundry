"""Admin routes for extended export/import functionality."""
from flask import Blueprint, request, redirect, url_for, flash

export_import_extended_bp = Blueprint('export_import_extended', __name__)


@export_import_extended_bp.route('/export/module/<int:id>')
@login_required
def export_module_xml(id):
    """Export a single module as XML."""
    from app.models import Module
    from app.services.bundle import export_module
    
    module = db.session.get(Module, id)
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin.list_modules'))
    
    xml_str = export_module(module)
    
    from flask import Response
    return Response(
        xml_str,
        mimetype='application/xml',
        headers={'Content-Disposition': f'attachment; filename="{module.slug}.xml"'}
    )


@export_import_extended_bp.route('/import/bulk', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def import_bulk_modules():
    """Import multiple modules from uploaded XML files."""
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


@export_import_extended_bp.route('/export/template/download')
@login_required
def download_template():
    """Download a module XML template."""
    from flask import Response
    
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
