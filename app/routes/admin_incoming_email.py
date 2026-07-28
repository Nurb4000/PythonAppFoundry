from flask import Blueprint, request, redirect, url_for, Response, flash
import csv, io
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app.services.exporters import _export_json, _export_xlsx, _export_pdf
from app import db
from app.models import IncomingEmail

incoming_email_bp = Blueprint('incoming_email', __name__)


@incoming_email_bp.route('/')
@admin_required
def list_incoming_emails():
    sort_col = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    search = request.args.get('search', '')
    q = db.session.query(IncomingEmail)
    if search:
        q = q.filter(
            db.or_(
                IncomingEmail.subject.ilike(f'%{search}%'),
                IncomingEmail.from_address.ilike(f'%{search}%'),
            )
        )
    sort_attr = getattr(IncomingEmail, sort_col, None)
    if sort_attr is not None:
        q = q.order_by(sort_attr.desc() if sort_order == 'desc' else sort_attr.asc())
    else:
        q = q.order_by(IncomingEmail.created_at.desc())
    emails = q.all()

    columns = ['id', 'message_id', 'subject', 'from_address', 'to_address', 'processed', 'created_at']
    fmt = request.args.get('format', '')
    if fmt == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(columns)
        for e in emails:
            w.writerow([e.id, e.message_id, e.subject, e.from_address, e.to_address, e.processed, e.created_at])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=incoming_emails.csv'})
    if fmt == 'json':
        return _export_json('incoming_emails', columns, emails, False)
    if fmt == 'xlsx':
        return _export_xlsx('incoming_emails', columns, emails, False)
    if fmt == 'pdf':
        return _export_pdf('incoming_emails', columns, emails, False)

    return render_admin('Incoming Emails', 'admin/incoming_email/list.html', emails=emails, sort_col=sort_col, sort_order=sort_order, search=search)


@incoming_email_bp.route('/<int:id>')
@admin_required
def view_incoming_email(id):
    e = IncomingEmail.query.get_or_404(id)
    return render_admin(f'Email: {e.subject or "(no subject)"}', 'admin/incoming_email/view.html', e=e)


@incoming_email_bp.route('/<int:id>/processed', methods=['POST'])
@admin_required
@csrf_protect
def mark_incoming_processed(id):
    e = IncomingEmail.query.get_or_404(id)
    from datetime import datetime, timezone
    e.processed = True
    e.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Email #{id} marked as processed')
    return redirect(url_for('admin.incoming_email.view_incoming_email', id=id))


@incoming_email_bp.route('/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_incoming_email(id):
    e = IncomingEmail.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash(f'Email #{id} deleted')
    return redirect(url_for('admin.incoming_email.list_incoming_emails'))
