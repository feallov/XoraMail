from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, Text, BigInteger, func, select, delete
from datetime import datetime, timedelta
from typing import Optional, List
from config.settings import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram user id
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    total_mails_created: Mapped[int] = mapped_column(Integer, default=0)


class TempMail(Base):
    __tablename__ = "temp_mails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    email: Mapped[str] = mapped_column(String(256))
    password: Mapped[str] = mapped_column(String(256))
    account_id: Mapped[str] = mapped_column(String(256))  # mail.tm account id
    token: Mapped[str] = mapped_column(Text)              # mail.tm JWT token
    label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    filter_keyword: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_message_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class ReceivedCode(Base):
    __tablename__ = "received_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    email: Mapped[str] = mapped_column(String(256))
    subject: Mapped[str] = mapped_column(String(512))
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    body_preview: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Database:
    def __init__(self):
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ── Users ──────────────────────────────────────────────────────────────

    async def get_or_create_user(self, user_id: int, username: str, full_name: str) -> User:
        async with self.session_factory() as s:
            user = await s.get(User, user_id)
            if not user:
                user = User(id=user_id, username=username, full_name=full_name)
                s.add(user)
                await s.commit()
                await s.refresh(user)
            return user

    async def get_user(self, user_id: int) -> Optional[User]:
        async with self.session_factory() as s:
            return await s.get(User, user_id)

    async def set_premium(self, user_id: int, days: int):
        async with self.session_factory() as s:
            user = await s.get(User, user_id)
            if user:
                now = datetime.utcnow()
                current = user.premium_until if (user.premium_until and user.premium_until > now) else now
                user.premium_until = current + timedelta(days=days)
                user.is_premium = True
                await s.commit()

    async def check_premium_expiry(self, user_id: int) -> bool:
        """Returns True if user is (still) premium."""
        async with self.session_factory() as s:
            user = await s.get(User, user_id)
            if not user or not user.is_premium:
                return False
            if user.premium_until and user.premium_until < datetime.utcnow():
                user.is_premium = False
                user.premium_until = None
                await s.commit()
                return False
            return True

    async def get_all_users_count(self) -> int:
        async with self.session_factory() as s:
            result = await s.execute(select(func.count(User.id)))
            return result.scalar_one()

    async def get_premium_users_count(self) -> int:
        async with self.session_factory() as s:
            result = await s.execute(select(func.count(User.id)).where(User.is_premium == True))
            return result.scalar_one()

    # ── TempMails ──────────────────────────────────────────────────────────

    async def create_mail(self, user_id: int, email: str, password: str,
                          account_id: str, token: str, expires_at: datetime,
                          label: Optional[str] = None, filter_keyword: Optional[str] = None) -> TempMail:
        async with self.session_factory() as s:
            mail = TempMail(
                user_id=user_id, email=email, password=password,
                account_id=account_id, token=token, expires_at=expires_at,
                label=label, filter_keyword=filter_keyword
            )
            s.add(mail)
            # bump counter
            user = await s.get(User, user_id)
            if user:
                user.total_mails_created += 1
            await s.commit()
            await s.refresh(mail)
            return mail

    async def get_active_mails(self, user_id: int) -> List[TempMail]:
        async with self.session_factory() as s:
            result = await s.execute(
                select(TempMail).where(
                    TempMail.user_id == user_id,
                    TempMail.is_active == True,
                    TempMail.expires_at > datetime.utcnow()
                )
            )
            return list(result.scalars().all())

    async def get_all_active_mails(self) -> List[TempMail]:
        async with self.session_factory() as s:
            result = await s.execute(
                select(TempMail).where(
                    TempMail.is_active == True,
                    TempMail.expires_at > datetime.utcnow()
                )
            )
            return list(result.scalars().all())

    async def deactivate_mail(self, mail_id: int):
        async with self.session_factory() as s:
            mail = await s.get(TempMail, mail_id)
            if mail:
                mail.is_active = False
                await s.commit()

    async def update_last_message(self, mail_id: int, message_id: str):
        async with self.session_factory() as s:
            mail = await s.get(TempMail, mail_id)
            if mail:
                mail.last_message_id = message_id
                await s.commit()

    async def cleanup_expired(self):
        async with self.session_factory() as s:
            await s.execute(
                TempMail.__table__.update()
                .where(TempMail.expires_at <= datetime.utcnow())
                .values(is_active=False)
            )
            await s.commit()

    async def get_mail_by_id(self, mail_id: int, user_id: int) -> Optional[TempMail]:
        async with self.session_factory() as s:
            result = await s.execute(
                select(TempMail).where(TempMail.id == mail_id, TempMail.user_id == user_id)
            )
            return result.scalar_one_or_none()

    # ── Codes history ──────────────────────────────────────────────────────

    async def save_received_code(self, user_id: int, email: str, subject: str,
                                  code: Optional[str], body_preview: str):
        async with self.session_factory() as s:
            rec = ReceivedCode(user_id=user_id, email=email, subject=subject,
                               code=code, body_preview=body_preview)
            s.add(rec)
            await s.commit()

    async def get_received_codes(self, user_id: int, limit: int = 10) -> List[ReceivedCode]:
        async with self.session_factory() as s:
            result = await s.execute(
                select(ReceivedCode)
                .where(ReceivedCode.user_id == user_id)
                .order_by(ReceivedCode.received_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
