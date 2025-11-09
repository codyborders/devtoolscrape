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
