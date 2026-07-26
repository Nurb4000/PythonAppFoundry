# Docker Deployment Quick Reference

## Quick Start

```bash
# Clone and setup
git clone https://github.com/Nurb4000/PythonAppFoundry
cd PythonAppFoundry
cp .env.docker.example .env
# Edit .env and set SECRET_KEY!

# Start with SQLite (default)
docker compose up -d

# Access the application
open http://localhost:5000
```

## Common Commands

```bash
# View logs
docker compose logs -f web

# Restart application
docker compose restart web

# Stop all services
docker compose down

# Remove all data (including database)
docker compose down -v

# Update to latest version
git pull
docker compose build --no-cache
docker compose up -d
```

## Environment Variables

Key variables in `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | — | Security key (change in production!) |
| `DATABASE_URL` | No | SQLite | Database connection string |
| `APP_DEBUG` | No | `true` | Flask debug mode |
| `LLAMA_CPP_URL` | No | — | llama.cpp server URL |

See `.env.docker.example` for all variables.

## Production Checklist

- [ ] Change `SECRET_KEY` to a random 32-byte hex string
- [ ] Set `APP_DEBUG=false`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS with a reverse proxy
- [ ] Set up regular database backups
- [ ] Review and adjust resource limits in `docker-compose.prod.yml`
- [ ] Monitor logs: `docker compose logs -f web`

## Troubleshooting

**Application won't start:**
```bash
docker compose logs web
# Check for configuration errors
```

**Database connection failed:**
```bash
docker compose logs db
# Verify DATABASE_URL and credentials
```

**AI generation not working:**
```bash
docker compose logs llamacpp
# Ensure model is downloaded and endpoint is correct
```

**Port already in use:**
```bash
# Change APP_PORT in .env or docker-compose.yml
```

## Data Persistence

All application data is stored in `./instance/`:
- `data.db` — SQLite database (or PostgreSQL data in `postgres_data` volume)
- `uploads/` — User uploaded files
- `backups/` — Database backups
- `credential.key` — Encryption key for credentials
- `logs/` — Application logs

Back up this directory regularly!

## Security Notes

1. **Never commit `.env` files** — They contain secrets
2. **Use strong `SECRET_KEY`** — Generate with: `openssl rand -hex 32`
3. **Keep images updated** — Pull latest versions regularly
4. **Use PostgreSQL in production** — SQLite is for development only
5. **Enable HTTPS** — Use nginx or Caddy as a reverse proxy

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PythonAppFoundry README](../README.md)
- [Admin Guide](../ADMIN_AND_DEVELOPER_GUIDE.md)
