"""Multi-tenant support for the platform.

Each tenant has its own isolated set of modules, routes, and data.
Tenants are identified by a subdomain or path prefix.
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


# In-memory tenant store (would typically be database-backed)
_tenants = {}
_default_tenant = None


def init_tenants(app):
    """Initialize tenant support from app config."""
    global _default_tenant
    
    # Create a default tenant if none exist
    if not _tenants:
        _default_tenant = Tenant(
            id=1,
            name='Default',
            slug='default',
            config={
                'subdomain': '',
                'path_prefix': '',
            }
        )
        _tenants['default'] = _default_tenant


def get_current_tenant():
    """Get the current tenant from the request context."""
    return getattr(g, '_current_tenant', _default_tenant)


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
    for tenant in _tenants.values():
        if tenant.config.get('subdomain') == subdomain:
            return tenant
    return None


def get_tenant_by_path_prefix(prefix):
    """Look up a tenant by path prefix."""
    for tenant in _tenants.values():
        if tenant.config.get('path_prefix') == prefix:
            return tenant
    return None
