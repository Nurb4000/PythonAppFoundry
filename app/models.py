from datetime import datetime, timezone
import logging

from flask_login import UserMixin
from sqlalchemy import Table, Column, Integer, String, Text, Boolean, DateTime, Float, Date, LargeBinary, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql.type_api import TypeEngine

from app import db

logger = logging.getLogger(__name__)

_dynamic_models = {}


class _ModelQueryProperty:
    def __get__(self, obj, cls):
        return db.session.query(cls)


class DynamicModel:
    @staticmethod
    def get_or_create(name, columns=None):
        from sqlalchemy import inspect as _sa_inspect

        table_name = name.lower()

        if name in _dynamic_models:
            inspector = _sa_inspect(db.engine)
            if table_name in inspector.get_table_names():
                return _dynamic_models[name]
            del _dynamic_models[name]
            if table_name in db.metadata.tables:
                del db.metadata.tables[table_name]

        if columns is None:
            columns = {}

        cols = [
            Column('id', Integer, primary_key=True),
        ]
        for col_name, col_type in columns.items():
            if isinstance(col_type, type) and issubclass(col_type, TypeEngine):
                cols.append(Column(col_name, col_type))
            elif isinstance(col_type, TypeEngine):
                cols.append(Column(col_name, type(col_type)))
            else:
                cols.append(Column(col_name, String(200)))

        table = Table(table_name, db.metadata, *cols, extend_existing=True)
        table.create(db.engine, checkfirst=True)

        Base = declarative_base()

        model = type(name, (Base,), {
            '__table__': table,
            '__tablename__': table_name,
            '__repr__': lambda self: f'<{name} id={getattr(self, "id", None)}>',
            'query': _ModelQueryProperty(),
        })

        _dynamic_models[name] = model
        logger.info(f'Created dynamic model: {name} (table: {table_name})')
        return model


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    groups = db.relationship('Group', secondary='user_groups', back_populates='users', lazy='select')

    def __repr__(self):
        return f'<User {self.username}>'


user_groups = db.Table('user_groups',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True),
)


class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default='')

    users = db.relationship('User', secondary=user_groups, back_populates='groups')

    def __repr__(self):
        return f'<Group {self.name}>'


class Module(db.Model):
    __tablename__ = 'modules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    version = db.Column(db.String(20), default='1.0.0')
    author = db.Column(db.String(100), default='')
    enabled = db.Column(db.Boolean, default=True)
    bpmn_xml = db.Column(db.Text, default='')
    bpmn_description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Module {self.name}>'


class ModuleVersion(db.Model):
    __tablename__ = 'module_versions'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False, index=True)
    version_number = db.Column(db.String(50), nullable=False)
    snapshot_xml = db.Column(db.Text, nullable=False)
    comment = db.Column(db.String(500), default='')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_current = db.Column(db.Boolean, default=False)

    module = db.relationship('Module', backref=db.backref('versions', lazy='dynamic', cascade='all, delete-orphan'))
    created_by = db.relationship('User')

    def __repr__(self):
        return f'<ModuleVersion {self.module_id}:{self.version_number}>'


class ModuleDependency(db.Model):
    __tablename__ = 'module_dependencies'

    id = db.Column(db.Integer, primary_key=True)
    source_module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False, index=True)
    target_module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False, index=True)
    dependency_type = db.Column(db.String(50), default='route_reference')  # route_reference, script_reference, form_reference
    reference_value = db.Column(db.String(500), default='')  # slug or id being referenced
    detected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    source_module = db.relationship('Module', foreign_keys=[source_module_id], backref=db.backref('dependencies_from', lazy='dynamic'))
    target_module = db.relationship('Module', foreign_keys=[target_module_id], backref=db.backref('dependencies_to', lazy='dynamic'))

    def __repr__(self):
        return f'<ModuleDependency {self.source_module_id}->{self.target_module_id}>'


class Route(db.Model):
    __tablename__ = 'routes'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    slug = db.Column(db.String(500), nullable=False)
    methods = db.Column(db.String(100), default='GET')
    script_id = db.Column(db.Integer, db.ForeignKey('scripts.id'), nullable=True)
    form_id = db.Column(db.Integer, db.ForeignKey('forms.id'), nullable=True)
    auth_required = db.Column(db.Boolean, default=False)
    allowed_groups = db.Column(db.Text, default='')
    title = db.Column(db.String(200), default='')

    module = db.relationship('Module', backref=db.backref('routes', lazy='dynamic'))
    script = db.relationship('Script', foreign_keys=[script_id],
                             post_update=True)
    form = db.relationship('Form', foreign_keys=[form_id],
                           post_update=True)

    def __repr__(self):
        return f'<Route {self.slug} [{self.methods}]>'


class Script(db.Model):
    __tablename__ = 'scripts'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    language = db.Column(db.String(20), default='python')
    source_code = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    module = db.relationship('Module', backref=db.backref('scripts', lazy='dynamic'))

    def __repr__(self):
        return f'<Script {self.name}>'


class Form(db.Model):
    __tablename__ = 'forms'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    schema_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    module = db.relationship('Module', backref=db.backref('forms', lazy='dynamic'))

    def __repr__(self):
        return f'<Form {self.name}>'


class ScheduledTask(db.Model):
    __tablename__ = 'scheduled_tasks'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    script_id = db.Column(db.Integer, db.ForeignKey('scripts.id'), nullable=True)
    cron_expression = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)

    module = db.relationship('Module', backref=db.backref('scheduled_tasks', lazy='dynamic'))
    script = db.relationship('Script')

    def __repr__(self):
        return f'<ScheduledTask {self.name} [{self.cron_expression}]>'


class Trigger(db.Model):
    __tablename__ = 'triggers'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    target_table = db.Column(db.String(100), nullable=False)
    script_id = db.Column(db.Integer, db.ForeignKey('scripts.id'), nullable=True)
    enabled = db.Column(db.Boolean, default=True)

    module = db.relationship('Module', backref=db.backref('triggers', lazy='dynamic'))
    script = db.relationship('Script')

    def __repr__(self):
        return f'<Trigger {self.name} on {self.event_type}:{self.target_table}>'


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), default='New Module')
    status = db.Column(db.String(20), default='active')
    latest_xml = db.Column(db.Text, nullable=True)
    module_id = db.Column(db.Integer, ForeignKey('modules.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User')

    def __repr__(self):
        return f'<ChatSession {self.title}>'


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, ForeignKey('chat_sessions.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    session = db.relationship('ChatSession', backref=db.backref('messages', lazy='dynamic',
                                                                order_by='ChatMessage.created_at'))

class Upload(db.Model):
    __tablename__ = 'uploads'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(500), nullable=False)
    original_name = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Upload {self.filename}>'


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=False)

    @classmethod
    def get(cls, key, default=''):
        row = db.session.query(cls).filter_by(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value):
        row = db.session.query(cls).filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(cls(key=key, value=value))
        db.session.commit()


class ExecutionLog(db.Model):
    __tablename__ = 'execution_logs'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    source_type = db.Column(db.String(20), nullable=False)
    source_name = db.Column(db.String(200), nullable=False)
    duration_ms = db.Column(db.Integer, default=0)
    status = db.Column(db.String(10), default='success')
    stdout = db.Column(db.Text, default='')
    error_message = db.Column(db.Text, default='')

    def __repr__(self):
        return f'<ExecutionLog {self.source_type}:{self.source_name} {self.status}>'
