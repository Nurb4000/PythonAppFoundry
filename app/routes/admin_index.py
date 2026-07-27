from flask import Blueprint, request, redirect, url_for, flash
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app.services.audit import log_audit
from sqlalchemy import text, inspect as sa_inspect
from app import db

index_bp = Blueprint('index', __name__)


@index_bp.route('/')
@admin_required
def list_indexes():
    """List all dynamic tables and their indexes."""
    from app.models import DynamicTableRegistry, Module
    
    # Get module filter from query params
    selected_module_id = request.args.get('module_id', type=int)
    
    # Query tables with optional module filter
    query = DynamicTableRegistry.query
    if selected_module_id:
        query = query.filter_by(module_id=selected_module_id)
    tables = query.all()
    
    # Get all modules for the filter dropdown
    all_modules = Module.query.order_by(Module.name).all()
    
    table_info = []
    for reg in tables:
        try:
            inspector = sa_inspect(db.session.get_bind())
            if reg.table_name in inspector.get_table_names():
                indexes = inspector.get_indexes(reg.table_name)
                # Filter to only show our dynamic indexes (start with idx_)
                dynamic_indexes = [idx for idx in indexes if idx['name'].startswith('idx_')]
                
                # Get table columns
                columns = [c['name'] for c in inspector.get_columns(reg.table_name)]
                
                table_info.append({
                    'table_name': reg.table_name,
                    'module_id': reg.module_id,
                    'module_name': reg.module.name if reg.module else 'Unknown',
                    'indexes': dynamic_indexes,
                    'columns': columns,
                    'row_count': _get_row_count(reg.table_name),
                })
        except Exception as e:
            table_info.append({
                'table_name': reg.table_name,
                'module_id': reg.module_id,
                'error': str(e),
            })
    
    return render_admin('Index Management', 'admin/index/list.html', 
                       tables=table_info, modules=all_modules, 
                       selected_module_id=selected_module_id)


@index_bp.route('/<table_name>/add', methods=['POST'])
@admin_required
@csrf_protect
def add_index(table_name):
    """Add an index to a dynamic table."""
    column = request.form.get('column', '').strip()
    
    if not column:
        flash('Column name is required.', 'error')
        return redirect(url_for('admin.index.list_indexes'))
    
    try:
        _create_index_on_table(table_name, column)
        log_audit('create', 'index', details=f'{table_name}.{column}')
        flash(f'Index created on {table_name}.{column}')
    except Exception as e:
        flash(f'Failed to create index: {e}', 'error')
    
    return redirect(url_for('admin.index.list_indexes'))


@index_bp.route('/<table_name>/<index_name>/drop', methods=['POST'])
@admin_required
@csrf_protect
def drop_index(table_name, index_name):
    """Drop an index from a dynamic table."""
    try:
        _drop_index_on_table(table_name, index_name)
        log_audit('drop', 'index', details=f'{table_name}.{index_name}')
        flash(f'Index {index_name} dropped from {table_name}')
    except Exception as e:
        flash(f'Failed to drop index: {e}', 'error')
    
    return redirect(url_for('admin.index.list_indexes'))


def _create_index_on_table(table_name, column):
    """Create an index on a table column."""
    from app import db
    
    index_name = f"idx_{table_name}_{column}"[:63]
    create_sql = f'CREATE INDEX "{index_name}" ON "{table_name}" ("{column}")'
    
    try:
        db.session.execute(text(create_sql))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise


def _drop_index_on_table(table_name, index_name):
    """Drop an index from a table."""
    from app import db
    
    drop_sql = f'DROP INDEX "{index_name}"'
    
    try:
        db.session.execute(text(drop_sql))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise


def _get_row_count(table_name):
    """Get row count for a table."""
    from app import db
    try:
        result = db.session.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        return result.scalar()
    except Exception:
        return 0
