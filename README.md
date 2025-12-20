# PiWebcam
Webcam streaming server for Raspberry Pi Camera (optimized for Pi Zero with NOIR camera).

## Features
- Live camera stream via HTTP
- Web interface with rotation controls (N/E/S/W)
- Connection status indicator
- Optional HTTP Basic Authentication
- Health check endpoint for monitoring
- CORS support for embedding in web apps
- Motion detection with configurable threshold and cooldown
- Automatic snapshot saving on motion events
- Motion status API endpoints
- Real-time motion indicator in web UI

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

Access at: `http://pi-noir-camera.local:8000/webcam.html`

## Command-Line Options

### Basic Options
```
--host HOST            Host to bind to (default: 0.0.0.0)
--port PORT            Port to bind to (default: 8000)
--resolution WxH       Camera resolution (default: 640x480)
--framerate FPS        Camera framerate (default: 30)
--no-auth              Disable authentication even if credentials set
--log-level LEVEL      Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
```

### Motion Detection Options
```
--motion-detect                Enable motion detection (default: disabled)
--motion-threshold PCT         Motion threshold 0-100% (default: 5.0)
--motion-cooldown SECS         Seconds between motion events (default: 5.0)
--motion-snapshot              Save snapshots when motion detected (default: disabled)
--motion-snapshot-dir DIR      Snapshot directory (default: ./snapshots)
--motion-snapshot-limit N      Max snapshots to keep, 0=unlimited (default: 0)
```

**Example with logging:**
```bash
# Debug mode for troubleshooting
python3 webcam.py --log-level DEBUG

# Quiet mode (errors only)
python3 webcam.py --log-level ERROR
```

## Endpoints

- `/webcam.html` - Web interface with controls
- `/webcam.jpg` - Current frame (JPEG)
- `/health` - Server status including motion detection (JSON, no auth required)
- `/motion/status` - Detailed motion detection status (JSON)
- `/motion/snapshot` - Latest motion snapshot image (JPEG)

## Motion Detection

PiWebcam includes a built-in motion detection system using frame differencing algorithm.

### How It Works

Motion detection compares consecutive camera frames to detect changes:
1. Converts frames to grayscale for efficiency
2. Calculates pixel-by-pixel difference
3. Triggers when percentage of changed pixels exceeds threshold
4. Enforces cooldown period to prevent spam

### Quick Start

```bash
# Enable motion detection with defaults (5% threshold, 5s cooldown)
python3 webcam.py --motion-detect

# Sensitive detection for low-light environments
python3 webcam.py --motion-detect --motion-threshold 3

# With snapshot saving (keeps last 100 snapshots)
python3 webcam.py --motion-detect --motion-snapshot --motion-snapshot-limit 100

# Full example with custom settings
python3 webcam.py --motion-detect \
  --motion-threshold 4.0 \
  --motion-cooldown 10 \
  --motion-snapshot \
  --motion-snapshot-dir /var/snapshots \
  --motion-snapshot-limit 50
```

### Configuration Guide

**Threshold** (`--motion-threshold`)
- Range: 0-100 (percentage of pixels that must change)
- Default: 5.0
- Lower values = more sensitive (triggers on small movements)
- Higher values = less sensitive (only large movements trigger)
- Recommended:
  - Indoor/well-lit: 5-8%
  - Outdoor/variable light: 8-12%
  - Low-light/NOIR camera: 3-5%

**Cooldown** (`--motion-cooldown`)
- Seconds to wait between motion events
- Default: 5.0
- Prevents multiple triggers for same motion event
- Set higher to reduce snapshot/notification spam

**Snapshots** (`--motion-snapshot`)
- Saves JPEG when motion first detected
- Filename format: `motion_YYYYMMDD_HHMMSS.jpg`
- Use `--motion-snapshot-limit` to auto-delete old snapshots
- Set to 0 for unlimited (disk space permitting)

### API Usage

**Check motion status:**
```bash
curl http://pi-noir-camera.local:8000/health | jq '.motion'
```

**Get detailed motion information:**
```bash
curl http://pi-noir-camera.local:8000/motion/status | jq
```

**Download latest snapshot:**
```bash
curl http://pi-noir-camera.local:8000/motion/snapshot -o latest_motion.jpg
```

### Web UI Indicator

The web interface shows real-time motion detection status:
- **Red pulsing badge** - Motion is currently being detected
- **Gray badge** - Motion detection enabled but idle (shows event count)
- **Hidden** - Motion detection disabled

### Logging

Motion events are logged for monitoring:
```
INFO - Motion detected! Change: 12.34%, Event #5
DEBUG - Motion ended. Change: 1.23%
INFO - Snapshot saved: /path/to/motion_20231215_143022.jpg
```

### Performance Considerations

Motion detection is CPU-intensive, especially on Raspberry Pi Zero:
- Uses grayscale conversion for better performance
- Frame differencing is fast but not ML-based
- May need to reduce framerate on Pi Zero: `--framerate 15`
- Consider lower resolution for better performance: `--resolution 320x240`

### Troubleshooting

**Too many false positives:**
- Increase threshold: `--motion-threshold 8`
- Increase cooldown: `--motion-cooldown 10`
- Check for environmental changes (shadows, clouds, swaying objects)

**Not detecting motion:**
- Decrease threshold: `--motion-threshold 3`
- Check camera is working: view `/webcam.jpg`
- Enable debug logging: `--log-level DEBUG`

**Snapshots filling disk:**
- Set snapshot limit: `--motion-snapshot-limit 100`
- Use systemd tmpfiles.d for automatic cleanup
- Monitor disk space with cron

## Testing

```bash
# Install test dependencies
pip3 install -r requirements-test.txt

# Run all tests
python3 test_webcam.py

# Run motion detection tests specifically
python3 test_motion_detection.py

# Run with verbose output
python3 -m unittest test_motion_detection.TestFrameComparison -v
python3 -m unittest test_motion_detection.TestMotionDetector -v
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
