#!/usr/bin/env bash
set -euo pipefail

export DD_SERVICE="devtoolscrape"
export DD_ENV="local"
export DD_PYTEST_USE_NEW_PLUGIN_BETA=true

ddtrace-run pytest "$@"
