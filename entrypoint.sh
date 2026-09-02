#!/bin/sh
set -e
export PYTHONPATH="/app:${PYTHONPATH}"
python -m action.main
