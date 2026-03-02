import hmac, hashlib
# Quick test: verify hmac.new works as expected
sig = hmac.new(b"secret", b"body", hashlib.sha256).hexdigest()
print("hmac.new works:", sig[:20])
