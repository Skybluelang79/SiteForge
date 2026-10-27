# Backup and restore

## PostgreSQL

Nightly logical backup (cron example):

```sh
pg_dump --format=custom --no-owner --file=/backups/siteforge-$(date +%F).dump "$DATABASE_URL"
```

Keep at least 30 daily backups, 12 weekly backups and 12 monthly backups. Encrypt backups at rest
and store them in a separate account/bucket from the database host.

Restore:

```sh
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" /backups/siteforge-YYYY-MM-DD.dump
```

## Media

- Local storage: snapshot the `media_data` Docker volume or run `aws s3 sync` to a versioned bucket.
- S3 storage (`STORAGE_BACKEND=s3`): enable bucket versioning, cross-region replication and object
  lock/retention as required by the contract.

## Verification

1. Restore the latest dump into a scratch database.
2. Run migrations (`manage.py migrate`) and `manage.py check`.
3. Start the backend with the scratch `DATABASE_URL` and verify `/api/v1/health/ready/`.
4. Spot-check login, a project dashboard, document download and a report export.
5. Record the restore drill date and outcome.

## Recovery objectives

Document the agreed RPO/RTO per deployment. A practical starting point is RPO 24h (nightly dump
plus continuous WAL archiving for production) and RTO 2h. Test restores at least quarterly.
