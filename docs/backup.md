# Backup and restore

The database contains personal list choices and optional holdings annotations. Treat backups as private data.

## Backup

Create a backup before schema upgrades:

```bash
mkdir -p backups
./scripts/backup
```

The script uses `pg_dump` from a temporary PostgreSQL client container and writes a timestamped custom-format dump under `backups/`. Keep a local rotation and, if the server supports it, an encrypted copy on a separate disk.

## Restore

Stop the web and worker services, create an empty database, and restore with `pg_restore`. Do not restore over a live database without a tested backup. After restoring, run `docker compose exec web alembic upgrade head`, start services, and check `/health/ready` plus the Settings page.

The project does not upload backups to a cloud service. The operator is responsible for retention, permissions, encryption, and testing a restore periodically.
