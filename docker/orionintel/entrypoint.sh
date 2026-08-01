#!/bin/bash
set -e

# 1) Apply database migrations before the app starts.
#    alembic env.py reads the DB URL from alembic.ini (baked into the image),
#    and the schemes/ package sits next to this .ini, so we cd there first.
#
#    The SAME image runs both the API and the celery worker. Only one of them
#    may migrate, otherwise both processes race on the alembic_version row, so
#    the worker service sets RUN_MIGRATIONS=0 in docker-compose.yml.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Running database migrations (alembic upgrade head)..."
  cd /app/models/db_schemes/minirag/
  alembic upgrade head
  cd /app
else
  echo "==> RUN_MIGRATIONS=0 — skipping migrations (another service owns them)."
fi

# 2) Hand off to the container's CMD (uvicorn ... / celery ... worker).
#    exec replaces this shell with the process so it becomes PID 1 and receives
#    Docker's stop signals — important for celery, which needs SIGTERM to do a
#    warm shutdown and finish the task it is holding.
echo "==> Starting application: $@"
exec "$@"
