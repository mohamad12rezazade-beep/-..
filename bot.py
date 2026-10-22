import os
import json
import re
import asyncio
import logging

from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==========================================
# تنظیمات
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# آیدی مدیر
ADMIN_CHAT_ID = 8935601841

CARD_NUMBER = "6219861856357990"
CARD_HOLDER = "رضازاده"

REQUIRED_CHANNEL = "@BNI_MMAD"
REQUIRED_GROUP = "@BNI_MMAD1"

CHANNEL_LINK = "https://t.me/BNI_MMAD"
GROUP_LINK = "https://t.me/BNI_MMAD1"

ORDER_CHANNEL = "@BNI_MMAD"

DATA_DIR = Path(__file__).resolve().parent
USERS_FILE = DATA_DIR / "users.json"
ORDERS_FILE = DATA_DIR / "orders.json"

DOGS_PRICE = Decimal("12")
DOGS_MINIMUM = Decimal("1000")

TON_UNIT = Decimal("0.1")
TON_UNIT_PRICE = Decimal("40000")

STARS_PRICE = Decimal("4800")
STARS_MINIMUM = 1
STARS_MAXIMUM = 1000

GET_PHONE = 1
GET_AMOUNT = 2
GET_WALLET = 3
GET_POST_LINK = 4
GET_RECEIPT = 5
SUPPORT_MESSAGE = 6

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

storage_lock = asyncio.Lock()
order_locks = defaultdict(asyncio.Lock)


# ==========================================
# JSON
# ==========================================

def now():
    return datetime.now(timezone.utc).isoformat()


def load_json(path):
    try:
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}

    except (OSError, json.JSONDecodeError):
        logger.exception("خطا در خواندن %s", path)
        return {}


def save_json(path, data):
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    temp_path.replace(path)


users = load_json(USERS_FILE)
orders = load_json(ORDERS_FILE)


async def save_users():
    async with storage_lock:
        save_json(USERS_FILE, users)


async def save_orders():
    async with storage_lock:
        save_json(ORDERS_FILE, orders)


def next_order_id():
    ids = []

    for key in orders:
        try:
            ids.append(int(key))
        except (ValueError, TypeError):
            pass

    return max(ids, default=0) + 1


# ==========================================
# منوها
# ==========================================

def menu():
    return ReplyKeyboardMarkup(
        [
            ["🛒 خرید DOGS", "💎 خرید TON"],
            ["⭐ خرید Stars"],
            ["📦 سفارش‌های من", "👤 حساب کاربری"],
            ["📞 پشتیبانی", "ℹ️ راهنما"],
        ],
        resize_keyboard=True,
    )


def membership_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("عضویت در کانال", url=CHANNEL_LINK)],
        [InlineKeyboardButton("عضویت در گروه", url=GROUP_LINK)],
        [InlineKeyboardButton(
            "✅ بررسی عضویت",
            callback_data="check_membership",
        )],
    ])


# ==========================================
# عضویت
# ==========================================

async def is_member(update, context):
    user_id = update.effective_user.id

    for chat_id in (REQUIRED_CHANNEL, REQUIRED_GROUP):
        try:
            member = await context.bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )

            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.KICKED,
            ):
                return False

        except TelegramError:
            logger.exception("خطا در بررسی عضویت")
            continue

    return True


async def ensure_membership(update, context):
    if await is_member(update, context):
        return True

    await update.effective_message.reply_text(
        "ابتدا در کانال و گروه عضو شو و سپس عضویتت را بررسی کن.",
        reply_markup=membership_keyboard(),
    )

    return False


async def membership_callback(update, context):
    query = update.callback_query
    await query.answer()

    if await is_member(update, context):
        uid = str(query.from_user.id)

        if not users.get(uid, {}).get("phone"):
            button = KeyboardButton(
                "📱 ارسال شماره تلفن",
                request_contact=True,
            )

            await query.message.reply_text(
                "عضویت تأیید شد. شماره تلفنت را ثبت کن.",
                reply_markup=ReplyKeyboardMarkup(
                    [[button]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
        else:
            await query.message.reply_text(
                "عضویت تأیید شد.",
                reply_markup=menu(),
            )
    else:
        await query.message.reply_text(
            "هنوز عضو کانال و گروه نشده‌ای.",
            reply_markup=membership_keyboard(),
        )


# ==========================================
# شروع
# ==========================================

async def start(update, context):
    user = update.effective_user
    uid = str(user.id)

    users.setdefault(uid, {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "phone": None,
        "created_at": now(),
    })

    users[uid]["username"] = user.username
    users[uid]["first_name"] = user.first_name

    await save_users()

    if not await ensure_membership(update, context):
        return ConversationHandler.END

    if not users[uid].get("phone"):
        button = KeyboardButton(
            "📱 ارسال شماره تلفن",
            request_contact=True,
        )

        await update.effective_message.reply_text(
            "سلام! برای ادامه شماره تلفنت را ثبت کن.",
            reply_markup=ReplyKeyboardMarkup(
                [[button]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )

        return GET_PHONE

    await update.effective_message.reply_text(
        "به ربات خوش آمدی!",
        reply_markup=menu(),
    )

    return ConversationHandler.END


async def receive_phone(update, context):
    contact = update.effective_message.contact
    user = update.effective_user

    if not contact or contact.user_id != user.id:
        await update.effective_message.reply_text(
            "لطفاً با دکمه مخصوص، شماره تلفن خودت را ارسال کن."
        )
        return GET_PHONE

    uid = str(user.id)

    users.setdefault(uid, {
        "user_id": user.id,
        "created_at": now(),
    })

    users[uid]["phone"] = contact.phone_number
    users[uid]["username"] = user.username
    users[uid]["first_name"] = user.first_name

    await save_users()

    await update.effective_message.reply_text(
        "شماره تلفن ثبت شد.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# ==========================================
# خرید
# ==========================================

async def begin_product(update, context, product):
    if not await ensure_membership(update, context):
        return ConversationHandler.END

    uid = str(update.effective_user.id)

    if not users.get(uid, {}).get("phone"):
        await update.effective_message.reply_text(
            "ابتدا /start را بزن و شماره تلفنت را ثبت کن."
        )
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["product"] = product

    messages = {
        "DOGS": (
            "🐶 خرید DOGS\n"
            "هر عدد: ۱۲ تومان\n"
            "حداقل: ۱۰۰۰ عدد\n\n"
            "تعداد را وارد کن:"
        ),
        "TON": (
            "💎 خرید TON\n"
            "هر ۰٫۱ TON برابر ۴۰٬۰۰۰ تومان است.\n"
            "مقدار باید مضربی از ۰٫۱ باشد.\n\n"
            "مثلاً ۰٫۱ یا ۱٫۲ را وارد کن:"
        ),
        "Stars": (
            "⭐ خرید Stars\n"
            "هر عدد: ۴٬۸۰۰ تومان\n"
            "حداقل: ۱ و حداکثر: ۱۰۰۰ عدد\n\n"
            "تعداد را وارد کن:"
        ),
    }

    await update.effective_message.reply_text(
        messages[product],
        reply_markup=ReplyKeyboardRemove(),
    )

    return GET_AMOUNT


async def select_dogs(update, context):
    return await begin_product(update, context, "DOGS")


async def select_ton(update, context):
    return await begin_product(update, context, "TON")


async def select_stars(update, context):
    return await begin_product(update, context, "Stars")


def calculate_price(product, text):
    try:
        text = (
            text.strip()
            .replace(",", ".")
            .replace("٫", ".")
            .replace("٬", "")
        )

        amount = Decimal(text)

    except (InvalidOperation, AttributeError):
        raise ValueError("لطفاً یک عدد معتبر وارد کن.")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("مقدار باید یک عدد مثبت باشد.")

    if product == "DOGS":
        if amount != amount.to_integral_value() or amount < DOGS_MINIMUM:
            raise ValueError("حداقل خرید DOGS برابر ۱۰۰۰ عدد است.")

        total = amount * DOGS_PRICE

    elif product == "TON":
        if amount < TON_UNIT or amount % TON_UNIT != 0:
            raise ValueError("مقدار TON باید مضربی از ۰٫۱ باشد.")

        total = (amount / TON_UNIT) * TON_UNIT_PRICE

    elif product == "Stars":
        if (
            amount != amount.to_integral_value()
            or amount < STARS_MINIMUM
            or amount > STARS_MAXIMUM
        ):
            raise ValueError("تعداد Stars باید بین ۱ تا ۱۰۰۰ باشد.")

        total = amount * STARS_PRICE

    else:
        raise ValueError("محصول نامعتبر است.")

    return amount, total


def format_number(value):
    return f"{Decimal(str(value)):,.2f}".rstrip("0").rstrip(".")


def format_toman(value):
    return f"{Decimal(str(value)):,.0f}"


async def receive_amount(update, context):
    product = context.user_data.get("product")

    if not product:
        await update.effective_message.reply_text(
            "از منو یک محصول انتخاب کن.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    try:
        amount, total = calculate_price(
            product,
            update.effective_message.text,
        )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return GET_AMOUNT

    context.user_data["amount"] = str(amount)
    context.user_data["total"] = str(total)

    if product == "Stars":
        await update.effective_message.reply_text(
            "لینک پست تلگرام را بفرست.\n"
            "مثال: https://t.me/channelname/123"
        )
        return GET_POST_LINK

    await update.effective_message.reply_text(
        "آدرس کیف پول مقصد را ارسال کن:"
    )

    return GET_WALLET


async def create_order(update, context, wallet=None, post_link=None):
    user = update.effective_user
    uid = str(user.id)

    async with storage_lock:
        order_id = next_order_id()

        order = {
            "order_id": order_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "phone": users.get(uid, {}).get("phone"),
            "product": context.user_data["product"],
            "amount": context.user_data["amount"],
            "wallet": wallet,
            "post_link": post_link,
            "total": context.user_data["total"],
            "status": "awaiting_receipt",
            "receipt_file_id": None,
            "created_at": now(),
            "updated_at": now(),
        }

        orders[str(order_id)] = order
        save_json(ORDERS_FILE, orders)

    context.user_data["current_order_id"] = order_id

    details = (
        f"🧾 سفارش شماره {order_id}\n\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {format_number(order['amount'])}\n"
        f"مبلغ: {format_toman(order['total'])} تومان\n\n"
        f"💳 شماره کارت: {CARD_NUMBER}\n"
        f"👤 صاحب کارت: {CARD_HOLDER}\n\n"
    )

    if post_link:
        details += f"🔗 لینک پست:\n{post_link}\n\n"
    else:
        details += f"👛 کیف پول:\n{wallet}\n\n"

    details += "پس از پرداخت، عکس رسید را ارسال کن."

    await update.effective_message.reply_text(details)

    return GET_RECEIPT


async def receive_wallet(update, context):
    wallet = update.effective_message.text.strip()

    if not 5 <= len(wallet) <= 300:
        await update.effective_message.reply_text(
            "آدرس کیف پول معتبر نیست. دوباره بفرست."
        )
        return GET_WALLET

    return await create_order(update, context, wallet=wallet)


def is_valid_telegram_post_link(link):
    return bool(re.match(
        r"^https?://(?:t\.me|telegram\.me)/(?:c/\d+|[A-Za-z0-9_]+)/\d+/?(?:\?.*)?$",
        link.strip(),
    ))


async def receive_post_link(update, context):
    post_link = update.effective_message.text.strip()

    if not is_valid_telegram_post_link(post_link):
        await update.effective_message.reply_text(
            "لینک معتبر نیست.\n"
            "مثال: https://t.me/channelname/123"
        )
        return GET_POST_LINK

    return await create_order(update, context, post_link=post_link)


# ==========================================
# رسید پرداخت
# ==========================================

async def receive_receipt(update, context):
    order_id = context.user_data.get("current_order_id")

    if not order_id:
        await update.effective_message.reply_text(
            "سفارش فعالی پیدا نشد.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    if not update.effective_message.photo:
        await update.effective_message.reply_text(
            "لطفاً عکس رسید را ارسال کن."
        )
        return GET_RECEIPT

    key = str(order_id)

    async with order_locks[key]:
        order = orders.get(key)

        if not order or order["status"] != "awaiting_receipt":
            await update.effective_message.reply_text(
                "این سفارش دیگر منتظر رسید نیست."
            )
            return ConversationHandler.END

        receipt_id = update.effective_message.photo[-1].file_id

        order["receipt_file_id"] = receipt_id
        order["status"] = "pending_admin"
        order["updated_at"] = now()

        await save_orders()

    username = "@" + order["username"] if order.get("username") else "ثبت نشده"

    caption = (
        f"🧾 سفارش شماره {order_id}\n\n"
        f"نام: {order.get('first_name') or 'ثبت نشده'}\n"
        f"شناسه: {order['user_id']}\n"
        f"نام کاربری: {username}\n"
        f"تلفن: {order.get('phone') or 'ثبت نشده'}\n\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {format_number(order['amount'])}\n"
        f"مبلغ: {format_toman(order['total'])} تومان\n"
    )

    if order["product"] == "Stars":
        caption += f"\nلینک پست:\n{order['post_link']}"
    else:
        caption += f"\nکیف پول:\n{order['wallet']}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تأیید",
                callback_data=f"approve:{order_id}",
            ),
            InlineKeyboardButton(
                "❌ رد",
                callback_data=f"reject:{order_id}",
            ),
        ]
    ])

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=receipt_id,
            caption=caption,
            reply_markup=keyboard,
        )
    except TelegramError:
        logger.exception("ارسال رسید برای مدیر ناموفق بود")

        async with order_locks[key]:
            order["status"] = "receipt_delivery_failed"
            order["updated_at"] = now()
            await save_orders()

        await update.effective_message.reply_text(
            "ارسال رسید برای مدیر ناموفق بود. با پشتیبانی تماس بگیر."
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "رسید برای مدیر ارسال شد. منتظر بررسی باش.",
        reply_markup=menu(),
    )

    context.user_data.clear()
    return ConversationHandler.END


# ==========================================
# تأیید و رد سفارش
# ==========================================

async def admin_order_action(update, context):
    query = update.callback_query

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer("این دکمه فقط برای مدیر است.", show_alert=True)
        return

    await query.answer()

    action, order_id_text = query.data.split(":", 1)
    order_id = int(order_id_text)
    key = str(order_id)

    async with order_locks[key]:
        order = orders.get(key)

        if not order:
            await query.message.reply_text("سفارش پیدا نشد.")
            return

        if order["status"] != "pending_admin":
            await query.message.reply_text(
                "این سفارش قبلاً بررسی شده است."
            )
            return

        if action == "reject":
            order["status"] = "rejected"
            order["updated_at"] = now()
        elif action == "approve":
            order["status"] = "approved_publishing"
            order["updated_at"] = now()
        else:
            return

        await save_orders()

    if action == "reject":
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"❌ سفارش شماره {order_id} رد شد.",
            )
        except TelegramError:
            logger.exception("ارسال پیام رد ناموفق بود")

        try:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n❌ سفارش رد شد.",
                reply_markup=None,
            )
        except TelegramError:
            logger.exception("ویرایش پیام مدیر ناموفق بود")

        return

    channel_text = (
        f"✅ سفارش تأییدشده شماره {order_id}\n\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {format_number(order['amount'])}\n"
        f"مبلغ: {format_toman(order['total'])} تومان"
    )

    if order["product"] == "Stars":
        channel_text += f"\n🔗 لینک پست:\n{order['post_link']}"
    else:
        channel_text += f"\n👛 کیف پول:\n{order['wallet']}"

    try:
        await context.bot.send_message(
            chat_id=ORDER_CHANNEL,
            text=channel_text,
            disable_web_page_preview=True,
        )
    except TelegramError:
        logger.exception("انتشار در کانال ناموفق بود")

        async with order_locks[key]:
            order["status"] = "approved_publish_failed"
            order["updated_at"] = now()
            await save_orders()

        await query.message.reply_text(
            "سفارش تأیید شد، اما انتشار در کانال ناموفق بود. "
            "دسترسی ربات به کانال را بررسی کن."
        )
        return

    async with order_locks[key]:
        order["status"] = "approved"
        order["updated_at"] = now()
        await save_orders()

    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"✅ سفارش شماره {order_id} تأیید و در کانال منتشر شد.",
        )
    except TelegramError:
        logger.exception("پیام تأیید به کاربر ارسال نشد")

    try:
        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n✅ تأیید و منتشر شد.",
            reply_markup=None,
        )
    except TelegramError:
        logger.exception("ویرایش پیام مدیر ناموفق بود")


# ==========================================
# حساب کاربری
# ==========================================

async def account(update, context):
    uid = str(update.effective_user.id)
    user = users.get(uid, {})

    await update.effective_message.reply_text(
        f"👤 حساب کاربری\n\n"
        f"شناسه: {uid}\n"
        f"نام: {user.get('first_name') or 'ثبت نشده'}\n"
        f"نام کاربری: @{user.get('username') or 'ثبت نشده'}\n"
        f"تلفن: {user.get('phone') or 'ثبت نشده'}",
        reply_markup=menu(),
    )


# ==========================================
# سفارش‌های من
# ==========================================

async def my_orders(update, context):
    user_id = update.effective_user.id

    items = [
        item for item in orders.values()
        if item.get("user_id") == user_id
    ]

    if not items:
        await update.effective_message.reply_text(
            "هنوز سفارشی ثبت نکرده‌ای.",
            reply_markup=menu(),
        )
        return

    items.sort(
        key=lambda item: item.get("order_id", 0),
        reverse=True,
    )

    statuses = {
        "awaiting_receipt": "در انتظار رسید",
        "pending_admin": "در انتظار بررسی مدیر",
        "approved_publishing": "در حال انتشار",
        "approved_publish_failed": "انتشار ناموفق",
        "receipt_delivery_failed": "خطا در ارسال رسید",
        "approved": "تأیید شده",
        "rejected": "رد شده",
    }

    lines = ["📦 سفارش‌های من\n"]

    for item in items[:20]:
        lines.append(
            f"شماره: {item['order_id']}\n"
            f"محصول: {item['product']}\n"
            f"مقدار: {format_number(item['amount'])}\n"
            f"مبلغ: {format_toman(item['total'])} تومان\n"
            f"وضعیت: {statuses.get(item['status'], item['status'])}\n"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=menu(),
    )


# ==========================================
# پشتیبانی
# ==========================================

async def support_start(update, context):
    await update.effective_message.reply_text(
        "پیام یا عکس خود را ارسال کن.\nبرای لغو /cancel را بزن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SUPPORT_MESSAGE


async def support_receive(update, context):
    user = update.effective_user

    header = (
        "📞 پیام جدید پشتیبانی\n\n"
        f"نام: {user.first_name or 'ثبت نشده'}\n"
        f"شناسه: {user.id}\n"
        f"نام کاربری: @{user.username or 'ثبت نشده'}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=header,
        )

        await context.bot.copy_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
        )

    except TelegramError:
        logger.exception("ارسال پیام پشتیبانی ناموفق بود")
        await update.effective_message.reply_text(
            "ارسال پیام ناموفق بود.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "پیامت برای پشتیبانی ارسال شد.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# ==========================================
# راهنما و لغو
# ==========================================

async def help_command(update, context):
    await update.effective_message.reply_text(
        "ℹ️ راهنمای ربات\n\n"
        "🐶 DOGS: هر عدد ۱۲ تومان؛ حداقل ۱۰۰۰ عدد.\n"
        "💎 TON: هر ۰٫۱ برابر ۴۰٬۰۰۰ تومان.\n"
        "⭐ Stars: هر عدد ۴٬۸۰۰ تومان؛ از ۱ تا ۱۰۰۰ عدد.\n\n"
        "محصول را انتخاب کن، مقدار را وارد کن، پرداخت کن "
        "و عکس رسید را بفرست.\n"
        "نتیجه پس از بررسی مدیر اعلام می‌شود.\n"
        "برای لغو عملیات /cancel را بزن.",
        reply_markup=menu(),
    )


async def cancel(update, context):
    context.user_data.clear()

    await update.effective_message.reply_text(
        "عملیات لغو شد.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# ==========================================
# آمار مدیر
# ==========================================

async def admin_stats(update, context):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.effective_message.reply_text(
            "این دستور فقط برای مدیر است."
        )
        return

    total_users = len(users)
    total_orders = len(orders)

    approved = sum(
        1 for item in orders.values()
        if item.get("status") == "approved"
    )

    pending = sum(
        1 for item in orders.values()
        if item.get("status") == "pending_admin"
    )

    rejected = sum(
        1 for item in orders.values()
        if item.get("status") == "rejected"
    )

    await update.effective_message.reply_text(
        f"📊 آمار ربات\n\n"
        f"کاربران: {total_users}\n"
        f"کل سفارش‌ها: {total_orders}\n"
        f"در انتظار بررسی: {pending}\n"
        f"تأییدشده: {approved}\n"
        f"ردشده: {rejected}"
    )


async def error_handler(update, context):
    logger.error(
        "خطای پیش‌بینی‌نشده",
        exc_info=context.error,
    )


# ==========================================
# اجرای ربات
# ==========================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است. "
            "در GitHub Secrets مقدار BOT_TOKEN را تنظیم کن."
        )

    # ADMIN_CHAT_ID مستقیماً در بالای فایل تنظیم شده است.
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^🛒 خرید DOGS$"), select_dogs),
            MessageHandler(filters.Regex(r"^💎 خرید TON$"), select_ton),
            MessageHandler(filters.Regex(r"^⭐ خرید Stars$"), select_stars),
            MessageHandler(filters.Regex(r"^📞 پشتیبانی$"), support_start),
        ],
        states={
            GET_PHONE: [
                MessageHandler(
                    filters.CONTACT | filters.ALL,
                    receive_phone,
                ),
            ],
            GET_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_amount,
                ),
            ],
            GET_WALLET: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_wallet,
                ),
            ],
            GET_POST_LINK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_post_link,
                ),
            ],
            GET_RECEIPT: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    receive_receipt,
                ),
            ],
            SUPPORT_MESSAGE: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    support_receive,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )

    application.add_handler(conversation)

    application.add_handler(
        CallbackQueryHandler(
            membership_callback,
            pattern=r"^check_membership$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_order_action,
            pattern=r"^(approve|reject):\d+$",
        )
    )

    application.add_handler(
        MessageHandler(filters.Regex(r"^👤 حساب کاربری$"), account)
    )

    application.add_handler(
        MessageHandler(filters.Regex(r"^📦 سفارش‌های من$"), my_orders)
    )

    application.add_handler(
        MessageHandler(filters.Regex(r"^ℹ️ راهنما$"), help_command)
    )

    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_error_handler(error_handler)

    logger.info("ربات در حال اجراست...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
