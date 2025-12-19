# PiWebcam
Webcam streaming server for Raspberry Pi Camera (optimized for Pi Zero with NOIR camera).

## Features
- Live camera stream via HTTP
- Web interface with rotation controls (N/E/S/W)
- Connection status indicator
- Optional HTTP Basic Authentication
- Health check endpoint for monitoring
- CORS support for embedding in web apps

## Quick Start

```bash
# Run with defaults (640x480 @ 30fps on port 8000)
python3 webcam.py

# Run with authentication
export WEBCAM_USER=your_username
export WEBCAM_PASS=your_password
python3 webcam.py

# Run with custom settings
python3 webcam.py --port 8080 --resolution 1280x720 --framerate 15

# View all options
python3 webcam.py --help
```

Access at: `http://<raspberry-pi-ip>:8000/webcam.html`

## Command-Line Options

```
--host HOST            Host to bind to (default: 0.0.0.0)
--port PORT            Port to bind to (default: 8000)
--resolution WxH       Camera resolution (default: 640x480)
--framerate FPS        Camera framerate (default: 30)
--no-auth              Disable authentication even if credentials set
```

## Endpoints

- `/webcam.html` - Web interface with controls
- `/webcam.jpg` - Current frame (JPEG)
- `/health` - Server status (JSON, no auth required)

## Testing

```bash
pip3 install -r requirements-test.txt
python3 test_webcam.py
```

## Configuration

The server binds to `0.0.0.0:8000` by default. Authentication is optional and controlled via environment variables.

## Install as Systemd Service (Raspberry Pi)

For auto-start on boot and proper daemon management on Raspberry Pi:

```bash
# Run installation script (on Raspberry Pi only)
./install-service.sh

# Enable and start service
sudo systemctl enable piwebcam
sudo systemctl start piwebcam

# Check status
sudo systemctl status piwebcam

# View logs
sudo journalctl -u piwebcam -f
```

### Configure Authentication for Service

```bash
# Create credentials file
sudo mkdir -p /etc/piwebcam
echo "WEBCAM_USER=admin" | sudo tee /etc/piwebcam/credentials.env
echo "WEBCAM_PASS=your_password" | sudo tee -a /etc/piwebcam/credentials.env
sudo chmod 600 /etc/piwebcam/credentials.env

# Edit service file to enable EnvironmentFile
sudo nano /etc/systemd/system/piwebcam.service
# Uncomment: EnvironmentFile=/etc/piwebcam/credentials.env

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart piwebcam
```
