"""Behavioural tests for ``RetryAiohttpSession``.

The parent ``AiohttpSession.make_request`` is replaced with a scripted stub, so
these tests exercise the retry logic without touching the network. Backoff is
set to zero and ``asyncio.sleep`` is stubbed out, so the suite runs instantly.
"""
from __future__ import annotations

import asyncio

import pytest

from aiogram.client.session.aiohttp import AiohttpSession

from retry_aiohttp_session import RetryAiohttpSession


class DummyMethod:
    """Stands in for a Bot API method; only its class name is used."""


class ProxyTimeoutError(Exception):
    """Mimics a python-socks proxy error: retryable by class name, not type."""


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


def _stub_parent(monkeypatch, side_effects):
    """Script ``AiohttpSession.make_request`` from a list of results/exceptions."""
    seq = iter(side_effects)
    calls = {"n": 0}

    async def fake(self, bot, method, timeout=None):
        calls["n"] += 1
        outcome = next(seq)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(AiohttpSession, "make_request", fake)
    return calls


def _session(**kwargs):
    kwargs.setdefault("backoff_base", 0)
    kwargs.setdefault("backoff_max", 0)
    return RetryAiohttpSession(**kwargs)


async def test_succeeds_on_first_try(monkeypatch):
    calls = _stub_parent(monkeypatch, ["ok"])
    result = await _session(max_attempts=4).make_request(None, DummyMethod())
    assert result == "ok"
    assert calls["n"] == 1


async def test_retries_transient_then_succeeds(monkeypatch):
    calls = _stub_parent(monkeypatch, [OSError("reset"), asyncio.TimeoutError(), "ok"])
    result = await _session(max_attempts=4).make_request(None, DummyMethod())
    assert result == "ok"
    assert calls["n"] == 3


async def test_proxy_error_matched_by_name(monkeypatch):
    calls = _stub_parent(monkeypatch, [ProxyTimeoutError(), "ok"])
    result = await _session(max_attempts=4).make_request(None, DummyMethod())
    assert result == "ok"
    assert calls["n"] == 2


async def test_gives_up_after_max_attempts(monkeypatch):
    calls = _stub_parent(monkeypatch, [OSError(), OSError(), OSError()])
    with pytest.raises(OSError):
        await _session(max_attempts=3).make_request(None, DummyMethod())
    assert calls["n"] == 3


async def test_non_retryable_raises_immediately(monkeypatch):
    calls = _stub_parent(monkeypatch, [ValueError("bad request")])
    with pytest.raises(ValueError):
        await _session(max_attempts=4).make_request(None, DummyMethod())
    assert calls["n"] == 1


async def test_max_attempts_clamped_to_one(monkeypatch):
    calls = _stub_parent(monkeypatch, [OSError()])
    with pytest.raises(OSError):
        await _session(max_attempts=0).make_request(None, DummyMethod())
    assert calls["n"] == 1
