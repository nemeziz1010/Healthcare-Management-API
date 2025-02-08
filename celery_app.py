from celery import Celery


def get_celery_app():
    return Celery()

celery = Celery(
    "fastapi-ehr",
    broker="redis://localhost:6379/0",  # Ensure Redis is running on this port
    backend="redis://localhost:6379/0",
    include=["tasks"],  # Make sure "tasks.py" exists in the same directory
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)

if __name__ == "__main__":
    celery.worker_main()
