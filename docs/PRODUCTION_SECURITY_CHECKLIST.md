# Production Security Checklist - Auth & Security Hardening

## Overview

This checklist ensures that all security controls from the Auth & Security Hardening implementation are properly configured for production deployment.

## Critical Security Controls

### 1. Environment Configuration

- [ ] **JWT_SECRET is set and secure**
  - Minimum 32 characters
  - Stored securely (not in code repository)
  - Different from development/staging secrets
  - Rotated every 90-180 days

- [ ] **Environment is set to "production"**
  - `ENVIRONMENT=production`
  - Triggers security headers (HSTS, secure cookies)
  - Enables production-specific validation

- [ ] **CORS_ORIGINS is properly configured**
  - No wildcard (`*`) in production
  - Only allows trusted frontend domains
  - No `localhost` in production list

### 2. Webhook Security

- [ ] **RAZORPAY_WEBHOOK_SECRET is configured**
  - Set from Razorpay dashboard
  - Not empty or placeholder value
  - Securely stored (environment variable or secret manager)

- [ ] **WEBHOOK_SKIP_VERIFY is disabled**
  - Set to `false` in production
  - Production guard blocks `true` value
  - Verified in server startup validation

- [ ] **Webhook signature verification is active**
  - Razorpay webhooks are verified before processing
  - Invalid signatures are rejected with 403
  - Audit events are logged for failures

### 3. MFA Configuration

- [ ] **MFA_ENFORCE_FOR_ADMINS is set appropriately**
  - Set to `true` for privileged user protection
  - Or `false` if not yet ready for MFA enforcement

- [ ] **MFA_ENCRYPTION_KEY is configured (if MFA enabled)**
  - Minimum 32 characters
  - Stored securely
  - Required when MFA enforcement is enabled

- [ ] **MFA infrastructure is ready**
  - MFA routes are implemented (`/api/auth/mfa/*`)
  - TOTP secret encryption is working
  - Users can enroll in MFA (if enforced)

### 4. Session Management

- [ ] **Session TTL is appropriate**
  - `ACCESS_TOKEN_TTL_SECONDS` is set (default: 900 = 15min)
  - `REFRESH_TOKEN_TTL_SECONDS` is set (default: 604800 = 7d)
  - Shorter TTL for higher security environments

- [ ] **Concurrent session limit is set**
  - `MAX_SESSIONS_PER_USER` is configured (default: 5)
  - Prevents session exhaustion attacks
  - Oldest sessions are evicted first

- [ ] **Legacy session acceptance is configured**
  - `AUTH_ACCEPT_LEGACY_SESSION=false` after migration
  - Legacy sessions are properly revoked
  - No fallback to insecure session tokens

### 5. Rate Limiting

- [ ] **Rate limiting is configured**
  - `AUTH_RATE_LIMIT_PER_MINUTE` is set (default: 10)
  - Redis URL is configured for multi-instance deployments
  - In-memory fallback is acceptable for single-instance

- [ ] **Redis is available (recommended for production)**
  - `REDIS_URL` is set and accessible
  - Redis connection is tested
  - Fallback to in-memory if Redis unavailable

### 6. Database Security

- [ ] **MongoDB indexes are created**
  - `user_sessions` TTL index on `expires_at`
  - `user_sessions` index on `user_id`
  - `user_sessions` index on `refresh_token_hash`
  - `audit_logs` indexes for queries and TTL

- [ ] **Database connections are secure**
  - MongoDB uses TLS/SSL
  - Database credentials are stored securely
  - Connection strings are not exposed

### 7. Security Headers

- [ ] **Security headers middleware is active**
  - Middleware is mounted on startup
  - Headers include: X-Content-Type-Options, X-Frame-Options, etc.
  - HSTS is enabled in production

- [ ] **CSP is configured correctly**
  - Default CSP is restrictive
  - No `unsafe-inline` in production
  - External scripts are from trusted domains

### 8. CSRF Protection

- [ ] **CSRF middleware is active**
  - Origin/Referer validation is enabled
  - SameSite cookie policy is set correctly
  - Logout cookies have proper attributes

- [ ] **Allowed origins are configured**
  - Origins list matches frontend domains
  - No wildcard in production
  - Proper validation logic is active

### 9. Audit Logging

- [ ] **Audit logs collection exists**
  - `audit_logs` collection is created
  - TTL index is set (default: 90 days)
  - Required indexes are created

- [ ] **Audit events are being emitted**
  - Login/logout events are logged
  - Privilege changes are logged
  - Webhook failures are logged
  - Token reuse is logged

- [ ] **Audit logs are not sensitive**
  - No secrets/tokens in audit logs
  - PII is minimized
  - Sanitization function is working

### 10. Infrastructure Security

- [ ] **Backend is behind load balancer**
  - SSL/TLS termination at load balancer
  - Backend instances are in private subnet
  - Health checks are configured

- [ ] **Database is not publicly accessible**
  - MongoDB is in private network
  - Security groups restrict access
  - Only backend instances can connect

- [ ] **Redis is secured (if used)**
  - Redis AUTH is enabled
  - Redis is in private network
  - TLS is enabled for Redis connections

## Verification Steps

### 1. Startup Validation

Run the following command to verify startup validation:
```bash
cd backend
python server.py
```

Expected output:
- No errors during startup
- "Auth_Module indexes created/verified" message
- "Security middleware added" message
- No validation errors

### 2. Authentication Flow Test

Test the complete authentication flow:
```bash
# Test Google login
curl -X POST https://your-api.com/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{"token": "VALID_GOOGLE_TOKEN"}'

# Test token refresh
curl -X POST https://your-api.com/api/auth/refresh \
  -H "Cookie: refresh_token=VALID_REFRESH_TOKEN"

# Test logout
curl -X POST https://your-api.com/api/auth/logout \
  -H "Cookie: refresh_token=VALID_REFRESH_TOKEN"
```

Expected results:
- Login returns access_token and sets refresh_token cookie
- Refresh returns new access_token and rotates refresh_token
- Logout clears cookies and revokes session

### 3. Security Headers Test

Test security headers:
```bash
curl -I https://your-api.com/api/health
```

Expected headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000` (production only)

### 4. Webhook Verification Test

Test webhook signature verification:
```bash
# Test with invalid signature (should fail)
curl -X POST https://your-api.com/api/prime/webhooks/razorpay \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: invalid_signature" \
  -d '{"event": "payment.captured"}'
```

Expected result:
- HTTP 403 Forbidden
- Audit event logged for verification failure

### 5. Rate Limiting Test

Test rate limiting:
```bash
# Send multiple requests quickly
for i in {1..15}; do
  curl https://your-api.com/api/health
done
```

Expected result:
- First 10 requests succeed (HTTP 200)
- Requests 11+ return HTTP 429
- Retry-After header is present

## Monitoring Setup

### 1. Critical Metrics

Set up monitoring for:
- Authentication failure rate
- Token refresh success rate
- Webhook verification failures
- Rate limit violations
- Audit log volume

### 2. Alert Thresholds

Configure alerts for:
- Authentication failures > 5% of total
- Webhook verification failures (any)
- Token reuse detection events (any)
- Rate limit violations > 10/minute
- Audit log write failures

### 3. Log Aggregation

Ensure logs are aggregated:
- Backend application logs
- Audit logs from MongoDB
- Security events and errors
- Authentication failures

## Deployment Procedure

### 1. Pre-Deployment Checklist

- [ ] All environment variables are set in production
- [ ] Database migrations have been run
- [ ] Auth_Module indexes are created
- [ ] Security tests pass in staging
- [ ] Rollback plan is documented

### 2. Deployment Steps

1. Deploy backend code with Auth_Module
2. Set environment variables
3. Run database migrations if needed
4. Restart backend instances
5. Verify startup validation passes
6. Test authentication flow
7. Monitor logs for errors

### 3. Post-Deployment Verification

- [ ] No authentication errors in logs
- [ ] Webhook verification is working
- [ ] Rate limiting is active
- [ ] Security headers are present
- [ ] Audit logs are being written
- [ ] Performance is acceptable

## Rollback Procedure

If issues occur after deployment:

1. **Immediate rollback**:
   - Revert to previous code version
   - Restore previous environment variables
   - Restart backend instances

2. **Partial rollback**:
   - Disable problematic features via environment variables
   - Example: Set `AUTH_ACCEPT_LEGACY_SESSION=true` if token issues

3. **Emergency measures**:
   - Disable rate limiting if causing issues
   - Disable MFA enforcement if problems
   - Contact security team for guidance

## Incident Response

### 1. Security Incident

If security incident is detected:

1. **Assess scope** of compromise
2. **Rotate JWT_SECRET** immediately
3. **Revoke all sessions** system-wide
4. **Enable additional monitoring**
5. **Investigate logs** for suspicious activity
6. **Document incident** and response

### 2. Performance Issues

If performance degradation occurs:

1. **Check rate limiting** is not too aggressive
2. **Verify Redis** is performing well
3. **Monitor audit log** write performance
4. **Disable non-critical features** if needed
5. **Scale infrastructure** if required

## Maintenance

### Regular Tasks

- **Monthly**: Review audit logs for suspicious patterns
- **Quarterly**: Rotate JWT_SECRET (scheduled)
- **Quarterly**: Review and update CORS origins
- **Semi-annually**: Review and update rate limits
- **Annually**: Complete security audit of auth system

### Documentation Updates

Keep this checklist updated with:
- New security features
- Changed configuration options
- Updated procedures
- Lessons learned from incidents

## Compliance

### SOC 2 Requirements

- ✅ Access control (RBAC, business scoping)
- ✅ System monitoring (audit logs, metrics)
- ✅ Change management (key rotation procedures)
- ✅ Incident response (documented procedures)

### PCI DSS Considerations

- ✅ Webhook signature verification
- ✅ No cardholder data in logs
- ✅ Secure transmission of payment data
- ✅ Access control to payment functions

## Sign-Off

**Completed by**: ___________________  
**Date**: ___________________  
**Environment**: ___________________  
**Notes**: ___________________

## References

- Auth_Module documentation: `backend/auth/`
- JWT Key Rotation procedures: `docs/JWT_KEY_ROTATION.md`
- Requirements: `.kiro/specs/auth-security-hardening/requirements.md`
- Design: `.kiro/specs/auth-security-hardening/design.md`
