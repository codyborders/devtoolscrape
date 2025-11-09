### 2025-11-09T01:40:17Z
- Looked up the latest Datadog Browser SDK release (v6.23.0) via the GitHub API so we could pin the edge proxy to the newest build.
- Updated `/etc/nginx/nginx.conf` to use `datadog_rum_config "v6"`, ran `nginx -t`, and reloaded nginx so the module now serves the v6 script bundle.
- Confirmed `https://devtoolscrape.com` embeds `www.datadoghq-browser-agent.com/us1/v6/datadog-rum.js`, proving the upgrade is live.
