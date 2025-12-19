# PiWebcam Changelog

## Completed Improvements

### Security
- ✅ **Path Traversal Vulnerability** - Added path validation with 403 responses
- ✅ **HTTP Basic Authentication** - Optional auth via WEBCAM_USER/WEBCAM_PASS env vars
- ✅ **Specific Exception Handling** - Replaced bare except with specific exceptions

### Portability & Configuration
- ✅ **Relative URLs** - Removed hardcoded hostname from webcam.html
- ✅ **Bind to All Interfaces** - Changed from specific hostname to 0.0.0.0
- ✅ **Command-Line Arguments** - Added --host, --port, --resolution, --framerate, --no-auth, --log-level
- ✅ **Default Content-Type** - Returns application/octet-stream for unknown file types

### Code Quality
- ✅ **Removed Magic Numbers** - Uses camera.framerate instead of hardcoded 30
- ✅ **Graceful Shutdown** - Camera properly closed in finally block
- ✅ **Professional Logging** - Replaced print() with Python logging module

### User Experience
- ✅ **Error Handling** - Image loading errors trigger retry with status update
- ✅ **Connection Status** - Visual indicator (Connecting/Connected/Connection Lost)
- ✅ **Load-Triggered Refresh** - Replaced setInterval with setTimeout chain
- ✅ **Accessibility** - Added ARIA labels and aria-pressed states

### API & Integration
- ✅ **CORS Headers** - Cross-origin support for embedding
- ✅ **Health Check Endpoint** - /health returns JSON status
- ✅ **OPTIONS Support** - Handles CORS preflight requests

### Deployment
- ✅ **Systemd Service** - Auto-start, auto-restart, systemd integration
- ✅ **Installation Script** - Automated service installation
- ✅ **Logging Integration** - Works with journalctl
