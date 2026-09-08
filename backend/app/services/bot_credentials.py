from app.security.crypto import box


def protect_token(token):
    return box.encrypt(token), box.mask(token)
