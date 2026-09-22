#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 scripts/actualizar.py
python3 scripts/embeber.py
python3 scripts/publicar.py
