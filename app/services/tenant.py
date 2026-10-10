"""Multi-tenant support with app-state-backed tenant store.

Tenants are stored in :class:`~app.services.app_state.AppState` so each
Gunicorn worker maintains its own isolated copy.
"""
import logging
from functools import wraps
from flask import request, g

logger = logging.getLogger(__name__)


class Tenant:
    """Represents a tenant in the multi-tenant system."""

    def __init__(self, id, name, slug, config=None):
        self.id = id
        self.name = name
        self.slug = slug
        self.config = config or {}

    def __repr__(self):
        return f'<Tenant {self.name} ({self.slug})>'


def _get_state():
    """Get AppState, falling back to module-level dict for compat."""
    try:
        from flask import current_app
        from app.services.app_state import get_state
        return get_state(current_app._get_current_object())
    except RuntimeError:
        return None


def init_tenants(app):
    """Initialize tenant support, storing tenants in AppState."""
    from app.services.app_state import get_state
    state = get_state(app)

    # Create a default tenant if none exist
    if not state.tenants:
        default = Tenant(
            id=1,
            name='Default',
            slug='default',
            config={
                'subdomain': '',
                'path_prefix': '',
            }
        )
        state.default_tenant = default
        state.tenants['default'] = default


def get_current_tenant():
    """Get the current tenant from the request context."""
    state = _get_state()
    fallback = _default_tenant if state is None else state.default_tenant
    return getattr(g, '_current_tenant', fallback)


def set_current_tenant(tenant):
    """Set the current tenant in the request context."""
    g._current_tenant = tenant


def tenant_required(f):
    """Decorator to enforce tenant isolation on routes."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        tenant = get_current_tenant()
        if tenant is None:
            from flask import abort
            abort(404)
        return f(*args, **kwargs)
    return wrapper


def get_tenant_by_subdomain(subdomain):
    """Look up a tenant by subdomain."""
    state = _get_state()
    tenants = state.tenants if state else _tenants
    for tenant in tenants.values():
        if tenant.config.get('subdomain') == subdomain:
            return tenant
    return None


def get_tenant_by_path_prefix(prefix):
    """Look up a tenant by path prefix."""
    state = _get_state()
    tenants = state.tenants if state else _tenants
    for tenant in tenants.values():
        if tenant.config.get('path_prefix') == prefix:
            return tenant
    return None


# Module-level fallbacks for backwards compatibility
_tenants = {}
_default_tenant = None
