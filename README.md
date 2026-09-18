# JOINIK — IoT Security Platform

JOINIK is a modular, AI-augmented IoT security platform. It integrates directly with ThingsBoard, providing a real-time dashboard, AI risk assessment, and alarm management system built with Django and Celery.

---

## Architecture

- **Web Application**: Django served by Gunicorn and Whitenoise.
- **Task Queue**: Celery handles asynchronous tasks like AI model execution and event processing.
- **Broker / Cache**: Redis is used for Celery message brokering, caching, and Django Channels (WebSocket).
- **Databases**: 
  - Local PostgreSQL for Django's application state (users, alarms, risk assessments).
  - External ThingsBoard PostgreSQL for reading real-time telemetry data.

---

## Prerequisites

Before installing the system, ensure you have the following installed on your host machine / Virtual Machine:

- **Git**
- **Docker**
- **Docker Compose**

---

## Configuration (.env)

The application is configured using a `.env` file located in the `web/` directory.

1. Navigate to the `web` folder:
   ```bash
   cd web
   ```
2. Create or edit the `.env` file based on your environment. Below is a template you can copy and paste:

```env
# ── Core Django Settings ──
DEBUG=False
SECRET_KEY=<your-secure-production-secret-key-here>

# ── Django Database (Local JOINIK State) ──
DB_NAME=<joinik_db_name>
DB_USER=<db_user>
DB_PASSWORD=<db_password>
DB_HOST=<db_host_ip_or_container_name>
DB_PORT=5432

# ── ThingsBoard Database (Read-Only Telemetry) ──
TB_DB_NAME=<thingsboard_db_name>
TB_DB_USER=<tb_db_user>
TB_DB_PASSWORD=<tb_db_password>
TB_DB_HOST=<thingsboard_host_ip>
TB_DB_PORT=5432

# ── ThingsBoard REST API ──
TB_URL=http://<thingsboard_host_ip>:8080
TB_ADMIN_EMAIL=<sysadmin@yourdomain.com>
TB_ADMIN_PASSWORD=<tb_admin_password>

# ── Redis / Celery Broker ──
# If using the Redis container from docker-compose, use: redis://redis:6379/0
REDIS_URL=redis://<redis_host_ip>:6379/0

# ── Pre-seeded Devices ──
JOINIK_MODULE_01_TB_ID=<device_uuid_from_thingsboard>
```

> **Note:** Ensure `DEBUG` is strictly set to `False` in production environments for security and to allow Whitenoise to properly serve static files.

---

## Installation & Deployment

You can deploy the JOINIK platform automatically using the provided one-liner installation script, or manually step-by-step.

### Option 1: Automated One-Liner Installation (Recommended)

Run the following command on your target Virtual Machine (e.g., Ubuntu/Debian). This script will automatically install Docker/Docker Compose (if missing), clone the repository, prompt you for the necessary database/ThingsBoard credentials, configure your `.env` file, and start the application.

```bash
curl -fsSL https://raw.githubusercontent.com/mdiftekharahmed/JOINIK/main/install.sh | bash
```

*(Note: The script might ask for `sudo` privileges during the installation of Docker or Docker Compose).*

---

### Option 2: Manual Installation Roadmap

If you prefer to configure everything manually, follow this roadmap:

#### 1. Clone the Repository

Clone the project onto your target Virtual Machine or host environment:

```bash
git clone https://github.com/mdiftekharahmed/JOINIK.git
cd JOINIK
```

#### 2. Configure your Environment

Copy the `.env` template below or from the Configuration section above into `web/.env`, and populate it with your specific credentials:

```bash
# Example: Using nano to create the file
nano web/.env
```

#### 3. Build and Start the Docker Containers

The provided `docker-compose.yml` file builds the Django web application and the Celery worker, linking them to the internal Redis container.

Run the following command to build the images and start the services in detached mode:

```bash
docker compose up -d --build
```

#### 4. First-time Setup (Migrations & Superuser)

If this is the first time you are deploying the application, apply the database migrations:

```bash
docker compose exec web python manage.py migrate
```

Finally, create an admin user to access the dashboard:

```bash
docker compose exec web python manage.py createsuperuser
```
*(Follow the prompts to enter an email, username, and password).*

---

## Management & Maintenance

### Viewing Logs

To view logs for all services in real-time:
```bash
docker-compose logs -f
```
To view logs for a specific service (e.g., the Celery worker):
```bash
docker-compose logs -f celery_worker
```

### Stopping the System

To stop the running containers without deleting them:
```bash
docker-compose stop
```

To take down the containers, network, and associated volumes (useful for a clean restart):
```bash
docker-compose down
```

### Updating the Application

When a new version of the code is pushed to GitHub, you can update your deployment with:

```bash
# Pull the latest changes
git pull origin main

# Rebuild and restart the containers
docker-compose up -d --build

# Run any new migrations
docker-compose exec web python manage.py migrate
```

---

## License

MIT License
