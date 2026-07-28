import logging
import re
from app.services.ai_assistant import _get_setting, _call_llm

logger = logging.getLogger(__name__)

SQL_BUILDER_SYSTEM_PROMPT = """You are a SQL query assistant for a database-driven web application.

Your job is to generate correct SQL SELECT queries based on the user's natural language description and the available database schema.

Rules:
1. Only output the SQL query. Do not include explanations, markdown, code fences, or any other text.
2. Use proper SQL syntax compatible with SQLite (the default database for this platform).
3. If the user asks for aggregation (counts, sums, averages), use GROUP BY appropriately.
4. If the user asks for filtering, use WHERE with proper column names from the schema.
5. Always include LIMIT unless the user explicitly asks for all rows. Use LIMIT 100 as default.
6. Use table.column format when there could be ambiguity (e.g., modules.name vs users.name).
7. For date filtering, use SQLite date functions like strftime() if needed.
8. If you cannot generate a valid query from the description, respond with: ERROR: <reason>

Available tables and columns:
{schema}

User request: {user_input}

Generate the SQL query:"""


def describe_tables(table_names=None):
    """Return a list of table descriptors with column info.

    Args:
        table_names: Optional list of specific table names. If None, returns all tables.

    Returns:
        List of dicts with keys: name, columns (list of dicts with name, type, pk, nullable)
    """
    from app import db
    tables = []
    metadata = db.metadata.tables

    if table_names:
        filtered = {k: v for k, v in metadata.items() if k in table_names}
    else:
        filtered = metadata

    for name, table in sorted(filtered.items()):
        cols = []
        for c in table.columns:
            cols.append({
                'name': c.name,
                'type': str(c.type),
                'pk': bool(c.primary_key),
                'nullable': c.nullable,
            })
        tables.append({'name': name, 'columns': cols})

    return tables


def _format_schema_for_prompt(tables):
    """Format table metadata into a readable schema string for the LLM prompt."""
    lines = []
    for t in tables:
        lines.append(f"Table: {t['name']}")
        for c in t['columns']:
            pk_mark = ' [PK]' if c['pk'] else ''
            nullable_mark = '' if c['nullable'] else ' [NOT NULL]'
            lines.append(f"  - {c['name']}: {c['type']}{pk_mark}{nullable_mark}")
        lines.append('')
    return '\n'.join(lines)


def natural_language_to_sql(user_input, table_names=None):
    """Convert natural language to SQL using the LLM.

    Args:
        user_input: The natural language query description.
        table_names: Optional list of specific tables to include. If None, all tables are used.

    Returns:
        Dict with keys: sql (str), error (str or None), tables_used (list)
    """
    from app import db

    tables = describe_tables(table_names)
    if not tables:
        return {'sql': None, 'error': 'No tables found in the database.', 'tables_used': []}

    schema_text = _format_schema_for_prompt(tables)
    prompt = SQL_BUILDER_SYSTEM_PROMPT.format(schema=schema_text, user_input=user_input)

    messages = [{'role': 'user', 'content': prompt}]
    temperature = float(_get_setting('llm_temperature', '0.1'))
    max_tokens = int(_get_setting('llm_max_tokens', '2048'))

    response = _call_llm(messages, temperature=temperature, max_tokens=max_tokens)

    if response.startswith('Error:'):
        return {'sql': None, 'error': response, 'tables_used': [t['name'] for t in tables]}

    sql = response.strip().rstrip(';').strip()

    if sql.upper().startswith('ERROR:'):
        return {'sql': None, 'error': sql, 'tables_used': [t['name'] for t in tables]}

    extracted = _extract_sql(sql)
    if not extracted:
        return {'sql': None, 'error': 'Could not extract SQL from LLM response.', 'tables_used': [t['name'] for t in tables]}

    return {
        'sql': extracted,
        'error': None,
        'tables_used': [t['name'] for t in tables],
    }


def _extract_sql(text):
    """Extract SQL from LLM response, handling markdown code blocks."""
    block = re.search(r'```(?:sql)?\s*\n(.*?)\n```', text, re.DOTALL)
    if block:
        return block.group(1).strip()

    lines = text.strip().split('\n')
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            continue
        if stripped.startswith('//') or stripped.startswith('/*'):
            continue
        clean_lines.append(line)

    sql = '\n'.join(clean_lines).strip()
    if sql and len(sql) > 3:
        return sql

    return None


def validate_sql(sql):
    """Validate SQL by attempting to parse it.

    Args:
        sql: SQL string to validate.

    Returns:
        Dict with keys: valid (bool), error (str or None)
    """
    if not sql or not sql.strip():
        return {'valid': False, 'error': 'Empty SQL query.'}

    sql_upper = sql.strip().upper()
    if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH') or
            sql_upper.startswith('INSERT') or sql_upper.startswith('UPDATE') or
            sql_upper.startswith('DELETE') or sql_upper.startswith('CREATE') or
            sql_upper.startswith('DROP') or sql_upper.startswith('ALTER')):
        return {'valid': False, 'error': 'SQL must start with a valid statement keyword.'}

    from app import db
    try:
        result = db.session.execute(db.text(sql + ' LIMIT 0'))
        return {'valid': True, 'error': None}
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def build_visual_query(table_name, columns=None, conditions=None, order_by=None,
                       limit=100, select_all=False):
    """Build a SQL SELECT query from visual builder form data.

    Args:
        table_name: Name of the table to query.
        columns: List of column names to SELECT. If None or empty, selects all.
        conditions: List of dicts with keys: column, operator, value.
        order_by: List of dicts with keys: column, direction (asc/desc).
        limit: Maximum number of rows to return.
        select_all: If True, selects all columns regardless of columns param.

    Returns:
        SQL string.
    """
    from app import db

    if table_name not in db.metadata.tables:
        return f'-- Error: Table "{table_name}" not found.'

    table = db.metadata.tables[table_name]

    if select_all or not columns:
        col_expr = '*'
    else:
        valid_cols = [c.name for c in table.columns if c.name in columns]
        if not valid_cols:
            return f'-- Error: No valid columns found for table "{table_name}".'
        col_expr = ', '.join(f'{table_name}.{c}' for c in valid_cols)

    sql = f'SELECT {col_expr} FROM {table_name}'

    if conditions:
        where_clauses = []
        params = {}
        for i, cond in enumerate(conditions):
            col = cond.get('column', '')
            op = cond.get('operator', '=').upper()
            value = cond.get('value')

            if not col or col == '---':
                continue

            if col not in table.columns:
                continue

            if op == 'IS NULL':
                where_clauses.append(f'{table_name}.{col} IS NULL')
            elif op == 'IS NOT NULL':
                where_clauses.append(f'{table_name}.{col} IS NOT NULL')
            elif op == 'LIKE':
                params[f'cond_{i}'] = f'%{value}%'
                where_clauses.append(f'{table_name}.{col} LIKE :cond_{i}')
            elif op == 'NOT LIKE':
                params[f'cond_{i}'] = f'%{value}%'
                where_clauses.append(f'{table_name}.{col} NOT LIKE :cond_{i}')
            elif op in ('=', '!=', '>', '<', '>=', '<='):
                params[f'cond_{i}'] = value
                where_clauses.append(f'{table_name}.{col} {op} :cond_{i}')
            else:
                continue

        if where_clauses:
            sql += ' WHERE ' + ' AND '.join(where_clauses)

    if order_by:
        order_parts = []
        for ob in order_by:
            col = ob.get('column', '')
            direction = ob.get('direction', 'asc').upper()
            if col and col in table.columns and direction in ('ASC', 'DESC'):
                order_parts.append(f'{table_name}.{col} {direction}')
        if order_parts:
            sql += ' ORDER BY ' + ', '.join(order_parts)

    if limit:
        sql += f' LIMIT {int(limit)}'

    return sql


def build_query_with_joins(table_name, columns=None, conditions=None, joins=None,
                           order_by=None, limit=100, select_all=False):
    """Build a SQL SELECT query with JOINs from visual builder form data.

    Args:
        table_name: Primary table name.
        columns: List of column names to SELECT.
        conditions: List of condition dicts (same as build_visual_query).
        joins: List of dicts with keys: table, on_column (left), on_ref_column (right), type (INNER/LEFT).
        order_by: List of order_by dicts.
        limit: Max rows.
        select_all: Select all columns.

    Returns:
        SQL string.
    """
    from app import db

    if table_name not in db.metadata.tables:
        return f'-- Error: Table "{table_name}" not found.'

    sql = build_visual_query(table_name, columns, conditions, order_by, limit, select_all)

    if not joins:
        return sql

    for join in joins:
        join_table = join.get('table', '')
        on_col = join.get('on_column', '')
        ref_col = join.get('on_ref_column', '')
        join_type = join.get('type', 'INNER').upper()

        if not join_table or not on_col or not ref_col:
            continue

        if join_table not in db.metadata.tables:
            continue

        sql += f' {join_type} JOIN {join_table}'
        sql += f' ON {table_name}.{on_col} = {join_table}.{ref_col}'

    if limit and 'LIMIT' not in sql.upper():
        sql += f' LIMIT {int(limit)}'

    return sql
