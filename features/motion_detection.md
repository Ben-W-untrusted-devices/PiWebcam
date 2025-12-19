# Motion Detection Feature

## Overview

Add motion detection capability to PiWebcam using frame differencing algorithm. Detect when camera detects movement and trigger configurable actions.

## Architecture

**Algorithm:** Frame differencing (simple, CPU-efficient for Pi Zero)
- Compare current frame with previous frame
- Calculate pixel difference percentage
- Trigger when difference exceeds threshold

**Components:**
1. Motion detector class
2. Configuration options (threshold, sensitivity, cooldown)
3. Event triggers (snapshots, webhooks, logging)
4. API endpoint for motion status
5. Web UI indicator

---

## Task Breakdown

### Phase 1: Core Detection (3 tickets, ~3h total)

#### Ticket 1.1: Frame Comparison Logic
**Estimate:** 1-1.5h
**Priority:** High
**Dependencies:** None

**Tasks:**
- [ ] Add PIL/Pillow for image processing (already available on Pi)
- [ ] Implement frame differencing function
- [ ] Calculate percentage of pixels changed
- [ ] Add basic threshold check
- [ ] Unit tests for comparison logic

**Acceptance Criteria:**
- Function compares two JPEG frames
- Returns percentage of change (0-100)
- Handles grayscale conversion for efficiency
- No memory leaks in capture loop

---

#### Ticket 1.2: Motion Detection State Machine
**Estimate:** 1-1.5h
**Priority:** High
**Dependencies:** Ticket 1.1

**Tasks:**
- [ ] Create MotionDetector class
- [ ] Add state tracking (idle, motion_detected, cooldown)
- [ ] Implement cooldown period (prevent spam)
- [ ] Add motion event counter
- [ ] Integrate into capture loop

**Acceptance Criteria:**
- Detects motion when threshold exceeded
- Cooldown prevents repeated triggers
- Thread-safe state access
- Minimal performance impact on capture loop

---

#### Ticket 1.3: Configuration Options
**Estimate:** 1h
**Priority:** High
**Dependencies:** Ticket 1.2

**Tasks:**
- [ ] Add CLI arguments: --motion-detect, --motion-threshold, --motion-cooldown
- [ ] Add environment variables fallback
- [ ] Validate threshold range (0-100)
- [ ] Add motion detection to startup logs
- [ ] Update --help documentation

**Acceptance Criteria:**
- Motion detection disabled by default
- Configurable threshold (default: 5%)
- Configurable cooldown (default: 5 seconds)
- Clear logging of motion settings

---

### Phase 2: Actions & Events (3 tickets, ~3h total)

#### Ticket 2.1: Motion Event Logging
**Estimate:** 30min
**Priority:** Medium
**Dependencies:** Ticket 1.2

**Tasks:**
- [ ] Log motion detected events (INFO level)
- [ ] Log motion ended events (DEBUG level)
- [ ] Include timestamp and change percentage
- [ ] Add motion event counter to logs

**Acceptance Criteria:**
- Clear log messages when motion detected
- Percentage logged for debugging
- Event counter increments correctly

---

#### Ticket 2.2: Snapshot on Motion
**Estimate:** 1-1.5h
**Priority:** Medium
**Dependencies:** Ticket 1.2

**Tasks:**
- [ ] Add --motion-snapshot flag
- [ ] Create snapshots directory
- [ ] Save JPEG with timestamp filename
- [ ] Add rotation limit (max N snapshots)
- [ ] Log snapshot saves

**Acceptance Criteria:**
- Snapshots saved as `motion_YYYYMMDD_HHMMSS.jpg`
- Optional directory cleanup (keep last N)
- Proper error handling for disk full
- No performance impact

---

#### Ticket 2.3: Motion Status API
**Estimate:** 1h
**Priority:** Medium
**Dependencies:** Ticket 1.2

**Tasks:**
- [ ] Add motion stats to /health endpoint
- [ ] Include: enabled, currently_detecting, total_events, last_event_time
- [ ] Create /motion/status endpoint (detailed)
- [ ] Add /motion/snapshot endpoint (get last snapshot)
- [ ] Update API documentation

**Acceptance Criteria:**
- /health includes motion status
- /motion/status returns detailed JSON
- /motion/snapshot returns latest snapshot image
- Proper 404 if no snapshot exists

---

### Phase 3: UI & Polish (2 tickets, ~2h total)

#### Ticket 3.1: Web UI Motion Indicator
**Estimate:** 1h
**Priority:** Low
**Dependencies:** Ticket 2.3

**Tasks:**
- [ ] Add motion detection indicator to webcam.html
- [ ] Show "Motion Detected!" badge when active
- [ ] Poll /health for motion status
- [ ] Add visual animation/highlight
- [ ] Show last detection timestamp

**Acceptance Criteria:**
- Visual indicator appears during motion
- Disappears after cooldown period
- Doesn't interfere with video stream
- Responsive design

---

#### Ticket 3.2: Testing & Documentation
**Estimate:** 1h
**Priority:** Medium
**Dependencies:** All above

**Tasks:**
- [ ] Add motion detection tests
- [ ] Test on actual Pi with camera
- [ ] Tune default threshold for Pi NOIR camera
- [ ] Update README.md with motion detection section
- [ ] Add troubleshooting guide
- [ ] Update CHANGELOG.md

**Acceptance Criteria:**
- Unit tests for frame comparison
- Integration tests for motion detection
- Documentation complete
- Example configurations provided

---

## Configuration Examples

```bash
# Enable motion detection with defaults
python3 webcam.py --motion-detect

# Custom threshold and cooldown
python3 webcam.py --motion-detect --motion-threshold 3 --motion-cooldown 10

# With snapshots
python3 webcam.py --motion-detect --motion-snapshot --motion-snapshot-dir /var/snapshots

# Sensitive detection for low-light
python3 webcam.py --motion-detect --motion-threshold 2
```

## API Examples

```bash
# Check motion status
curl http://pi-camera.local:8000/health

# Detailed motion stats
curl http://pi-camera.local:8000/motion/status

# Get latest snapshot
curl http://pi-camera.local:8000/motion/snapshot -o latest.jpg
```

---

## Implementation Notes

**Performance Considerations:**
- Use grayscale conversion for comparison (faster)
- Downsample frames for comparison (optional)
- Compare every Nth frame only (optional optimization)
- Ensure GC doesn't cause latency spikes

**Pi Zero Limitations:**
- Limited CPU - frame differencing is CPU-intensive
- May need to reduce frame rate when motion detection enabled
- Consider comparing at lower resolution

**Future Enhancements (not in scope):**
- Webhook notifications
- Email alerts
- Motion zones (only detect in specific areas)
- Video recording on motion
- Machine learning classification (person/animal/vehicle)

---

## Estimated Total Time

**Phase 1:** 3-4 hours
**Phase 2:** 3-4 hours
**Phase 3:** 2 hours

**Total:** 8-10 hours across 8 tickets

**All tickets are <2h as requested**
