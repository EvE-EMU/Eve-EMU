import os

from celery import Celery
from celery.app import trace

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eve_auth.settings.local")

from django.conf import settings

app = Celery("eve_auth")

app.config_from_object("django.conf:settings")
app.conf.broker_connection_retry_on_startup = True

app.conf.broker_transport_options = {
    "priority_steps": list(range(10)),
    "queue_order_strategy": "priority",
}
app.conf.task_default_priority = 5
app.conf.worker_prefetch_multiplier = 1

app.conf.ONCE = {
    "backend": "allianceauth.services.tasks.DjangoBackend",
    "settings": {},
}

app.conf.task_routes = {
    "discord.*": {"queue": "services"},
    "aadiscordbot.tasks.*": {"queue": "aadiscordbot"},
}

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

trace.LOG_SUCCESS = "Task %(name)s[%(id)s] succeeded in %(runtime)ss"
