from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, render_admin
from app import db
from app.models import Form, Module
from app.services.audit import log_audit

forms_bp = Blueprint('forms', __name__)

@forms_bp.route('/')
@developer_or_admin_required
def list_forms():
    return list_view(Form, 'forms', ['id', 'name'],
        'admin.forms.edit_form', 'admin.forms.new_form', has_module=True)

@forms_bp.route('/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_form():
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        f = Form(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            schema_json=request.form.get('schema_json', '[]'),
        )
        db.session.add(f)
        db.session.commit()
        log_audit('create', 'form', f.id, f.name)
        return redirect(url_for('admin.forms.list_forms'))
    return render_admin('New Form', 'admin/forms/new.html', modules=modules)

@forms_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def edit_form(id):
    f = Form.query.get_or_404(id)
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        f.module_id = int(request.form['module_id'])
        f.name = request.form['name']
        f.schema_json = request.form.get('schema_json', '[]')
        db.session.commit()
        log_audit('edit', 'form', f.id, f.name)
        return redirect(url_for('admin.forms.list_forms'))
    return render_admin('Edit Form', 'admin/forms/edit.html', f=f, modules=modules)


@forms_bp.route('/ask-ai', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def ask_ai_form():
    """Generate a form schema from natural language description."""
    from app.services.ai_assistant import generate_form_schema, compute_diff
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    description = (data.get('description') or '').strip()
    existing_schema = (data.get('existing_schema') or '').strip()

    if not description:
        return jsonify({'success': False, 'error': 'No description provided'}), 400

    result = generate_form_schema(description, existing_schema or None)

    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})

    new_schema = result.get('schema_json')
    old_schema = existing_schema or '[]'
    diff_lines = None
    if new_schema:
        try:
            import json
            old_parsed = json.loads(old_schema) if old_schema else []
            new_parsed = json.loads(new_schema) if new_schema else []
            diff_text_old = json.dumps(old_parsed, indent=2)
            diff_text_new = json.dumps(new_parsed, indent=2)
            diff_lines = compute_diff(diff_text_old, diff_text_new)
        except Exception:
            pass

    return jsonify({
        'success': True,
        'reply': result['reply'],
        'schema_json': new_schema,
        'diff': diff_lines,
    })
