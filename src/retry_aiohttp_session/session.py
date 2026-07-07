"""Drop-in aiogram session that retries Bot API calls on transient network errors.

``RetryAiohttpSession`` subclasses aiogram's ``AiohttpSession`` and retries every
Bot API request when it fails with a transient network error (a timeout, a
dropped connection, a 5xx from Telegram, or a proxy-level error). Because aiogram
routes *all* API calls through ``make_request``, a single session instance covers
every method -- ``send_message``, ``send_document``, ``edit_message_text``,
``answer_callback_query`` and so on -- with no per-call retry code.

It was extracted from a production bot deployed behind an unreliable HTTP/SOCKS
proxy, where roughly one new connection in five timed out. Wrapping the session
turned those failures from lost user replies into transparent, logged retries.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

if TYPE_CHECKING:
    from aiogram.methods import TelegramMethod
    from aiogram.methods.base import TelegramType

logger = logging.getLogger(__name__)

# Transient errors worth retrying. Proxy backends (python-socks) raise
# ProxyError / ProxyTimeoutError that subclass plain Exception rather than
# aiohttp.ClientError, so aiogram does NOT wrap them in TelegramNetworkError.
# They are matched separately by class name in `_is_retryable`, which keeps this
# package free of any hard dependency on a particular proxy library.
_RETRYABLE_EXC = (
    TelegramNetworkError,
    TelegramServerError,
    asyncio.TimeoutError,
    OSError,
)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, _RETRYABLE_EXC):
        return True
    name = type(exc).__name__
    return "Proxy" in name or "Timeout" in name


class RetryAiohttpSession(AiohttpSession):
    """``AiohttpSession`` that retries a Bot API call on a transient failure.

    Parameters
    ----------
    max_attempts:
        Total number of tries per request (the first call plus retries).
        Values below 1 are clamped to 1, which disables retrying.
    backoff_base:
        Base delay, in seconds, for the linear backoff between retries. Attempt
        *n* waits ``min(backoff_base * n, backoff_max)`` seconds before the next
        try.
    backoff_max:
        Upper bound, in seconds, for a single backoff sleep.

    ``TelegramRetryAfter`` (Telegram rate limiting) is always honoured by waiting
    exactly ``retry_after + 1`` seconds, independent of the backoff settings.

    Any extra positional/keyword arguments are forwarded to ``AiohttpSession``,
    so the usual ``proxy=...`` / ``timeout=...`` options keep working::

        session = RetryAiohttpSession(proxy="http://127.0.0.1:1080", max_attempts=5)
        bot = Bot(token, session=session)
    """

    def __init__(
        self,
        *args: Any,
        max_attempts: int = 4,
        backoff_base: float = 1.5,
        backoff_max: float = 5.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._max_attempts = max(1, max_attempts)
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await super().make_request(bot, method, timeout=timeout)
            except TelegramRetryAfter as exc:
                # Rate limit from Telegram: wait exactly as long as it asks.
                if attempt == self._max_attempts:
                    raise
                logger.warning(
                    "Bot API rate limited on %s (attempt %d/%d), retrying after %ss",
                    type(method).__name__,
                    attempt,
                    self._max_attempts,
                    exc.retry_after,
                )
                await asyncio.sleep(exc.retry_after + 1)
            except Exception as exc:  # asyncio.CancelledError is BaseException -> not caught
                if attempt == self._max_attempts or not _is_retryable(exc):
                    raise
                logger.warning(
                    "Bot API network error on %s (attempt %d/%d): %s",
                    type(method).__name__,
                    attempt,
                    self._max_attempts,
                    f"{type(exc).__name__}: {exc}",
                )
                # Linear backoff with a ceiling: a dropped connection is usually
                # cured by a fresh one, so there is no need to wait long.
                await asyncio.sleep(min(self._backoff_base * attempt, self._backoff_max))
        # Unreachable: the final attempt either returns a result or re-raises above.
        raise RuntimeError("make_request: retries exhausted without a result")
