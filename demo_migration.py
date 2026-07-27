#!/usr/bin/env python3
"""
Demonstration script for database migration feature.

This script shows how the migration service works by:
1. Creating a sample SQLite database with test data
2. Exporting all data
3. Creating a new PostgreSQL-compatible database (simulated)
4. Importing the data
5. Verifying the migration
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from app.services.db_migration import export_database, import_to_new_database, verify_migration
from app import db, create_app

# Create a test application
app = create_app()

with app.app_context():
    print("=" * 60)
    print("Database Migration Feature Demonstration")
    print("=" * 60)
    
    # Step 1: Show current database
    print("\n1. Current Database:")
    print(f"   URL: {db.engine.url}")
    print(f"   Type: {'SQLite' if 'sqlite' in str(db.engine.url) else 'Other'}")
    
    # Step 2: Export data from current database
    print("\n2. Exporting data from current database...")
    exported = export_database(db.session)
    
    table_count = len(exported['tables'])
    total_rows = sum(t.get('row_count', 0) for t in exported['tables'].values())
    
    print(f"   Tables exported: {table_count}")
    print(f"   Total rows: {total_rows}")
    print(f"   Exported at: {exported['exported_at']}")
    
    # Show sample tables
    print("\n   Sample tables:")
    for i, (table_name, table_data) in enumerate(list(exported['tables'].items())[:5]):
        if 'error' not in table_data:
            print(f"     - {table_name}: {table_data['row_count']} rows")
    
    # Step 3: Demonstrate import to new database (using SQLite for demo)
    print("\n3. Importing to new database (demo using SQLite):")
    new_db_url = 'sqlite:///test_migration.db'
    
    try:
        import_results = import_to_new_database(exported, new_db_url)
        print(f"   Tables imported: {import_results['tables_imported']}")
        print(f"   Tables failed: {import_results['tables_failed']}")
        print(f"   Total rows imported: {import_results['total_rows']}")
        
        if import_results['errors']:
            print("\n   Errors:")
            for error in import_results['errors'][:3]:
                print(f"     - {error}")
        
        # Step 4: Verify migration
        print("\n4. Verifying migration...")
        new_engine = create_engine(new_db_url)
        verification = verify_migration(exported, new_engine)
        
        print(f"   Tables checked: {verification['tables_checked']}")
        print(f"   Tables matched: {verification['tables_matched']}")
        print(f"   Tables mismatched: {verification['tables_mismatched']}")
        
        if verification['tables_mismatched'] == 0:
            print("\n   ✓ Migration verification PASSED!")
        else:
            print("\n   ⚠ Migration verification completed with issues:")
            for detail in verification['details']:
                if detail.get('status') == 'mismatch':
                    print(f"     - {detail['table']}: expected {detail['original_count']}, got {detail['new_count']}")
        
        # Clean up test database
        import os
        if os.path.exists('test_migration.db'):
            os.remove('test_migration.db')
            print("\n   Cleaned up test database")
            
    except Exception as e:
        print(f"   Error during import: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("Demonstration complete!")
print("=" * 60)
print("\nThe database migration feature is now available at:")
print("  /__admin/db-migration")
print("\nFeatures:")
print("  - Export all data from current database")
print("  - Import to new PostgreSQL or SQLite database")
print("  - Automatic backup before migration")
print("  - Row count verification after migration")
print("  - Audit logging of all migration attempts")
