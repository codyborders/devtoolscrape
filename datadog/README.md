# Datadog Log Collection

Follow these steps to ship DevTools Scraper JSON logs to Datadog using the Agent:

1. **Enable log collection in the Agent**
   - Edit `/etc/datadog-agent/datadog.yaml` and ensure `logs_enabled: true`.
   - Restart the Agent after making changes: `sudo systemctl restart datadog-agent`.

2. **Install the DevTools Scraper log configuration**
   - Copy the provided config into the Agent's `conf.d` directory:
     ```bash
     sudo mkdir -p /etc/datadog-agent/conf.d/devtoolscrape.d
     sudo cp datadog/conf.d/devtoolscrape.d/conf.yaml /etc/datadog-agent/conf.d/devtoolscrape.d/conf.yaml
     sudo systemctl restart datadog-agent
     ```
   - The file instructs the Agent to tail the structured JSON logs emitted to `/var/log/devtoolscrape/*.log`.

3. **Verify ingestion**
   - Run the Agent status command (`sudo datadog-agent status`) and look under *Logs Agent* to confirm the tailer is running.
   - Within the Datadog UI, navigate to *Logs Explorer* and filter by `service:devtoolscrape`.

The application already tags logs with `service=devtoolscrape` and `env` (default `local`). Adjust the `tags` or file glob in `conf.yaml` if you deploy to multiple environments or rotate logs differently.
