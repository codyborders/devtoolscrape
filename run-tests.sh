#!/bin/bash
# Wrapper script for running tests with correct PYTHONPATH
PYTHONPATH=.packages pytest tests/ "$@"
