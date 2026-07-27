#!/usr/bin/env python3
"""
Demonstration script for global search feature.

This script shows how the search service works by searching across
all entity types in the platform.
"""
import sys
sys.path.insert(0, '.')

from app.services.search import search_all
from app import create_app

app = create_app()

with app.app_context():
    print("=" * 70)
    print("Global Search Feature Demonstration")
    print("=" * 70)
    
    # Test searches for different entity types
    test_queries = ['admin', 'module', 'script', 'route']
    
    for query in test_queries:
        print(f"\nSearching for: '{query}'")
        print("-" * 70)
        
        results = search_all(query, limit=10)
        total = sum(len(v) for v in results.values())
        
        if total > 0:
            print(f"Found {total} result(s):")
            for entity_type, items in results.items():
                if items:
                    print(f"\n  {entity_type.upper()} ({len(items)}):")
                    for item in items[:3]:  # Show first 3
                        name = item.get('name', item.get('username', 'N/A'))
                        url = item.get('url', '')
                        print(f"    - {name} → {url}")
        else:
            print("  No results found")
    
    print("\n" + "=" * 70)
    print("Search feature is available at: /__admin/search")
    print("=" * 70)
