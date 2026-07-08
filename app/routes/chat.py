from flask import Blueprint, request, jsonify, render_template_string, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import ChatSession, ChatMessage, Module
from app.services.ai_assistant import chat_completion
from app.services.bundle import import_module, export_module

chat_bp = Blueprint('chat', __name__, url_prefix='/__admin/chat')

CHAT_PAGE = '''<!DOCTYPE html>
<html>
<head><title>AI Module Designer</title>
<style>
body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 960px; }
.chat-layout { display: flex; height: calc(100vh - 37px - 32px); }
nav { background: #f5f5f5; width: 240px; padding: 1rem; border-right: 1px solid #ddd; overflow-y: auto; }
nav h3 { margin: 0 0 0.5rem 0; }
nav a { display: block; padding: 0.4rem; color: #333; text-decoration: none; border-radius: 4px; }
nav a:hover { background: #e0e0e0; }
nav a.active { background: #007bff; color: #fff; }
nav .new-btn { background: #28a745; color: #fff; text-align: center; padding: 0.5rem; border-radius: 4px; margin-bottom: 1rem; }
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.header { padding: 0.75rem 1rem; border-bottom: 1px solid #ddd; background: #fafafa; display: flex; justify-content: space-between; align-items: center; }
.header h2 { margin: 0; font-size: 1.1rem; }
.msgs { flex: 1; overflow-y: auto; padding: 1rem; }
.msg { margin-bottom: 1rem; max-width: 80%; padding: 0.75rem; border-radius: 8px; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; }
.msg.user { background: #007bff; color: #fff; margin-left: auto; }
.msg.assistant { background: #f0f0f0; color: #333; }
.msg .xml-block { background: #1e1e1e; color: #d4d4d4; padding: 0.75rem; border-radius: 4px; font-family: monospace; font-size: 0.85rem; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; overflow-x: auto; margin-top: 0.5rem; max-height: 300px; overflow-y: auto; }
.msg .actions { margin-top: 0.5rem; }
.msg .actions button { margin-right: 0.5rem; padding: 0.3rem 0.75rem; border: none; border-radius: 4px; cursor: pointer; }
.btn-import { background: #28a745; color: #fff; }
.btn-preview { background: #6c757d; color: #fff; }
.btn-approve { background: #ffc107; color: #000; }
.err { color: #c00; background: #ffe0e0; padding: 0.5rem; border-radius: 4px; margin: 0.5rem 0; }
.input-area { padding: 1rem; border-top: 1px solid #ddd; display: flex; gap: 0.5rem; }
.input-area textarea { flex: 1; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; resize: none; font-family: inherit; min-height: 48px; }
.input-area button { padding: 0.5rem 1.5rem; background: #007bff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #ccc; border-top-color: #007bff; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 0.5rem; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="chat-layout">
<nav>
<a class="new-btn" href="{{ url_for('chat.new_session') }}">+ New Module</a>
<h3>Sessions</h3>
{% for s in sessions %}
<a href="{{ url_for('chat.view_session', id=s.id) }}" {% if s.id == session.id %}class="active"{% endif %}>{{ s.title }}</a>
{% endfor %}
</nav>
<div class="main">
<div class="header">
<h2>{{ session.title }}</h2>
<div>
<form method="POST" action="{{ url_for('chat.delete_session', id=session.id) }}" style="display:inline" onsubmit="return confirm('Delete this session? This cannot be undone.')">
  <button type="submit" style="background:#dc3545;color:#fff;border:none;padding:0.3rem 0.75rem;border-radius:4px;cursor:pointer;margin-right:0.5rem;">Delete</button>
</form>
{% if session.latest_xml %}
<button class="btn-preview" onclick="previewXml()">Preview XML</button>
<form method="POST" action="{{ url_for('chat.import_module_route', id=session.id) }}" style="display:inline">
  <input type="text" name="version_comment" placeholder="Version comment (optional)" style="padding:0.3rem 0.5rem;border:1px solid #ccc;border-radius:4px;margin-right:0.5rem;width:180px;font-size:0.85rem;">
  <button class="btn-import" type="submit">Import Module</button>
</form>
{% endif %}
</div>
</div>
<div class="msgs" id="msgArea">
{% for m in messages %}
<div class="msg {{ m.role }}">{{ m.content }}
{% if m.role == 'assistant' and loop.last and session.latest_xml %}
<div class="xml-block">{{ session.latest_xml }}</div>
{% endif %}
</div>
{% endfor %}
</div>
<form class="input-area" id="chatForm" method="POST" action="{{ url_for('chat.send_message', id=session.id) }}">
<textarea name="message" rows="2" placeholder="Describe the module you want..." required autofocus></textarea>
<button type="submit" id="sendBtn">Send</button>
</form>
</div>
<script>
document.getElementById('chatForm').onsubmit = function() {
  document.getElementById('sendBtn').disabled = true;
  document.getElementById('sendBtn').innerHTML = '<span class="spinner"></span> Thinking...';
};
function previewXml() {
  const xml = {{ session.latest_xml|tojson|safe }};
  const w = window.open('', '_blank', 'width=600,height=400');
  w.document.write('<pre style="background:#1e1e1e;color:#d4d4d4;padding:1rem;overflow:auto;height:100vh;margin:0">' + xml.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</pre>');
}
var area = document.getElementById('msgArea');
area.scrollTop = area.scrollHeight;
</script>
</div>
<div style="text-align:center;color:#999;font-size:0.8em;padding:0.5rem 0;border-top:1px solid #eee;">Copyright 2026 IDS</div>
</body>
</html>
'''

NO_SESSION = '''<!DOCTYPE html>
<html>
<head><title>AI Module Designer</title>
<style>
body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 960px; }
.chat-layout { display: flex; height: calc(100vh - 37px - 32px); }
nav { background: #f5f5f5; width: 240px; padding: 1rem; border-right: 1px solid #ddd; overflow-y: auto; }
nav h3 { margin: 0 0 0.5rem 0; }
nav a { display: block; padding: 0.4rem; color: #333; text-decoration: none; border-radius: 4px; }
nav a:hover { background: #e0e0e0; }
.main { flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
</head>
<body>
<div class="chat-layout">
<nav>
<a href="{{ url_for('chat.new_session') }}" style="background:#28a745;color:#fff;text-align:center;padding:0.5rem;border-radius:4px;margin-bottom:1rem">+ New Module</a>
<h3>Sessions</h3>
{% for s in sessions %}
<a href="{{ url_for('chat.view_session', id=s.id) }}">{{ s.title }}</a>
{% endfor %}
</nav>
<div class="main"><p>Select a session or create a new one.</p></div>
</div>
<div style="text-align:center;color:#999;font-size:0.8em;padding:0.5rem 0;border-top:1px solid #eee;">Copyright 2026 IDS</div>
</body>
</html>
'''


@chat_bp.route('/')
@login_required
def index():
    sessions = db.session.query(ChatSession).filter_by(
        user_id=current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    return render_template_string(NO_SESSION, sessions=sessions)


@chat_bp.route('/new')
@login_required
def new_session():
    session = ChatSession(user_id=current_user.id)
    db.session.add(session)
    db.session.commit()
    first_msg = ChatMessage(
        session_id=session.id,
        role='assistant',
        content='Hello! Describe the module you want to build — what it does, what data it manages, what routes it needs, and who can access them.',
    )
    db.session.add(first_msg)
    db.session.commit()
    return redirect(url_for('chat.view_session', id=session.id))


@chat_bp.route('/<int:id>')
@login_required
def view_session(id):
    session = ChatSession.query.get_or_404(id)
    if session.user_id != current_user.id and current_user.role != 'admin':
        return 'Forbidden', 403
    sessions = db.session.query(ChatSession).filter_by(
        user_id=current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    messages = session.messages.order_by(ChatMessage.created_at).all()
    return render_template_string(CHAT_PAGE, session=session, messages=messages,
                                   sessions=sessions)


@chat_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_session(id):
    session = ChatSession.query.get_or_404(id)
    if session.user_id != current_user.id and current_user.role != 'admin':
        return 'Forbidden', 403
    ChatMessage.query.filter_by(session_id=session.id).delete()
    db.session.delete(session)
    db.session.commit()
    flash('Session deleted')
    return redirect(url_for('chat.index'))


@chat_bp.route('/<int:id>/send', methods=['POST'])
@login_required
def send_message(id):
    session = ChatSession.query.get_or_404(id)
    if session.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403

    text = request.form.get('message', '').strip()
    if not text:
        flash('Message cannot be empty')
        return redirect(url_for('chat.view_session', id=id))

    user_msg = ChatMessage(session_id=id, role='user', content=text)
    db.session.add(user_msg)
    db.session.commit()

    messages = session.messages.order_by(ChatMessage.created_at).all()
    history = [{'role': m.role, 'content': m.content} for m in messages]

    result = chat_completion(history)

    reply_text = result['reply']
    if result.get('xml'):
        session.latest_xml = result['xml']
        try:
            valid, err = result.get('valid'), result.get('error')
            if valid:
                reply_text += '\n\n---\n✅ The XML above is valid and ready for import.'
            else:
                reply_text += f'\n\n---\n⚠️ XML validation issue: {err}'
        except Exception:
            pass
        session.title = _guess_title(result['xml']) or session.title

    assistant_msg = ChatMessage(session_id=id, role='assistant', content=reply_text)
    db.session.add(assistant_msg)
    db.session.commit()

    return redirect(url_for('chat.view_session', id=id))


@chat_bp.route('/<int:id>/import', methods=['POST'])
@login_required
def import_module_route(id):
    session = ChatSession.query.get_or_404(id)
    if session.user_id != current_user.id and current_user.role != 'admin':
        return 'Forbidden', 403

    if not session.latest_xml:
        flash('No XML to import')
        return redirect(url_for('chat.view_session', id=id))

    try:
        module = import_module(session.latest_xml, update_existing=True)
        session.status = 'imported'
        session.module_id = module.id
        db.session.commit()
        
        # Get version comment from form (optional)
        version_comment = request.form.get('version_comment', '').strip()
        if not version_comment:
            version_comment = f'Imported from AI Designer'
        
        try:
            from app.routes.admin import create_auto_version
            create_auto_version(module.id, comment=version_comment)
        except Exception:
            pass
        
        flash(f'Module "{module.name}" imported successfully!')
        return redirect(url_for('admin.list_modules'))
    except Exception as e:
        flash(f'Import failed: {e}', 'error')
        return redirect(url_for('chat.view_session', id=id))


@chat_bp.route('/<int:id>/xml')
@login_required
def get_xml(id):
    session = ChatSession.query.get_or_404(id)
    if session.user_id != current_user.id and current_user.role != 'admin':
        return 'Forbidden', 403
    return session.latest_xml or '', 200, {'Content-Type': 'text/plain'}


@chat_bp.route('/refine/<int:id>')
@login_required
def refine_module(id):
    module = Module.query.get_or_404(id)
    xml_str = export_module(module)
    session = ChatSession(user_id=current_user.id, latest_xml=xml_str,
                          title=f'Refine: {module.name}')
    db.session.add(session)
    db.session.flush()

    intro = (f'I want to modify the "{module.name}" module. '
             f'Here is its current XML:\n\n```xml\n{xml_str}\n```\n\n'
             f'Please help me update it.')
    db.session.add(ChatMessage(session_id=session.id, role='user', content=intro))
    db.session.commit()
    return redirect(url_for('chat.view_session', id=session.id))


def _guess_title(xml_str):
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_str)
        return root.get('name')
    except Exception:
        return None
