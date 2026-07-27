#!/usr/bin/env python3
"""
Demonstration script for dynamic table indexing feature.

This script shows how to:
1. Create dynamic tables with indexes
2. Manage indexes via the admin UI
3. Understand performance implications
"""
import sys
sys.path.insert(0, '.')

from app import create_app, db
from app.models import DynamicModel
from sqlalchemy import String, Integer, DateTime
from sqlalchemy import inspect as sa_inspect

app = create_app()

with app.app_context():
    print("=" * 70)
    print("Dynamic Table Indexing Feature Demonstration")
    print("=" * 70)
    
    # Example 1: Create a table with indexes
    print("\n[Example 1] Creating dynamic table with indexes...")
    print("-" * 70)
    
    try:
        # Create a sample table for order tracking
        Order = DynamicModel.get_or_create('orders', {
            'customer_id': Integer,
            'status': String(50),
            'total_amount': String(20),  # Stored as string for flexibility
            'created_at': String(50),    # ISO format datetime
        }, indexes=['customer_id', 'status'])
        
        print("✓ Table 'orders' created with columns:")
        print("  - customer_id (indexed)")
        print("  - status (indexed)")
        print("  - total_amount")
        print("  - created_at")
        
        # Verify indexes were created
        inspector = sa_inspect(db.session.get_bind())
        if 'orders' in inspector.get_table_names():
            indexes = inspector.get_indexes('orders')
            dynamic_indexes = [idx for idx in indexes if idx['name'].startswith('idx_orders')]
            
            print(f"\n✓ Created {len(dynamic_indexes)} indexes:")
            for idx in dynamic_indexes:
                print(f"  - {idx['name']}: columns={idx['column_names']}")
        
        # Clean up
        db.session.execute(db.text('DROP TABLE IF EXISTS orders'))
        db.session.commit()
        print("\n✓ Test table cleaned up")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Example 2: Adding indexes to existing table
    print("\n[Example 2] Indexes are created automatically...")
    print("-" * 70)
    print("When you call DynamicModel.get_or_create() with the indexes parameter,")
    print("indexes are created automatically if the columns exist.")
    print("If columns are added later, you can manage indexes via the admin UI.")
    
    # Example 3: Admin UI
    print("\n[Example 3] Managing indexes via Admin UI...")
    print("-" * 70)
    print("Navigate to: /__admin/indexes")
    print("\nFeatures:")
    print("  ✓ View all dynamic tables and their indexes")
    print("  ✓ See row counts per table")
    print("  ✓ Add indexes to existing tables")
    print("  ✓ Drop unused indexes")
    print("  ✓ Best practices guidance")
    
    print("\n" + "=" * 70)
    print("Demonstration complete!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("1. Specify indexes when creating dynamic tables")
    print("2. Use indexes for columns in WHERE, JOIN, ORDER BY clauses")
    print("3. Avoid indexing low-cardinality columns (booleans, enums with few values)")
    print("4. Monitor index usage to identify unused indexes")
    print("5. Each index adds ~5-15% overhead to write operations")
