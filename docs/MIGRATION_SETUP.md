# Database Migration - Installation & Usage Guide

## Quick Start

### 1. Install Required Dependencies

For **SQLite to SQLite** migration (no extra dependencies):
```bash
# Already included in requirements.txt
```

For **SQLite/PostgreSQL to PostgreSQL** migration:
```bash
pip install psycopg2-binary
```

Or uncomment the psycopg2 line in `requirements.txt`:
```bash
# In requirements.txt, uncomment:
# psycopg2-binary==2.9.9
pip install -r requirements.txt
```

### 2. Access the Migration Tool

Navigate to: **Admin Panel → DB Migration**
URL: `/__admin/db-migration`

### 3. Perform Migration

1. Enter your target database URL in the format field
2. Click "Save Migration Target"
3. Review the migration details
4. Click "Execute Migration"
5. Wait for verification to complete
6. Update your `.env` file with the new `DATABASE_URL`
7. Restart the application

## Database URL Formats

### SQLite
```
sqlite:///path/to/database.db
```

### PostgreSQL
```
postgresql://username:password@hostname:port/dbname
```

Example:
```
postgresql://myuser:mypassword@localhost:5432/myapp_db
```

## Troubleshooting

### Error: "No module named 'psycopg2'"

**Solution:** Install the psycopg2 driver:
```bash
pip install psycopg2-binary
```

### Error: "Connection refused" or "Could not connect to server"

**Solutions:**
1. Verify PostgreSQL is running: `systemctl status postgresql`
2. Check the hostname/port in your URL
3. Ensure the database exists: `createdb myapp_db`
4. Verify user has CREATE TABLE and INSERT privileges

### Error: "Source and target databases cannot be the same"

**Solution:** You cannot migrate a database to itself. Create a new database first.

### Migration fails partway through

**Solutions:**
1. Check the audit log at `/__admin/audit` for detailed error messages
2. A pre-migration backup was automatically created - restore from `/__admin/backup/list` if needed
3. Verify network connectivity to the target database
4. Ensure sufficient disk space on the target server

## Security Notes

- Migration is **admin-only** - developers cannot access it
- Pre-migration backup is **automatically created** before each migration
- All migrations are **logged in the audit trail**
- Database URLs are **validated** before execution
- Source and target **cannot be the same** database

## What Gets Migrated

The migration includes:
- ✓ All platform tables (users, modules, routes, scripts, etc.)
- ✓ Dynamic tables created by modules
- ✓ Settings and credentials
- ✓ Execution logs and audit logs
- ✓ Chat sessions and messages
- ✓ File upload records
- ✗ Actual file uploads (stored on disk, not in DB)

## After Migration

1. **Update `.env` file:**
   ```bash
   DATABASE_URL=postgresql://newuser:newpass@newhost:5432/newdb
   ```

2. **Restart the application:**
   ```bash
   # Stop current instance
   # Start with new .env
   python run.py
   ```

3. **Verify everything works:**
   - Log in to admin panel
   - Check that all modules are present
   - Test a few routes
   - Verify scheduled tasks are running

4. **Keep old database as backup** until you're confident the migration succeeded

## Performance Tips

- **Large databases:** Migration may take several minutes. Be patient.
- **Network latency:** If target DB is on another server, ensure stable connection
- **Database size:** Check table sizes before migration: `/__admin/data`
- **Peak hours:** Run migrations during low-traffic periods

## Support

If you encounter issues:
1. Check the audit log for detailed error messages
2. Review the application logs
3. Verify database connectivity with a simple test query
4. Ensure all prerequisites are met
