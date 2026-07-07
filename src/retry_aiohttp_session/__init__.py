"""Resilient aiogram session with automatic Bot API retries."""
from __future__ import annotations

from .session import RetryAiohttpSession

__all__ = ["RetryAiohttpSession"]
__version__ = "0.1.0"
