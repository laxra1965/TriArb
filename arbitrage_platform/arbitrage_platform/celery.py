import os
from celery import Celery
from celery.schedules import crontab # Needs to be imported

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arbitrage_platform.settings')

app = Celery('arbitrage_platform')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Celery Beat Schedules
app.conf.beat_schedule = {
    'update-all-exchange-pairs-every-6-hours': {
        'task': 'market_data.tasks.update_all_pairs_from_exchanges_task',
        'schedule': crontab(minute=0, hour='*/6'), # Every 6 hours
    },
    'schedule-active-pair-volume-updates-every-15-minutes': {
        'task': 'market_data.tasks.schedule_all_active_pair_volume_updates_task',
        'schedule': crontab(minute='*/15'), # Every 15 minutes
        # Args or kwargs for the task can be added here if needed
    },
}
