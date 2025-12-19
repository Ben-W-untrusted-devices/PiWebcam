# PiWebcam Issues & Improvements

## High Priority

### ~~2. Hardcoded URL in Frontend (webcam.html:143)~~ ✓ RESOLVED
**Severity:** High - Portability Issue

**Status:** Fixed - Now uses relative URL

**Solution Implemented:**
Changed to relative URL: `webcam.jpg?t=...` for better portability across different networks and devices.

---

## Medium Priority

### ~~3. Missing Content-Type Default (webcam.py:51-61)~~ ✓ RESOLVED
**Severity:** Medium - Error Handling

**Status:** Fixed - Returns default Content-Type for unknown extensions

**Solution Implemented:**
Added `else: return "application/octet-stream"` as default for unknown file types.

---

### ~~4. No Error Handling for Image Loading (webcam.html:148-152)~~ ✓ RESOLVED
**Severity:** Medium - User Experience

**Status:** Fixed - Added error handler with retry logic

**Solution Implemented:**
Added `onerror` handler that logs errors, updates connection status, and retries after 1 second delay.

---

### ~~5. Magic Numbers - Frame Rate Duplication (webcam.py:40)~~ ✓ RESOLVED
**Severity:** Medium - Code Quality

**Status:** Fixed - Now uses camera.framerate property

**Solution Implemented:**
Changed `time.sleep(1.0 / 30)` to `time.sleep(1.0 / camera.framerate)` to eliminate duplication.

---

## Low Priority

### ~~6. No Graceful Camera Shutdown (webcam.py:96+)~~ ✓ RESOLVED
**Severity:** Low - Resource Management

**Status:** Fixed - Camera properly closed on shutdown

**Solution Implemented:**
Added `finally` block that calls `camera.close()` and `httpd.server_close()` to ensure proper cleanup.

---

### ~~7. Hardcoded Hostname in Python (webcam.py:19)~~ ✓ RESOLVED
**Severity:** Low - Portability

**Status:** Fixed - Now binds to all interfaces

**Solution Implemented:**
Changed `HOST_NAME = "pi-noir-camera.local"` to `HOST_NAME = "0.0.0.0"` to bind to all network interfaces.

---

### ~~8. No Loading State in UI (webcam.html)~~ ✓ RESOLVED
**Severity:** Low - User Experience

**Status:** Fixed - Added connection status indicator

**Solution Implemented:**
Added status div that displays "Connecting...", "Connected" (green), or "Connection lost, retrying..." (orange) based on stream state.

---

### ~~9. Unchecked Interval Timer (webcam.html:158)~~ ✓ RESOLVED
**Severity:** Low - Performance

**Status:** Fixed - Replaced setInterval with setTimeout chain

**Solution Implemented:**
Replaced `setInterval` with `setTimeout` called from `onload` and `onerror` handlers. Next refresh only scheduled after current image loads or fails.

---

### ~~10. Accessibility Issues (webcam.html)~~ ✓ RESOLVED
**Severity:** Low - Accessibility

**Status:** Fixed - Added ARIA attributes

**Solution Implemented:**
- Added `role="img"` and `aria-label="Live webcam feed"` to canvas
- Added dynamic `aria-pressed` states to rotation buttons
- Added `role="status"` and `aria-live="polite"` to status indicator

---

## Architecture Improvements

These are longer-term architectural considerations:

- **No HTTPS Support:** Streams and any future credentials sent unencrypted
- **No Authentication:** Anyone on network can access camera stream
- **No CORS Headers:** Limits ability to embed in other web applications
- **No Health Check Endpoint:** Can't programmatically verify server is running

---

## Legend
- **Critical:** Security vulnerabilities or data loss risks
- **High:** Major functionality or portability issues
- **Medium:** Code quality, error handling, user experience issues
- **Low:** Minor improvements, cleanup, enhancements
