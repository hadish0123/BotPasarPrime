from __future__ import annotations

import hashlib
from pathlib import Path


class BackupIntegrityError(Exception):
    pass


def calculate_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(path: str | Path, expected_sha256: str) -> bool:
    actual = calculate_sha256(path)
    if actual != expected_sha256:
        raise BackupIntegrityError("Backup integrity verification failed")
    return True
