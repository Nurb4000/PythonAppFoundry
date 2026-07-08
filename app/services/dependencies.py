import re
import logging
from datetime import datetime, timezone
from app import db
from app.models import Module, ModuleDependency, Route, Script, Form

logger = logging.getLogger(__name__)


def detect_dependencies(module_id):
    """Scan a module's scripts for references to other modules and create dependency records."""
    module = db.session.get(Module, module_id)
    if not module:
        raise ValueError(f'Module with id {module_id} not found')

    # Clear existing dependencies for this module
    ModuleDependency.query.filter_by(source_module_id=module_id).delete()
    db.session.commit()

    # Get all other modules for reference matching
    all_modules = Module.query.filter(Module.id != module_id).all()
    module_slugs = {m.slug: m.id for m in all_modules}
    module_ids = {m.id: m.slug for m in all_modules}

    dependencies_found = []

    # Scan all scripts in the module
    scripts = Script.query.filter_by(module_id=module_id).all()
    for script in scripts:
        source_code = script.source_code or ''

        # Pattern 1: References to other modules by slug (e.g., url_for('module_slug.route'), redirect('/module_slug/...'))
        slug_patterns = [
            r"url_for\s*\(\s*['\"]" + r"|'.*".join([re.escape(slug) for slug in module_slugs.keys()]) + r"['\"]",
            r"redirect\s*\(\s*['\"]/" + r"|'.*".join([re.escape(slug) for slug in module_slugs.keys()]) + r"['\"]",
            r"request\.url_root.*" + r"|'.*".join([re.escape(slug) for slug in module_slugs.keys()]) + r"['\"]",
        ]

        for pattern in slug_patterns:
            matches = re.finditer(pattern, source_code, re.IGNORECASE)
            for match in matches:
                # Extract the slug from the match
                for slug in module_slugs.keys():
                    if slug in match.group(0):
                        target_module_id = module_slugs[slug]
                        dep = ModuleDependency(
                            source_module_id=module_id,
                            target_module_id=target_module_id,
                            dependency_type='route_reference',
                            reference_value=slug,
                            detected_at=datetime.now(timezone.utc)
                        )
                        db.session.add(dep)
                        dependencies_found.append((script.name, slug, 'route_reference'))
                        break

        # Pattern 2: References to other modules' scripts by ID
        script_ref_pattern = r'script_id\s*=\s*(\d+)'
        matches = re.finditer(script_ref_pattern, source_code)
        for match in matches:
            script_id = int(match.group(1))
            # Check if this script belongs to another module
            other_script = db.session.get(Script, script_id)
            if other_script and other_script.module_id != module_id:
                target_module_id = other_script.module_id
                dep = ModuleDependency(
                    source_module_id=module_id,
                    target_module_id=target_module_id,
                    dependency_type='script_reference',
                    reference_value=str(script_id),
                    detected_at=datetime.now(timezone.utc)
                )
                db.session.add(dep)
                dependencies_found.append((script.name, f'script#{script_id}', 'script_reference'))

    db.session.commit()
    return dependencies_found


def get_dependencies(module_id):
    """Get all modules that depend on the given module (modules that reference it)."""
    module = db.session.get(Module, module_id)
    if not module:
        raise ValueError(f'Module with id {module_id} not found')

    # Find all dependencies where this module is the target
    dependencies = ModuleDependency.query.filter_by(
        target_module_id=module_id
    ).all()

    result = []
    for dep in dependencies:
        source_module = db.session.get(Module, dep.source_module_id)
        if source_module:
            result.append({
                'source_module': source_module,
                'dependency_type': dep.dependency_type,
                'reference_value': dep.reference_value,
                'detected_at': dep.detected_at
            })

    return result


def get_dependency_count(module_id):
    """Get the number of modules that depend on the given module."""
    return ModuleDependency.query.filter_by(
        target_module_id=module_id
    ).count()


def has_dependencies(module_id):
    """Check if a module has any dependencies (other modules reference it)."""
    return get_dependency_count(module_id) > 0
