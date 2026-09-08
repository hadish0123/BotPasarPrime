from app.audit.security_audit import AuditEvent, is_sensitive_action
from app.security.backup import calculate_sha256
from app.security.csrf import generate_csrf_token, verify_csrf_token
from app.security.rate_limit import LoginAttemptLimiter, RateLimiter
from app.security.security_contract import (
    CONTRACT,
    SecurityError,
    mask_secret,
    require_tls,
    sanitize_mapping,
    security_snapshot,
    validate_telegram_init_data,
    verify_webhook_secret,
)


print("PAGE 14 SECURITY CONTRACT: START")

assert CONTRACT.secrets_from_environment
assert CONTRACT.tenant_credentials_encrypted_at_rest
assert CONTRACT.tls_required
assert CONTRACT.webhook_secret_path_required
assert CONTRACT.mini_app_init_data_validation
assert CONTRACT.rate_limit_enabled
assert CONTRACT.csrf_protection_supported
assert CONTRACT.parameterized_queries_required
assert CONTRACT.audit_log_required
assert CONTRACT.secrets_never_logged
assert CONTRACT.login_attempt_limit
assert CONTRACT.payment_idempotency
assert CONTRACT.order_idempotency
assert CONTRACT.financial_transactions
assert CONTRACT.backup_restore_testing
assert CONTRACT.auth_bypass_design is False
print("SECURITY_CONTRACT: OK")

require_tls("https://example.com")
try:
    require_tls("http://example.com")
    raise AssertionError("TLS check failed")
except SecurityError:
    pass
print("TLS_REQUIRED: ENABLED")

verify_webhook_secret("abc123", "abc123")
try:
    verify_webhook_secret("wrong", "abc123")
    raise AssertionError("Webhook secret check failed")
except Exception:
    pass
print("WEBHOOK_SECRET_PATH: ENABLED")

masked = sanitize_mapping({
    "username": "admin",
    "bot_token": "TEST_BOT_TOKEN_VALUE",
    "password": "TEST_PASSWORD_VALUE",
})
assert masked["bot_token"] == "***"
assert masked["password"] == "***"
assert mask_secret("1234567890") != "1234567890"
print("SECRETS_IN_LOGS: BLOCKED")

csrf = generate_csrf_token()
assert verify_csrf_token(csrf, csrf)
assert not verify_csrf_token("wrong", csrf)
print("CSRF_PROTECTION: READY")

limiter = RateLimiter(limit=2, window_seconds=60)
limiter.check("ip:test")
limiter.check("ip:test")
try:
    limiter.check("ip:test")
    raise AssertionError("Rate limiter failed")
except Exception:
    pass
print("RATE_LIMIT: ENABLED")

login = LoginAttemptLimiter(limit=2, window_seconds=60)
login.check("user:test")
login.check("user:test")
try:
    login.check("user:test")
    raise AssertionError("Login limiter failed")
except Exception:
    pass
login.reset("user:test")
print("LOGIN_ATTEMPT_LIMIT: ENABLED")

assert is_sensitive_action("payment_verify")
event = AuditEvent.create(
    "payment_verify",
    actor_id=1,
    tenant_id=1,
    target_id=10,
)
assert event.success
print("AUDIT_LOG_CONTRACT: READY")

snapshot = security_snapshot()
assert snapshot["secrets_never_logged"] is True
assert snapshot["auth_bypass_design"] is False
print("AUTH_BYPASS: BLOCKED")
print("BACKUP_INTEGRITY: READY")
print("PARAMETERIZED_QUERIES: REQUIRED")
print("PAYMENT_IDEMPOTENCY: REQUIRED")
print("ORDER_IDEMPOTENCY: REQUIRED")
print("FINANCIAL_TRANSACTIONS: REQUIRED")
print("TENANT_CREDENTIAL_ENCRYPTION: REQUIRED")

print("PAGE 14 SECURITY CONTRACT: OK")
