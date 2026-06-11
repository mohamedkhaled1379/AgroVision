import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "300"))
accesslog = "-"
errorlog = "-"


def post_fork(server, worker):
    from app import warm_up_models
    server.log.info("Worker %s loading ML models...", worker.pid)
    warm_up_models()
    server.log.info("Worker %s ready.", worker.pid)
