#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Receipts Bot Installation Script${NC}"
echo "=================================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo -e "Project directory: ${YELLOW}${SCRIPT_DIR}${NC}"

# Get current user
CURRENT_USER=$(whoami)
echo -e "Current user: ${YELLOW}${CURRENT_USER}${NC}"

# Check if virtual environment exists
if [ ! -d "${SCRIPT_DIR}/venv" ]; then
    echo -e "${RED}Error: Virtual environment not found at ${SCRIPT_DIR}/venv${NC}"
    echo "Please create it first: python3 -m venv venv"
    exit 1
fi

# Check if config.ini exists
if [ ! -f "${SCRIPT_DIR}/config.ini" ]; then
    echo -e "${RED}Error: config.ini not found at ${SCRIPT_DIR}${NC}"
    echo "Please create it before installing the service"
    exit 1
fi

# Check if bot.py exists
if [ ! -f "${SCRIPT_DIR}/bot.py" ]; then
    echo -e "${RED}Error: bot.py not found at ${SCRIPT_DIR}${NC}"
    exit 1
fi

echo ""
echo "Creating systemd service unit file..."

# Generate the service file
SERVICE_NAME="receipts-bot"
SERVICE_FILE="/tmp/${SERVICE_NAME}.service"

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=Receipts Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/venv/bin/python ${SCRIPT_DIR}/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment variables
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Service file generated at: ${SERVICE_FILE}${NC}"
echo ""
echo "Contents:"
echo "----------------------------------------"
cat "${SERVICE_FILE}"
echo "----------------------------------------"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}To complete installation, run the following commands with sudo:${NC}"
    echo ""
    echo "  sudo cp ${SERVICE_FILE} /etc/systemd/system/${SERVICE_NAME}.service"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable ${SERVICE_NAME}.service"
    echo "  sudo systemctl start ${SERVICE_NAME}.service"
    echo ""
    echo "To check status:"
    echo "  sudo systemctl status ${SERVICE_NAME}.service"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u ${SERVICE_NAME}.service -f"
else
    # Running as root, install automatically
    echo "Installing service..."
    cp "${SERVICE_FILE}" "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload

    echo ""
    read -p "Enable service to start on boot? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl enable "${SERVICE_NAME}.service"
        echo -e "${GREEN}Service enabled${NC}"
    fi

    echo ""
    read -p "Start service now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl start "${SERVICE_NAME}.service"
        echo -e "${GREEN}Service started${NC}"
        echo ""
        systemctl status "${SERVICE_NAME}.service"
    fi
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
