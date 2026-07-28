from jinja2.sandbox import ImmutableSandboxedEnvironment
import jinja2

_sandbox_env = ImmutableSandboxedEnvironment(
    autoescape=True,
    undefined=jinja2.StrictUndefined,
)
_sandbox_env.filters['split'] = lambda s, sep=',': s.split(sep) if sep else s.split()


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
