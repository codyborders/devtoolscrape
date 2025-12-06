#!/bin/bash

# Build script for devtoolscrape
echo "Building devtoolscrape Docker image..."

DD_GIT_REPOSITORY_URL="$(git config --get remote.origin.url)"
DD_GIT_COMMIT_SHA="$(git rev-parse HEAD)"

# Stop and remove existing container
docker stop devtoolscrape 2>/dev/null || true
docker rm devtoolscrape 2>/dev/null || true

# Build with no cache to ensure all changes are included
docker build --no-cache \\
  --build-arg "DD_GIT_REPOSITORY_URL=${DD_GIT_REPOSITORY_URL}" \\
  --build-arg "DD_GIT_COMMIT_SHA=${DD_GIT_COMMIT_SHA}" \\
  -t devtoolscrape .

# Start the container
docker run -d --name devtoolscrape -p 8000:8000 devtoolscrape

echo "Build complete! Container started on port 8000"
echo "Access the app at: http://localhost:8000" 
