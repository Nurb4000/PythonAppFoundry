"""Admin routes for script management."""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, render_admin
from app.services.script_runner import execute_script
from app import db
from app.models import Script, Module
from app.services.audit import log_audit

scripts_bp = Blueprint('scripts', __name__)


@scripts_bp.route('/')
@developer_or_admin_required
def list_scripts():
    return list_view(Script, 'scripts', ['id', 'name', 'language'], 'admin.scripts.edit_script', 'admin.scripts.new_script', has_module=True)


@scripts_bp.route('/new', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def new_script():
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        source = request.form.get('source_code', '')
        language = request.form.get('language', 'python')
        if language == 'python' and source.strip():
            try:
                compile(source, f'<{request.form["name"]}>', 'exec')
            except SyntaxError as e:
                flash(f'Syntax error in script "{request.form["name"]}": {e.msg} (line {e.lineno})', 'error')
                return redirect(url_for('admin.scripts.new_script'))
        s = Script(module_id=int(request.form['module_id']), name=request.form['name'], language=language, source_code=source, description=request.form.get('description', ''))
        db.session.add(s)
        db.session.commit()
        log_audit('create', 'script', s.id, s.name)
        return redirect(url_for('admin.scripts.list_scripts'))
    return render_admin('New Script', 'admin/scripts/new.html', modules=modules)


@scripts_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@developer_or_admin_required
@csrf_protect
def edit_script(id):
    s = Script.query.get_or_404(id)
    modules = db.session.query(Module).all()
    if request.method == 'POST':
        source = request.form.get('source_code', '')
        language = request.form.get('language', 'python')
        if language == 'python' and source.strip():
            try:
                compile(source, f'<{request.form["name"]}>', 'exec')
            except SyntaxError as e:
                flash(f'Syntax error in script "{request.form["name"]}": {e.msg} (line {e.lineno})', 'error')
                return redirect(url_for('admin.scripts.edit_script', id=s.id))
        s.module_id = int(request.form['module_id'])
        s.name = request.form['name']
        s.language = language
        s.source_code = source
        s.description = request.form.get('description', '')
        db.session.commit()
        log_audit('edit', 'script', s.id, s.name)
        return redirect(url_for('admin.scripts.list_scripts'))
    return render_admin('Edit Script', 'admin/scripts/edit.html', s=s, modules=modules)


@scripts_bp.route('/debug/<int:id>')
@developer_or_admin_required
def debug_script(id):
    s = Script.query.get_or_404(id)
    import time
    t0 = time.time()
    from io import StringIO
    import sys
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    error = None
    output = None
    try:
        result = execute_script(s)
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    except Exception as e:
        import traceback
        error = traceback.format_exc()
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    finally:
        sys.stdout = old_stdout
    source_lines = [{'line_num': i + 1, 'line': line} for i, line in enumerate(s.source_code.split('\n'))]
    return render_admin('Debug: ' + s.name, 'admin/scripts/debug.html', s=s, duration=duration, source_lines=source_lines, error=error, output=output)


@scripts_bp.route('/ask-ai', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def ask_ai_debug():
    """Send an error + script context to the LLM for debugging help."""
    from app.services.ai_assistant import debug_script_error
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    error_text = (data.get('error') or '').strip()
    script_source = (data.get('script_source') or '').strip()
    script_name = (data.get('script_name') or '').strip()

    if not error_text:
        return jsonify({'success': False, 'error': 'No error message provided'}), 400

    if not script_source and script_name:
        s = Script.query.filter_by(name=script_name).first()
        if s:
            script_source = s.source_code

    if not script_source:
        return jsonify({'success': False, 'error': 'Script source not found'}), 400

    result = debug_script_error(error_text, script_source, script_name)

    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})

    return jsonify({
        'success': True,
        'reply': result['reply'],
        'fix_code': result.get('fix_code'),
    })


@scripts_bp.route('/enhance-ai', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def enhance_ai():
    """Send a script to the LLM for proactive enhancement."""
    from app.services.ai_assistant import enhance_script, compute_diff
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    source_code = (data.get('source_code') or '').strip()
    script_name = (data.get('script_name') or '').strip()
    instructions = (data.get('instructions') or '').strip()

    if not source_code:
        return jsonify({'success': False, 'error': 'No script source provided'}), 400

    result = enhance_script(source_code, script_name, instructions)

    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})

    enhanced_code = result.get('enhanced_code')
    diff_lines = None
    if enhanced_code:
        diff_lines = compute_diff(source_code, enhanced_code)

    return jsonify({
        'success': True,
        'reply': result['reply'],
        'enhanced_code': enhanced_code,
        'diff': diff_lines,
    })
