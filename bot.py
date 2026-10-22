import os
import json
import logging
import asyncio
import re

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
# تنظیمات ربات
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

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
TON_MINIMUM = Decimal("0.1")

STARS_PRICE = Decimal("4800")
STARS_MINIMUM = 1
STARS_MAXIMUM = 1000


# ==========================================
# تنظیم لاگ
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ==========================================
# وضعیت‌های مکالمه
# ==========================================

GET_PHONE = 1
GET_AMOUNT = 2
GET_WALLET = 3
GET_POST_LINK = 4
GET_RECEIPT = 5
SUPPORT_MESSAGE = 6


# ==========================================
# قفل‌ها
# نکته: این خط اصلاح شده است.
# ==========================================

storage_lock = asyncio.Lock()

order_locks = defaultdict(asyncio.Lock)


# ==========================================
# زمان
# ==========================================

def now():
    return datetime.now(timezone.utc).isoformat()


# ==========================================
# ذخیره و بارگذاری JSON
# ==========================================

def load_json(path):
    try:
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except (OSError, json.JSONDecodeError):
        logger.exception("خطا در خواندن فایل %s", path)
        return {}


def save_json(path, data):
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

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
            continue

    return max(ids, default=0) + 1


# ==========================================
# منوی اصلی
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
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "عضویت در کانال",
                    url=CHANNEL_LINK,
                )
            ],
            [
                InlineKeyboardButton(
                    "عضویت در گروه",
                    url=GROUP_LINK,
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ بررسی عضویت",
                    callback_data="check_membership",
                )
            ],
        ]
    )


# ==========================================
# بررسی عضویت
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
            logger.exception(
                "خطا در بررسی عضویت کاربر %s در %s",
                user_id,
                chat_id,
            )

            # اگر تلگرام خطا بدهد، طبق درخواست اجازه عبور می‌دهیم.
            continue

    return True


async def ensure_membership(update, context):
    if await is_member(update, context):
        return True

    await update.effective_message.reply_text(
        "برای استفاده از ربات، ابتدا در کانال و گروه عضو شو "
        "و سپس دکمه بررسی عضویت را بزن.",
        reply_markup=membership_keyboard(),
    )

    return False


async def membership_callback(update, context):
    query = update.callback_query
    await query.answer()

    if await is_member(update, context):
        uid = str(query.from_user.id)

        if not users.get(uid, {}).get("phone"):
            contact_button = KeyboardButton(
                "📱 ارسال شماره تلفن",
                request_contact=True,
            )

            await query.message.reply_text(
                "عضویتت تأیید شد ✅\n"
                "برای ادامه شماره تلفنت را ارسال کن.",
                reply_markup=ReplyKeyboardMarkup(
                    [[contact_button]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )

        else:
            await query.message.reply_text(
                "عضویتت تأیید شد ✅",
                reply_markup=menu(),
            )

    else:
        await query.message.reply_text(
            "هنوز عضویتت در کانال و گروه تأیید نشده است.",
            reply_markup=membership_keyboard(),
        )


# ==========================================
# شروع ربات
# ==========================================

async def start(update, context):
    user = update.effective_user
    uid = str(user.id)

    users.setdefault(
        uid,
        {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "phone": None,
            "created_at": now(),
        },
    )

    users[uid]["username"] = user.username
    users[uid]["first_name"] = user.first_name

    await save_users()

    if not await ensure_membership(update, context):
        return ConversationHandler.END

    if not users[uid].get("phone"):
        contact_button = KeyboardButton(
            "📱 ارسال شماره تلفن",
            request_contact=True,
        )

        await update.effective_message.reply_text(
            "سلام! 👋\n"
            "برای استفاده از ربات شماره تلفنت را ثبت کن.",
            reply_markup=ReplyKeyboardMarkup(
                [[contact_button]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )

        return GET_PHONE

    await update.effective_message.reply_text(
        "سلام! به ربات خوش اومدی 🌟",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# ==========================================
# ثبت شماره تلفن
# ==========================================

async def receive_phone(update, context):
    contact = update.effective_message.contact
    user = update.effective_user

    if not contact or contact.user_id != user.id:
        await update.effective_message.reply_text(
            "لطفاً شماره تلفن خودت را با دکمه ارسال شماره تلفن بفرست."
        )
        return GET_PHONE

    uid = str(user.id)

    users.setdefault(
        uid,
        {
            "user_id": user.id,
            "created_at": now(),
        },
    )

    users[uid]["phone"] = contact.phone_number
    users[uid]["username"] = user.username
    users[uid]["first_name"] = user.first_name

    await save_users()

    await update.effective_message.reply_text(
        "شماره تلفنت ثبت شد ✅",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# ==========================================
# شروع خرید
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

    if product == "DOGS":
        message = (
            "🐶 خرید DOGS\n\n"
            "قیمت هر DOGS: ۱۲ تومان\n"
            "حداقل خرید: ۱۰۰۰ عدد\n\n"
            "تعداد موردنظرت را وارد کن:"
        )

    elif product == "TON":
        message = (
            "💎 خرید TON\n\n"
            "هر ۰٫۱ TON برابر ۴۰٬۰۰۰ تومان است.\n"
            "حداقل خرید: ۰٫۱ TON\n\n"
            "مقدار موردنظرت را وارد کن؛ مثلاً ۰٫۱ یا ۱٫۲:"
        )

    else:
        message = (
            "⭐ خرید Telegram Stars\n\n"
            "قیمت هر Star: ۴٬۸۰۰ تومان\n"
            "حداقل خرید: ۱ عدد\n"
            "حداکثر خرید: ۱۰۰۰ عدد\n\n"
            "تعداد Stars موردنظرت را وارد کن:"
        )

    await update.effective_message.reply_text(
        message,
        reply_markup=ReplyKeyboardRemove(),
    )

    return GET_AMOUNT


async def select_dogs(update, context):
    return await begin_product(update, context, "DOGS")


async def select_ton(update, context):
    return await begin_product(update, context, "TON")


async def select_stars(update, context):
    return await begin_product(update, context, "Stars")


# ==========================================
# محاسبه مبلغ
# ==========================================

def calculate_price(product, amount_text):
    try:
        text = (
            amount_text.strip()
            .replace(",", ".")
            .replace("٫", ".")
            .replace("٬", "")
        )

        amount = Decimal(text)

    except (InvalidOperation, AttributeError):
        raise ValueError("لطفاً مقدار را به‌صورت عددی وارد کن.")

    if not amount.is_finite():
        raise ValueError("مقدار واردشده معتبر نیست.")

    if product == "DOGS":

        if (
            amount != amount.to_integral_value()
            or amount < DOGS_MINIMUM
        ):
            raise ValueError(
                "تعداد DOGS باید عدد صحیح و حداقل ۱۰۰۰ باشد."
            )

        total = amount * DOGS_PRICE

    elif product == "TON":

        if amount < TON_MINIMUM or amount % TON_UNIT != 0:
            raise ValueError(
                "مقدار TON باید حداقل ۰٫۱ و مضرب ۰٫۱ باشد."
            )

        total = (amount / TON_UNIT) * TON_UNIT_PRICE

    elif product == "Stars":

        if (
            amount != amount.to_integral_value()
            or amount < STARS_MINIMUM
            or amount > STARS_MAXIMUM
        ):
            raise ValueError(
                "تعداد Stars باید عدد صحیحی بین ۱ تا ۱۰۰۰ باشد."
            )

        total = amount * STARS_PRICE

    else:
        raise ValueError("محصول انتخاب‌شده معتبر نیست.")

    return amount, total


def format_number(value):
    value = Decimal(str(value))
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def format_toman(value):
    return f"{Decimal(str(value)):,.0f}"


# ==========================================
# دریافت تعداد محصول
# ==========================================

async def receive_amount(update, context):
    product = context.user_data.get("product")

    if not product:
        await update.effective_message.reply_text(
            "لطفاً از منوی اصلی یک محصول انتخاب کن.",
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
            "🔗 حالا لینک پست تلگرام را ارسال کن.\n\n"
            "مثال:\n"
            "https://t.me/channelname/123"
        )

        return GET_POST_LINK

    await update.effective_message.reply_text(
        "👛 آدرس کیف پول مقصد را وارد کن:"
    )

    return GET_WALLET


# ==========================================
# ساخت سفارش
# ==========================================

async def create_order(update, context, wallet=None, post_link=None):
    user = update.effective_user
    uid = str(user.id)

    product = context.user_data["product"]
    amount = context.user_data["amount"]
    total = context.user_data["total"]

    async with storage_lock:
        order_id = next_order_id()

        order = {
            "order_id": order_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "phone": users.get(uid, {}).get("phone"),
            "product": product,
            "amount": amount,
            "wallet": wallet,
            "post_link": post_link,
            "total": total,
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
        f"📦 محصول: {product}\n"
        f"🔢 مقدار: {format_number(amount)}\n"
        f"💰 مبلغ: {format_toman(total)} تومان\n\n"
        f"💳 شماره کارت:\n{CARD_NUMBER}\n\n"
        f"👤 صاحب کارت: {CARD_HOLDER}\n\n"
    )

    if product == "Stars":
        details += f"🔗 لینک پست:\n{post_link}\n\n"
    else:
        details += f"👛 آدرس کیف پول:\n{wallet}\n\n"

    details += "پس از پرداخت، عکس رسید را ارسال کن."

    await update.effective_message.reply_text(details)

    return GET_RECEIPT


# ==========================================
# دریافت آدرس کیف پول DOGS و TON
# ==========================================

async def receive_wallet(update, context):
    wallet = update.effective_message.text.strip()

    if not 5 <= len(wallet) <= 300:
        await update.effective_message.reply_text(
            "آدرس کیف پول معتبر نیست؛ لطفاً دوباره وارد کن."
        )
        return GET_WALLET

    context.user_data["wallet"] = wallet

    return await create_order(
        update,
        context,
        wallet=wallet,
    )


# ==========================================
# دریافت لینک پست Stars
# ==========================================

def is_valid_telegram_post_link(link):
    patterns = [
        r"^https?://t\.me/[A-Za-z0-9_]+/\d+/?(?:\?.*)?$",
        r"^https?://t\.me/c/\d+/\d+/?(?:\?.*)?$",
        r"^https?://telegram\.me/[A-Za-z0-9_]+/\d+/?(?:\?.*)?$",
    ]

    return any(
        re.match(pattern, link.strip())
        for pattern in patterns
    )


async def receive_post_link(update, context):
    post_link = update.effective_message.text.strip()

    if not is_valid_telegram_post_link(post_link):
        await update.effective_message.reply_text(
            "❌ لینک پست معتبر نیست.\n\n"
            "لینکی شبیه این ارسال کن:\n"
            "https://t.me/channelname/123"
        )
        return GET_POST_LINK

    context.user_data["post_link"] = post_link

    return await create_order(
        update,
        context,
        post_link=post_link,
    )


# ==========================================
# دریافت رسید
# ==========================================

async def receive_receipt(update, context):
    order_id = context.user_data.get("current_order_id")

    if not order_id:
        await update.effective_message.reply_text(
            "سفارش فعالی پیدا نشد. از منوی اصلی دوباره شروع کن.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    if not update.effective_message.photo:
        await update.effective_message.reply_text(
            "لطفاً عکس رسید را به‌صورت عکس ارسال کن."
        )
        return GET_RECEIPT

    key = str(order_id)

    async with order_locks[key]:
        order = orders.get(key)

        if not order or order.get("status") != "awaiting_receipt":
            await update.effective_message.reply_text(
                "این سفارش دیگر منتظر رسید نیست."
            )
            return ConversationHandler.END

        receipt_file_id = update.effective_message.photo[-1].file_id

        order["receipt_file_id"] = receipt_file_id
        order["status"] = "pending_admin"
        order["updated_at"] = now()

        await save_orders()

    username = (
        f"@{order['username']}"
        if order.get("username")
        else "ثبت نشده"
    )

    caption = (
        f"🧾 سفارش جدید شماره {order_id}\n\n"
        f"👤 نام: {order.get('first_name') or 'ثبت نشده'}\n"
        f"🆔 شناسه کاربر: {order['user_id']}\n"
        f"🔗 نام کاربری: {username}\n"
        f"📱 تلفن: {order.get('phone') or 'ثبت نشده'}\n\n"
        f"📦 محصول: {order['product']}\n"
        f"🔢 مقدار: {format_number(order['amount'])}\n"
        f"💰 مبلغ: {format_toman(order['total'])} تومان\n"
    )

    if order["product"] == "Stars":
        caption += f"\n🔗 لینک پست:\n{order.get('post_link')}"
    else:
        caption += f"\n👛 کیف پول:\n{order.get('wallet')}"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید سفارش",
                    callback_data=f"approve:{order_id}",
                ),
                InlineKeyboardButton(
                    "❌ رد سفارش",
                    callback_data=f"reject:{order_id}",
                ),
            ]
        ]
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=receipt_file_id,
            caption=caption,
            reply_markup=keyboard,
        )

    except TelegramError:
        logger.exception("ارسال سفارش برای مدیر ناموفق بود")

        async with order_locks[key]:
            order["status"] = "receipt_delivery_failed"
            order["updated_at"] = now()
            await save_orders()

        await update.effective_message.reply_text(
            "ارسال رسید برای مدیر با خطا مواجه شد. "
            "لطفاً با پشتیبانی تماس بگیر."
        )

        return ConversationHandler.END

    await update.effective_message.reply_text(
        "رسیدت برای مدیر ارسال شد ✅\n"
        "پس از بررسی، نتیجه بهت اطلاع داده می‌شه.",
        reply_markup=menu(),
    )

    context.user_data.pop("current_order_id", None)
    context.user_data.pop("product", None)

    return ConversationHandler.END


# ==========================================
# تأیید و رد سفارش توسط مدیر
# ==========================================

async def admin_order_action(update, context):
    query = update.callback_query

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer(
            "این دکمه فقط برای مدیر است.",
            show_alert=True,
        )
        return

    await query.answer()

    action, order_id_text = query.data.split(":", 1)

    order_id = int(order_id_text)
    key = str(order_id)

    async with order_locks[key]:
        order = orders.get(key)

        if not order:
            await query.message.reply_text(
                "سفارش پیدا نشد."
            )
            return

        if order.get("status") != "pending_admin":
            await query.message.reply_text(
                "این سفارش قبلاً بررسی شده یا قابل بررسی نیست."
            )
            return

        if action == "reject":
            order["status"] = "rejected"
            order["updated_at"] = now()

            await save_orders()

        elif action == "approve":
            order["status"] = "approved_publishing"
            order["updated_at"] = now()

            await save_orders()

        else:
            return

    # رد سفارش: به کانال چیزی ارسال نمی‌شود.
    if action == "reject":
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"❌ سفارش شماره {order_id} رد شد.\n\n"
                    "برای پیگیری با پشتیبانی تماس بگیر."
                ),
            )
        except TelegramError:
            logger.exception("ارسال پیام رد به کاربر ناموفق بود")

        try:
            await query.edit_message_caption(
                caption=(
                    (query.message.caption or "")
                    + "\n\n❌ سفارش توسط مدیر رد شد."
                ),
                reply_markup=None,
            )
        except TelegramError:
            logger.exception("ویرایش پیام مدیر ناموفق بود")

        return

    # تأیید سفارش: انتشار در کانال
    channel_text = (
        f"✅ سفارش تأییدشده شماره {order_id}\n\n"
        f"📦 محصول: {order['product']}\n"
        f"🔢 مقدار: {format_number(order['amount'])}\n"
        f"💰 مبلغ: {format_toman(order['total'])} تومان"
    )

    if order["product"] == "Stars":
        channel_text += f"\n🔗 لینک پست:\n{order.get('post_link')}"
    else:
        channel_text += f"\n👛 آدرس کیف پول:\n{order.get('wallet')}"

    try:
        await context.bot.send_message(
            chat_id=ORDER_CHANNEL,
            text=channel_text,
            disable_web_page_preview=True,
        )

    except TelegramError:
        logger.exception("انتشار سفارش در کانال ناموفق بود")

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
            text=(
                f"✅ سفارش شماره {order_id} تأیید شد.\n\n"
                "سفارش در کانال منتشر شد."
            ),
        )
    except TelegramError:
        logger.exception("ارسال پیام تأیید به کاربر ناموفق بود")

    try:
        await query.edit_message_caption(
            caption=(
                (query.message.caption or "")
                + "\n\n✅ سفارش تأیید و در کانال منتشر شد."
            ),
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
        "👤 حساب کاربری\n\n"
        f"🆔 شناسه: {uid}\n"
        f"نام: {user.get('first_name') or 'ثبت نشده'}\n"
        f"نام کاربری: @{user.get('username') or 'ثبت نشده'}\n"
        f"شماره تلفن: {user.get('phone') or 'ثبت نشده'}",
        reply_markup=menu(),
    )


# ==========================================
# سفارش‌های من
# ==========================================

async def my_orders(update, context):
    user_id = update.effective_user.id

    user_orders = [
        order
        for order in orders.values()
        if order.get("user_id") == user_id
    ]

    if not user_orders:
        await update.effective_message.reply_text(
            "هنوز سفارشی ثبت نکردی.",
            reply_markup=menu(),
        )
        return

    user_orders.sort(
        key=lambda item: item.get("order_id", 0),
        reverse=True,
    )

    status_names = {
        "awaiting_receipt": "در انتظار رسید",
        "pending_admin": "در انتظار بررسی مدیر",
        "approved_publishing": "در حال انتشار",
        "approved_publish_failed": "تأیید شده، انتشار ناموفق",
        "receipt_delivery_failed": "خطا در ارسال رسید برای مدیر",
        "approved": "تأیید شده",
        "rejected": "رد شده",
    }

    lines = ["📦 سفارش‌های شما:\n"]

    for order in user_orders[:20]:
        lines.append(
            f"شماره سفارش: {order['order_id']}\n"
            f"محصول: {order['product']}\n"
            f"مقدار: {format_number(order['amount'])}\n"
            f"مبلغ: {format_toman(order['total'])} تومان\n"
            f"وضعیت: {status_names.get(order['status'], order['status'])}\n"
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
        "پیامت رو برای پشتیبانی بفرست.\n"
        "می‌تونی متن یا عکس ارسال کنی.\n"
        "برای لغو /cancel رو بزن.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return SUPPORT_MESSAGE


async def support_receive(update, context):
    user = update.effective_user

    username = (
        f"@{user.username}"
        if user.username
        else "ثبت نشده"
    )

    header = (
        "📞 پیام جدید پشتیبانی\n\n"
        f"👤 نام: {user.first_name or 'ثبت نشده'}\n"
        f"🆔 شناسه کاربر: {user.id}\n"
        f"🔗 نام کاربری: {username}"
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
            "ارسال پیام ناموفق بود. بعداً دوباره تلاش کن.",
            reply_markup=menu(),
        )

        return ConversationHandler.END

    await update.effective_message.reply_text(
        "پیامت برای پشتیبانی ارسال شد ✅",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# ==========================================
# راهنما
# ==========================================

async def help_command(update, context):
    await update.effective_message.reply_text(
        "ℹ️ راهنمای ربات\n\n"
        "🐶 DOGS: هر عدد ۱۲ تومان؛ حداقل ۱۰۰۰ عدد.\n"
        "💎 TON: هر ۰٫۱ TON برابر ۴۰٬۰۰۰ تومان.\n"
        "⭐ Stars: هر عدد ۴٬۸۰۰ تومان؛ از ۱ تا ۱۰۰۰ عدد.\n\n"
        "برای خرید Stars باید لینک پست تلگرام را ارسال کنی.\n"
        "بعد از نمایش مبلغ و شماره کارت، پرداخت کن و عکس رسید را بفرست.\n"
        "پس از بررسی مدیر، نتیجه برایت ارسال می‌شود.\n\n"
        "برای لغو عملیات /cancel را بزن.",
        reply_markup=menu(),
    )


# ==========================================
# لغو عملیات
# ==========================================

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
        1 for order in orders.values()
        if order.get("status") == "approved"
    )

    pending = sum(
        1 for order in orders.values()
        if order.get("status") == "pending_admin"
    )

    rejected = sum(
        1 for order in orders.values()
        if order.get("status") == "rejected"
    )

    await update.effective_message.reply_text(
        "📊 آمار ربات\n\n"
        f"👥 کاربران: {total_users}\n"
        f"📦 کل سفارش‌ها: {total_orders}\n"
        f"⏳ در انتظار بررسی: {pending}\n"
        f"✅ تأییدشده و منتشرشده: {approved}\n"
        f"❌ ردشده: {rejected}"
    )


# ==========================================
# مدیریت خطا
# ==========================================

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
            "BOT_TOKEN تنظیم نشده است. آن را در Secrets وارد کن."
        )

    if ADMIN_CHAT_ID == 0:
        raise RuntimeError(
            "ADMIN_CHAT_ID تنظیم نشده است."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),

            MessageHandler(
                filters.Regex(r"^🛒 خرید DOGS$"),
                select_dogs,
            ),

            MessageHandler(
                filters.Regex(r"^💎 خرید TON$"),
                select_ton,
            ),

            MessageHandler(
                filters.Regex(r"^⭐ خرید Stars$"),
                select_stars,
            ),

            MessageHandler(
                filters.Regex(r"^📞 پشتیبانی$"),
                support_start,
            ),
        ],

        states={
            GET_PHONE: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
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
        MessageHandler(
            filters.Regex(r"^👤 حساب کاربری$"),
            account,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.Regex(r"^📦 سفارش‌های من$"),
            my_orders,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.Regex(r"^ℹ️ راهنما$"),
            help_command,
        )
    )

    application.add_handler(
        CommandHandler("admin", admin_stats)
    )

    application.add_error_handler(error_handler)

    logger.info("ربات در حال اجراست...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
 
