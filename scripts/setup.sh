#!/bin/bash
set -e

# Install Python dependencies to local .packages directory
# This ensures they persist and are accessible during agent execution
python3 -m pip install --target ./.packages -r requirements.txt

# Also create venv for local development
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# Install Node dependencies (for datadog-ci tooling)
npm install

echo "Setup complete."
echo "For agents: PYTHONPATH=.packages pytest tests/"
echo "For local dev: source .venv/bin/activate"
