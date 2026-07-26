"""Admin routes for XML import preview."""
from flask import Blueprint, request, redirect, url_for, jsonify, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required
import xml.etree.ElementTree as ET

import_preview_bp = Blueprint('import_preview', __name__)


@import_preview_bp.route('/import-preview', methods=['POST'])
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
        xml_str = xml_file.read().decode('utf-8')
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
        
        # Check for existing module with same slug
        from app.models import Module
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
                }
            }
        })
    except ET.ParseError as e:
        return jsonify({'error': f'Invalid XML: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400
