import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from slugify import slugify

from app import db
from app.models import Module, Route, Script, Form, ScheduledTask, Trigger


def export_module(module):
    root = ET.Element('module')
    root.set('name', module.name)
    root.set('slug', module.slug)
    root.set('version', module.version)
    root.set('author', module.author)

    desc = ET.SubElement(root, 'description')
    desc.text = module.description

    routes_elem = ET.SubElement(root, 'routes')
    for route in module.routes:
        r = ET.SubElement(routes_elem, 'route')
        r.set('slug', route.slug)
        r.set('method', route.methods)
        r.set('title', route.title)
        r.set('auth_required', str(route.auth_required).lower())
        if route.script:
            r.set('script', route.script.name)
        if route.form:
            r.set('form', route.form.name)

    scripts_elem = ET.SubElement(root, 'scripts')
    for script in module.scripts:
        s = ET.SubElement(scripts_elem, 'script')
        s.set('name', script.name)
        s.set('language', script.language)
        s.text = f'\n{script.source_code}\n'

    forms_elem = ET.SubElement(root, 'forms')
    for form in module.forms:
        f = ET.SubElement(forms_elem, 'form')
        f.set('name', form.name)
        f.text = f'\n{form.schema_json}\n'

    tasks_elem = ET.SubElement(root, 'scheduled_tasks')
    for task in module.scheduled_tasks:
        t = ET.SubElement(tasks_elem, 'task')
        t.set('name', task.name)
        t.set('script', task.script.name if task.script else '')
        t.set('schedule', task.cron_expression)

    triggers_elem = ET.SubElement(root, 'triggers')
    for trigger in module.triggers:
        tg = ET.SubElement(triggers_elem, 'trigger')
        tg.set('name', trigger.name)
        tg.set('event', trigger.event_type)
        tg.set('table', trigger.target_table)
        tg.set('script', trigger.script.name if trigger.script else '')

    return ET.tostring(root, encoding='unicode', xml_declaration=True)


def import_module(xml_str, update_existing=False, module_id=None):
    root = ET.fromstring(xml_str)

    if root.tag != 'module':
        raise ValueError('Root element must be <module>')

    name = root.get('name', 'Untitled')
    new_slug = root.get('slug', slugify(name))
    version = root.get('version', '1.0.0')
    author = root.get('author', '')

    # Determine existing module to update
    existing = None
    if module_id:
        existing = db.session.get(Module, module_id)
        if not existing:
            raise ValueError(f'Module with id {module_id} not found')
    else:
        existing = db.session.query(Module).filter_by(slug=new_slug).first()

    if existing:
        if update_existing:
            existing.routes.delete()
            existing.scripts.delete()
            existing.forms.delete()
            existing.scheduled_tasks.delete()
            existing.triggers.delete()
            # Update in place to preserve the module ID
            module = existing
            module.name = name
            module.slug = new_slug
            module.description = root.findtext('description') or ''
            # Auto-bump patch version when updating
            try:
                parts = module.version.split('.')
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
                module.version = f'{major}.{minor}.{patch + 1}'
            except (IndexError, ValueError):
                module.version = version
            module.author = author
            db.session.flush()
        else:
            raise ValueError(f'Module with slug "{new_slug}" already exists')
    else:
        module = Module(
            name=name,
            slug=new_slug,
            description=(root.findtext('description') or ''),
            version=version,
            author=author,
        )
        db.session.add(module)
        db.session.flush()

    # Scripts first (routes/tasks/triggers reference them)
    scripts_elem = root.find('scripts')
    script_map = {}
    if scripts_elem is not None:
        for s_elem in scripts_elem.findall('script'):
            script = Script(
                module_id=module.id,
                name=s_elem.get('name', 'unnamed'),
                language=s_elem.get('language', 'python'),
                source_code=(s_elem.text or '').strip(),
            )
            db.session.add(script)
            db.session.flush()
            script_map[script.name] = script

    # Forms
    forms_elem = root.find('forms')
    form_map = {}
    if forms_elem is not None:
        for f_elem in forms_elem.findall('form'):
            form = Form(
                module_id=module.id,
                name=f_elem.get('name', 'unnamed'),
                schema_json=(f_elem.text or '').strip() or '[]',
            )
            db.session.add(form)
            db.session.flush()
            form_map[form.name] = form

    # Routes
    routes_elem = root.find('routes')
    if routes_elem is not None:
        # Check for conflicting route slugs with existing modules
        for r_elem in routes_elem.findall('route'):
            route_slug = r_elem.get('slug', '/')
            existing_route = db.session.query(Route).filter_by(slug=route_slug).first()
            if existing_route and existing_route.module_id != module.id:
                if update_existing:
                    db.session.delete(existing_route)
                    db.session.flush()
                else:
                    raise ValueError(
                        f'Route slug "{route_slug}" is already in use by '
                        f'module "{existing_route.module.name}". '
                        'Delete that route or use update_existing.'
                    )

        for r_elem in routes_elem.findall('route'):
            route = Route(
                module_id=module.id,
                slug=r_elem.get('slug', '/'),
                methods=r_elem.get('method', 'GET'),
                title=r_elem.get('title', ''),
                auth_required=r_elem.get('auth_required', 'false').lower() == 'true',
                script_id=script_map[r_elem.get('script', '')].id
                         if r_elem.get('script') in script_map else None,
                form_id=form_map[r_elem.get('form', '')].id
                        if r_elem.get('form') in form_map else None,
            )
            db.session.add(route)

    # Scheduled tasks
    tasks_elem = root.find('scheduled_tasks')
    if tasks_elem is not None:
        for t_elem in tasks_elem.findall('task'):
            task = ScheduledTask(
                module_id=module.id,
                name=t_elem.get('name', 'unnamed'),
                cron_expression=t_elem.get('schedule', '0 0 * * *'),
                script_id=script_map[t_elem.get('script', '')].id
                         if t_elem.get('script') in script_map else None,
            )
            db.session.add(task)

    # Triggers
    triggers_elem = root.find('triggers')
    if triggers_elem is not None:
        for tg_elem in triggers_elem.findall('trigger'):
            trigger = Trigger(
                module_id=module.id,
                name=tg_elem.get('name', 'unnamed'),
                event_type=tg_elem.get('event', 'on_insert'),
                target_table=tg_elem.get('table', ''),
                script_id=script_map[tg_elem.get('script', '')].id
                         if tg_elem.get('script') in script_map else None,
            )
            db.session.add(trigger)

    db.session.commit()

    # Auto-detect dependencies for the imported module
    try:
        from app.services.dependencies import detect_dependencies
        detect_dependencies(module.id)
    except Exception as e:
        # Log but don't fail the import if dependency detection fails
        import logging
        logging.getLogger(__name__).warning(f'Failed to detect dependencies for module {module.id}: {e}')

    return module
