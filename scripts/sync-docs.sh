#!/bin/bash
# 同步 static/index.html -> docs/index.html (DEMO 模式)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC="$ROOT_DIR/static/index.html"
DST="$ROOT_DIR/docs/index.html"
if [ ! -f "$SRC" ]; then echo "ERROR: $SRC not found"; exit 1; fi
sed 's|<head>|<head>\n  <meta name="demo" content="true">|' "$SRC" > "$DST"
echo "Synced: $SRC -> $DST ($(wc -c < "$DST") bytes)"
