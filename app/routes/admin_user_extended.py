"""Admin routes for extended user management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

user_extended_bp = Blueprint('user_extended', __name__)


@user_extended_bp.route('/users/export')
@admin_required
def export_users():
    """Export users as CSV."""
    from app.models import User
    import csv, io
    from flask import Response
    
    users = db.session.query(User).all()
    
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['id', 'username', 'role', 'is_active', 'is_approved', 'created_at'])
    for u in users:
        w.writerow([u.id, u.username, u.role, u.is_active, u.is_approved, u.created_at])
    
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=users.csv'}
    )


@user_extended_bp.route('/users/import', methods=['POST'])
@admin_required
@csrf_protect
def import_users():
    """Import users from CSV file."""
    import csv
    from app.models import User
    import bcrypt
    
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('admin.list_users'))
    
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        flash('Invalid file format. Please upload a CSV file.', 'error')
        return redirect(url_for('admin.list_users'))
    
    imported = 0
    errors = 0
    
    try:
        content = file.read().decode('utf-8')
        reader = csv.DictReader(content.splitlines())
        
        for row in reader:
            username = row.get('username', '').strip()
            password = row.get('password', '').strip()
            role = row.get('role', 'user').strip()
            
            if not username or not password:
                errors += 1
                continue
            
            # Check if user exists
            existing = db.session.query(User).filter_by(username=username).first()
            if existing:
                errors += 1
                continue
            
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(
                username=username,
                password_hash=pw_hash,
                role=role,
                is_active=True,
                is_approved=True,
            )
            db.session.add(user)
            imported += 1
        
        db.session.commit()
        flash(f'Imported {imported} user(s). {errors} error(s).')
    except Exception as e:
        flash(f'Import failed: {e}', 'error')
    
    return redirect(url_for('admin.list_users'))


@user_extended_bp.route('/users/<int:id>/reset-password', methods=['POST'])
@admin_required
@csrf_protect
def reset_password(id):
    """Reset a user's password."""
    import bcrypt
    from app.models import User
    
    user = db.session.get(User, id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.list_users'))
    
    new_password = request.form.get('new_password', '')
    if not new_password:
        flash('Password cannot be empty', 'error')
        return redirect(url_for('admin.list_users'))
    
    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    user.password_hash = pw_hash
    db.session.commit()
    flash(f'Password reset for {user.username}')
    return redirect(url_for('admin.list_users'))
