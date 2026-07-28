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

    # Build a combined regex pattern for all slugs (safe since slugs are URL-safe)
    escaped_slugs = [re.escape(slug) for slug in module_slugs.keys()]
    slug_alt = '|'.join(escaped_slugs) if escaped_slugs else ''

    # Scan all scripts in the module
    scripts = Script.query.filter_by(module_id=module_id).all()
    for script in scripts:
        source_code = script.source_code or ''

        # Pattern 1: References to other modules by slug (e.g., url_for('module_slug.route'), redirect('/module_slug/...'))
        slug_patterns = []
        if slug_alt:
            slug_patterns.append(r"url_for\s*\(\s*['\"](" + slug_alt + r")['\"]")
            slug_patterns.append(r"redirect\s*\(\s*['\"]/" + r"/'.*".join([re.escape(slug) for slug in module_slugs.keys()]) + r"['\"]")
            slug_patterns.append(r"request\.url_root.*?(" + slug_alt + r")")

        for pattern in slug_patterns:
            try:
                matches = re.finditer(pattern, source_code, re.IGNORECASE)
                for match in matches:
                    matched_slug = match.group(1) if match.groups() else None
                    if matched_slug and matched_slug in module_slugs:
                        target_module_id = module_slugs[matched_slug]
                        dep = ModuleDependency(
                            source_module_id=module_id,
                            target_module_id=target_module_id,
                            dependency_type='route_reference',
                            reference_value=matched_slug,
                            detected_at=datetime.now(timezone.utc)
                        )
                        db.session.add(dep)
                        dependencies_found.append((script.name, matched_slug, 'route_reference'))
            except re.error:
                continue

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


def detect_cycles():
    """Detect cycles in the module dependency graph using DFS with coloring.

    Returns a list of cycles, where each cycle is a list of module slugs
    forming the circular dependency (e.g., ['alpha', 'beta', 'gamma'] means
    alpha -> beta -> gamma -> alpha).
    """
    from collections import defaultdict

    adjacency = defaultdict(set)
    all_module_ids = {m.id: m.slug for m in Module.query.all()}

    deps = ModuleDependency.query.all()
    for dep in deps:
        src_slug = all_module_ids.get(dep.source_module_id)
        tgt_slug = all_module_ids.get(dep.target_module_id)
        if src_slug and tgt_slug and src_slug != tgt_slug:
            adjacency[src_slug].add(tgt_slug)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {slug: WHITE for slug in all_module_ids.values()}
    parent = {}
    cycles = []

    def dfs(node):
        color[node] = GRAY
        for neighbor in adjacency.get(node, set()):
            if color.get(neighbor) == GRAY:
                cycle = []
                curr = node
                while curr != neighbor:
                    cycle.append(curr)
                    curr = parent.get(curr)
                    if curr is None:
                        break
                cycle.append(neighbor)
                cycle.reverse()
                cycles.append(cycle)
            elif color.get(neighbor, BLACK) == WHITE:
                parent[neighbor] = node
                dfs(neighbor)
        color[node] = BLACK

    for slug in all_module_ids.values():
        if color[slug] == WHITE:
            dfs(slug)

    return cycles


def get_graph_data():
    """Get the full dependency graph as nodes and edges for visualization."""
    modules = Module.query.all()
    nodes = [{'id': m.id, 'name': m.name, 'slug': m.slug} for m in modules]

    deps = ModuleDependency.query.all()
    edges = []
    seen = set()
    for dep in deps:
        key = (dep.source_module_id, dep.target_module_id, dep.dependency_type)
        if key not in seen:
            seen.add(key)
            src = db.session.get(Module, dep.source_module_id)
            tgt = db.session.get(Module, dep.target_module_id)
            if src and tgt:
                edges.append({
                    'source': src.slug,
                    'target': tgt.slug,
                    'type': dep.dependency_type
                })

    cycles = detect_cycles()
    return {'nodes': nodes, 'edges': edges, 'cycles': cycles}
