"""
State Machine and Session Management for Wake-Word Gating.
Implements the active listening window and security session tracking (SR-1, SO-1).
"""

from datetime import datetime, timezone
import threading
import time
from typing import Callable, List, Optional
import uuid

from voice_control.models.command import SystemState


class SessionManager:
    """
    Manages the wake-word-gated listening session.
    A valid session token is created only upon genuine wake-word detection,
    and automatically expires after `window_duration_seconds`.
    """

    def __init__(self, window_duration_seconds: float = 4.0):
        self.window_duration = window_duration_seconds
        self._state = SystemState.IDLE
        self._current_session_token: Optional[str] = None
        self._session_start: Optional[float] = None
        self._session_expires_at: Optional[float] = None
        self._lock = threading.Lock()
        self._state_callbacks: List[Callable[[SystemState, Optional[str]], None]] = []

    def register_state_callback(self, callback: Callable[[SystemState, Optional[str]], None]) -> None:
        """Register listener for state changes (e.g. for Feedback/LED indicator)."""
        with self._lock:
            self._state_callbacks.append(callback)

    def open_session(self) -> str:
        """
        Transition to LISTENING state and issue an authorized session token.
        Called strictly when the Wake-Word Detector detects the wake word.
        """
        with self._lock:
            token = str(uuid.uuid4())
            now = time.time()
            self._current_session_token = token
            self._session_start = now
            self._session_expires_at = now + self.window_duration
            self._state = SystemState.LISTENING

        self._notify_state_change(SystemState.LISTENING, token)
        return token

    def check_and_update(self) -> SystemState:
        """
        Check if the active listening session has timed out.
        If expired, transitions back to IDLE.
        """
        expired = False
        with self._lock:
            if self._state == SystemState.LISTENING:
                if self._session_expires_at and time.time() >= self._session_expires_at:
                    self._state = SystemState.IDLE
                    self._current_session_token = None
                    self._session_start = None
                    self._session_expires_at = None
                    expired = True
            current_state = self._state

        if expired:
            self._notify_state_change(SystemState.IDLE, None)

        return current_state

    def close_session(self) -> None:
        """Explicitly terminate the listening session and return to IDLE."""
        with self._lock:
            self._state = SystemState.IDLE
            self._current_session_token = None
            self._session_start = None
            self._session_expires_at = None

        self._notify_state_change(SystemState.IDLE, None)

    def is_session_valid(self, token: Optional[str]) -> bool:
        """
        Validate whether a given token belongs to the currently active listening session.
        Implements Security Requirement SR-1 / SO-1.
        """
        if not token:
            return False

        with self._lock:
            if self._state != SystemState.LISTENING:
                return False
            if self._session_expires_at and time.time() > self._session_expires_at:
                return False
            return self._current_session_token == token

    @property
    def current_state(self) -> SystemState:
        with self._lock:
            return self._state

    @property
    def current_token(self) -> Optional[str]:
        with self._lock:
            return self._current_session_token

    @property
    def time_remaining_seconds(self) -> float:
        with self._lock:
            if self._state != SystemState.LISTENING or not self._session_expires_at:
                return 0.0
            remaining = self._session_expires_at - time.time()
            return max(0.0, remaining)

    def _notify_state_change(self, state: SystemState, token: Optional[str]) -> None:
        with self._lock:
            callbacks = list(self._state_callbacks)
        for cb in callbacks:
            try:
                cb(state, token)
            except Exception:
                pass
