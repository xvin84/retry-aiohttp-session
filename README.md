# retry-aiohttp-session

**English** | [Русский](README.ru.md)

A drop-in [aiogram](https://github.com/aiogram/aiogram) session that transparently
retries Telegram Bot API calls on transient network failures - timeouts, dropped
connections, Telegram 5xx responses, and proxy-level errors.

Because aiogram routes every Bot API request through `AiohttpSession.make_request`,
a single session instance covers **all** methods - `send_message`, `send_document`,
`edit_message_text`, `answer_callback_query`, and the rest. No per-call retry code,
no changes to your handlers.

## Why

Extracted from a production bot deployed behind an unreliable HTTP/SOCKS proxy,
where roughly one new connection in five timed out. Without retries, every timeout
meant a user simply never received their reply. Wrapping the session turned those
failures into transparent, logged retries - one small class, zero changes to the
handler code.

## Install

```bash
pip install git+https://github.com/xvin84/retry-aiohttp-session.git
```

Not on PyPI yet. It is a single, dependency-free module (only aiogram itself), so
you can also just copy `src/retry_aiohttp_session/session.py` into your project.

## Usage

```python
from aiogram import Bot
from retry_aiohttp_session import RetryAiohttpSession

session = RetryAiohttpSession(
    proxy="http://127.0.0.1:1080",  # any AiohttpSession kwarg works; omit for a direct connection
    max_attempts=5,
)
bot = Bot(token="123:ABC", session=session)
```

That is the whole integration - every API call the bot makes is now retried on a
transient error. See [`examples/basic_bot.py`](examples/basic_bot.py) for a runnable bot.

## How it works

`RetryAiohttpSession` subclasses aiogram's `AiohttpSession` and overrides
`make_request`:

- **Transient network errors** (`TelegramNetworkError`, `TelegramServerError`,
  `asyncio.TimeoutError`, `OSError`) are retried with linear backoff -
  `min(backoff_base * attempt, backoff_max)` seconds.
- **Proxy errors** from `python-socks` (`ProxyError`, `ProxyTimeoutError`) subclass
  plain `Exception` rather than `aiohttp.ClientError`, so aiogram never wraps them in
  `TelegramNetworkError`. They are matched by class name (`"Proxy"` / `"Timeout"`),
  which keeps this package free of any hard dependency on a specific proxy backend.
- **`TelegramRetryAfter`** (Telegram rate limiting) is always honoured by sleeping
  exactly `retry_after + 1` seconds, independent of the backoff settings.
- **Everything else** (`TelegramBadRequest`, `asyncio.CancelledError`, …) is
  re-raised immediately - there is no point retrying a malformed request or a
  cancelled task.

Each retry is logged at `WARNING` level via the standard `logging` module under the
`retry_aiohttp_session` logger.

## Configuration

| Parameter      | Default | Description                                                        |
| -------------- | ------- | ------------------------------------------------------------------ |
| `max_attempts` | `4`     | Total tries per request (first call + retries). Clamped to ≥ 1.    |
| `backoff_base` | `1.5`   | Base seconds for the linear backoff between retries.               |
| `backoff_max`  | `5.0`   | Ceiling for a single backoff sleep.                                |

All other positional/keyword arguments are forwarded to `AiohttpSession`
(`proxy`, `timeout`, `api`, …).

## Requirements

- Python ≥ 3.11
- aiogram ≥ 3.7 (tested on 3.20)

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
```

## License

[MIT](LICENSE)
