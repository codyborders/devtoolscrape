### 2025-11-09T01:40:17Z
- Looked up the latest Datadog Browser SDK release (v6.23.0) via the GitHub API so we could pin the edge proxy to the newest build.
- Updated `/etc/nginx/nginx.conf` to use `datadog_rum_config "v6"`, ran `nginx -t`, and reloaded nginx so the module now serves the v6 script bundle.
- Confirmed `https://devtoolscrape.com` embeds `www.datadoghq-browser-agent.com/us1/v6/datadog-rum.js`, proving the upgrade is live.

### 2025-11-09T01:50:10Z
- Toggled the Datadog nginx module to add `allowedTracingUrls` (pointing at https://devtoolscrape.com) so browser sessions can correlate with backend traces per Datadog’s RUM+tracing guide.
- Validated the config with `nginx -t`, reloaded nginx, and confirmed the rendered HTML now includes `allowedTracingUrls` in the `DD_RUM.init` payload.

### 2025-11-09T02:09:42Z
- Backed out the experimental `allowedTracingUrls` config since the Datadog nginx module only emits strings and the browser SDK complained about the type mismatch.
- Removed the nginx stanza plus the temporary template shim, ran `nginx -t`, reloaded nginx, and confirmed the injected payload no longer includes the unsupported field.
