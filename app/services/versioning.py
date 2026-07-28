import difflib
import logging
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from app import db
from app.models import Module, ModuleVersion, User
from app.services.bundle import export_module

logger = logging.getLogger(__name__)


def create_version(module_id, comment='', user_id=None):
    """Create a version snapshot of the current module state."""
    module = db.session.get(Module, module_id)
    if not module:
        raise ValueError(f'Module with id {module_id} not found')

    # Generate version number
    existing_versions = ModuleVersion.query.filter_by(
        module_id=module_id
    ).order_by(ModuleVersion.id.desc()).all()

    if existing_versions:
        last_version = existing_versions[0].version_number
        try:
            parts = last_version.split('.')
            if len(parts) == 3:
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
                new_version = f'{major}.{minor}.{patch + 1}'
            else:
                new_version = f'{len(existing_versions) + 1}.0.0'
        except (ValueError, IndexError):
            new_version = f'{len(existing_versions) + 1}.0.0'
    else:
        new_version = '1.0.0'

    # Export current module state
    snapshot_xml = export_module(module)

    # Create version record
    version = ModuleVersion(
        module_id=module_id,
        version_number=new_version,
        snapshot_xml=snapshot_xml,
        comment=comment,
        created_by_id=user_id,
        is_current=True,
    )

    # Mark all previous versions as not current
    for v in existing_versions:
        v.is_current = False

    db.session.add(version)
    db.session.commit()

    logger.info(f'Created version {new_version} for module {module.name}')
    return version


def get_versions(module_id):
    """Get all versions for a module, ordered by creation date (newest first)."""
    return ModuleVersion.query.filter_by(
        module_id=module_id
    ).order_by(ModuleVersion.created_at.desc()).all()


def get_version(version_id):
    """Get a specific version by ID."""
    return db.session.get(ModuleVersion, version_id)


def restore_version(version_id):
    """Restore a module to a previous version."""
    version = db.session.get(ModuleVersion, version_id)
    if not version:
        raise ValueError(f'Version with id {version_id} not found')

    module = version.module

    # Import the snapshot (this will delete current children and recreate them)
    from app.services.bundle import import_module
    try:
        restored_module = import_module(version.snapshot_xml, update_existing=True, module_id=module.id)
        
        # Update the module's version to match the restored version
        restored_module.version = version.version_number
        db.session.commit()

        logger.info(f'Restored module {module.name} to version {version.version_number}')
        return restored_module
    except Exception as e:
        db.session.rollback()
        raise ValueError(f'Failed to restore version: {str(e)}')


def diff_versions(version_id_1, version_id_2):
    """Get a diff between two versions."""
    v1 = db.session.get(ModuleVersion, version_id_1)
    v2 = db.session.get(ModuleVersion, version_id_2)

    if not v1 or not v2:
        raise ValueError('One or both versions not found')

    # Split into lines for diff
    lines1 = v1.snapshot_xml.splitlines(keepends=True)
    lines2 = v2.snapshot_xml.splitlines(keepends=True)

    # Generate unified diff
    diff = difflib.unified_diff(
        lines1, lines2,
        fromfile=f'Version {v1.version_number}',
        tofile=f'Version {v2.version_number}',
        lineterm=''
    )

    return ''.join(diff)


def get_version_count(module_id):
    """Get the total number of versions for a module."""
    return ModuleVersion.query.filter_by(module_id=module_id).count()


def _parse_xml_safe(xml_str):
    """Parse XML string, return root element or None on failure."""
    try:
        return ET.fromstring(xml_str)
    except ET.ParseError:
        return None


def _compare_attrs(old_elem, new_elem, tag):
    """Compare attribute dicts for two elements of the same tag."""
    old_attrs = dict(old_elem.attrib) if old_elem is not None else {}
    new_attrs = dict(new_elem.attrib) if new_elem is not None else {}
    changes = {}
    all_keys = set(list(old_attrs.keys()) + list(new_attrs.keys()))
    for key in all_keys:
        old_val = old_attrs.get(key, '')
        new_val = new_attrs.get(key, '')
        if old_val != new_val:
            changes[key] = {'old': old_val, 'new': new_val}
    return changes


def _compare_text_content(old_elem, new_elem, child_tag):
    """Compare text content of a specific child element."""
    old_text = (old_elem.findtext(child_tag) if old_elem is not None else '') or ''
    new_text = (new_elem.findtext(child_tag) if new_elem is not None else '') or ''
    if old_text.strip() != new_text.strip():
        return {'old': old_text, 'new': new_text}
    return {}


def _diff_collection(old_root, new_root, collection_tag, name_attr, text_child=None, sub_elements=None):
    """
    Compare a named collection of elements between two module roots.
    
    Returns dict with 'added', 'removed', 'modified' keys.
    - added: list of element names that exist in new but not old
    - removed: list of element names that exist in old but not new
    - modified: list of dicts with 'name', 'changes' for elements present in both but different
    """
    result = {'added': [], 'removed': [], 'modified': []}

    if old_root is None or new_root is None:
        return result

    old_coll = old_root.find(collection_tag)
    new_coll = new_root.find(collection_tag)

    old_items = {}
    new_items = {}

    if old_coll is not None:
        for elem in old_coll.findall(name_attr if name_attr else ''):
            n = elem.get('name', elem.get('slug', elem.tag))
            old_items[n] = elem

    if new_coll is not None:
        for elem in new_coll.findall(name_attr if name_attr else ''):
            n = elem.get('name', elem.get('slug', elem.tag))
            new_items[n] = elem

    old_names = set(old_items.keys())
    new_names = set(new_items.keys())

    for name in new_names - old_names:
        result['added'].append(name)

    for name in old_names - new_names:
        result['removed'].append(name)

    for name in old_names & new_names:
        old_elem = old_items[name]
        new_elem = new_items[name]

        attr_changes = _compare_attrs(old_elem, new_elem, name_attr or 'name')
        text_changes = {}
        if text_child:
            text_changes = _compare_text_content(old_elem, new_elem, text_child)

        all_changes = {**attr_changes, **text_changes}
        if all_changes:
            result['modified'].append({'name': name, 'changes': all_changes})

    return result


def structured_diff_versions(version_id_1, version_id_2):
    """
    Produce a structured, categorized diff between two module versions.
    
    Returns a dict with sections: metadata, scripts, routes, forms, templates,
    scheduled_tasks, triggers, query_reports, credentials, requirements.
    Each section has 'added', 'removed', 'modified' lists.
    """
    v1 = db.session.get(ModuleVersion, version_id_1)
    v2 = db.session.get(ModuleVersion, version_id_2)

    if not v1 or not v2:
        raise ValueError('One or both versions not found')

    root1 = _parse_xml_safe(v1.snapshot_xml)
    root2 = _parse_xml_safe(v2.snapshot_xml)

    if not root1 or not root2:
        raise ValueError('Failed to parse version XML snapshots')

    diff = {
        'version_1': v1.version_number,
        'version_2': v2.version_number,
        'metadata': {},
        'scripts': {'added': [], 'removed': [], 'modified': []},
        'routes': {'added': [], 'removed': [], 'modified': []},
        'forms': {'added': [], 'removed': [], 'modified': []},
        'templates': {'added': [], 'removed': [], 'modified': []},
        'scheduled_tasks': {'added': [], 'removed': [], 'modified': []},
        'triggers': {'added': [], 'removed': [], 'modified': []},
        'query_reports': {'added': [], 'removed': [], 'modified': []},
        'credentials': {'added': [], 'removed': [], 'modified': []},
        'requirements': {},
    }

    # Module-level metadata comparison
    meta_fields = ['name', 'slug', 'version', 'author']
    for field in meta_fields:
        old_val = root1.get(field, '')
        new_val = root2.get(field, '')
        if old_val != new_val:
            diff['metadata'][field] = {'old': old_val, 'new': new_val}

    # Description
    desc_changes = _compare_text_content(root1, root2, 'description')
    if desc_changes:
        diff['metadata']['description'] = desc_changes

    # Scripts (name attribute, source_code is text content)
    diff['scripts'] = _diff_collection(root1, root2, 'scripts', 'script', text_child=None)
    # For scripts, also compare source_code (stored as text of the script element)
    old_scripts_elem = root1.find('scripts')
    new_scripts_elem = root2.find('scripts')
    if old_scripts_elem is not None and new_scripts_elem is not None:
        old_script_map = {s.get('name'): s for s in old_scripts_elem.findall('script')}
        new_script_map = {s.get('name'): s for s in new_scripts_elem.findall('script')}
        common_names = set(old_script_map.keys()) & set(new_script_map.keys())
        # Rebuild modified list to include source_code comparison
        source_changes = []
        for name in common_names:
            old_s = old_script_map[name]
            new_s = new_script_map[name]
            old_src = (old_s.text or '').strip()
            new_src = (new_s.text or '').strip()
            if old_src != new_src:
                source_changes.append({'name': name, 'changes': {'source_code': {'old': old_src[:200], 'new': new_src[:200]}}})
        diff['scripts']['modified'] = source_changes

    # Routes (slug attribute)
    diff['routes'] = _diff_collection(root1, root2, 'routes', 'route')

    # Forms (name attribute, schema is text content)
    old_forms_elem = root1.find('forms')
    new_forms_elem = root2.find('forms')
    form_diff = _diff_collection(root1, root2, 'forms', 'form')
    if old_forms_elem is not None and new_forms_elem is not None:
        old_form_map = {f.get('name'): f for f in old_forms_elem.findall('form')}
        new_form_map = {f.get('name'): f for f in new_forms_elem.findall('form')}
        common_names = set(old_form_map.keys()) & set(new_form_map.keys())
        schema_changes = []
        for name in common_names:
            old_f = old_form_map[name]
            new_f = new_form_map[name]
            old_schema = (old_f.text or '').strip()
            new_schema = (new_f.text or '').strip()
            if old_schema != new_schema:
                schema_changes.append({'name': name, 'changes': {'schema': {'old': old_schema[:200], 'new': new_schema[:200]}}})
        form_diff['modified'] = schema_changes
    diff['forms'] = form_diff

    # Templates (name attribute, body is child element)
    diff['templates'] = _diff_collection(root1, root2, 'templates', 'template')

    # Scheduled tasks (name attribute)
    diff['scheduled_tasks'] = _diff_collection(root1, root2, 'scheduled_tasks', 'task')

    # Triggers (name attribute)
    diff['triggers'] = _diff_collection(root1, root2, 'triggers', 'trigger')

    # Query reports (name attribute)
    diff['query_reports'] = _diff_collection(root1, root2, 'query_reports', 'query_report')

    # Requirements (text content of <requirements> element)
    old_req = (root1.findtext('requirements') or '').strip()
    new_req = (root2.findtext('requirements') or '').strip()
    if old_req != new_req:
        diff['requirements'] = {'old': old_req, 'new': new_req}

    return diff


def validate_restore_dependencies(version_id):
    """
    Validate that restoring a version won't break dependencies.
    
    Scans the snapshot XML for references to other modules by slug.
    Returns a dict with:
      - 'safe': bool, whether restore is safe
      - 'warnings': list of warning strings
      - 'errors': list of error strings
      - 'referenced_slugs': list of module slugs referenced in the snapshot
    """
    version = db.session.get(ModuleVersion, version_id)
    if not version:
        raise ValueError(f'Version with id {version_id} not found')

    root = _parse_xml_safe(version.snapshot_xml)
    if not root:
        return {'safe': False, 'warnings': [], 'errors': ['Failed to parse version XML'], 'referenced_slugs': []}

    result = {'safe': True, 'warnings': [], 'errors': [], 'referenced_slugs': []}

    # Collect all current module slugs
    all_modules = Module.query.all()
    current_slugs = {m.slug for m in all_modules}

    # Scan scripts for url_for references to other module slugs
    scripts_elem = root.find('scripts')
    if scripts_elem is not None:
        for script_elem in scripts_elem.findall('script'):
            source = (script_elem.text or '').strip()
            if not source:
                continue
            # Find url_for('slug...') patterns
            import re
            url_for_matches = re.findall(r"url_for\s*\(\s*['\"]([^'\"]+)'[\"']", source)
            for match in url_for_matches:
                slug = match.split('.')[0] if '.' in match else match
                if slug not in current_slugs and slug:
                    result['referenced_slugs'].append(slug)
                    result['warnings'].append(
                        f'Script "{script_elem.get("name", "unknown")}" references module slug "{slug}" '
                        f'which does not exist in the current installation'
                    )

    # Scan route scripts for redirect patterns
    routes_elem = root.find('routes')
    if routes_elem is not None:
        for route_elem in routes_elem.findall('route'):
            script_ref = route_elem.get('script', '')
            if script_ref:
                result['referenced_slugs'].append(f'route:{script_ref}')

    # Check if any referenced slugs are missing
    if result['warnings']:
        result['safe'] = False

    return result
