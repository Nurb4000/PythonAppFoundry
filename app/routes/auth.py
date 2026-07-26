from urllib.parse import urlparse, urljoin

from flask import Blueprint, request, redirect, url_for, render_template, flash, session as flask_session
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt

from app import db
from app.models import User, Route, Setting
from app.services.rate_limiter import _rate_limiter

auth_bp = Blueprint('auth', __name__, url_prefix='/__auth')











@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    disabled = Setting.get('registration_disabled', 'false') == 'true'
    require_approval = Setting.get('registration_require_approval', 'false') == 'true'

    if disabled:
        return render_template('auth/register.html',
            error='Registration is currently disabled.', success=None)

    if request.method == 'POST':
        # Rate limiting on registration attempts
        client_ip = request.remote_addr
        limited, remaining = _rate_limiter.is_rate_limited(f'register:{client_ip}')
        if limited:
            return render_template('auth/register.html',
                error=f'Too many registration attempts. Please try again in {int(remaining)} seconds.', 
                success=None)
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not username or not password:
            return render_template('auth/register.html',
                error='Username and password are required.', success=None)
        if password != confirm:
            return render_template('auth/register.html',
                error='Passwords do not match.', success=None)
        if len(password) < 4:
            return render_template('auth/register.html',
                error='Password must be at least 4 characters.', success=None)
        existing = db.session.query(User).filter_by(username=username).first()
        if existing:
            return render_template('auth/register.html',
                error='Username already taken.', success=None)
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        approved = not require_approval
        user = User(username=username, password_hash=pw_hash, role='user',
                    is_approved=approved, is_active=True)
        db.session.add(user)
        db.session.commit()
        if require_approval:
            msg = 'Account created. An admin must approve your account before you can log in.'
        else:
            msg = 'Account created. You can now log in.'
        return render_template('auth/register.html',
            success=msg, error=None)
    return render_template('auth/register.html', success=None, error=None)


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    registration_disabled = Setting.get('registration_disabled', 'false') == 'true'
    if request.method == 'POST':
        # Rate limiting on login attempts
        client_ip = request.remote_addr
        limited, remaining = _rate_limiter.is_rate_limited(f'login:{client_ip}')
        if limited:
            return render_template('auth/login.html', 
                error=f'Too many login attempts. Please try again in {int(remaining)} seconds.', 
                registration_disabled=registration_disabled)
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = db.session.query(User).filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            if not user.is_active:
                return render_template('auth/login.html', error='Your account has been disabled.', registration_disabled=registration_disabled)
            if not user.is_approved:
                return render_template('auth/login.html', error='Your account is pending approval.', registration_disabled=registration_disabled)
            login_user(user)
            next_page = request.args.get('next')
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            if current_user.role == 'admin':
                if db.session.query(Route).count() == 0:
                    next_page = url_for('admin.modules.list_modules')
                else:
                    next_page = '/'
            elif current_user.role == 'developer':
                next_page = url_for('admin.modules.list_modules')
            else:
                next_page = url_for('auth.profile')
            return redirect(next_page)
        return render_template('auth/login.html', error='Invalid credentials', registration_disabled=registration_disabled)
    return render_template('auth/login.html', registration_disabled=registration_disabled)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if db.session.query(User).count() > 0:
        return render_template('auth/setup.html',
            error='Setup already completed. A user already exists.',
            success=None, username='')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not username or not password:
            return render_template('auth/setup.html',
                error='Username and password are required.',
                success=None, username=username)
        if password != confirm:
            return render_template('auth/setup.html',
                error='Passwords do not match.',
                success=None, username=username)
        if len(password) < 4:
            return render_template('auth/setup.html',
                error='Password must be at least 4 characters.',
                success=None, username=username)
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(username=username, password_hash=pw_hash, role='admin')
        db.session.add(user)
        db.session.commit()
        return render_template('auth/setup.html',
            success=f'User "{username}" created. You can now log in.',
            error=None, username=username)

    username = request.args.get('username', 'admin')
    return render_template('auth/setup.html', success=None, error=None, username=username)
