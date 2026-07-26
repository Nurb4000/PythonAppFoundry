"""Admin routes for extended chat functionality."""
from flask import Blueprint, request, redirect, url_for, render_template_string

chat_extended_bp = Blueprint('chat_extended', __name__)


@chat_extended_bp.route('/chat/<int:id>/export')
@login_required
def export_chat(id):
    """Export a chat session as JSON."""
    from app.models import ChatSession, ChatMessage
    
    session = db.session.get(ChatSession, id)
    if not session:
        flash('Chat session not found', 'error')
        return redirect(url_for('chat.index'))
    
    messages = session.messages.order_by(ChatMessage.created_at).all()
    
    export_data = {
        'session': {
            'id': session.id,
            'title': session.title,
            'status': session.status,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'updated_at': session.updated_at.isoformat() if session.updated_at else None,
        },
        'messages': [
            {
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]
    }
    
    from flask import Response
    import json
    return Response(
        json.dumps(export_data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="chat_{session.id}.json"'}
    )


@chat_extended_bp.route('/chat/<int:id>/clear', methods=['POST'])
@login_required
@csrf_protect
def clear_chat(id):
    """Clear all messages in a chat session."""
    from app.models import ChatSession, ChatMessage
    
    session = db.session.get(ChatSession, id)
    if not session:
        flash('Chat session not found', 'error')
        return redirect(url_for('chat.index'))
    
    ChatMessage.query.filter_by(session_id=id).delete()
    db.session.commit()
    flash(f'Cleared {len(session.messages)} message(s) from "{session.title}"')
    return redirect(url_for('chat.view_session', id=id))


@chat_extended_bp.route('/chat/<int:id>/rename', methods=['POST'])
@login_required
@csrf_protect
def rename_chat(id):
    """Rename a chat session."""
    from app.models import ChatSession
    
    session = db.session.get(ChatSession, id)
    if not session:
        flash('Chat session not found', 'error')
        return redirect(url_for('chat.index'))
    
    new_title = request.form.get('new_title', '').strip()
    if new_title:
        session.title = new_title
        db.session.commit()
        flash(f'Renamed chat to "{new_title}"')
    else:
        flash('Title cannot be empty', 'error')
    
    return redirect(url_for('chat.view_session', id=id))
