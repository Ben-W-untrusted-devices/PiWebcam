#!/bin/bash
# Install PiWebcam as a systemd service

set -e

echo "Installing PiWebcam systemd service..."

# Get the actual directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Update WorkingDirectory and ExecStart paths in service file
sed "s|/home/pi/PiWebcam|$SCRIPT_DIR|g" piwebcam.service > /tmp/piwebcam.service

# Copy service file to systemd directory
sudo cp /tmp/piwebcam.service /etc/systemd/system/piwebcam.service
rm /tmp/piwebcam.service

# Reload systemd to recognize new service
sudo systemctl daemon-reload

echo "✓ Service file installed"
echo ""
echo "Next steps:"
echo "  1. (Optional) Configure authentication:"
echo "     sudo mkdir -p /etc/piwebcam"
echo "     echo 'WEBCAM_USER=admin' | sudo tee /etc/piwebcam/credentials.env"
echo "     echo 'WEBCAM_PASS=your_password' | sudo tee -a /etc/piwebcam/credentials.env"
echo "     sudo chmod 600 /etc/piwebcam/credentials.env"
echo "     Then uncomment EnvironmentFile line in /etc/systemd/system/piwebcam.service"
echo ""
echo "  2. Enable and start the service:"
echo "     sudo systemctl enable piwebcam"
echo "     sudo systemctl start piwebcam"
echo ""
echo "  3. Check status:"
echo "     sudo systemctl status piwebcam"
echo ""
echo "  4. View logs:"
echo "     sudo journalctl -u piwebcam -f"
