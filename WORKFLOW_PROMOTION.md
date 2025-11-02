# Build → Deploy → Promote Workflow

This document captures how code moves from a local machine into the "green" canary, how Datadog evaluates it, and how it’s promoted to the "blue" production stack after a clean run. The process keeps Depot as the only build engine; GitHub Actions just deploys artifacts that already exist in the container registry.

## 1. Local build (Depot only)

1. Make changes locally. When you’re ready to test the canary, build with Depot:
   ```bash
   IMAGE="ghcr.io/<org>/<repo>"
   SHA=$(git rev-parse HEAD)

   depot build \
     --project "$DEPOT_PROJECT_ID" \
     --push \
     --tag "$IMAGE:$SHA" \
     --tag "$IMAGE:green" \
     .
   ```
   This publishes the current commit to GitHub Container Registry under both the immutable SHA tag and the moving `:green` tag.
2. After the Depot build finishes, push the code to GitHub (`git push`). There is **no build step in CI**, so pushing before the Depot build would deploy an old image.

## 2. GitHub Actions: deploy to green only

- A workflow `.github/workflows/deploy-green.yml` triggers on pushes to the branch you want (e.g., `main`).
- The job SSHes into the droplet and runs:
  ```bash
  docker pull ghcr.io/<org>/<repo>:green
  cd /root/devtoolscrape
  docker compose -f docker-compose.blue-green.yml up -d --no-deps web-green
  docker image prune -af
  ```
- The compose file in production has separate services for `web-blue`, `web-green`, and an `router` fronting them.
- Because Depot already pushed `:green`, this step simply updates the green service with the latest image.

## 3. Datadog Synthetic Monitoring

- Create a Datadog Synthetic HTTP test hitting the green version (e.g., a header-based route or dedicated canary URL).
- Set it to run every few minutes and alert on any failure.
- Store the test's public ID for automation. Add `DATADOG_API_KEY` and `DATADOG_APP_KEY` secrets to GitHub so workflows can query historical results.

## 4. Scheduled promotion (24-hour clean run)

- Add a scheduled workflow `.github/workflows/promote-green.yml` with a daily cron.
- The job performs:
  1. Pull Synthetic results for the last 24 hours via Datadog API. If any failure exists, exit without promoting.
  2. If clean, retag the image on the registry:
     ```bash
     docker pull ghcr.io/<org>/<repo>:green
     docker tag ghcr.io/<org>/<repo>:green ghcr.io/<org>/<repo>:blue
     docker tag ghcr.io/<org>/<repo>:green ghcr.io/<org>/<repo>:current   # optional convenience tag
     docker push ghcr.io/<org>/<repo>:blue
     docker push ghcr.io/<org>/<repo>:current
     ```
  3. SSH back into the droplet, pull `:blue`, and restart the blue service:
     ```bash
     docker pull ghcr.io/<org>/<repo>:blue
     cd /root/devtoolscrape
     docker compose -f docker-compose.blue-green.yml up -d --no-deps web-blue
     docker image prune -af
     ```
- Optionally add a step to flip the Nginx/load-balancer config to direct traffic to the new stack (manual or automated).

## 5. Rollback / Manual Controls

- To revert quickly, retag the previous known good image as `:blue` (or `:green`) and rerun the deploy workflow.
- Swapping the router config manually lets you control how fast production traffic shifts to green.
- Local testing remains the same using the Docker compose playground (`docker compose -f docker-compose.local-blue-green.yml up ...`).

## Required Secrets & Environment

| Secret                | Used For                                 |
|-----------------------|------------------------------------------|
| `DEPOT_PROJECT_ID`    | Local build (environment variable)       |
| `DEPOT_TOKEN`         | Local build (environment variable)       |
| `DO_HOST` / `DO_USER`
  `DO_SSH_KEY`          | GitHub Actions SSH deploy steps          |
| `DATADOG_API_KEY`
  `DATADOG_APP_KEY`     | Scheduled promotion workflow             |
| `GITHUB_TOKEN` (auto) | GHCR auth in workflow if needed          |

**Note:** capture the Datadog Synthetic public ID in a repository secret (e.g., `DATADOG_SYNTHETIC_ID`) so the promotion workflow knows which test to query.

## Summary

- **Depot** builds → pushes a `:green` container image.
- **GitHub Actions (deploy)**: `docker compose ... up -d web-green`.
- **Datadog** synthetic test monitors the canary.
- **GitHub Actions (promote)** retags `:green → :blue` and restarts blue only after 24 hours of clean tests.

This gives you automated green deployments, observable canary health, and a one-click promotion path once Datadog certifies the environment.
