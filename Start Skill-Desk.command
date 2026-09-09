#!/bin/zsh
cd -- "${0:A:h}"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python scripts/skill_desk.py
fi
exec python3 scripts/skill_desk.py
