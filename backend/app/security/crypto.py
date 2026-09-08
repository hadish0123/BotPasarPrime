from cryptography.fernet import Fernet

from app.core.config import settings


class SecretBox:
    def __init__(self):
        try:
            self.f = Fernet(settings.fernet_key)
        except (TypeError, ValueError):
            self.f = None

    def encrypt(self, v):
        if not self.f:
            raise RuntimeError("FERNET_KEY is not configured")
        return self.f.encrypt(v.encode()).decode()

    def decrypt(self, v):
        if not self.f:
            raise RuntimeError("FERNET_KEY is not configured")
        return self.f.decrypt(v.encode()).decode()

    @staticmethod
    def mask(v):
        return ("*" * max(0, len(v) - 4)) + v[-4:] if v else ""


box = SecretBox()
