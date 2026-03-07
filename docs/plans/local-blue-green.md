# Local Blue/Green Playground

The repository now ships with a self-contained Docker Compose topology so you can exercise the “blue” (baseline) and “green” (experimental) stacks side-by-side on your laptop.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- `.env` file in the project root (same one you use for normal runs)

## Start the environment

```bash
docker compose -f docker-compose.local-blue-green.yml up --build -d
# router listens on http://localhost:8080
```

This launches:

| Service  | Description                         | Internal Port | Notes                                |
|----------|-------------------------------------|---------------|--------------------------------------|
| web-blue | Baseline stack (current main)       | 8000          | Logs under `./logs/blue/`            |
| web-green| Experimental stack (feature branch) | 8000          | Logs under `./logs/green/`           |
| router   | Nginx reverse proxy                 | 80 -> 8080    | Exposes `localhost:8080` to browser  |

Both app containers mount the source tree, so any local code changes are reflected immediately after a restart.

## Swap active stack

The router mounts a mutable config file (`deploy/nginx/local/default.conf`). Use the helper script to point traffic at the desired stack:

```bash
./scripts/local_switch_stack.sh blue   # default
./scripts/local_switch_stack.sh green  # switch to green
```

The script copies the appropriate template (`default.conf.<color>`) into place and reloads Nginx inside the router container.

## Tear down

```bash
docker compose -f docker-compose.local-blue-green.yml down
```

By design this setup is isolated from the production Compose file—you can safely experiment without touching live deployments.
