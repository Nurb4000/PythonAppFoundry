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


@api_bp.route('/upload', methods=['POST'])
@login_required
def api_upload_file():
    """Upload a file and return JSON with the upload details."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file_obj = request.files['file']
    if not file_obj.filename:
        return jsonify({'error': 'No filename provided'}), 400
    
    try:
        from app.services.file_upload import upload_file
        upload = upload_file(file_obj)
        return jsonify({
            'id': upload.id,
            'filename': upload.filename,
            'original_name': upload.original_name,
            'mime_type': upload.mime_type,
            'size': upload.size,
            'url': f'/uploads/{upload.filename}',
            'created_at': upload.created_at.isoformat() if upload.created_at else None,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/uploads', methods=['GET'])
@login_required
def api_list_uploads():
    """List all uploaded files (paginated)."""
    from app.models import Upload
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)  # Max 100 per page
    
    uploads = db.session.query(Upload).order_by(Upload.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'uploads': [{
            'id': u.id,
            'filename': u.filename,
            'original_name': u.original_name,
            'mime_type': u.mime_type,
            'size': u.size,
            'url': f'/uploads/{u.filename}',
            'created_at': u.created_at.isoformat() if u.created_at else None,
        } for u in uploads.items],
        'total': uploads.total,
        'page': uploads.page,
        'pages': uploads.pages,
    })


@api_bp.route('/queries/<int:id>/run', methods=['POST'])
@login_required
def api_run_query(id):
    from app.models import QueryReport
    q = QueryReport.query.get_or_404(id)
    import time as _t
    t0 = _t.time()
    columns = []
    rows = []
    chart_labels = []
    chart_datasets = []
    try:
        sql = request.form.get('sql', q.sql)
        result = db.session.execute(db.text(sql))
        if result.returns_rows:
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
        if q.chart_type != 'none' and q.label_column and q.data_columns:
            label_idx = None
            for i, c in enumerate(columns):
                if c.lower() == q.label_column.lower():
                    label_idx = i
                    break
            data_col_indices = []
            data_col_names = []
            for dc in q.data_columns.split(','):
                dc = dc.strip()
                for i, c in enumerate(columns):
                    if c.lower() == dc.lower():
                        data_col_indices.append(i)
                        data_col_names.append(c)
                        break
            if label_idx is not None and data_col_indices:
                chart_labels = [str(r[label_idx]) for r in rows]
                colors = ['#2563eb', '#e94560', '#28a745', '#ffc107', '#6f42c1', '#fd7e14', '#20c997', '#dc3545']
                for j, dc_idx in enumerate(data_col_indices):
                    chart_datasets.append({
                        'label': data_col_names[j],
                        'data': [float(r[dc_idx]) if r[dc_idx] is not None else 0 for r in rows],
                        'backgroundColor': colors[j % len(colors)],
                        'borderColor': colors[j % len(colors)],
                        'borderWidth': 1,
                    })
        duration = int((_t.time() - t0) * 1000)
        q.last_run = _t.time()
        db.session.commit()
        return jsonify({
            'columns': columns, 'rows': rows,
            'chart_labels': chart_labels, 'chart_datasets': chart_datasets,
            'chart_title': q.chart_title,
            'duration_ms': duration,
        })
    except Exception as e:
        duration = int((_t.time() - t0) * 1000)
        return jsonify({'error': str(e), 'duration_ms': duration}), 400


@api_bp.route('/webhook/<slug>', methods=['POST'])
def api_webhook(slug):
    """Public webhook endpoint. Fires triggers associated with this slug.
    
    Accepts JSON or form data in the request body.
    No authentication required - secure by obscurity (unique slug).
    """
    from app.services.triggers import fire_webhook
    
    # Extract payload from request
    if request.is_json:
        payload = request.get_json(silent=True) or {}
    else:
        payload = dict(request.form)
        # Also include files if present
        for key, value in request.files.items():
            payload[key] = value.filename
    
    fire_webhook(slug, payload)
    
    return jsonify({'status': 'ok', 'webhook': slug})
