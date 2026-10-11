"""Tests for SQL builder hardening (identifier sanitization, read-only validation)."""
import pytest


class TestSanitizeIdentifier:
    """Test _sanitize_identifier helper."""

    def test_valid_simple(self, app_context):
        from app.services.sql_builder import _sanitize_identifier
        assert _sanitize_identifier('users') == 'users'

    def test_valid_with_underscore(self, app_context):
        from app.services.sql_builder import _sanitize_identifier
        assert _sanitize_identifier('user_groups') == 'user_groups'

    def test_valid_qualified(self, app_context):
        """table.column format should be allowed."""
        from app.services.sql_builder import _sanitize_identifier
        assert _sanitize_identifier('users.id') == 'users.id'

    def test_invalid_special_char(self, app_context):
        from app.services.sql_builder import _sanitize_identifier
        with pytest.raises(ValueError, match='Invalid SQL identifier'):
            _sanitize_identifier('users; DROP TABLE users--')

    def test_invalid_space(self, app_context):
        from app.services.sql_builder import _sanitize_identifier
        with pytest.raises(ValueError, match='Invalid SQL identifier'):
            _sanitize_identifier('user name')

    def test_invalid_empty(self, app_context):
        from app.services.sql_builder import _sanitize_identifier
        with pytest.raises(ValueError, match='Invalid SQL identifier'):
            _sanitize_identifier('')

    def test_invalid_starts_with_digit(self, app_context):
        from app.services.sql_builder import _sanitize_identifier
        with pytest.raises(ValueError, match='Invalid SQL identifier'):
            _sanitize_identifier('1users')


class TestValidateReadOnly:
    """Test validate_read_only function."""

    def test_simple_select(self, app_context):
        from app.services.sql_builder import validate_read_only
        result = validate_read_only('SELECT * FROM users')
        assert result == 'SELECT * FROM users'

    def test_with_cte(self, app_context):
        from app.services.sql_builder import validate_read_only
        result = validate_read_only('WITH cte AS (SELECT 1) SELECT * FROM cte')
        assert result.startswith('WITH')

    def test_reject_insert(self, app_context):
        from app.services.sql_builder import validate_read_only
        with pytest.raises(ValueError, match='read-only'):
            validate_read_only('INSERT INTO users VALUES (1)')

    def test_reject_semicolon(self, app_context):
        """Multi-statement with semicolon should be rejected."""
        from app.services.sql_builder import validate_read_only
        with pytest.raises(ValueError, match='Multiple SQL statements'):
            validate_read_only('SELECT * FROM users; DROP TABLE users')

    def test_strip_line_comment(self, app_context):
        """Line comments should be stripped."""
        from app.services.sql_builder import validate_read_only
        result = validate_read_only('SELECT * FROM users -- comment')
        assert '--' not in result or result.endswith('--')

    def test_strip_block_comment(self, app_context):
        """Block comments should be stripped."""
        from app.services.sql_builder import validate_read_only
        result = validate_read_only('SELECT /* comment */ * FROM users')
        assert '/*' not in result and '*/' not in result

    def test_empty_after_comments(self, app_context):
        """Query that becomes empty after stripping comments should fail."""
        from app.services.sql_builder import validate_read_only
        with pytest.raises(ValueError, match='empty'):
            validate_read_only('-- SELECT * FROM users')

    def test_comment_injection(self, app_context):
        """Comment-based injection: SELECT * FROM users; DROP TABLE users--"""
        from app.services.sql_builder import validate_read_only
        # The semicolon check should catch this before comment stripping
        with pytest.raises(ValueError, match='Multiple SQL statements'):
            validate_read_only('SELECT * FROM users; DROP TABLE users--')


class TestValidateSql:
    """Test validate_sql function."""

    def test_valid_select(self, app_context):
        from app.services.sql_builder import validate_sql
        result = validate_sql('SELECT * FROM users LIMIT 10')
        assert result['valid'] is True

    def test_empty_sql(self, app_context):
        from app.services.sql_builder import validate_sql
        result = validate_sql('')
        assert result['valid'] is False
        assert 'Empty' in result['error']

    def test_insert_rejected(self, app_context):
        """INSERT should be rejected by read-only check."""
        from app.services.sql_builder import validate_sql
        result = validate_sql('INSERT INTO users VALUES (1)')
        assert result['valid'] is False
        assert 'read-only' in result['error'].lower()

    def test_multi_statement_rejected(self, app_context):
        """Multi-statement should be rejected."""
        from app.services.sql_builder import validate_sql
        result = validate_sql('SELECT * FROM users; DROP TABLE users')
        assert result['valid'] is False
        assert 'Multiple' in result['error']


class TestBuildVisualQuery:
    """Test build_visual_query with identifier sanitization."""

    def test_valid_query(self, app_context):
        from app.services.sql_builder import build_visual_query
        sql = build_visual_query('users', columns=['id', 'username'])
        assert 'SELECT' in sql
        assert 'FROM users' in sql

    def test_invalid_table_name(self, app_context):
        from app.services.sql_builder import build_visual_query
        sql = build_visual_query('nonexistent_table_xyz')
        assert '-- Error:' in sql

    def test_injection_in_table_name(self, app_context):
        """Table name with injection attempt should be sanitized."""
        from app.services.sql_builder import build_visual_query
        sql = build_visual_query('users; DROP TABLE users--')
        # Should either error or sanitize the identifier
        assert '-- Error:' in sql or 'DROP' not in sql

    def test_injection_in_column_name(self, app_context):
        """Column name with injection attempt should be sanitized."""
        from app.services.sql_builder import build_visual_query
        sql = build_visual_query('users', columns=['id', 'username; DROP TABLE users--'])
        # The invalid column should be filtered out
        assert 'SELECT' in sql
        assert 'DROP' not in sql or '-- Error:' in sql

    def test_injection_in_condition(self, app_context):
        """Condition column with injection attempt should be sanitized."""
        from app.services.sql_builder import build_visual_query
        conditions = [
            {'column': 'username; DROP TABLE users--', 'operator': '=', 'value': 'admin'}
        ]
        sql = build_visual_query('users', columns=['id'], conditions=conditions)
        assert 'SELECT' in sql
        # The invalid condition column should be filtered out
        assert 'DROP' not in sql or '-- Error:' in sql

    def test_injection_in_order_by(self, app_context):
        """Order by column with injection attempt should be sanitized."""
        from app.services.sql_builder import build_visual_query
        order_by = [{'column': 'username; DROP TABLE users--', 'direction': 'asc'}]
        sql = build_visual_query('users', columns=['id'], order_by=order_by)
        assert 'SELECT' in sql
        assert 'DROP' not in sql or '-- Error:' in sql


class TestBuildQueryWithJoins:
    """Test build_query_with_joins with identifier sanitization."""

    def test_valid_join(self, app_context):
        from app.services.sql_builder import build_query_with_joins
        # Use a table that exists and has relationships
        sql = build_query_with_joins('users')
        assert 'SELECT' in sql

    def test_injection_in_join_table(self, app_context):
        """Join table with injection attempt should be sanitized."""
        from app.services.sql_builder import build_query_with_joins
        joins = [
            {'table': 'modules; DROP TABLE modules--', 'on_column': 'id', 'on_ref_column': 'id'}
        ]
        sql = build_query_with_joins('users', joins=joins)
        assert 'SELECT' in sql
        # The invalid join table should be filtered out
        assert 'DROP' not in sql or '-- Error:' in sql

    def test_injection_in_join_columns(self, app_context):
        """Join columns with injection attempt should be sanitized."""
        from app.services.sql_builder import build_query_with_joins
        joins = [
            {'table': 'modules', 'on_column': 'id; DROP TABLE users--', 'on_ref_column': 'id'}
        ]
        sql = build_query_with_joins('users', joins=joins)
        assert 'SELECT' in sql
        # The invalid join column should be filtered out
        assert 'DROP' not in sql or '-- Error:' in sql
