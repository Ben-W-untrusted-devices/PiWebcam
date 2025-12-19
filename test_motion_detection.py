#!/usr/bin/python3

import unittest
import io
import time
from PIL import Image
import numpy as np

# Import functions and classes to test
from webcam import compare_frames, MotionDetector


class TestFrameComparison(unittest.TestCase):
	"""Unit tests for frame comparison logic"""

	def create_test_frame(self, width=100, height=100, color=128):
		"""Helper to create a test JPEG frame with uniform color"""
		img = Image.new('L', (width, height), color=color)
		buffer = io.BytesIO()
		img.save(buffer, format='JPEG')
		return buffer.getvalue()

	def create_test_frame_with_box(self, width=100, height=100, bg_color=128, box_color=255, box_size=20):
		"""Helper to create a test frame with a white box in the center"""
		img = Image.new('L', (width, height), color=bg_color)
		# Draw a box in the center
		pixels = img.load()
		x_start = (width - box_size) // 2
		y_start = (height - box_size) // 2
		for x in range(x_start, x_start + box_size):
			for y in range(y_start, y_start + box_size):
				pixels[x, y] = box_color
		buffer = io.BytesIO()
		img.save(buffer, format='JPEG')
		return buffer.getvalue()

	def test_identical_frames(self):
		"""Test that identical frames return 0% change"""
		frame = self.create_test_frame(color=128)
		percentage = compare_frames(frame, frame)
		self.assertEqual(percentage, 0.0)

	def test_none_frames(self):
		"""Test that None frames return 0% change"""
		frame = self.create_test_frame()
		self.assertEqual(compare_frames(None, frame), 0.0)
		self.assertEqual(compare_frames(frame, None), 0.0)
		self.assertEqual(compare_frames(None, None), 0.0)

	def test_completely_different_frames(self):
		"""Test frames with completely different colors"""
		frame1 = self.create_test_frame(color=0)    # Black
		frame2 = self.create_test_frame(color=255)  # White
		percentage = compare_frames(frame1, frame2, threshold=5.0)
		# Should be very high percentage (close to 100%)
		self.assertGreater(percentage, 90.0)

	def test_small_change_detection(self):
		"""Test detection of a small change (box in center)"""
		frame1 = self.create_test_frame(width=100, height=100, color=128)
		frame2 = self.create_test_frame_with_box(width=100, height=100, bg_color=128, box_size=20)
		percentage = compare_frames(frame1, frame2, threshold=5.0)
		# 20x20 box in 100x100 image = 4% of pixels
		# Should be around 4%, allowing for JPEG compression artifacts
		self.assertGreater(percentage, 2.0)
		self.assertLess(percentage, 10.0)

	def test_threshold_sensitivity(self):
		"""Test that higher threshold reduces detected changes"""
		frame1 = self.create_test_frame(color=128)
		frame2 = self.create_test_frame(color=130)  # Slightly different

		# Low threshold should detect change
		low_threshold_result = compare_frames(frame1, frame2, threshold=1.0)

		# High threshold should not detect change (difference is only 2)
		high_threshold_result = compare_frames(frame1, frame2, threshold=10.0)

		self.assertGreater(low_threshold_result, high_threshold_result)

	def test_invalid_jpeg_data(self):
		"""Test that invalid JPEG data returns 0% gracefully"""
		frame = self.create_test_frame()
		invalid_data = b"not a jpeg image"
		percentage = compare_frames(frame, invalid_data)
		self.assertEqual(percentage, 0.0)

	def test_different_size_frames(self):
		"""Test comparison of frames with different sizes"""
		frame1 = self.create_test_frame(width=100, height=100)
		frame2 = self.create_test_frame(width=200, height=200)
		# Should handle gracefully (may return 0 or calculate based on smaller)
		percentage = compare_frames(frame1, frame2)
		self.assertGreaterEqual(percentage, 0.0)
		self.assertLessEqual(percentage, 100.0)


class TestMotionDetector(unittest.TestCase):
	"""Unit tests for MotionDetector state machine"""

	def create_test_frame(self, width=100, height=100, color=128):
		"""Helper to create a test JPEG frame"""
		img = Image.new('L', (width, height), color=color)
		buffer = io.BytesIO()
		img.save(buffer, format='JPEG')
		return buffer.getvalue()

	def test_initialization(self):
		"""Test MotionDetector initializes correctly"""
		detector = MotionDetector(threshold=10.0, cooldown_seconds=3.0)
		self.assertEqual(detector.threshold, 10.0)
		self.assertEqual(detector.cooldown_seconds, 3.0)
		self.assertEqual(detector.state, MotionDetector.STATE_IDLE)
		self.assertEqual(detector.motion_event_count, 0)

	def test_first_frame_no_motion(self):
		"""Test that first frame doesn't trigger motion (no previous frame)"""
		detector = MotionDetector(threshold=5.0)
		frame = self.create_test_frame()
		motion_detected, change_pct = detector.check_motion(frame)
		self.assertFalse(motion_detected)
		self.assertEqual(change_pct, 0.0)

	def test_identical_frames_no_motion(self):
		"""Test identical frames don't trigger motion"""
		detector = MotionDetector(threshold=5.0)
		frame = self.create_test_frame(color=128)

		# First frame (baseline)
		detector.check_motion(frame)

		# Second identical frame
		motion_detected, change_pct = detector.check_motion(frame)
		self.assertFalse(motion_detected)
		self.assertEqual(detector.state, MotionDetector.STATE_IDLE)

	def test_motion_detection_trigger(self):
		"""Test that significant change triggers motion detection"""
		detector = MotionDetector(threshold=5.0)
		frame1 = self.create_test_frame(color=0)    # Black
		frame2 = self.create_test_frame(color=255)  # White

		# First frame (baseline)
		detector.check_motion(frame1)

		# Second frame with significant change
		motion_detected, change_pct = detector.check_motion(frame2)
		self.assertTrue(motion_detected)
		self.assertEqual(detector.state, MotionDetector.STATE_MOTION_DETECTED)
		self.assertEqual(detector.motion_event_count, 1)
		self.assertIsNotNone(detector.last_motion_time)

	def test_motion_event_counter(self):
		"""Test that motion event counter increments correctly"""
		detector = MotionDetector(threshold=5.0, cooldown_seconds=0.1)
		frame_still = self.create_test_frame(color=128)
		frame_motion = self.create_test_frame(color=255)

		# Baseline
		detector.check_motion(frame_still)

		# First motion event
		detector.check_motion(frame_motion)
		self.assertEqual(detector.motion_event_count, 1)

		# Back to still (motion ends, enter cooldown)
		detector.check_motion(frame_still)

		# Wait for cooldown to expire
		time.sleep(0.15)

		# Another motion event (should increment counter)
		detector.check_motion(frame_motion)
		self.assertEqual(detector.motion_event_count, 2)

	def test_cooldown_prevents_retriggering(self):
		"""Test that cooldown prevents immediate re-triggering"""
		detector = MotionDetector(threshold=5.0, cooldown_seconds=1.0)
		frame_still = self.create_test_frame(color=128)
		frame_motion = self.create_test_frame(color=255)

		# Baseline
		detector.check_motion(frame_still)

		# Motion detected
		detector.check_motion(frame_motion)
		self.assertEqual(detector.motion_event_count, 1)

		# Back to still (motion ends, enter cooldown)
		detector.check_motion(frame_still)
		self.assertEqual(detector.state, MotionDetector.STATE_COOLDOWN)

		# Try to trigger motion again during cooldown
		motion_detected, _ = detector.check_motion(frame_motion)
		self.assertFalse(motion_detected)  # Should be blocked by cooldown
		self.assertEqual(detector.motion_event_count, 1)  # Counter should not increment

	def test_cooldown_expires(self):
		"""Test that cooldown expires after configured time"""
		detector = MotionDetector(threshold=5.0, cooldown_seconds=0.1)
		frame_still = self.create_test_frame(color=128)
		frame_motion = self.create_test_frame(color=255)

		# Baseline
		detector.check_motion(frame_still)

		# Motion detected
		detector.check_motion(frame_motion)

		# Back to still (enter cooldown)
		detector.check_motion(frame_still)
		self.assertEqual(detector.state, MotionDetector.STATE_COOLDOWN)

		# Wait for cooldown to expire
		time.sleep(0.15)

		# Check that we can trigger motion again
		detector.check_motion(frame_still)  # This should transition from cooldown to idle
		motion_detected, _ = detector.check_motion(frame_motion)
		self.assertTrue(motion_detected)
		self.assertEqual(detector.motion_event_count, 2)

	def test_get_status(self):
		"""Test get_status returns correct information"""
		detector = MotionDetector(threshold=7.5, cooldown_seconds=3.0)
		frame = self.create_test_frame()
		detector.check_motion(frame)

		status = detector.get_status()
		self.assertEqual(status['threshold'], 7.5)
		self.assertEqual(status['cooldown_seconds'], 3.0)
		self.assertEqual(status['state'], MotionDetector.STATE_IDLE)
		self.assertEqual(status['motion_event_count'], 0)

	def test_is_motion_active(self):
		"""Test is_motion_active() returns correct state"""
		detector = MotionDetector(threshold=5.0)
		frame1 = self.create_test_frame(color=128)
		frame2 = self.create_test_frame(color=255)

		# Initially not active
		self.assertFalse(detector.is_motion_active())

		# Baseline
		detector.check_motion(frame1)
		self.assertFalse(detector.is_motion_active())

		# Motion detected
		detector.check_motion(frame2)
		self.assertTrue(detector.is_motion_active())

		# Motion ends
		detector.check_motion(frame1)
		self.assertFalse(detector.is_motion_active())  # In cooldown, not active

	def test_thread_safety(self):
		"""Test that concurrent access is thread-safe"""
		detector = MotionDetector(threshold=5.0)
		frame = self.create_test_frame()

		# Multiple threads calling these should not crash
		import threading

		def check_motion():
			for _ in range(10):
				detector.check_motion(frame)

		def get_status():
			for _ in range(10):
				detector.get_status()

		threads = []
		for _ in range(5):
			threads.append(threading.Thread(target=check_motion))
			threads.append(threading.Thread(target=get_status))

		for t in threads:
			t.start()

		for t in threads:
			t.join()

		# If we get here without deadlock or exception, thread safety is working


if __name__ == '__main__':
	unittest.main()
