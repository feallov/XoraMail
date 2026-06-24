import logging
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice,
    PreCheckoutQuery, SuccessfulPayment
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.database import Database
from src.mail_client import MailClient, extract_code
from src.keyboards import (
    main_menu_kb, mails_list_kb, mail_detail_kb,
    premium_kb, back_to_menu_kb, admin_kb, channel_sub_kb
)
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()
mail_client = MailClient()


class CreateMailStates(StatesGroup):
    waiting_label = State()
    waiting_filter = State()


class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_give_premium_id = State()
    waiting_give_premium_days = State()
    waiting_filter_mail_id = State()


# ── helpers ──────────────────────────────────────────────────────────────────

def get_db(data: dict) -> Database:
    return data["db"]


async def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, **data):
    db: Database = get_db(data)
    await db.get_or_create_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name
    )
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать в TempMail Bot!</b>\n\n"
        "🔐 Создавайте временные почты за секунды\n"
        "📩 Получайте коды подтверждения автоматически\n"
        "🔍 Фильтруйте письма по ключевым словам\n\n"
        "Выберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, state: FSMContext, **data):
    await state.clear()
    await call.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await call.answer()


# ── Check channel sub ────────────────────────────────────────────────────────

@router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery, **data):
    if not settings.REQUIRED_CHANNEL_ID:
        await call.answer("✅ Всё отлично!")
        return
    bot: Bot = data["bot"]
    try:
        member = await bot.get_chat_member(settings.REQUIRED_CHANNEL_ID, call.from_user.id)
        if member.status in ("left", "kicked", "banned"):
            raise Exception()
        await call.message.edit_text(
            "✅ Подписка подтверждена!\n\nВыберите действие:",
            reply_markup=main_menu_kb()
        )
    except Exception:
        await call.answer("❌ Вы ещё не подписались!", show_alert=True)


# ── Create mail flow ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "create_mail")
async def cb_create_mail(call: CallbackQuery, state: FSMContext, **data):
    db: Database = get_db(data)
    user = await db.get_user(call.from_user.id)
    is_premium = await db.check_premium_expiry(call.from_user.id)

    active = await db.get_active_mails(call.from_user.id)
    limit = settings.MAX_MAILS_PREMIUM if is_premium else settings.MAX_MAILS_FREE
    if len(active) >= limit:
        await call.answer(
            f"❌ Лимит почт: {limit}. {'Удалите старые.' if is_premium else 'Купите Premium для большего количества.'}",
            show_alert=True
        )
        return

    await state.set_state(CreateMailStates.waiting_label)
    await call.message.edit_text(
        "📧 <b>Создание временной почты</b>\n\n"
        "Введите метку для почты (например: «регистрация», «Авито»)\n"
        "или нажмите /skip чтобы пропустить:",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(CreateMailStates.waiting_label)
async def process_label(message: Message, state: FSMContext, **data):
    label = None if message.text == "/skip" else message.text[:50]
    await state.update_data(label=label)
    await state.set_state(CreateMailStates.waiting_filter)
    await message.answer(
        "🔍 <b>Фильтр писем</b>\n\n"
        "Введите ключевое слово — бот будет показывать только письма, "
        "содержащие его (от кого, тема или тело).\n"
        "Например: <code>discord</code>, <code>google</code>, <code>noreply</code>\n\n"
        "Или нажмите /skip чтобы получать все письма:",
        parse_mode="HTML"
    )


@router.message(CreateMailStates.waiting_filter)
async def process_filter(message: Message, state: FSMContext, **data):
    db: Database = get_db(data)
    filter_kw = None if message.text == "/skip" else message.text[:64]
    state_data = await state.get_data()
    label = state_data.get("label")
    await state.clear()

    status_msg = await message.answer("⏳ Создаю почту...")

    is_premium = await db.check_premium_expiry(message.from_user.id)
    lifetime = settings.MAIL_LIFETIME_PREMIUM if is_premium else settings.MAIL_LIFETIME_FREE

    try:
        email, password, account_id, token = await mail_client.create_account(label)
        expires_at = datetime.utcnow() + timedelta(minutes=lifetime)
        mail = await db.create_mail(
            user_id=message.from_user.id,
            email=email,
            password=password,
            account_id=account_id,
            token=token,
            expires_at=expires_at,
            label=label,
            filter_keyword=filter_kw
        )

        filter_str = f"🔍 Фильтр: <code>{filter_kw}</code>\n" if filter_kw else ""
        label_str = f"📌 Метка: <b>{label}</b>\n" if label else ""
        await status_msg.edit_text(
            f"✅ <b>Почта создана!</b>\n\n"
            f"{label_str}"
            f"📧 Адрес: <code>{email}</code>\n"
            f"⏳ Активна: {lifetime} минут\n"
            f"{filter_str}\n"
            f"Письма и коды будут приходить автоматически!",
            reply_markup=mail_detail_kb(mail.id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Mail creation error: {e}")
        await status_msg.edit_text(
            "❌ Ошибка при создании почты. Попробуйте ещё раз.",
            reply_markup=back_to_menu_kb()
        )


# ── My mails ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_mails")
async def cb_my_mails(call: CallbackQuery, **data):
    db: Database = get_db(data)
    mails = await db.get_active_mails(call.from_user.id)
    if not mails:
        await call.message.edit_text(
            "📭 У вас нет активных почт.\n\nСоздайте новую!",
            reply_markup=back_to_menu_kb()
        )
        await call.answer()
        return
    await call.message.edit_text(
        f"📬 <b>Ваши активные почты</b> ({len(mails)}):",
        reply_markup=mails_list_kb(mails),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("mail_"))
async def cb_mail_detail(call: CallbackQuery, **data):
    db: Database = get_db(data)
    mail_id = int(call.data.split("_")[1])
    mail = await db.get_mail_by_id(mail_id, call.from_user.id)
    if not mail or not mail.is_active:
        await call.answer("❌ Почта не найдена или уже удалена", show_alert=True)
        return

    mins_left = max(0, int((mail.expires_at - datetime.utcnow()).total_seconds() // 60))
    filter_str = f"🔍 Фильтр: <code>{mail.filter_keyword}</code>\n" if mail.filter_keyword else ""
    label_str = f"📌 Метка: <b>{mail.label}</b>\n" if mail.label else ""

    await call.message.edit_text(
        f"📧 <b>Детали почты</b>\n\n"
        f"{label_str}"
        f"Адрес: <code>{mail.email}</code>\n"
        f"⏳ Осталось: {mins_left} мин\n"
        f"{filter_str}",
        reply_markup=mail_detail_kb(mail.id),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("check_"))
async def cb_check_mail(call: CallbackQuery, **data):
    db: Database = get_db(data)
    mail_id = int(call.data.split("_")[1])
    mail = await db.get_mail_by_id(mail_id, call.from_user.id)
    if not mail:
        await call.answer("❌ Почта не найдена", show_alert=True)
        return

    await call.answer("🔄 Проверяю...")
    try:
        messages = await mail_client.get_messages(mail.token)
        if not messages:
            await call.message.answer("📭 Писем нет")
            return
        for msg in messages[-5:]:
            subject = msg.get("subject", "(no subject)")
            from_addr = msg.get("from", {}).get("address", "?")
            body = await mail_client.get_message_body(mail.token, msg["id"])
            code = extract_code(subject + " " + body)
            code_str = f"\n🔑 <b>Код:</b> <code>{code}</code>" if code else ""
            await call.message.answer(
                f"📩 <b>{subject}</b>\n"
                f"👤 От: <code>{from_addr}</code>"
                f"{code_str}\n\n"
                f"<i>{body[:300]}</i>",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(e)
        await call.message.answer("❌ Ошибка при проверке почты")


@router.callback_query(F.data.startswith("filter_"))
async def cb_set_filter(call: CallbackQuery, state: FSMContext, **data):
    mail_id = int(call.data.split("_")[1])
    await state.set_state(AdminStates.waiting_filter_mail_id)
    await state.update_data(filter_mail_id=mail_id)
    await call.message.edit_text(
        "🔍 Введите новое ключевое слово для фильтра\n"
        "или /skip чтобы убрать фильтр:"
    )
    await call.answer()


@router.message(AdminStates.waiting_filter_mail_id)
async def process_new_filter(message: Message, state: FSMContext, **data):
    db: Database = get_db(data)
    state_data = await state.get_data()
    mail_id = state_data["filter_mail_id"]
    await state.clear()

    mail = await db.get_mail_by_id(mail_id, message.from_user.id)
    if not mail:
        await message.answer("❌ Почта не найдена", reply_markup=back_to_menu_kb())
        return

    new_filter = None if message.text == "/skip" else message.text[:64]
    # direct DB update
    from sqlalchemy import update as sa_update
    from src.database import TempMail
    async with db.session_factory() as s:
        await s.execute(
            sa_update(TempMail).where(TempMail.id == mail_id).values(filter_keyword=new_filter)
        )
        await s.commit()

    txt = f"✅ Фильтр обновлён: <code>{new_filter}</code>" if new_filter else "✅ Фильтр снят"
    await message.answer(txt, reply_markup=mail_detail_kb(mail_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("delete_"))
async def cb_delete_mail(call: CallbackQuery, **data):
    db: Database = get_db(data)
    mail_id = int(call.data.split("_")[1])
    mail = await db.get_mail_by_id(mail_id, call.from_user.id)
    if mail:
        await db.deactivate_mail(mail_id)
        try:
            await mail_client.delete_account(mail.token, mail.account_id)
        except Exception:
            pass
    await call.message.edit_text(
        "🗑 Почта удалена!",
        reply_markup=back_to_menu_kb()
    )
    await call.answer("✅ Удалено")


# ── History ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "history")
async def cb_history(call: CallbackQuery, **data):
    db: Database = get_db(data)
    codes = await db.get_received_codes(call.from_user.id, limit=10)
    if not codes:
        await call.message.edit_text(
            "📜 История кодов пуста.",
            reply_markup=back_to_menu_kb()
        )
        await call.answer()
        return
    lines = []
    for c in codes:
        code_str = f" → 🔑 <code>{c.code}</code>" if c.code else ""
        lines.append(
            f"📧 <code>{c.email}</code>\n"
            f"📝 {c.subject}{code_str}\n"
            f"🕒 {c.received_at.strftime('%d.%m %H:%M')}"
        )
    await call.message.edit_text(
        "📜 <b>Последние 10 писем:</b>\n\n" + "\n\n".join(lines),
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await call.answer()


# ── Help ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery, **data):
    db: Database = get_db(data)
    is_prem = await db.check_premium_expiry(call.from_user.id)
    plan = "⭐ Premium" if is_prem else "🆓 Бесплатный"
    await call.message.edit_text(
        f"ℹ️ <b>Как пользоваться ботом</b>\n\n"
        f"1️⃣ Нажмите «📧 Создать почту»\n"
        f"2️⃣ Укажите метку (необязательно)\n"
        f"3️⃣ Укажите фильтр по слову (необязательно)\n"
        f"4️⃣ Копируйте адрес и используйте для регистраций\n"
        f"5️⃣ Коды приходят автоматически!\n\n"
        f"📊 Ваш тариф: <b>{plan}</b>\n"
        f"📬 Одновременных почт: {settings.MAX_MAILS_PREMIUM if is_prem else settings.MAX_MAILS_FREE}\n"
        f"⏳ Время жизни почты: {settings.MAIL_LIFETIME_PREMIUM if is_prem else settings.MAIL_LIFETIME_FREE} мин\n\n"
        f"🔄 Проверка почт каждые {settings.MAIL_CHECK_INTERVAL} сек",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
    await call.answer()


# ── Premium / Payments ────────────────────────────────────────────────────────

@router.callback_query(F.data == "premium")
async def cb_premium(call: CallbackQuery, **data):
    db: Database = get_db(data)
    is_prem = await db.check_premium_expiry(call.from_user.id)
    user = await db.get_user(call.from_user.id)

    if is_prem and user and user.premium_until:
        until = user.premium_until.strftime("%d.%m.%Y")
        await call.message.edit_text(
            f"⭐ <b>У вас уже есть Premium!</b>\n\n"
            f"✅ Активен до: <b>{until}</b>\n\n"
            f"📬 Почт одновременно: {settings.MAX_MAILS_PREMIUM}\n"
            f"⏳ Время жизни: {settings.MAIL_LIFETIME_PREMIUM} мин",
            reply_markup=premium_kb(),
            parse_mode="HTML"
        )
    else:
        await call.message.edit_text(
            "⭐ <b>Premium подписка</b>\n\n"
            f"🆓 <b>Бесплатно:</b>\n"
            f"  • {settings.MAX_MAILS_FREE} почты одновременно\n"
            f"  • {settings.MAIL_LIFETIME_FREE} мин время жизни\n\n"
            f"⭐ <b>Premium:</b>\n"
            f"  • {settings.MAX_MAILS_PREMIUM} почт одновременно\n"
            f"  • {settings.MAIL_LIFETIME_PREMIUM} мин время жизни\n"
            f"  • Приоритетная проверка\n\n"
            f"Оплата через Telegram Stars 🌟",
            reply_markup=premium_kb(),
            parse_mode="HTML"
        )
    await call.answer()


@router.callback_query(F.data.in_({"buy_week", "buy_month"}))
async def cb_buy(call: CallbackQuery, **data):
    bot: Bot = data["bot"]
    if call.data == "buy_week":
        title = "Premium на 7 дней"
        desc = f"{settings.MAX_MAILS_PREMIUM} почт · {settings.MAIL_LIFETIME_PREMIUM} мин · 7 дней"
        price = settings.STARS_PRICE_WEEK
        payload = "premium_7"
    else:
        title = "Premium на 30 дней"
        desc = f"{settings.MAX_MAILS_PREMIUM} почт · {settings.MAIL_LIFETIME_PREMIUM} мин · 30 дней"
        price = settings.STARS_PRICE_PREMIUM
        payload = "premium_30"

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=title,
        description=desc,
        payload=payload,
        currency="XTR",           # Telegram Stars
        prices=[LabeledPrice(label=title, amount=price)],
        provider_token=""         # empty for Stars
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_payment(message: Message, **data):
    db: Database = get_db(data)
    payload = message.successful_payment.invoice_payload
    days = 7 if payload == "premium_7" else 30
    await db.set_premium(message.from_user.id, days)
    await message.answer(
        f"🎉 <b>Premium активирован на {days} дней!</b>\n\n"
        f"📬 Теперь вам доступно {settings.MAX_MAILS_PREMIUM} почт одновременно\n"
        f"⏳ Время жизни почты: {settings.MAIL_LIFETIME_PREMIUM} минут\n\n"
        f"Спасибо за поддержку! ❤️",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ── Admin panel ───────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, **data):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery, **data):
    if not await is_admin(call.from_user.id):
        return
    db: Database = get_db(data)
    total = await db.get_all_users_count()
    prem = await db.get_premium_users_count()
    active = await db.get_all_active_mails()
    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👤 Всего пользователей: {total}\n"
        f"⭐ Premium: {prem}\n"
        f"📧 Активных почт: {len(active)}",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext, **data):
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await call.message.edit_text("📢 Введите текст рассылки (HTML поддерживается):")
    await call.answer()


@router.message(AdminStates.waiting_broadcast)
async def process_broadcast(message: Message, state: FSMContext, **data):
    if not await is_admin(message.from_user.id):
        return
    db: Database = get_db(data)
    bot: Bot = data["bot"]
    await state.clear()

    from sqlalchemy import select
    from src.database import User
    async with db.session_factory() as s:
        result = await s.execute(select(User.id))
        user_ids = [row[0] for row in result.fetchall()]

    ok, fail = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, message.text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1

    await message.answer(f"📢 Рассылка завершена: ✅{ok} ❌{fail}", reply_markup=admin_kb())


@router.callback_query(F.data == "admin_give_premium")
async def cb_give_premium(call: CallbackQuery, state: FSMContext, **data):
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_give_premium_id)
    await call.message.edit_text("👤 Введите Telegram ID пользователя:")
    await call.answer()


@router.message(AdminStates.waiting_give_premium_id)
async def process_give_id(message: Message, state: FSMContext, **data):
    if not await is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
        await state.update_data(give_uid=uid)
        await state.set_state(AdminStates.waiting_give_premium_days)
        await message.answer(f"⏳ Сколько дней Premium выдать пользователю {uid}?")
    except ValueError:
        await message.answer("❌ Неверный ID")
        await state.clear()


@router.message(AdminStates.waiting_give_premium_days)
async def process_give_days(message: Message, state: FSMContext, **data):
    if not await is_admin(message.from_user.id):
        return
    db: Database = get_db(data)
    state_data = await state.get_data()
    uid = state_data["give_uid"]
    await state.clear()
    try:
        days = int(message.text.strip())
        await db.set_premium(uid, days)
        await message.answer(f"✅ Premium на {days} дней выдан пользователю {uid}", reply_markup=admin_kb())
        try:
            bot: Bot = data["bot"]
            await bot.send_message(
                uid,
                f"🎁 Вам выдан Premium на {days} дней!\n\nСпасибо, что пользуетесь нашим ботом! ❤️",
                reply_markup=main_menu_kb()
            )
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Неверное число дней")
