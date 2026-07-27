#!/usr/bin/env python3
"""Test that blueprints are registered correctly."""
import sys
sys.path.insert(0, '.')

from app import create_app
from app.routes.admin_blueprints import register_admin_blueprints
from flask import Blueprint

app = create_app()

# Check that all blueprints are registered
with app.app_context():
    # Get all registered blueprints
    registered = set(app.blueprints.keys())
    
    # Expected blueprints
    expected = {
        'modules', 'routes', 'scripts', 'forms', 'tasks', 'triggers',
        'users', 'groups', 'data', 'uploads', 'packages', 'settings',
        'queries', 'credentials', 'incoming_email', 'dashboard',
        'backup', 'marketplace', 'versions', 'test_script', 'import_preview',
        'openapi', 'dead_letter', 'db_migration'
    }
    
    print("Blueprint Registration Test")
    print("=" * 50)
    
    # Check which blueprints are registered
    missing = expected - registered
    extra = registered - expected
    
    if missing:
        print(f"✗ Missing blueprints: {missing}")
    else:
        print(f"✓ All {len(expected)} blueprints registered")
    
    if extra:
        print(f"⚠ Extra blueprints: {extra}")
    
    # Check URL rules
    print("\nSample URL Rules:")
    for rule in app.url_map.iter_rules():
        if rule.endpoint and 'modules' in rule.endpoint:
            print(f"  {rule.methods} {rule.rule} -> {rule.endpoint}")
            if len([r for r in app.url_map.iter_rules() if 'modules' in r.endpoint]) > 5:
                break

if __name__ == '__main__':
    print("\nTest complete!")
