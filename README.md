# JOINIK — IoT Security Platform

JOINIK is a modular, AI-augmented IoT security platform. It integrates directly with ThingsBoard, providing a real-time dashboard, AI risk assessment, and alarm management system built with Django and Celery.

## Prerequisites

- **Docker** and **Docker Compose**
- Redis (Running on VM or via Compose)
- PostgreSQL (ThingsBoard Database and local JOINIK database)

## Deployment via Docker Compose

1. Clone this repository on your VM:
   ```bash
   git clone https://github.com/mdiftekharahmed/JOINIK.git
   cd JOINIK
   ```

2. Configure Environment Variables:
   Update the `web/.env` file with your production database credentials, ThingsBoard details, and ensure `DEBUG=False`.
   ```env
   DEBUG=False
   SECRET_KEY=your-production-secret-key
   # Add your database and TB connection string details here...
   ```

3. Build and Run the Services:
   ```bash
   docker-compose up -d --build
   ```

4. Apply Database Migrations and Create Superuser (First run only):
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

## Architecture

- **Web Service**: Gunicorn serving the Django WSGI application on port 8000. Static files are served efficiently via Whitenoise.
- **Celery Worker**: Background task processing for AI risk scoring and notifications.
- **Redis**: Message broker and caching layer (configured in `.env`).

## License
MIT License
