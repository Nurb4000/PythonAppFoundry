from jinja2.sandbox import ImmutableSandboxedEnvironment, SandboxedEnvironment
import jinja2

_sandbox_env = ImmutableSandboxedEnvironment(
    autoescape=True,
    undefined=jinja2.StrictUndefined,
)

# A dedicated sandbox for rendering *script-supplied* template strings.
# It uses a lenient (non-strict) Undefined so partial-context rendering keeps
# working, while still blocking dunder attribute access and unsafe calls that
# are used in Jinja2 SSTI escape chains.
_script_render_env = SandboxedEnvironment(
    autoescape=True,
    undefined=jinja2.Undefined,
)

# Add commonly used filters that may not be in the sandbox by default
_sandbox_env.filters['split'] = lambda s, sep=',': s.split(sep) if sep else s.split()
_sandbox_env.filters['dict'] = dict
_sandbox_env.filters['keys'] = lambda d: d.keys() if isinstance(d, dict) else []
_sandbox_env.filters['values'] = lambda d: d.values() if isinstance(d, dict) else []
_sandbox_env.filters['cycle'] = lambda *args: args[0] if args else ''
_sandbox_env.filters['date'] = lambda d, fmt='%Y-%m-%d': d.strftime(fmt) if d else ''
_sandbox_env.filters['time'] = lambda d, fmt='%H:%M': d.strftime(fmt) if d else ''
_sandbox_env.filters['datetime'] = lambda d, fmt='%Y-%m-%d %H:%M': d.strftime(fmt) if d else ''


def render_db_template(template_body, **context):
    """Render a database-stored Jinja2 template in a sandbox.

    Usage in scripts::

        tpl = Template.query.filter_by(name='dashboard', module_id=module_id).first()
        return render_db_template(tpl.body, title='Sales', rows=data)

    The sandbox blocks unsafe attribute access (``__class__``, ``__subclasses__``),
    mutating operations on passed objects (``.append()``, ``.update()``), and
    calling unsafe callables.  All variables are HTML-escaped by default to
    prevent XSS.  Missing variables raise ``UndefinedError`` rather than
    rendering as empty strings.
    """
    tmpl = _sandbox_env.from_string(template_body)
    return tmpl.render(**context)


def render_script_template(template_body, **context):
    """Render a script-supplied template string in a sandbox.

    This is the safe replacement for Flask's ``render_template_string``: it
    uses a sandboxed Jinja2 environment so template source coming from
    untrusted scripts/imports cannot traverse dunders (``__class__``,
    ``__subclasses__``) to reach arbitrary Python objects.
    """
    tmpl = _script_render_env.from_string(template_body)
    return tmpl.render(**context)
