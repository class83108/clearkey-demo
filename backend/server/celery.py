import os

from celery import Celery
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

# Create a new Celery instance
app = Celery("server", broker=settings.CELERY_BROKER_URL)

# use a string here - meaning the worker doesn't have to serialize
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# 記憶體優化配置 - 其他配置已移至 settings.py 統一管理
app.conf.update(
    # 任務執行優化
    task_always_eager=False,
    task_store_eager_result=False,
)