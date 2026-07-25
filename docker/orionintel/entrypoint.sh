#!/bin/bash
set -e

# 1) Apply database migrations before the app starts.
#    alembic env.py reads the DB URL from alembic.ini (baked into the image),
#    and the schemes/ package sits next to this .ini, so we cd there first.
echo "==> Running database migrations (alembic upgrade head)..."
cd /app/models/db_schemes/minirag/
alembic upgrade head
cd /app

# 2) Hand off to the container's CMD (uvicorn ...).
#    exec replaces this shell with uvicorn so it becomes PID 1 and receives
#    Docker's stop signals. (mini-rag's entrypoint omits this line, which is
#    why its app never actually starts after migrations — fixed here.)
echo "==> Starting application: $@"
exec "$@"
