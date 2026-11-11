# Gunicorn settings read automatically from the working directory.
# Before a worker stops (deploy, restart, free server going to sleep) save anything still queued in memory
# by low-database mode (app/lowdb.py).


def worker_exit(server, worker):
    try:
        from app import lowdb
        lowdb.flush_all()
    except Exception:  # pragma: no cover
        pass
    try:
        # free hosting without a permanent disk: save accounts and settings to the private GitHub copy
        from app import persist
        persist.push_all_on_exit()
    except Exception:  # pragma: no cover
        pass
