from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app import db
from app.models import Credential, Module

credentials_bp = Blueprint('credentials', __name__)


@credentials_bp.route('/')
@admin_required
def list_credentials():
    module_id = request.args.get('module_id', type=int)
    q = db.session.query(Credential)
    if module_id:
        q = q.filter(Credential.module_id == module_id)
    q = q.order_by(Credential.module_id, Credential.name)
    creds = q.all()
    modules = db.session.query(Module).order_by(Module.name).all()
    return render_admin('Credentials', 'admin/credentials/list.html', creds=creds, modules=modules, module_id=module_id)


@credentials_bp.route('/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def new_credential():
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        from app.services.credential_store import encrypt_value
        c = Credential(
            module_id=int(request.form['module_id']),
            name=request.form['name'],
            credential_type=request.form.get('credential_type', 'api_key'),
            value_encrypted=encrypt_value(request.form['value']),
            description=request.form.get('description', ''),
        )
        db.session.add(c)
        db.session.commit()
        flash(f'Credential "{c.name}" saved')
        return redirect(url_for('admin.credentials.list_credentials'))
    return render_admin('New Credential', 'admin/credentials/new.html', modules=modules)


@credentials_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def edit_credential(id):
    c = Credential.query.get_or_404(id)
    modules = db.session.query(Module).order_by(Module.name).all()
    if request.method == 'POST':
        from app.services.credential_store import encrypt_value
        c.module_id = int(request.form['module_id'])
        c.name = request.form['name']
        c.credential_type = request.form.get('credential_type', 'api_key')
        c.description = request.form.get('description', '')
        if request.form.get('value'):
            c.value_encrypted = encrypt_value(request.form['value'])
        db.session.commit()
        flash(f'Credential "{c.name}" updated')
        return redirect(url_for('admin.credentials.list_credentials'))
    return render_admin('Edit Credential', 'admin/credentials/edit.html', c=c, modules=modules)


@credentials_bp.route('/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_credential(id):
    c = Credential.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash(f'Credential "{c.name}" deleted')
    return redirect(url_for('admin.credentials.list_credentials'))
