# PiWebcam Issues

> **IMPORTANT:** This file tracks ONLY unresolved issues and planned improvements.
> Completed work is documented in [CHANGELOG.md](CHANGELOG.md).
> When working on this codebase, always keep this file synced with reality.

---

## In Progress

_No issues currently in progress_

---

## Current Issues

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
