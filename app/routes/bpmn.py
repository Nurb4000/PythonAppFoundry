from flask import Blueprint, request, jsonify, render_template_string
from flask_login import login_required, current_user

from app import db
from app.models import Setting, Module
from app.services.ai_assistant import _call_llm, _build_system_prompt
from app.services.bundle import import_module

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

BPMN_PAGE = '''<!DOCTYPE html>
<html>
<head><title>BPMN Workflow Designer</title>
<link rel="stylesheet" href="/static/bpmn-js/assets/diagram-js.css">
<link rel="stylesheet" href="/static/bpmn-js/assets/bpmn-js.css">
<link rel="stylesheet" href="/static/bpmn-js/assets/bpmn-font/css/bpmn.css">
<style>
* { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; margin: 0; background: #fff; color: #333; }
.layout { display: flex; height: calc(100vh - 37px); }
.sidebar { width: 380px; min-width: 380px; background: #f5f5f5; padding: 16px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; border-right: 1px solid #ddd; }
.sidebar h2 { font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.sidebar label { font-size: 12px; color: #666; display: block; margin-bottom: 4px; }
.sidebar input, .sidebar select, .sidebar textarea { width: 100%; padding: 8px 10px; background: #fff; border: 1px solid #ccc; color: #333; border-radius: 4px; font-size: 13px; }
.sidebar textarea { resize: vertical; font-family: inherit; }
.sidebar textarea#description { min-height: 80px; }
.sidebar textarea#result { min-height: 200px; font-family: 'Courier New', monospace; font-size: 12px; }
.canvas-wrap { flex: 1; position: relative; background: #fff; }
#canvas { width: 100%; height: 100%; min-height: 400px; }
.canvas-placeholder { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px; pointer-events: none; z-index: 0; }
.btn { padding: 8px 16px; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 600; background: #fff; color: #333; }
.btn:hover { background: #f0f0f0; }
.btn-primary { background: #007bff; color: #fff; border-color: #007bff; }
.btn-primary:hover { background: #0056b3; }
.btn-success { background: #28a745; color: #fff; border-color: #28a745; }
.btn-success:hover { background: #218838; }
.btn-sm { padding: 4px 10px; font-size: 11px; }
.section { margin-bottom: 12px; }
.status { padding: 8px 12px; border-radius: 4px; font-size: 12px; display: none; white-space: pre-wrap; word-break: break-word; }
.status.error { display: block; background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
.status.success { display: block; background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
.status.loading { display: block; background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
/* BPMN palette and canvas element visibility */
.djs-palette { background: #f5f5f5 !important; border: 1px solid #ccc !important; }
.djs-palette .entry { color: #333 !important; font-size: 16px !important; }
.djs-palette .entry:hover { background: #e0e0e0 !important; }
.djs-palette .entry.selected { background: #d0d0d0 !important; }
.djs-palette-header { background: #e8e8e8 !important; color: #333 !important; font-weight: 600 !important; padding: 6px !important; }
.djs-palette .group { border-bottom: 1px solid #ddd !important; }
.bjs-container .djs-label { fill: #333 !important; font-size: 12px !important; }
.djs-shape .djs-visual > rect,
.djs-shape .djs-visual > circle,
.djs-shape .djs-visual > ellipse,
.djs-shape .djs-visual > polygon { stroke: #333 !important; fill: #fafafa !important; }
.djs-shape .djs-visual > path { stroke: #333 !important; fill: #fafafa !important; }
.djs-connection .djs-visual > path { stroke: #666 !important; }
.djs-connection .djs-visual > polygon { stroke: #666 !important; fill: #666 !important; }
.bjs-bendpoint > circle { fill: #007bff !important; stroke: #fff !important; }
</style>
</head>
<body>
<div class="layout">
<div class="sidebar">
<div class="section" style="display:flex;gap:6px;flex-wrap:wrap;">
<button class="btn btn btn-sm" onclick="loadExample()">Load Example</button>
<button class="btn btn btn-sm" onclick="resetCanvas()">New</button>
<button class="btn btn btn-sm" onclick="document.getElementById('fileInput').click()">Open File</button>
<input type="file" id="fileInput" accept=".bpmn,.xml" style="display:none" onchange="handleFile(event)">
<button class="btn btn btn-sm" onclick="exportXML()">Download</button>
</div>
<div class="section">
<h2>Process Description</h2>
<textarea id="description" placeholder="Describe what this workflow should do..."></textarea>
</div>
<div class="section">
<h2>BPMN XML</h2>
<textarea id="bpmnXml" style="min-height:100px;font-family:'Courier New',monospace;font-size:11px;" placeholder="Paste BPMN XML or load a file..."></textarea>
<button class="btn btn btn-sm" onclick="loadBpmnXml()" style="margin-top:4px;">Load into Modeler</button>
</div>
<div class="section" style="display:flex;gap:8px;">
<button class="btn btn-success" onclick="convertToModule()" style="flex:1;padding:12px;font-size:15px;">Convert to Module</button>
</div>
<div id="status" class="status"></div>
<div class="section">
<h2>Generated Module XML</h2>
<div style="display:flex;gap:8px;margin-bottom:4px;">
<button class="btn btn btn-sm" onclick="copyResult()">Copy XML</button>
<button class="btn btn-primary btn-sm" id="importBtn" style="display:none;" onclick="importModule()">Import Module</button>
</div>
<textarea id="result" readonly placeholder="Module XML will appear here after conversion..."></textarea>
</div>
</div>
<div class="canvas-wrap">
<div class="canvas-placeholder" id="placeholder">Loading BPMN modeler...</div>
<div id="canvas"></div>
</div>
</div>
<script>
var modeler = null;
function loadBpmn(xml) {
  if (!modeler) { setStatus('Modeler not ready', 'error'); return; }
  setStatus('Importing BPMN diagram...', 'loading');
  var el = document.getElementById('placeholder');
  if (el) el.style.display = 'none';
  modeler.importXML(xml).then(function() {
    var canvas = modeler.get('canvas');
    canvas.zoom('fit-viewport');
    setStatus('Diagram loaded', 'success');
    modeler.saveXML({ format: true }).then(function(r) {
      document.getElementById('bpmnXml').value = r.xml;
    });
  }).catch(function(err) {
    setStatus('Failed to load diagram: ' + (err.message || err), 'error');
  });
}
function loadExample() {
  document.getElementById('description').value = 'Create a request approval workflow where users submit requests that need manager approval or rejection.';
  var xml = `<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
  id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_1" isExecutable="true">
    <startEvent id="Start_1" name="Start"><outgoing>Flow_1</outgoing></startEvent>
    <task id="Task_1" name="Submit Request"><incoming>Flow_1</incoming><outgoing>Flow_2</outgoing></task>
    <exclusiveGateway id="Gateway_1" name="Approved?" default="Flow_4">
      <incoming>Flow_2</incoming><outgoing>Flow_3</outgoing><outgoing>Flow_4</outgoing>
    </exclusiveGateway>
    <task id="Task_2" name="Approve"><incoming>Flow_3</incoming><outgoing>Flow_5</outgoing></task>
    <task id="Task_3" name="Reject"><incoming>Flow_4</incoming><outgoing>Flow_6</outgoing></task>
    <endEvent id="End_1" name="Done"><incoming>Flow_5</incoming><incoming>Flow_6</incoming></endEvent>
    <sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>
    <sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="Gateway_1"/>
    <sequenceFlow id="Flow_3" name="Yes" sourceRef="Gateway_1" targetRef="Task_2"/>
    <sequenceFlow id="Flow_4" name="No" sourceRef="Gateway_1" targetRef="Task_3"/>
    <sequenceFlow id="Flow_5" sourceRef="Task_2" targetRef="End_1"/>
    <sequenceFlow id="Flow_6" sourceRef="Task_3" targetRef="End_1"/>
  </process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="S_Start_1" bpmnElement="Start_1"><dc:Bounds x="156" y="82" width="36" height="36"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="S_Task_1" bpmnElement="Task_1"><dc:Bounds x="252" y="65" width="100" height="70"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="S_Gateway_1" bpmnElement="Gateway_1"><dc:Bounds x="412" y="70" width="50" height="50"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="S_Task_2" bpmnElement="Task_2"><dc:Bounds x="522" y="65" width="100" height="70"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="S_Task_3" bpmnElement="Task_3"><dc:Bounds x="522" y="185" width="100" height="70"/></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="S_End_1" bpmnElement="End_1"><dc:Bounds x="682" y="82" width="36" height="36"/></bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="E_Flow_1" bpmnElement="Flow_1"><di:waypoint x="192" y="100"/><di:waypoint x="252" y="100"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="E_Flow_2" bpmnElement="Flow_2"><di:waypoint x="352" y="100"/><di:waypoint x="412" y="95"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="E_Flow_3" bpmnElement="Flow_3"><di:waypoint x="462" y="95"/><di:waypoint x="522" y="100"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="E_Flow_4" bpmnElement="Flow_4"><di:waypoint x="437" y="120"/><di:waypoint x="572" y="185"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="E_Flow_5" bpmnElement="Flow_5"><di:waypoint x="622" y="100"/><di:waypoint x="682" y="100"/></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="E_Flow_6" bpmnElement="Flow_6"><di:waypoint x="622" y="220"/><di:waypoint x="700" y="220"/><di:waypoint x="700" y="118"/></bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</definitions>`;
  loadBpmn(xml);
}
function handleFile(event) {
  var file = event.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) { loadBpmn(e.target.result); };
  reader.readAsText(file);
  event.target.value = '';
}
function loadBpmnXml() {
  var xml = document.getElementById('bpmnXml').value.trim();
  if (!xml) { setStatus('No XML to load', 'error'); return; }
  loadBpmn(xml);
}
function resetCanvas() {
  if (!modeler) return;
  var empty = '<?xml version="1.0" encoding="UTF-8"?><definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" id="d1" targetNamespace="http://bpmn.io/schema/bpmn"><process id="p1" isExecutable="true"/><bpmndi:BPMNDiagram id="di1"><bpmndi:BPMNPlane id="pl1" bpmnElement="p1"/></bpmndi:BPMNDiagram></definitions>';
  loadBpmn(empty);
  document.getElementById('description').value = '';
  document.getElementById('bpmnXml').value = '';
  document.getElementById('result').value = '';
  document.getElementById('importBtn').style.display = 'none';
  setStatus('Canvas cleared', 'success');
}
function exportXML() {
  if (!modeler) { setStatus('Modeler not ready', 'error'); return; }
  modeler.saveXML({ format: true }).then(function(r) {
    var blob = new Blob([r.xml], { type: 'application/xml' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'workflow.bpmn';
    a.click();
    URL.revokeObjectURL(url);
  }).catch(function(err) { setStatus('Export failed', 'error'); });
}
function setStatus(msg, type) {
  var el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status ' + type;
}
function copyResult() {
  var el = document.getElementById('result');
  el.select();
  document.execCommand('copy');
  setStatus('XML copied', 'success');
}
function convertToModule() {
  if (!modeler) { setStatus('Modeler not ready', 'error'); return; }
  var description = document.getElementById('description').value.trim();
  if (!description) { setStatus('Please enter a process description', 'error'); return; }
  document.getElementById('result').value = '';
  setStatus('Getting diagram and converting...', 'loading');
  document.getElementById('importBtn').style.display = 'none';
  modeler.saveXML({ format: true }).then(function(r) {
    fetch('/__admin/bpmn/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bpmn_xml: r.xml, description: description }),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      if (data.success) {
        document.getElementById('result').value = data.xml;
        document.getElementById('importBtn').style.display = 'inline-block';
        setStatus('Module XML generated. Click Import to add it.', 'success');
      } else {
        setStatus('Error: ' + data.error, 'error');
      }
    })
    .catch(function(err) { setStatus('Request failed: ' + err.message, 'error'); });
  }).catch(function(err) { setStatus('Failed to get diagram: ' + (err.message || err), 'error'); });
}
var bpmnModuleId = {% if module %}{{ module.id }}{% else %}null{% endif %};
function importModule() {
  var xml = document.getElementById('result').value.trim();
  if (!xml) { setStatus('No XML to import', 'error'); return; }
  setStatus('Importing module...', 'loading');
  modeler.saveXML({ format: true }).then(function(r) {
    fetch('/__admin/bpmn/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        xml: xml,
        bpmn_xml: r.xml,
        bpmn_description: document.getElementById('description').value.trim(),
        module_id: bpmnModuleId,
      }),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      if (data.success) {
        window.location.href = '/__admin/modules/edit/' + data.id;
      } else {
        setStatus('Import failed: ' + data.error, 'error');
      }
    })
    .catch(function(err) { setStatus('Import request failed: ' + err.message, 'error'); });
  }).catch(function(err) { setStatus('Failed to get diagram: ' + (err.message || err), 'error'); });
}
</script>
<script src="/static/bpmn-js/bpmn-modeler.production.min.js"></script>
<script>
try {
  modeler = new BpmnJS({ container: '#canvas' });
  document.getElementById('placeholder').style.display = 'none';
  {% if module %}
  fetch('/__admin/bpmn/load/{{ module.id }}').then(function(r) { return r.json(); }).then(function(d) {
    if (d.success && d.bpmn_xml) {
      document.getElementById('description').value = d.bpmn_description;
      modeler.importXML(d.bpmn_xml).then(function() {
        setStatus('Loaded BPMN for ' + d.module_name, 'success');
        modeler.get('canvas').zoom('fit-viewport');
      }).catch(function(err) {
        setStatus('Failed to load BPMN: ' + err.message, 'error');
      });
    } else {
      loadExample();
    }
  }).catch(function() { loadExample(); });
  {% else %}
  loadExample();
  {% endif %}
} catch (e) {
  setStatus('Modeler init failed: ' + e.message, 'error');
  document.getElementById('placeholder').textContent = 'Failed: ' + e.message;
}
</script>
</body>
</html>
'''


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
    return render_template_string(BPMN_PAGE, module=module)


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
