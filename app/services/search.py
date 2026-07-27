"""Global search service for finding entities across the platform."""
import logging
from typing import List, Dict, Any
from sqlalchemy import or_, text
from app import db
from app.models import Module, Route, Script, Form, User, Group, ScheduledTask, Trigger, Setting

logger = logging.getLogger(__name__)


def search_all(query: str, limit: int = 50) -> Dict[str, List[Dict[str, Any]]]:
    """Search across all entity types.
    
    Args:
        query: Search string to match against entity names/descriptions
        limit: Maximum results per entity type
        
    Returns:
        Dictionary with entity type as key and list of results as value
    """
    if not query or not query.strip():
        return {}
    
    search_term = f'%{query.strip()}%'
    results = {
        'modules': [],
        'routes': [],
        'scripts': [],
        'forms': [],
        'users': [],
        'groups': [],
        'tasks': [],
        'triggers': [],
        'settings': [],
    }
    
    try:
        results['modules'] = _search_modules(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching modules: {e}')
    
    try:
        results['routes'] = _search_routes(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching routes: {e}')
    
    try:
        results['scripts'] = _search_scripts(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching scripts: {e}')
    
    try:
        results['forms'] = _search_forms(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching forms: {e}')
    
    try:
        results['users'] = _search_users(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching users: {e}')
    
    try:
        results['groups'] = _search_groups(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching groups: {e}')
    
    try:
        results['tasks'] = _search_tasks(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching tasks: {e}')
    
    try:
        results['triggers'] = _search_triggers(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching triggers: {e}')
    
    try:
        results['settings'] = _search_settings(search_term, limit)
    except Exception as e:
        logger.error(f'Error searching settings: {e}')
    
    return results


def _search_modules(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search modules by name, slug, or description."""
    modules = Module.query.filter(
        or_(
            Module.name.ilike(query),
            Module.slug.ilike(query),
            Module.description.ilike(query)
        )
    ).limit(limit).all()
    
    return [{
        'id': m.id,
        'type': 'module',
        'name': m.name,
        'slug': m.slug,
        'description': m.description[:100] if m.description else '',
        'url': f'/__admin/modules/{m.id}/edit',
    } for m in modules]


def _search_routes(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search routes by slug or title."""
    routes = Route.query.filter(
        or_(
            Route.slug.ilike(query),
            Route.title.ilike(query)
        )
    ).limit(limit).all()
    
    return [{
        'id': r.id,
        'type': 'route',
        'name': r.slug,
        'title': r.title or r.slug,
        'module': r.module.name if r.module else 'Unknown',
        'url': f'/__admin/routes/{r.id}/edit',
    } for r in routes]


def _search_scripts(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search scripts by name or description."""
    scripts = Script.query.filter(
        or_(
            Script.name.ilike(query),
            Script.description.ilike(query)
        )
    ).limit(limit).all()
    
    return [{
        'id': s.id,
        'type': 'script',
        'name': s.name,
        'module': s.module.name if s.module else 'Unknown',
        'url': f'/__admin/scripts/{s.id}/edit',
    } for s in scripts]


def _search_forms(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search forms by name."""
    forms = Form.query.filter(
        Form.name.ilike(query)
    ).limit(limit).all()
    
    return [{
        'id': f.id,
        'type': 'form',
        'name': f.name,
        'module': f.module.name if f.module else 'Unknown',
        'url': f'/__admin/forms/{f.id}/edit',
    } for f in forms]


def _search_users(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search users by username."""
    users = User.query.filter(
        User.username.ilike(query)
    ).limit(limit).all()
    
    return [{
        'id': u.id,
        'type': 'user',
        'name': u.username,
        'role': u.role,
        'url': f'/__admin/users/{u.id}/edit',
    } for u in users]


def _search_groups(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search groups by name."""
    groups = Group.query.filter(
        Group.name.ilike(query)
    ).limit(limit).all()
    
    return [{
        'id': g.id,
        'type': 'group',
        'name': g.name,
        'url': f'/__admin/groups/{g.id}/edit',
    } for g in groups]


def _search_tasks(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search scheduled tasks by name."""
    tasks = ScheduledTask.query.filter(
        ScheduledTask.name.ilike(query)
    ).limit(limit).all()
    
    return [{
        'id': t.id,
        'type': 'task',
        'name': t.name,
        'module': t.module.name if t.module else 'Unknown',
        'url': f'/__admin/tasks/{t.id}/edit',
    } for t in tasks]


def _search_triggers(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search triggers by name."""
    triggers = Trigger.query.filter(
        Trigger.name.ilike(query)
    ).limit(limit).all()
    
    return [{
        'id': t.id,
        'type': 'trigger',
        'name': t.name,
        'module': t.module.name if t.module else 'Unknown',
        'url': f'/__admin/triggers/{t.id}/edit',
    } for t in triggers]


def _search_settings(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search settings by key."""
    settings = Setting.query.filter(
        Setting.key.ilike(query)
    ).limit(limit).all()
    
    return [{
        'id': s.id,
        'type': 'setting',
        'name': s.key,
        'url': '/__admin/settings',
    } for s in settings]
