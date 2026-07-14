#!/bin/bash
# install_service.sh — Cài đặt drone-companion systemd service trên Raspberry Pi 5
#
# Chạy từ thư mục companion/ sau khi SSH vào Pi:
#   chmod +x install_service.sh
#   sudo ./install_service.sh
#
# Sau khi cài, quản lý bằng:
#   sudo systemctl status  drone-companion
#   sudo systemctl start   drone-companion
#   sudo systemctl stop    drone-companion
#   sudo systemctl restart drone-companion
#   journalctl -u drone-companion -f   # xem log realtime

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="drone-companion"
INSTALL_DIR="/opt/drone-delivery-system/companion"
SERVICE_FILE="$INSTALL_DIR/$SERVICE_NAME.service"
SYSTEMD_DIR="/etc/systemd/system"

# Detect the real user who ran the script via sudo
REAL_USER=${SUDO_USER:-$(logname 2>/dev/null || whoami)}
REAL_GROUP=$(id -gn "$REAL_USER")

echo "===== Drone Companion Install Script ====="
echo "Install dir  : $INSTALL_DIR"
echo "Service name : $SERVICE_NAME"
echo "Target User  : $REAL_USER"
echo "Target Group : $REAL_GROUP"
echo ""

# 1. Create install directory and copy files
echo "[1/6] Copying companion files to $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    sudo cp -r "$SCRIPT_DIR"/. "$INSTALL_DIR/"
else
    echo "       Already in $INSTALL_DIR — skipping copy"
fi
sudo chown -R "$REAL_USER:$REAL_GROUP" "$INSTALL_DIR"

# 2. Create Python virtual environment
echo "[2/6] Creating Python venv..."
sudo -u "$REAL_USER" python3 -m venv "$INSTALL_DIR/venv"

# 3. Install dependencies
echo "[3/6] Installing dependencies..."
sudo -u "$REAL_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
sudo -u "$REAL_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
echo "       Dependencies installed"

# 4. Create .env from .env.example if not exists
echo "[4/6] Checking .env config..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    sudo cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    sudo chown "$REAL_USER:$REAL_GROUP" "$INSTALL_DIR/.env"
    echo "       Created .env from .env.example"
    echo "       ⚠️  EDIT $INSTALL_DIR/.env with your IP and UART settings before starting!"
else
    echo "       .env already exists — skipping"
fi

# 5. Install systemd service
echo "[5/6] Installing systemd service..."
sudo cp "$INSTALL_DIR/$SERVICE_NAME.service" "$SYSTEMD_DIR/$SERVICE_NAME.service"
# Update User and Group in systemd service to match the target user/group
sudo sed -i "s/User=pi/User=$REAL_USER/g" "$SYSTEMD_DIR/$SERVICE_NAME.service"
sudo sed -i "s/Group=pi/Group=$REAL_GROUP/g" "$SYSTEMD_DIR/$SERVICE_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "       Service enabled (auto-start on boot)"

# 6. Add user to dialout group for UART access
echo "[6/6] Adding $REAL_USER to dialout group (UART access)..."
sudo usermod -aG dialout "$REAL_USER"
echo "       Done (re-login required for group to take effect)"

echo ""
echo "===== Installation Complete ====="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/drone-delivery-system/companion/.env"
echo "     Set SERVER_IP and MAVLINK_DEVICE correctly"
echo ""
echo "  2. Start the service:"
echo "     sudo systemctl start drone-companion"
echo ""
echo "  3. View live logs:"
echo "     journalctl -u drone-companion -f"
echo ""
echo "  4. Check status:"
echo "     sudo systemctl status drone-companion"
