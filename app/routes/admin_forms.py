from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, list_view, render_admin
from app import db
from app.models import Form, Module

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
        return redirect(url_for('admin.forms.list_forms'))
    return render_admin('Edit Form', 'admin/forms/edit.html', f=f, modules=modules)
