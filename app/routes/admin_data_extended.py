"""Admin routes for extended data browser functionality."""
from flask import Blueprint, request, redirect, url_for, render_template_string

data_extended_bp = Blueprint('data_extended', __name__)


@data_extended_bp.route('/data/<table_name>/export')
@admin_required
def export_table(table_name):
    """Export a table as CSV."""
    from app.models import db
    from sqlalchemy import Table, MetaData
    import csv, io
    from flask import Response
    
    if table_name not in db.metadata.tables:
        flash('Table not found', 'error')
        return redirect(url_for('admin.list_tables'))
    
    table = db.metadata.tables[table_name]
    rows = db.session.execute(table.select()).mappings().fetchall()
    
    if not rows:
        flash('Table is empty', 'info')
        return redirect(url_for('admin.list_tables'))
    
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(rows[0].keys())
    for row in rows:
        w.writerow(row.values())
    
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{table_name}.csv"'}
    )


@data_extended_bp.route('/data/<table_name>/import', methods=['POST'])
@admin_required
@csrf_protect
def import_table(table_name):
    """Import data into a table from CSV."""
    from app.models import db
    from sqlalchemy import Table, MetaData
    import csv
    
    if table_name not in db.metadata.tables:
        flash('Table not found', 'error')
        return redirect(url_for('admin.list_tables'))
    
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('admin.list_tables'))
    
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        flash('Invalid file format. Please upload a CSV file.', 'error')
        return redirect(url_for('admin.list_tables'))
    
    try:
        content = file.read().decode('utf-8')
        reader = csv.DictReader(content.splitlines())
        
        table = db.metadata.tables[table_name]
        inserted = 0
        
        for row in reader:
            values = {}
            for key, value in row.items():
                if key in [c.name for c in table.columns]:
                    # Try to convert types
                    col = table.c[key]
                    if col.type.__class__.__name__ == 'Integer':
                        try:
                            values[key] = int(value) if value else None
                        except ValueError:
                            values[key] = None
                    elif col.type.__class__.__name__ == 'Float':
                        try:
                            values[key] = float(value) if value else None
                        except ValueError:
                            values[key] = None
                    elif col.type.__class__.__name__ == 'Boolean':
                        values[key] = value.lower() in ('true', '1', 'yes') if value else False
                    else:
                        values[key] = value
            
            db.session.execute(table.insert().values(**values))
            inserted += 1
        
        db.session.commit()
        flash(f'Imported {inserted} row(s) into {table_name}')
    except Exception as e:
        db.session.rollback()
        flash(f'Import failed: {e}', 'error')
    
    return redirect(url_for('admin.list_tables'))


@data_extended_bp.route('/data/<table_name>/truncate', methods=['POST'])
@admin_required
@csrf_protect
def truncate_table(table_name):
    """Truncate a table (delete all data)."""
    from app.models import db
    
    if table_name not in db.metadata.tables:
        flash('Table not found', 'error')
        return redirect(url_for('admin.list_tables'))
    
    table = db.metadata.tables[table_name]
    db.session.execute(table.delete())
    db.session.commit()
    flash(f'Table {table_name} truncated')
    return redirect(url_for('admin.list_tables'))
