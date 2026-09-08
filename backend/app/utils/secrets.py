SENSITIVE_KEYS = {
    "token",
    "password",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "encrypted_value",
}


def scrub(data):
    if isinstance(data, dict):
        return {
            k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else scrub(v)) for k, v in data.items()
        }

    if isinstance(data, list):
        return [scrub(x) for x in data]

    return data
