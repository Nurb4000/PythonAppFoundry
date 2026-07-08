import json
import sys
import time
import traceback
import smtplib
from email.mime.text import MIMEText
from io import StringIO

from flask import request, redirect, url_for, flash, render_template_string, jsonify as flask_jsonify
from flask_login import current_user

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


def execute_script(script, route=None, extra_globals=None, source_type='route', source_name=None):
    if source_name is None:
        source_name = script.name

    t0 = time.time()
    log_entry = ExecutionLog(
        source_type=source_type,
        source_name=source_name,
    )

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
        '__import__': __import__,
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
        'render': render_template_string,
        'jsonify': flask_jsonify,
        'send_email': _send_email,
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

    except Exception as e:
        tb = traceback.format_exc()
        _duration_ms = int((time.time() - t0) * 1000)
        log_entry.duration_ms = _duration_ms
        log_entry.status = 'error'
        log_entry.error_message = f'{e}\n\n{tb}'[:4000]
        _save_log(log_entry)
        return f'<pre style="color:#c00;">Script error in {script.name}:\n{e}\n\n{tb}</pre>', 500
    finally:
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
    lines = source.split('\n')
    indented = []
    for line in lines:
        if line.strip():
            indented.append('    ' + line)
        else:
            indented.append(line)
    return 'def _script():\n' + '\n'.join(indented) + '\n    return _result\n'


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
