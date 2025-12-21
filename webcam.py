#!/usr/bin/python3

import io
import os
import sys
import time
import threading
import base64
import argparse
import logging
from picamera import PiCamera

from http.server import BaseHTTPRequestHandler, HTTPServer

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

# In-memory storage for current frame
current_frame = None
frame_lock = threading.Lock()

# Motion detector instance (None if disabled)
motion_detector = None

# Motion snapshot configuration
MOTION_SNAPSHOT_ENABLED = False
MOTION_SNAPSHOT_DIR = './snapshots'
MOTION_SNAPSHOT_LIMIT = 0
latest_snapshot_path = None  # Track most recent snapshot
snapshot_lock = threading.Lock()  # Protect latest_snapshot_path

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
	Save a motion detection snapshot to disk.

	Args:
		frame_bytes: JPEG frame to save

	Returns:
		Path to saved snapshot, or None if save failed
	"""
	global latest_snapshot_path

	if not MOTION_SNAPSHOT_ENABLED or frame_bytes is None:
		return None

	try:
		# Ensure snapshot directory exists
		os.makedirs(MOTION_SNAPSHOT_DIR, exist_ok=True)

		# Generate timestamp filename
		from datetime import datetime
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		filename = f"motion_{timestamp}.jpg"
		filepath = os.path.join(MOTION_SNAPSHOT_DIR, filename)

		# Save snapshot
		with open(filepath, 'wb') as f:
			f.write(frame_bytes)

		logger.info(f"Snapshot saved: {filepath}")
		with snapshot_lock:
			latest_snapshot_path = filepath

		# Cleanup old snapshots if limit is set
		if MOTION_SNAPSHOT_LIMIT > 0:
			cleanup_old_snapshots()

		return filepath

	except Exception as e:
		logger.error(f"Failed to save snapshot: {e}")
		return None

def cleanup_old_snapshots():
	"""Remove oldest snapshots if limit exceeded"""
	try:
		# Get all snapshot files
		snapshots = []
		for filename in os.listdir(MOTION_SNAPSHOT_DIR):
			if filename.startswith('motion_') and filename.endswith('.jpg'):
				filepath = os.path.join(MOTION_SNAPSHOT_DIR, filename)
				# Get file modification time
				mtime = os.path.getmtime(filepath)
				snapshots.append((mtime, filepath))

		# Sort by modification time (oldest first)
		snapshots.sort()

		# Remove oldest files if we exceed the limit
		while len(snapshots) > MOTION_SNAPSHOT_LIMIT:
			_, filepath = snapshots.pop(0)
			os.remove(filepath)
			logger.debug(f"Removed old snapshot: {filepath}")

	except Exception as e:
		logger.error(f"Failed to cleanup old snapshots: {e}")

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

			# Compare frames
			change_percentage = compare_frames(self.previous_frame, current_frame_bytes)
			self.last_change_percentage = change_percentage

			# Update previous frame for next comparison
			self.previous_frame = current_frame_bytes

			# Check if we're in cooldown
			if self.state == self.STATE_COOLDOWN:
				if self._is_cooldown_expired():
					self.state = self.STATE_IDLE
					self.baseline_frame = current_frame_bytes
					# Fall through to check if this frame triggers new motion
				else:
					# Still in cooldown, don't trigger
					return False, change_percentage

			# Handle state transitions based on current state
			if self.state == self.STATE_IDLE:
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
				# Always check if we've returned to baseline (motion ended)
				baseline_change = compare_frames(self.baseline_frame, current_frame_bytes)
				if baseline_change < self.threshold:
					# Returned to baseline, motion ended
					self.state = self.STATE_COOLDOWN
					self.last_motion_time = time.time()
					return False, change_percentage
				else:
					# Still away from baseline (motion ongoing)
					if change_percentage >= self.threshold:
						# Update timestamp on significant changes
						self.last_motion_time = time.time()
					return True, change_percentage

			return False, change_percentage

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

# Background capture thread
def capture_loop():
	"""Continuously capture frames from camera to memory"""
	global current_frame, motion_detector
	while True:
		try:
			# Capture to in-memory buffer
			stream = io.BytesIO()
			camera.capture(stream, format='jpeg', use_video_port=True)

			# Thread-safe update of current frame
			frame_bytes = stream.getvalue()
			with frame_lock:
				current_frame = frame_bytes

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

			time.sleep(1.0 / camera.framerate)
		except Exception as e:
			logger.error(f"Capture error: {e}")
			time.sleep(1)

class SimpleCloudFileServer(BaseHTTPRequestHandler):
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

		# Handle webcam requests - serve from memory
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

			health_status = {
				"status": "ok",
				"camera": {
					"ready": camera_ready,
					"resolution": f"{int(camera.resolution[0])}x{int(camera.resolution[1])}",
					"framerate": float(camera.framerate)
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

			# Thread-safe read of snapshot path
			with snapshot_lock:
				snapshot_path = latest_snapshot_path

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
					"directory": MOTION_SNAPSHOT_DIR if MOTION_SNAPSHOT_ENABLED else None,
					"limit": MOTION_SNAPSHOT_LIMIT if MOTION_SNAPSHOT_ENABLED else None,
					"latest": snapshot_path
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

			# Thread-safe read of snapshot path
			with snapshot_lock:
				snapshot_path = latest_snapshot_path

			if not MOTION_SNAPSHOT_ENABLED or snapshot_path is None:
				self.sendHeader(response=404, contentType="text/plain")
				self.wfile.write(b"No snapshot available")
				return

			try:
				with open(snapshot_path, 'rb') as f:
					snapshot_data = f.read()
				self.sendHeader(contentType="image/jpeg")
				self.wfile.write(snapshot_data)
				return
			except (FileNotFoundError, IOError):
				self.sendHeader(response=404, contentType="text/plain")
				self.wfile.write(b"Snapshot file not found")
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
	parser.add_argument('--no-auth', action='store_true',
		help='Disable authentication even if WEBCAM_USER/WEBCAM_PASS are set')
	parser.add_argument('--log-level', default='INFO',
		choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
		help='Logging level (default: INFO)')

	# Motion detection arguments
	parser.add_argument('--motion-detect', action='store_true',
		help='Enable motion detection (default: disabled)')
	parser.add_argument('--motion-threshold', type=float, default=5.0,
		help='Motion detection threshold percentage 0-100 (default: 5.0)')
	parser.add_argument('--motion-cooldown', type=float, default=5.0,
		help='Seconds between motion events (default: 5.0)')
	parser.add_argument('--motion-snapshot', action='store_true',
		help='Save snapshots when motion detected (default: disabled)')
	parser.add_argument('--motion-snapshot-dir', default='./snapshots',
		help='Directory for motion snapshots (default: ./snapshots)')
	parser.add_argument('--motion-snapshot-limit', type=int, default=0,
		help='Max snapshots to keep, 0=unlimited (default: 0)')

	return parser.parse_args()

def initialize_camera(resolution_str, framerate):
	"""Initialize and configure camera"""
	global camera

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
	logger.info(f"Camera initialized: {width}x{height} @ {framerate}fps")

def main():
	"""Main entry point"""
	global HOST_NAME, PORT_NUMBER, AUTH_USER, AUTH_PASS, AUTH_ENABLED, motion_detector
	global MOTION_SNAPSHOT_ENABLED, MOTION_SNAPSHOT_DIR, MOTION_SNAPSHOT_LIMIT

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

		# Configure motion snapshots
		if args.motion_snapshot:
			# Validate snapshot directory is safe
			snapshot_dir = os.path.abspath(args.motion_snapshot_dir)
			unsafe_prefixes = ['/etc', '/root', '/sys', '/proc', '/boot']
			if any(snapshot_dir.startswith(prefix) for prefix in unsafe_prefixes):
				logger.error(f"Unsafe snapshot directory: {snapshot_dir}")
				logger.error(f"Cannot write to system directories: {', '.join(unsafe_prefixes)}")
				sys.exit(1)

			MOTION_SNAPSHOT_ENABLED = True
			MOTION_SNAPSHOT_DIR = snapshot_dir
			MOTION_SNAPSHOT_LIMIT = args.motion_snapshot_limit
			logger.info(f"Motion snapshots enabled: dir={MOTION_SNAPSHOT_DIR}, limit={MOTION_SNAPSHOT_LIMIT}")
	else:
		logger.info("Motion detection disabled")

	# Initialize camera
	initialize_camera(args.resolution, args.framerate)

	# Start background capture thread
	capture_thread = threading.Thread(target=capture_loop, daemon=True)
	capture_thread.start()
	logger.info("Camera capture thread started")

	# Start HTTP server
	server_class = HTTPServer
	httpd = server_class((HOST_NAME, PORT_NUMBER), SimpleCloudFileServer)

	logger.info(f"Server started on {HOST_NAME}:{PORT_NUMBER}")
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		logger.info("Received shutdown signal")
	finally:
		camera.close()
		httpd.server_close()
		logger.info("Server stopped")

if __name__ == '__main__':
	main()
