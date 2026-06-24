from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # === TELEGRAM ===
    BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"

    # === MONETIZATION ===
    # Telegram Stars payment (built-in, no extra setup)
    STARS_PRICE_PREMIUM: int = 50          # Stars for 30 days premium
    STARS_PRICE_WEEK: int = 15             # Stars for 7 days premium

    # Optional: Yukassa / Stripe (fill if needed)
    PAYMENT_PROVIDER_TOKEN: str = ""       # leave empty to use Stars only

    # === CHANNEL / SUBSCRIPTION GATE ===
    # If set, users must subscribe to this channel to use the bot
    REQUIRED_CHANNEL_ID: Optional[str] = None   # e.g. "@mychannel" or "-1001234567890"
    REQUIRED_CHANNEL_URL: str = "https://t.me/yourchannel"

    # === ADMIN ===
    ADMIN_IDS: list[int] = []              # list of Telegram user IDs

    # === DATABASE ===
    DATABASE_URL: str = "sqlite+aiosqlite:///./tempmail.db"

    # === MAIL SETTINGS ===
    MAIL_LIFETIME_FREE: int = 15           # minutes for free users
    MAIL_LIFETIME_PREMIUM: int = 30        # minutes for premium users
    MAX_MAILS_FREE: int = 2               # simultaneous mailboxes for free users
    MAX_MAILS_PREMIUM: int = 10           # simultaneous mailboxes for premium users
    MAIL_CHECK_INTERVAL: int = 15         # seconds between inbox checks

    # === MAIL.TM API (free, no key needed) ===
    MAILTM_API: str = "https://api.mail.tm"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
