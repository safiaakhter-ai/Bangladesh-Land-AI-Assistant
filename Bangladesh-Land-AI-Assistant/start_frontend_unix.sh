#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/frontend"
[ -d node_modules ] || npm ci
exec npm run dev
