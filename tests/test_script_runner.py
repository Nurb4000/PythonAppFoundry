"""Tests for the script runner sandbox."""
import pytest


class TestScriptSandbox:
    """Test that the script execution sandbox blocks dangerous operations."""

    def test_basic_script_execution(self, app_context, sample_script):
        """A simple script should execute and return result."""
        from app.services.script_runner import execute_script
        result = execute_script(sample_script, source_type='script', source_name='test')
        assert 'hello world' in str(result)

    def test_os_import_blocked(self, app_context, sample_script):
        """Importing 'os' should raise an error in sandbox."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='os_test',
            language='python',
            source_code='import os\n_result = os.getcwd()',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='os_test')
        assert 'error' in str(result).lower() or 'blocked' in str(result).lower()

    def test_subprocess_import_blocked(self, app_context, sample_script):
        """Importing 'subprocess' should raise an error in sandbox."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='sub_test',
            language='python',
            source_code='import subprocess\n_result = subprocess.run(["echo", "hi"])',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='sub_test')
        assert 'error' in str(result).lower() or 'blocked' in str(result).lower()

    def test_socket_import_blocked(self, app_context, sample_script):
        """Importing 'socket' should raise an error in sandbox."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='sock_test',
            language='python',
            source_code='import socket\n_result = socket.socket()',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='sock_test')
        assert 'error' in str(result).lower() or 'blocked' in str(result).lower()

    def test_sys_import_blocked(self, app_context, sample_script):
        """Importing 'sys' should raise an error in sandbox."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='sys_test',
            language='python',
            source_code='import sys\n_result = sys.version',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='sys_test')
        assert 'error' in str(result).lower() or 'blocked' in str(result).lower()

    def test_json_import_allowed(self, app_context, sample_script):
        """Importing 'json' should be allowed (safe module)."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='json_test',
            language='python',
            source_code='import json\n_result = json.dumps({"key": "value"})',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='json_test')
        assert '"key"' in str(result) or '"value"' in str(result)

    def test_math_import_allowed(self, app_context, sample_script):
        """Importing 'math' should be allowed (safe module)."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='math_test',
            language='python',
            source_code='import math\n_result = math.sqrt(144)',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='math_test')
        assert '12.0' in str(result)

    def test_getattr_removed(self, app_context, sample_script):
        """getattr builtin should be removed from sandbox."""
        from app.models import Script
        from app.services.script_runner import execute_script
        from app import db as _db

        s = Script(
            module_id=sample_script.module_id,
            name='getattr_test',
            language='python',
            source_code='_result = getattr.__name__',
        )
        _db.session.add(s)
        _db.session.commit()

        result = execute_script(s, source_type='script', source_name='getattr_test')
        # Should error since getattr is removed
        assert 'error' in str(result).lower() or 'builtin' in str(result).lower()


class TestScriptTimeout:
    """Test script execution timeout."""

    def test_timeout_config(self, app_context):
        """Script timeout should be configurable via settings."""
        from app.models import Setting
        # Default timeout should be 30 seconds
        Setting.set('script_timeout', '30')
        assert Setting.get('script_timeout', '30') == '30'


class TestWrapInFunction:
    """Test the _wrap_in_function helper."""

    def test_wrap_adds_return(self, app_context):
        """Wrapped script should have return _result at the end."""
        from app.services.script_runner import _wrap_in_function
        source = '_result = 42'
        wrapped = _wrap_in_function(source)
        assert 'def _script():' in wrapped
        assert 'return _result' in wrapped
        assert '_result = 42' in wrapped

    def test_wrap_indents_body(self, app_context):
        """Script body should be indented inside the wrapper function."""
        from app.services.script_runner import _wrap_in_function
        source = 'x = 1\n_result = x + 1'
        wrapped = _wrap_in_function(source)
        lines = wrapped.split('\n')
        # Body lines should be indented
        assert any(line.startswith('    ') for line in lines)
