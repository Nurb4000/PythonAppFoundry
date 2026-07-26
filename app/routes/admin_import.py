"""Admin routes for module import functionality."""
from flask import Blueprint, request, redirect, url_for, flash

import_bp = Blueprint('import', __name__)


@import_bp.route('/import', methods=['GET', 'POST'])
@developer_or_admin_required
def import_module():
    """Import a module from XML file."""
    from app.services.bundle import import_module
    
    if request.method == 'POST':
        if 'import_xml' not in request.files:
            flash('No file provided', 'error')
            return redirect(url_for('admin.import_module'))
        
        xml_file = request.files['import_xml']
        if not xml_file.filename:
            flash('Empty filename', 'error')
            return redirect(url_for('admin.import_module'))
        
        try:
            xml_str = xml_file.read().decode('utf-8')
            module = import_module(xml_str)
            flash(f'Module "{module.name}" imported successfully')
            return redirect(url_for('admin.list_modules'))
        except Exception as e:
            flash(f'Import failed: {e}', 'error')
            return redirect(url_for('admin.import_module'))
    
    return render_admin('Import Module', '''
<form method="POST" enctype="multipart/form-data">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <label>XML File <input name="import_xml" type="file" accept=".xml" required></label>
  <button type="submit" style="margin-top:1rem;padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Import</button>
</form>
''')
