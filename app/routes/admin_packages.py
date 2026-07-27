"""Admin routes for Python packages management."""
from flask import Blueprint, request, redirect, url_for, flash
import subprocess
import json as _json
from app.services.admin_utils import admin_required, render_admin
from app.services.audit import log_audit

packages_bp = Blueprint('packages', __name__)

@packages_bp.route('/')
@admin_required
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
                    else:
                        log_audit('install', 'package', details=pkg)
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
                        else:
                            log_audit('uninstall', 'package', details=pkg)
                    except subprocess.TimeoutExpired:
                        install_error = 'Uninstall timed out after 60s'
                    except FileNotFoundError:
                        install_error = f'pip not found at "{pip_bin}"'

    # Get installed packages list
    packages = []
    try:
        r = subprocess.run([pip_bin, 'list', '--format=json'], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            packages = _json.loads(r.stdout)
        else:
            install_error = f'Error listing packages:\n{r.stderr}'
    except FileNotFoundError:
        install_error = f'pip not found at "{pip_bin}"'

    output_text = '\n'.join(output_lines)
    return render_admin('Python Packages', 'admin/packages/list.html', packages=packages, protected_pkgs=protected_pkgs, output_text=output_text, install_error=install_error, selected=selected)
