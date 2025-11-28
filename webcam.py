#!/usr/bin/python3

import time
import threading
from picamera import PiCamera

from http.server import BaseHTTPRequestHandler, HTTPServer

camera = PiCamera()
camera.resolution = (640, 480)
camera.framerate = 30
#camera.start_preview()

#camera warm-up time
time.sleep(2)

# hosting
HOST_NAME = "pi-noir-camera.local"
PORT_NUMBER = 8000 # Magic number. Can't bind under 1024 on normal user accounts; port 80 is the normal HTTP port
WEBCAM_FILENAME = "/tmp/webcam.jpg"  # Use RAM disk for fast I/O

# Background capture thread
def capture_loop():
	"""Continuously capture frames from camera to file"""
	while True:
		try:
			camera.capture(WEBCAM_FILENAME, use_video_port=True)
			time.sleep(1.0 / 30)  # 30 fps
		except Exception as e:
			printServerMessage(f"Capture error: {e}")
			time.sleep(1)

class SimpleCloudFileServer(BaseHTTPRequestHandler):
	def sendHeader(self, response=200, contentType="image/jpeg"):
		self.send_response(response)
		self.send_header("Content-type", contentType)
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
	
	def do_HEAD(self):
		self.sendHeader()
	
	def do_GET(self):
		filename = (self.path[1:]).split("?")[0]

		# Handle webcam requests - just serve the continuously updated file
		if filename == "webcam.jpg":
			filename = WEBCAM_FILENAME

		try:
			with open(filename, "rb") as in_file:
				data = in_file.read()
				self.sendHeader(contentType=self.contentTypeFrom(filename))
				self.wfile.write(data)
		except:
			printServerMessage("File not found: " + filename)
			self.sendHeader(response=404, contentType="text/plain")
			self.wfile.write(b"404 file not found")

def printServerMessage(customMessage):
	print(customMessage, "(Time: %s, Host: %s, port: %s)" % (time.asctime(), HOST_NAME, PORT_NUMBER))
	
if __name__ == '__main__':
	# Start background capture thread
	capture_thread = threading.Thread(target=capture_loop, daemon=True)
	capture_thread.start()
	printServerMessage("Camera capture thread started")

	# Start HTTP server
	server_class = HTTPServer
	httpd = server_class((HOST_NAME, PORT_NUMBER), SimpleCloudFileServer)

	printServerMessage("Server startup")
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		pass
	httpd.server_close()
	printServerMessage("Server stop")
