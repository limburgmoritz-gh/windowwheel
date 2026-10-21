#!/bin/zsh
# Startet WindowWheel aus dem Quellcode (virtuelle Umgebung in .venv).
cd "$(dirname "$0")"
exec .venv/bin/python -m windowwheel "$@"
