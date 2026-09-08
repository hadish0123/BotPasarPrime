import hashlib
import hmac
import urllib.parse


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400):
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received = data.pop("hash", None)
    if not received:
        return False, None
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return False, None
    return True, data
