#!/bin/sh
set -eu

mkdir -p /data /app/backend/uploads
chown -R vosi:vosi /data /app/backend/uploads

exec gosu vosi "$@"
