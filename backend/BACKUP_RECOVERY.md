# VOSI backup and recovery

The production Compose stack is single-node SQLite. This utility creates a compressed backup containing SQLite online-backup snapshots, account uploads, and a manifest. It deliberately excludes .env files, provider keys, account session tokens, and other secrets.

## Create a backup

From the backend directory, after configuring .env:

```bash
docker compose --profile backup run --rm backup
```

The archive is written to the host-mounted backups directory with mode 0600. Store a second encrypted copy outside the VM. Do not commit backups to Git.

For a consistent point-in-time backup across all three independent SQLite databases, briefly stop API writes before running the backup:

```bash
docker compose stop api
docker compose --profile backup run --rm backup
docker compose start api
```

Without stopping writes, SQLite still gives each database a consistent individual snapshot, but the databases may represent slightly different moments.

## Verify a backup

```bash
tar -tzf backups/vosi-backup-*.tar.gz
```

Check for vosi/manifest.json and the expected database files. The utility runs PRAGMA integrity_check on each database snapshot before packaging it.

## Restore procedure

1. Stop the API and cloud worker: docker compose stop api cloud-browser-worker.
2. Preserve the current vosi_data volume before replacing anything.
3. Extract the archive into a temporary directory and inspect vosi/manifest.json. Never extract an archive from an untrusted source.
4. Copy listed databases/*.sqlite3 files to their configured database paths in /data; restore account_uploads/ to VOSI_ACCOUNT_UPLOAD_DIR. Preserve ownership for the API container user.
5. Start the API and check /health/ready, account sign-in, chat history, task history and screen history before resuming traffic.

A backup is not proven until a restore has been rehearsed. Run a restore drill before production launch and periodically thereafter. Keep encrypted off-host copies and define a retention policy appropriate to your data.
