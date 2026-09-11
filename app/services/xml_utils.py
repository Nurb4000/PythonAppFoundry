"""Safe XML parsing helpers.

Untrusted XML (module imports, import previews, AI-generated bundles) is parsed
with ``defusedxml`` rather than the stdlib ``xml.etree.ElementTree``. defusedxml
is a drop-in replacement that blocks external-entity / DTD-based attacks such as
XXE and the "billion laughs" entity-expansion DoS.
"""
import logging

from defusedxml.ElementTree import fromstring as _defused_fromstring

logger = logging.getLogger(__name__)


class XMLParseError(ValueError):
    """Raised when untrusted XML trips a defusedxml security guard."""


def safe_fromstring(xml_text):
    """Parse an XML string, rejecting DTDs and entity expansions.

    Raises :class:`XMLParseError` (a ``ValueError``) on malicious or malformed
    input so callers can surface a friendly message instead of leaking the raw
    defusedxml exception.
    """
    try:
        return _defused_fromstring(xml_text)
    except Exception as e:
        logger.warning('Blocked unsafe XML parse: %s', e)
        raise XMLParseError(
            'The provided XML is malformed or contains disallowed content.'
        ) from e
