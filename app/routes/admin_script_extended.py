"""Admin routes for extended script management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

script_extended_bp = Blueprint('script_extended', __name__)


@script_extended_bp.route('/scripts/<int:id>/validate')
@developer_or_admin_required
def validate_script(id):
    """Validate a script's syntax."""
    from app.models import Script
    
    script = db.session.get(Script, id)
    if not script:
        flash('Script not found', 'error')
        return redirect(url_for('admin.list_scripts'))
    
    try:
        compile(script.source_code, f'<{script.name}>', 'exec')
        flash(f'Script "{script.name}" is syntactically valid')
    except SyntaxError as e:
        flash(f'Syntax error in "{script.name}": {e.msg} (line {e.lineno})', 'error')
    
    return redirect(url_for('admin.list_scripts'))


@script_extended_bp.route('/scripts/bulk-validate', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def bulk_validate_scripts():
    """Validate multiple scripts at once."""
    from app.models import Script
    
    script_ids = request.form.getlist('script_ids')
    valid = 0
    invalid = 0
    
    for sid in script_ids:
        script = db.session.get(Script, int(sid))
        if script:
            try:
                compile(script.source_code, f'<{script.name}>', 'exec')
                valid += 1
            except SyntaxError:
                invalid += 1
    
    flash(f'Validated {len(script_ids)} script(s). {valid} valid, {invalid} invalid.')
    return redirect(url_for('admin.list_scripts'))


@script_extended_bp.route('/scripts/<int:id>/format')
@developer_or_admin_required
def format_script(id):
    """Format a script's source code (basic indentation fix)."""
    from app.models import Script
    
    script = db.session.get(Script, id)
    if not script:
        flash('Script not found', 'error')
        return redirect(url_for('admin.list_scripts'))
    
    # Basic formatting: remove leading/trailing whitespace from each line
    lines = script.source_code.splitlines()
    formatted = '\n'.join(line.strip() for line in lines)
    
    script.source_code = formatted
    db.session.commit()
    flash(f'Script "{script.name}" formatted')
    return redirect(url_for('admin.list_scripts'))
