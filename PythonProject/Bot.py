import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Конфигурация
BOT_TOKEN = "7339755623:AAF6KM6ZMJb6Xw9UOw304J7jxzaEr5xFHYI"
ADMIN_ID = 2104918787

# Каналы для проверки подписки (3 спонсора)
CHANNELS = ["@DeadSmoke2", "@DeadSmoke2", "@DeadSmoke2"]  # Замените на реальные каналы

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# База данных
DB_NAME = 'bot_database.db'

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Состояния для админ панели
class AdminStates(StatesGroup):
    waiting_broadcast_message = State()
    waiting_user_message = State()
    waiting_user_id = State()


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        stage INTEGER DEFAULT 1,
        subscribed BOOLEAN DEFAULT 0,
        screenshot1_sent BOOLEAN DEFAULT 0,
        screenshot2_sent BOOLEAN DEFAULT 0,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Таблица сообщений для админа
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_text TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        from_admin BOOLEAN DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()


def check_and_update_db():
    """Проверить и обновить структуру базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Проверить существование таблицы users
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        # Таблица не существует, создать новую
        init_db()
        conn.close()
        return

    # Проверить столбцы таблицы users
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    # Добавить недостающие столбцы
    if 'first_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
        logger.info("Added column 'first_name' to users table")

    if 'last_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
        logger.info("Added column 'last_name' to users table")

    if 'username' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        logger.info("Added column 'username' to users table")

    if 'stage' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN stage INTEGER DEFAULT 1")
        logger.info("Added column 'stage' to users table")

    if 'subscribed' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN subscribed BOOLEAN DEFAULT 0")
        logger.info("Added column 'subscribed' to users table")

    if 'screenshot1_sent' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN screenshot1_sent BOOLEAN DEFAULT 0")
        logger.info("Added column 'screenshot1_sent' to users table")

    if 'screenshot2_sent' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN screenshot2_sent BOOLEAN DEFAULT 0")
        logger.info("Added column 'screenshot2_sent' to users table")

    if 'registered_at' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        logger.info("Added column 'registered_at' to users table")

    if 'last_activity' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        logger.info("Added column 'last_activity' to users table")

    conn.commit()

    # Проверить таблицу admin_messages
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_messages'")
    if not cursor.fetchone():
        cursor.execute('''
        CREATE TABLE admin_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_text TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            from_admin BOOLEAN DEFAULT 0
        )
        ''')
        logger.info("Created table 'admin_messages'")

    conn.commit()
    conn.close()


def get_user_data(user_id: int) -> Optional[Dict]:
    """Получить данные пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
        SELECT user_id, username, first_name, last_name, stage, subscribed, 
               screenshot1_sent, screenshot2_sent, registered_at, last_activity
        FROM users WHERE user_id = ?
        ''', (user_id,))

        row = cursor.fetchone()
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting user data: {e}")
        row = None

    conn.close()

    if row:
        return {
            'user_id': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'stage': row[4] if row[4] is not None else 1,
            'subscribed': bool(row[5]) if row[5] is not None else False,
            'screenshot1_sent': bool(row[6]) if row[6] is not None else False,
            'screenshot2_sent': bool(row[7]) if row[7] is not None else False,
            'registered_at': row[8],
            'last_activity': row[9]
        }
    return None


def get_all_users(limit: int = 100, offset: int = 0) -> List[Dict]:
    """Получить список всех пользователей"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
        SELECT user_id, username, first_name, last_name, stage, subscribed, 
               screenshot1_sent, screenshot2_sent, registered_at, last_activity
        FROM users 
        ORDER BY registered_at DESC
        LIMIT ? OFFSET ?
        ''', (limit, offset))

        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting all users: {e}")
        rows = []

    conn.close()

    users = []
    for row in rows:
        users.append({
            'user_id': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'stage': row[4] if row[4] is not None else 1,
            'subscribed': bool(row[5]) if row[5] is not None else False,
            'screenshot1_sent': bool(row[6]) if row[6] is not None else False,
            'screenshot2_sent': bool(row[7]) if row[7] is not None else False,
            'registered_at': row[8],
            'last_activity': row[9]
        })

    return users


def get_users_count() -> int:
    """Получить общее количество пользователей"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0] or 0
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting users count: {e}")
        count = 0

    conn.close()
    return count


def update_user(user_id: int, username: str, first_name: str, last_name: str):
    """Обновить или создать пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # Проверить, существует ли пользователь
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        existing_user = cursor.fetchone()

        if existing_user:
            # Обновить существующего пользователя
            cursor.execute('''
            UPDATE users SET 
                username = COALESCE(?, username), 
                first_name = COALESCE(?, first_name), 
                last_name = COALESCE(?, last_name), 
                last_activity = CURRENT_TIMESTAMP 
            WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
        else:
            # Создать нового пользователя с начальными значениями
            cursor.execute('''
            INSERT INTO users 
            (user_id, username, first_name, last_name, stage, subscribed, 
             screenshot1_sent, screenshot2_sent, last_activity)
            VALUES (?, ?, ?, ?, 1, 0, 0, 0, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))

        conn.commit()
    except sqlite3.OperationalError as e:
        logger.error(f"Error updating user: {e}")
        conn.rollback()

    conn.close()


def mark_subscribed(user_id: int):
    """Отметить подписку пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
        UPDATE users SET subscribed = 1, stage = 2, last_activity = CURRENT_TIMESTAMP 
        WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.error(f"Error marking subscribed: {e}")

    conn.close()


def mark_screenshot1(user_id: int):
    """Отметить отправку первого скриншота"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
        UPDATE users SET screenshot1_sent = 1, stage = 3, last_activity = CURRENT_TIMESTAMP 
        WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.error(f"Error marking screenshot1: {e}")

    conn.close()


def mark_screenshot2(user_id: int):
    """Отметить отправку второго скриншота"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
        UPDATE users SET screenshot2_sent = 1, stage = 4, last_activity = CURRENT_TIMESTAMP 
        WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.error(f"Error marking screenshot2: {e}")

    conn.close()


def save_message(user_id: int, message_text: str, from_admin: bool = False):
    """Сохранить сообщение в историю"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('''
        INSERT INTO admin_messages (user_id, message_text, from_admin)
        VALUES (?, ?, ?)
        ''', (user_id, message_text, int(from_admin)))
        conn.commit()
    except sqlite3.OperationalError as e:
        logger.error(f"Error saving message: {e}")

    conn.close()


async def check_subscription(user_id: int) -> bool:
    """Проверить подписку на каналы"""
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked", "restricted"]:
                return False
        except Exception as e:
            logger.error(f"Error checking subscription to {channel}: {e}")
            return False
    return True


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = message.from_user

    # Сохраняем/обновляем пользователя в БД
    update_user(user.id, user.username, user.first_name, user.last_name)

    # Получаем данные пользователя
    user_data = get_user_data(user.id)

    # Проверяем подписку
    is_subscribed = await check_subscription(user.id)

    if not is_subscribed:
        # Пользователь не подписан - показываем каналы с кнопками
        keyboard = []

        # Добавляем кнопки для каждого канала
        for channel in CHANNELS:
            # Убираем @ из начала для создания ссылки
            channel_name = channel.lstrip('@')
            channel_url = f"https://t.me/{channel_name}"
            keyboard.append([InlineKeyboardButton(text=f"📢 {channel}", url=channel_url)])

        # Добавляем кнопку "Проверить подписку"
        keyboard.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            f"👋 Привет, {user.first_name or 'друг'}! Для работы бота нужно выполнить 3 простых шага:\n\n"
            f"📋 <b>Шаг 1 из 3:</b> Подписаться на каналы спонсоров:\n\n"
            f"1. {CHANNELS[0]}\n"
            f"2. {CHANNELS[1]}\n"
            f"3. {CHANNELS[2]}\n\n"
            "⚠️ Без подписки получить мишку не получится✨\n\n"
            "Нажмите на кнопки выше чтобы подписаться, затем нажмите 'Проверить подписку'",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    # Пользователь подписан, определяем его текущий этап
    current_stage = user_data.get('stage', 1) if user_data else 1
    screenshot1_sent = user_data.get('screenshot1_sent', False) if user_data else False
    screenshot2_sent = user_data.get('screenshot2_sent', False) if user_data else False

    if current_stage == 1:
        # Пользователь только начал, переводим на этап 2
        mark_subscribed(user.id)
        await message.answer(
            "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
            "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
            "с текстом:\n<code>Работает, мишку получил</code>\n\n"
            "📸 После этого отправьте нам скриншот ответа!",
            parse_mode='HTML'
        )

    elif current_stage == 2:
        if not screenshot1_sent:
            # На этапе 2, еще не отправлял первый скрин
            await message.answer(
                "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
                "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
                "с текстом:\n<code>Работает, мишку получил</code>\n\n"
                "📸 После этого отправьте нам скриншот ответа!",
                parse_mode='HTML'
            )
        else:
            # На этапе 2, но уже отправил первый скрин - исправляем состояние
            mark_screenshot1(user.id)
            await message.answer(
                "✅ <b>Первый скриншот уже получен!</b>\n\n"
                "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
                "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
                "📸 Отправьте нам скриншот комментария!",
                parse_mode='HTML'
            )

    elif current_stage == 3:
        if not screenshot2_sent:
            # На этапе 3, ждет второй скрин
            await message.answer(
                "✅ <b>Первый скриншот уже получен!</b>\n\n"
                "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
                "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
                "📸 Отправьте нам скриншот комментария!",
                parse_mode='HTML'
            )
        else:
            # На этапе 3, но уже отправил второй скрин - исправляем состояние
            mark_screenshot2(user.id)
            await message.answer(
                "🎉 <b>Спасибо за помощь!</b>\n\n"
                "🤖 Наш бот полностью бесплатен, поэтому эти шаги очень важны для нас!\n\n"
                "⏳ Из-за загруженности бота вашу заявку рассмотрит модератор "
                "в течение 72 часов и отправит приз!\n\n"
                "✅ Вы выполнили все шаги! Ожидайте приз!",
                parse_mode='HTML'
            )

    elif current_stage >= 4:
        # Уже завершил все этапы
        await message.answer(
            "✅ Вы уже выполнили все шаги! Ваша заявка рассматривается модератором.\n\n"
            "⏰ Срок рассмотрения: до 72 часов\n"
            "🎁 Приз будет отправлен автоматически после проверки!",
            parse_mode='HTML'
        )

    else:
        # Неизвестное состояние, начинаем с начала
        mark_subscribed(user.id)
        await message.answer(
            "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
            "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
            "с текстом:\n<code>Работает, мишку получил</code>\n\n"
            "📸 После этого отправьте нам скриншот ответа!",
            parse_mode='HTML'
        )


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    """Обработчик проверки подписки через кнопку"""
    user = callback.from_user
    is_subscribed = await check_subscription(user.id)

    if not is_subscribed:
        # Пользователь все еще не подписался
        keyboard = []

        # Добавляем кнопки для каждого канала
        for channel in CHANNELS:
            # Убираем @ из начала для создания ссылки
            channel_name = channel.lstrip('@')
            channel_url = f"https://t.me/{channel_name}"
            keyboard.append([InlineKeyboardButton(text=f"📢 {channel}", url=channel_url)])

        # Добавляем кнопку "Проверить подписку"
        keyboard.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            f"❌ Вы еще не подписались на все каналы!\n\n"
            f"📋 <b>Пожалуйста, подпишитесь на:</b>\n\n"
            f"1. {CHANNELS[0]}\n"
            f"2. {CHANNELS[1]}\n"
            f"3. {CHANNELS[2]}\n\n"
            "Нажмите на кнопки выше чтобы подписаться, затем нажмите 'Проверить подписку'",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        await callback.answer("Вы еще не подписались на все каналы!")
        return

    # Пользователь подписан
    user_data = get_user_data(user.id)
    if not user_data:
        # Создаем пользователя если его нет
        update_user(user.id, user.username, user.first_name, user.last_name)
        user_data = get_user_data(user.id)

    current_stage = user_data.get('stage', 1) if user_data else 1
    screenshot1_sent = user_data.get('screenshot1_sent', False) if user_data else False
    screenshot2_sent = user_data.get('screenshot2_sent', False) if user_data else False

    if current_stage == 1:
        # Начинаем с этапа 2
        mark_subscribed(user.id)
        await callback.message.edit_text(
            "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
            "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
            "с текстом:\n<code>Работает, мишку получил</code>\n\n"
            "📸 После этого отправьте нам скриншот ответа!",
            parse_mode='HTML'
        )

    elif current_stage == 2:
        if not screenshot1_sent:
            # На этапе 2, еще не отправлял первый скрин
            await callback.message.edit_text(
                "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
                "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
                "с текстом:\n<code>Работает, мишку получил</code>\n\n"
                "📸 После этого отправьте нам скриншот ответа!",
                parse_mode='HTML'
            )
        else:
            # На этапе 2, но уже отправил первый скрин - исправляем состояние
            mark_screenshot1(user.id)
            await callback.message.edit_text(
                "✅ <b>Первый скриншот уже получен!</b>\n\n"
                "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
                "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
                "📸 Отправьте нам скриншот комментария!",
                parse_mode='HTML'
            )

    elif current_stage == 3:
        if not screenshot2_sent:
            # На этапе 3, ждет второй скрин
            await callback.message.edit_text(
                "✅ <b>Первый скриншот уже получен!</b>\n\n"
                "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
                "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
                "📸 Отправьте нам скриншот комментария!",
                parse_mode='HTML'
            )
        else:
            # На этапе 3, но уже отправил второй скрин - исправляем состояние
            mark_screenshot2(user.id)
            await callback.message.edit_text(
                "🎉 <b>Спасибо за помощь!</b>\n\n"
                "🤖 Наш бот полностью бесплатен, поэтому эти шаги очень важны для нас!\n\n"
                "⏳ Из-за загруженности бота вашу заявку рассмотрит модератор "
                "в течение 72 часов и отправит приз!\n\n"
                "✅ Вы выполнили все шаги! Ожидайте приз!",
                parse_mode='HTML'
            )

    elif current_stage >= 4:
        # Уже завершил все этапы
        await callback.message.edit_text(
            "✅ Вы уже выполнили все шаги! Ваша заявка рассматривается модератором.\n\n"
            "⏰ Срок рассмотрения: до 72 часов\n"
            "🎁 Приз будет отправлен автоматически после проверки!",
            parse_mode='HTML'
        )

    else:
        # По умолчанию
        mark_subscribed(user.id)
        await callback.message.edit_text(
            "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
            "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
            "с текстом:\n<code>Работает, мишку получил</code>\n\n"
            "📸 После этого отправьте нам скриншот ответа!",
            parse_mode='HTML'
        )

    await callback.answer()


@dp.message(Command("check"))
async def cmd_check(message: Message):
    """Проверка подписки"""
    user = message.from_user
    is_subscribed = await check_subscription(user.id)

    if not is_subscribed:
        # Пользователь не подписан - показываем каналы с кнопками
        keyboard = []

        # Добавляем кнопки для каждого канала
        for channel in CHANNELS:
            # Убираем @ из начала для создания ссылки
            channel_name = channel.lstrip('@')
            channel_url = f"https://t.me/{channel_name}"
            keyboard.append([InlineKeyboardButton(text=f"📢 {channel}", url=channel_url)])

        # Добавляем кнопку "Проверить подписку"
        keyboard.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            f"❌ Вы еще не подписались на все каналы!\n\n"
            f"📋 <b>Пожалуйста, подпишитесь на:</b>\n\n"
            f"1. {CHANNELS[0]}\n"
            f"2. {CHANNELS[1]}\n"
            f"3. {CHANNELS[2]}\n\n"
            "Нажмите на кнопки выше чтобы подписаться, затем нажмите 'Проверить подписку'",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    # Пользователь подписан
    user_data = get_user_data(user.id)
    if not user_data:
        # Создаем пользователя если его нет
        update_user(user.id, user.username, user.first_name, user.last_name)
        user_data = get_user_data(user.id)

    current_stage = user_data.get('stage', 1) if user_data else 1
    screenshot1_sent = user_data.get('screenshot1_sent', False) if user_data else False
    screenshot2_sent = user_data.get('screenshot2_sent', False) if user_data else False

    if current_stage == 1:
        # Начинаем с этапа 2
        mark_subscribed(user.id)
        await message.answer(
            "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
            "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
            "с текстом:\n<code>Работает, мишку получил</code>\n\n"
            "📸 После этого отправьте нам скриншот ответа!",
            parse_mode='HTML'
        )

    elif current_stage == 2:
        if not screenshot1_sent:
            # На этапе 2, еще не отправлял первый скрин
            await message.answer(
                "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
                "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
                "с текстом:\n<code>Работает, мишку получил</code>\n\n"
                "📸 После этого отправьте нам скриншот ответа!",
                parse_mode='HTML'
            )
        else:
            # На этапе 2, но уже отправил первый скрин - исправляем состояние
            mark_screenshot1(user.id)
            await message.answer(
                "✅ <b>Первый скриншот уже получен!</b>\n\n"
                "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
                "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
                "📸 Отправьте нам скриншот комментария!",
                parse_mode='HTML'
            )

    elif current_stage == 3:
        if not screenshot2_sent:
            # На этапе 3, ждет второй скрин
            await message.answer(
                "✅ <b>Первый скриншот уже получен!</b>\n\n"
                "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
                "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
                "📸 Отправьте нам скриншот комментария!",
                parse_mode='HTML'
            )
        else:
            # На этапе 3, но уже отправил второй скрин - исправляем состояние
            mark_screenshot2(user.id)
            await message.answer(
                "🎉 <b>Спасибо за помощь!</b>\n\n"
                "🤖 Наш бот полностью бесплатен, поэтому эти шаги очень важны для нас!\n\n"
                "⏳ Из-за загруженности бота вашу заявку рассмотрит модератор "
                "в течение 72 часов и отправит приз!\n\n"
                "✅ Вы выполнили все шаги! Ожидайте приз!",
                parse_mode='HTML'
            )

    elif current_stage >= 4:
        # Уже завершил все этапы
        await message.answer(
            "✅ Вы уже выполнили все шаги! Ваша заявка рассматривается модератором.\n\n"
            "⏰ Срок рассмотрения: до 72 часов\n"
            "🎁 Приз будет отправлен автоматически после проверки!",
            parse_mode='HTML'
        )

    else:
        # По умолчанию
        mark_subscribed(user.id)
        await message.answer(
            "✅ <b>Отлично!</b> Вы подписались на все каналы!\n\n"
            "📝 <b>Шаг 2 из 3:</b> Напишите ответ к комментарию, по которому нашли этого бота, "
            "с текстом:\n<code>Работает, мишку получил</code>\n\n"
            "📸 После этого отправьте нам скриншот ответа!",
            parse_mode='HTML'
        )


@dp.message(F.photo)
async def handle_photo(message: Message):
    """Обработка скриншотов"""
    user = message.from_user

    # Получаем данные пользователя
    user_data = get_user_data(user.id)

    if not user_data:
        # Если пользователя нет в БД, создаем его
        update_user(user.id, user.username, user.first_name, user.last_name)
        user_data = get_user_data(user.id)

        if not user_data:
            await message.answer("Пожалуйста, сначала начните с /start")
            return

    current_stage = user_data.get('stage', 1)
    screenshot1_sent = user_data.get('screenshot1_sent', False)
    screenshot2_sent = user_data.get('screenshot2_sent', False)

    # Проверяем подписку пользователя
    is_subscribed = await check_subscription(user.id)

    if not is_subscribed:
        # Если пользователь не подписан
        keyboard = []

        # Добавляем кнопки для каждого канала
        for channel in CHANNELS:
            # Убираем @ из начала для создания ссылки
            channel_name = channel.lstrip('@')
            channel_url = f"https://t.me/{channel_name}"
            keyboard.append([InlineKeyboardButton(text=f"📢 {channel}", url=channel_url)])

        # Добавляем кнопку "Проверить подписку"
        keyboard.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            f"❌ Сначала нужно подписаться на каналы!\n\n"
            f"📋 <b>Пожалуйста, подпишитесь на:</b>\n\n"
            f"1. {CHANNELS[0]}\n"
            f"2. {CHANNELS[1]}\n"
            f"3. {CHANNELS[2]}\n\n"
            "Нажмите на кнопки выше чтобы подписаться, затем нажмите 'Проверить подписку'",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    if current_stage == 2 and not screenshot1_sent:
        # Первый скриншот - этап 2
        mark_screenshot1(user.id)
        await message.answer(
            "✅ <b>Отлично!</b> Первый скриншот получен!\n\n"
            "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
            "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
            "📸 Отправьте нам скриншот комментария!",
            parse_mode='HTML'
        )

    elif current_stage == 3 and not screenshot2_sent:
        # Второй скриншот - этап 3
        mark_screenshot2(user.id)
        await message.answer(
            "🎉 <b>Спасибо за помощь!</b>\n\n"
            "🤖 Наш бот полностью бесплатен, поэтому эти шаги очень важны для нас!\n\n"
            "⏳ Из-за загруженности бота вашу заявку рассмотрит модератор "
            "в течение 72 часов и отправит приз!\n\n"
            "✅ Вы выполнили все шаги! Ожидайте приз!",
            parse_mode='HTML'
        )

    elif current_stage == 2 and screenshot1_sent:
        # Уже отправил первый скрин, но состояние не обновилось
        mark_screenshot1(user.id)
        await message.answer(
            "✅ <b>Первый скриншот уже получен!</b>\n\n"
            "💬 <b>Шаг 3 из 3:</b> Напишите комментарий к любому видео:\n\n"
            "<code>@DemzooK_Bot, каждому по мишке</code>\n\n"
            "📸 Отправьте нам скриншот комментария!",
            parse_mode='HTML'
        )

    elif current_stage == 3 and screenshot2_sent:
        # Уже отправил второй скрин, но состояние не обновилось
        mark_screenshot2(user.id)
        await message.answer(
            "🎉 <b>Спасибо за помощь!</b>\n\n"
            "🤖 Наш бот полностью бесплатен, поэтому эти шаги очень важны для нас!\n\n"
            "⏳ Из-за загруженности бота вашу заявку рассмотрит модератор "
            "в течение 72 часов и отправит приз!\n\n"
            "✅ Вы выполнили все шаги! Ожидайте приз!",
            parse_mode='HTML'
        )

    elif current_stage >= 4:
        # Уже завершил все этапы
        await message.answer(
            "✅ Вы уже выполнили все шаги! Ваша заявка рассматривается модератором.\n\n"
            "⏰ Срок рассмотрения: до 72 часов\n"
            "🎁 Приз будет отправлен автоматически после проверки!",
            parse_mode='HTML'
        )

    else:
        # Неизвестное состояние
        await message.answer("✅ Скриншот получен! Продолжайте следовать инструкциям.", parse_mode='HTML')


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ панель"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    keyboard = [
        [InlineKeyboardButton(text="👥 Статистика игроков", callback_data="players")],
        [InlineKeyboardButton(text="📊 Статистика по дням", callback_data="days")],
        [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="broadcast")],
        [InlineKeyboardButton(text="💬 Написать пользователю", callback_data="write_user")],
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="find_user")],
        [InlineKeyboardButton(text="👤 Инфо пользователей", callback_data="users_info")]
    ]

    await message.answer(
        "🛠 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "players")
async def show_players_stats(callback: CallbackQuery):
    """Показать статистику по игрокам"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT COUNT(*) FROM users')
        total = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE subscribed = 1')
        subscribed = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE stage = 2')
        stage2 = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE stage = 3')
        stage3 = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE stage = 4')
        completed = cursor.fetchone()[0] or 0
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting player stats: {e}")
        total = subscribed = stage2 = stage3 = completed = 0

    conn.close()

    progress = round(completed / total * 100 if total > 0 else 0, 1)

    text = (
        f"📊 <b>Статистика игроков</b>\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"✅ Подписавшихся: {subscribed}\n"
        f"📝 На этапе 2: {stage2}\n"
        f"💬 На этапе 3: {stage3}\n"
        f"🎉 Завершили: {completed}\n\n"
        f"📈 Прогресс: {progress}%"
    )

    await callback.message.edit_text(text, parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == "days")
async def show_days_stats(callback: CallbackQuery):
    """Показать статистику за 7 и 30 дней"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # За 7 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE last_activity >= datetime('now', '-7 days')
        ''')
        last_7_days = cursor.fetchone()[0] or 0

        # За 30 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE last_activity >= datetime('now', '-30 days')
        ''')
        last_30_days = cursor.fetchone()[0] or 0

        # Новые за 7 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE registered_at >= datetime('now', '-7 days')
        ''')
        new_7_days = cursor.fetchone()[0] or 0

        # Новые за 30 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE registered_at >= datetime('now', '-30 days')
        ''')
        new_30_days = cursor.fetchone()[0] or 0
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting days stats: {e}")
        last_7_days = last_30_days = new_7_days = new_30_days = 0

    conn.close()

    text = (
        f"📅 <b>Статистика по дням</b>\n\n"
        f"🔄 <b>Активные пользователи:</b>\n"
        f"• За 7 дней: {last_7_days}\n"
        f"• За 30 дней: {last_30_days}\n\n"
        f"🆕 <b>Новые пользователи:</b>\n"
        f"• За 7 дней: {new_7_days}\n"
        f"• За 30 дней: {new_30_days}"
    )

    await callback.message.edit_text(text, parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == "broadcast")
async def broadcast_handler(callback: CallbackQuery, state: FSMContext):
    """Начать процесс рассылки"""
    await callback.message.edit_text(
        "📢 Введите сообщение для рассылки всем пользователям:"
    )
    await state.set_state(AdminStates.waiting_broadcast_message)
    await callback.answer()


@dp.message(AdminStates.waiting_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext):
    """Обработать сообщение для рассылки"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    message_text = message.text

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting users for broadcast: {e}")
        users = []
    conn.close()

    sent = 0
    failed = 0

    await message.answer(f"📤 Начинаю рассылку на {len(users)} пользователей...")

    for user_id_tuple in users:
        user_id = user_id_tuple[0]
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            sent += 1
            save_message(user_id, message_text, from_admin=True)
            await asyncio.sleep(0.05)  # Задержка чтобы не превысить лимиты
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Не отправлено: {failed}"
    )
    await state.clear()


@dp.callback_query(F.data == "write_user")
async def write_user_handler(callback: CallbackQuery, state: FSMContext):
    """Начать процесс отправки сообщения пользователю"""
    await callback.message.edit_text(
        "💬 Введите ID пользователя, которому хотите отправить сообщение:"
    )
    await state.set_state(AdminStates.waiting_user_id)
    await callback.answer()


@dp.message(AdminStates.waiting_user_id)
async def process_user_id(message: Message, state: FSMContext):
    """Обработать ID пользователя"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer(
            f"✅ ID пользователя сохранен: {user_id}\n"
            f"Теперь введите сообщение для этого пользователя:"
        )
        await state.set_state(AdminStates.waiting_user_message)
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите числовой ID:")


@dp.message(AdminStates.waiting_user_message)
async def process_user_message(message: Message, state: FSMContext):
    """Обработать сообщение для пользователя"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    data = await state.get_data()
    user_id = data.get('user_id')
    message_text = message.text

    try:
        await bot.send_message(
            chat_id=user_id,
            text=message_text
        )

        save_message(user_id, message_text, from_admin=True)
        await message.answer(f"✅ Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

    await state.clear()


@dp.callback_query(F.data == "find_user")
async def find_user_handler(callback: CallbackQuery):
    """Обработчик поиска пользователя"""
    keyboard = [
        [InlineKeyboardButton(text="⬅️ Назад в админ панель", callback_data="back_to_admin")]
    ]

    await callback.message.edit_text(
        "🔍 Для поиска информации о пользователе используйте команду:\n\n"
        "<code>/user USER_ID</code>\n\n"
        "Например: <code>/user 123456789</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode='HTML'
    )
    await callback.answer()


@dp.callback_query(F.data == "users_info")
async def users_info_handler(callback: CallbackQuery):
    """Показать информацию о пользователях"""
    users = get_all_users(limit=20)  # Получаем первых 20 пользователей
    total_users = get_users_count()

    if not users:
        await callback.message.edit_text("📭 В базе данных пока нет пользователей.")
        await callback.answer()
        return

    # Создаем клавиатуру с кнопками навигации
    keyboard = []

    # Добавляем информацию о пользователях
    text = f"👤 <b>Информация о пользователях</b>\n\n"
    text += f"📊 Всего пользователей: {total_users}\n\n"

    for i, user in enumerate(users, 1):
        username = f"@{user['username']}" if user['username'] else "нет юзернейма"
        stage_text = {
            1: "Не подписан",
            2: "Этап 2 (скрин 1)",
            3: "Этап 3 (скрин 2)",
            4: "Завершил"
        }.get(user.get('stage', 1), "Неизвестно")

        text += f"{i}. ID: <code>{user['user_id']}</code>\n"
        text += f"   👤 {user['first_name'] or 'Без имени'}\n"
        text += f"   📱 {username}\n"
        text += f"   📈 Этап: {stage_text}\n"
        text += f"   📅 Регистр: {user['registered_at'][:16] if user['registered_at'] else 'неизвестно'}\n\n"

    text += "\n📋 Используйте /user ID для подробной информации"

    keyboard.append([InlineKeyboardButton(text="⬅️ Назад в админ панель", callback_data="back_to_admin")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode='HTML'
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    """Вернуться в админ панель"""
    keyboard = [
        [InlineKeyboardButton(text="👥 Статистика игроков", callback_data="players")],
        [InlineKeyboardButton(text="📊 Статистика по дням", callback_data="days")],
        [InlineKeyboardButton(text="📢 Отправить сообщение всем", callback_data="broadcast")],
        [InlineKeyboardButton(text="💬 Написать пользователю", callback_data="write_user")],
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="find_user")],
        [InlineKeyboardButton(text="👤 Инфо пользователей", callback_data="users_info")]
    ]

    await callback.message.edit_text(
        "🛠 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode='HTML'
    )
    await callback.answer()


@dp.message(Command("user"))
async def cmd_user(message: Message):
    """Получить информацию о пользователе"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    if len(message.text.split()) < 2:
        await message.answer("❌ Использование: /user USER_ID")
        return

    try:
        user_id = int(message.text.split()[1])
        user_data = get_user_data(user_id)

        if not user_data:
            await message.answer(f"❌ Пользователь {user_id} не найден")
            return

        # Получаем историю сообщений
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM admin_messages WHERE user_id = ?', (user_id,))
            message_count = cursor.fetchone()[0] or 0
        except sqlite3.OperationalError:
            message_count = 0
        conn.close()

        stage_text = {
            1: "Не подписан",
            2: "Подписан, ждет 1 скрин",
            3: "Отправил 1 скрин, ждет 2 скрин",
            4: "Завершил все шаги"
        }.get(user_data.get('stage', 1), "Неизвестно")

        subscribed = user_data.get('subscribed', False)
        screenshot1_sent = user_data.get('screenshot1_sent', False)
        screenshot2_sent = user_data.get('screenshot2_sent', False)

        text = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 ID: <code>{user_data['user_id']}</code>\n"
            f"👤 Имя: {user_data.get('first_name', 'Не указано') or 'Не указано'}\n"
            f"📛 Фамилия: {user_data.get('last_name', 'Не указано') or 'Не указано'}\n"
            f"📱 Юзернейм: @{user_data.get('username', 'Не указан') or 'Не указан'}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"📈 Этап: {stage_text} ({user_data.get('stage', 1)})\n"
            f"✅ Подписан: {'Да' if subscribed else 'Нет'}\n"
            f"📸 Скрин 1: {'Да' if screenshot1_sent else 'Нет'}\n"
            f"📸 Скрин 2: {'Да' if screenshot2_sent else 'Нет'}\n\n"
            f"📅 Регистрация: {user_data.get('registered_at', 'Неизвестно')}\n"
            f"🕐 Последняя активность: {user_data.get('last_activity', 'Неизвестно')}\n\n"
            f"💬 Сообщений в истории: {message_count}"
        )

        await message.answer(text, parse_mode='HTML')
    except ValueError:
        await message.answer("❌ Неверный формат ID")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("players"))
async def cmd_players(message: Message):
    """Показать статистику игроков (команда)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT COUNT(*) FROM users')
        total = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE subscribed = 1')
        subscribed = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE stage = 2')
        stage2 = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE stage = 3')
        stage3 = cursor.fetchone()[0] or 0

        cursor.execute('SELECT COUNT(*) FROM users WHERE stage = 4')
        completed = cursor.fetchone()[0] or 0
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting player stats: {e}")
        total = subscribed = stage2 = stage3 = completed = 0

    conn.close()

    progress = round(completed / total * 100 if total > 0 else 0, 1)

    text = (
        f"📊 <b>Статистика игроков</b>\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"✅ Подписавшихся: {subscribed}\n"
        f"📝 На этапе 2: {stage2}\n"
        f"💬 На этапе 3: {stage3}\n"
        f"🎉 Завершили: {completed}\n\n"
        f"📈 Прогресс: {progress}%"
    )

    await message.answer(text, parse_mode='HTML')


@dp.message(Command("days"))
async def cmd_days(message: Message):
    """Показать статистику по дням (команда)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # За 7 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE last_activity >= datetime('now', '-7 days')
        ''')
        last_7_days = cursor.fetchone()[0] or 0

        # За 30 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE last_activity >= datetime('now', '-30 days')
        ''')
        last_30_days = cursor.fetchone()[0] or 0

        # Новые за 7 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE registered_at >= datetime('now', '-7 days')
        ''')
        new_7_days = cursor.fetchone()[0] or 0

        # Новые за 30 дней
        cursor.execute('''
        SELECT COUNT(*) FROM users 
        WHERE registered_at >= datetime('now', '-30 days')
        ''')
        new_30_days = cursor.fetchone()[0] or 0
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting days stats: {e}")
        last_7_days = last_30_days = new_7_days = new_30_days = 0

    conn.close()

    text = (
        f"📅 <b>Статистика по дням</b>\n\n"
        f"🔄 <b>Активные пользователи:</b>\n"
        f"• За 7 дней: {last_7_days}\n"
        f"• За 30 дней: {last_30_days}\n\n"
        f"🆕 <b>Новые пользователи:</b>\n"
        f"• За 7 дней: {new_7_days}\n"
        f"• За 30 дней: {new_30_days}"
    )

    await message.answer(text, parse_mode='HTML')


@dp.message(Command("message"))
async def cmd_message(message: Message):
    """Отправка сообщения всем пользователям (команда)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа!")
        return

    if len(message.text.split()) < 2:
        await message.answer("❌ Использование: /message ваш_текст_сообщения")
        return

    message_text = ' '.join(message.text.split()[1:])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"Error getting users for broadcast: {e}")
        users = []
    conn.close()

    sent = 0
    failed = 0

    await message.answer(f"📤 Начинаю рассылку на {len(users)} пользователей...")

    for user_id_tuple in users:
        user_id = user_id_tuple[0]
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            sent += 1
            save_message(user_id, message_text, from_admin=True)
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Не отправлено: {failed}"
    )


@dp.message()
async def handle_text(message: Message):
    """Обработка текстовых сообщений"""
    user = message.from_user
    message_text = message.text

    # Сохраняем сообщение от пользователя
    save_message(user.id, message_text, from_admin=False)

    user_data = get_user_data(user.id)

    if not user_data:
        await message.answer("Пожалуйста, сначала начните с /start")
        return

    # Если пользователь не подписан, напоминаем
    if not user_data.get('subscribed', False):
        is_subscribed = await check_subscription(user.id)
        if not is_subscribed:
            keyboard = []

            # Добавляем кнопки для каждого канала
            for channel in CHANNELS:
                # Убираем @ из начала для создания ссылки
                channel_name = channel.lstrip('@')
                channel_url = f"https://t.me/{channel_name}"
                keyboard.append([InlineKeyboardButton(text=f"📢 {channel}", url=channel_url)])

            # Добавляем кнопку "Проверить подписку"
            keyboard.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")])

            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

            await message.answer(
                f"❌ Сначала нужно подписаться на каналы!\n\n"
                f"📋 <b>Пожалуйста, подпишитесь на:</b>\n\n"
                f"1. {CHANNELS[0]}\n"
                f"2. {CHANNELS[1]}\n"
                f"3. {CHANNELS[2]}\n\n"
                "Нажмите на кнопки выше чтобы подписаться, затем нажмите 'Проверить подписку'",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return


async def main():
    """Основная функция запуска бота"""
    # Проверить и обновить структуру базы данных
    check_and_update_db()

    print("🤖 Бот запущен!")
    print("📊 База данных проверена и обновлена")
    print(f"📢 Каналы для подписки: {CHANNELS}")

    # Запуск бота
    await dp.start_polling(bot)


if __name__ == '__main__':
    # Установка библиотеки: pip install aiogram
    asyncio.run(main())