# Arbitrage Platform - Deployment Guide

This document provides guidance on deploying, managing, and maintaining the Arbitrage Platform in a production environment.

## Table of Contents
1.  [Prerequisites](#prerequisites)
2.  [Environment Configuration](#environment-configuration)
3.  [Building Docker Images](#building-docker-images)
4.  [Running with Docker Compose](#running-with-docker-compose)
5.  [SSL/HTTPS Setup](#sslhttps-setup) (Refer to README.md for detailed SSL/HTTPS strategy)
6.  [Database Migrations](#database-migrations)
7.  [Creating a Superuser](#creating-a-superuser)
8.  [Celery Worker and Beat](#celery-worker-and-beat)
9.  [Static Files](#static-files) (If serving static files directly from Django in prod, not recommended)
10. [Backup Strategy](#backup-strategy)
11. [Recovery Strategy](#recovery-strategy)
12. [Monitoring](#monitoring) (Refer to MONITORING.md for detailed strategy)
13. [Security Hardening](#security-hardening)

*(Sections like Prerequisites, Environment Configuration, etc., would be filled in for a complete guide.)*

## Backup Strategy

A robust backup strategy is essential to prevent data loss and ensure business continuity in case of hardware failure, data corruption, or other disasters.

### 1. PostgreSQL Database

The PostgreSQL database is the primary data store for the application, containing:
- User accounts and credentials (hashed passwords)
- User-configured API keys (encrypted secrets)
- Wallet balances and transaction history
- Tracked exchange pairs and their market data (volume, price, precision rules)
- Arbitrage trade attempts and individual leg details
- User notifications
- Celery Beat schedules (if using `django-celery-beat`)
- Django OTP device registrations

**Recommendations:**
-   **Frequency:** Implement regular, automated backups. Daily backups are a common baseline. More frequent backups (e.g., every few hours or using Point-In-Time Recovery) might be necessary depending on the rate of data change and recovery point objective (RPO).
-   **Method:**
    -   **`pg_dump` / `pg_dumpall`:** Use `pg_dump` for logical backups of individual databases or `pg_dumpall` for the entire PostgreSQL cluster (including users/roles). These backups are human-readable (in plain text format) or can be in a custom format for `pg_restore`. They are flexible but can be slower to restore for very large databases.
        ```bash
        # Example: pg_dump -U <user> -h <host> -Fc <dbname> > <backupfile>.dump
        ```
    -   **Point-In-Time Recovery (PITR):** For more granular recovery, configure PITR by enabling continuous archiving of Write-Ahead Log (WAL) files along with periodic base backups. This allows restoring the database to any specific point in time. Managed cloud database services (AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL) often provide robust and simplified PITR capabilities.
-   **Storage:**
    -   Store backups in a **separate, secure, and off-site location** from the primary database server/cluster. This could be cloud storage (AWS S3, Google Cloud Storage, Azure Blob Storage), a dedicated backup server, or another physically isolated medium.
    -   Encrypt backups, especially if stored in third-party cloud services.
-   **Retention Policy:** Define a clear retention policy based on business needs and compliance requirements. For example:
    -   Keep daily backups for 7-14 days.
    -   Keep weekly backups for 4-8 weeks.
    -   Keep monthly backups for 6-12 months (or longer for archival purposes).
    -   Keep yearly backups for several years if required for compliance.

### 2. Redis Data

Redis is used for:
-   **Celery Broker (e.g., DB 0):** Stores task messages. Data is largely transient.
    -   **Importance:** If tasks are idempotent and can be re-queued upon system recovery, broker data loss might be acceptable. If tasks are critical and non-idempotent, data loss here could mean lost work.
    -   **Strategy:** Enable Redis persistence (RDB snapshots or AOF logging) for the broker database if task persistence is critical. Back up these RDB/AOF files.
-   **Celery Result Backend (e.g., DB 1, if used):** Stores task results.
    -   **Importance:** Depends on how critical retaining task results is. If results are short-lived or only for informational purposes, this might be less critical than broker data.
    -   **Strategy:** Similar to the broker, enable Redis persistence and back up RDB/AOF files if results are important.
-   **Django Cache (e.g., DB 2):** Stores cached market data (like pair volumes/prices).
    -   **Importance:** Cache data is generally ephemeral and can be rebuilt by the application.
    -   **Strategy:** Backing up cache data is usually **not a priority**. The application should be designed to repopulate the cache as needed after a Redis restart or data loss.

**Redis Backup Method (if persistence is enabled):**
-   If RDB snapshots are used, back up the `.rdb` file.
-   If AOF logging is used, back up the AOF file(s).
-   Store these backups securely, similar to database backups.

### 3. Docker Volumes

-   **`postgres_data`:** This named volume holds the actual PostgreSQL data files.
    -   **Strategy:** The primary way to back this up is via the PostgreSQL-specific methods (`pg_dump`, PITR) mentioned above, which operate on the live or properly shut down database. Directly backing up the volume's raw files is possible but requires stopping the database container to ensure data consistency, or using filesystem-level snapshotting if the underlying storage supports it and is configured for database consistency.
-   **`redis_data`:** If Redis persistence is enabled, this volume holds the RDB/AOF files.
    -   **Strategy:** Similar to `postgres_data`, this can be backed up by copying the RDB/AOF files from the volume (ideally after a `BGSAVE` or ensuring AOF is synced), or by backing up the volume itself (Redis should ideally be stopped or `SAVE` command issued before filesystem copy for RDB consistency).
-   **Other Volumes:** Identify any other Docker volumes that might be used to store persistent application data (e.g., user-uploaded files, logs if not sent to stdout/stderr). Currently, no other critical stateful volumes are defined in `docker-compose.yml`.

### 4. Application Code & Configuration
-   **Application Code:** The Django application code (including all Python files, templates, static assets defined within the project) should be stored in a **version control system (e.g., Git)**. Regular pushes to a remote repository (e.g., GitHub, GitLab, Bitbucket) serve as a backup of the codebase.
-   **Environment Variables & Deployment Configurations:**
    -   Sensitive information (database passwords, `DJANGO_SECRET_KEY`, API keys for external services) should be managed as environment variables, **not hardcoded in `settings.py` or committed to the Git repository.**
    -   The `.env` file containing these secrets for a specific deployment environment must be **backed up securely and kept private**.
    -   Deployment configurations (e.g., `docker-compose.prod.yml`, Nginx configuration files, systemd service files, Kubernetes manifests) should also be version-controlled or securely backed up.

## Recovery Strategy (Conceptual)

A well-defined recovery strategy is essential to restore service quickly and reliably. This strategy should be documented thoroughly and tested periodically.

### 1. Database Recovery (PostgreSQL)
-   **From `pg_dump`:**
    1.  Set up a new PostgreSQL instance (or clean the existing one).
    2.  Create the database and user with appropriate permissions if not already existing.
    3.  Use `pg_restore` (for custom/tar formats) or `psql` (for plain SQL dumps) to import the data from the backup file.
        ```bash
        # Example: pg_restore -U <user> -d <dbname> -h <host> <backupfile>.dump
        # Example: psql -U <user> -d <dbname> -h <host> -f <backupfile>.sql
        ```
-   **Using PITR:**
    1.  Restore the base backup to a new PostgreSQL instance.
    2.  Configure `recovery.conf` (or equivalent in newer PostgreSQL versions) to specify the restore command for WAL files from the archive.
    3.  Start PostgreSQL, which will enter recovery mode and replay WAL files up to the desired point in time.
-   **Post-Recovery:**
    -   Verify data integrity and consistency.
    -   Update database connection strings in the application configuration if the database host or credentials have changed.

### 2. Redis Recovery
-   **From RDB/AOF Files:**
    1.  Ensure the Redis server is stopped.
    2.  Replace the existing (or empty) RDB/AOF files in the Redis data directory (e.g., the `redis_data` Docker volume) with the backup files.
    3.  Restart the Redis server. It will load data from these files.
-   **Cache Rebuilding:** If Redis was primarily used for caching (e.g., Django cache on DB 2), data loss might be acceptable. The application should be able to rebuild the cache over time as data is requested or background tasks repopulate it. Ensure Celery tasks that rely on broker data are either idempotent or can be safely re-queued if the broker state (DB 0) is lost and not recovered.

### 3. Application Redeployment (Django App, Celery Workers, Beat)
1.  **Infrastructure:** Ensure the necessary server infrastructure (VMs, Kubernetes cluster, etc.) is available.
2.  **Code Deployment:**
    -   Clone the application code from the Git repository (to a specific release tag or commit).
    -   Rebuild Docker images if they are not available in a container registry: `docker-compose build web celery_worker celery_beat`.
3.  **Configuration:**
    -   Restore the backed-up environment variables (`.env` file or inject them from a secure secret management system) into the deployment environment.
    -   Ensure `docker-compose.yml` (or other orchestration manifests) are correctly configured.
4.  **Service Startup:**
    -   Start the database and Redis services first and ensure they are healthy.
    -   Run Django database migrations: `docker-compose exec web python manage.py migrate`.
    -   Start the Django web application (Gunicorn), Celery workers, and Celery Beat services: `docker-compose up -d web celery_worker celery_beat`.
5.  **Post-Recovery Steps:**
    -   Create a superuser if needed: `docker-compose exec web python manage.py createsuperuser`.
    -   Run any necessary data seeding or re-initialization scripts (e.g., `update_all_exchange_pairs` Celery task).

### 4. Testing Recovery Procedures
-   **Regular Drills:** Periodically test the entire backup and recovery process in a non-production environment. This is crucial to identify issues with the backup files, recovery steps, or configurations.
-   **Documentation Review:** Keep the recovery plan documentation up-to-date with any changes in the application architecture or infrastructure.
-   **RPO/RTO Goals:** Ensure the recovery procedures can meet the defined Recovery Point Objective (RPO - maximum acceptable data loss) and Recovery Time Objective (RTO - maximum acceptable downtime).

This strategy provides a conceptual framework. Specific implementation details will depend on the chosen hosting environment, tools, and business requirements.
