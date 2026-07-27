"""Admin blueprints registration - imports and registers all admin route blueprints."""
from flask import Blueprint
from app.routes.admin_modules import modules_bp
from app.routes.admin_routes import routes_bp
from app.routes.admin_scripts import scripts_bp
from app.routes.admin_forms import forms_bp
from app.routes.admin_tasks import tasks_bp
from app.routes.admin_triggers import triggers_bp
from app.routes.admin_users import users_bp
from app.routes.admin_groups import groups_bp
from app.routes.admin_data import data_bp
from app.routes.admin_uploads import uploads_bp
from app.routes.admin_packages import packages_bp
from app.routes.admin_settings import settings_bp
from app.routes.admin_queries import queries_bp
from app.routes.admin_credentials import credentials_bp
from app.routes.admin_incoming_email import incoming_email_bp
from app.routes.admin_dashboard import dashboard_bp
from app.routes.admin_backup import backup_bp
from app.routes.admin_marketplace import marketplace_bp
from app.routes.admin_versions import versions_bp
from app.routes.admin_test_script import test_script_bp
from app.routes.admin_import_preview import import_preview_bp
from app.routes.admin_openapi import openapi_bp
from app.routes.admin_dead_letter import dead_letter_bp
from app.routes.admin_audit import audit_bp
from app.routes.admin_templates import templates_bp
from app.routes.admin_db_migration import db_migration_bp
from app.routes.admin_search import search_bp

def register_admin_blueprints(admin_bp: Blueprint):
    """Register all admin sub-blueprints with the main admin blueprint."""
    admin_bp.register_blueprint(modules_bp, url_prefix='/modules')
    admin_bp.register_blueprint(routes_bp, url_prefix='/routes')
    admin_bp.register_blueprint(scripts_bp, url_prefix='/scripts')
    admin_bp.register_blueprint(forms_bp, url_prefix='/forms')
    admin_bp.register_blueprint(tasks_bp, url_prefix='/tasks')
    admin_bp.register_blueprint(triggers_bp, url_prefix='/triggers')
    admin_bp.register_blueprint(users_bp, url_prefix='/users')
    admin_bp.register_blueprint(groups_bp, url_prefix='/groups')
    admin_bp.register_blueprint(data_bp, url_prefix='/data')
    admin_bp.register_blueprint(uploads_bp, url_prefix='/uploads')
    admin_bp.register_blueprint(packages_bp, url_prefix='/packages')
    admin_bp.register_blueprint(settings_bp, url_prefix='/settings')
    admin_bp.register_blueprint(queries_bp, url_prefix='/queries')
    admin_bp.register_blueprint(credentials_bp, url_prefix='/credentials')
    admin_bp.register_blueprint(incoming_email_bp, url_prefix='/incoming-emails')
    admin_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    admin_bp.register_blueprint(backup_bp, url_prefix='/backup')
    admin_bp.register_blueprint(marketplace_bp, url_prefix='/marketplace')
    admin_bp.register_blueprint(versions_bp, url_prefix='/modules/<int:module_id>/versions')
    admin_bp.register_blueprint(test_script_bp, url_prefix='/scripts/test')
    admin_bp.register_blueprint(import_preview_bp, url_prefix='/import-preview')
    admin_bp.register_blueprint(openapi_bp, url_prefix='/__api')
    admin_bp.register_blueprint(dead_letter_bp, url_prefix='/dead-letter')
    admin_bp.register_blueprint(audit_bp, url_prefix='/audit')
    admin_bp.register_blueprint(templates_bp, url_prefix='/templates')
    admin_bp.register_blueprint(db_migration_bp, url_prefix='/db-migration')
    admin_bp.register_blueprint(search_bp, url_prefix='/search')
