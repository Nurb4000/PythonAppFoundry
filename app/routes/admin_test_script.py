from flask import Blueprint, request, jsonify
from app.services.csrf import csrf_protect
from app.services.admin_utils import developer_or_admin_required
from app.models import Script

test_script_bp = Blueprint('test_script', __name__)


@test_script_bp.route('/<int:id>', methods=['POST'])
@developer_or_admin_required
@csrf_protect
def test_script(id):
    """Test a script by executing it and returning the result as JSON."""
    from app.services.script_runner import execute_script
    s = Script.query.get_or_404(id)
    
    import time
    t0 = time.time()
    import sys
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    error = None
    output = None
    result = None
    try:
        result = execute_script(s)
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    except Exception as e:
        import traceback
        error = traceback.format_exc()
        output = sys.stdout.getvalue()
        duration = int((time.time() - t0) * 1000)
    finally:
        sys.stdout = old_stdout
    
    return jsonify({
        'success': error is None,
        'result': str(result)[:2000] if result else None,
        'output': output[:2000] if output else '',
        'error': error[:2000] if error else None,
        'duration_ms': duration,
    })

