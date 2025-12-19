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

# Background capture thread
def capture_loop():
	"""Continuously capture frames from camera to memory"""
	global current_frame
	while True:
		try:
			# Capture to in-memory buffer
			stream = io.BytesIO()
			camera.capture(stream, format='jpeg', use_video_port=True)

			# Thread-safe update of current frame
			with frame_lock:
				current_frame = stream.getvalue()

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
					"resolution": f"{camera.resolution[0]}x{camera.resolution[1]}",
					"framerate": camera.framerate
				},
				"server": {
					"host": HOST_NAME,
					"port": PORT_NUMBER
				}
			}

			response_body = json.dumps(health_status, indent=2).encode('utf-8')
			self.sendHeader(contentType="application/json")
			self.wfile.write(response_body)
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

	camera = PiCamera()
	camera.resolution = (width, height)
	camera.framerate = framerate

	# Camera warm-up time
	time.sleep(2)
	logger.info(f"Camera initialized: {width}x{height} @ {framerate}fps")

def main():
	"""Main entry point"""
	global HOST_NAME, PORT_NUMBER, AUTH_USER, AUTH_PASS, AUTH_ENABLED

	# Parse command-line arguments
	args = parse_args()

	# Configure logging
	log_level = getattr(logging, args.log_level)
	logging.basicConfig(
		level=log_level,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S'
	)

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
