import aiohttp
import random
import string
import re
from typing import Optional, Tuple, List, Dict
from config.settings import settings

API = settings.MAILTM_API


def _random_string(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def extract_code(text: str) -> Optional[str]:
    """Try to pull a verification / OTP code from email body or subject."""
    patterns = [
        r'\b(\d{4,8})\b',                          # 4-8 digit code
        r'(?i)code[:\s]+([A-Z0-9]{4,10})',         # "code: XXXX"
        r'(?i)otp[:\s]+([A-Z0-9]{4,10})',
        r'(?i)verify[:\s]+([A-Z0-9]{4,10})',
        r'(?i)confirmation[:\s]+([A-Z0-9]{4,10})',
        r'\b([A-Z0-9]{6,10})\b',                   # uppercase alphanum block
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None


class MailClient:
    """Thin async wrapper around mail.tm public API."""

    async def get_domains(self) -> List[str]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API}/domains") as r:
                data = await r.json()
                return [d["domain"] for d in data.get("hydra:member", [])]

    async def create_account(self, label: Optional[str] = None) -> Tuple[str, str, str, str]:
        """Returns (email, password, account_id, token)."""
        domains = await self.get_domains()
        if not domains:
            raise RuntimeError("No domains available from mail.tm")

        domain = random.choice(domains)
        username = (label or _random_string(10)).lower().replace(" ", "")
        username = re.sub(r"[^a-z0-9]", "", username) or _random_string(8)
        # ensure uniqueness
        username = f"{username}{_random_string(4)}"
        email = f"{username}@{domain}"
        password = _random_string(16)

        async with aiohttp.ClientSession() as session:
            # Register
            async with session.post(f"{API}/accounts", json={"address": email, "password": password}) as r:
                if r.status not in (200, 201):
                    text = await r.text()
                    raise RuntimeError(f"Account creation failed ({r.status}): {text}")
                acc = await r.json()
                account_id = acc["id"]

            # Get token
            async with session.post(f"{API}/token", json={"address": email, "password": password}) as r:
                if r.status != 200:
                    text = await r.text()
                    raise RuntimeError(f"Token fetch failed ({r.status}): {text}")
                token_data = await r.json()
                token = token_data["token"]

        return email, password, account_id, token

    async def get_messages(self, token: str) -> List[Dict]:
        """Fetch all messages in the inbox."""
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API}/messages", headers=headers) as r:
                if r.status != 200:
                    return []
                data = await r.json()
                return data.get("hydra:member", [])

    async def get_message_body(self, token: str, message_id: str) -> str:
        """Fetch full message body text."""
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API}/messages/{message_id}", headers=headers) as r:
                if r.status != 200:
                    return ""
                data = await r.json()
                # prefer text, fall back to html-stripped
                text = data.get("text", "") or ""
                if not text:
                    html = data.get("html", [""])[0] if data.get("html") else ""
                    text = re.sub(r"<[^>]+>", " ", html)
                return text.strip()

    async def delete_account(self, token: str, account_id: str):
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            await session.delete(f"{API}/accounts/{account_id}", headers=headers)
