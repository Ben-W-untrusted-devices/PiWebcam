# PiWebcam Test Suite

## Overview

Comprehensive unit test suite for the PiWebcam project covering security, functionality, and regression testing.

## Running Tests

### Option 1: Using pytest (recommended)

```bash
# Install test dependencies
pip3 install -r requirements-test.txt

# Run all tests with verbose output
python3 -m pytest test_webcam.py -v

# Run with coverage report
python3 -m pytest test_webcam.py -v --cov=webcam --cov-report=html

# Run specific test class
python3 -m pytest test_webcam.py::TestPathTraversalSecurity -v

# Run specific test
python3 -m pytest test_webcam.py::TestPathTraversalSecurity::test_parent_directory_traversal_blocked -v
```

### Option 2: Using unittest directly

```bash
# No dependencies needed
python3 test_webcam.py
```

## Test Categories

### 1. Security Tests (`TestPathTraversalSecurity`)
**Critical regression tests** to prevent security vulnerabilities:
- ✅ Parent directory traversal blocked
- ✅ Current directory access allowed
- ✅ Subdirectory access allowed
- ✅ Absolute paths outside CWD blocked
- ✅ Various encoding attempts blocked

### 2. Content Type Detection (`TestContentTypeDetection`)
Tests MIME type detection for different file types:
- ✅ HTML files → `text/html`
- ✅ CSS files → `text/css`
- ✅ JPEG files → `image/jpeg`
- ✅ PNG files → `image/png`
- ✅ SVG files → `image/svg+xml`
- ⚠️ Unknown types → `None` (should return `application/octet-stream`)

### 3. Frame Capture (`TestFrameCapture`)
Tests camera frame capture and storage:
- ✅ Frames stored in memory
- ✅ JPEG header validation

### 4. Thread Safety (`TestThreadSafety`)
Tests concurrent access to shared resources:
- ✅ Frame lock exists
- ✅ Concurrent read/write operations safe

### 5. HTTP Responses (`TestHTTPResponses`)
Tests correct HTTP status codes and headers:
- ✅ `webcam.jpg` returns `image/jpeg` content type
- ✅ Camera initializing returns `503 Service Unavailable`
- ✅ Nonexistent files return `404 Not Found`
- ✅ Path traversal returns `403 Forbidden`

### 6. Query String Handling (`TestQueryStringHandling`)
Tests URL parameter handling:
- ✅ Query parameters properly stripped from filenames

### 7. Camera Configuration (`TestCameraConfiguration`)
Tests camera initialization:
- ✅ Resolution set to 640x480
- ✅ Framerate set to 30fps
- ⚠️ Capture loop sleep time hardcoded (should use `camera.framerate`)

### 8. Server Configuration (`TestServerConfiguration`)
Tests server setup:
- ✅ Port above 1024 (for non-root users)
- ✅ Hostname configured

### 9. Exception Handling (`TestExceptionHandling`)
Tests error handling:
- ✅ `FileNotFoundError` caught properly
- ✅ `IOError` caught properly

### 10. Regression Suite (`TestRegressionSuite`)
**Critical tests** to prevent reintroduction of fixed bugs:
- ✅ Path traversal vulnerability stays fixed
- ✅ No bare `except:` clauses

## Test Coverage

Current test coverage areas:
- **Security**: Path traversal, directory restrictions
- **HTTP**: Response codes, headers, content types
- **Threading**: Lock mechanisms, concurrent access
- **Camera**: Configuration, capture functionality
- **Error Handling**: Exception catching, error responses
- **Regression**: Previously fixed bugs

## Known Issues Documented in Tests

The test suite documents known issues from `ISSUES.md`:
- **Issue #4**: `contentTypeFrom()` returns `None` instead of default
- **Issue #6**: Capture loop uses magic number instead of `camera.framerate`

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip3 install -r requirements-test.txt
    python3 -m pytest test_webcam.py -v --cov=webcam
```

## Adding New Tests

When adding features or fixing bugs:

1. Add tests to appropriate test class
2. For security fixes, add regression test to `TestRegressionSuite`
3. Update this README with new test coverage
4. Run full test suite before committing

## Test Maintenance

- Run tests before every commit
- Update tests when changing functionality
- Add regression tests for every bug fix
- Keep test coverage above 80%
