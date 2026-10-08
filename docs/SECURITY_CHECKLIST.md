# ApplyXAI Agent Security Checklist

## Pre-Build Security Review

### ✓ Secrets Verification

The following secrets must NOT be included in the packaged executable:

- [x] PostgreSQL credentials - Not included (backend-only)
- [x] Razorpay secret keys - Not included (backend-only)
- [x] OpenAI API keys - Not included (user-provided, not in code)
- [x] Server master secrets - Not included (backend-only)
- [x] Application signing secrets - Not included (backend-only)
- [x] Admin credentials - Not included (backend-only)
- [x] `.env` file - Excluded from PyInstaller spec
- [x] `.env.example` - Included but contains no secrets

### ✓ Server Communication

- [x] All production server communication uses HTTPS/WSS
- [x] Plain HTTP only allowed for localhost (development)
- [x] Device token authentication required
- [x] Server can revoke device tokens
- [x] Agent rejects unauthorized commands

### ✓ Local Storage

- [x] Device token stored in `%LOCALAPPDATA%\ApplyXAI\agent\agent.json`
- [x] User data in per-user directory (Windows security boundary)
- [x] LinkedIn password never stored (user signs in manually)
- [x] ApplyXAI password never stored
- [x] No secrets in installation directory

### ✓ Code Review

- [x] No hardcoded credentials in source code
- [x] No hardcoded API keys
- [x] No hardcoded passwords
- [x] Logging excludes sensitive data (passwords, tokens, keys)
- [x] Error messages don't leak sensitive information

### ✓ PyInstaller Configuration

- [x] Backend excluded from build
- [x] Frontend excluded from build
- [x] Tests excluded from build
- [x] Development files excluded
- [x] `.env` files excluded
- [x] Logs directory excluded
- [x] Storage directory excluded

### ✓ Windows Installer

- [x] No silent installation of Chrome
- [x] User must opt-in for Windows startup
- [x] Admin privileges required (prevents tampering)
- [x] Uninstaller clean and complete
- [x] User data preserved on uninstall

## Runtime Security

### ✓ Authentication

- [x] Device token authentication
- [x] Server validates device tokens
- [x] Server can revoke tokens
- [x] Pairing codes are short-lived (10 minutes)
- [x] Pairing codes are single-use
- [x] Pairing codes tied to authenticated user

### ✓ Authorization

- [x] Server derives identity from authenticated credentials
- [x] Agent never trusts user ID from local client
- [x] Plan limits enforced on server
- [x] Server validates all commands

### ✓ Data Protection

- [x] LinkedIn credentials never transmitted
- [x] User signs in to LinkedIn in their own browser
- [x] ApplyXAI never sees LinkedIn password
- [x] Job application data transmitted over HTTPS
- [x] Resume downloaded over HTTPS

### ✓ Process Security

- [x] Agent runs as user (not system)
- [x] No privilege escalation
- [x] No system-wide installations without admin
- [x] Chrome profile isolated per user

## Post-Build Verification

### Manual Checks

1. Scan executable for hardcoded strings:
   ```powershell
   strings ApplyXAI-Agent.exe | findstr /i "password secret key token"
   ```
   Expected: No sensitive strings found

2. Check for environment files:
   ```powershell
   strings ApplyXAI-Agent.exe | findstr /i ".env"
   ```
   Expected: No .env file paths

3. Verify backend modules excluded:
   ```powershell
   strings ApplyXAI-Agent.exe | findstr /i "sqlalchemy psycopg redis celery"
   ```
   Expected: No backend dependency strings

4. Check for test code:
   ```powershell
   strings ApplyXAI-Agent.exe | findstr /i "pytest test_"
   ```
   Expected: No test code

### Automated Checks

Run these tests before release:

```powershell
# Test that agent imports successfully
.\ApplyXAI-Agent.exe --help

# Test status command
.\ApplyXAI-Agent.exe status

# Test invalid pairing code is rejected
.\ApplyXAI-Agent.exe pair --server https://app.applyxai.com --code INVALID
# Expected: Error message

# Test unpair works
.\ApplyXAI-Agent.exe unpair

# Test configuration paths work outside repository
cd C:\Temp
C:\Path\To\ApplyXAI-Agent.exe status
```

## Known Limitations

### Current Version (1.0.0)

1. **Device token storage**: Tokens stored in plain text in `agent.json`
   - Risk: Malware with user privileges could read tokens
   - Mitigation: Use Windows Credential Manager in future version
   - Acceptable for MVP: Requires local system access

2. **No code signing**: Executable not digitally signed
   - Risk: Windows may show SmartScreen warning
   - Mitigation: Sign with code signing certificate in future
   - Acceptable for MVP: Users can bypass warning

3. **No automatic updates**: Updates must be manual
   - Risk: Users may miss security updates
   - Mitigation: Update check UI (planned for v1.1)
   - Acceptable for MVP: Security impact low

4. **Chrome auto-download**: undetected-chromedriver downloads ChromeDriver
   - Risk: Downloaded from internet at runtime
   - Mitigation: Bundle ChromeDriver in future version
   - Acceptable for MVP: Uses official Selenium infrastructure

## Security Best Practices for Users

1. **Run as standard user**: Don't run as administrator unless necessary
2. **Keep Windows updated**: Install security patches
3. **Use strong passwords**: For ApplyXAI account
4. **Enable 2FA**: On ApplyXAI account when available
5. **Review pairing**: Remove unknown devices from Automation page
6. **Monitor logs**: Check for unusual activity
7. **Uninstall when not needed**: Remove agent if not using service

## Security Incident Response

If a security issue is discovered:

1. **Stop the agent**: Close the application
2. **Unpair the device**: Remove from Automation page
3. **Change password**: ApplyXAI account password
4. **Review activity**: Check job application history
5. **Contact support**: Report the issue
6. **Reinstall**: After issue is resolved

## Compliance

### Data Privacy

- [x] User data stored locally
- [x] No data transmitted without consent
- [x] LinkedIn credentials never transmitted
- [x] User can delete all data locally

### Platform Terms

- [x] Respects LinkedIn's terms of service
- [x] User signs in manually (no credential harvesting)
- [x] No CAPTCHA bypass
- [x] Respects rate limits

## Future Security Enhancements

### v1.1 Planned

- [ ] Windows Credential Manager for token storage
- [ ] Code signing certificate
- [ ] Automatic update checks
- [ ] Bundled ChromeDriver (no runtime download)
- [ ] Enhanced logging with sensitive data redaction

### v2.0 Planned

- [ ] Hardware-based device binding
- [ ] Encrypted local storage
- [ ] Certificate pinning for HTTPS
- [ ] Audit logging
- [ ] Security health checks

## Sign-Off

- [ ] Security review completed by: _______________ Date: _______
- [ ] Build tested and verified by: _______________ Date: _______
- [ ] Approved for release by: _______________ Date: _______
