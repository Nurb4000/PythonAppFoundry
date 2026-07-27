"""Database migration service for transferring data between SQLite and PostgreSQL.

This service handles:
- Exporting all data from the current database
- Creating a new database with compatible schema
- Importing data into the new database
- Verifying migration integrity
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.orm import sessionmaker
from app import db

logger = logging.getLogger(__name__)


def export_database(session):
    """Export all data from the current database.
    
    Returns a dictionary with table names and their data.
    """
    exporter = DatabaseExporter(session)
    return exporter.export_all()


def import_to_new_database(exported_data, new_db_url):
    """Import exported data into a new database.
    
    Args:
        exported_data: Dictionary from export_database()
        new_db_url: SQLAlchemy database URL for the new database
        
    Returns:
        Dictionary with migration results
    """
    importer = DatabaseImporter(new_db_url)
    return importer.import_all(exported_data)


def verify_migration(original_data, new_engine):
    """Verify that data was migrated correctly by comparing row counts.
    
    Args:
        original_data: Original exported data
        new_engine: SQLAlchemy engine for the new database
        
    Returns:
        Dictionary with verification results
    """
    verifier = MigrationVerifier(new_engine)
    return verifier.verify(original_data)


class DatabaseExporter:
    """Exports data from the current database."""
    
    def __init__(self, session):
        self.session = session
        self.engine = session.get_bind()
        
    def export_all(self):
        """Export all tables and their data."""
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        
        exported = {
            'tables': {},
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'source_db': str(self.engine.url),
        }
        
        for table_name in table_names:
            # Skip alembic_version if it exists
            if table_name == 'alembic_version':
                continue
                
            try:
                result = self.session.execute(text(f'SELECT * FROM "{table_name}"'))
                columns = result.keys()
                data = result.fetchall()
                
                exported['tables'][table_name] = {
                    'columns': list(columns),
                    'rows': [list(row) for row in data],
                    'row_count': len(data),
                }
                logger.info(f'Exported table {table_name}: {len(data)} rows')
            except Exception as e:
                logger.error(f'Failed to export table {table_name}: {e}')
                exported['tables'][table_name] = {
                    'error': str(e),
                    'row_count': 0,
                }
        
        return exported


class DatabaseImporter:
    """Imports data into a new database."""
    
    def __init__(self, db_url):
        self.db_url = db_url
        try:
            self.engine = create_engine(db_url)
        except ImportError as e:
            raise ImportError(
                f'Database driver not found. For PostgreSQL, install psycopg2: pip install psycopg2-binary. '
                f'Error: {e}'
            )
        self.metadata = MetaData()
        
    def import_all(self, exported_data):
        """Import all tables and data."""
        results = {
            'imported_at': datetime.now(timezone.utc).isoformat(),
            'target_db': self.db_url,
            'tables_imported': 0,
            'tables_failed': 0,
            'total_rows': 0,
            'errors': [],
        }
        
        # Create all tables first
        self.metadata.reflect(bind=self.engine)
        
        for table_name, table_data in exported_data['tables'].items():
            if 'error' in table_data:
                results['tables_failed'] += 1
                results['errors'].append(f'{table_name}: {table_data["error"]}')
                continue
            
            try:
                self._import_table(table_name, table_data)
                results['tables_imported'] += 1
                results['total_rows'] += table_data['row_count']
                logger.info(f'Imported table {table_name}: {table_data["row_count"]} rows')
            except Exception as e:
                results['tables_failed'] += 1
                results['errors'].append(f'{table_name}: {str(e)}')
                logger.error(f'Failed to import table {table_name}: {e}')
        
        return results
    
    def _import_table(self, table_name, table_data):
        """Import a single table."""
        columns = table_data['columns']
        rows = table_data['rows']
        
        # Create table if it doesn't exist
        if not self._table_exists(table_name):
            self._create_table(table_name, columns)
        
        # Insert data
        if rows:
            for row in rows:
                self._insert_row(table_name, columns, row)
    
    def _table_exists(self, table_name):
        """Check if a table exists in the new database."""
        inspector = inspect(self.engine)
        return table_name in inspector.get_table_names()
    
    def _create_table(self, table_name, columns):
        """Create a table with appropriate PostgreSQL types."""
        column_defs = []
        for i, col_name in enumerate(columns):
            # First column is usually 'id' - make it primary key
            if i == 0 and col_name.lower() == 'id':
                column_defs.append(f'"id" BIGINT PRIMARY KEY')
            else:
                # Use TEXT as default for simplicity
                column_defs.append(f'"{col_name}" TEXT')
        
        create_sql = f'CREATE TABLE "{table_name}" ({", ".join(column_defs)})'
        with self.engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()
    
    def _insert_row(self, table_name, columns, row):
        """Insert a single row into a table."""
        if len(columns) != len(row):
            raise ValueError(f'Column count mismatch for {table_name}: {len(columns)} columns, {len(row)} values')
        
        # Build INSERT statement with named parameters
        col_names = ', '.join(f'"{c}"' for c in columns)
        placeholders = ', '.join([f':{c}' for c in columns])
        insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'
        
        # Create parameter dict
        params = {col: val for col, val in zip(columns, row)}
        
        with self.engine.connect() as conn:
            conn.execute(text(insert_sql), params)
            conn.commit()


class MigrationVerifier:
    """Verifies migration integrity."""
    
    def __init__(self, new_engine):
        self.new_engine = new_engine
        
    def verify(self, original_data):
        """Verify that all tables and row counts match."""
        results = {
            'verified_at': datetime.now(timezone.utc).isoformat(),
            'tables_checked': 0,
            'tables_matched': 0,
            'tables_mismatched': 0,
            'details': [],
        }
        
        inspector = inspect(self.new_engine)
        new_table_names = set(inspector.get_table_names())
        original_table_names = set(original_data['tables'].keys())
        
        # Check for missing tables
        if original_table_names - new_table_names:
            results['details'].append({
                'error': 'Missing tables in new database',
                'tables': list(original_table_names - new_table_names),
            })
        
        # Check for extra tables
        if new_table_names - original_table_names:
            results['details'].append({
                'warning': 'Extra tables in new database',
                'tables': list(new_table_names - original_table_names),
            })
        
        # Verify row counts
        for table_name in original_table_names & new_table_names:
            results['tables_checked'] += 1
            
            original_count = original_data['tables'][table_name].get('row_count', 0)
            try:
                new_count = self._get_row_count(table_name)
                
                if original_count == new_count:
                    results['tables_matched'] += 1
                    results['details'].append({
                        'table': table_name,
                        'status': 'ok',
                        'row_count': new_count,
                    })
                else:
                    results['tables_mismatched'] += 1
                    results['details'].append({
                        'table': table_name,
                        'status': 'mismatch',
                        'original_count': original_count,
                        'new_count': new_count,
                    })
            except Exception as e:
                results['tables_mismatched'] += 1
                results['details'].append({
                    'table': table_name,
                    'status': 'error',
                    'error': str(e),
                })
        
        return results
    
    def _get_row_count(self, table_name):
        """Get row count for a table."""
        with self.new_engine.connect() as conn:
            result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            return result.fetchone()[0]
