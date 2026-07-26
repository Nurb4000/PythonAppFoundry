from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import ChatSession, ChatMessage, Module
from app.services.ai_assistant import chat_completion
from app.services.bundle import import_module, export_module

chat_bp = Blueprint('chat', __name__, url_prefix='/__admin/chat')




@chat_bp.route('/')
@login_required
def index():
    sessions = db.session.query(ChatSession).filter_by(
        user_id=current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    return render_template('chat/no_session.html', sessions=sessions)


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
    return render_template('chat/chat_page.html', session=session, messages=messages,
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
        return redirect(url_for('admin.modules.list_modules'))
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
