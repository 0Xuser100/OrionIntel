"""Flower configuration, loaded by `celery -A celery_app flower --conf=flowerconfig.py`.

Flower is the read-only web dashboard for the cluster: live workers, task
history, queue depth, and a per-task detail view. It has no OrionIntel logic in
it — it just reads the broker and the result backend.
"""

import os

from dotenv import dotenv_values

# In Docker the settings arrive as real environment variables (compose
# `env_file:`), and there is NO .env file in the image. Running locally it is the
# other way round. Read the environment first and fall back to the file, so the
# same config works in both.
#
# The reference repo does only `dotenv_values(".env")["CELERY_FLOWER_PASSWORD"]`,
# which raises KeyError and kills the container in Docker.
_file_config = dotenv_values(".env")


def _setting(name: str, default: str = "") -> str:
    return os.environ.get(name) or _file_config.get(name) or default


port = 5555
# Cap on how many completed tasks Flower keeps in memory. Flower is not a
# database: restart it and this history is gone (Celery's own results in Redis
# and the celery_task_executions table are the durable records).
max_tasks = 10000
auto_refresh = True

# HTTP basic auth — Flower exposes every task's arguments, so it must not be
# open. user is "admin"; password comes from CELERY_FLOWER_PASSWORD.
basic_auth = [f"admin:{_setting('CELERY_FLOWER_PASSWORD', 'admin')}"]
