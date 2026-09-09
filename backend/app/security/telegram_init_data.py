import hashlib
import hmac
import json
import time
import urllib.parse


def validate_init_data(init_data: str, bot_token: str, max_age: int = 300):
    if not init_data or not bot_token:
        return False, None

    try:
        pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return False, None

    data = dict(pairs)
    received = data.pop("hash", None)
    if not received or len(received) != 64:
        return False, None

    auth_date_raw = data.get("auth_date")
    try:
        auth_date = int(auth_date_raw or 0)
    except (TypeError, ValueError):
        return False, None

    now = int(time.time())
    if auth_date <= 0 or auth_date > now + 30 or now - auth_date > max_age:
        return False, None

    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return False, None

    raw_user = data.get("user")
    if raw_user:
        try:
            data["user"] = json.loads(raw_user)
        except json.JSONDecodeError:
            return False, None

    return True, data
