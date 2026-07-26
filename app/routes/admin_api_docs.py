"""Admin routes for API documentation."""
from flask import Blueprint, request, redirect, url_for, render_template_string

api_docs_bp = Blueprint('api_docs', __name__)


@api_docs_bp.route('/api-docs')
@login_required
def api_docs():
    """Display API documentation and examples."""
    return render_admin('API Documentation', '''
<h2>PythonAppFoundry API Documentation</h2>

<h3>Available Endpoints</h3>
<table style="width:100%;border-collapse:collapse;">
<thead>
  <tr style="background:#f4f4f4;">
    <th style="padding:0.75rem;text-align:left;border-bottom:2px solid #ddd;">Endpoint</th>
    <th style="padding:0.75rem;text-align:left;border-bottom:2px solid #ddd;">Method</th>
    <th style="padding:0.75rem;text-align:left;border-bottom:2px solid #ddd;">Description</th>
  </tr>
</thead>
<tbody>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/modules</code></td>
    <td style="padding:0.75rem;">GET</td>
    <td style="padding:0.75rem;">List all modules</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/modules/{slug}/export</code></td>
    <td style="padding:0.75rem;">GET</td>
    <td style="padding:0.75rem;">Export module as XML</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/modules/import</code></td>
    <td style="padding:0.75rem;">POST</td>
    <td style="padding:0.75rem;">Import module from XML</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/webhook/{slug}</code></td>
    <td style="padding:0.75rem;">POST</td>
    <td style="padding:0.75rem;">Trigger webhook</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/upload</code></td>
    <td style="padding:0.75rem;">POST</td>
    <td style="padding:0.75rem;">Upload a file</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/uploads</code></td>
    <td style="padding:0.75rem;">GET</td>
    <td style="padding:0.75rem;">List uploaded files</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/queries/{id}/run</code></td>
    <td style="padding:0.75rem;">POST</td>
    <td style="padding:0.75rem;">Execute a query report</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/openapi.json</code></td>
    <td style="padding:0.75rem;">GET</td>
    <td style="padding:0.75rem;">OpenAPI specification (JSON)</td>
  </tr>
  <tr style="border-bottom:1px solid #eee;">
    <td style="padding:0.75rem;"><code>/__api/swagger</code></td>
    <td style="padding:0.75rem;">GET</td>
    <td style="padding:0.75rem;">Swagger UI interface</td>
  </tr>
</tbody>
</table>

<h3>Authentication</h3>
<p>Most API endpoints require authentication. Include your session cookie in requests.</p>

<h3>Webhook Examples</h3>
<pre style="background:#f4f4f4;padding:1rem;border-radius:4px;overflow-x:auto;">
curl -X POST http://localhost:5000/__api/webhook/my-webhook \\
  -H "Content-Type: application/json" \\
  -d '{"action": "test", "data": {"key": "value"}}'
</pre>

<h3>File Upload Example</h3>
<pre style="background:#f4f4f4;padding:1rem;border-radius:4px;overflow-x:auto;">
curl -X POST http://localhost:5000/__api/upload \\
  -H "Content-Type: multipart/form-data" \\
  -F "file=@/path/to/file.txt"
</pre>
''')
