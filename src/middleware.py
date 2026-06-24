import asyncio
from typing import Callable, Any, Awaitable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, Update
from aiogram.exceptions import TelegramBadRequest
from collections import defaultdict
from config.settings import settings
from src.keyboards import channel_sub_kb


# ── Throttle ────────────────────────────────────────────────────────────────

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 1.0):
        self._rate = rate
        self._last: Dict[int, float] = defaultdict(float)

    async def __call__(self, handler: Callable, event: Message, data: dict):
        import time
        user_id = event.from_user.id if event.from_user else 0
        now = time.monotonic()
        if now - self._last[user_id] < self._rate:
            await event.answer("⏳ Не так быстро! Подождите секунду.")
            return
        self._last[user_id] = now
        return await handler(event, data)


# ── Channel subscription ─────────────────────────────────────────────────────

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def __call__(self, handler: Callable, event: TelegramObject, data: dict):
        if not settings.REQUIRED_CHANNEL_ID:
            return await handler(event, data)

        # Extract user_id
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        # Skip admins
        if user.id in settings.ADMIN_IDS:
            return await handler(event, data)

        # Allow "check_sub" callback to pass through
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        try:
            member = await self.bot.get_chat_member(settings.REQUIRED_CHANNEL_ID, user.id)
            if member.status in ("left", "kicked", "banned"):
                raise Exception("not member")
        except Exception:
            text = (
                "👋 Для использования бота необходимо подписаться на наш канал!\n\n"
                "После подписки нажмите кнопку ✅"
            )
            if isinstance(event, Message):
                await event.answer(text, reply_markup=channel_sub_kb(settings.REQUIRED_CHANNEL_URL))
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(text, reply_markup=channel_sub_kb(settings.REQUIRED_CHANNEL_URL))
                await event.answer()
            return

        return await handler(event, data)
