import os
import json
import logging
import asyncio

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path

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


# =====================================================
# تنظیمات
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8714704830:AAGYitrRQQ0TLv2Zg-fc1gbKTyi6Jm08n-g")

# آیدی عددی مدیر را وارد کن.
ADMIN_CHAT_ID = 8935601841

CARD_NUMBER = "6219861856357990"
CARD_HOLDER = "رضازاده"

REQUIRED_CHANNEL = "@BNI_MMAD"
REQUIRED_GROUP = "@BNI_MMAD1"

CHANNEL_LINK = "https://t.me/BNI_MMAD"
GROUP_LINK = "https://t.me/BNI_MMAD1"

DATA_DIR = Path(__file__).resolve().parent

USERS_FILE = DATA_DIR / "users.json"
ORDERS_FILE = DATA_DIR / "orders.json"

DOGS_PRICE = Decimal("12")
DOGS_MINIMUM = Decimal("1000")

TON_UNIT = Decimal("0.1")
TON_UNIT_PRICE = Decimal("40000")
TON_MINIMUM = Decimal("0.1")


# =====================================================
# گزارش‌گیری
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =====================================================
# وضعیت‌های مکالمه
# =====================================================

GET_PHONE = 1
GET_AMOUNT = 2
GET_WALLET = 3
GET_RECEIPT = 4
SUPPORT_MESSAGE = 5


# =====================================================
# فایل‌های JSON
# =====================================================

def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        logger.exception("خطا در خواندن فایل %s", path)
        return default


def save_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")

    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.flush()
        os.fsync(file.fileno())

    os.replace(temporary, path)


users = load_json(USERS_FILE, {})
orders = load_json(ORDERS_FILE, {})

storage_lock = asyncio.Lock()

# جلوگیری از بررسی هم‌زمان یک سفارش
order_locks = defaultdict(asyncio.Lock)


async def save_users():
    async with storage_lock:
        save_json(USERS_FILE, users)


async def save_orders():
    async with storage_lock:
        save_json(ORDERS_FILE, orders)


def next_order_id():
    return max(
        (int(key) for key in orders),
        default=0,
    ) + 1


# =====================================================
# ابزارهای عمومی
# =====================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    return f"{Decimal(str(value)):,.0f}"


def decimal_text(value):
    return format(Decimal(str(value)).normalize(), "f")


def menu():
    return ReplyKeyboardMarkup(
        [
            ["🛒 خرید DOGS", "💎 خرید TON"],
            ["📦 سفارش‌های من", "👤 حساب کاربری"],
            ["📞 پشتیبانی", "ℹ️ راهنما"],
        ],
        resize_keyboard=True,
    )


def membership_menu():
    return InlineKeyboardMarkup([
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
                "بررسی مجدد عضویت",
                callback_data="check_membership",
            )
        ],
    ])


def admin_only(update):
    return (
        update.effective_user is not None
        and update.effective_user.id == ADMIN_CHAT_ID
    )


# =====================================================
# بررسی عضویت
# =====================================================

async def check_one_membership(bot, user_id, chat_id):
    try:
        member = await bot.get_chat_member(
            chat_id=chat_id,
            user_id=user_id,
        )

        if member.status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        ):
            return False

        return True

    except TelegramError:
        # خطای API به‌تنهایی باعث رد کاربر نمی‌شود.
        logger.exception(
            "خطا در بررسی عضویت کاربر %s در %s",
            user_id,
            chat_id,
        )
        return True

    except Exception:
        logger.exception(
            "خطای غیرمنتظره در بررسی عضویت"
        )
        return True


async def check_membership(bot, user_id):
    channel_ok = await check_one_membership(
        bot,
        user_id,
        REQUIRED_CHANNEL,
    )

    group_ok = await check_one_membership(
        bot,
        user_id,
        REQUIRED_GROUP,
    )

    return channel_ok and group_ok


# =====================================================
# شروع ربات
# =====================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return ConversationHandler.END

    uid = str(user.id)

    if uid not in users:
        users[uid] = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "phone": None,
            "created_at": now(),
        }
    else:
        users[uid]["username"] = user.username
        users[uid]["first_name"] = user.first_name

    try:
        await save_users()
    except OSError:
        logger.exception("ذخیره اطلاعات کاربر ناموفق بود")
        await message.reply_text(
            "خطا در ذخیره اطلاعات. بعداً دوباره تلاش کن."
        )
        return ConversationHandler.END

    if not await check_membership(context.bot, user.id):
        await message.reply_text(
            "برای استفاده از ربات، ابتدا عضو کانال و گروه شو.",
            reply_markup=membership_menu(),
        )
        return ConversationHandler.END

    if not users[uid].get("phone"):
        keyboard = ReplyKeyboardMarkup(
            [[
                KeyboardButton(
                    "📱 ارسال شماره تلفن",
                    request_contact=True,
                )
            ]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await message.reply_text(
            "سلام!\nبرای ثبت‌نام شماره تلفنت را ارسال کن.",
            reply_markup=keyboard,
        )

        return GET_PHONE

    await message.reply_text(
        "خوش آمدی! محصول موردنظر را انتخاب کن.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# =====================================================
# دریافت شماره تلفن
# =====================================================

async def receive_phone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return ConversationHandler.END

    uid = str(user.id)

    if users.get(uid, {}).get("phone"):
        await message.reply_text(
            "شماره تلفنت قبلاً ثبت شده است.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    if not message.contact:
        await message.reply_text(
            "لطفاً از دکمه ارسال شماره تلفن استفاده کن."
        )
        return GET_PHONE

    if message.contact.user_id != user.id:
        await message.reply_text(
            "باید شماره تلفن متعلق به حساب خودت را ارسال کنی."
        )
        return GET_PHONE

    users[uid]["phone"] = message.contact.phone_number

    try:
        await save_users()
    except OSError:
        logger.exception("ذخیره شماره تلفن ناموفق بود")
        users[uid]["phone"] = None

        await message.reply_text(
            "ثبت شماره تلفن ناموفق بود. دوباره تلاش کن."
        )
        return GET_PHONE

    await message.reply_text(
        "شماره تلفن ثبت شد.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# =====================================================
# بررسی مجدد عضویت
# =====================================================

async def membership_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    uid = str(user.id)

    if not await check_membership(context.bot, user.id):
        await query.message.reply_text(
            "عضویت شما تأیید نشده است.",
            reply_markup=membership_menu(),
        )
        return

    if uid not in users:
        users[uid] = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "phone": None,
            "created_at": now(),
        }
        await save_users()

    if not users[uid].get("phone"):
        keyboard = ReplyKeyboardMarkup(
            [[
                KeyboardButton(
                    "📱 ارسال شماره تلفن",
                    request_contact=True,
                )
            ]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await query.message.reply_text(
            "عضویت بررسی شد. شماره تلفنت را ارسال کن.",
            reply_markup=keyboard,
        )
    else:
        await query.message.reply_text(
            "عضویت بررسی شد. می‌توانی خرید کنی.",
            reply_markup=menu(),
        )


# =====================================================
# انتخاب محصول
# =====================================================

async def select_dogs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["product"] = "DOGS"

    await update.effective_message.reply_text(
        "🪙 خرید DOGS\n\n"
        "قیمت هر عدد: ۱۲ تومان\n"
        "حداقل سفارش: ۱۰۰۰ عدد\n\n"
        "تعداد موردنظر را وارد کن:"
    )

    return GET_AMOUNT


async def select_ton(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["product"] = "TON"

    await update.effective_message.reply_text(
        "💎 خرید TON\n\n"
        "قیمت هر ۰٫۱ TON: ۴۰٬۰۰۰ تومان\n"
        "حداقل خرید: ۰٫۱ TON\n\n"
        "مقدار موردنظر را وارد کن؛ مثلاً 0.1 یا 0.5 یا 1:"
    )

    return GET_AMOUNT


# =====================================================
# محاسبه قیمت
# =====================================================

def calculate_price(product, amount):
    if not amount.is_finite() or amount <= 0:
        raise ValueError("مقدار باید عدد مثبت باشد.")

    if product == "DOGS":
        if amount != amount.to_integral_value():
            raise ValueError("تعداد DOGS باید عدد صحیح باشد.")

        if amount < DOGS_MINIMUM:
            raise ValueError("حداقل خرید DOGS برابر ۱۰۰۰ عدد است.")

        return amount * DOGS_PRICE

    if product == "TON":
        if amount < TON_MINIMUM:
            raise ValueError("حداقل خرید TON برابر ۰٫۱ است.")

        units = amount / TON_UNIT

        if units != units.to_integral_value():
            raise ValueError("مقدار TON باید مضربی از ۰٫۱ باشد.")

        return units * TON_UNIT_PRICE

    raise ValueError("محصول نامعتبر است.")


async def receive_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    try:
        amount = Decimal(message.text.strip())
        product = context.user_data.get("product")
        total = calculate_price(product, amount)

    except (InvalidOperation, ValueError, AttributeError) as exc:
        await message.reply_text(
            f"مقدار معتبر نیست: {exc}\nدوباره وارد کن."
        )
        return GET_AMOUNT

    context.user_data["amount"] = decimal_text(amount)
    context.user_data["total"] = decimal_text(total)

    await message.reply_text(
        f"محصول: {product}\n"
        f"مقدار: {decimal_text(amount)}\n"
        f"مبلغ نهایی: {money(total)} تومان\n\n"
        "حالا آدرس کیف پول مقصد را ارسال کن:"
    )

    return GET_WALLET


# =====================================================
# دریافت کیف پول و ایجاد سفارش
# =====================================================

async def receive_wallet(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    wallet = (message.text or "").strip()

    if not 5 <= len(wallet) <= 300:
        await message.reply_text(
            "آدرس کیف پول معتبر نیست. دوباره ارسال کن."
        )
        return GET_WALLET

    product = context.user_data.get("product")
    amount = context.user_data.get("amount")
    total = context.user_data.get("total")

    if not all((product, amount, total)):
        await message.reply_text(
            "اطلاعات سفارش ناقص است. دوباره محصول را انتخاب کن.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    uid = str(user.id)

    async with storage_lock:
        order_id = max(
            (int(key) for key in orders),
            default=0,
        ) + 1

        order = {
            "order_id": order_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "phone": users.get(uid, {}).get("phone"),
            "product": product,
            "amount": amount,
            "wallet": wallet,
            "total": total,
            "status": "awaiting_receipt",
            "receipt_file_id": None,
            "created_at": now(),
            "updated_at": now(),
        }

        orders[str(order_id)] = order

        try:
            save_json(ORDERS_FILE, orders)
        except OSError:
            orders.pop(str(order_id), None)
            logger.exception("ذخیره سفارش ناموفق بود")
            await message.reply_text(
                "ثبت سفارش ناموفق بود. دوباره تلاش کن."
            )
            return ConversationHandler.END

    context.user_data["order_id"] = order_id

    await message.reply_text(
        f"✅ سفارش شماره {order_id}\n\n"
        f"محصول: {product}\n"
        f"مقدار: {amount}\n"
        f"کیف پول مقصد:\n{wallet}\n\n"
        f"شماره کارت: {CARD_NUMBER}\n"
        f"به نام: {CARD_HOLDER}\n"
        f"مبلغ نهایی: {money(total)} تومان\n\n"
        "پس از پرداخت، عکس رسید را ارسال کن.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return GET_RECEIPT


# =====================================================
# دریافت رسید
# =====================================================

async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message.photo:
        await message.reply_text(
            "لطفاً تصویر رسید پرداخت را به‌صورت عکس ارسال کن."
        )
        return GET_RECEIPT

    order_id = context.user_data.get("order_id")

    if order_id is None:
        await message.reply_text(
            "سفارش فعالی پیدا نشد.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    order_key = str(order_id)
    order = orders.get(order_key)

    if not order or order["status"] != "awaiting_receipt":
        await message.reply_text(
            "این سفارش در انتظار رسید نیست.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    photo = message.photo[-1]

    order["receipt_file_id"] = photo.file_id
    order["status"] = "pending_admin"
    order["updated_at"] = now()

    try:
        await save_orders()
    except OSError:
        order["status"] = "awaiting_receipt"
        order["receipt_file_id"] = None

        logger.exception("ذخیره رسید ناموفق بود")
        await message.reply_text(
            "ذخیره رسید ناموفق بود. دوباره عکس را ارسال کن."
        )
        return GET_RECEIPT

    username = (
        f"@{order['username']}"
        if order.get("username")
        else "ندارد"
    )

    caption = (
        f"🧾 سفارش جدید\n\n"
        f"شماره سفارش: {order_id}\n"
        f"نام: {order.get('first_name') or 'نامشخص'}\n"
        f"آیدی کاربر: {order['user_id']}\n"
        f"نام کاربری: {username}\n"
        f"تلفن: {order.get('phone') or 'ثبت نشده'}\n\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {order['amount']}\n"
        f"کیف پول: {order['wallet']}\n"
        f"مبلغ: {money(order['total'])} تومان\n"
        "وضعیت: در انتظار بررسی"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ تأیید",
            callback_data=f"approve:{order_id}",
        ),
        InlineKeyboardButton(
            "❌ رد",
            callback_data=f"reject:{order_id}",
        ),
    ]])

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo.file_id,
            caption=caption,
            reply_markup=keyboard,
        )
    except TelegramError:
        logger.exception("ارسال رسید به مدیر ناموفق بود")
        await message.reply_text(
            "رسید ذخیره شد، اما ارسال آن به مدیر ناموفق بود. "
            "با پشتیبانی تماس بگیر.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    await message.reply_text(
        "رسید برای مدیر ارسال شد. پس از بررسی، نتیجه اعلام می‌شود.",
        reply_markup=menu(),
    )

    for key in ("order_id", "product", "amount", "total"):
        context.user_data.pop(key, None)

    return ConversationHandler.END


# =====================================================
# تأیید و رد سفارش
# =====================================================

async def admin_order_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer(
            "اجازه انجام این عملیات را نداری.",
            show_alert=True,
        )
        return

    try:
        action, order_id = query.data.split(":", 1)
    except (AttributeError, ValueError):
        await query.answer(
            "اطلاعات عملیات نامعتبر است.",
            show_alert=True,
        )
        return

    if action not in ("approve", "reject"):
        await query.answer(
            "عملیات نامعتبر است.",
            show_alert=True,
        )
        return

    async with order_locks[order_id]:
        order = orders.get(order_id)

        if not order:
            await query.answer(
                "سفارش پیدا نشد.",
                show_alert=True,
            )
            return

        if order.get("status") != "pending_admin":
            # پیام تکراری در چت مدیر ارسال نمی‌شود.
            await query.answer(
                "این سفارش قبلاً بررسی شده است.",
                show_alert=True,
            )
            return

        old_status = order["status"]

        if action == "approve":
            order["status"] = "approved"
            result = "تأیید شد"
            user_message = (
                f"✅ سفارش شماره {order_id} تأیید شد.\n"
                "برای پیگیری بیشتر از پشتیبانی استفاده کن."
            )
        else:
            order["status"] = "rejected"
            result = "رد شد"
            user_message = (
                f"❌ سفارش شماره {order_id} رد شد.\n"
                "برای پیگیری با پشتیبانی تماس بگیر."
            )

        order["updated_at"] = now()
        order["reviewed_by"] = query.from_user.id

        try:
            await save_orders()
        except OSError:
            order["status"] = old_status
            logger.exception(
                "ذخیره نتیجه سفارش %s ناموفق بود",
                order_id,
            )
            await query.answer(
                "ذخیره نتیجه ناموفق بود؛ دوباره تلاش کن.",
                show_alert=True,
            )
            return

        # حذف دکمه‌ها
        try:
            await query.edit_message_reply_markup(
                reply_markup=None
            )
        except TelegramError:
            logger.exception(
                "حذف دکمه‌های سفارش %s ناموفق بود",
                order_id,
            )

        await query.answer(
            f"سفارش {result}.",
            show_alert=True,
        )

        # نمایش نتیجه روی همان پیام مدیر
        try:
            old_caption = query.message.caption or ""
            await query.edit_message_caption(
                caption=old_caption + f"\n\n📌 نتیجه بررسی: {result}",
                reply_markup=None,
            )
        except TelegramError:
            logger.exception(
                "ویرایش پیام سفارش %s ناموفق بود",
                order_id,
            )

        # اطلاع به کاربر
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=user_message,
            )
        except TelegramError:
            logger.exception(
                "ارسال نتیجه سفارش %s به کاربر ناموفق بود",
                order_id,
            )


# =====================================================
# حساب کاربری
# =====================================================

async def account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    data = users.get(str(user.id), {})

    await update.effective_message.reply_text(
        "👤 حساب کاربری\n\n"
        f"نام: {data.get('first_name') or user.first_name}\n"
        f"آیدی: {user.id}\n"
        f"نام کاربری: @{user.username or 'ندارد'}\n"
        f"شماره تلفن: {data.get('phone') or 'ثبت نشده'}",
        reply_markup=menu(),
    )


# =====================================================
# سفارش‌های من
# =====================================================

async def my_orders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    result = [
        order
        for order in orders.values()
        if order.get("user_id") == user.id
    ]

    if not result:
        await update.effective_message.reply_text(
            "هنوز سفارشی نداری.",
            reply_markup=menu(),
        )
        return

    result.sort(
        key=lambda order: order["order_id"],
        reverse=True,
    )

    status_names = {
        "awaiting_receipt": "در انتظار رسید",
        "pending_admin": "در انتظار بررسی",
        "approved": "تأیید شده",
        "rejected": "رد شده",
    }

    lines = ["📦 سفارش‌های شما:\n"]

    for order in result[:20]:
        lines.append(
            f"سفارش: {order['order_id']}\n"
            f"محصول: {order['product']}\n"
            f"مقدار: {order['amount']}\n"
            f"مبلغ: {money(order['total'])} تومان\n"
            f"وضعیت: {status_names.get(order['status'], 'نامشخص')}\n"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=menu(),
    )


# =====================================================
# پشتیبانی
# =====================================================

async def support_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "پیامت را برای پشتیبانی بفرست. "
        "می‌توانی متن یا عکس ارسال کنی."
    )

    return SUPPORT_MESSAGE


async def support_receive(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                "📩 پیام پشتیبانی\n\n"
                f"نام: {user.full_name}\n"
                f"آیدی: {user.id}\n"
                f"نام کاربری: @{user.username or 'ندارد'}"
            ),
        )

        await context.bot.copy_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )

    except TelegramError:
        logger.exception("ارسال پیام پشتیبانی ناموفق بود")
        await message.reply_text(
            "ارسال پیام ناموفق بود. دوباره تلاش کن.",
            reply_markup=menu(),
        )
        return ConversationHandler.END

    await message.reply_text(
        "پیامت به مدیر ارسال شد.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# =====================================================
# راهنما
# =====================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "راهنمای خرید\n\n"
        "DOGS: هر عدد ۱۲ تومان، حداقل ۱۰۰۰ عدد.\n"
        "TON: هر ۰٫۱ واحد ۴۰٬۰۰۰ تومان، حداقل ۰٫۱.\n\n"
        "مراحل خرید: انتخاب محصول، واردکردن مقدار، "
        "ارسال آدرس کیف پول، پرداخت و ارسال عکس رسید.\n"
        "سپس مدیر سفارش را بررسی می‌کند.",
        reply_markup=menu(),
    )


# =====================================================
# لغو
# =====================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.effective_message.reply_text(
        "عملیات لغو شد.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


# =====================================================
# آمار مدیر
# =====================================================

async def admin_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not admin_only(update):
        await update.effective_message.reply_text(
            "اجازه دسترسی نداری."
        )
        return

    pending = sum(
        order.get("status") == "pending_admin"
        for order in orders.values()
    )

    approved = sum(
        order.get("status") == "approved"
        for order in orders.values()
    )

    rejected = sum(
        order.get("status") == "rejected"
        for order in orders.values()
    )

    await update.effective_message.reply_text(
        "📊 آمار ربات\n\n"
        f"کاربران: {len(users)}\n"
        f"سفارش‌ها: {len(orders)}\n"
        f"در انتظار بررسی: {pending}\n"
        f"تأییدشده: {approved}\n"
        f"ردشده: {rejected}"
    )


# =====================================================
# خطاهای کلی
# =====================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "خطای پیش‌بینی‌نشده",
        exc_info=context.error,
    )


# =====================================================
# اجرای ربات
# =====================================================

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        raise RuntimeError(
            "توکن ربات را در متغیر محیطی BOT_TOKEN تنظیم کن."
        )

    if ADMIN_CHAT_ID == 123456789:
        raise RuntimeError(
            "آیدی عددی مدیر را در ADMIN_CHAT_ID تنظیم کن."
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

    logger.info("ربات اجرا شد.")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
