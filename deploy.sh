#!/bin/bash

##############################################################################
# Family Hub Deployment Script
# Automatisiertes Deployment auf Proxmox LXC Container
##############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_ID=145  # Ändere wenn du anderen Container verwendest
INSTALL_DIR="/opt/family-hub"
SERVICE_NAME="familyhub"

echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Family Hub Deployment Script      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# Check if running on Proxmox host
if ! command -v pct &> /dev/null; then
    echo -e "${RED}Fehler: Dieses Script muss auf dem Proxmox Host ausgeführt werden!${NC}"
    exit 1
fi

# Check if container exists
if ! pct status $CONTAINER_ID &> /dev/null; then
    echo -e "${RED}Fehler: Container $CONTAINER_ID existiert nicht!${NC}"
    echo -e "${YELLOW}Möchtest du den Container jetzt erstellen? (y/n)${NC}"
    read -r response
    if [[ "$response" == "y" ]]; then
        echo "Container-Erstellung wird noch nicht unterstützt. Bitte manuell erstellen."
        exit 1
    fi
    exit 1
fi

echo -e "${GREEN}✓${NC} Container $CONTAINER_ID gefunden"

# Check if container is running
if ! pct status $CONTAINER_ID | grep -q "running"; then
    echo -e "${YELLOW}Container wird gestartet...${NC}"
    pct start $CONTAINER_ID
    sleep 5
fi

echo -e "${GREEN}✓${NC} Container läuft"

# Install dependencies in container
echo -e "${YELLOW}Installiere Dependencies im Container...${NC}"
pct exec $CONTAINER_ID -- bash -c "apt update && apt install -y python3 python3-pip python3-venv git curl"

# Create installation directory
echo -e "${YELLOW}Erstelle Installationsverzeichnis...${NC}"
pct exec $CONTAINER_ID -- mkdir -p $INSTALL_DIR

# Copy files to container
echo -e "${YELLOW}Kopiere Dateien in Container...${NC}"
pct push $CONTAINER_ID . $INSTALL_DIR -r

# Setup Python virtual environment
echo -e "${YELLOW}Richte Python Virtual Environment ein...${NC}"
pct exec $CONTAINER_ID -- bash -c "cd $INSTALL_DIR/backend && python3 -m venv venv"

# Install Python packages
echo -e "${YELLOW}Installiere Python Packages...${NC}"
pct exec $CONTAINER_ID -- bash -c "cd $INSTALL_DIR/backend && venv/bin/pip install -r requirements.txt"

# Check if .env exists, if not copy from example
echo -e "${YELLOW}Prüfe Konfiguration...${NC}"
pct exec $CONTAINER_ID -- bash -c "
    if [ ! -f $INSTALL_DIR/backend/.env ]; then
        echo 'Kopiere .env.example zu .env'
        cp $INSTALL_DIR/backend/.env.example $INSTALL_DIR/backend/.env
        echo '${YELLOW}ACHTUNG: Bitte .env Datei bearbeiten und Keys eintragen!${NC}'
    fi
"

# Create systemd service
echo -e "${YELLOW}Erstelle Systemd Service...${NC}"
pct exec $CONTAINER_ID -- bash -c "cat > /etc/systemd/system/${SERVICE_NAME}.service << 'EOF'
[Unit]
Description=Family Hub FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/backend
Environment=\"PATH=${INSTALL_DIR}/backend/venv/bin\"
ExecStart=${INSTALL_DIR}/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
"

# Reload systemd
echo -e "${YELLOW}Lade Systemd neu...${NC}"
pct exec $CONTAINER_ID -- systemctl daemon-reload

# Enable and start service
echo -e "${YELLOW}Aktiviere und starte Service...${NC}"
pct exec $CONTAINER_ID -- systemctl enable $SERVICE_NAME
pct exec $CONTAINER_ID -- systemctl restart $SERVICE_NAME

# Wait for service to start
sleep 3

# Check service status
if pct exec $CONTAINER_ID -- systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Service erfolgreich gestartet!${NC}"
else
    echo -e "${RED}✗ Service konnte nicht gestartet werden!${NC}"
    pct exec $CONTAINER_ID -- systemctl status $SERVICE_NAME
    exit 1
fi

# Get container IP
CONTAINER_IP=$(pct exec $CONTAINER_ID -- hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Deployment erfolgreich! 🎉       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "Family Hub läuft jetzt auf:"
echo -e "${GREEN}http://${CONTAINER_IP}:8000${NC}"
echo ""
echo -e "${YELLOW}Nächste Schritte:${NC}"
echo "1. Bearbeite .env Datei im Container:"
echo "   pct enter $CONTAINER_ID"
echo "   nano $INSTALL_DIR/backend/.env"
echo ""
echo "2. Generiere VAPID Keys:"
echo "   cd $INSTALL_DIR/backend"
echo "   source venv/bin/activate"
echo "   python -c \"from pywebpush import WebPusher; keys = WebPusher.create_keys(); print('PRIVATE:', keys['private_key'].decode()); print('PUBLIC:', keys['public_key'].decode())\""
echo ""
echo "3. Trage Keys in .env ein und starte Service neu:"
echo "   systemctl restart $SERVICE_NAME"
echo ""
echo "4. Optional: Richte Nginx Reverse Proxy ein"
echo "   http://192.168.188.4:81"
echo ""
echo -e "${YELLOW}Logs anzeigen:${NC}"
echo "journalctl -u $SERVICE_NAME -f"
echo ""
