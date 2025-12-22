# HTTPS Setup Instructions

## On the Pi (via SSH):

### 1. Make the certificate generation script executable:
```bash
cd /home/pi/Apps/PiWebcam
chmod +x generate-cert.sh
```

### 2. Generate SSL certificate (one-time):
```bash
./generate-cert.sh
```

This creates `cert.pem` and `key.pem` in the current directory.

### 3. Test HTTPS manually:
```bash
# Stop any running instance first
sudo systemctl stop piwebcam  # If running as service

# Test HTTPS
python3 webcam.py --ssl --port 8443 --quality 50
```

### 4. Access from browser:
```
https://pi-noir-camera.local:8443/webcam.html
```

**Browser will show security warning:**
- Click "Advanced" or "Show Details"
- Click "Accept the Risk and Continue" or "Proceed"
- This is normal for self-signed certificates

### 5. Update systemd service (optional):

If you want HTTPS to run automatically:

```bash
# Edit service file
sudo nano /etc/systemd/system/piwebcam.service

# Change ExecStart line to:
ExecStart=/usr/bin/python3 /home/pi/PiWebcam/webcam.py --ssl --port 8443 --quality 50

# Save and exit (Ctrl+X, Y, Enter)

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart piwebcam

# Check status
sudo systemctl status piwebcam
```

## Certificate Files:

- `cert.pem` - SSL certificate (safe to share)
- `key.pem` - Private key (keep secret, chmod 600)

## Certificate Renewal:

Certificates expire after 1 year. To renew:

```bash
cd /home/pi/Apps/PiWebcam
./generate-cert.sh
sudo systemctl restart piwebcam  # If using service
```

## Ports:

- **8443** - Standard HTTPS alternative port (recommended, no root needed)
- **443** - Standard HTTPS port (requires root privileges)

## Troubleshooting:

**"Certificate or key file not found" error:**
```bash
# Check files exist
ls -la cert.pem key.pem

# Regenerate if missing
./generate-cert.sh
```

**"Permission denied" error:**
```bash
# Fix permissions
chmod 600 key.pem cert.pem
```

**Browser still shows warning:**
- This is normal for self-signed certificates
- Click "Advanced" → "Proceed"
- Each browser/device needs to accept once

**Port 443 "Permission denied":**
```bash
# Use port 8443 instead (doesn't require root)
python3 webcam.py --ssl --port 8443
```
