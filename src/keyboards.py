from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import settings
from typing import List
from src.database import TempMail
from datetime import datetime


def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📧 Создать почту", callback_data="create_mail")
    b.button(text="📬 Мои почты", callback_data="my_mails")
    b.button(text="📜 История кодов", callback_data="history")
    b.button(text="⭐ Premium", callback_data="premium")
    b.button(text="ℹ️ Помощь", callback_data="help")
    b.adjust(2, 2, 1)
    return b.as_markup()


def mails_list_kb(mails: List[TempMail]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in mails:
        mins_left = max(0, int((m.expires_at - datetime.utcnow()).total_seconds() // 60))
        label = m.label or m.email.split("@")[0]
        b.button(text=f"📧 {label} ({mins_left}м)", callback_data=f"mail_{m.id}")
    b.button(text="➕ Создать новую", callback_data="create_mail")
    b.button(text="🏠 Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def mail_detail_kb(mail_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Проверить почту", callback_data=f"check_{mail_id}")
    b.button(text="🔑 Фильтр по ключевому слову", callback_data=f"filter_{mail_id}")
    b.button(text="🗑 Удалить", callback_data=f"delete_{mail_id}")
    b.button(text="◀️ Назад", callback_data="my_mails")
    b.adjust(1)
    return b.as_markup()


def premium_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"⭐ 7 дней — {settings.STARS_PRICE_WEEK} Stars", callback_data="buy_week")
    b.button(text=f"⭐ 30 дней — {settings.STARS_PRICE_PREMIUM} Stars", callback_data="buy_month")
    b.button(text="◀️ Назад", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Главное меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def channel_sub_kb(channel_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 Подписаться", url=channel_url)
    b.button(text="✅ Я подписался", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()


def admin_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика", callback_data="admin_stats")
    b.button(text="📢 Рассылка", callback_data="admin_broadcast")
    b.button(text="👤 Выдать Premium", callback_data="admin_give_premium")
    b.adjust(1)
    return b.as_markup()
