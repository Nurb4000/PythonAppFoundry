# Database Migration Feature

## Overview

The database migration feature allows admins to safely migrate data between SQLite and PostgreSQL databases directly from the admin UI, without requiring CLI commands or manual intervention.

## Access

Navigate to **Admin Panel → DB Migration** at `/__admin/db-migration`

## Features

- **Export all data** from the current database (SQLite or PostgreSQL)
- **Import to new database** with automatic schema conversion
- **Pre-migration backup** created automatically before each migration
- **Row count verification** ensures data integrity after migration
- **Audit logging** tracks all migration attempts
- **Admin-only access** for security

## Migration Process

1. **Enter target database URL** in the admin settings page
   - Example: `postgresql://username:password@localhost:5432/dbname`
   
2. **Save migration target** (this doesn't execute anything yet)

3. **Click "Execute Migration"** to begin the process

4. **Automatic steps:**
   - Create backup of current database
   - Export all tables and data
   - Import to new database with compatible schema
   - Verify row counts match
   - Log results to audit trail

5. **Update `.env` file** with new `DATABASE_URL` and restart the application

## Supported Databases

- **Source:** SQLite, PostgreSQL
- **Target:** SQLite, PostgreSQL
- **Requirement:** For PostgreSQL targets, install `psycopg2-binary` package

## Prerequisites

### For PostgreSQL Migration

If you're migrating to PostgreSQL, you must install the psycopg2 driver:

```bash
pip install psycopg2-binary
```

This is included in `requirements.txt` as an optional dependency (commented out).
Uncomment the line to enable PostgreSQL support.

## Example PostgreSQL URL

```
postgresql://myuser:mypassword@localhost:5432/mydatabase
```

## Security

- Only accessible to admin users
- CSRF protection on all migration actions
- Pre-migration backup automatically created
- Source and target cannot be the same database
- All migrations are logged in the audit trail

## Troubleshooting

If migration fails:
1. Check the audit log at `/__admin/audit` for error details
2. Verify the target database URL is correct and accessible
3. Ensure the target database server is running
4. Check that the database user has CREATE TABLE and INSERT privileges
5. Restore from backup if needed (available at `/__admin/backup/list`)

## Technical Details

The migration service:
- Exports data using SQLAlchemy's text() queries
- Creates tables with PostgreSQL-compatible types
- Uses parameterized queries to prevent SQL injection
- Verifies migration by comparing row counts
- Handles all platform tables including dynamic tables
