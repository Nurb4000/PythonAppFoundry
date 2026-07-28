from jinja2.sandbox import ImmutableSandboxedEnvironment
import jinja2

_sandbox_env = ImmutableSandboxedEnvironment(
    autoescape=True,
    undefined=jinja2.StrictUndefined,
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
