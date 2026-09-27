#!/bin/sh
# Human-operated deployment template. Never run against remote services during tests.
set -eu
: "${APP_ROOT:?}" "${BACKUP_STAGING:?}" "${RESTIC_REPOSITORY:?}" "${RESTIC_PASSWORD_FILE:?}"
umask 077
mkdir -p "$BACKUP_STAGING"
exec 9>"$BACKUP_STAGING/backup.lock"
flock -n 9 || exit 1
snapshot="$BACKUP_STAGING/snapshot-$(date -u +%Y%m%dT%H%M%SZ)"
cd "$APP_ROOT"
.venv/bin/python app/manage.py export_snapshot "$snapshot"
restic backup "$snapshot" --tag study-daily
# Only reached after remote backup success. Retain the export on failure for investigation.
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_STAGING/last-success.new"
mv "$BACKUP_STAGING/last-success.new" "$BACKUP_STAGING/last-success"
# Retention/prune is deliberately not automatic. Enable after a verified restore drill.
