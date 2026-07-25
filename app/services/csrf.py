import secrets
import functools
from flask import request, session, abort, redirect, url_for


def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf_token(token):
    expected = session.get('csrf_token', '')
    if not expected or not token:
        return False
    return secrets.compare_digest(expected, token)


def csrf_protect(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            form_token = request.form.get('csrf_token', '')
            header_token = request.headers.get('X-CSRF-Token', '')
            json_token = ''
            if request.is_json:
                json_data = request.get_json(silent=True) or {}
                json_token = json_data.get('csrf_token', '')
            token = form_token or header_token or json_token
            if not validate_csrf_token(token):
                abort(403)
        return f(*args, **kwargs)
    return wrapper


def csrf_token():
    return generate_csrf_token()
