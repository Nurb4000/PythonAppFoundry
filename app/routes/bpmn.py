from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from app import db
from app.models import Setting, Module
from app.services.ai_assistant import _call_llm, _build_system_prompt
from app.services.bundle import import_module
from app.services.audit import log_audit

bpmn_bp = Blueprint('bpmn', __name__, url_prefix='/__admin/bpmn')

BPMN_SYSTEM_PROMPT = """You are a module generator for a database-driven web application platform. Your task is to convert BPMN 2.0 process diagrams into platform module XML.

Rules:
- Analyze the BPMN process model carefully
- Each user task in BPMN becomes a route with a form
- Each script task becomes a route with a script
- Gateways (exclusive/parallel) become routing logic in scripts (use if/else with redirect())
- Sequence flows define navigation between pages (use redirect() after form submission)
- Process data objects become DynamicModel tables
- Pool/Lane assignments become auth_required or role-based access
- Start events define the entry point route (slug="/")
- End events define completion/confirmation pages
- Wrap scripts in CDATA sections
- Match script/form names exactly between routes and their definitions

"""




def _developer_or_admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_user.role not in ('admin', 'developer'):
            from flask import abort
            abort(403)
        return f(*a, **kw)
    return wrapper


@bpmn_bp.route('/')
@_developer_or_admin_required
def designer():
    module_id = request.args.get('module_id', type=int)
    module = None
    if module_id:
        module = db.session.get(Module, module_id)
    return render_template('bpmn/bpmn_page.html', module=module)


@bpmn_bp.route('/load/<int:module_id>')
@_developer_or_admin_required
def load_bpmn(module_id):
    module = db.session.get(Module, module_id)
    if not module:
        return jsonify({'success': False, 'error': 'Module not found'})
    return jsonify({
        'success': True,
        'bpmn_xml': module.bpmn_xml or '',
        'bpmn_description': module.bpmn_description or '',
        'module_name': module.name,
    })


@bpmn_bp.route('/convert', methods=['POST'])
@_developer_or_admin_required
def convert():
    data = request.get_json()
    bpmn_xml = data.get('bpmn_xml', '')
    description = data.get('description', '')

    guide_prompt = _build_system_prompt()
    user_prompt = f"""The user wants: {description}

Here is the BPMN 2.0 process model:
{bpmn_xml}

Generate a complete platform module XML that implements this workflow."""

    messages = [
        {'role': 'system', 'content': BPMN_SYSTEM_PROMPT + '\n\n' + guide_prompt},
        {'role': 'user', 'content': user_prompt},
    ]

    response = _call_llm(messages)
    if response.startswith('Error:'):
        return jsonify({'success': False, 'error': response})

    # Extract XML from response
    import re
    blocks = re.findall(r'```xml\s*\n(.*?)\n```', response, re.DOTALL)
    if blocks:
        xml_str = blocks[-1]
    else:
        match = re.search(r'<module\b', response)
        if match:
            xml_str = response[match.start():]
        else:
            xml_str = response

    return jsonify({'success': True, 'xml': xml_str})


@bpmn_bp.route('/import', methods=['POST'])
@_developer_or_admin_required
def import_route():
    data = request.get_json()
    xml_str = data.get('xml', '')
    if not xml_str.strip():
        return jsonify({'success': False, 'error': 'No XML provided'})

    try:
        module_id = data.get('module_id')
        module = import_module(xml_str, update_existing=bool(module_id), module_id=module_id)
        # Store the BPMN source data on the module
        bpmn_xml = data.get('bpmn_xml', '')
        bpmn_desc = data.get('bpmn_description', '')
        if bpmn_xml or bpmn_desc:
            module.bpmn_xml = bpmn_xml
            module.bpmn_description = bpmn_desc
            db.session.commit()
        log_audit('import', 'module', module.id, module.name, details='source=bpmn')
        try:
            from app.routes.admin import create_auto_version
            create_auto_version(module.id)
        except Exception:
            pass
        return jsonify({
            'success': True,
            'name': module.name,
            'slug': module.slug,
            'id': module.id,
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Import error: {e}'})
