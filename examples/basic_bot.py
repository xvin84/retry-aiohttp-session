"""Minimal aiogram bot wired up with RetryAiohttpSession.

Run with:  BOT_TOKEN=123:ABC python examples/basic_bot.py

Point `PROXY` at an HTTP/SOCKS proxy if you reach Telegram through one; leave it
unset to connect directly. Every Bot API call this bot makes is retried on a
transient network error -- no extra code in the handler.
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from retry_aiohttp_session import RetryAiohttpSession

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer("Hello! This reply survives a flaky network.")


async def main() -> None:
    token = os.environ["BOT_TOKEN"]
    proxy = os.environ.get("PROXY") or None

    session = RetryAiohttpSession(proxy=proxy, max_attempts=5)
    bot = Bot(token=token, session=session)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
