#!/bin/bash
set -e

echo "Restoring dump into $POSTGRES_DB..."
pg_restore \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --no-owner \
    --no-privileges \
    /docker-entrypoint-initdb.d/du_portal_diploma.dump
echo "Restore complete."
