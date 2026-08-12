# MFA Setup and Migration Guide

## Overview

This guide provides step-by-step instructions for setting up Multi-Factor Authentication (MFA) enforcement for privileged users in the multi-business bakery platform.

## Prerequisites

Before starting MFA setup, ensure:

- ✅ Auth_Module is deployed and tested
- ✅ Backend server is running with Auth_Module enabled
- ✅ MongoDB is accessible and has required indexes
- ✅ Environment variables are configured
- ✅ Frontend is updated with MFA components
- ✅ Security team has approved MFA enforcement

## Environment Configuration

### Required Environment Variables

Add these to your backend environment configuration:

```bash
# MFA Enforcement
MFA_ENFORCE_FOR_ADMINS=true
MFA_ENCRYPTION_KEY=your_secure_32_char_encryption_key

# Rate Limiting (for MFA attempts)
AUTH_RATE_LIMIT_PER_MINUTE=10

# Existing Auth_Module variables
JWT_SECRET=your_secure_32_char_secret
AUTH_ACCEPT_LEGACY_SESSION=false
```

### Generating Encryption Key

Generate a secure encryption key for MFA secrets:

```bash
# Generate a 32-byte encryption key (Fernet-compatible)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**IMPORTANT**: Store this key securely in your secrets manager. Never commit it to version control.

## Step 1: Backend Setup

### 1.1 Install Dependencies

Ensure the required Python packages are installed:

```bash
cd backend
pip install pyotp cryptography
```

### 1.2 Register MFA Routes

Add the MFA routes to your main application in `server.py`:

```python
from mfa_routes import router as mfa_router

# Register MFA routes
app.include_router(mfa_router)
```

### 1.3 Create MongoDB Indexes

The MFA module requires MongoDB indexes for performance:

```python
# Run during application startup
async def ensure_mfa_indexes(db):
    """Ensure MFA-related MongoDB indexes exist."""
    await db.mfa_pending_enrollments.create_index(
        [("user_id", 1), ("expires_at", 1)],
        expire_after_seconds=600  # 10 minutes TTL
    )
    await db.mfa_pending_enrollments.create_index([("created_at", 1)])
    
    await db.users.create_index([("mfa.enabled", 1)])
    await db.users.create_index([("mfa.last_verified_at", 1)])
```

### 1.4 Restart Backend Server

```bash
# Stop current server
# Set environment variables
export MFA_ENFORCE_FOR_ADMINS=true
export MFA_ENCRYPTION_KEY=your_encryption_key

# Start server
python server.py
```

## Step 2: Frontend Setup

### 2.1 Add MFA Components

The MFA components are already created:
- `frontend/src/components/MFAEnrollment.jsx` - Enrollment UI
- `frontend/src/components/MFAVerification.jsx` - Verification UI

### 2.2 Update Routes (if needed)

Add MFA enrollment route to your React Router if you want a dedicated MFA setup page:

```jsx
// App.jsx or Routes.jsx
import MFAEnrollment from './components/MFAEnrollment';

<Route path="/mfa-setup" element={<MFAEnrollment />} />
```

### 2.3 Add to Admin Profile

Consider adding MFA setup link to the admin profile page:

```jsx
<div className="mfa-section">
  <h3>Multi-Factor Authentication</h3>
  <p>Enhance your account security with MFA</p>
  <button onClick={() => navigate('/mfa-setup')}>
    Enable MFA
  </button>
</div>
```

## Step 3: Initial Migration

### 3.1 Check Current Status

Run the migration script to check MFA enrollment status:

```bash
cd backend
python3 scripts/mfa_migration.py --report
```

Expected output:
```
MFA Enrollment Status Report
Total privileged users: 5
Enrolled in MFA: 0 (0.0%)
Not enrolled: 5

By Role:
  super_admin:
    Total: 1
    Enrolled: 0 (0.0%)
    Not enrolled: 1
  business_admin:
    Total: 3
    Enrolled: 0 (0.0%)
    Not enrolled: 3
  staff:
    Total: 1
    Not enrolled: 1
```

### 3.2 Enable MFA Enforcement

Set the environment variable:

```bash
export MFA_ENFORCE_FOR_ADMINS=true
```

### 3.3 Notify Users

Send communication to privileged users:

**Email Template:**

```
Subject: Important: Multi-Factor Authentication Required

Dear [User Name],

To enhance the security of your privileged account, we are implementing 
Multi-Factor Authentication (MFA) for all admin and staff accounts.

What this means:
- You'll need to enter a code from your authenticator app when logging in
- This adds an extra layer of security to protect your account
- It will take approximately 5 minutes to set up

When to expect this:
- On your next login after [Date], you'll be prompted to enable MFA
- The setup process is simple and we provide backup codes for recovery

If you have questions or need assistance, please contact the support team.

Thank you for helping us keep the platform secure.

Security Team
```

### 3.4 Start Enrollment

Users will be prompted to enroll in MFA on their next login when they:

1. Log in with Google OAuth
2. See "MFA enrollment required" message
3. Follow the enrollment flow:
   - Download authenticator app (Google Authenticator, Authy, etc.)
   - Scan QR code or enter manual secret
   - Enter verification code
   - Save backup codes securely

## Step 4: Monitoring Migration Progress

### 4.1 Track Enrollment Rate

Run the migration script regularly to track progress:

```bash
python3 scripts/mfa_migration.py --report
```

Target: 100% enrollment rate for privileged users

### 4.2 Monitor Authentication Metrics

Watch for:
- MFA verification success rate (target: >98%)
- MFA verification failure rate (should be <2%)
- Account recovery attempts (backup code usage)
- User support requests related to MFA

### 4.3 Dashboard Metrics

Consider adding a simple dashboard to track:
- Total privileged users
- MFA enrollment count
- Enrollment percentage
- Failed verification attempts
- Backup code usage

## Step 5: Troubleshooting

### Common Issues

#### Issue: User sees "MFA enrollment required" but can't complete it

**Symptoms:**
- User gets stuck in enrollment flow
- QR code won't scan
- Verification code always fails

**Solutions:**
1. Verify MFA_ENCRYPTION_KEY is set correctly
2. Check backend logs for encryption errors
3. Ensure user's device clock is synchronized
4. Try manual entry instead of QR code
5. Contact support if issues persist

#### Issue: Authenticator app shows "Invalid Secret"

**Symptoms:**
- User scans QR code but authenticator shows error
- Manual entry doesn't work

**Solutions:**
1. Check that QR code URL is generated correctly
2. Verify browser is not blocking the QR code image
3. Try regenerating the enrollment (cancel and start over)
4. Check that encryption key is the same between frontend and backend

#### Issue: Backup codes don't work

**Symptoms:**
- User enters backup code but it's rejected
- All backup codes fail

**Solutions:**
1. Verify backup codes are being hashed correctly
2. Check that backup codes haven't been used already
3. Ensure case-insensitive comparison
4. Regenerate backup codes if needed

#### Issue: Device trust not working

**Symptoms:**
- User trusts device but still gets MFA prompt
- Device trust expires immediately

**Solutions:**
1. Check that device fingerprinting is working
2. Verify trust duration is set correctly (default: 30 days)
3. Check that device trust data is being saved correctly
4. Review logs for device trust validation errors

## Step 6: Admin Operations

### 6.1 Reset User MFA

If a user loses access to their authenticator:

```bash
# Use the MFA reset script (super_admin only)
python3 -c "
from backend.auth.mfa import reset_mfa
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def reset():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['multi_business_db']
    
    result = await reset_mfa(
        db,
        'user_id_to_reset',
        'admin_user_id',
        '127.0.0.1',
        'User lost authenticator device'
    )
    print(result)

asyncio.run(reset())
"
```

### 6.2 Disable MFA for User

To disable MFA for a specific user (emergency only):

```bash
# Use the MFA disable endpoint
curl -X DELETE http://localhost:8000/api/auth/mfa/disable \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"user_id": "user_id", "reason": "Emergency disable"}'
```

### 6.3 View User MFA Status

```bash
# Use the MFA status endpoint
curl -X GET http://localhost:8000/api/auth/mfa/status \
  -H "Authorization: Bearer <user_token>"
```

## Step 7: Production Deployment

### 7.1 Staging Testing

Before production deployment:

1. Deploy MFA enforcement to staging
2. Test enrollment flow with real users
3. Test verification flow
4. Test backup code recovery
5. Test admin reset flow
6. Verify audit logging

### 7.2 Production Rollout

**Recommended rollout strategy:**

**Phase 1: Soft Launch (Week 1)**
- Enable MFA enforcement in production
- Send user communication
- Monitor metrics and support requests
- Address any issues quickly

**Phase 2: Gradual Enforcement (Week 2-3)**
- Track enrollment progress
- Send reminders to non-enrolled users
- Monitor success rates
- Optimize based on feedback

**Phase 3: Full Enforcement (Week 4)**
- Achieve 100% enrollment rate
- Remove temporary workarounds
- Document final procedures
- Consider requiring MFA for specific operations

### 7.3 Rollback Plan

If issues occur:

1. **Immediate rollback:**
   ```bash
   export MFA_ENFORCE_FOR_ADMINS=false
   # Restart backend
   ```

2. **Partial rollback:**
   - Disable MFA for specific roles (e.g., staff only)
   - Adjust enforcement level
   - Provide alternative authentication method

3. **Emergency measures:**
   - Temporarily allow password-only login
   - Override MFA for specific users
   - Contact security team for guidance

## Step 8: Post-Deployment

### 8.1 Continuous Monitoring

Monitor these metrics:

- MFA enrollment rate (target: 100%)
- MFA verification success rate (target: >98%)
- Backup code usage rate
- Failed verification attempts
- User support tickets related to MFA

### 8.2 Regular Maintenance

**Monthly:**
- Review MFA enrollment status
- Check for users with low backup codes (<3)
- Review audit logs for security events
- Update documentation as needed

**Quarterly:**
- Test MFA enforcement with security audit
- Review and update MFA policies
- Consider adding new authenticator app support
- Rotate encryption key if needed

**Annually:**
- Complete security review of MFA system
- Update MFA technology stack
- Review and enhance backup code recovery
- Update user training materials

## Security Best Practices

### For Users

1. **Backup Codes:**
   - Store backup codes in secure location (password manager)
   - Never share backup codes with anyone
   - Regenerate backup codes if compromised
   - Keep backup codes accessible for recovery

2. **Authenticator App:**
   - Use reputable authenticator apps
   - Keep authenticator app updated
   - Enable backup for authenticator app data
   - Use strong device passcode

3. **Device Trust:**
   - Only trust personal devices
   - Don't trust public/shared devices
   - Revoke device trust when device is lost
   - Review trusted devices regularly

### For Administrators

1. **Key Management:**
   - Rotate encryption keys quarterly
   - Store keys in secure secrets manager
   - Never log encryption keys
   - Use different keys for development/staging/production

2. **User Support:**
   - Provide clear documentation
   - Have escalation process for MFA issues
   - Train support team on MFA troubleshooting
   - Document common issues and solutions

3. **Security Monitoring:**
   - Monitor for MFA bypass attempts
   - Alert on repeated verification failures
   - Investigate unusual backup code usage
   - Regular security audits

## Testing Checklist

### Before Production

- [ ] MFA enrollment flow works smoothly
- [ ] MFA verification flow works correctly
- [ ] Backup code recovery is functional
- [ ] Admin reset flow is operational
- [ ] Device trust management works
- [ ] Audit logging captures all MFA events
- [ ] Rate limiting prevents brute force
- [ ] Security headers are still applied
- [ ] Legacy session acceptance is disabled

### After Production

- [ ] Users can enroll in MFA successfully
- [ ] Users can verify MFA during login
- [ ] Users can recover with backup codes
- [ ] Admins can reset user MFA
- [ ] Metrics show high success rates
- [ ] Support requests are manageable
- [ ] No security incidents related to MFA

## Success Criteria

MFA enforcement is considered successful when:

- ✅ 100% of privileged users are enrolled in MFA
- ✅ MFA verification success rate >98%
- ✅ Backup code recovery is functional
- ✅ User support requests are minimal
- ✅ Security metrics meet requirements
- ✅ Audit logs show proper MFA events
- ✅ System performance is not degraded

## Contact Information

For MFA-related issues:
- **Primary Contact**: Security Team
- **Secondary Contact**: DevOps Team
- **Escalation**: CTO Office

## References

- MFA Requirements: `.kiro/specs/mfa-enforcement/requirements.md`
- MFA Design: `.kiro/specs/mfa-enforcement/design.md`
- JWT Key Rotation: `docs/JWT_KEY_ROTATION.md`
- Production Checklist: `docs/PRODUCTION_SECURITY_CHECKLIST.md`
- Legacy Session Cutover: `docs/LEGACY_SESSION_CUTOVER.md`
