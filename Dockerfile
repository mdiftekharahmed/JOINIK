FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY ./web/requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt
# Add daphne for production (ASGI)
RUN pip install daphne whitenoise

# Copy project
COPY ./web /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Run daphne
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
