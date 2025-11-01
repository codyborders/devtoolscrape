#!/usr/bin/env bash
set -euo pipefail

export DD_SERVICE="devtoolscrape"
export DD_ENV="local"

pytest --ddtrace --ddtrace-patch-all "$@"
