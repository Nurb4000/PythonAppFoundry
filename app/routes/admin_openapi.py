"""Admin routes for OpenAPI specification."""
from flask import Blueprint, request, redirect, url_for, Response, jsonify

openapi_bp = Blueprint('openapi', __name__)


@openapi_bp.route('/openapi.json')
@login_required
def api_openapi():
    """Return the OpenAPI specification as JSON."""
    from app.services.openapi import export_openapi_json
    spec_json = export_openapi_json(current_app._get_current_object(), db.session)
    return Response(spec_json, mimetype='application/json')


@openapi_bp.route('/swagger')
@login_required
def api_swagger():
    """Serve Swagger UI for the OpenAPI spec."""
    swagger_ui = '''<!DOCTYPE html>
<html>
<head>
    <title>Swagger UI - PythonAppFoundry</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({
            url: "/__api/openapi.json",
            dom_id: '#swagger-ui',
        });
    </script>
</body>
</html>'''
    return swagger_ui
