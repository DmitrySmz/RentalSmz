from __future__ import annotations

import os
import time
import uuid
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Literal

SessionKind = Literal["client", "employee"]

IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "120"))  # 2 минуты


@dataclass(frozen=True)
class SessionUser:
    kind: SessionKind
    user_id: int


@dataclass
class SessionRecord:
    sid: str
    user: SessionUser
    created_at: float
    last_seen: float

    def remaining_seconds(self) -> int:
        now = time.time()
        left = IDLE_TIMEOUT_SECONDS - (now - self.last_seen)
        return max(0, int(left))


class SessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: Dict[str, SessionRecord] = {}

    def _purge_if_expired(self, sid: str, rec: SessionRecord) -> bool:
        if rec.remaining_seconds() <= 0:
            self._store.pop(sid, None)
            return True
        return False

    def create(self, user: SessionUser) -> str:
        sid = uuid.uuid4().hex
        now = time.time()
        rec = SessionRecord(sid=sid, user=user, created_at=now, last_seen=now)
        with self._lock:
            self._store[sid] = rec
        return sid

    def delete(self, sid: str) -> None:
        with self._lock:
            self._store.pop(sid, None)

    def get(self, sid: str) -> Optional[SessionRecord]:
        with self._lock:
            rec = self._store.get(sid)
            if not rec:
                return None
            if self._purge_if_expired(sid, rec):
                return None
            return rec

    def touch(self, sid: str) -> Optional[SessionRecord]:
        with self._lock:
            rec = self._store.get(sid)
            if not rec:
                return None
            if self._purge_if_expired(sid, rec):
                return None
            rec.last_seen = time.time()
            return rec

    def remaining(self, sid: str) -> int:
        rec = self.get(sid)
        return rec.remaining_seconds() if rec else 0


session_manager = SessionManager()
