#!/bin/sh
# Run MISH on your own computer: open a terminal in this folder and run  sh START-MAC-LINUX.sh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  python3 run_local.py
else
  echo "Python 3 is not installed. Download it from https://www.python.org/downloads/"
fi
