"""Stable machine fingerprint for ticket/machine binding.

Derives a short, stable id from the host so the Worker can detect when the
same install ticket is presented from a different machine (a leaked-ticket
signal). It intentionally avoids anything privacy-sensitive or volatile —
just hostname + OS + architecture, hashed.
"""

from __future__ import annotations

import functools
import hashlib
import platform
import socket


@functools.lru_cache(maxsize=1)
def machine_id() -> str:
    parts = [
        socket.gethostname() or "",
        platform.system() or "",
        platform.machine() or "",
        platform.node() or "",
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]
