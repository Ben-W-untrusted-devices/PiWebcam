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
# Run without authentication
python3 webcam.py

# Run with authentication
export WEBCAM_USER=your_username
export WEBCAM_PASS=your_password
python3 webcam.py
```

Access at: `http://<raspberry-pi-ip>:8000/webcam.html`

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
