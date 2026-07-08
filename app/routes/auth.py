from urllib.parse import urlparse, urljoin

from flask import Blueprint, request, redirect, url_for, render_template_string, flash, session as flask_session
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt

from app import db
from app.models import User, Route, Setting

auth_bp = Blueprint('auth', __name__, url_prefix='/__auth')

STYLE = '''body { font-family: system-ui, sans-serif; max-width: 400px; margin: 3rem auto; padding: 0 1rem; }
input, select { display: block; width: 100%; margin-bottom: 1rem; padding: 0.5rem; box-sizing: border-box; }
button { padding: 0.5rem 2rem; cursor: pointer; }
.error { color: #c00; }
.success { color: #080; }
.card { background: #f9f9f9; border: 1px solid #ddd; border-radius: 8px; padding: 1.5rem; }
h2 { margin-top: 0; }'''

LOGIN_TEMPLATE = f'''<!DOCTYPE html>
<html>
<head><title>Log In</title><style>{STYLE}</style></head>
<body>
<div class="card">
<h2>Log In</h2>
{{% if error %}}<p class="error">{{{{ error }}}}</p>{{% endif %}}
<form method="POST">
<label>Username <input name="username" required autofocus></label>
<label>Password <input name="password" type="password" required></label>
<button>Log In</button>
</form>
{{% if not registration_disabled %}}<p style="margin-top:1rem;font-size:0.9em;">No account? <a href="{{{{ url_for('auth.register') }}}}">Register</a></p>{{% endif %}}
</div>
</body>
</html>
'''

SETUP_TEMPLATE = f'''<!DOCTYPE html>
<html>
<head><title>Initial Setup</title><style>{STYLE}</style></head>
<body>
<div class="card">
<h2>Create Admin User</h2>
{{% if error %}}<p class="error">{{{{ error }}}}</p>{{% endif %}}
{{% if success %}}<p class="success">{{{{ success }}}}</p>
<a href="{{{{ url_for('auth.login') }}}}">Proceed to Login</a>
{{% else %}}
<form method="POST">
<label>Username <input name="username" value="{{{{ username }}}}" required></label>
<label>Password <input name="password" type="password" required minlength="4"></label>
<label>Confirm <input name="confirm" type="password" required></label>
<button>Create Admin User</button>
</form>
{{% endif %}}
</div>
</body>
</html>
'''


REGISTER_TEMPLATE = f'''<!DOCTYPE html>
<html>
<head><title>Register</title><style>{STYLE}</style></head>
<body>
<div class="card">
<h2>Create Account</h2>
{{% if error %}}<p class="error">{{{{ error }}}}</p>{{% endif %}}
{{% if success %}}<p class="success">{{{{ success }}}}</p>
<a href="{{{{ url_for('auth.login') }}}}">Log In</a>
{{% else %}}
<form method="POST">
<label>Username <input name="username" required autofocus></label>
<label>Password <input name="password" type="password" required minlength="4"></label>
<label>Confirm <input name="confirm" type="password" required></label>
<button>Register</button>
</form>
<p style="margin-top:1rem;font-size:0.9em;">Already have an account? <a href="{{{{ url_for('auth.login') }}}}">Log in</a></p>
{{% endif %}}
</div>
</body>
</html>
'''

PROFILE_TEMPLATE = f'''<!DOCTYPE html>
<html>
<head><title>My Profile</title><style>{STYLE} .label {{ font-weight:600;color:#555;font-size:0.85em;text-transform:uppercase; }}</style></head>
<body>
<div class="card">
<h2>My Profile</h2>
<p><span class="label">Username</span><br>{{{{ current_user.username }}}}</p>
<p><span class="label">Role</span><br>{{{{ current_user.role }}}}</p>
<p><a href="{{{{ url_for('auth.logout') }}}}">Log Out</a></p>
</div>
</body>
</html>
'''


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    disabled = Setting.get('registration_disabled', 'false') == 'true'
    require_approval = Setting.get('registration_require_approval', 'false') == 'true'

    if disabled:
        return render_template_string(REGISTER_TEMPLATE,
            error='Registration is currently disabled.', success=None)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not username or not password:
            return render_template_string(REGISTER_TEMPLATE,
                error='Username and password are required.', success=None)
        if password != confirm:
            return render_template_string(REGISTER_TEMPLATE,
                error='Passwords do not match.', success=None)
        if len(password) < 4:
            return render_template_string(REGISTER_TEMPLATE,
                error='Password must be at least 4 characters.', success=None)
        existing = db.session.query(User).filter_by(username=username).first()
        if existing:
            return render_template_string(REGISTER_TEMPLATE,
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
        return render_template_string(REGISTER_TEMPLATE,
            success=msg, error=None)
    return render_template_string(REGISTER_TEMPLATE, success=None, error=None)


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template_string(PROFILE_TEMPLATE)

def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    registration_disabled = Setting.get('registration_disabled', 'false') == 'true'
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = db.session.query(User).filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            if not user.is_active:
                return render_template_string(LOGIN_TEMPLATE, error='Your account has been disabled.', registration_disabled=registration_disabled)
            if not user.is_approved:
                return render_template_string(LOGIN_TEMPLATE, error='Your account is pending approval.', registration_disabled=registration_disabled)
            login_user(user)
            next_page = request.args.get('next')
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            if current_user.role == 'admin':
                if db.session.query(Route).count() == 0:
                    next_page = url_for('admin.list_modules')
                else:
                    next_page = '/'
            elif current_user.role == 'developer':
                next_page = url_for('admin.list_modules')
            else:
                next_page = url_for('auth.profile')
            return redirect(next_page)
        return render_template_string(LOGIN_TEMPLATE, error='Invalid credentials', registration_disabled=registration_disabled)
    return render_template_string(LOGIN_TEMPLATE, registration_disabled=registration_disabled)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if db.session.query(User).count() > 0:
        return render_template_string(SETUP_TEMPLATE,
            error='Setup already completed. A user already exists.',
            success=None, username='')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not username or not password:
            return render_template_string(SETUP_TEMPLATE,
                error='Username and password are required.',
                success=None, username=username)
        if password != confirm:
            return render_template_string(SETUP_TEMPLATE,
                error='Passwords do not match.',
                success=None, username=username)
        if len(password) < 4:
            return render_template_string(SETUP_TEMPLATE,
                error='Password must be at least 4 characters.',
                success=None, username=username)
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(username=username, password_hash=pw_hash, role='admin')
        db.session.add(user)
        db.session.commit()
        return render_template_string(SETUP_TEMPLATE,
            success=f'User "{username}" created. You can now log in.',
            error=None, username=username)

    username = request.args.get('username', 'admin')
    return render_template_string(SETUP_TEMPLATE, success=None, error=None, username=username)
