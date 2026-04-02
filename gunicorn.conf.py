# Gunicorn configuration file
# Bind to localhost by default so nginx can front requests (and inject RUM) on the public ports.
import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:9000")
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True


def post_fork(server, worker):
    """Reinitialize ddtrace in each worker process.

    With preload_app=True, gunicorn loads the application in the master process
    before forking. ddtrace-run patches the master, but forked workers inherit
    a stale copy that never sends traces. Calling patch_all() after the fork
    ensures each worker has its own live tracer and patched integrations.
    """
    try:
        from ddtrace import patch_all
        patch_all()
    except Exception:
        pass
