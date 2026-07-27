import json
import signal
import sys
import threading
import time
import traceback
import smtplib
from email.mime.text import MIMEText
from io import StringIO

from flask import request, redirect, url_for, flash, get_flashed_messages, render_template_string, jsonify as flask_jsonify
from flask_login import current_user
from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, Text, Boolean, Float, Column
from app.models import DynamicModel
from app.services.template_renderer import render_db_template

from app import db
from app.models import Setting, ExecutionLog


def _send_email(to, subject, body, html=False):
    host = Setting.get('smtp_host', 'localhost')
    port = int(Setting.get('smtp_port', '587'))
    user = Setting.get('smtp_user', '')
    password = Setting.get('smtp_password', '')
    from_addr = Setting.get('smtp_from', 'noreply@example.com')
    use_tls = Setting.get('smtp_tls', 'true') == 'true'

    msg = MIMEText(body, 'html' if html else 'plain')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to if isinstance(to, str) else ','.join(to)

    try:
        server = smtplib.SMTP(host, port, timeout=10)
        if use_tls:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, [to] if isinstance(to, str) else to, msg.as_string())
        server.quit()
    except Exception as e:
        raise RuntimeError(f'Email send failed: {e}')


class ScriptTimeout(Exception):
    pass


def _make_get_credential(module_id):
    def get_credential(name):
        from app.models import Credential
        from app.services.credential_store import decrypt_value
        c = Credential.query.filter_by(module_id=module_id, name=name).first()
        if c is None:
            raise NameError(f'Credential "{name}" not found for this module')
        return decrypt_value(c.value_encrypted)
    get_credential.__name__ = 'get_credential'
    return get_credential


class _ModuleDynamicModel:
    """Module-scoped DynamicModel wrapper that auto-registers table ownership."""
    def __init__(self, module_id):
        self._module_id = module_id

    def get_or_create(self, name, columns=None):
        return DynamicModel.get_or_create(name, columns, module_id=self._module_id)


SENSITIVE_SETTINGS = {
    'smtp_password', 'llm_api_key', 'imap_password',
    'secret_key', 'database_url',
}


def _get_setting_safe(key, default=''):
    """Get a setting value, blocking access to sensitive keys."""
    if key in SENSITIVE_SETTINGS:
        return default or ''
    return Setting.get(key, default)


def _call_api(method='GET', url=None, headers=None, json=None, data=None,
              timeout=30, retries=3, backoff=2, verify_ssl=True):
    """Centralized HTTP client with retry and error handling.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        url: Full URL to call
        headers: dict of HTTP headers
        json: dict to send as JSON body
        data: str or bytes to send as raw body
        timeout: request timeout in seconds (default 30)
        retries: number of retries on failure (default 3)
        backoff: exponential backoff multiplier in seconds (default 2)
        verify_ssl: Verify SSL certificates (default True). Set False to skip verification.

    Returns:
        dict with keys: status_code, headers (dict), body (parsed JSON or raw text), elapsed_ms
    """
    import urllib.request
    import urllib.error
    import json as _json
    import time as _time
    import ssl as _ssl

    if url is None:
        raise ValueError('url is required')

    t0 = _time.time()

    body_bytes = None
    if json is not None:
        body_bytes = _json.dumps(json).encode('utf-8')
        if headers is None:
            headers = {}
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
    elif data is not None:
        if isinstance(data, str):
            body_bytes = data.encode('utf-8')
        else:
            body_bytes = data

    # Set up SSL context with verification
    ssl_ctx = None
    if verify_ssl:
        try:
            ssl_ctx = _ssl.create_default_context()
        except Exception:
            pass

    last_error = None
    for attempt in range(1 + retries):
        try:
            req = urllib.request.Request(url, data=body_bytes, method=method.upper())
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)

            if ssl_ctx:
                with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
                    raw = resp.read()
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        body = _json.loads(raw.decode('utf-8'))
                    else:
                        body = raw.decode('utf-8', errors='replace')

                    elapsed = int((_time.time() - t0) * 1000)
                    return {
                        'status_code': resp.status,
                        'headers': dict(resp.headers),
                        'body': body,
                        'elapsed_ms': elapsed,
                    }
            else:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        body = _json.loads(raw.decode('utf-8'))
                    else:
                        body = raw.decode('utf-8', errors='replace')

                    elapsed = int((_time.time() - t0) * 1000)
                    return {
                        'status_code': resp.status,
                        'headers': dict(resp.headers),
                        'body': body,
                        'elapsed_ms': elapsed,
                    }

        except urllib.error.HTTPError as e:
            last_error = e
            if attempt < retries and e.code >= 500:
                _time.sleep(backoff * (2 ** attempt))
                continue
            elapsed = int((_time.time() - t0) * 1000)
            try:
                err_body = e.read().decode('utf-8', errors='replace')
            except Exception:
                err_body = str(e)
            return {
                'status_code': e.code,
                'headers': dict(e.headers),
                'body': err_body,
                'elapsed_ms': elapsed,
                'error': str(e),
            }

        except Exception as e:
            last_error = e
            if attempt < retries:
                _time.sleep(backoff * (2 ** attempt))
                continue
            elapsed = int((_time.time() - t0) * 1000)
            return {
                'status_code': 0,
                'headers': {},
                'body': str(e),
                'elapsed_ms': elapsed,
                'error': str(e),
            }

    elapsed = int((_time.time() - t0) * 1000)
    return {
        'status_code': 0,
        'headers': {},
        'body': str(last_error),
        'elapsed_ms': elapsed,
        'error': str(last_error),
    }


def execute_script(script, route=None, extra_globals=None, source_type='route', source_name=None):
    if source_name is None:
        source_name = script.name

    t0 = time.time()

    timeout = int(Setting.get('script_timeout', '30'))

    old_alarm = None
    if timeout > 0 and threading.current_thread() is threading.main_thread():
        old_alarm = signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(ScriptTimeout()))
        signal.alarm(timeout)

    log_entry = ExecutionLog(
        source_type=source_type,
        source_name=source_name,
    )

    # Blocked modules — scripts cannot import these for security
    BLOCKED_MODULES = {
        'os', 'subprocess', 'sys', 'importlib', 'pkg_resources',
        'ctypes', 'socket', 'http', 'urllib', 'requests',
        'shutil', 'tempfile', 'pickle', 'marshal', 'codecs',
        'threading', 'multiprocessing', 'signal',
    }

    # Custom __import__ that blocks dangerous modules
    import builtins as _builtins
    _original_import = _builtins.__import__

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split('.')[0] in BLOCKED_MODULES:
            raise ImportError(f'Module "{name}" is blocked for security reasons')
        return _original_import(name, globals, locals, fromlist, level)

    safe_builtins = {
        'True': True,
        'False': False,
        'None': None,
        'int': int,
        'float': float,
        'str': str,
        'bool': bool,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'len': len,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'sorted': sorted,
        'reversed': reversed,
        'min': min,
        'max': max,
        'sum': sum,
        'any': any,
        'all': all,
        'abs': abs,
        'round': round,
        'isinstance': isinstance,
        'type': type,
        'hasattr': hasattr,
        'getattr': getattr,
        'setattr': setattr,
        'dir': dir,
        'print': print,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'KeyError': KeyError,
        'IndexError': IndexError,
        'AttributeError': AttributeError,
        'Exception': Exception,
        '__import__': _safe_import,
    }

    safe_globals = {
        '__builtins__': safe_builtins,
        'request': request,
        'session': db.session,
        'db': db,
        'current_user': current_user,
        'redirect': redirect,
        'url_for': url_for,
        'flash': flash,
        'get_flashed_messages': get_flashed_messages,
        'render': render_template_string,
        'jsonify': flask_jsonify,
        'send_email': _send_email,
        'render_chart': render_chart,
        'DynamicModel': _ModuleDynamicModel(script.module_id),
        'Integer': Integer,
        'String': String,
        'DateTime': DateTime,
        'Text': Text,
        'Boolean': Boolean,
        'Float': Float,
        'Column': Column,
        'datetime': datetime,
        'timezone': timezone,
        'get_credential': _make_get_credential(script.module_id),
        'call_api': _call_api,
        'get_setting': _get_setting_safe,
        'render_db_template': render_db_template,
    }

    if extra_globals:
        safe_globals.update(extra_globals)

    if route:
        safe_globals['route'] = route
        if route.form:
            _inject_form_helpers(safe_globals, route.form)

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        source = script.source_code

        # Try direct execution first (supports _result = x pattern)
        try:
            compiled = compile(source, f'<script:{script.name}>', 'exec')
        except SyntaxError as syn:
            if 'return' in str(syn) and 'outside function' in str(syn):
                source = _wrap_in_function(source)
                compiled = compile(source, f'<script:{script.name}>', 'exec')
            else:
                raise

        exec(compiled, safe_globals)

        # If we wrapped in a function, call it and use its return value
        if '_script' in safe_globals:
            result = safe_globals['_script']()
            if result is not None:
                _duration_ms = int((time.time() - t0) * 1000)
                log_entry.duration_ms = _duration_ms
                log_entry.status = 'success'
                output = sys.stdout.getvalue()
                log_entry.stdout = output[:4000]
                _save_log(log_entry)
                return result

        output = sys.stdout.getvalue()
        result = safe_globals.get('_result', output if output.strip() else None)

        if result is not None:
            _duration_ms = int((time.time() - t0) * 1000)
            log_entry.duration_ms = _duration_ms
            log_entry.status = 'success'
            log_entry.stdout = str(result)[:4000]
            _save_log(log_entry)
            return result

        if output.strip():
            _duration_ms = int((time.time() - t0) * 1000)
            log_entry.duration_ms = _duration_ms
            log_entry.status = 'success'
            log_entry.stdout = output[:4000]
            _save_log(log_entry)
            return output

        _duration_ms = int((time.time() - t0) * 1000)
        log_entry.duration_ms = _duration_ms
        log_entry.status = 'success'
        _save_log(log_entry)
        return ''

    except ScriptTimeout:
        _duration_ms = timeout * 1000
        log_entry.duration_ms = _duration_ms
        log_entry.status = 'error'
        log_entry.error_message = f'Script execution timed out after {timeout}s'
        _save_log(log_entry)
        return f'<pre style="color:#c00;">Script timed out after {timeout}s</pre>', 500

    except Exception as e:
        tb = traceback.format_exc()
        _duration_ms = int((time.time() - t0) * 1000)
        log_entry.duration_ms = _duration_ms
        log_entry.status = 'error'
        log_entry.error_message = f'{e}\n\n{tb}'[:4000]
        _save_log(log_entry)
        return f'<pre style="color:#c00;">Script error in {script.name}:\n{e}\n\n{tb}</pre>', 500
    finally:
        if old_alarm is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_alarm)
        sys.stdout = old_stdout


def _save_log(entry):
    try:
        db.session.add(entry)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def _wrap_in_function(source):
    import textwrap
    body = textwrap.indent(source, '    ')
    return f'def _script():\n{body}\n    return _result\n'


def _inject_form_helpers(globals_dict, form):
    try:
        fields = json.loads(form.schema_json)
    except (json.JSONDecodeError, TypeError):
        fields = []

    if not isinstance(fields, list):
        fields = []

    globals_dict['form_fields'] = fields

    def render_form(action='', method='POST', submit_label='Submit', fields=None, **kwargs):
        if fields is None:
            fields = globals_dict.get('form_fields', [])
        has_file = any(f.get('type') == 'file' for f in fields)
        enctype = ' enctype="multipart/form-data"' if has_file else ''
        html = ['<form action="%s" method="%s"%s>' % (action, method, enctype)]
        for f in fields:
            fname = f.get('name', '')
            flabel = f.get('label', fname)
            ftype = f.get('type', 'text')
            required = 'required' if f.get('required', False) else ''
            placeholder = f.get('placeholder', '')
            value = request.form.get(fname, '')

            html.append('<div style="margin-bottom:12px;">')
            html.append('<label for="%s" style="display:block;font-weight:600;margin-bottom:4px;">%s</label>' % (fname, flabel))

            if ftype == 'textarea':
                html.append('<textarea id="%s" name="%s" %s placeholder="%s" style="width:100%%;padding:8px;border:1px solid #ccc;border-radius:4px;min-height:100px;">%s</textarea>' % (fname, fname, required, placeholder, value))
            elif ftype == 'select':
                opts = f.get('options', '')
                html.append('<select id="%s" name="%s" %s style="width:100%%;padding:8px;border:1px solid #ccc;border-radius:4px;">' % (fname, fname, required))
                for opt in opts.split(','):
                    opt = opt.strip()
                    sel = ' selected' if opt == value else ''
                    html.append('<option value="%s"%s>%s</option>' % (opt, sel, opt))
                html.append('</select>')
            elif ftype == 'checkbox':
                checked = ' checked' if value else ''
                html.append('<input type="checkbox" id="%s" name="%s" %s %s style="margin-top:4px;">' % (fname, fname, required, checked))
            elif ftype == 'file':
                html.append('<input type="file" id="%s" name="%s" %s style="width:100%%;padding:6px;border:1px solid #ccc;border-radius:4px;">' % (fname, fname, required))
            else:
                html.append('<input type="%s" id="%s" name="%s" value="%s" %s placeholder="%s" style="width:100%%;padding:8px;border:1px solid #ccc;border-radius:4px;">' % (ftype, fname, fname, value, required, placeholder))

            html.append('</div>')

        html.append('<button type="submit" style="padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">%s</button>' % submit_label)
        html.append('</form>')
        return '\n'.join(html)

    globals_dict['render_form'] = render_form


def render_chart(chart_type, labels, datasets, title='', canvas_id=None):
    import json
    import secrets
    cid = canvas_id or 'chart_' + secrets.token_hex(4)
    data = {
        'type': chart_type,
        'data': {'labels': labels, 'datasets': datasets},
        'options': {
            'responsive': True,
            'plugins': {
                'title': {'display': bool(title), 'text': title} if title else {}
            }
        }
    }
    html = '''<div style="max-width:600px;margin:1rem 0;">
  <canvas id="%s"></canvas>
</div>
<script>
(function() {
  if (typeof Chart === "undefined") {
    var s = document.createElement("script");
    s.src = "/static/chart.umd.min.js";
    s.onload = function() { new Chart(document.getElementById("%s"), %s); };
    document.head.appendChild(s);
  } else {
    new Chart(document.getElementById("%s"), %s);
  }
})();
</script>''' % (cid, cid, json.dumps(data), cid, json.dumps(data))
    return html
