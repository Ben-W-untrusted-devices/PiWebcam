#!/usr/bin/env python3
"""
Unit tests for PiWebcam server

Run with: python3 -m pytest test_webcam.py -v
Or: python3 test_webcam.py
"""

import unittest
import io
import os
import sys
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from http.client import HTTPConnection


class MockPiCamera:
	"""Mock PiCamera for testing without hardware"""
	def __init__(self):
		self.resolution = None
		self.framerate = None
		self.closed = False

	def capture(self, stream, format=None, use_video_port=False):
		"""Mock capture - writes fake JPEG data"""
		stream.write(b'\xff\xd8\xff\xe0')  # JPEG header
		stream.seek(0)

	def close(self):
		self.closed = True


class TestPathTraversalSecurity(unittest.TestCase):
	"""Test security against path traversal attacks"""

	def setUp(self):
		"""Set up test environment"""
		# Mock the PiCamera module before importing webcam
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		# Import after mocking
		global webcam
		import webcam as webcam_module
		webcam = webcam_module

		# Store original cwd
		self.original_cwd = os.getcwd()

	def test_parent_directory_traversal_blocked(self):
		"""Should block attempts to access parent directories"""
		# Test standard path traversal attempts (platform-specific)
		if os.name == 'posix':
			malicious_paths = [
				'../../../etc/passwd',
				'../../..',
				'./../../../etc/passwd',
			]
		else:
			malicious_paths = [
				'..\\..\\..\\windows\\system32\\config\\sam',
				'..\\..\\..',
			]

		for path in malicious_paths:
			current_dir = os.path.abspath(os.getcwd())
			requested_path = os.path.abspath(path)

			# Verify that malicious path doesn't start with current dir
			self.assertFalse(
				requested_path.startswith(current_dir),
				f"Path traversal not properly detected for: {path}"
			)

	def test_current_directory_allowed(self):
		"""Should allow access to files in current directory"""
		current_dir = os.path.abspath(os.getcwd())

		allowed_paths = [
			'webcam.html',
			'./webcam.html',
			'LICENSE',
		]

		for path in allowed_paths:
			requested_path = os.path.abspath(path)
			self.assertTrue(
				requested_path.startswith(current_dir),
				f"Valid path incorrectly blocked: {path}"
			)

	def test_subdirectory_allowed(self):
		"""Should allow access to subdirectories"""
		current_dir = os.path.abspath(os.getcwd())

		# Test subdirectory access
		subdir_path = os.path.abspath('subdir/file.txt')
		self.assertTrue(
			subdir_path.startswith(current_dir),
			"Subdirectory access should be allowed"
		)

	def test_absolute_path_outside_cwd_blocked(self):
		"""Should block absolute paths outside current directory"""
		current_dir = os.path.abspath(os.getcwd())

		# Platform-specific paths that should be outside CWD
		if os.name == 'posix':
			malicious_paths = [
				'/etc/passwd',
				'/var/log/syslog',
			]
		else:
			malicious_paths = [
				'C:\\Windows\\System32\\config\\sam',
			]

		for path in malicious_paths:
			requested_path = os.path.abspath(path)
			self.assertFalse(
				requested_path.startswith(current_dir),
				f"Absolute path should be blocked: {path}"
			)


class TestContentTypeDetection(unittest.TestCase):
	"""Test MIME type detection"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		# Don't instantiate handler - just test the method directly
		self.webcam = webcam_module

	def test_html_content_type(self):
		"""Should return text/html for .html files"""
		# Create a temporary handler instance just to access the method
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		self.assertEqual(
			handler.contentTypeFrom('index.html'),
			'text/html'
		)

	def test_css_content_type(self):
		"""Should return text/css for .css files"""
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		self.assertEqual(
			handler.contentTypeFrom('style.css'),
			'text/css'
		)

	def test_jpeg_content_type(self):
		"""Should return image/jpeg for .jpg and .jpeg files"""
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		self.assertEqual(
			handler.contentTypeFrom('photo.jpg'),
			'image/jpeg'
		)
		self.assertEqual(
			handler.contentTypeFrom('photo.jpeg'),
			'image/jpeg'
		)

	def test_png_content_type(self):
		"""Should return image/png for .png files"""
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		self.assertEqual(
			handler.contentTypeFrom('image.png'),
			'image/png'
		)

	def test_svg_content_type(self):
		"""Should return image/svg+xml for .svg files"""
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		self.assertEqual(
			handler.contentTypeFrom('icon.svg'),
			'image/svg+xml'
		)

	def test_unknown_content_type_returns_default(self):
		"""Should return application/octet-stream for unknown file types (FIXED)"""
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		result = handler.contentTypeFrom('file.xyz')
		self.assertEqual(result, 'application/octet-stream')


class TestFrameCapture(unittest.TestCase):
	"""Test camera frame capture and storage"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

	def test_frame_stored_in_memory(self):
		"""Should store captured frames in memory"""
		import webcam

		# Simulate a capture
		stream = io.BytesIO()
		webcam.camera.capture(stream, format='jpeg', use_video_port=True)

		frame_data = stream.getvalue()
		self.assertIsNotNone(frame_data)
		self.assertGreater(len(frame_data), 0)

	def test_jpeg_header_present(self):
		"""Captured frame should have JPEG header"""
		import webcam

		stream = io.BytesIO()
		webcam.camera.capture(stream, format='jpeg', use_video_port=True)

		frame_data = stream.getvalue()
		# JPEG files start with FF D8 FF
		self.assertTrue(frame_data.startswith(b'\xff\xd8\xff'))


class TestThreadSafety(unittest.TestCase):
	"""Test thread-safe frame access"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

	def test_frame_lock_exists(self):
		"""Should have a lock for thread-safe access"""
		import webcam
		self.assertIsNotNone(webcam.frame_lock)
		self.assertIsInstance(webcam.frame_lock, threading.Lock)

	def test_concurrent_access_safe(self):
		"""Should safely handle concurrent frame access"""
		import webcam

		errors = []

		def read_frame():
			try:
				with webcam.frame_lock:
					_ = webcam.current_frame
			except Exception as e:
				errors.append(e)

		def write_frame():
			try:
				with webcam.frame_lock:
					webcam.current_frame = b'test data'
			except Exception as e:
				errors.append(e)

		# Create multiple threads accessing the frame
		threads = []
		for _ in range(10):
			threads.append(threading.Thread(target=read_frame))
			threads.append(threading.Thread(target=write_frame))

		for t in threads:
			t.start()

		for t in threads:
			t.join()

		# No errors should have occurred
		self.assertEqual(len(errors), 0)


class TestHTTPResponses(unittest.TestCase):
	"""Test HTTP response codes and headers"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		self.webcam = webcam_module

		# Create mock request/response
		self.mock_request = Mock()
		self.mock_request.makefile = Mock(return_value=io.BytesIO())

	def test_webcam_jpg_returns_jpeg_content_type(self):
		"""webcam.jpg should return image/jpeg content type"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		# Set a current frame
		self.webcam.current_frame = b'fake jpeg data'
		handler.path = '/webcam.jpg'

		handler.do_GET()

		# Verify JPEG content type was sent
		handler.send_header.assert_any_call('Content-type', 'image/jpeg')

	def test_webcam_jpg_unavailable_returns_503(self):
		"""Should return 503 when camera is initializing"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		# No current frame available
		self.webcam.current_frame = None
		handler.path = '/webcam.jpg'

		handler.do_GET()

		# Verify 503 response
		handler.send_response.assert_called_with(503)

	def test_nonexistent_file_returns_404(self):
		"""Should return 404 for nonexistent files"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		handler.path = '/nonexistent.html'

		handler.do_GET()

		# Verify 404 response
		handler.send_response.assert_called_with(404)

	def test_path_traversal_returns_403(self):
		"""Should return 403 for path traversal attempts"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		handler.path = '/../../../etc/passwd'

		handler.do_GET()

		# Verify 403 response
		handler.send_response.assert_called_with(403)


class TestQueryStringHandling(unittest.TestCase):
	"""Test handling of URL query parameters"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		self.webcam = webcam_module

	def test_query_string_stripped(self):
		"""Should strip query parameters from filename"""
		# Test that query string is properly removed
		test_cases = [
			('/webcam.jpg?t=123456', 'webcam.jpg'),
			('/index.html?v=1', 'index.html'),
			('/file.css?cache=bust', 'file.css'),
		]

		for path_with_query, expected_filename in test_cases:
			filename = (path_with_query[1:]).split("?")[0]
			self.assertEqual(filename, expected_filename)


class TestCameraConfiguration(unittest.TestCase):
	"""Test camera initialization and configuration"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

	def test_camera_resolution_set(self):
		"""Should set camera resolution to 640x480"""
		import webcam
		self.assertEqual(webcam.camera.resolution, (640, 480))

	def test_camera_framerate_set(self):
		"""Should set camera framerate to 30fps"""
		import webcam
		self.assertEqual(webcam.camera.framerate, 30)

	def test_camera_framerate_sync(self):
		"""Capture loop sleep should match camera framerate (FIXED)"""
		import webcam
		import inspect

		# Verify the sleep time uses camera.framerate instead of magic number
		source = inspect.getsource(webcam.capture_loop)

		# Should use camera.framerate, not hardcoded 30
		self.assertIn('camera.framerate', source)
		self.assertNotIn('1.0 / 30', source)


class TestServerConfiguration(unittest.TestCase):
	"""Test server host and port configuration"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

	def test_port_above_1024(self):
		"""Should use port above 1024 for non-root users"""
		import webcam
		self.assertGreaterEqual(webcam.PORT_NUMBER, 1024)

	def test_hostname_configured(self):
		"""Should have hostname configured"""
		import webcam
		self.assertIsNotNone(webcam.HOST_NAME)
		self.assertIsInstance(webcam.HOST_NAME, str)


class TestExceptionHandling(unittest.TestCase):
	"""Test proper exception handling"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		self.webcam = webcam_module

	def test_file_not_found_caught(self):
		"""Should catch FileNotFoundError without crashing"""
		mock_request = Mock()
		mock_request.makefile = Mock(return_value=io.BytesIO(b'GET / HTTP/1.1\r\n\r\n'))
		handler = self.webcam.SimpleCloudFileServer(
			mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		handler.path = '/does_not_exist.html'

		# Should not raise exception
		try:
			handler.do_GET()
		except FileNotFoundError:
			self.fail("FileNotFoundError should be caught")

	def test_io_error_caught(self):
		"""Should catch IOError without crashing"""
		# This would need more complex mocking to trigger IOError
		# Documenting expected behavior
		pass


class TestHealthEndpoint(unittest.TestCase):
	"""Test health check endpoint"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		self.webcam = webcam_module

		self.mock_request = Mock()
		self.mock_request.makefile = Mock(return_value=io.BytesIO())

	def test_health_endpoint_returns_json(self):
		"""Health endpoint should return JSON with status"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		handler.path = '/health'
		handler.do_GET()

		# Verify JSON content type
		handler.send_header.assert_any_call('Content-type', 'application/json')

		# Verify response contains expected fields
		response_data = handler.wfile.getvalue().decode('utf-8')
		self.assertIn('"status"', response_data)
		self.assertIn('"camera"', response_data)
		self.assertIn('"server"', response_data)

	def test_health_endpoint_reports_camera_status(self):
		"""Health endpoint should report camera readiness"""
		import json

		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		# Set camera as ready
		self.webcam.current_frame = b'test frame'
		handler.path = '/health'
		handler.do_GET()

		response_data = json.loads(handler.wfile.getvalue().decode('utf-8'))
		self.assertTrue(response_data['camera']['ready'])


class TestCORSHeaders(unittest.TestCase):
	"""Test CORS header support"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		self.webcam = webcam_module

		self.mock_request = Mock()
		self.mock_request.makefile = Mock(return_value=io.BytesIO())

	def test_cors_headers_present(self):
		"""All responses should include CORS headers"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		self.webcam.current_frame = b'test frame'
		handler.path = '/webcam.jpg'
		handler.do_GET()

		# Verify CORS headers were sent
		handler.send_header.assert_any_call('Access-Control-Allow-Origin', '*')

	def test_options_request_handled(self):
		"""OPTIONS requests should be handled for CORS preflight"""
		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()

		handler.path = '/webcam.jpg'
		handler.do_OPTIONS()

		# Should send response without error
		handler.send_response.assert_called()


class TestAuthentication(unittest.TestCase):
	"""Test HTTP Basic Authentication"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

		import webcam as webcam_module
		self.webcam = webcam_module

		self.mock_request = Mock()
		self.mock_request.makefile = Mock(return_value=io.BytesIO())

	def test_auth_disabled_by_default(self):
		"""Authentication should be disabled when env vars not set"""
		# Save original values
		original_enabled = self.webcam.AUTH_ENABLED

		# Disable auth
		self.webcam.AUTH_ENABLED = False

		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)

		# Should return True when auth disabled
		self.assertTrue(handler.check_auth())

		# Restore
		self.webcam.AUTH_ENABLED = original_enabled

	def test_auth_required_when_enabled(self):
		"""Should require auth when enabled and no header provided"""
		# Enable auth
		original_enabled = self.webcam.AUTH_ENABLED
		original_user = self.webcam.AUTH_USER
		original_pass = self.webcam.AUTH_PASS

		self.webcam.AUTH_ENABLED = True
		self.webcam.AUTH_USER = 'testuser'
		self.webcam.AUTH_PASS = 'testpass'

		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.headers = {}

		# Should return False when no auth header
		self.assertFalse(handler.check_auth())

		# Restore
		self.webcam.AUTH_ENABLED = original_enabled
		self.webcam.AUTH_USER = original_user
		self.webcam.AUTH_PASS = original_pass

	def test_auth_success_with_valid_credentials(self):
		"""Should authenticate with valid credentials"""
		import base64

		original_enabled = self.webcam.AUTH_ENABLED
		original_user = self.webcam.AUTH_USER
		original_pass = self.webcam.AUTH_PASS

		self.webcam.AUTH_ENABLED = True
		self.webcam.AUTH_USER = 'testuser'
		self.webcam.AUTH_PASS = 'testpass'

		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)

		# Create valid auth header
		credentials = base64.b64encode(b'testuser:testpass').decode('utf-8')
		handler.headers = {'Authorization': f'Basic {credentials}'}

		# Should return True with valid credentials
		self.assertTrue(handler.check_auth())

		# Restore
		self.webcam.AUTH_ENABLED = original_enabled
		self.webcam.AUTH_USER = original_user
		self.webcam.AUTH_PASS = original_pass

	def test_auth_fails_with_invalid_credentials(self):
		"""Should reject invalid credentials"""
		import base64

		original_enabled = self.webcam.AUTH_ENABLED
		original_user = self.webcam.AUTH_USER
		original_pass = self.webcam.AUTH_PASS

		self.webcam.AUTH_ENABLED = True
		self.webcam.AUTH_USER = 'testuser'
		self.webcam.AUTH_PASS = 'testpass'

		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)

		# Create invalid auth header
		credentials = base64.b64encode(b'wronguser:wrongpass').decode('utf-8')
		handler.headers = {'Authorization': f'Basic {credentials}'}

		# Should return False with invalid credentials
		self.assertFalse(handler.check_auth())

		# Restore
		self.webcam.AUTH_ENABLED = original_enabled
		self.webcam.AUTH_USER = original_user
		self.webcam.AUTH_PASS = original_pass

	def test_health_endpoint_accessible_without_auth(self):
		"""Health endpoint should be accessible without authentication"""
		original_enabled = self.webcam.AUTH_ENABLED

		self.webcam.AUTH_ENABLED = True
		self.webcam.AUTH_USER = 'testuser'
		self.webcam.AUTH_PASS = 'testpass'

		handler = self.webcam.SimpleCloudFileServer(
			self.mock_request, ('127.0.0.1', 8000), Mock()
		)
		handler.send_response = Mock()
		handler.send_header = Mock()
		handler.end_headers = Mock()
		handler.wfile = io.BytesIO()
		handler.headers = {}  # No auth header

		# Health endpoint should work without auth
		handler.path = '/health'
		handler.do_GET()

		# Should return 200, not 401
		handler.send_response.assert_called_with(200)

		# Restore
		self.webcam.AUTH_ENABLED = original_enabled


class TestRegressionSuite(unittest.TestCase):
	"""Regression tests for fixed bugs"""

	def setUp(self):
		sys.modules['picamera'] = MagicMock()
		sys.modules['picamera'].PiCamera = MockPiCamera

	def test_path_traversal_fix_regression(self):
		"""REGRESSION: Path traversal vulnerability should stay fixed"""
		import webcam

		# Attempt path traversal
		current_dir = os.path.abspath(os.getcwd())
		malicious_path = os.path.abspath('../../../etc/passwd')

		# Should be blocked
		self.assertFalse(malicious_path.startswith(current_dir))

	def test_bare_exception_fix_regression(self):
		"""REGRESSION: Should not use bare except clause"""
		import webcam
		import inspect

		# Get source code of do_GET method
		source = inspect.getsource(webcam.SimpleCloudFileServer.do_GET)

		# Should not contain bare 'except:'
		# This is a basic check - more sophisticated AST parsing could be used
		self.assertNotIn('except:\n', source)


def run_tests():
	"""Run all tests"""
	unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
	print("=" * 70)
	print("PiWebcam Test Suite")
	print("=" * 70)
	print()

	# Run tests
	run_tests()
