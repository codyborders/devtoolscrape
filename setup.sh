#!/bin/bash
set -e

# Install Python dependencies system-wide (for CI/agent environments)
pip install --upgrade pip
pip install -r requirements.txt

# Also create venv for local development
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Install Node dependencies (for datadog-ci tooling)
npm install

echo "Setup complete. For local dev, activate venv with: source .venv/bin/activate"
