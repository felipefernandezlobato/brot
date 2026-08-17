#!/bin/bash
# Fail the deploy if migrations fail. Without this, a failed `alembic upgrade`
# fell through to uvicorn and served the new code against the old schema — every
# endpoint touching a new column returned 500. Better that Render marks the deploy
# failed and keeps the previous version serving.
set -e

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
