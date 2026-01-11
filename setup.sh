#!/bin/bash
set -e

# Install Python dependencies system-wide (for CI/agent environments)
# Use python3 -m pip to ensure we install to the correct Python
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Also create venv for local development
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# Install Node dependencies (for datadog-ci tooling)
npm install

echo "Setup complete. For local dev, activate venv with: source .venv/bin/activate"
