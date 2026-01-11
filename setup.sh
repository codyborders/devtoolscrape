#!/bin/bash
set -e

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Node dependencies (for datadog-ci tooling)
npm install

echo "Setup complete. Activate the virtual environment with: source .venv/bin/activate"
