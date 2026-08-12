# Legacy Session Cutover Procedure

## Overview

This document provides the step-by-step procedure for transitioning from legacy session tokens to the new JWT-based authentication system.

## Background

The Auth_Module supports dual-accept mode during migration:
- **JWT access tokens**: New secure tokens (15min TTL, automatic refresh)
- **Legacy session tokens**: Old MongoDB-based sessions (7-day TTL)

The `AUTH_ACCEPT_LEGACY_SESSION` flag controls whether the system accepts legacy sessions during the transition period.

## Prerequisites

Before starting the cutover:
- ✅ Backend Auth_Module is deployed and tested
- ✅ Frontend token transport is updated (access tokens in memory, refresh via cookie)
- ✅ All backend routers are migrated to Auth_Module
- ✅ CI guard for forbidden auth patterns is passing
- ✅ Integration tests are passing
- ✅ Production security checklist is completed

## Phase 1: Dual-Accept Mode (Initial Deployment)

### 1.1 Deploy with Legacy Session Acceptance

Set environment variable to allow both token types:
```bash
AUTH_ACCEPT_LEGACY_SESSION=true
```

### 1.2 Monitor User Experience

Monitor for:
- Authentication failures
- User complaints about login issues
- Token refresh errors
- Audit log events for authentication failures

### 1.3 Metrics to Track

- Legacy session usage (percentage of requests using legacy sessions)
- JWT token usage (percentage of requests using JWT)
- Authentication success rate
- Token refresh success rate
- Session revocation events

### 1.4 Minimum Soak Period

**Minimum: 7 days**
- Ensures all active users have opportunity to re-authenticate
- Allows legacy sessions to naturally expire (7-day TTL)
- Provides time to identify and fix issues

**Recommended: 14 days**
- Two full legacy session expiry cycles
- More comprehensive testing
- Reduced risk of user impact

## Phase 2: Revoke Legacy Sessions

### 2.1 Prepare Revocation Script

Create a script to revoke all legacy sessions:
```python
# revoke_legacy_sessions.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

async def revoke_legacy_sessions():
    """Revoke all legacy session tokens."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Delete all sessions with session_token field (legacy sessions)
    result = await db.user_sessions.delete_many({
        "session_token": {"$exists": true}
    })
    
    print(f"Revoked {result.deleted_count} legacy sessions")
    client.close()

if __name__ == "__main__":
    asyncio.run(revoke_legacy_sessions())
```

### 2.2 Test in Staging

Run the revocation script in staging environment:
```bash
python revoke_legacy_sessions.py
```

Verify:
- Legacy sessions are deleted
- JWT sessions remain intact
- Users can still log in with JWT
- Token refresh works correctly

### 2.3 Schedule Production Revocation

Choose a low-traffic time window:
- Avoid peak business hours
- Consider time zones of all users
- Have rollback plan ready

## Phase 3: Disable Legacy Session Acceptance

### 3.1 Update Environment Variable

Set environment variable to reject legacy sessions:
```bash
AUTH_ACCEPT_LEGACY_SESSION=false
```

### 3.2 Deploy to Production

1. Update environment variable in production
2. Restart all backend instances
3. Verify startup validation passes
4. Monitor for authentication errors

### 3.3 Run Legacy Session Revocation

Execute the revocation script:
```bash
python revoke_legacy_sessions.py
```

### 3.4 Verify System Health

Check:
- Authentication success rate (should remain high)
- No increase in 401 errors
- Token refresh success rate
- User login functionality
- Audit logs for authentication events

## Phase 4: Post-Cutover Monitoring

### 4.1 Monitor Key Metrics

For 7 days after cutover, monitor:
- Authentication failure rate (should be < 1%)
- Token refresh success rate (should be > 99%)
- User login success rate
- Session creation rate
- Audit log events

### 4.2 User Communication

Notify users about the change:
- Email notification before cutover
- In-app notification after cutover
- Support documentation updated
- FAQ for common issues

### 4.3 Rollback Plan

If issues occur, rollback procedure:
1. Set `AUTH_ACCEPT_LEGACY_SESSION=true`
2. Restart backend instances
3. Investigate root cause
4. Fix issue
5. Retry cutover after fix

## Verification Checklist

### Pre-Cutover
- [ ] All backend routers migrated to Auth_Module
- [ ] Frontend token transport updated
- [ ] Integration tests passing
- [ ] Staging environment tested successfully
- [ ] Rollback plan documented
- [ ] Team notified of schedule

### During Cutover
- [ ] Environment variable updated
- [ ] Backend instances restarted
- [ ] Legacy sessions revoked
- [ ] Authentication tests passed
- [ ] Monitoring configured
- [ ] Support team on standby

### Post-Cutover
- [ ] Authentication success rate > 99%
- [ ] Token refresh success rate > 99%
- [ ] No increase in user complaints
- [ ] Audit logs show normal activity
- [ ] Performance metrics stable
- [ ] Security controls active

## Troubleshooting

### Issue: High Authentication Failure Rate

**Symptoms**: Users unable to log in, increased 401 errors

**Solutions**:
1. Check `AUTH_ACCEPT_LEGACY_SESSION` flag
2. Verify JWT_SECRET is set correctly
3. Check frontend token transport
4. Review audit logs for specific errors
5. Consider temporary rollback to investigate

### Issue: Token Refresh Failures

**Symptoms**: Users logged out unexpectedly, refresh errors

**Solutions**:
1. Verify refresh token cookie is being set
2. Check cookie SameSite/Secure attributes
3. Verify CORS configuration
4. Check Redis connectivity (if using)
5. Review token rotation logic

### Issue: Legacy Sessions Still Working

**Symptoms**: Old session tokens still accepted after cutover

**Solutions**:
1. Verify `AUTH_ACCEPT_LEGACY_SESSION=false` is set
2. Restart all backend instances
3. Run legacy session revocation script
4. Check for cached environment variables
5. Verify no code paths bypass the flag

## Timeline Example

### Week 1-2: Initial Deployment
- Deploy with `AUTH_ACCEPT_LEGACY_SESSION=true`
- Monitor usage metrics
- Address any issues

### Week 3-4: Soak Period
- Continue monitoring
- Gather user feedback
- Prepare revocation script

### Week 5: Preparation
- Test revocation in staging
- Schedule production cutover
- Notify users of upcoming change

### Week 6: Cutover
- Set `AUTH_ACCEPT_LEGACY_SESSION=false`
- Revoke legacy sessions
- Monitor closely for 24-48 hours

### Week 7-8: Post-Cutover
- Continue monitoring
- Address any issues
- Complete transition

## Success Criteria

The cutover is considered successful when:
- ✅ Authentication success rate > 99%
- ✅ Token refresh success rate > 99%
- ✅ No legacy session usage in logs
- ✅ User complaints minimal
- ✅ Audit logs show normal activity
- ✅ Performance metrics stable
- ✅ Security controls verified

## Contact Information

For issues during cutover:
- **Primary Contact**: DevOps Team
- **Secondary Contact**: Security Team
- **Escalation**: CTO Office

## References

- Auth_Module documentation: `backend/auth/`
- JWT key rotation: `docs/JWT_KEY_ROTATION.md`
- Production checklist: `docs/PRODUCTION_SECURITY_CHECKLIST.md`
- Design document: `.kiro/specs/auth-security-hardening/design.md`
