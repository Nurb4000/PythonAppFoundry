import imaplib
import email as email_lib
from email.header import decode_header
import logging
from datetime import datetime, timezone

from app import db
from app.models import IncomingEmail, Setting

logger = logging.getLogger(__name__)


def poll_incoming_mail():
    """Connect to IMAP, fetch unseen messages, store in incoming_emails."""
    enabled = Setting.get('imap_enabled', 'false') == 'true'
    if not enabled:
        return

    host = Setting.get('imap_host', '')
    port = int(Setting.get('imap_port', '993'))
    user = Setting.get('imap_user', '')
    password = Setting.get('imap_password', '')
    folder = Setting.get('imap_folder', 'INBOX')
    use_ssl = Setting.get('imap_use_ssl', 'true') == 'true'
    mark_seen = Setting.get('imap_mark_seen', 'false') == 'true'

    if not host or not user or not password:
        return

    try:
        if use_ssl:
            mail = imaplib.IMAP4_SSL(host, port)
        else:
            mail = imaplib.IMAP4(host, port)
        mail.login(user, password)
        mail.select(folder)

        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            mail.logout()
            return

        msg_ids = messages[0].split()
        if not msg_ids:
            mail.logout()
            return

        for mid in msg_ids:
            try:
                status, msg_data = mail.fetch(mid, '(RFC822)')
                if status != 'OK':
                    continue

                raw_email = msg_data[0][1]
                parsed = email_lib.message_from_bytes(raw_email)

                # Dedup by Message-ID
                msg_id_header = parsed.get('Message-ID', '') or ''
                if msg_id_header:
                    existing = db.session.query(IncomingEmail).filter_by(message_id=msg_id_header).first()
                    if existing:
                        continue

                subject = _decode_header_value(parsed.get('Subject', ''))
                from_addr = _decode_header_value(parsed.get('From', ''))
                to_addr = _decode_header_value(parsed.get('To', ''))
                body_text = ''
                body_html = ''
                attachments = []

                if parsed.is_multipart():
                    for part in parsed.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get('Content-Disposition', ''))
                        if 'attachment' in content_disposition:
                            filename = part.get_filename()
                            if filename:
                                attachments.append(filename)
                        elif content_type == 'text/plain':
                            try:
                                body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
                            except Exception:
                                pass
                        elif content_type == 'text/html':
                            try:
                                body_html = part.get_payload(decode=True).decode('utf-8', errors='replace')
                            except Exception:
                                pass
                else:
                    content_type = parsed.get_content_type()
                    if content_type == 'text/plain':
                        try:
                            body_text = parsed.get_payload(decode=True).decode('utf-8', errors='replace')
                        except Exception:
                            pass
                    elif content_type == 'text/html':
                        try:
                            body_html = parsed.get_payload(decode=True).decode('utf-8', errors='replace')
                        except Exception:
                            pass

                email_record = IncomingEmail(
                    message_id=msg_id_header,
                    subject=subject,
                    from_address=from_addr,
                    to_address=to_addr,
                    body_text=body_text,
                    body_html=body_html,
                    attachments=','.join(attachments),
                )
                db.session.add(email_record)
                db.session.commit()

            except Exception as e:
                logger.error(f'Error processing email {mid}: {e}')
                db.session.rollback()

        if mark_seen:
            for mid in msg_ids:
                mail.store(mid, '+FLAGS', '\\Seen')

        mail.logout()

    except Exception as e:
        logger.error(f'IMAP poll failed: {e}')


def _decode_header_value(value):
    """Decode email header values."""
    if not value:
        return ''
    try:
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                try:
                    decoded.append(part.decode(charset or 'utf-8', errors='replace'))
                except Exception:
                    decoded.append(part.decode('utf-8', errors='replace'))
            else:
                decoded.append(str(part))
        return ' '.join(decoded)
    except Exception:
        return str(value)
