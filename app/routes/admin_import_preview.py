from flask import Blueprint, request, jsonify
import xml.etree.ElementTree as ET
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required
from app import db
from app.models import Module

import_preview_bp = Blueprint('import_preview', __name__)


@import_preview_bp.route('/', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def import_preview():
    """Preview what will be imported from an XML file without actually importing."""
    if 'import_xml' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    xml_file = request.files['import_xml']
    if not xml_file.filename:
        return jsonify({'error': 'Empty filename'}), 400
    
    try:
        from app.services.bundle import import_module
        xml_str = xml_file.read().decode('utf-8')
        
        # Parse XML to extract preview info without importing
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_str)
        
        if root.tag != 'module':
            return jsonify({'error': 'Root element must be <module>'}), 400
        
        name = root.get('name', 'Untitled')
        slug = root.get('slug', '')
        
        # Count items that would be imported
        scripts = root.find('scripts')
        script_count = len(scripts.findall('script')) if scripts is not None else 0
        
        routes = root.find('routes')
        route_count = len(routes.findall('route')) if routes is not None else 0
        
        forms = root.find('forms')
        form_count = len(forms.findall('form')) if forms is not None else 0
        
        tasks = root.find('scheduled_tasks')
        task_count = len(tasks.findall('task')) if tasks is not None else 0
        
        triggers = root.find('triggers')
        trigger_count = len(triggers.findall('trigger')) if triggers is not None else 0

        creds = root.find('credentials')
        cred_count = len(creds.findall('credential')) if creds is not None else 0

        requirements = root.find('requirements')
        has_requirements = bool(requirements is not None and requirements.text and requirements.text.strip())

        # Check for existing module with same slug
        existing = db.session.query(Module).filter_by(slug=slug).first()
        
        return jsonify({
            'success': True,
            'preview': {
                'name': name,
                'slug': slug,
                'existing': existing is not None,
                'existing_id': existing.id if existing else None,
                'counts': {
                    'scripts': script_count,
                    'routes': route_count,
                    'forms': form_count,
                    'tasks': task_count,
                    'triggers': trigger_count,
                    'credentials': cred_count,
                    'has_requirements': has_requirements,
                }
            }
        })
    except ET.ParseError as e:
        return jsonify({'error': f'Invalid XML: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

