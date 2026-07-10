import os
from flask import Flask, request, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    if config_class:
        app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.dynamic import dynamic_bp
    from app.routes.chat import chat_bp
    from app.routes.bpmn import bpmn_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/__admin')
    app.register_blueprint(api_bp, url_prefix='/__api')
    app.register_blueprint(dynamic_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(bpmn_bp)

    from datetime import datetime as _datetime, timezone as _tz

    @app.template_filter('localtime')
    def _localtime(dt):
        if dt is None:
            return ''
        try:
            if dt.tzinfo is not None:
                return dt.astimezone().replace(tzinfo=None)
            return dt.replace(tzinfo=_tz.utc).astimezone().replace(tzinfo=None)
        except Exception:
            return dt

    upload_dir = os.path.join(app.instance_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        import os.path
        from app.models import Upload
        upload = db.session.query(Upload).filter_by(filename=filename).first()
        if not upload:
            abort(404)
        return send_from_directory(upload_dir, filename)

    @app.template_filter('attr')
    def jinja_attr(obj, name):
        return getattr(obj, name, '')

    @app.after_request
    def inject_admin_bar(response):
        if response.content_type and 'text/html' in response.content_type:
            from app.models import Setting
            site_name = Setting.get('site_name', '')
            body = response.get_data(as_text=True)

            if site_name:
                if '<title>' in body:
                    body = body.replace('<title>', f'<title>{site_name} — ')
                elif '<head>' in body:
                    body = body.replace('<head>', f'<head><title>{site_name}</title>')

            if (current_user.is_authenticated
                    and not request.path.startswith('/__api')
                    and not request.path.startswith('/__auth')):
                site_tag = f'{site_name} — ' if site_name else ''
                if current_user.role == 'admin':
                    bar = f'''<div id="admin-bar" style="position:fixed;top:0;left:0;right:0;z-index:9999;background:#1a1a2e;color:#eee;padding:6px 16px;font:13px system-ui;display:flex;gap:16px;align-items:center;flex-wrap:wrap;border-bottom:2px solid #e94560">
                <span style="font-weight:600;color:#e94560">{site_tag}Admin</span>
                <a href="/__admin/dashboard" style="color:#eee;text-decoration:none">Dashboard</a>
                <a href="/__admin/modules" style="color:#eee;text-decoration:none">Modules</a>
                <a href="/__admin/routes" style="color:#eee;text-decoration:none">Routes</a>
                <a href="/__admin/scripts" style="color:#eee;text-decoration:none">Scripts</a>
                <a href="/__admin/forms" style="color:#eee;text-decoration:none">Forms</a>
                <a href="/__admin/tasks" style="color:#eee;text-decoration:none">Tasks</a>
                <a href="/__admin/triggers" style="color:#eee;text-decoration:none">Triggers</a>
                <a href="/__admin/users" style="color:#eee;text-decoration:none">Users</a>
                <a href="/__admin/groups" style="color:#eee;text-decoration:none">Groups</a>
                <a href="/__admin/data" style="color:#eee;text-decoration:none">Data</a>
                <a href="/__admin/queries" style="color:#eee;text-decoration:none">Queries</a>
                <a href="/__admin/credentials" style="color:#eee;text-decoration:none">Credentials</a>
                <a href="/__admin/incoming-emails" style="color:#eee;text-decoration:none">Incoming</a>
                <a href="/__admin/packages" style="color:#eee;text-decoration:none">Packages</a>
                <a href="/__admin/uploads" style="color:#eee;text-decoration:none">Uploads</a>
                <a href="/__admin/chat" style="color:#eee;text-decoration:none">AI Designer</a>
                <a href="/__admin/bpmn" style="color:#eee;text-decoration:none">BPMN</a>
                <a href="/__admin/integration-health" style="color:#eee;text-decoration:none">Integrations</a>
                <a href="/__admin/settings" style="color:#eee;text-decoration:none">Settings</a>
                <span style="flex:1"></span>
                <span>{current_user.username}</span>
                <a href="/" style="color:#eee;text-decoration:none">View Site</a>
                <a href="/__auth/logout" style="color:#e94560;text-decoration:none">Logout</a>
            </div>'''
                elif current_user.role == 'developer':
                    bar = f'''<div id="admin-bar" style="position:fixed;top:0;left:0;right:0;z-index:9999;background:#1a1a2e;color:#eee;padding:6px 16px;font:13px system-ui;display:flex;gap:16px;align-items:center;flex-wrap:wrap;border-bottom:2px solid #e94560">
                <span style="font-weight:600;color:#e94560">{site_tag}Dev</span>
                <a href="/__admin/dashboard" style="color:#eee;text-decoration:none">Dashboard</a>
                <a href="/__admin/modules" style="color:#eee;text-decoration:none">Modules</a>
                <a href="/__admin/routes" style="color:#eee;text-decoration:none">Routes</a>
                <a href="/__admin/scripts" style="color:#eee;text-decoration:none">Scripts</a>
                <a href="/__admin/forms" style="color:#eee;text-decoration:none">Forms</a>
                <a href="/__admin/queries" style="color:#eee;text-decoration:none">Queries</a>
                <a href="/__admin/credentials" style="color:#eee;text-decoration:none">Credentials</a>
                <a href="/__admin/incoming-emails" style="color:#eee;text-decoration:none">Incoming</a>
                <a href="/__admin/packages" style="color:#eee;text-decoration:none">Packages</a>
                <a href="/__admin/uploads" style="color:#eee;text-decoration:none">Uploads</a>
                <a href="/__admin/chat" style="color:#eee;text-decoration:none">AI Designer</a>
                <a href="/__admin/bpmn" style="color:#eee;text-decoration:none">BPMN</a>
                <span style="flex:1"></span>
                <span>{current_user.username}</span>
                <a href="/" style="color:#eee;text-decoration:none">View Site</a>
                <a href="/__auth/logout" style="color:#e94560;text-decoration:none">Logout</a>
            </div>'''
                else:
                    bar = f'''<div id="admin-bar" style="position:fixed;top:0;left:0;right:0;z-index:9999;background:#1a1a2e;color:#eee;padding:6px 16px;font:13px system-ui;display:flex;gap:16px;align-items:center;flex-wrap:wrap;border-bottom:2px solid #e94560">
                <a href="/__auth/profile" style="color:#eee;text-decoration:none">Profile</a>
                <span style="flex:1"></span>
                <span>{current_user.username}</span>
                <a href="/" style="color:#eee;text-decoration:none">View Site</a>
                <a href="/__auth/logout" style="color:#e94560;text-decoration:none">Logout</a>
            </div>'''
                if '<body>' in body:
                    body = body.replace('<body>', f'<body style="padding-top:38px">{bar}', 1)
                else:
                    body = f'<!DOCTYPE html><html><body style="padding-top:38px">{bar}{body}</body></html>'

            response.set_data(body)
        return response

    with app.app_context():
        db.create_all()

        # Migrate: add missing columns
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        routes_cols = {c['name'] for c in inspector.get_columns('routes')}
        if 'allowed_groups' not in routes_cols:
            from sqlalchemy import text
            db.session.execute(text('ALTER TABLE routes ADD COLUMN allowed_groups TEXT DEFAULT \'\''))
            db.session.commit()

        # Add is_system to modules if missing
        mod_cols = {c['name'] for c in inspector.get_columns('modules')}
        if 'is_system' not in mod_cols:
            db.session.execute(text("ALTER TABLE modules ADD COLUMN is_system BOOLEAN DEFAULT 0"))
            db.session.commit()

        # Check if query_reports table exists and has module_id
        table_names = inspector.get_table_names()
        if 'query_reports' in table_names:
            qr_cols = {c['name'] for c in inspector.get_columns('query_reports')}
            if 'module_id' not in qr_cols:
                db.session.execute(text('ALTER TABLE query_reports ADD COLUMN module_id INTEGER REFERENCES modules(id)'))
                db.session.commit()
                # Migrate existing queries to System Automation module
                sys_mod = db.session.query(Module).filter_by(slug='system-automation').first()
                if sys_mod:
                    db.session.execute(
                        text('UPDATE query_reports SET module_id = :mid WHERE module_id IS NULL'),
                        {'mid': sys_mod.id}
                    )
                    db.session.commit()

        from app.models import Route
        from app.services.scheduler import init_scheduler
        from app.services.credential_store import init_credential_store
        init_credential_store(app)
        _debug = os.environ.get('APP_DEBUG', 'true').lower() in ('1', 'true', 'yes')
        if not _debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            init_scheduler(app)

        # Clean up duplicate route slugs — keep only the first for each slug
        seen = set()
        dupes = []
        for r in db.session.query(Route).order_by(Route.id).all():
            if r.slug in seen:
                dupes.append(r)
            else:
                seen.add(r.slug)
        for r in dupes:
            db.session.delete(r)
        if dupes:
            db.session.commit()

        # Auto-create System Automation module if missing
        from app.models import Module
        sys_mod = db.session.query(Module).filter_by(slug='system-automation').first()
        if sys_mod is None:
            sys_mod = Module(
                name='System Automation',
                slug='system-automation',
                description='Built-in system module for platform-wide automations, reports, and utilities. Cannot be deleted.',
                version='1.0.0',
                author='System',
                is_system=True,
            )
            db.session.add(sys_mod)
            db.session.commit()

    return app
