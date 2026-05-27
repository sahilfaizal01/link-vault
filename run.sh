#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d ../venv ]]; then
  python3 -m venv .venv
fi

if [[ -d ../venv ]]; then
  source ../venv/bin/activate
elif [[ -d .venv ]]; then
  source .venv/bin/activate
fi

pip install -q -r requirements.txt
python -m backend.main
