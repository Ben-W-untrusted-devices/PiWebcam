# PiWebcam Issues & Improvements

## Critical Priority

### ~~1. Path Traversal Vulnerability (webcam.py:82)~~ ✓ RESOLVED
**Severity:** Critical - Security Issue

**Status:** Fixed - Now validates all file paths are within current directory

**Solution Implemented:**
- Added `os.path.abspath()` to resolve requested path
- Validates resolved path starts with current directory
- Returns 403 Forbidden for path traversal attempts
- Also fixed bare exception handler to catch only `FileNotFoundError` and `IOError`

---

## High Priority

### 2. Hardcoded URL in Frontend (webcam.html:143)
**Severity:** High - Portability Issue

**Location:** `webcam.html:143`

**Problem:**
```javascript
let webcamURL = "http://pi-noir-camera.local:8000/webcam.jpg?t=" + (new Date()).getTime();
```
Hardcoded hostname prevents using the app on different networks or devices.

**Solution:**
Use relative URL:
```javascript
let webcamURL = "webcam.jpg?t=" + (new Date()).getTime();
```

---

## Medium Priority

### ~~3. Bare Exception Handler (webcam.py:86)~~ ✓ RESOLVED
**Severity:** Medium - Error Handling

**Status:** Fixed as part of path traversal fix

**Solution Implemented:**
Now uses specific exception handling:
```python
except (FileNotFoundError, IOError):
```

---

### 4. Missing Content-Type Default (webcam.py:51-61)
**Severity:** Medium - Error Handling

**Location:** `webcam.py:51-61`

**Problem:**
`contentTypeFrom()` returns `None` for unknown file extensions, which will cause errors in `sendHeader()`.

**Solution:**
Add default return value:
```python
return "application/octet-stream"
```

---

### 5. No Error Handling for Image Loading (webcam.html:148-152)
**Severity:** Medium - User Experience

**Location:** `webcam.html:148-152`

**Problem:**
Image load failures are silently ignored. User has no feedback if camera stream stops.

**Solution:**
Add `onerror` handler to retry or display error status.

---

### 6. Magic Numbers - Frame Rate Duplication (webcam.py:40)
**Severity:** Medium - Code Quality

**Location:** `webcam.py:40`

**Problem:**
```python
time.sleep(1.0 / 30)  # 30 fps
```
Duplicates the framerate value from line 12. Could get out of sync.

**Solution:**
```python
time.sleep(1.0 / camera.framerate)
```

---

## Low Priority

### 7. No Graceful Camera Shutdown (webcam.py:96+)
**Severity:** Low - Resource Management

**Location:** `webcam.py:96+`

**Problem:**
Camera isn't explicitly closed on shutdown. May leave camera resource locked.

**Solution:**
Add camera cleanup in finally block:
```python
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    camera.close()
    httpd.server_close()
```

---

### 8. Hardcoded Hostname in Python (webcam.py:19)
**Severity:** Low - Portability

**Location:** `webcam.py:19`

**Problem:**
```python
HOST_NAME = "pi-noir-camera.local"
```
Limits portability to devices with this specific hostname.

**Solution:**
Use `"0.0.0.0"` or make configurable via environment variable.

---

### 9. No Loading State in UI (webcam.html)
**Severity:** Low - User Experience

**Location:** `webcam.html`

**Problem:**
User sees blank screen if initial connection fails. No feedback about connection status.

**Solution:**
Add loading indicator and connection status display.

---

### 10. Unchecked Interval Timer (webcam.html:158)
**Severity:** Low - Performance

**Location:** `webcam.html:158`

**Problem:**
Interval continues even if images fail to load, potentially queueing up failed requests.

**Solution:**
Only schedule next refresh after current image loads successfully.

---

### 11. Accessibility Issues (webcam.html)
**Severity:** Low - Accessibility

**Location:** `webcam.html`

**Problems:**
- Canvas has no alt text or aria-label
- Buttons lack aria-pressed states for current rotation

**Solution:**
Add appropriate ARIA attributes.

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
