# Gunicorn settings read automatically from the working directory.
# Before a worker stops (deploy, restart, free server going to sleep) save anything still queued in memory
# by low-database mode (app/lowdb.py).


def worker_exit(server, worker):
    try:
        from app import lowdb
        lowdb.flush_all()
    except Exception:  # pragma: no cover
        pass


# Recycle a worker periodically to cap gradual memory growth on the 512 MB Free instance.
# lowdb.flush_all() in worker_exit persists queued analytics before the worker is replaced.
max_requests = 500
max_requests_jitter = 50
