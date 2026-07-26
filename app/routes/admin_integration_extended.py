"""Admin routes for extended integration management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

integration_extended_bp = Blueprint('integration_extended', __name__)


@integration_extended_bp.route('/integrations/test-smtp', methods=['POST'])
@admin_required
@csrf_protect
def test_smtp():
    """Test SMTP configuration."""
    from app.services.script_runner import _send_email
    
    to = request.form.get('test_to', '')
    if not to:
        flash('Recipient email required', 'error')
        return redirect(url_for('admin.edit_settings'))
    
    try:
        _send_email(to=to, subject='SMTP Test', body='<h1>SMTP Test</h1><p>If you receive this email, your SMTP configuration is working correctly.</p>', html=True)
        flash(f'SMTP test email sent to {to}')
    except Exception as e:
        flash(f'SMTP test failed: {e}', 'error')
    
    return redirect(url_for('admin.edit_settings'))


@integration_extended_bp.route('/integrations/test-imap', methods=['POST'])
@admin_required
@csrf_protect
def test_imap():
    """Test IMAP configuration."""
    from app.services.incoming_mail import poll_incoming_mail
    
    try:
        # Try to connect to IMAP server
        from app.models import Setting
        host = Setting.get('imap_host', '')
        port = int(Setting.get('imap_port', '993'))
        user = Setting.get('imap_user', '')
        password = Setting.get('imap_password', '')
        
        if not host or not user or not password:
            flash('IMAP host, username, and password are required', 'error')
            return redirect(url_for('admin.edit_settings'))
        
        import imaplib
        if Setting.get('imap_use_ssl', 'true') == 'true':
            mail = imaplib.IMAP4_SSL(host, port)
        else:
            mail = imaplib.IMAP4(host, port)
        
        mail.login(user, password)
        mail.select('INBOX')
        mail.logout()
        
        flash('IMAP connection test successful')
    except Exception as e:
        flash(f'IMAP connection test failed: {e}', 'error')
    
    return redirect(url_for('admin.edit_settings'))


@integration_extended_bp.route('/integrations/test-llm', methods=['POST'])
@admin_required
@csrf_protect
def test_llm():
    """Test LLM configuration."""
    from app.services.ai_assistant import _call_llm
    
    try:
        messages = [{'role': 'user', 'content': 'Hello, this is a test message.'}]
        response = _call_llm(messages)
        
        if response.startswith('Error:'):
            flash(f'LLM test failed: {response}', 'error')
        else:
            flash('LLM connection test successful')
    except Exception as e:
        flash(f'LLM connection test failed: {e}', 'error')
    
    return redirect(url_for('admin.edit_settings'))
