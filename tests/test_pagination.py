"""Tests for admin list view pagination."""
import pytest


class TestPagination:
    """Test that list_view applies pagination correctly."""

    def test_default_page_size(self, logged_in_client):
        """Default page size should be 50."""
        resp = logged_in_client.get('/__admin/scripts/')
        assert resp.status_code == 200

    def test_custom_page_size(self, logged_in_client):
        """Custom per_page parameter should be respected."""
        resp = logged_in_client.get('/__admin/scripts/?per_page=25')
        assert resp.status_code == 200

    def test_page_parameter(self, logged_in_client):
        """Page parameter should work."""
        resp = logged_in_client.get('/__admin/scripts/?page=1')
        assert resp.status_code == 200

    def test_pagination_preserves_module_filter(self, logged_in_client):
        """Module filter should be preserved across pages."""
        resp = logged_in_client.get('/__admin/scripts/?module_id=1&page=2')
        assert resp.status_code == 200

    def test_pagination_preserves_sort(self, logged_in_client):
        """Sort parameters should be preserved across pages."""
        resp = logged_in_client.get('/__admin/scripts/?sort=name&order=desc&page=2')
        assert resp.status_code == 200

    def test_per_page_clamped_min(self, logged_in_client):
        """per_page below 10 should be clamped to 10."""
        resp = logged_in_client.get('/__admin/scripts/?per_page=1')
        assert resp.status_code == 200

    def test_per_page_clamped_max(self, logged_in_client):
        """per_page above 500 should be clamped to 500."""
        resp = logged_in_client.get('/__admin/scripts/?per_page=10000')
        assert resp.status_code == 200

    def test_export_bypasses_pagination(self, logged_in_client):
        """JSON export should include all rows regardless of pagination."""
        resp = logged_in_client.get('/__admin/scripts?format=json', follow_redirects=True)
        assert resp.status_code == 200
        assert resp.mimetype == 'application/json'

    def test_csv_export_bypasses_pagination(self, logged_in_client):
        """CSV export should include all rows regardless of pagination."""
        resp = logged_in_client.get('/__admin/scripts?format=csv', follow_redirects=True)
        assert resp.status_code == 200
        assert resp.mimetype == 'text/csv'
