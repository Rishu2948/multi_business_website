# JWT Key Rotation and Session Revocation Procedures

## Overview

This document provides operational procedures for JWT key rotation and mass session revocation in the multi-business bakery platform's authentication system.

## JWT Key Rotation

### When to Rotate JWT Keys

Rotate JWT keys in the following situations:
- **Scheduled rotation**: Every 90-180 days as security best practice
- **Key compromise**: If JWT_SECRET is suspected to be leaked
- **Security incident**: Any breach that may have exposed the signing key
- **Employee departure**: When personnel with key access leave the organization

### Preparation

1. **Generate new JWT secret**:
   ```bash
   # Generate a cryptographically secure random key (minimum 32 characters)
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Test the new key**:
   - Update `JWT_SECRET` in development/staging environment
   - Test login, token refresh, and API calls
   - Verify no token validation errors

### Rotation Procedure

#### Option 1: Dual-Graceful Rotation (Recommended)

1. **Add new secret as secondary**:
   - Temporarily support both old and new secrets during transition
   - Modify `backend/auth/config.py` to accept multiple secrets
   - Update environment: `JWT_SECRET=old_secret,new_secret`

2. **Update all environments**:
   - Start with development/staging
   - Update production after staging verification
   - Restart all backend instances

3. **Monitor for 24-48 hours**:
   - Watch for authentication failures
   - Monitor error logs for JWT validation errors
   - Verify token refresh works with both keys

4. **Remove old secret**:
   - After all tokens have naturally expired (7 days)
   - Update environment to only use new secret
   - Restart all instances

#### Option 2: Forced Rotation (Emergency Only)

1. **Immediately update JWT_SECRET**:
   - Update environment variable
   - Restart all backend instances immediately

2. **Accept impact**:
   - All existing access tokens will be invalid
   - Users will need to re-authenticate via refresh token
   - If refresh tokens are also compromised, force logout all users

3. **Force logout if needed**:
   ```python
   # Use the revoke_all_sessions function
   from backend.auth.sessions import revoke_all_sessions
   await revoke_all_sessions(db, user_id)
   ```

### Verification

After rotation, verify:
- ✅ New users can log in successfully
- ✅ Existing users can refresh tokens
- ✅ API calls with new tokens work
- ✅ No authentication errors in logs
- ✅ Token expiration still enforced

## Mass Session Revocation

### When to Revoke All Sessions

Revoke all user sessions in these scenarios:
- **Privilege escalation attack**: If admin accounts are compromised
- **Mass compromise**: System-wide security incident
- **Configuration change**: When disabling legacy session acceptance
- **Emergency**: Immediate security response required

### Revoke All Sessions for a User

```python
from backend.auth.sessions import revoke_all_sessions

# Revoke all sessions for a specific user
revoked_count = await revoke_all_sessions(db, user_id)
print(f"Revoked {revoked_count} sessions for user {user_id}")
```

### Revoke All Sessions System-Wide

```python
from backend.auth.sessions import revoke_all_sessions
from motor.motor_asyncio import AsyncIOMotorClient

# Get all users with active sessions
async def revoke_all_system_sessions(db):
    """Revoke all sessions across all users."""
    result = await db.user_sessions.delete_many({})
    return result.deleted_count

# Usage
total_revoked = await revoke_all_system_sessions(db)
print(f"Revoked {total_revoked} total sessions")
```

### Revoke Sessions by Criteria

```python
# Revoke sessions older than a certain date
cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
result = await db.user_sessions.delete_many({
    "created_at": {"$lt": cutoff_date}
})

# Revoke sessions for specific role (emergency)
result = await db.user_sessions.delete_many({
    "user_id": {"$in": compromised_user_ids}
})
```

## Token Family Revocation (Reuse Detection)

The Auth_Module automatically detects refresh token reuse and revokes the entire token family:

```python
from backend.auth.tokens import TokenManager

token_manager = TokenManager(db)

# When reuse is detected, this automatically:
# 1. Identifies the reused token
# 2. Revokes all sessions for that user
# 3. Emits audit event for security monitoring
```

No manual intervention is required - the system handles it automatically.

## Emergency Procedures

### 1. Immediate Security Incident

If JWT secret is compromised:

1. **Generate new secret**
2. **Forced rotation** (see above)
3. **Revoke all sessions** system-wide
4. **Notify users** of required re-login
5. **Monitor logs** for failed authentication attempts

### 2. Account Compromise

If specific admin accounts are compromised:

```python
# Revoke all sessions for compromised user
await revoke_all_sessions(db, compromised_user_id)

# Optional: Reset user role to customer temporarily
await db.users.update_one(
    {"user_id": compromised_user_id},
    {"$set": {"role": "customer"}}
)
```

### 3. Legacy Session Cutover

When disabling `AUTH_ACCEPT_LEGACY_SESSION`:

1. **Set flag to false**:
   ```bash
   AUTH_ACCEPT_LEGACY_SESSION=false
   ```

2. **Revoke all legacy sessions**:
   ```python
   # Delete all sessions with session_token field
   await db.user_sessions.delete_many({
       "session_token": {"$exists": true}
   })
   ```

3. **Monitor** for increased authentication failures

## Monitoring and Alerts

### Key Metrics to Monitor

- **Authentication failure rate**: Spikes may indicate key rotation issues
- **Token refresh rate**: Unusual patterns may indicate token reuse attacks
- **Session revocation events**: Monitor for mass revocations
- **Audit log events**: Watch for `TOKEN_REUSE_DETECTED` events

### Alert Thresholds

Set up alerts for:
- Authentication failures > 5% of total requests
- Token reuse detection events (any occurrence)
- Mass session revocation (>10 users at once)
- Failed webhook signature verification

## Recovery Procedures

### If Key Rotation Fails

1. **Roll back** to previous JWT_SECRET
2. **Investigate** failure cause
3. **Fix issue** (e.g., environment variable not propagated)
4. **Retry** rotation with proper procedure

### If Users Cannot Log In After Rotation

1. **Check** JWT_SECRET is set correctly
2. **Verify** new secret is minimum 32 characters
3. **Restart** all backend instances
4. **Clear** any CDN or proxy caches
5. **Provide** alternative authentication method if needed

## Backup and Recovery

### Backup Required Secrets

- `JWT_SECRET` - JWT signing key
- `MFA_ENCRYPTION_KEY` - MFA secret encryption
- `RAZORPAY_WEBHOOK_SECRET` - Payment webhook verification

### Recovery from Backup

If secrets are lost and no backup exists:

1. **JWT_SECRET**: Generate new secret and force key rotation
2. **MFA_ENCRYPTION_KEY**: Users will need to re-enroll in MFA
3. `RAZORPAY_WEBHOOK_SECRET**: Regenerate from Razorpay dashboard

## SRE Copilot Residual Risk

### Documented Gap

The SRE Copilot Lambda function (if deployed separately) may still use legacy authentication methods. This represents a residual security risk that should be addressed in a future update.

### Mitigation

- Ensure SRE Copilot Lambda is deployed in secure VPC
- Use IAM roles instead of API keys where possible
- Monitor Lambda authentication logs
- Plan migration to use the centralized Auth_Module

## Contact Information

For issues with JWT key rotation or session revocation:
- Contact: Security Team
- Escalation: CTO Office
- Emergency: On-call Security Engineer

## References

- Auth_Module documentation: `backend/auth/`
- Requirements document: `.kiro/specs/auth-security-hardening/requirements.md`
- Design document: `.kiro/specs/auth-security-hardening/design.md`
