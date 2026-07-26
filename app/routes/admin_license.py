"""Admin routes for license information."""
from flask import Blueprint, request, redirect, url_for, render_template_string

license_bp = Blueprint('license', __name__)


@license_bp.route('/license')
@admin_required
def license_page():
    """Display license information."""
    return render_admin('License', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>MIT License</h2>
  
  <div class="dash-card">
    <pre style="margin:0;white-space:pre-wrap;font-size:0.85em;line-height:1.6;">Copyright 2026 IDS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.</pre>
  </div>
</div>
''')
