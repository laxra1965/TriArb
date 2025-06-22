# Monitoring Strategy for Arbitrage Platform

A robust monitoring strategy is crucial for maintaining the health, performance, and reliability of the Arbitrage Platform in a production environment. This document outlines key areas and metrics to monitor for each component of the system.

## 1. Key Metrics to Monitor per Service

### Django Web Application (Gunicorn)
-   **Request Rate & API Latency:** Track the number of requests per second/minute and the average/p95/p99 latency for key API endpoints (e.g., `/api/scanner/opportunities/`, `/api/trading/execute/`, auth endpoints). This helps identify performance bottlenecks and usage patterns.
-   **Error Rates:** Monitor HTTP 4xx (client errors) and 5xx (server errors) rates. High 5xx rates indicate application issues.
-   **Worker Performance:**
    -   CPU and Memory Utilization of Gunicorn worker processes.
    -   Number of active vs. idle workers.
    -   Restart frequency of worker processes.
-   **Database Interaction:**
    -   Database connection pool usage (if applicable via PgBouncer or similar).
    -   Average query latency from Django to the database.
    -   Rate of database errors (e.g., connection errors, timeouts).
-   **Application-Specific Metrics:**
    -   Number of arbitrage opportunities identified per scan.
    -   Number of trade execution attempts (success, failure, partial).

### Celery Workers
-   **Task Queue Length:** Monitor the length of Celery queues (e.g., default queue, and any other specialized queues). A continuously growing queue indicates workers cannot keep up.
-   **Number of Active/Idle Workers:** Track the number of Celery worker processes and their status.
-   **Task Success/Failure Rates:** Monitor the rate of successful vs. failed tasks. High failure rates need investigation.
-   **Task Execution Time:** Track average, p95, and p99 execution times for critical tasks (e.g., `update_single_pair_volume_task`, `trade_execution_task` if it becomes async).
-   **Task Retry Rates:** If tasks are configured to retry, monitor the retry rate.
-   **Resource Utilization:** CPU and Memory utilization of Celery worker processes.

### Celery Beat Scheduler
-   **Process Health:** Ensure the Celery Beat process is running.
-   **Scheduling Accuracy:** Verify that scheduled tasks are being enqueued at the correct intervals (indirectly monitored by checking queue lengths and task execution logs for periodic tasks).
-   **Missed Ticks:** Some Celery monitoring tools can report if Beat misses schedule ticks.

### PostgreSQL Database (`db` service)
-   **System Resources:** CPU utilization, memory usage, disk I/O, available disk space.
-   **Connections:** Number of active connections, idle connections, connection limits.
-   **Query Performance:** Average query latency, identification of slow queries, index hit rate.
-   **Replication:** If using read replicas, monitor replication lag and status.
-   **Database-Specific Metrics:** Transaction rates, deadlocks, cache hit rates.

### Redis (`redis` service - for Celery Broker, Cache, Channels)
-   **System Resources:** CPU utilization, memory usage (especially important if Redis is used for more than just transient data).
-   **Connections:** Number of connected clients, rejected connections (if maxclients is reached).
-   **Command Latency:** Average latency for Redis commands.
    -   **Cache Performance:** Cache hit/miss ratio for the Django cache backend (DB 2).
-   **Broker Performance (Celery - DB 0):** Number of messages in queues (can be seen via Celery tools or Redis directly), memory used by broker queues.
-   **Channels Layer (Celery - DB an alternative, or same Redis instance DB different from broker):** Message rates, group memberships, channel layer backend health.
-   **Persistence:** If RDB snapshots or AOF persistence is enabled, monitor success/failure of these operations and disk space used.

## 2. Logging Aggregation

-   **Centralization:** All logs from Django (Gunicorn stdout/stderr), Celery workers (stdout/stderr), Celery Beat (stdout/stderr), and potentially PostgreSQL/Redis should be centralized.
-   **Tools:** Utilize tools like:
    -   **ELK Stack (Elasticsearch, Logstash, Kibana):** Powerful for searching, analyzing, and visualizing logs.
    -   **Grafana Loki:** A horizontally-scalable, highly-available, multi-tenant log aggregation system inspired by Prometheus.
    -   **Splunk:** Commercial log aggregation and analysis platform.
    -   **Cloud Provider Solutions:** AWS CloudWatch Logs, Google Cloud Logging, Azure Monitor Logs.
-   **Structured Logging:** Using JSON-formatted logs (as configured with `python-json-logger` in Django/Celery) makes parsing and analysis much more effective in these tools.

## 3. Alerting

Set up alerts for critical conditions to ensure prompt attention and resolution. Examples:
-   **High Error Rates:** Sustained 5xx errors on web or API endpoints.
-   **Service Unavailability:** `/healthz/` endpoint failing, Docker container healthchecks failing.
-   **Resource Exhaustion:** High CPU/memory/disk on any service (web, workers, DB, Redis).
-   **Long Celery Queues:** Task queues growing beyond a defined threshold for an extended period.
-   **High Task Failure Rate:** Celery tasks failing frequently.
-   **Database Issues:** High query latency, excessive connections, low disk space.
-   **Redis Issues:** High memory usage, connection problems.
-   **Business Logic Metrics:** E.g., no successful trades for X hours, critical failure in commission deduction.

## 4. Tools (Examples)

-   **APM (Application Performance Monitoring):**
    -   **Sentry:** Excellent for error tracking and performance monitoring in Django/Celery.
    -   New Relic, Datadog, Dynatrace: Comprehensive commercial APM solutions.
-   **Metrics Collection & Visualization:**
    -   **Prometheus:** Time-series database for metrics. Django/Celery can expose metrics via exporters (e.g., `django-prometheus`, Celery exporters).
    -   **Grafana:** For visualizing metrics from Prometheus and other sources.
-   **Log Management:** (As mentioned above: ELK, Loki, Splunk, Cloud solutions).
-   **Health Checks:**
    -   The `/healthz/` endpoint created in Django.
    -   Docker built-in healthchecks in `docker-compose.yml`.
    -   External uptime monitoring services (e.g., UptimeRobot, Pingdom).

A combination of these strategies and tools will provide good visibility into the production state of the Arbitrage Platform. Start with essential logging and health checks, then gradually add more sophisticated metrics and APM as needed.
