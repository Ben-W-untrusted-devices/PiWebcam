# PiWebcam Project Configuration

## Issue Tracking

This project uses `ISSUES.md` as the issue tracker for bugs, improvements, and technical debt.

When working on this codebase:
- Check `ISSUES.md` for known issues before making changes
- Add new issues to `ISSUES.md` when discovered
- Update or remove issues from `ISSUES.md` when resolved

## Project Overview

PiWebcam is a simple Raspberry Pi camera streaming application consisting of:
- `webcam.py` - Python HTTP server that captures and streams camera frames
- `webcam.html` - Web interface for viewing the stream with rotation controls

## Key Technologies

- Python 3 with `picamera` library
- Built-in HTTP server (`http.server`)
- Vanilla JavaScript (no frameworks)
- Canvas-based image rendering
