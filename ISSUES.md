# PiWebcam Issues

> **IMPORTANT:** This file tracks ONLY unresolved issues and planned improvements.
> Completed work is documented in [CHANGELOG.md](CHANGELOG.md).
> When working on this codebase, always keep this file synced with reality.

---

## In Progress

_No issues currently in progress_

---

## Current Issues

### HTTPS Support
**Priority:** Low
**Complexity:** High

**Issue:**
All traffic (including credentials if auth is enabled) is sent unencrypted over HTTP.

**Recommendation:**
Use a reverse proxy (nginx/Apache) with SSL rather than implementing HTTPS directly in Python. This is the standard production approach.

**Example nginx config:**
```nginx
server {
    listen 443 ssl;
    server_name camera.example.com;

    ssl_certificate /etc/letsencrypt/live/camera.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/camera.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
    }
}
```

---

---

## Future Considerations (Not Yet Planned)

### Credential Storage
**Status:** Deferred - current env var approach has limitations

**Current limitations:**
- Environment variables visible in process list
- Not persistent across reboots
- Stored in shell history
- Can't change without restart

**Possible approaches:**
- Config file with bcrypt-hashed passwords (chmod 600)
- Systemd EnvironmentFile
- System keyring integration

**Decision:** Defer until deployment requirements are clearer. Environment variables work well enough for most use cases, especially with systemd EnvironmentFile.

---

## Contributing

When adding issues to this file:
- Only add **unresolved** issues
- Include priority and complexity estimates
- Provide clear problem description
- Suggest potential solutions
- When resolved, move to CHANGELOG.md and remove from here
