"""Tests for module bundle import/export."""
import pytest


class TestModuleExport:
    """Test XML export of modules."""

    def test_export_module_xml(self, app_context, sample_module):
        """Export should produce valid XML with module data."""
        from app.services.bundle import export_module
        xml_str = export_module(sample_module)
        assert '<?xml' in xml_str
        assert '<module' in xml_str
        assert 'test-module' in xml_str
        assert 'Test Module' in xml_str

    def test_export_includes_scripts(self, app_context, sample_script):
        """Export should include scripts belonging to the module."""
        from app.services.bundle import export_module
        xml_str = export_module(sample_script.module)
        assert 'test_script' in xml_str
        assert 'hello world' in xml_str


class TestModuleImport:
    """Test XML import of modules."""

    def test_import_minimal_module(self, app_context, clean_db):
        """Import a minimal valid module XML."""
        from app.services.bundle import import_module
        from app.models import Module

        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<module name="Imported" slug="imported-test" version="1.0.0" author="Test">
</module>'''

        m = import_module(xml_str)
        assert m.name == 'Imported'
        assert m.slug == 'imported-test'
        assert m.version == '1.0.0'

    def test_import_with_script(self, app_context, clean_db):
        """Import a module containing a script."""
        from app.services.bundle import import_module
        from app.models import Module, Script

        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<module name="WithScript" slug="with-script" version="1.0.0" author="Test">
  <scripts>
    <script name="hello" language="python">
      _result = "hello from import"
    </script>
  </scripts>
</module>'''

        m = import_module(xml_str)
        scripts = Script.query.filter_by(module_id=m.id).all()
        assert len(scripts) == 1
        assert scripts[0].name == 'hello'

    def test_import_duplicate_slug_raises(self, app_context, sample_module):
        """Import with duplicate slug should raise ValueError."""
        from app.services.bundle import import_module

        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<module name="Duplicate" slug="test-module" version="1.0.0" author="Test">
</module>'''

        with pytest.raises(ValueError, match='already exists'):
            import_module(xml_str)

    def test_import_update_existing(self, app_context, sample_module):
        """Import with update_existing=True should update the module name and bump patch version."""
        from app.services.bundle import import_module

        xml_str = '''<?xml version="1.0" encoding="UTF-8"?>
<module name="Updated Module" slug="test-module" version="2.0.0" author="Updater">
</module>'''

        m = import_module(xml_str, update_existing=True)
        assert m.name == 'Updated Module'
        # Bundle import auto-bumps patch version on update
        assert m.version.startswith('1.0.')  # Patch bump from 1.0.0


class TestXXESafety:
    """Test XML parsing safety against XXE attacks."""

    def test_xxe_entity_expansion(self, app_context):
        """XXE entity expansion should be blocked by defusedxml."""
        from app.services.xml_utils import safe_fromstring, XMLParseError

        # Basic external entity attempt — defusedxml blocks entities
        xxe_xml = '''<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<module name="XXE" slug="xxe-test" version="1.0.0" author="Test">&xxe;</module>'''

        with pytest.raises(XMLParseError):
            safe_fromstring(xxe_xml)

    def test_billion_laughs_guard(self, app_context):
        """Billion laughs attack should be blocked by defusedxml."""
        from app.services.xml_utils import safe_fromstring, XMLParseError

        # Simplified billion laughs — entities are blocked
        bl_xml = '''<?xml version="1.0"?>
<!DOCTYPE r [
  <!ENTITY a "ha">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<module name="BL" slug="bl-test" version="1.0.0" author="Test">&c;</module>'''

        with pytest.raises(XMLParseError):
            safe_fromstring(bl_xml)
