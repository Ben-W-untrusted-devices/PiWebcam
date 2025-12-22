#!/bin/bash
# Generate self-signed SSL certificate for HTTPS support
# Valid for 1 year, can be regenerated anytime

echo "Generating self-signed SSL certificate..."

openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout key.pem \
    -out cert.pem \
    -days 365 \
    -subj "/CN=pi-noir-camera.local/O=PiWebcam/C=US"

chmod 600 key.pem cert.pem

echo "✓ Certificate generated successfully!"
echo ""
echo "Files created:"
echo "  - cert.pem (SSL certificate)"
echo "  - key.pem (private key)"
echo ""
echo "Run with SSL:"
echo "  python3 webcam.py --ssl --port 8443"
echo ""
echo "Access at:"
echo "  https://pi-noir-camera.local:8443/webcam.html"
echo ""
echo "Note: Browser will show security warning (click 'Advanced' → 'Accept Risk')"
