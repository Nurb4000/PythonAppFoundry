"""Admin routes for extended form management."""
from flask import Blueprint, request, redirect, url_for, render_template_string

form_extended_bp = Blueprint('form_extended', __name__)


@form_extended_bp.route('/forms/<int:id>/preview')
@developer_or_admin_required
def preview_form(id):
    """Preview a form's rendered output."""
    from app.models import Form
    
    form = db.session.get(Form, id)
    if not form:
        flash('Form not found', 'error')
        return redirect(url_for('admin.list_forms'))
    
    # Render the form using the same logic as render_form()
    try:
        import json
        fields = json.loads(form.schema_json)
        
        html = '<form method="POST" style="max-width:400px;">'
        for field in fields:
            fname = field.get('name', '')
            flabel = field.get('label', fname)
            ftype = field.get('type', 'text')
            required = 'required' if field.get('required') else ''
            placeholder = field.get('placeholder', '')
            
            html += f'<div style="margin-bottom:12px;">'
            html += f'<label for="{fname}" style="display:block;font-weight:600;margin-bottom:4px;">{flabel}</label>'
            
            if ftype == 'textarea':
                html += f'<textarea id="{fname}" name="{fname}" {required} placeholder="{placeholder}" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;min-height:100px;"></textarea>'
            elif ftype == 'select':
                opts = field.get('options', '').split(',')
                html += f'<select id="{fname}" name="{fname}" {required} style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">'
                for opt in opts:
                    html += f'<option value="{opt.strip()}">{opt.strip()}</option>'
                html += '</select>'
            elif ftype == 'checkbox':
                html += f'<div style="margin-top:4px;"><input type="checkbox" id="{fname}" name="{fname}" {required}> <span style="font-weight:normal;">{flabel}</span></div>'
            elif ftype == 'file':
                html += f'<input type="file" id="{fname}" name="{fname}" {required} style="width:100%;padding:6px;border:1px solid #ccc;border-radius:4px;">'
            else:
                html += f'<input type="{ftype}" id="{fname}" name="{fname}" value="" {required} placeholder="{placeholder}" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">'
            
            html += '</div>'
        
        html += '<button type="submit" style="padding:10px 24px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">Submit</button>'
        html += '</form>'
        
        return render_admin(f'Form Preview: {form.name}', html)
    except Exception as e:
        flash(f'Failed to preview form: {e}', 'error')
        return redirect(url_for('admin.list_forms'))


@form_extended_bp.route('/forms/bulk-preview', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def bulk_preview_forms():
    """Preview multiple forms at once."""
    from app.models import Form
    
    form_ids = request.form.getlist('form_ids')
    previewed = 0
    
    for fid in form_ids:
        form = db.session.get(Form, int(fid))
        if form:
            previewed += 1
    
    flash(f'Previewed {previewed} form(s)')
    return redirect(url_for('admin.list_forms'))
