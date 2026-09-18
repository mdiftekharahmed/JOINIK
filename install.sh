#!/bin/bash
set -e

# ==============================================================================
# JOINIK Automated Installation Script
# This script installs Docker and Docker Compose (if missing), clones the 
# repository, prompts for necessary credentials, generates the .env file, 
# and deploys the application.
# ==============================================================================

echo "================================================================="
echo "                  JOINIK Automated Setup                         "
echo "================================================================="

# 1. Install Docker and Docker Compose if missing
if ! command -v docker &> /dev/null; then
    echo "[*] Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "[+] Docker installed."
else
    echo "[+] Docker is already installed."
fi

if ! docker compose version &> /dev/null; then
    echo "[*] Docker Compose plugin not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    echo "[+] Docker Compose plugin installed."
else
    echo "[+] Docker Compose is already installed."
fi

# 2. Clone the repository
REPO_URL="https://github.com/mdiftekharahmed/JOINIK.git"
INSTALL_DIR="$HOME/JOINIK"

if [ -d "$INSTALL_DIR" ]; then
    echo "[*] Directory $INSTALL_DIR already exists. Pulling latest changes..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "[*] Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 3. Create .env file with user prompts
ENV_FILE="web/.env"
echo "[*] Configuring the environment..."

# Generate a random secret key if one doesn't exist
SECRET_KEY=$(head -c 32 /dev/urandom | base64)

# Prompt for interactive configuration
read -p "Enter PostgreSQL Database Name for JOINIK [default: joinik]: " DB_NAME
DB_NAME=${DB_NAME:-joinik}

read -p "Enter PostgreSQL User [default: postgres]: " DB_USER
DB_USER=${DB_USER:-postgres}

read -sp "Enter PostgreSQL Password [default: postgres]: " DB_PASSWORD
echo ""
DB_PASSWORD=${DB_PASSWORD:-postgres}

# We assume ThingsBoard DB is local or provide IP
read -p "Enter ThingsBoard Host IP (where ThingsBoard is hosted) [default: 100.82.190.70]: " TB_HOST
TB_HOST=${TB_HOST:-100.82.190.70}

read -p "Enter ThingsBoard REST API Admin Email [default: sysadmin@thingsboard.org]: " TB_ADMIN_EMAIL
TB_ADMIN_EMAIL=${TB_ADMIN_EMAIL:-sysadmin@thingsboard.org}

read -sp "Enter ThingsBoard REST API Admin Password: " TB_ADMIN_PASSWORD
echo ""

echo "[*] Writing configuration to $ENV_FILE..."
cat <<EOF > "$ENV_FILE"
# ── Core Django Settings ──
DEBUG=False
SECRET_KEY=$SECRET_KEY

# ── Django Database (Local JOINIK State) ──
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=host.docker.internal
DB_PORT=5432

# ── ThingsBoard Database (Read-Only Telemetry) ──
TB_DB_NAME=thingsboard
TB_DB_USER=postgres
TB_DB_PASSWORD=postgres
TB_DB_HOST=$TB_HOST
TB_DB_PORT=5432

# ── ThingsBoard REST API ──
TB_URL=http://$TB_HOST:8080
TB_ADMIN_EMAIL=$TB_ADMIN_EMAIL
TB_ADMIN_PASSWORD=$TB_ADMIN_PASSWORD

# ── Redis / Celery Broker ──
REDIS_URL=redis://redis:6379/0

# ── Pre-seeded Devices ──
JOINIK_MODULE_01_TB_ID=432bd840-b20a-11f1-be96-b92a8fbab147
EOF

echo "[+] Configuration saved!"

# 4. Run Docker Compose
echo "[*] Building and starting Docker containers..."
sudo docker compose up -d --build

# 5. Run Database Migrations
echo "[*] Running database migrations..."
sudo docker compose exec -T web python manage.py migrate

echo "================================================================="
echo "                INSTALLATION COMPLETE!                           "
echo "================================================================="
echo "You can access the application at http://localhost:8000"
echo "To create an admin superuser, run:"
echo "  sudo docker compose exec web python manage.py createsuperuser"
echo "================================================================="
