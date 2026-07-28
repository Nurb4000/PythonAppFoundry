import json
import logging
import re
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import URLError

from app import db
from app.models import Setting

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_HEADER = """You are a module generator for a database-driven web application platform.
Your job is to produce valid XML module bundles based on the user's description.

Rules:
1. Always output the full XML module, never a diff or partial update.
2. Wrap the XML in ```xml ... ``` code blocks within your response.
3. If the user asks for changes, return the COMPLETE updated XML, not just the changed parts.
4. Every module needs at minimum a name, slug, and at least one route with a script.
5. Use CDATA sections for script source code.
6. Validate that all script/form references in routes match actual definitions.

Here is the schema and documentation:

"""


def _build_system_prompt():
    guide_path = None
    try:
        import os
        guide_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'AI_GUIDE.md'
        )
        with open(guide_path) as f:
            return SYSTEM_PROMPT_HEADER + f.read()
    except (IOError, OSError) as e:
        logger.warning(f'Could not read AI_GUIDE.md at {guide_path}: {e}')
        return SYSTEM_PROMPT_HEADER + '\nNo additional documentation available.'


def _get_setting(key, default):
    return Setting.get(key, default)


def _call_llm(messages, temperature=None, max_tokens=None):
    provider = _get_setting('llm_provider', 'llamacpp')
    endpoint = _get_setting('llm_endpoint', 'http://localhost:8080')
    api_key = _get_setting('llm_api_key', '')
    model = _get_setting('llm_model', '')
    timeout = int(_get_setting('llm_timeout', '300'))
    temperature = temperature if temperature is not None else float(
        _get_setting('llm_temperature', '0.3'))
    max_tokens = max_tokens if max_tokens is not None else int(
        _get_setting('llm_max_tokens', '4096'))

    try:
        if provider == 'openai':
            return _call_openai(messages, endpoint, api_key, model, temperature, max_tokens, timeout)
        return _call_llamacpp(messages, endpoint, api_key, temperature, max_tokens, timeout)
    except Exception as e:
        logger.error(f'LLM call failed: {e}')
        return f'Error: {e}'


def _call_llamacpp(messages, endpoint, api_key, temperature, max_tokens, timeout=120):
    url = f'{endpoint.rstrip("/")}/v1/chat/completions'
    payload = json.dumps({
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }).encode()

    req = Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    if api_key:
        req.add_header('Authorization', f'Bearer {api_key}')

    try:
        resp = urlopen(req, timeout=timeout)
        body = json.loads(resp.read().decode())
        return body['choices'][0]['message']['content']
    except URLError as e:
        logger.error(f'LLM connection failed: {e}')
        return f'Error: Could not reach {url}. Is the LLM server running?'
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f'LLM response parse failed: {e}')
        return f'Error: Unexpected response from LLM.'
    except Exception as e:
        logger.error(f'LLM call failed: {e}')
        return f'Error: {e}'


def _call_openai(messages, endpoint, api_key, model, temperature, max_tokens, timeout=120):
    if not api_key:
        return 'Error: OpenAI API key is not configured.'

    url = f'{endpoint.rstrip("/")}/v1/chat/completions'
    body = {
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if model:
        body['model'] = model

    payload = json.dumps(body).encode()
    req = Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {api_key}')

    try:
        resp = urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode())
        return data['choices'][0]['message']['content']
    except URLError as e:
        logger.error(f'OpenAI connection failed: {e}')
        return f'Error: Could not reach {url}.'
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f'OpenAI response parse failed: {e}')
        return f'Error: Unexpected response from OpenAI.'
    except Exception as e:
        logger.error(f'OpenAI call failed: {e}')
        return f'Error: {e}'


def _extract_xml(text):
    blocks = re.findall(r'```xml\s*\n(.*?)\n```', text, re.DOTALL)
    if blocks:
        return blocks[-1]
    match = re.search(r'<module\b', text)
    if match:
        return text[match.start():]
    return None


def _validate_xml(xml_str):
    if not xml_str:
        return False, 'No XML found in response'
    try:
        root = ET.fromstring(xml_str)
        if root.tag != 'module':
            return False, 'Root element must be <module>'
        name = root.get('name')
        slug = root.get('slug')
        if not name or not slug:
            return False, 'Module must have name and slug attributes'
        routes = root.find('routes')
        if routes is None or len(routes) == 0:
            return False, 'Module must have at least one route'
        scripts = root.find('scripts')
        if scripts is None or len(scripts) == 0:
            return False, 'Module must have at least one script'
        return True, None
    except ET.ParseError as e:
        return False, f'XML parse error: {e}'


DEBUG_SYSTEM_PROMPT = """You are a debugging assistant for a Flask-based web application platform called PythonAppFoundry.

Scripts run in a sandboxed environment with these constraints:
- BLOCKED imports (cannot be used): os, subprocess, sys, importlib, urllib, requests, http, socket, shutil, tempfile, pickle, marshal, codecs, threading, multiprocessing, signal, ctypes, pkg_resources
- Available globals in every script: db, request, session, current_user, redirect, url_for, flash, get_flashed_messages, render (render_template_string), jsonify, datetime, timezone, Integer, String, DateTime, Text, Boolean, Float, Column
- Platform helpers: DynamicModel.get_or_create(name, columns), call_api(method, url, headers, json, data, timeout, retries), get_credential(name), get_setting(key, default), send_email(to, subject, body, html), render_chart(chart_type, labels, datasets, title), render_form(action, method, submit_label, fields), form_fields
- Scripts use 'return' to send data to the caller (automatically wrapped in a function). Alternatively set _result = value.
- Scripts can access route.form fields via form_fields and render_form().
- Scripts can access DynamicModel to create/query dynamic database tables.
- Scripts should NOT import any modules — all needed functions are pre-injected as globals.

Analyze the error and provide a response in this exact format:

**Root Cause:**
[One paragraph explaining what went wrong and why]

**Corrected Script:**
```python
[The full corrected script code]
```

**Explanation:**
[One paragraph explaining the fix and any sandbox-aware advice]

Rules:
1. Always provide the FULL corrected script, never a partial snippet or diff.
2. If the error is due to a blocked import, suggest an alternative using the available globals (e.g., call_api() instead of requests, DynamicModel instead of direct SQL).
3. If the script uses 'return' outside a function, explain that the platform auto-wraps scripts.
4. Keep explanations concise and actionable.
"""


def debug_script_error(error_message, script_source, script_name=''):
    prompt = f"""A script named "{script_name}" failed with the following error:

--- ERROR ---
{error_message}
--- END ERROR ---

Here is the script source code:

--- SCRIPT ---
{script_source}
--- END SCRIPT ---

Analyze the error, explain the root cause, and provide the corrected script."""

    messages = [
        {'role': 'system', 'content': DEBUG_SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    temperature = float(_get_setting('llm_temperature', '0.3'))
    max_tokens = int(_get_setting('llm_max_tokens', '4096'))

    response = _call_llm(messages, temperature, max_tokens)
    if response.startswith('Error:'):
        return {'reply': response, 'fix_code': None, 'error': response}

    fix_code = _extract_code_block(response)
    return {'reply': response, 'fix_code': fix_code, 'error': None}


def _extract_code_block(text):
    match = re.search(r'```(?:python)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def compute_diff(old_text, new_text):
    """Compute a unified diff between two text strings.
    
    Returns a list of diff line dicts with keys:
      - type: 'unchanged', 'added', 'removed'
      - value: the line content
      - old_line: line number in old text (1-indexed, None for added)
      - new_line: line number in new text (1-indexed, None for removed)
    """
    import difflib
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    
    diff_lines = []
    for op, oi, ni, (old_l, new_l) in difflib.SequenceMatcher(
        autojunk=False, a=old_lines, b=new_lines
    ).get_opcodes():
        if op == 'equal':
            diff_lines.append({
                'type': 'unchanged',
                'value': old_l.rstrip('\n'),
                'old_line': oi + 1,
                'new_line': ni + 1,
            })
        elif op == 'replace':
            for i, line in enumerate(old_lines[oi:ni]):
                diff_lines.append({
                    'type': 'removed',
                    'value': line.rstrip('\n'),
                    'old_line': oi + i + 1,
                    'new_line': None,
                })
            for i, line in enumerate(new_lines[oi:ni]):
                diff_lines.append({
                    'type': 'added',
                    'value': line.rstrip('\n'),
                    'old_line': None,
                    'new_line': ni + i + 1,
                })
        elif op == 'delete':
            for i, line in enumerate(old_lines[oi:ni]):
                diff_lines.append({
                    'type': 'removed',
                    'value': line.rstrip('\n'),
                    'old_line': oi + i + 1,
                    'new_line': None,
                })
        elif op == 'insert':
            for i, line in enumerate(new_lines[oi:ni]):
                diff_lines.append({
                    'type': 'added',
                    'value': line.rstrip('\n'),
                    'old_line': None,
                    'new_line': oi + i + 1,
                })
    return diff_lines


ENHANCE_SCRIPT_SYSTEM_PROMPT = """You are a code enhancement assistant for Python scripts in a Flask-based web application platform called PythonAppFoundry.

Scripts run in a sandboxed environment with these constraints:
- BLOCKED imports (cannot be used): os, subprocess, sys, importlib, urllib, requests, http, socket, shutil, tempfile, pickle, marshal, codecs, threading, multiprocessing, signal, ctypes, pkg_resources
- Available globals in every script: db, request, session, current_user, redirect, url_for, flash, get_flashed_messages, render (render_template_string), jsonify, datetime, timezone, Integer, String, DateTime, Text, Boolean, Float, Column
- Platform helpers: DynamicModel.get_or_create(name, columns), call_api(method, url, headers, json, data, timeout, retries), get_credential(name), get_setting(key, default), send_email(to, subject, body, html), render_chart(chart_type, labels, datasets, title), render_form(action, method, submit_label, fields), form_fields
- Scripts use 'return' to send data to the caller (automatically wrapped in a function). Alternatively set _result = value.
- Scripts can access route.form fields via form_fields and render_form().
- Scripts can access DynamicModel to create/query dynamic database tables.
- Scripts should NOT import any modules — all needed functions are pre-injected as globals.

Analyze the script and provide improvements based on the user's request. Respond in this exact format:

**Improvements Made:**
[Bullet points describing what was changed and why]

**Enhanced Script:**
```python
[The full enhanced script code]
```

Rules:
1. Always provide the FULL script, never a partial snippet or diff.
2. Preserve the script's existing functionality unless the user explicitly asks for changes.
3. Improve error handling, add docstrings, optimize structure, fix potential issues.
4. If the script uses blocked imports, suggest alternatives using available globals.
5. Keep explanations concise and actionable.
"""


def enhance_script(source_code, script_name='', instructions=''):
    prompt = f"""Improve this script based on the following request:

{instructions if instructions else 'Review and enhance this script. Improve error handling, add documentation, optimize structure, and fix any potential issues.'}

--- SCRIPT ({script_name}) ---
{source_code}
--- END SCRIPT ---

Provide your improvements and the enhanced script."""

    messages = [
        {'role': 'system', 'content': ENHANCE_SCRIPT_SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    temperature = float(_get_setting('llm_temperature', '0.3'))
    if temperature > 0.2:
        temperature = 0.15
    max_tokens = int(_get_setting('llm_max_tokens', '4096'))

    response = _call_llm(messages, temperature, max_tokens)
    if response.startswith('Error:'):
        return {'reply': response, 'enhanced_code': None, 'error': response}

    enhanced_code = _extract_code_block(response)
    return {'reply': response, 'enhanced_code': enhanced_code, 'error': None}


FORM_SCHEMA_SYSTEM_PROMPT = """You are a form schema generator for a web application platform called PythonAppFoundry.

Forms are defined as JSON arrays of field objects. Each field has these properties:
- name: (required) unique field name, lowercase with underscores
- label: (required) human-readable label
- type: (required) one of: text, email, password, number, textarea, select, checkbox, date, time, datetime, file, hidden, url, tel, range
- required: (optional) boolean, default false
- placeholder: (optional) placeholder text
- options: (optional) comma-separated list for select fields
- min/max/step: (optional) numeric constraints

Example schema:
[
  {"name": "full_name", "label": "Full Name", "type": "text", "required": true, "placeholder": "Enter your name"},
  {"name": "email", "label": "Email Address", "type": "email", "required": true},
  {"name": "message", "label": "Message", "type": "textarea", "required": false, "placeholder": "Type your message..."},
  {"name": "priority", "label": "Priority", "type": "select", "options": "Low,Medium,High"}
]

Rules:
1. Output ONLY valid JSON array, no markdown, no code fences, no explanations.
2. Use descriptive field names (lowercase with underscores).
3. Choose appropriate types based on the field purpose.
4. Include reasonable placeholders and labels.
5. Set required=true for essential fields only.
6. Keep the schema practical and usable.
"""


def generate_form_schema(description, existing_schema=None):
    prompt = f"Generate a form schema for this description:\n\n{description}"
    if existing_schema:
        prompt += f"\n\nCurrent schema (improve or modify as needed):\n{existing_schema}"

    messages = [
        {'role': 'system', 'content': FORM_SCHEMA_SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    temperature = float(_get_setting('llm_temperature', '0.3'))
    if temperature > 0.2:
        temperature = 0.1
    max_tokens = int(_get_setting('llm_max_tokens', '4096'))

    response = _call_llm(messages, temperature, max_tokens)
    if response.startswith('Error:'):
        return {'reply': response, 'schema_json': None, 'error': response}

    schema_text = response.strip()
    try:
        import json
        parsed = json.loads(schema_text)
        if not isinstance(parsed, list):
            raise ValueError("Expected a JSON array")
        return {'reply': 'Schema generated successfully', 'schema_json': json.dumps(parsed, indent=2), 'error': None}
    except (json.JSONDecodeError, ValueError) as e:
        return {'reply': f'Failed to parse schema: {e}', 'schema_json': None, 'error': str(e)}


TEMPLATE_IMPROVE_SYSTEM_PROMPT = """You are a template improvement assistant for a web application platform called PythonAppFoundry.

Templates are Jinja2 HTML templates that can use these platform variables:
- {{ variable }} for simple values
- {% if condition %}...{% endif %} for conditionals
- {% for item in items %}...{% endfor %} for loops
- {{ variable|default('') }} for filters
- {{ variable|escape }} or {{ variable|e }} for HTML escaping

Improve the template based on the user's request. Respond in this exact format:

**Changes Made:**
[Bullet points describing what was improved]

**Improved Template:**
```html
[The full improved template code]
```

Rules:
1. Always provide the FULL template, never a partial snippet.
2. Preserve existing functionality and Jinja2 syntax.
3. Improve HTML structure, accessibility, responsiveness, and styling.
4. Fix any HTML errors or best practice violations.
5. Keep explanations concise.
"""


def improve_template(body, content_type='html', instructions=''):
    prompt = f"Improve this template based on the following request:\n\n{instructions if instructions else 'Review and improve this template. Fix HTML structure, improve accessibility, add responsive design, and follow best practices.'}\n\n--- TEMPLATE ({content_type}) ---\n{body}\n--- END TEMPLATE ---"

    messages = [
        {'role': 'system', 'content': TEMPLATE_IMPROVE_SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    temperature = float(_get_setting('llm_temperature', '0.3'))
    if temperature > 0.2:
        temperature = 0.15
    max_tokens = int(_get_setting('llm_max_tokens', '4096'))

    response = _call_llm(messages, temperature, max_tokens)
    if response.startswith('Error:'):
        return {'reply': response, 'improved_body': None, 'error': response}

    improved = _extract_code_block(response)
    return {'reply': response, 'improved_body': improved, 'error': None}


ROUTE_CONFIG_SYSTEM_PROMPT = """You are a route configuration assistant for a web application platform called PythonAppFoundry.

Routes map URL slugs to scripts and/or forms. Each route has:
- slug: URL path (e.g., "users/list", "api/data")
- methods: HTTP methods (GET, POST, PUT, DELETE, or comma-separated)
- script_id: associated script name (optional)
- form_id: associated form name (optional)
- auth_required: boolean, whether login is needed
- allowed_groups: comma-separated group IDs that can access (empty = all)
- title: human-readable title

Rules:
1. Output a JSON object with route configuration suggestions.
2. Use lowercase hyphenated slugs for URLs.
3. Suggest appropriate HTTP methods based on the operation.
4. Recommend auth_required=true for any data-modifying routes.
5. Keep explanations concise.

Respond in this format:

**Suggested Route Configuration:**
```json
{
  "slug": "example/route",
  "methods": "GET",
  "auth_required": false,
  "title": "Example Route",
  "notes": "Explanation of choices"
}
```
"""


def suggest_route_config(description, existing_slug=''):
    prompt = f"Suggest a route configuration for this description:\n\n{description}"
    if existing_slug:
        prompt += f"\n\nCurrent slug: {existing_slug}"

    messages = [
        {'role': 'system', 'content': ROUTE_CONFIG_SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ]

    temperature = float(_get_setting('llm_temperature', '0.3'))
    if temperature > 0.2:
        temperature = 0.1
    max_tokens = int(_get_setting('llm_max_tokens', '4096'))

    response = _call_llm(messages, temperature, max_tokens)
    if response.startswith('Error:'):
        return {'reply': response, 'config_json': None, 'error': response}

    config_text = _extract_code_block(response)
    if not config_text:
        config_text = response.strip()

    try:
        import json
        parsed = json.loads(config_text)
        return {'reply': 'Route configuration suggested', 'config_json': json.dumps(parsed, indent=2), 'error': None}
    except (json.JSONDecodeError, ValueError):
        return {'reply': response, 'config_json': None, 'error': 'Could not parse route configuration'}


def chat_completion(messages, temperature=None, max_tokens=None):
    system_text = _build_system_prompt()
    llm_messages = [{'role': 'system', 'content': system_text}]
    for msg in messages:
        llm_messages.append({'role': msg['role'], 'content': msg['content']})

    response = _call_llm(llm_messages, temperature, max_tokens)
    if response.startswith('Error:'):
        return {'reply': response, 'xml': None, 'valid': False, 'error': response}

    xml_str = _extract_xml(response)
    valid, error_msg = _validate_xml(xml_str) if xml_str else (False, None)

    return {
        'reply': response,
        'xml': xml_str,
        'valid': valid,
        'error': error_msg,
        'validated': True,
    }
