#!/bin/sh
set -e

exec waitress-serve \
  --listen="${HOST:-0.0.0.0}:${PORT:-3000}" \
  app.main:server
