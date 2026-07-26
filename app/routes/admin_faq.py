"""Admin routes for FAQ."""
from flask import Blueprint, request, redirect, url_for, render_template_string

faq_bp = Blueprint('faq', __name__)


@faq_bp.route('/faq')
@developer_or_admin_required
def faq():
    """Display frequently asked questions."""
    faqs = [
        {
            'question': 'What is PythonAppFoundry?',
            'answer': 'PythonAppFoundry is a database-driven web application platform where everything (routes, scripts, forms, tasks) lives in a database. Modules are self-contained bundles that can be imported/exported as XML.',
        },
        {
            'question': 'How do I create a module?',
            'answer': 'Go to Modules → + New, or use the AI Designer to generate a module from a natural language description.',
        },
        {
            'question': 'What variables are available in scripts?',
            'answer': 'request, session, db, current_user, redirect, url_for, flash, render, jsonify, send_email, render_form, DynamicModel, datetime, timezone, get_credential, call_api, and more.',
        },
        {
            'question': 'Can I use external Python packages?',
            'answer': 'Yes! Install them via the Packages admin page or declare them in module XML with <requirements>.',
        },
        {
            'question': 'How do I backup my database?',
            'answer': 'Go to Backups and click "Create New Backup". Backups are stored in instance/backups/.',
        },
        {
            'question': 'What is the script sandbox?',
            'answer': 'Scripts run in a hardened sandbox. Dangerous modules (os, subprocess, sys, socket) are blocked. Scripts cannot read sensitive settings.',
        },
        {
            'question': 'How do webhooks work?',
            'answer': 'Webhooks are configured as triggers with event_type="webhook". External services POST to /__api/webhook/{slug} to trigger scripts.',
        },
        {
            'question': 'Can I use PostgreSQL instead of SQLite?',
            'answer': 'Yes! Set DATABASE_URL in your .env file to a PostgreSQL connection string. See the scaling guide in the admin documentation.',
        },
    ]
    
    return render_admin('FAQ', '''
<div style="max-width:800px;margin:0 auto;">
  <h2>Frequently Asked Questions</h2>
  
  {% for faq in faqs %}
  <div style="border:1px solid #ddd;border-radius:8px;padding:1rem;margin-bottom:1rem;">
    <h3 style="margin-top:0;color:#2563eb;">{{ faq.question }}</h3>
    <p style="color:#666;margin:0;">{{ faq.answer }}</p>
  </div>
  {% endfor %}
</div>
''', faqs=faqs)
