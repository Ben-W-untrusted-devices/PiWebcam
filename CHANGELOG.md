# PiWebcam Changelog

## Completed Improvements

### Motion Detection Feature (December 2024)
**Priority:** Medium | **Complexity:** Medium | **Time:** 8 tickets across 3 phases

Complete motion detection system using frame differencing algorithm:

**Phase 1: Core Detection**
- ✅ Frame comparison logic with grayscale conversion and pixel differencing
- ✅ MotionDetector state machine (idle → motion_detected → cooldown)
- ✅ CLI arguments: --motion-detect, --motion-threshold, --motion-cooldown
- ✅ Threshold validation (0-100 range)
- ✅ Thread-safe state tracking

**Phase 2: Actions & Events**
- ✅ Motion event logging (INFO for detection, DEBUG for motion end)
- ✅ Snapshot saving on motion detection
- ✅ Configurable snapshot directory and rotation limit
- ✅ Timestamp-based filenames (motion_YYYYMMDD_HHMMSS.jpg)
- ✅ Enhanced /health endpoint with motion status
- ✅ /motion/status endpoint for detailed information
- ✅ /motion/snapshot endpoint for latest snapshot image

**Phase 3: UI & Polish**
- ✅ Real-time motion indicator in web UI (pulsing red badge)
- ✅ Event counter and last detection timestamp display
- ✅ Comprehensive documentation in README
- ✅ Configuration guide and troubleshooting section
- ✅ Unit tests for frame comparison and state machine

**Technical Details:**
- Uses PIL/Pillow and numpy for efficient image processing
- Configurable sensitivity (threshold) and cooldown period
- Automatic cleanup of old snapshots when limit exceeded
- Proper error handling and graceful degradation
- No performance impact when disabled

**Files Modified:**
- webcam.py: +450 lines (core implementation)
- webcam.html: +65 lines (UI indicator)
- README.md: +143 lines (documentation)
- requirements.txt: Added (PIL, numpy dependencies)
- test_motion_detection.py: +287 lines (test suite)

---

### Motion Detection Cooldown State Machine Fix (December 2024)
**Priority:** Medium | **Complexity:** Low

Fixed critical bugs in the motion detection state machine that prevented proper cooldown behavior:

**Issues Resolved:**
- ✅ State now properly transitions to cooldown when motion ends (frame returns to baseline)
- ✅ Cooldown prevents immediate re-triggering of motion events
- ✅ `is_motion_active()` correctly returns False during cooldown state
- ✅ Motion event counter properly increments for multiple motion sessions
- ✅ Cooldown expiration now correctly allows new motion detection

**Technical Changes:**
- Added baseline frame tracking to detect when frames return to original state
- Restructured state machine logic to check baseline when in MOTION_DETECTED state
- Fixed cooldown expiration to fall through and check for new motion in same frame
- All 17 motion detection unit tests now pass on Raspberry Pi hardware

**Test Results:**
```
test_cooldown_expires - PASS
test_cooldown_prevents_retriggering - PASS
test_is_motion_active - PASS
test_motion_event_counter - PASS
```

**Files Modified:**
- webcam.py:162-247 (`MotionDetector` class)

---

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
