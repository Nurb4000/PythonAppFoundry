from flask import Blueprint, request, redirect, url_for, render_template_string, abort, jsonify, flash, Response
from app.services.scheduler import refresh_tasks
from app.services.csrf import csrf_protect, csrf_token
from app.services.validation import validate_slug, validate_route_slug, validate_cron_expression
from app.services.admin_utils import (
    admin_required as _admin_required,
    developer_or_admin_required as _dev_admin_required,
    create_auto_version as _create_auto_version,
    AttrProxy as _AttrProxy,
    render_admin as _render_admin,
    list_view as _list_view,
    _export_csv as _export_csv_util,
    ADMIN_TEMPLATE,
    LIST_TEMPLATE,
)
from flask_login import login_required, current_user
from sqlalchemy import func, inspect as sa_inspect
from sqlalchemy import Table, MetaData
import csv, io, os, subprocess
from datetime import datetime as _datetime, timezone as _tz

from app import db
from app.models import User, Module, Route, Script, Form, ScheduledTask, Trigger, ChatSession, ChatMessage, Upload, Setting, Group, ExecutionLog, ModuleVersion, QueryReport, IncomingEmail, Credential
from app.services.script_runner import execute_script

admin_bp = Blueprint('admin', __name__)

# Re-export utilities for use in this file
admin_required = _admin_required
developer_or_admin_required = _dev_admin_required
create_auto_version = _create_auto_version
AttrProxy = _AttrProxy
render_admin = _render_admin
list_view = _list_view
export_csv = _export_csv_util
# ── Blueprint Registration ──
# Import and register all admin blueprints
from app.routes.admin_blueprints import register_admin_blueprints

# Register all blueprints with the admin blueprint
register_admin_blueprints(admin_bp)
