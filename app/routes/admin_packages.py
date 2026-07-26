"""Admin routes for Python package management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, Response
import subprocess, json, io
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required

packages_bp = Blueprint('packages', __name__)


@packages_bp.route('/packages', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def admin_packages():
    pip_bin = 'pip'
    output_lines = []
    install_error = ''
    selected = request.form.get('selected', '')
    protected_pkgs = {
        'flask', 'flask-sqlalchemy', 'flask-login', 'flask-migrate',
        'sqlalchemy', 'werkzeug', 'jinja2', 'markupsafe',
        'itsdangerous', 'click', 'greenlet', 'blinker',
        'bcrypt', 'apscheduler', 'python-slugify', 'python-dotenv',
        'cryptography', 'pip', 'setuptools', 'wheel',
    }

    if request.method == 'POST':
        if 'install' in request.form:
            pkg = request.form.get('package', '').strip()
            if pkg:
                cmd = [pip_bin, 'install'] + pkg.split()
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    output_lines = (r.stdout or '').splitlines() + (r.stderr or '').splitlines()
                    if r.returncode != 0:
                        install_error = f'Exit code {r.returncode}'
                except subprocess.TimeoutExpired:
                    install_error = 'Install timed out after 120s'
                except FileNotFoundError:
                    install_error = f'pip not found at "{pip_bin}"'
        elif 'uninstall' in request.form:
            pkg = request.form.get('package', '').strip()
            if pkg:
                pkg_name = pkg.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0].strip()
                if pkg_name.lower() in protected_pkgs:
                    install_error = f'"{pkg_name}" is a protected platform package and cannot be uninstalled.'
                else:
                    cmd = [pip_bin, 'uninstall', '-y', pkg]
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        output_lines = (r.stdout or '').splitlines() + (r.stderr or '').splitlines()
                        if r.returncode != 0:
                            install_error = f'Exit code {r.returncode}'
                    except subprocess.TimeoutExpired:
                        install_error = 'Uninstall timed out after 60s'
                    except FileNotFoundError:
                        install_error = f'pip not found at "{pip_bin}"'

    packages = []
    try:
        r = subprocess.run([pip_bin, 'list', '--format=json'], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            packages = json.loads(r.stdout)
        else:
            install_error = f'Error listing packages:\n{r.stderr}'
    except FileNotFoundError:
        install_error = f'pip not found at "{pip_bin}"'

    output_text = '\n'.join(output_lines)
    return render_admin('Python Packages', '''
<script>
function fillUninstall(name) { document.getElementById('uninstall-input').value = name; }
</script>
<h2>Python Packages</h2>

<div style="display:flex;gap:24px;flex-wrap:wrap;">
<div style="flex:1;min-width:300px;">
<h3>Installed Packages</h3>
<div style="max-height:500px;overflow-y:auto;border:1px solid #ddd;border-radius:4px;">
<table style="width:100%;border-collapse:collapse;">
<thead><tr style="background:#f4f4f4;"><th style="padding:6px 10px;text-align:left;border-bottom:1px solid #ddd;">Package</th><th style="padding:6px 10px;text-align:left;border-bottom:1px solid #ddd;">Version</th><th style="padding:6px 10px;text-align:left;border-bottom:1px solid #ddd;">Actions</th></tr></thead>
<tbody>
{% for pkg in packages %}
{% set pkg_lower = pkg.name.lower() %}
<tr style="border-bottom:1px solid #eee;">
  <td style="padding:6px 10px;font-size:0.85em;">{{ pkg.name }}{% if pkg_lower in protected_pkgs %} <span style="color:#999;font-size:0.8em;" title="Platform package — protected">&#128274;</span>{% endif %}</td>
  <td style="padding:6px 10px;font-size:0.85em;color:#666;">{{ pkg.version }}</td>
  <td style="padding:6px 10px;font-size:0.85em;">
    {% if pkg_lower in protected_pkgs %}<span style="color:#999;">Protected</span>{% else %}<a href="#" onclick="fillUninstall('{{ pkg.name }}');return false;" style="color:#dc3545;">Uninstall</a>{% endif %}
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
</div>

<div style="flex:1;min-width:300px;">
<h3>Install Package</h3>
<form method="POST" style="margin-bottom:24px;">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label style="display:block;margin-bottom:8px;">
  <strong>Package name</strong><br>
  <input name="package" type="text" value="{{ selected }}" placeholder="requests requests==2.31.0" style="padding:6px 10px;width:100%;max-width:400px;"><br>
  <span style="color:#888;font-size:0.85em;">Name with optional <code>==version</code>. Multiple space-separated names are allowed.</span>
</label>
<button name="install" type="submit" style="padding:8px 20px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Install</button>
</form>

<h3>Uninstall Package</h3>
<form method="POST" onsubmit="return confirm('Uninstall ' + document.getElementById('uninstall-input').value + '?')">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label style="display:block;margin-bottom:8px;">
  <strong>Package name</strong><br>
  <input id="uninstall-input" name="package" type="text" value="{{ selected }}" placeholder="requests" style="padding:6px 10px;width:100%;max-width:400px;"><br>
</label>
<button name="uninstall" type="submit" style="padding:8px 20px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;">Uninstall</button>
</form>

{% if output_text %}
<h3>Command Output</h3>
<div style="max-height:400px;overflow-y:auto;border:1px solid {% if install_error %}#fcc{% else %} #ddd{% endif %};border-radius:4px;background:#f4f4f4;padding:8px;">
<pre style="margin:0;font-size:0.85em;white-space:pre-wrap;">{{ output_text }}</pre>
</div>
{% endif %}
</div>
</div>
''', packages=packages, protected_pkgs=protected_pkgs, output_text=output_text, install_error=install_error, selected=selected)
