# retry-aiohttp-session

[English](README.md) | **Русский**

Готовая к подключению сессия для [aiogram](https://github.com/aiogram/aiogram),
которая прозрачно повторяет вызовы Telegram Bot API при временных сетевых сбоях —
таймаутах, обрывах соединения, ответах 5xx от Telegram и ошибках уровня прокси.

Поскольку aiogram проводит каждый запрос к Bot API через
`AiohttpSession.make_request`, одного экземпляра сессии достаточно, чтобы покрыть
**все** методы — `send_message`, `send_document`, `edit_message_text`,
`answer_callback_query` и остальные. Никакого кода повторов в хэндлерах.

## Зачем

Класс выделен из продакшен-бота, развёрнутого за нестабильным HTTP/SOCKS-прокси,
где примерно одно новое соединение из пяти отваливалось по таймауту. Без повторов
каждый такой таймаут означал, что пользователь просто не получал ответ. Обёртка над
сессией превратила эти сбои в прозрачные, логируемые повторы — один небольшой класс
и ноль правок в коде хэндлеров.

## Установка

```bash
pip install git+https://github.com/xvin84/retry-aiohttp-session.git
```

Пакета на PyPI пока нет. Это один модуль без сторонних зависимостей (кроме самого
aiogram), поэтому можно просто скопировать `src/retry_aiohttp_session/session.py`
в свой проект.

## Использование

```python
from aiogram import Bot
from retry_aiohttp_session import RetryAiohttpSession

session = RetryAiohttpSession(
    proxy="http://127.0.0.1:1080",  # работает любой kwarg AiohttpSession; убери для прямого соединения
    max_attempts=5,
)
bot = Bot(token="123:ABC", session=session)
```

Это вся интеграция — каждый вызов API, который делает бот, теперь повторяется при
временной ошибке. Запускаемый пример — в [`examples/basic_bot.py`](examples/basic_bot.py).

## Как это работает

`RetryAiohttpSession` наследует `AiohttpSession` из aiogram и переопределяет
`make_request`:

- **Временные сетевые ошибки** (`TelegramNetworkError`, `TelegramServerError`,
  `asyncio.TimeoutError`, `OSError`) повторяются с линейным backoff —
  `min(backoff_base * attempt, backoff_max)` секунд.
- **Ошибки прокси** из `python-socks` (`ProxyError`, `ProxyTimeoutError`) наследуют
  обычный `Exception`, а не `aiohttp.ClientError`, поэтому aiogram не оборачивает их
  в `TelegramNetworkError`. Они ловятся по имени класса (`"Proxy"` / `"Timeout"`) —
  так пакет не зависит жёстко от конкретного прокси-бэкенда.
- **`TelegramRetryAfter`** (rate limit от Telegram) всегда соблюдается: сессия ждёт
  ровно `retry_after + 1` секунд, независимо от настроек backoff.
- **Всё остальное** (`TelegramBadRequest`, `asyncio.CancelledError`, …)
  пробрасывается сразу — нет смысла повторять некорректный запрос или отменённую
  задачу.

Каждый повтор логируется на уровне `WARNING` через стандартный модуль `logging`
в логгере `retry_aiohttp_session`.

## Настройки

| Параметр       | По умолчанию | Описание                                                          |
| -------------- | ------------ | ----------------------------------------------------------------- |
| `max_attempts` | `4`          | Всего попыток на запрос (первый вызов + повторы). Не меньше 1.     |
| `backoff_base` | `1.5`        | Базовое число секунд для линейного backoff между повторами.       |
| `backoff_max`  | `5.0`        | Потолок для одной паузы backoff.                                   |

Все прочие позиционные/именованные аргументы передаются в `AiohttpSession`
(`proxy`, `timeout`, `api`, …).

## Требования

- Python ≥ 3.11
- aiogram ≥ 3.7 (проверено на 3.20)

## Разработка

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
```

## Лицензия

[MIT](LICENSE)
