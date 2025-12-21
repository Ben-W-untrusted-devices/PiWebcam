# PiWebcam Issues

> **IMPORTANT:** This file tracks ONLY unresolved issues and planned improvements.
> Completed work is documented in [CHANGELOG.md](CHANGELOG.md).
> When working on this codebase, always keep this file synced with reality.

---

## In Progress

_No issues currently in progress_

---

## Current Issues

### Missing Input Validation: Negative Snapshot Limit
**Priority:** Low
**Complexity:** Low

**Issue:**
`--motion-snapshot-limit` (line 565) accepts any integer including negative values. While the check on line 127 prevents negative limits from being used, the argument parser should validate this.

**Solution:**
```python
parser.add_argument('--motion-snapshot-limit', type=int, default=0,
    help='Max snapshots to keep, 0=unlimited (default: 0)',
    choices=range(0, 10000))  # or use a custom validator
```

**Location:** webcam.py:565

---

### Performance: Double Frame Comparison During Motion
**Priority:** Medium
**Complexity:** Medium

**Issue:**
When in MOTION_DETECTED state, frames are compared twice per iteration:
1. Line 211: `compare_frames(self.previous_frame, current_frame_bytes)`
2. Line 241: `compare_frames(self.baseline_frame, current_frame_bytes)`

Each comparison processes every pixel. This doubles CPU usage during motion events.

**Impact:**
- 2x CPU usage during motion detection
- Potential frame drops on Pi Zero
- Higher power consumption

**Solution:**
Restructure logic to avoid redundant comparison:
```python
# Calculate baseline comparison once
baseline_change = compare_frames(self.baseline_frame, current_frame_bytes)
# Use both baseline_change and change_percentage for state logic
```

**Location:** webcam.py:211, 241

---

### Memory Usage: Multiple Frame Copies in Memory
**Priority:** Low
**Complexity:** Medium

**Issue:**
Frame data (typically 50-100KB JPEG per frame) is stored in multiple locations simultaneously:
- `current_frame` (global)
- `motion_detector.previous_frame`
- `motion_detector.baseline_frame`

With 640x480 @ 30fps, this could be 150-300KB of memory just for frame storage, plus any temporary copies during comparison.

**Impact:**
- Increased memory usage (especially on Pi Zero with 512MB RAM)
- Could cause issues with high resolution or long-running processes

**Possible Solutions:**
1. Use weak references where appropriate
2. Implement frame size limits
3. Consider frame pooling/reuse
4. Document memory requirements

**Location:** webcam.py:36, 187-188, 207, 215

---

### Missing Upper Limit: Motion Cooldown Duration
**Priority:** Low
**Complexity:** Low

**Issue:**
`--motion-cooldown` (line 559) accepts any positive float without upper limit. Users could set extremely large values (e.g., 999999 seconds = 11.5 days) which would effectively disable motion detection.

**Solution:**
Add reasonable upper limit:
```python
if not 0.1 <= args.motion_cooldown <= 3600:  # Max 1 hour
    logger.error(f"Motion cooldown must be between 0.1 and 3600 seconds")
    sys.exit(1)
```

**Location:** webcam.py:559, 633

---

### Error Handling: No Camera Reconnection Logic
**Priority:** Medium
**Complexity:** Medium

**Issue:**
If camera is disconnected during operation, the capture loop (line 319) catches exceptions and sleeps for 1 second, then retries indefinitely. There's no:
- Retry limit (could loop forever logging errors)
- Reconnection attempt
- Graceful degradation
- Alert mechanism

**Impact:**
- Logs fill up with error messages
- CPU usage from continuous retry attempts
- No indication to user that camera is offline
- Requires manual restart

**Solution:**
Implement retry logic with exponential backoff and max attempts:
```python
max_retries = 10
retry_count = 0
backoff = 1

while retry_count < max_retries:
    try:
        # capture logic
        retry_count = 0  # reset on success
    except Exception as e:
        retry_count += 1
        logger.error(f"Capture error (attempt {retry_count}/{max_retries}): {e}")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)  # max 60 sec backoff
```

**Location:** webcam.py:286-321

---

### Inconsistent JSON Type Conversion
**Priority:** Low
**Complexity:** Low

**Issue:**
The `/health` endpoint (lines 430-432) explicitly converts types to avoid JSON serialization issues:
```python
"total_events": int(status['motion_event_count'])
```

But the `/motion/status` endpoint (lines 457-458) uses values directly:
```python
"motion_event_count": status['motion_event_count']
```

While this works now, it creates inconsistency and potential future issues if types change.

**Solution:**
Apply consistent explicit type conversion to all JSON endpoints for robustness.

**Location:** webcam.py:452-470

---

### HTTPS Support
**Priority:** Low
**Complexity:** High

**Issue:**
All traffic (including credentials if auth is enabled) is sent unencrypted over HTTP.

**Recommendation:**
Use a reverse proxy (nginx/Apache) with SSL rather than implementing HTTPS directly in Python. This is the standard production approach.

**Example nginx config:**
```nginx
server {
    listen 443 ssl;
    server_name camera.example.com;

    ssl_certificate /etc/letsencrypt/live/camera.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/camera.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
    }
}
```

---

---

## Future Considerations (Not Yet Planned)

### Credential Storage
**Status:** Deferred - current env var approach has limitations

**Current limitations:**
- Environment variables visible in process list
- Not persistent across reboots
- Stored in shell history
- Can't change without restart

**Possible approaches:**
- Config file with bcrypt-hashed passwords (chmod 600)
- Systemd EnvironmentFile
- System keyring integration

**Decision:** Defer until deployment requirements are clearer. Environment variables work well enough for most use cases, especially with systemd EnvironmentFile.

---

## Contributing

When adding issues to this file:
- Only add **unresolved** issues
- Include priority and complexity estimates
- Provide clear problem description
- Suggest potential solutions
- When resolved, move to CHANGELOG.md and remove from here
