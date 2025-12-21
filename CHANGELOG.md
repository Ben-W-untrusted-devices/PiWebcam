# PiWebcam Changelog

## Completed Improvements

### Security and Input Validation Improvements
**Priority:** High/Medium | **Complexity:** Low | **Time:** 5 tickets

Comprehensive security hardening and input validation across all user-controllable parameters:

**Issues Resolved:**
- ✅ **Race Condition on latest_snapshot_path** - Global variable accessed from multiple threads without synchronization
- ✅ **Missing Camera Resolution Validation** - No bounds checking on resolution parameters
- ✅ **Missing Camera Framerate Validation** - No validation of framerate limits
- ✅ **Missing Port Number Validation** - Invalid port numbers not rejected
- ✅ **Unsafe Snapshot Directory Paths** - No protection against writing to system directories

**Technical Changes:**

1. **Thread Safety (webcam.py:47, 125-126, 457-458, 487-488)**:
   - Added `snapshot_lock` to protect `latest_snapshot_path` global variable
   - Protected writes in `save_motion_snapshot()` function
   - Protected reads in `/motion/status` and `/motion/snapshot` endpoints
   - Prevents TOCTOU race conditions and stale path reads

2. **Camera Resolution Validation (webcam.py:592-600)**:
   - Enforces PiCamera V2 limits: 64-3280x64-2464
   - Rejects negative, zero, or extreme values
   - Clear error messages with valid range
   - Prevents camera initialization failures

3. **Camera Framerate Validation (webcam.py:602-605)**:
   - Enforces PiCamera limits: 1-90 fps
   - Rejects invalid framerates before camera initialization
   - Prevents application crashes from hardware limits

4. **Port Number Validation (webcam.py:631-637)**:
   - Validates range: 1-65535 (standard TCP/IP port range)
   - Warns when privileged ports (<1024) are used
   - Provides actionable error messages

5. **Snapshot Directory Security (webcam.py:673-679)**:
   - Converts to absolute path for consistent validation
   - Blocks writes to system directories: `/etc`, `/root`, `/sys`, `/proc`, `/boot`
   - Prevents accidental file overwrites in sensitive locations
   - Protects against path traversal attacks

**User Experience:**
```bash
# Invalid resolution rejected with clear message
$ python3 webcam.py --resolution 99999x99999
ERROR - Resolution 99999x99999 out of range. Must be 64-3280x64-2464

# Invalid framerate rejected
$ python3 webcam.py --framerate 200
ERROR - Framerate 200 out of range. Must be between 1 and 90 fps

# Invalid port rejected
$ python3 webcam.py --port 70000
ERROR - Port 70000 must be between 1 and 65535

# Privileged port warning
$ python3 webcam.py --port 80
WARNING - Port 80 requires root privileges

# Unsafe directory blocked
$ python3 webcam.py --motion-snapshot --motion-snapshot-dir /etc
ERROR - Unsafe snapshot directory: /etc
ERROR - Cannot write to system directories: /etc, /root, /sys, /proc, /boot
```

**Security Impact:**
- Eliminates race condition that could serve wrong snapshots or cause crashes
- Prevents camera hardware failures from invalid parameters
- Blocks attempts to write to system directories
- Provides defense-in-depth against malicious or accidental misuse

**Files Modified:**
- webcam.py:47 (snapshot_lock addition)
- webcam.py:125-126 (thread-safe write)
- webcam.py:457-458, 487-488 (thread-safe reads)
- webcam.py:592-605 (resolution and framerate validation)
- webcam.py:631-637 (port validation)
- webcam.py:673-679 (snapshot directory validation)

---

### Motion Detection Feature
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

### Motion Detection Cooldown State Machine Fix
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

### Optional Dependencies with Graceful Degradation
**Priority:** Medium | **Complexity:** Medium

Made PIL (Pillow) and numpy dependencies optional with graceful degradation:

**Issues Resolved:**
- ✅ Application no longer crashes at startup if PIL/numpy are missing
- ✅ Motion detection dependencies loaded conditionally with try/except
- ✅ Clear error messages when motion detection is requested without dependencies
- ✅ Helpful installation instructions provided in error message
- ✅ Application runs normally without motion detection when libraries unavailable

**Technical Changes:**
- Wrapped PIL and numpy imports in try/except block
- Added `MOTION_DETECTION_AVAILABLE` flag to track library availability
- Check flag before initializing `MotionDetector` class
- Provide actionable error message: "Install with: pip3 install -r requirements.txt"
- Motion detection code only executes when dependencies are present

**User Experience:**
```
# Without PIL/numpy installed, running with motion detection:
$ python3 webcam.py --motion-detect
ERROR - Motion detection requires PIL (Pillow) and numpy libraries
ERROR - Import error: No module named 'PIL'
ERROR - Install with: pip3 install -r requirements.txt

# Without PIL/numpy installed, running without motion detection:
$ python3 webcam.py
INFO - Authentication disabled
INFO - Camera initialized: 640x480 @ 30fps
INFO - Server started at http://0.0.0.0:8000
```

**Files Modified:**
- webcam.py:19-25 (conditional imports)
- webcam.py:619-624 (dependency check)

---

### JSON Serialization Fix for PiCamera Objects
**Priority:** High | **Complexity:** Low

Fixed crash in /health endpoint caused by non-JSON-serializable PiCamera objects:

**Issue:**
The `/health` endpoint was including `camera.framerate` directly in JSON response. PiCamera returns a `PiCameraFraction` object for framerate, which cannot be serialized to JSON, causing crashes when clients poll the health endpoint.

**Error:**
```
TypeError: Object of type PiCameraFraction is not JSON serializable
```

**Fix:**
- Convert `camera.framerate` to float before JSON serialization
- Changed `"framerate": camera.framerate` to `"framerate": float(camera.framerate)`

**Files Modified:**
- webcam.py:417 (/health endpoint)

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
