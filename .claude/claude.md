# PiWebcam Project Configuration

## Issue Tracking

This project uses `ISSUES.md` for tracking **unresolved issues only**.

**CRITICAL RULES:**
- `ISSUES.md` contains ONLY unresolved issues and planned improvements
- When an issue is resolved, move it to `CHANGELOG.md` and remove from `ISSUES.md`
- Always keep `ISSUES.md` synced with reality - update it as you work
- Never let resolved items accumulate in `ISSUES.md`

When working on this codebase:
- Check `ISSUES.md` for known issues before making changes
- Add new issues to `ISSUES.md` when discovered
- **When you resolve an issue:** Add to `CHANGELOG.md` and remove from `ISSUES.md`
- Check `CHANGELOG.md` to see what's already been completed

## Project Overview

PiWebcam is a simple Raspberry Pi camera streaming application consisting of:
- `webcam.py` - Python HTTP server that captures and streams camera frames
- `webcam.html` - Web interface for viewing the stream with rotation controls

## Key Technologies

- Python 3 with `picamera` library
- Built-in HTTP server (`http.server`)
- Vanilla JavaScript (no frameworks)
- Canvas-based image rendering
