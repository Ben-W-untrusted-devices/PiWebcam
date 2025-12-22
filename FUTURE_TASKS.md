# Future Tasks - Backend Work Required

This file tracks UI/feature improvements that require backend implementation.

---

## H.264 Hardware Encoder Streaming

**Priority:** High
**Complexity:** High
**Category:** Performance Enhancement

**Description:**
Use Pi camera's hardware H.264 encoder for 30 FPS video streaming instead of individual JPEG captures (currently limited to 8-10 FPS).

**Current Limitation:**
- Using individual `camera.capture()` calls in loop
- Each capture has overhead: sensor readout + ISP + format conversion
- JPEG encoding even at lowest quality only achieves 8-10 FPS
- Theoretical limit of individual captures: ~10 FPS regardless of settings

**Backend Requirements:**

1. **Server-side H.264 recording:**
   - Replace capture loop with `camera.start_recording(output, format='h264')`
   - Implement H.264 stream packaging (fMP4 or HLS)
   - Handle fragmented MP4 with proper headers for live streaming
   - Manage segment buffering and client synchronization

2. **New endpoint: `/stream` (H.264)**
   - Serve H.264 stream as fragmented MP4
   - Or implement HLS with .m3u8 playlist + .ts segments
   - Proper MIME types and headers for live streaming
   - Handle multiple concurrent clients

3. **Alternative: Keep simpler architecture with better performance**
   - Use `camera.start_recording(output, format='mjpeg')`
   - Serve as multipart/x-mixed-replace stream (MJPEG)
   - Simpler than H.264 but achieves 30 FPS goal
   - Currently implemented (see CHANGELOG)

**Frontend Requirements:**

1. **Replace canvas with video element:**
```html
<video id="webcamElement" autoplay muted playsinline></video>
```

2. **Media Source Extensions (for H.264):**
```javascript
const video = document.getElementById('webcamElement');
const mediaSource = new MediaSource();
video.src = URL.createObjectURL(mediaSource);

mediaSource.addEventListener('sourceopen', () => {
    const sourceBuffer = mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E"');

    // Fetch and append H.264 segments
    fetch('/stream')
        .then(response => {
            const reader = response.body.getReader();
            function push() {
                reader.read().then(({ done, value }) => {
                    if (done) return;
                    sourceBuffer.appendBuffer(value);
                    push();
                });
            }
            sourceBuffer.addEventListener('updateend', push);
            push();
        });
});
```

3. **Or use HLS.js library (simpler):**
```javascript
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
const video = document.getElementById('webcamElement');
if (Hls.isSupported()) {
    const hls = new Hls();
    hls.loadSource('/stream/playlist.m3u8');
    hls.attachMedia(video);
}
</script>
```

4. **Keep rotation/zoom controls working on video element**

**Expected Performance:**
- Server: 30 FPS H.264 encode (hardware assisted, ~1-2 Mbps bitrate)
- Network: 30 FPS (much lower bandwidth than MJPEG)
- Client: 30 FPS hardware decode in browser
- Latency: 1-3 seconds (buffering), configurable

**Complexity Factors:**
- Browser compatibility (Safari vs Chrome MSE differences)
- Codec parameters and browser support (H.264 baseline profile)
- Buffering strategies and latency tuning
- Error recovery and stream reconnection
- Segment timing and synchronization

**Alternative Considered:**
MJPEG streaming (implemented) achieves 30 FPS with moderate complexity. H.264 provides better bandwidth efficiency but significantly higher implementation complexity.

---

## Motion Event Timeline

**Priority:** Medium
**Complexity:** Medium
**Category:** Motion Detection Enhancement

**Description:**
Display a scrollable list/timeline of recent motion events with timestamps.

**Current Limitation:**
- `/health` endpoint only returns latest event timestamp
- No historical event data available

**Backend Requirements:**
1. Add in-memory event history (deque with max size)
2. Store event metadata: timestamp, change percentage, duration
3. New endpoint: `/motion/events` returning last N events

**Example Response:**
```json
{
  "events": [
    {
      "timestamp": 1735154823.456,
      "change_percentage": 12.5,
      "duration": 3.2
    },
    {
      "timestamp": 1735154750.123,
      "change_percentage": 8.7,
      "duration": 1.5
    }
  ],
  "total": 45
}
```

**Frontend Work:**
```javascript
function renderEventLog() {
    fetch('/motion/events')
        .then(r => r.json())
        .then(data => {
            const html = data.events.map(e =>
                `<div class="event">
                    🔴 ${new Date(e.timestamp * 1000).toLocaleString()}
                    (${e.change_percentage.toFixed(1)}% change, ${e.duration.toFixed(1)}s)
                </div>`
            ).join('');
            document.getElementById('eventLog').innerHTML = html;
        });
}
```

---

## Snapshot Gallery (Carousel)

**Priority:** Medium
**Complexity:** Medium
**Category:** Motion Detection Enhancement

**Description:**
Browse through recent snapshots with prev/next buttons or thumbnails.

**Current Limitation:**
- `snapshot_history` stores all snapshots in RAM
- `/motion/snapshot` only returns the latest one
- No way to access historical snapshots

**Backend Requirements:**
1. New endpoint: `/motion/snapshots` returning all or paginated snapshots
2. Optional: `/motion/snapshot/<index>` for specific snapshot

**Example Response:**
```json
{
  "snapshots": [
    {
      "timestamp": 1735154823.456,
      "index": 0,
      "url": "/motion/snapshot/0"
    },
    {
      "timestamp": 1735154750.123,
      "index": 1,
      "url": "/motion/snapshot/1"
    }
  ],
  "count": 15,
  "limit": 50
}
```

**Alternative Approach:**
Return all snapshots as base64-encoded JSON (memory intensive):
```json
{
  "snapshots": [
    {
      "timestamp": 1735154823.456,
      "data": "base64_encoded_jpeg_data_here"
    }
  ]
}
```

**Frontend Work:**
```html
<div id="snapshotGallery">
    <button onclick="prevSnapshot()">‹</button>
    <img id="snapshotPreview" />
    <button onclick="nextSnapshot()">›</button>
    <span id="snapshotIndex">1/10</span>
</div>

<script>
let currentSnapshotIndex = 0;
let snapshots = [];

function loadSnapshots() {
    fetch('/motion/snapshots')
        .then(r => r.json())
        .then(data => {
            snapshots = data.snapshots;
            showSnapshot(0);
        });
}

function showSnapshot(index) {
    if (index < 0 || index >= snapshots.length) return;
    currentSnapshotIndex = index;
    document.getElementById('snapshotPreview').src = snapshots[index].url;
    document.getElementById('snapshotIndex').textContent =
        `${index + 1}/${snapshots.length}`;
}

function nextSnapshot() { showSnapshot(currentSnapshotIndex + 1); }
function prevSnapshot() { showSnapshot(currentSnapshotIndex - 1); }
</script>
```

---

## Statistics Dashboard

**Priority:** Low
**Complexity:** Medium
**Category:** Monitoring

**Description:**
Display detailed server statistics: uptime, total frames captured, memory usage, etc.

**Current Limitation:**
- No tracking of server uptime
- No frame capture counter
- No memory usage reporting

**Backend Requirements:**
1. Track server start time
2. Track total frames captured
3. Calculate memory usage (Python `psutil` library)
4. New endpoint: `/stats`

**Example Response:**
```json
{
  "server": {
    "uptime_seconds": 86400,
    "start_time": 1735068423.456
  },
  "camera": {
    "total_frames_captured": 2592000,
    "frames_per_second": 30
  },
  "memory": {
    "process_rss_mb": 45.2,
    "snapshot_storage_mb": 5.1,
    "snapshot_count": 50
  },
  "motion": {
    "total_events": 127,
    "snapshots_in_ram": 50,
    "current_state": "idle"
  }
}
```

**Frontend Work:**
```html
<div id="stats" class="card">
    <h3>Statistics</h3>
    <div>Uptime: <span id="uptime"></span></div>
    <div>Total Frames: <span id="totalFrames"></span></div>
    <div>Memory Usage: <span id="memUsage"></span></div>
    <div>Motion Events: <span id="totalEvents"></span></div>
</div>

<script>
function updateStats() {
    fetch('/stats')
        .then(r => r.json())
        .then(data => {
            const hours = Math.floor(data.server.uptime_seconds / 3600);
            document.getElementById('uptime').textContent = `${hours}h`;
            document.getElementById('totalFrames').textContent =
                data.camera.total_frames_captured.toLocaleString();
            document.getElementById('memUsage').textContent =
                `${data.memory.process_rss_mb.toFixed(1)} MB`;
            document.getElementById('totalEvents').textContent =
                data.motion.total_events;
        });
}
setInterval(updateStats, 5000);
</script>
```

---

## Motion Heatmap Overlay

**Priority:** Low
**Complexity:** High
**Category:** Advanced Motion Detection

**Description:**
Overlay a visual heatmap showing which regions of the frame triggered motion detection.

**Current Limitation:**
- Motion detection only returns a single percentage
- No per-region data
- Frame comparison happens at pixel level but results are aggregated

**Backend Requirements:**
1. Modify `compare_frames()` to return region data (grid of changed blocks)
2. Add to `/health` or `/motion/status` response
3. Possibly significant CPU overhead

**Example Response:**
```json
{
  "motion": {
    "enabled": true,
    "regions": [
      {"x": 100, "y": 150, "w": 50, "h": 50, "intensity": 0.8},
      {"x": 320, "y": 240, "w": 80, "h": 60, "intensity": 0.6}
    ]
  }
}
```

**Frontend Work:**
```javascript
function drawMotionHeatmap(regions) {
    const ctx = document.getElementById('webcamElement').getContext('2d');
    ctx.save();
    ctx.globalAlpha = 0.5;

    regions.forEach(region => {
        const color = `rgba(255, 0, 0, ${region.intensity})`;
        ctx.fillStyle = color;
        ctx.fillRect(region.x, region.y, region.w, region.h);
    });

    ctx.restore();
}
```

**Alternative Approach:**
Use difference image as grayscale overlay (requires sending full diff image).

---

## Progressive Web App (PWA)

**Priority:** Low
**Complexity:** Medium
**Category:** Platform Enhancement

**Description:**
Allow "installing" to home screen on mobile devices, offline support for UI.

**Current Limitation:**
- No service worker
- No manifest.json
- No offline capability

**Backend Requirements:**
1. Serve `manifest.json` at root
2. Optionally: serve service worker script
3. Update CSP headers if needed

**Frontend Work:**

Create `manifest.json`:
```json
{
  "name": "Pi NOIR Webcam",
  "short_name": "PiWebcam",
  "description": "Raspberry Pi Camera Streaming",
  "start_url": "/webcam.html",
  "display": "standalone",
  "background_color": "#000000",
  "theme_color": "#4CAF50",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

Create `service-worker.js`:
```javascript
const CACHE_NAME = 'piwebcam-v1';
const ASSETS = ['/webcam.html', '/manifest.json'];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
    );
});

self.addEventListener('fetch', (e) => {
    // Don't cache webcam stream, only static assets
    if (e.request.url.includes('webcam.jpg')) {
        return fetch(e.request);
    }

    e.respondWith(
        caches.match(e.request)
            .then(response => response || fetch(e.request))
    );
});
```

Update `webcam.html`:
```html
<head>
    <link rel="manifest" href="/manifest.json">
    <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/service-worker.js');
        }
    </script>
</head>
```

---

## Implementation Priority

**High Value, Low Effort:**
1. Statistics Dashboard (useful for monitoring)

**High Value, Medium Effort:**
2. Motion Event Timeline (provides context)
3. Snapshot Gallery (leverages existing data)

**Low Priority:**
4. Motion Heatmap (advanced feature, high CPU cost)
5. PWA Support (nice-to-have, limited benefit for webcam)

---

## Notes

- All features should maintain RAM-only storage philosophy
- Consider memory limits when adding historical data
- Use `collections.deque` with `maxlen` for bounded history
- Add configuration options for history limits
