#!/usr/bin/bash

SCRIPT_DIR=$(dirname -- "${BASH_SOURCE[0]}")
cd $SCRIPT_DIR
pyreverse -o png ../note.py

sphinx-build -b html . html
