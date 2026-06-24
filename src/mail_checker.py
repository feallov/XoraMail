import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from src.database import Database, TempMail
from src.mail_client import MailClient, extract_code
from config.settings import settings

logger = logging.getLogger(__name__)
client = MailClient()


class MailChecker:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db

    async def start_polling(self):
        logger.info("Mail checker started")
        while True:
            try:
                await self.db.cleanup_expired()
                mails = await self.db.get_all_active_mails()
                tasks = [self._check_mail(m) for m in mails]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Poller error: {e}")
            await asyncio.sleep(settings.MAIL_CHECK_INTERVAL)

    async def _check_mail(self, mail: TempMail):
        try:
            messages = await client.get_messages(mail.token)
        except Exception as e:
            logger.warning(f"Failed to fetch messages for {mail.email}: {e}")
            return

        for msg in messages:
            msg_id = msg.get("id", "")
            # skip already-seen
            if mail.last_message_id and msg_id <= mail.last_message_id:
                continue

            subject = msg.get("subject", "(no subject)")
            from_addr = msg.get("from", {}).get("address", "unknown")
            intro = msg.get("intro", "")

            # Fetch full body to extract code
            body = await client.get_message_body(mail.token, msg_id)
            code = extract_code(subject + " " + body)

            # Filter: skip if keyword set and not found
            if mail.filter_keyword:
                kw = mail.filter_keyword.lower()
                if kw not in subject.lower() and kw not in body.lower() and kw not in from_addr.lower():
                    continue

            # Save to history
            await self.db.save_received_code(
                user_id=mail.user_id,
                email=mail.email,
                subject=subject,
                code=code,
                body_preview=(body[:300] + "…") if len(body) > 300 else body
            )

            # Update last seen
            await self.db.update_last_message(mail.id, msg_id)

            # Build notification
            label_str = f"📌 <b>{mail.label}</b>\n" if mail.label else ""
            code_str = f"\n\n🔑 <b>Код:</b> <code>{code}</code>" if code else ""
            text = (
                f"📬 <b>Новое письмо!</b>\n"
                f"{label_str}"
                f"📧 На: <code>{mail.email}</code>\n"
                f"👤 От: <code>{from_addr}</code>\n"
                f"📝 Тема: {subject}"
                f"{code_str}\n\n"
                f"💬 <i>{intro[:200] if intro else body[:200]}</i>"
            )
            try:
                await self.bot.send_message(mail.user_id, text, parse_mode="HTML")
            except TelegramForbiddenError:
                logger.warning(f"User {mail.user_id} blocked the bot")
            except Exception as e:
                logger.error(f"Send error to {mail.user_id}: {e}")
