"""Admin routes for incoming email management."""
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, Response
import csv, io
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required
from app import db
from app.models import IncomingEmail

incoming_email_bp = Blueprint('incoming_email', __name__)


@incoming_email_bp.route('/incoming-emails')
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

    if request.args.get('format') == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'message_id', 'subject', 'from_address', 'to_address', 'processed', 'created_at'])
        for e in emails:
            w.writerow([e.id, e.message_id, e.subject, e.from_address, e.to_address, e.processed, e.created_at])
        return Response(buf.getvalue(), mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=incoming_emails.csv'})

    return render_admin('Incoming Emails', '''
<div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap;">
  <form method="GET" style="display:flex;gap:8px;align-items:center;flex:1;">
    <input name="search" type="text" placeholder="Search subject or sender..." value="{{ search }}" style="padding:6px 12px;border:1px solid #ddd;border-radius:4px;flex:1;max-width:300px;">
    <button type="submit" style="padding:6px 12px;">Search</button>
    {% if search %}<a href="{{ url_for('admin.list_incoming_emails') }}" style="color:#007bff;text-decoration:none;">Clear</a>{% endif %}
  </form>
  <a href="?format=csv{% if search %}&search={{ search }}{% endif %}" style="margin-left:auto;">Export CSV</a>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th><a href="?sort=id&order={% if sort_col == 'id' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">ID{% if sort_col == 'id' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Subject</th>
  <th><a href="?sort=from_address&order={% if sort_col == 'from_address' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">From{% if sort_col == 'from_address' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>To</th>
  <th><a href="?sort=processed&order={% if sort_col == 'processed' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Status{% if sort_col == 'processed' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=module_slug&order={% if sort_col == 'module_slug' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Module{% if sort_col == 'module_slug' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th><a href="?sort=created_at&order={% if sort_col == 'created_at' and sort_order == 'asc' %}desc{% else %}asc{% endif %}">Received{% if sort_col == 'created_at' %}<span style="font-size:0.7em;margin-left:2px;">{% if sort_order == 'asc' %}▲{% else %}▼{% endif %}</span>{% endif %}</a></th>
  <th>Actions</th>
</tr></thead>
<tbody>
{% for e in emails %}
<tr>
  <td>{{ e.id }}</td>
  <td><strong>{{ e.subject[:80] if e.subject else '(no subject)' }}</strong></td>
  <td>{{ e.from_address[:60] }}</td>
  <td>{{ e.to_address[:60] if e.to_address else '—' }}</td>
  <td>{% if e.processed %}<span style="color:#080;">Processed</span>{% else %}<span style="color:#856404;">Pending</span>{% endif %}</td>
  <td>{{ e.module_slug or '—' }}</td>
  <td style="white-space:nowrap;">{{ e.created_at|localtime }}</td>
  <td>
    <a href="{{ url_for('admin.view_incoming_email', id=e.id) }}">View</a>
    {% if not e.processed %}
    <form method="POST" action="{{ url_for('admin.mark_incoming_processed', id=e.id) }}" style="display:inline">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#080;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Mark Done</button>
    </form>
    {% endif %}
    <form method="POST" action="{{ url_for('admin.delete_incoming_email', id=e.id) }}" style="display:inline" onsubmit="return confirm('Delete email #{{ e.id }}?')">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="submit" style="background:none;border:none;color:#c00;cursor:pointer;text-decoration:underline;padding:0;font:inherit;font-size:0.9em;">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody></table>
</div>
{% if not emails %}
<p style="color:#888;">No incoming emails yet. Configure IMAP settings and enable polling to start receiving emails.</p>
{% endif %}''', emails=emails, sort_col=sort_col, sort_order=sort_order, search=search)


@incoming_email_bp.route('/incoming-emails/<int:id>')
@admin_required
def view_incoming_email(id):
    e = IncomingEmail.query.get_or_404(id)
    return render_admin(f'Email: {e.subject or "(no subject)"}', '''
<h2>{{ e.subject or '(no subject)' }}</h2>
<table>
<tr><th>ID</th><td>{{ e.id }}</td></tr>
<tr><th>From</th><td>{{ e.from_address }}</td></tr>
<tr><th>To</th><td>{{ e.to_address }}</td></tr>
<tr><th>Message-ID</th><td><code>{{ e.message_id }}</code></td></tr>
<tr><th>Received</th><td>{{ e.created_at|localtime }}</td></tr>
<tr><th>Status</th><td>{% if e.processed %}Processed{% else %}Pending{% endif %}</td></tr>
{% if e.module_slug %}<tr><th>Claimed By</th><td>{{ e.module_slug }}</td></tr>{% endif %}
{% if e.attachments %}<tr><th>Attachments</th><td>{{ e.attachments }}</td></tr>{% endif %}
</table>
{% if e.body_html %}
<h3>HTML Body</h3>
<div style="border:1px solid #ddd;border-radius:4px;padding:1rem;margin-bottom:1rem;max-height:500px;overflow-y:auto;background:#fff;">
  {{ e.body_html|safe }}
</div>
{% endif %}
{% if e.body_text %}
<h3>Plain Text Body</h3>
<pre style="background:#f4f4f4;padding:1rem;border-radius:4px;overflow:auto;white-space:pre-wrap;word-wrap:break-word;">{{ e.body_text }}</pre>
{% endif %}
<div style="margin-top:1rem;">
  <a href="{{ url_for('admin.list_incoming_emails') }}">&larr; Back</a>
  {% if not e.processed %}
  <form method="POST" action="{{ url_for('admin.mark_incoming_processed', id=e.id) }}" style="display:inline;margin-left:0.5rem;">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" style="background:#080;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;">Mark as Processed</button>
  </form>
  {% endif %}
</div>''', e=e)


@incoming_email_bp.route('/incoming-emails/<int:id>/processed', methods=['POST'])
@admin_required
@csrf_protect
def mark_incoming_processed(id):
    e = IncomingEmail.query.get_or_404(id)
    from datetime import datetime, timezone
    e.processed = True
    e.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Email #{id} marked as processed')
    return redirect(url_for('admin.view_incoming_email', id=id))


@incoming_email_bp.route('/incoming-emails/<int:id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def delete_incoming_email(id):
    e = IncomingEmail.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash(f'Email #{id} deleted')
    return redirect(url_for('admin.list_incoming_emails'))
