from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
from celery import current_app as celery_app
from celery.exceptions import TimeoutError as CeleryTimeoutError
# from redis.exceptions import ConnectionError as RedisConnectionError # If checking Redis directly via django-redis client
from django.core.cache import caches
from django.conf import settings # To check if cache is enabled

# A simple task to be used for Celery health check, if not using the existing debug_task
# from celery import shared_task
# @shared_task(name="health_check_ping_task", ignore_result=False) # ignore_result=False to get result
# def health_check_ping():
#     return "pong"

def health_check(request):
    status_summary = {}
    http_status_code = 200 # Assume OK initially

    # Check Database Connection
    db_conn_name = 'default' # Check the default database
    db_conn = connections[db_conn_name]
    try:
        # A simple query to check if the database is responsive
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        status_summary[f'database_{db_conn_name}'] = 'ok'
    except OperationalError as e:
        status_summary[f'database_{db_conn_name}'] = f'error - {str(e)}'
        http_status_code = 503
    except Exception as e: # Catch other potential DB connection issues
        status_summary[f'database_{db_conn_name}'] = f'error - unexpected: {str(e)}'
        http_status_code = 503

    # Check Celery Ping (sends a task and waits for a short reply)
    try:
        # Using the existing debug_task from arbitrage_platform.celery
        # Ensure it's configured to return a result or complete quickly if ignore_result=True
        # For a more reliable ping, a dedicated task that returns a value is better.
        # Let's assume debug_task is sufficient for a basic check of broker/worker connectivity.
        # If debug_task has ignore_result=True, .get() will always return None immediately unless it fails to send.
        # To truly test worker responsiveness, a task that returns something is needed.
        # For now, we will test if the task can be sent and if a worker acknowledges it quickly (if not ignore_result)
        # If using debug_task (ignore_result=True), this mainly tests broker connectivity.
        # For a better check: result = celery_app.send_task('health_check_ping_task').get(timeout=3)

        # Let's try sending the existing debug_task. It has ignore_result=True.
        # A more robust check would be a dedicated task that returns a value.
        # For this subtask, we will just attempt to send it.
        # To check worker, we'd need a task that returns something.
        # celery_app.control.ping() is another option but requires more setup for reply.

        # Simplistic check: try to send a task. This mostly checks broker.
        ping_task_result = celery_app.send_task('arbitrage_platform.celery.debug_task', args=[])
        if ping_task_result.id: # Task was accepted by broker
             status_summary['celery_broker'] = 'ok (task sent)'
             # To actually check worker, you'd need a task that returns a result and use .get(timeout=...)
             # For now, we'll assume if broker is ok, and workers *should* be running, it's a basic pass.
             # status_summary['celery_worker_ping'] = 'pending_check_requires_returning_task'
        else:
             status_summary['celery_broker'] = 'error - task could not be sent'
             http_status_code = 503

    except Exception as e:
        status_summary['celery_broker'] = f'error - {str(e)}'
        http_status_code = 503

    # Check Cache Connection (e.g., Redis used for Django Cache)
    try:
        # Check if 'default' cache is configured and not a dummy cache
        if 'default' in settings.CACHES and \
           settings.CACHES['default']['BACKEND'] != 'django.core.cache.backends.dummy.DummyCache':
            default_cache = caches['default']
            cache_key = 'health_check_key'
            cache_value = 'ok_value'
            default_cache.set(cache_key, cache_value, timeout=5)
            if default_cache.get(cache_key) == cache_value:
                status_summary['cache_default'] = 'ok'
                default_cache.delete(cache_key) # Clean up
            else:
                status_summary['cache_default'] = 'error - set/get failed'
                http_status_code = 503
        else:
            status_summary['cache_default'] = 'not_configured_or_dummy'
            # Not necessarily an error state if cache is optional or dummy is intentional for dev

    except Exception as e:
        status_summary['cache_default'] = f'error - {str(e)}'
        http_status_code = 503


    if http_status_code == 200:
        status_summary['overall_status'] = 'ok'
    else:
        status_summary['overall_status'] = 'error'

    return JsonResponse(status_summary, status=http_status_code)
