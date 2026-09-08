import hashlib


def key(*parts):
    return hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()
