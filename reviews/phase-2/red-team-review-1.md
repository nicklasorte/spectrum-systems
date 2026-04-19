# Phase 2 Red Team Review #1

**Date**: April 2026  
**Scope**: Persistent Backend, Prompt Injection Boundary, Replay Infrastructure  
**Findings**: 10 issues (1 critical, 6 high, 3 medium)  

## Critical Issues

### 1. S3 Access Control Not Documented
- **Risk**: Artifacts publicly readable if bucket policy is misconfigured
- **Evidence**: `postgres-backend.ts` creates S3 client but no IAM policy enforcement documented
- **Fix**: Document required IAM policy, enforce least-privilege bucket settings
- **Owner**: Infrastructure team
- **Deadline**: Before production

### 2. Audit Log Not Immutable
- **Risk**: Malicious actor deletes decision records to hide control decisions
- **Evidence**: `audit_log` table has no CHECK constraints or append-only enforcement
- **Fix**: Add CHECK constraints, implement append-only archive table, disable DELETE
- **Owner**: DB team
- **Deadline**: Before production

### 3. Injection Bypass via Character Encoding
- **Risk**: Unicode escapes, ROT13, or base64 bypass detection regex
- **Evidence**: `detectInjectionAttempts()` uses simple regex without normalization
- **Fix**: Normalize unicode, decode common encodings before pattern matching
- **Owner**: Security team
- **Deadline**: Before production

### 4. ReplayBundle Not Signed
- **Risk**: Attacker modifies seeds/model versions post-hoc to change output
- **Evidence**: `ReplayBundle` stored but not HMAC'd or signed
- **Fix**: Add cryptographic signature (HMAC-SHA256) to bundle
- **Owner**: Security team
- **Deadline**: Before production

## High Priority Issues

### 5. Database Credentials in Environment Variables
- **Risk**: Credentials in plaintext in environment, visible in process listings
- **Evidence**: `postgres-factory.ts` reads PG_PASSWORD from env
- **Fix**: Integrate with Vault/SecretsManager, not env vars
- **Owner**: Infrastructure team
- **Timeline**: Before production

### 6. Injection Boundary Not Uniform Across All MVPs
- **Risk**: MVP-11 (Revision Integration) lacks injection hardening
- **Evidence**: Only MVP-4 has `minutes-extraction-agent-injection-hardened.ts`
- **Fix**: Apply boundary enforcement to MVP-5, MVP-8, MVP-11
- **Owner**: Security team
- **Timeline**: Before Phase 2 completion

### 7. Match Rate Calculation Vulnerable to Forgery
- **Risk**: Non-deterministic step outputs `{"result":"deterministic"}` every time, passes replay check
- **Evidence**: `computeMatchRate()` only compares JSON fields, ignores semantic content
- **Fix**: Implement content-aware comparison or cryptographic hash of outputs
- **Owner**: Architecture team
- **Timeline**: Before Phase 2 completion

### 8. Expired Overrides Not Purged Automatically
- **Risk**: Stale override records accumulate, cause policy confusion
- **Evidence**: `getOverrideBacklog()` filters expired but no cleanup job exists
- **Fix**: Add scheduled purge job (cron/Lambda) to archive expired overrides
- **Owner**: Operations team
- **Timeline**: Q2 2026

## Medium Priority Issues

### 9. Backup/Recovery Strategy Absent
- **Risk**: Data loss or corruption recovery undefined
- **Evidence**: No documented backup frequency, retention, or restore testing
- **Fix**: Document PostgreSQL backup strategy, test restore procedure
- **Owner**: Operations team
- **Timeline**: Q2 2026

### 10. Input Truncation Applied After Injection Detection
- **Risk**: Very large transcript could cause buffer issues before detection
- **Evidence**: `sanitizeForLLMContext()` truncates at 100KB after removing patterns
- **Fix**: Truncate first to 100KB, then apply injection detection
- **Owner**: Security team
- **Timeline**: Next sprint

## Summary

**Blockers for production**: Issues 1–4  
**Blockers for Phase 2 completion**: Issues 5–7  
**Later**: Issues 8–10  

All findings addressed via Fix Slice #1 (forthcoming).

---

**Red Team Lead**: [Security Team]  
**Review Method**: Code review + threat modeling  
**Follow-up**: Fix verification testing required before merge
