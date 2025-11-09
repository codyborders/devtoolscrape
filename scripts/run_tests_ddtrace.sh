#!/usr/bin/env bash
set -euo pipefail

export DD_SERVICE="devtoolscrape"
export DD_ENV="local"
export DD_PYTEST_USE_NEW_PLUGIN_BETA=true
export DD_CIVISIBILITY_INTELLIGENT_TEST_RUNNER_ENABLED=false
export DD_CIVISIBILITY_EARLY_FLAKE_DETECTION_ENABLED=false
export DD_CIVISIBILITY_AUTO_TEST_RETRIES_ENABLED=false
export DD_CIVISIBILITY_TEST_SKIPPING_ENABLED=false
export DD_REMOTE_CONFIGURATION_ENABLED=false

pytest --ddtrace --ddtrace-patch-all "$@"
