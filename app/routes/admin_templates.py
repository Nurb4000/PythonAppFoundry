"""Admin routes for database template management."""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, render_admin
from app import db
from app.models import Template, Module
from app.services.audit import log_audit

templates_bp = Blueprint('templates', __name__)


@templates_bp.route('/')
@developer_or_admin_required
def list_templates():
    return list_view(Template, 'templates', ['id', 'name', 'content_type'],
                     'admin.templates.edit_template', 'admin.templates.new_template',
                     has_module=True)


@templates_bp.route('/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_template():
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        t = Template(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            body=request.form.get('body', ''),
            content_type=request.form.get('content_type', 'html'),
            description=request.form.get('description', ''),
        )
        db.session.add(t)
        db.session.commit()
        log_audit('create', 'template', t.id, t.name)
        return redirect(url_for('admin.templates.list_templates'))
    return render_admin('New Template', 'admin/templates/new.html', modules=modules)


@templates_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def edit_template(id):
    t = Template.query.get_or_404(id)
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        t.module_id = int(request.form['module_id'])
        t.name = request.form['name']
        t.body = request.form.get('body', '')
        t.content_type = request.form.get('content_type', 'html')
        t.description = request.form.get('description', '')
        db.session.commit()
        log_audit('edit', 'template', t.id, t.name)
        return redirect(url_for('admin.templates.list_templates'))
    return render_admin('Edit Template', 'admin/templates/edit.html', t=t, modules=modules)


@templates_bp.route('/preview', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def preview_template():
    """Render a template body with sample context via AJAX."""
    data = request.get_json(silent=True)
    if not data or not data.get('body'):
        return jsonify({'success': False, 'error': 'No template body provided'}), 400
    try:
        from app.services.template_renderer import render_db_template
        context = data.get('context', {})
        rendered = render_db_template(data['body'], **context)
        return jsonify({'success': True, 'rendered': rendered})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@templates_bp.route('/ask-ai', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def ask_ai_template():
    """Improve a template using the LLM."""
    from app.services.ai_assistant import improve_template, compute_diff
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    body = (data.get('body') or '').strip()
    content_type = (data.get('content_type') or 'html').strip()
    instructions = (data.get('instructions') or '').strip()

    if not body:
        return jsonify({'success': False, 'error': 'No template body provided'}), 400

    result = improve_template(body, content_type, instructions)

    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})

    improved_body = result.get('improved_body')
    diff_lines = None
    if improved_body:
        diff_lines = compute_diff(body, improved_body)

    return jsonify({
        'success': True,
        'reply': result['reply'],
        'improved_body': improved_body,
        'diff': diff_lines,
    })
