from flask import Blueprint, request, redirect, url_for, flash
import os
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required, render_admin
from app import db
from app.models import Module

marketplace_bp = Blueprint('marketplace', __name__)


@marketplace_bp.route('/')
@developer_or_admin_required
def module_marketplace():
    """Browse and install modules from the marketplace."""
    from app.services.marketplace import list_available_modules
    available = list_available_modules()
    
    # Check which are already installed
    installed_slugs = {m.slug for m in db.session.query(Module.slug).all()}
    
    return render_admin('Module Marketplace', 'admin/marketplace/list.html', available=available, installed_slugs=installed_slugs)


@marketplace_bp.route('/<slug>/install', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def install_marketplace_module(slug):
    """Install a module from the marketplace."""
    from app.services.marketplace import get_module_info
    from app.services.bundle import import_module
    
    info = get_module_info(slug)
    if not info:
        flash(f'Module "{slug}" not found in marketplace', 'error')
        return redirect(url_for('admin.marketplace.module_marketplace'))
    
    xml_path = info.get('xml_source')
    if not xml_path or not os.path.exists(xml_path):
        flash(f'Module XML not found for "{slug}"', 'error')
        return redirect(url_for('admin.marketplace.module_marketplace'))
    
    try:
        with open(xml_path) as f:
            xml_str = f.read()
        module = import_module(xml_str)
        flash(f'Module "{module.name}" installed from marketplace')
    except Exception as e:
        flash(f'Installation failed: {e}', 'error')
    
    return redirect(url_for('admin.marketplace.module_marketplace'))

