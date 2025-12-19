#!/usr/bin/python3

import unittest
import io
from PIL import Image
import numpy as np

# Import the function to test
from webcam import compare_frames


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


if __name__ == '__main__':
	unittest.main()
