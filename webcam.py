#!/usr/bin/python3

import io
import os
import sys
import time
import threading
import base64
import argparse
import logging
import ssl
from picamera import PiCamera

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Configure logging
logger = logging.getLogger('piwebcam')

# Optional dependencies for motion detection
try:
	from PIL import Image
	import numpy as np
	MOTION_DETECTION_AVAILABLE = True
except ImportError as e:
	MOTION_DETECTION_AVAILABLE = False
	MOTION_DETECTION_IMPORT_ERROR = str(e)

# Global variables (will be set by parse_args or defaults)
camera = None
HOST_NAME = None
PORT_NUMBER = None
AUTH_USER = None
AUTH_PASS = None
AUTH_ENABLED = False
JPEG_QUALITY = 85

# In-memory storage for current frame (legacy, for /webcam.jpg compatibility)
current_frame = None
frame_lock = threading.Lock()

# Global performance metrics
stream_fps = 0.0
fps_lock = threading.Lock()

# Streaming output for MJPEG
class StreamingOutput:
	"""Thread-safe output for MJPEG streaming"""
	def __init__(self):
		self.frame = None
		self.buffer = io.BytesIO()
		self.condition = threading.Condition()

	def write(self, buf):
		"""Called by camera for each MJPEG frame"""
		if buf.startswith(b'\xff\xd8'):
			# New frame, store the previous complete frame
			with self.condition:
				self.buffer.truncate()
				self.buffer.seek(0)
				self.buffer.write(buf)
				self.frame = self.buffer.getvalue()
				self.condition.notify_all()

streaming_output = StreamingOutput()

# Motion detector instance (None if disabled)
motion_detector = None

# Motion snapshot configuration (in-memory storage)
MOTION_SNAPSHOT_ENABLED = False
MOTION_SNAPSHOT_LIMIT = 0
snapshot_history = []  # List of (timestamp, bytes) tuples - stored in RAM
snapshot_lock = threading.Lock()  # Protect snapshot_history

# Motion detection functions
def compare_frames(frame1_bytes, frame2_bytes, threshold=5.0):
	"""
	Compare two JPEG frames and return percentage of pixels changed.

	Args:
		frame1_bytes: First frame as JPEG bytes
		frame2_bytes: Second frame as JPEG bytes
		threshold: Pixel difference threshold (0-255) to consider a pixel changed

	Returns:
		Float percentage of pixels changed (0.0-100.0)
		Returns 0.0 if frames cannot be compared
	"""
	if frame1_bytes is None or frame2_bytes is None:
		return 0.0

	try:
		# Load images from bytes
		img1 = Image.open(io.BytesIO(frame1_bytes))
		img2 = Image.open(io.BytesIO(frame2_bytes))

		# Convert to grayscale for efficiency
		img1_gray = img1.convert('L')
		img2_gray = img2.convert('L')

		# Convert to numpy arrays for fast computation
		arr1 = np.array(img1_gray, dtype=np.int16)
		arr2 = np.array(img2_gray, dtype=np.int16)

		# Calculate absolute difference
		diff = np.abs(arr1 - arr2)

		# Count pixels that changed more than threshold
		changed_pixels = np.sum(diff > threshold)

		# Calculate percentage
		total_pixels = arr1.size
		percentage = (changed_pixels / total_pixels) * 100.0

		return percentage

	except Exception as e:
		logger.error(f"Frame comparison error: {e}")
		return 0.0

def save_motion_snapshot(frame_bytes):
	"""
	Save a motion detection snapshot to RAM (in-memory storage).

	Args:
		frame_bytes: JPEG frame to save

	Returns:
		Timestamp of saved snapshot, or None if save failed
	"""
	global snapshot_history

	if not MOTION_SNAPSHOT_ENABLED or frame_bytes is None:
		return None

	try:
		import time
		timestamp = time.time()

		# Thread-safe append to snapshot history
		with snapshot_lock:
			snapshot_history.append((timestamp, frame_bytes))

			# Cleanup old snapshots if limit is set
			if MOTION_SNAPSHOT_LIMIT > 0 and len(snapshot_history) > MOTION_SNAPSHOT_LIMIT:
				# Remove oldest snapshots
				snapshot_history = snapshot_history[-MOTION_SNAPSHOT_LIMIT:]

		logger.info(f"Snapshot saved to RAM: {len(frame_bytes)} bytes, total snapshots: {len(snapshot_history)}")
		return timestamp

	except Exception as e:
		logger.error(f"Failed to save snapshot: {e}")
		return None

# Motion detection state machine
class MotionDetector:
	"""Thread-safe motion detection state machine"""

	# States
	STATE_IDLE = "idle"
	STATE_MOTION_DETECTED = "motion_detected"
	STATE_COOLDOWN = "cooldown"

	def __init__(self, threshold=5.0, cooldown_seconds=5.0):
		"""
		Initialize motion detector.

		Args:
			threshold: Percentage change threshold to trigger motion (0-100)
			cooldown_seconds: Seconds to wait before detecting motion again
		"""
		self.threshold = threshold
		self.cooldown_seconds = cooldown_seconds

		self.state = self.STATE_IDLE
		self.state_lock = threading.Lock()

		self.motion_event_count = 0
		self.last_motion_time = None
		self.last_change_percentage = 0.0

		self.previous_frame = None
		self.baseline_frame = None  # Frame to compare against when detecting motion end

	def check_motion(self, current_frame_bytes):
		"""
		Check if motion is detected in current frame.

		Args:
			current_frame_bytes: Current frame as JPEG bytes

		Returns:
			Tuple of (motion_detected: bool, change_percentage: float)
		"""
		if current_frame_bytes is None:
			return False, 0.0

		with self.state_lock:
			# Need a previous frame to compare
			if self.previous_frame is None:
				self.previous_frame = current_frame_bytes
				self.baseline_frame = current_frame_bytes
				return False, 0.0

			# Check if we're in cooldown
			if self.state == self.STATE_COOLDOWN:
				if self._is_cooldown_expired():
					self.state = self.STATE_IDLE
					self.baseline_frame = current_frame_bytes
					# Fall through to check if this frame triggers new motion
				else:
					# Still in cooldown, don't trigger (no comparison needed)
					return False, self.last_change_percentage

			# Handle state-specific frame comparisons
			if self.state == self.STATE_IDLE:
				# Compare with previous frame to detect motion start
				change_percentage = compare_frames(self.previous_frame, current_frame_bytes)
				self.last_change_percentage = change_percentage
				self.previous_frame = current_frame_bytes

				# Check if motion started
				if change_percentage >= self.threshold:
					# New motion detected!
					self.state = self.STATE_MOTION_DETECTED
					self.motion_event_count += 1
					self.last_motion_time = time.time()
					return True, change_percentage
				else:
					return False, change_percentage

			elif self.state == self.STATE_MOTION_DETECTED:
				# Compare with baseline to detect motion end (optimization: single comparison)
				baseline_change = compare_frames(self.baseline_frame, current_frame_bytes)
				self.last_change_percentage = baseline_change
				self.previous_frame = current_frame_bytes

				if baseline_change < self.threshold:
					# Returned to baseline, motion ended
					self.state = self.STATE_COOLDOWN
					self.last_motion_time = time.time()
					return False, baseline_change
				else:
					# Still away from baseline (motion ongoing)
					self.last_motion_time = time.time()
					return True, baseline_change

			return False, self.last_change_percentage

	def _is_cooldown_expired(self):
		"""Check if cooldown period has expired"""
		if self.last_motion_time is None:
			return True
		elapsed = time.time() - self.last_motion_time
		return elapsed >= self.cooldown_seconds

	def get_status(self):
		"""
		Get current motion detection status.

		Returns:
			Dict with status information (thread-safe)
		"""
		with self.state_lock:
			return {
				"state": self.state,
				"motion_event_count": self.motion_event_count,
				"last_motion_time": self.last_motion_time,
				"last_change_percentage": self.last_change_percentage,
				"threshold": self.threshold,
				"cooldown_seconds": self.cooldown_seconds
			}

	def is_motion_active(self):
		"""Check if motion is currently being detected (thread-safe)"""
		with self.state_lock:
			return self.state == self.STATE_MOTION_DETECTED

# Background monitoring thread for motion detection and performance stats
def monitoring_loop():
	"""Monitor stream frames for motion detection and log performance"""
	global current_frame, motion_detector, streaming_output, stream_fps
	frame_count = 0
	last_perf_log = time.time()
	total_frame_size = 0

	logger.info(f"MJPEG streaming started with quality={JPEG_QUALITY}")

	while True:
		try:
			# Wait for a new frame from the stream
			with streaming_output.condition:
				streaming_output.condition.wait()
				frame_bytes = streaming_output.frame

			if frame_bytes is None:
				continue

			# Update legacy current_frame for /webcam.jpg compatibility
			with frame_lock:
				current_frame = frame_bytes

			total_frame_size += len(frame_bytes)

			# Check for motion if enabled
			if motion_detector is not None:
				motion_detected, change_pct = motion_detector.check_motion(frame_bytes)

				# Log motion events
				if motion_detected:
					status = motion_detector.get_status()
					logger.info(f"Motion detected! Change: {change_pct:.2f}%, Event #{status['motion_event_count']}")

					# Save snapshot if enabled
					if MOTION_SNAPSHOT_ENABLED:
						save_motion_snapshot(frame_bytes)
				else:
					# Log motion ended only when state changes from motion_detected to cooldown
					status = motion_detector.get_status()
					if status['state'] == MotionDetector.STATE_COOLDOWN and change_pct < motion_detector.threshold:
						logger.debug(f"Motion ended. Change: {change_pct:.2f}%")

			# Performance logging every 5 seconds
			frame_count += 1
			if time.time() - last_perf_log >= 5.0:
				avg_size = total_frame_size / frame_count / 1024  # KB
				actual_fps = frame_count / (time.time() - last_perf_log)

				# Update global FPS metric
				with fps_lock:
					stream_fps = actual_fps

				logger.info(f"Stream Performance: {actual_fps:.1f} FPS | Avg Size: {avg_size:.1f}KB")
				frame_count = 0
				last_perf_log = time.time()
				total_frame_size = 0

		except Exception as e:
			logger.error(f"Monitoring error: {e}")
			time.sleep(1)

class SimpleCloudFileServer(BaseHTTPRequestHandler):
	def log_request(self, code='-', size='-'):
		"""Override to control request logging based on log level"""
		# Only log requests if DEBUG level is enabled, or if it's an error
		if logger.isEnabledFor(logging.DEBUG):
			BaseHTTPRequestHandler.log_request(self, code, size)
		elif isinstance(code, int) and code >= 400:
			BaseHTTPRequestHandler.log_request(self, code, size)

	def sendHeader(self, response=200, contentType="image/jpeg"):
		self.send_response(response)
		self.send_header("Content-type", contentType)
		# CORS headers for cross-origin access
		self.send_header("Access-Control-Allow-Origin", "*")
		self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
		self.send_header("Access-Control-Allow-Headers", "Content-Type")
		self.end_headers()
	
	def contentTypeFrom(self, filename):
		if filename.endswith("html"):
			return "text/html"
		elif filename.endswith("css"):
			return "text/css"
		elif filename.endswith("jpg") or filename.endswith("jpeg"):
			return "image/jpeg"
		elif filename.endswith("png"):
			return "image/png"
		elif filename.endswith("svg"):
			return "image/svg+xml"
		else:
			return "application/octet-stream"

	def check_auth(self):
		"""Check HTTP Basic Authentication. Returns True if authorized or auth disabled."""
		if not AUTH_ENABLED:
			return True

		auth_header = self.headers.get('Authorization')
		if auth_header is None:
			return False

		try:
			# Parse "Basic base64string"
			auth_type, auth_string = auth_header.split(' ', 1)
			if auth_type.lower() != 'basic':
				return False

			# Decode credentials
			decoded = base64.b64decode(auth_string).decode('utf-8')
			username, password = decoded.split(':', 1)

			# Verify credentials
			return username == AUTH_USER and password == AUTH_PASS
		except Exception:
			return False

	def send_auth_required(self):
		"""Send 401 Unauthorized response with WWW-Authenticate header"""
		self.send_response(401)
		self.send_header('WWW-Authenticate', 'Basic realm="Webcam Access"')
		self.send_header('Content-type', 'text/plain')
		self.end_headers()
		self.wfile.write(b'401 Unauthorized')

	def do_HEAD(self):
		self.sendHeader()

	def do_OPTIONS(self):
		"""Handle CORS preflight requests"""
		self.sendHeader(contentType="text/plain")
	
	def do_GET(self):
		filename = (self.path[1:]).split("?")[0]

		# Allow health endpoint without auth (for monitoring)
		if filename != "health":
			if not self.check_auth():
				self.send_auth_required()
				return

		# Handle MJPEG stream endpoint
		if filename == "stream":
			self.send_response(200)
			self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			try:
				while True:
					with streaming_output.condition:
						streaming_output.condition.wait()
						frame = streaming_output.frame

					if frame is None:
						continue

					self.wfile.write(b'--FRAME\r\n')
					self.send_header('Content-Type', 'image/jpeg')
					self.send_header('Content-Length', str(len(frame)))
					self.end_headers()
					self.wfile.write(frame)
					self.wfile.write(b'\r\n')
			except (BrokenPipeError, ConnectionResetError):
				logger.debug("Client disconnected from stream")
			except Exception as e:
				logger.error(f"Stream error: {e}")
			return

		# Handle webcam requests - serve from memory (legacy, for compatibility)
		if filename == "webcam.jpg":
			with frame_lock:
				if current_frame is not None:
					self.sendHeader(contentType="image/jpeg")
					self.wfile.write(current_frame)
				else:
					self.sendHeader(response=503, contentType="text/plain")
					self.wfile.write(b"Camera initializing, please wait")
			return

		# Handle health check endpoint
		if filename == "health":
			import json
			with frame_lock:
				camera_ready = current_frame is not None

			# Get current stream FPS
			with fps_lock:
				current_fps = stream_fps

			health_status = {
				"status": "ok",
				"camera": {
					"ready": camera_ready,
					"resolution": f"{int(camera.resolution[0])}x{int(camera.resolution[1])}",
					"framerate": float(camera.framerate)
				},
				"stream": {
					"fps": round(current_fps, 1)
				},
				"server": {
					"host": HOST_NAME,
					"port": PORT_NUMBER
				}
			}

			# Add motion detection status if enabled
			if motion_detector is not None:
				status = motion_detector.get_status()
				health_status["motion"] = {
					"enabled": True,
					"currently_detecting": bool(motion_detector.is_motion_active()),
					"total_events": int(status['motion_event_count']),
					"last_event_time": float(status['last_motion_time']) if status['last_motion_time'] is not None else None
				}
			else:
				health_status["motion"] = {
					"enabled": False
				}

			response_body = json.dumps(health_status, indent=2).encode('utf-8')
			self.sendHeader(contentType="application/json")
			self.wfile.write(response_body)
			return

		# Handle detailed motion status endpoint
		if filename == "motion/status":
			import json
			if motion_detector is None:
				self.sendHeader(response=404, contentType="application/json")
				self.wfile.write(json.dumps({"error": "Motion detection not enabled"}).encode('utf-8'))
				return

			status = motion_detector.get_status()

			# Thread-safe read of snapshot history
			with snapshot_lock:
				snapshot_count = len(snapshot_history)
				latest_timestamp = snapshot_history[-1][0] if snapshot_history else None

			motion_status = {
				"enabled": True,
				"state": status['state'],
				"currently_detecting": motion_detector.is_motion_active(),
				"motion_event_count": status['motion_event_count'],
				"last_motion_time": status['last_motion_time'],
				"last_change_percentage": status['last_change_percentage'],
				"config": {
					"threshold": status['threshold'],
					"cooldown_seconds": status['cooldown_seconds']
				},
				"snapshot": {
					"enabled": MOTION_SNAPSHOT_ENABLED,
					"storage": "RAM (in-memory)",
					"count": snapshot_count,
					"limit": MOTION_SNAPSHOT_LIMIT if MOTION_SNAPSHOT_ENABLED else None,
					"latest_timestamp": latest_timestamp
				}
			}

			response_body = json.dumps(motion_status, indent=2).encode('utf-8')
			self.sendHeader(contentType="application/json")
			self.wfile.write(response_body)
			return

		# Handle latest motion snapshot endpoint
		if filename == "motion/snapshot":
			if motion_detector is None:
				self.sendHeader(response=404, contentType="text/plain")
				self.wfile.write(b"Motion detection not enabled")
				return

			# Thread-safe read of latest snapshot from RAM
			with snapshot_lock:
				if snapshot_history:
					latest_snapshot = snapshot_history[-1][1]  # Get bytes from (timestamp, bytes) tuple
				else:
					latest_snapshot = None

			if not MOTION_SNAPSHOT_ENABLED or latest_snapshot is None:
				self.sendHeader(response=404, contentType="text/plain")
				self.wfile.write(b"No snapshot available")
				return

			# Serve snapshot directly from RAM
			self.sendHeader(contentType="image/jpeg")
			self.wfile.write(latest_snapshot)
			return

		# Handle other file requests (like webcam.html)
		try:
			# Security: Prevent path traversal attacks
			# Get absolute path and ensure it's within current directory
			current_dir = os.path.abspath(os.getcwd())
			requested_path = os.path.abspath(filename)

			# Reject if path tries to escape current directory
			if not requested_path.startswith(current_dir):
				logger.warning(f"Path traversal attempt blocked: {filename}")
				self.sendHeader(response=403, contentType="text/plain")
				self.wfile.write(b"403 Forbidden")
				return

			with open(requested_path, "rb") as in_file:
				data = in_file.read()
				self.sendHeader(contentType=self.contentTypeFrom(filename))
				self.wfile.write(data)
		except (FileNotFoundError, IOError):
			logger.info(f"File not found: {filename}")
			self.sendHeader(response=404, contentType="text/plain")
			self.wfile.write(b"404 file not found")

def parse_args():
	"""Parse command-line arguments"""
	parser = argparse.ArgumentParser(
		description='PiWebcam - Raspberry Pi Camera Streaming Server',
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog='''
Examples:
  %(prog)s                          # Run with defaults
  %(prog)s --port 8080              # Use custom port
  %(prog)s --resolution 1280x720    # HD resolution
  %(prog)s --framerate 15           # Lower framerate
  %(prog)s --no-auth                # Disable authentication
  %(prog)s --motion-detect          # Enable motion detection
  %(prog)s --motion-detect --motion-threshold 3  # Sensitive detection
		'''
	)

	parser.add_argument('--host', default='0.0.0.0',
		help='Host to bind to (default: 0.0.0.0)')
	parser.add_argument('--port', type=int, default=8000,
		help='Port to bind to (default: 8000)')
	parser.add_argument('--resolution', default='640x480',
		help='Camera resolution WIDTHxHEIGHT (default: 640x480)')
	parser.add_argument('--framerate', type=int, default=30,
		help='Camera framerate (default: 30)')
	parser.add_argument('--quality', type=int, default=85,
		help='JPEG quality 1-100, lower=faster encoding (default: 85)')
	parser.add_argument('--no-auth', action='store_true',
		help='Disable authentication even if WEBCAM_USER/WEBCAM_PASS are set')
	parser.add_argument('--log-level', default='INFO',
		choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
		help='Logging level (default: INFO)')

	# SSL/HTTPS arguments
	parser.add_argument('--ssl', action='store_true',
		help='Enable HTTPS with SSL certificate')
	parser.add_argument('--cert', default='cert.pem',
		help='Path to SSL certificate file (default: cert.pem)')
	parser.add_argument('--key', default='key.pem',
		help='Path to SSL private key file (default: key.pem)')

	# Motion detection arguments
	parser.add_argument('--motion-detect', action='store_true',
		help='Enable motion detection (default: disabled)')
	parser.add_argument('--motion-threshold', type=float, default=5.0,
		help='Motion detection threshold percentage 0-100 (default: 5.0)')
	parser.add_argument('--motion-cooldown', type=float, default=5.0,
		help='Seconds between motion events (default: 5.0)')
	parser.add_argument('--motion-snapshot', action='store_true',
		help='Save snapshots to RAM when motion detected (default: disabled)')
	parser.add_argument('--motion-snapshot-limit', type=int, default=0,
		help='Max snapshots to keep in RAM, 0=unlimited (default: 0)')

	return parser.parse_args()

def initialize_camera(resolution_str, framerate):
	"""Initialize and configure camera"""
	global camera, JPEG_QUALITY

	# Parse resolution string
	try:
		width, height = map(int, resolution_str.split('x'))
	except ValueError:
		logger.error(f"Invalid resolution format '{resolution_str}'. Use WIDTHxHEIGHT (e.g., 640x480)")
		sys.exit(1)

	# Validate resolution is within PiCamera supported range
	MAX_WIDTH = 3280  # Pi Camera V2 max
	MAX_HEIGHT = 2464
	MIN_WIDTH = 64
	MIN_HEIGHT = 64

	if not (MIN_WIDTH <= width <= MAX_WIDTH and MIN_HEIGHT <= height <= MAX_HEIGHT):
		logger.error(f"Resolution {width}x{height} out of range. Must be {MIN_WIDTH}-{MAX_WIDTH}x{MIN_HEIGHT}-{MAX_HEIGHT}")
		sys.exit(1)

	# Validate framerate is within PiCamera supported range
	if not 1 <= framerate <= 90:
		logger.error(f"Framerate {framerate} out of range. Must be between 1 and 90 fps")
		sys.exit(1)

	camera = PiCamera()
	camera.resolution = (width, height)
	camera.framerate = framerate

	# Camera warm-up time
	time.sleep(2)
	logger.info(f"Camera initialized: {width}x{height} @ {framerate}fps, quality={JPEG_QUALITY}")

def main():
	"""Main entry point"""
	global HOST_NAME, PORT_NUMBER, AUTH_USER, AUTH_PASS, AUTH_ENABLED, motion_detector
	global MOTION_SNAPSHOT_ENABLED, MOTION_SNAPSHOT_LIMIT, JPEG_QUALITY

	# Parse command-line arguments
	args = parse_args()

	# Configure logging
	log_level = getattr(logging, args.log_level)
	logging.basicConfig(
		level=log_level,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S'
	)

	# Validate port number
	if not 1 <= args.port <= 65535:
		logger.error(f"Port {args.port} must be between 1 and 65535")
		sys.exit(1)

	if args.port < 1024:
		logger.warning(f"Port {args.port} requires root privileges")

	# Validate JPEG quality
	if not 1 <= args.quality <= 100:
		logger.error(f"JPEG quality {args.quality} must be between 1 and 100")
		sys.exit(1)

	JPEG_QUALITY = args.quality
	logger.info(f"Setting JPEG quality to: {JPEG_QUALITY}")

	# Update global configuration
	HOST_NAME = args.host
	PORT_NUMBER = args.port
	AUTH_USER = os.environ.get('WEBCAM_USER')
	AUTH_PASS = os.environ.get('WEBCAM_PASS')
	AUTH_ENABLED = (AUTH_USER is not None and AUTH_PASS is not None) and not args.no_auth

	if AUTH_ENABLED:
		logger.info(f"Authentication enabled for user: {AUTH_USER}")
	else:
		logger.info("Authentication disabled")

	# Initialize motion detection if enabled
	if args.motion_detect:
		# Check if motion detection dependencies are available
		if not MOTION_DETECTION_AVAILABLE:
			logger.error("Motion detection requires PIL (Pillow) and numpy libraries")
			logger.error(f"Import error: {MOTION_DETECTION_IMPORT_ERROR}")
			logger.error("Install with: pip3 install -r requirements.txt")
			sys.exit(1)

		# Validate threshold range
		if not 0 <= args.motion_threshold <= 100:
			logger.error(f"Motion threshold must be between 0 and 100, got {args.motion_threshold}")
			sys.exit(1)

		motion_detector = MotionDetector(
			threshold=args.motion_threshold,
			cooldown_seconds=args.motion_cooldown
		)
		logger.info(f"Motion detection enabled: threshold={args.motion_threshold}%, cooldown={args.motion_cooldown}s")

		# Configure motion snapshots (in-memory storage)
		if args.motion_snapshot:
			# Validate snapshot limit is non-negative
			if args.motion_snapshot_limit < 0:
				logger.error(f"Snapshot limit must be >= 0, got {args.motion_snapshot_limit}")
				sys.exit(1)

			MOTION_SNAPSHOT_ENABLED = True
			MOTION_SNAPSHOT_LIMIT = args.motion_snapshot_limit
			logger.info(f"Motion snapshots enabled: storage=RAM, limit={MOTION_SNAPSHOT_LIMIT if MOTION_SNAPSHOT_LIMIT > 0 else 'unlimited'}")
	else:
		logger.info("Motion detection disabled")

	# Initialize camera
	initialize_camera(args.resolution, args.framerate)

	# Start MJPEG recording to streaming output
	camera.start_recording(streaming_output, format='mjpeg', quality=JPEG_QUALITY)
	logger.info(f"MJPEG recording started: quality={JPEG_QUALITY}")

	# Start background monitoring thread for motion detection
	monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
	monitoring_thread.start()
	logger.info("Monitoring thread started")

	# Start HTTP server (threaded to handle multiple clients)
	httpd = ThreadingHTTPServer((HOST_NAME, PORT_NUMBER), SimpleCloudFileServer)

	# Enable SSL/HTTPS if requested
	if args.ssl:
		if not os.path.exists(args.cert) or not os.path.exists(args.key):
			logger.error(f"SSL certificate or key file not found")
			logger.error(f"  Certificate: {args.cert}")
			logger.error(f"  Key: {args.key}")
			logger.error(f"Generate certificate with: ./generate-cert.sh")
			sys.exit(1)

		context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
		context.load_cert_chain(args.cert, args.key)
		httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
		protocol = "https"
		logger.info("SSL/HTTPS enabled")
	else:
		protocol = "http"

	logger.info(f"Server started on {HOST_NAME}:{PORT_NUMBER}")
	logger.info(f"MJPEG stream available at: {protocol}://{HOST_NAME}:{PORT_NUMBER}/stream")
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		logger.info("Received shutdown signal")
	finally:
		camera.stop_recording()
		camera.close()
		httpd.server_close()
		logger.info("Server stopped")

if __name__ == '__main__':
	main()
