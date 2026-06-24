# 📧 TempMail Bot

Telegram бот для создания временных почт с автоматическим получением кодов подтверждения.

---

## 🚀 Быстрый старт

### 1. Клонировать / распаковать проект

```bash
cd tempmail-bot
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Настроить `.env`

Откройте `.env` и заполните:

| Переменная | Обязательно | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен от @BotFather |
| `ADMIN_IDS` | ✅ | `[ваш_telegram_id]` |
| `REQUIRED_CHANNEL_ID` | ❌ | Канал для обязательной подписки |
| `STARS_PRICE_WEEK` | ❌ | Цена 7 дней Premium в Stars (по умолч. 15) |
| `STARS_PRICE_PREMIUM` | ❌ | Цена 30 дней Premium в Stars (по умолч. 50) |

### 4. Запустить

```bash
python bot.py
```

---

## ☁️ Деплой на Render.com

1. Зарегистрируйтесь на [render.com](https://render.com)
2. Создайте новый **Background Worker**
3. Подключите GitHub репозиторий с проектом
4. Render автоматически найдёт `render.yaml`
5. В **Environment Variables** добавьте:
   - `BOT_TOKEN` — токен бота
   - `ADMIN_IDS` — `[ваш_id]`
   - остальные переменные по желанию
6. Нажмите **Deploy**

> ⚠️ На бесплатном плане Render используйте **Background Worker** (не Web Service).  
> SQLite файл хранится на подключённом диске (`/app/tempmail.db`).

---

## ⭐ Монетизация

### Telegram Stars (встроено, работает без настройки)
- Пользователи покупают Premium прямо в боте через Telegram Stars
- Звёзды приходят на ваш аккаунт/канал в Telegram
- Настройте вывод в [@BotFather](https://t.me/BotFather) → Bot Settings → Payments

### Подписка на канал (бесплатная монетизация)
- Заполните `REQUIRED_CHANNEL_ID` в `.env`
- Все пользователи должны подписаться перед использованием
- Продавайте рекламу на канале

### Stripe / ЮКасса
- Получите `PAYMENT_PROVIDER_TOKEN` в @BotFather → Payments
- Добавьте в `.env`

---

## 📁 Структура проекта

```
tempmail-bot/
├── bot.py                 # Точка входа
├── requirements.txt
├── render.yaml            # Конфиг для Render.com
├── .env                   # Токены и настройки
├── config/
│   └── settings.py        # Pydantic-настройки
└── src/
    ├── handlers.py         # Все обработчики команд
    ├── database.py         # SQLAlchemy модели + async DB
    ├── mail_client.py      # API клиент mail.tm
    ├── mail_checker.py     # Фоновая проверка почт
    ├── keyboards.py        # Inline клавиатуры
    └── middleware.py       # Антиспам + проверка подписки
```

---

## 🎛 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Главное меню |
| `/admin` | Панель администратора (только для ADMIN_IDS) |

### Возможности через меню:
- 📧 Создать почту (с меткой и фильтром)
- 📬 Список активных почт + проверка вручную
- 📜 История полученных кодов
- ⭐ Купить Premium через Stars
- ℹ️ Помощь

---

## 🔧 Технологии

- **aiogram 3** — Telegram Bot API
- **mail.tm** — бесплатный API временных почт (без регистрации)
- **SQLAlchemy async** + **aiosqlite** — база данных
- **pydantic-settings** — конфигурация через `.env`
