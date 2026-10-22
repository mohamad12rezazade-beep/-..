import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= تنظیمات =================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

CARD_NUMBER = "6219861856357990"
CARD_HOLDER = "رضازاده"

REQUIRED_CHANNEL = "@BNI_MMAD"
REQUIRED_GROUP = "@BNI_MMAD1"

CHANNEL_LINK = "https://t.me/BNI_MMAD"
GROUP_LINK = "https://t.me/BNI_MMAD1"

ORDER_CHANNEL = "@BNI_MMAD"

DOGS_PRICE = 12
DOGS_MIN = 1000

TON_PRICE_PER_01 = 40000
TON_MIN = 0.1

STARS_PRICE = 4800
STARS_MIN = 1
STARS_MAX = 1000

USERS_FILE = Path("users.json")
ORDERS_FILE = Path("orders.json")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

storage_lock = asyncio.Lock()
order_locks = defaultdict(asyncio.Lock)

(
    GET_PHONE,
    AMOUNT,
    WALLET,
    RECEIPT,
    SUPPORT_MESSAGE,
) = range(5)


# ================= ذخیره‌سازی =================

def load_json(path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        logger.exception("خطا در خواندن %s", path)
        return default


def save_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    temporary.replace(path)


def load_users():
    return load_json(USERS_FILE, {})


def load_orders():
    return load_json(ORDERS_FILE, {})


async def update_user(user_id, **fields):
    async with storage_lock:
        users = load_users()
        key = str(user_id)

        if key not in users:
            users[key] = {}

        users[key].update(fields)
        save_json(USERS_FILE, users)


async def create_order(order):
    async with storage_lock:
        orders = load_orders()
        orders[order["id"]] = order
        save_json(ORDERS_FILE, orders)


async def get_order(order_id):
    async with storage_lock:
        return load_orders().get(order_id)


async def set_order_fields(order_id, **fields):
    async with storage_lock:
        orders = load_orders()

        if order_id not in orders:
            return False

        orders[order_id].update(fields)
        save_json(ORDERS_FILE, orders)

    return True


# ================= منوها =================

def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["🐶 خرید DOGS", "💎 خرید TON"],
            ["⭐ خرید Stars", "🛟 پشتیبانی"],
            ["👤 حساب کاربری"],
        ],
        resize_keyboard=True,
    )


def membership_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("عضویت در کانال", url=CHANNEL_LINK),
            InlineKeyboardButton("عضویت در گروه", url=GROUP_LINK),
        ],
        [
            InlineKeyboardButton(
                "بررسی عضویت",
                callback_data="check_membership",
            )
        ],
    ])


async def is_member(bot, user_id):
    for chat_id in (REQUIRED_CHANNEL, REQUIRED_GROUP):
        try:
            member = await bot.get_chat_member(chat_id, user_id)

            if member.status in ("left", "kicked"):
                return False

        except Exception:
            logger.exception(
                "بررسی عضویت در %s ناموفق بود",
                chat_id,
            )
            # مطابق تنظیم خواسته‌شده، خطای API مانع ادامه کار نمی‌شود.

    return True


async def ensure_membership(update, context):
    user = update.effective_user

    if await is_member(context.bot, user.id):
        return True

    if update.callback_query:
        await update.callback_query.answer()

        await update.callback_query.message.reply_text(
            "برای استفاده از ربات، ابتدا عضو کانال و گروه شو.",
            reply_markup=membership_keyboard(),
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            "برای استفاده از ربات، ابتدا عضو کانال و گروه شو.",
            reply_markup=membership_keyboard(),
        )

    return False


# ================= شروع ربات =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    existing = users.get(str(user.id), {})

    await update_user(
        user.id,
        name=user.full_name,
        username=user.username,
    )

    if not await ensure_membership(update, context):
        return ConversationHandler.END

    if not existing.get("phone"):
        await update.effective_message.reply_text(
            "سلام! برای ثبت‌نام، شماره تلفنت رو با دکمه زیر بفرست.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(
                    "📱 ارسال شماره تلفن",
                    request_contact=True,
                )]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return GET_PHONE

    await update.effective_message.reply_text(
        "سلام! به ربات خرید خوش اومدی.",
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


async def receive_phone(update, context):
    contact = update.effective_message.contact
    user = update.effective_user

    if not contact or contact.user_id != user.id:
        await update.effective_message.reply_text(
            "لطفاً شماره تلفن خودت رو با دکمه ارسال شماره بفرست."
        )
        return GET_PHONE

    await update_user(user.id, phone=contact.phone_number)

    await update.effective_message.reply_text(
        "ثبت‌نام انجام شد.",
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


async def membership_callback(update, context):
    query = update.callback_query
    await query.answer()

    if await is_member(context.bot, query.from_user.id):
        await query.message.reply_text(
            "عضویت تأیید شد. حالا می‌تونی از منو استفاده کنی.",
            reply_markup=main_menu(),
        )
    else:
        await query.message.reply_text(
            "هنوز عضویتت تأیید نشده. عضو کانال و گروه شو و دوباره امتحان کن.",
            reply_markup=membership_keyboard(),
        )


# ================= خرید =================

def product_from_text(text):
    mapping = {
        "🐶 خرید DOGS": "DOGS",
        "💎 خرید TON": "TON",
        "⭐ خرید Stars": "Stars",
    }
    return mapping.get(text)


async def begin_purchase(update, context):
    if not await ensure_membership(update, context):
        return ConversationHandler.END

    product = product_from_text(update.effective_message.text)

    if not product:
        return ConversationHandler.END

    context.user_data["product"] = product

    if product == "DOGS":
        message = (
            "مقدار DOGS رو به عدد وارد کن.\n"
            f"حداقل خرید: {DOGS_MIN}\n"
            f"قیمت هر DOGS: {DOGS_PRICE} تومان"
        )

    elif product == "TON":
        message = (
            "مقدار TON رو وارد کن؛ مثال: 0.1 یا 0.5\n"
            f"حداقل خرید: {TON_MIN}\n"
            f"هر 0.1 TON برابر {TON_PRICE_PER_01:,} تومان است."
        )

    else:
        message = (
            "تعداد Stars رو وارد کن.\n"
            f"حداقل: {STARS_MIN}\n"
            f"حداکثر: {STARS_MAX}\n"
            f"قیمت هر Star: {STARS_PRICE:,} تومان"
        )

    await update.effective_message.reply_text(
        message,
        reply_markup=ReplyKeyboardRemove(),
    )

    return AMOUNT


async def receive_amount(update, context):
    product = context.user_data.get("product")

    try:
        raw = update.effective_message.text.strip()

        if product == "DOGS":
            amount = int(raw)

            if amount < DOGS_MIN:
                raise ValueError

            price = amount * DOGS_PRICE

        elif product == "TON":
            amount = float(raw.replace(",", "."))

            if amount < TON_MIN:
                raise ValueError

            # قیمت به ازای هر 0.1 TON
            units = amount / 0.1

            # تنها مضرب‌های 0.1 پذیرفته می‌شوند.
            if abs(units - round(units)) > 1e-8:
                await update.effective_message.reply_text(
                    "مقدار TON باید مضرب 0.1 باشد؛ مثل 0.1، 0.2 یا 1.0."
                )
                return AMOUNT

            price = int(round(units)) * TON_PRICE_PER_01

        elif product == "Stars":
            amount = int(raw)

            if not STARS_MIN <= amount <= STARS_MAX:
                raise ValueError

            price = amount * STARS_PRICE

        else:
            await update.effective_message.reply_text(
                "محصول نامعتبره. از منو دوباره شروع کن.",
                reply_markup=main_menu(),
            )
            return ConversationHandler.END

    except ValueError:
        await update.effective_message.reply_text(
            "مقدار واردشده معتبر نیست. دوباره مقدار رو وارد کن."
        )
        return AMOUNT

    context.user_data["amount"] = amount
    context.user_data["price"] = price

    await update.effective_message.reply_text(
        "آدرس کیف پول مقصد رو بفرست."
    )

    return WALLET


async def receive_wallet(update, context):
    wallet = update.effective_message.text.strip()

    if len(wallet) < 5:
        await update.effective_message.reply_text(
            "آدرس کیف پول معتبر به نظر نمی‌رسه. دوباره بفرست."
        )
        return WALLET

    user = update.effective_user
    product = context.user_data["product"]
    amount = context.user_data["amount"]
    price = context.user_data["price"]

    order_id = f"{user.id}_{int(datetime.now().timestamp())}"

    order = {
        "id": order_id,
        "user_id": user.id,
        "username": user.username,
        "name": user.full_name,
        "product": product,
        "amount": amount,
        "wallet": wallet,
        "price": price,
        "status": "waiting_receipt",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    await create_order(order)
    context.user_data["order_id"] = order_id

    await update.effective_message.reply_text(
        f"🧾 سفارش: {order_id}\n"
        f"📦 محصول: {product}\n"
        f"🔢 مقدار: {amount}\n"
        f"💰 مبلغ قابل پرداخت: {price:,} تومان\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"👤 صاحب کارت: {CARD_HOLDER}\n\n"
        "پس از پرداخت، عکس رسید رو همین‌جا ارسال کن.",
        parse_mode="Markdown",
    )

    return RECEIPT


async def receive_receipt(update, context):
    photo_message = update.effective_message

    if not photo_message.photo:
        await photo_message.reply_text(
            "لطفاً عکس رسید پرداخت رو به صورت عکس ارسال کن."
        )
        return RECEIPT

    order_id = context.user_data.get("order_id")

    if not order_id:
        await photo_message.reply_text(
            "سفارشی پیدا نشد. از منو دوباره شروع کن.",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    order = await get_order(order_id)

    if not order or order["status"] != "waiting_receipt":
        await photo_message.reply_text(
            "این سفارش در انتظار رسید نیست. از منو دوباره شروع کن.",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    await set_order_fields(
        order_id,
        status="pending_admin",
        receipt_file_id=photo_message.photo[-1].file_id,
    )

    keyboard = InlineKeyboardMarkup([
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
    ])

    admin_caption = (
        "🛒 سفارش جدید برای بررسی\n\n"
        f"🆔 سفارش: {order_id}\n"
        f"👤 نام: {order['name']}\n"
        f"🆔 شناسه کاربر: {order['user_id']}\n"
        f"📦 محصول: {order['product']}\n"
        f"🔢 مقدار: {order['amount']}\n"
        f"💰 مبلغ: {order['price']:,} تومان\n"
        f"👛 کیف پول: {order['wallet']}"
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo_message.photo[-1].file_id,
            caption=admin_caption,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("ارسال رسید به مدیر ناموفق بود")
        await photo_message.reply_text(
            "ارسال رسید برای مدیر ناموفق شد. لطفاً از بخش پشتیبانی پیام بده."
        )
        return ConversationHandler.END

    await photo_message.reply_text(
        "رسید دریافت شد و برای مدیر ارسال شد. بعد از بررسی نتیجه رو بهت اطلاع می‌دیم.",
        reply_markup=main_menu(),
    )

    context.user_data.pop("order_id", None)
    context.user_data.pop("product", None)
    context.user_data.pop("amount", None)
    context.user_data.pop("price", None)

    return ConversationHandler.END


# ================= تأیید یا رد مدیر =================

async def admin_order_action(update, context):
    query = update.callback_query

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer(
            "اجازه انجام این کار رو نداری.",
            show_alert=True,
        )
        return

    action, order_id = query.data.split(":", 1)

    async with order_locks[order_id]:
        order = await get_order(order_id)

        if not order:
            await query.answer("سفارش پیدا نشد.", show_alert=True)
            return

        if order.get("status") != "pending_admin":
            await query.answer(
                "این سفارش قبلاً بررسی شده.",
                show_alert=True,
            )
            return

        if action == "approve":
            new_status = "approved"
        elif action == "reject":
            new_status = "rejected"
        else:
            await query.answer("عملیات نامعتبره.", show_alert=True)
            return

        # ابتدا وضعیت نهایی ذخیره می‌شود تا callback تکراری دوباره اقدام نکند.
        await set_order_fields(
            order_id,
            status=new_status,
            reviewed_at=datetime.now().isoformat(timespec="seconds"),
        )

        if action == "approve":
            try:
                await context.bot.send_message(
                    chat_id=ORDER_CHANNEL,
                    text=(
                        "✅ سفارش تأیید شد\n\n"
                        f"🆔 شماره سفارش: {order_id}\n"
                        f"📦 محصول: {order['product']}\n"
                        f"🔢 مقدار: {order['amount']}\n"
                        f"💰 مبلغ: {order['price']:,} تومان\n"
                        f"👛 کیف پول مقصد:\n{order['wallet']}"
                    ),
                )
            except Exception:
                logger.exception("انتشار سفارش در کانال ناموفق بود")

                # سفارش تأییدشده می‌ماند؛ در صورت خطای ارسال، مدیر مطلع می‌شود.
                await query.answer(
                    "سفارش تأیید شد، اما ارسال به کانال ناموفق بود. دسترسی ربات را بررسی کن.",
                    show_alert=True,
                )

                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"⚠️ انتشار سفارش {order_id} در کانال ناموفق بود.",
                    )
                except Exception:
                    logger.exception("اطلاع‌رسانی خطا به مدیر ناموفق بود")

                try:
                    await query.edit_message_caption(
                        caption=(
                            admin_caption_from_order(order)
                            + "\n\n⚠️ تأیید شد؛ ارسال به کانال ناموفق بود."
                        ),
                        reply_markup=None,
                    )
                except Exception:
                    logger.exception("ویرایش پیام مدیر ناموفق بود")

                return

            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=f"✅ سفارش {order_id} تأیید شد و در کانال منتشر شد.",
                )
            except Exception:
                logger.exception("ارسال پیام تأیید به کاربر ناموفق بود")

            result_text = "✅ سفارش تأیید شد و در کانال منتشر شد."

        else:
            try:
                await context.bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"❌ سفارش {order_id} توسط مدیر رد شد.\n"
                        "اگر فکر می‌کنی اشتباهی رخ داده، از بخش پشتیبانی پیام بده."
                    ),
                )
            except Exception:
                logger.exception("ارسال پیام رد به کاربر ناموفق بود")

            result_text = "❌ سفارش رد شد و در کانال منتشر نشد."

        await query.answer(result_text, show_alert=True)

        try:
            await query.edit_message_caption(
                caption=admin_caption_from_order(order) + "\n\n" + result_text,
                reply_markup=None,
            )
        except Exception:
            logger.exception("ویرایش پیام سفارش مدیر ناموفق بود")


def admin_caption_from_order(order):
    return (
        "🛒 جزئیات سفارش\n\n"
        f"🆔 سفارش: {order['id']}\n"
        f"👤 نام: {order['name']}\n"
        f"🆔 شناسه کاربر: {order['user_id']}\n"
        f"📦 محصول: {order['product']}\n"
        f"🔢 مقدار: {order['amount']}\n"
        f"💰 مبلغ: {order['price']:,} تومان\n"
        f"👛 کیف پول: {order['wallet']}"
    )


# ================= پشتیبانی =================

async def support_start(update, context):
    if not await ensure_membership(update, context):
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "پیامت رو برای پشتیبانی بفرست."
    )

    return SUPPORT_MESSAGE


async def support_receive(update, context):
    user = update.effective_user
    text = update.effective_message.text

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                "🛟 پیام پشتیبانی\n\n"
                f"👤 کاربر: {user.full_name}\n"
                f"🆔 شناسه: {user.id}\n"
                f"متن پیام:\n{text}"
            ),
        )

        await update.effective_message.reply_text(
            "پیامت برای پشتیبانی ارسال شد.",
            reply_markup=main_menu(),
        )

    except Exception:
        logger.exception("ارسال پیام پشتیبانی ناموفق بود")
        await update.effective_message.reply_text(
            "ارسال پیام ناموفق بود. کمی بعد دوباره امتحان کن.",
            reply_markup=main_menu(),
        )

    return ConversationHandler.END


async def account(update, context):
    user = update.effective_user
    users = load_users()
    data = users.get(str(user.id), {})

    await update.effective_message.reply_text(
        f"👤 حساب کاربری\n"
        f"نام: {user.full_name}\n"
        f"شناسه: {user.id}\n"
        f"شماره تلفن: {data.get('phone', 'ثبت نشده')}",
        reply_markup=main_menu(),
    )


async def cancel(update, context):
    context.user_data.clear()

    await update.effective_message.reply_text(
        "عملیات لغو شد.",
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


async def error_handler(update, context):
    logger.error(
        "خطای مدیریت‌نشده: %s",
        context.error,
        exc_info=context.error,
    )


# ================= اجرای ربات =================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "متغیر محیطی BOT_TOKEN تنظیم نشده است."
        )

    if not ADMIN_CHAT_ID:
        raise RuntimeError(
            "متغیر محیطی ADMIN_CHAT_ID تنظیم نشده است."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex(r"^(🐶 خرید DOGS|💎 خرید TON|⭐ خرید Stars)$"),
                begin_purchase,
            ),
            MessageHandler(
                filters.Regex(r"^🛟 پشتیبانی$"),
                support_start,
            ),
        ],
        states={
            GET_PHONE: [
                MessageHandler(filters.CONTACT, receive_phone),
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount),
            ],
            WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet),
            ],
            RECEIPT: [
                MessageHandler(filters.PHOTO, receive_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_receipt),
            ],
            SUPPORT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, support_receive),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )

    app.add_handler(conversation)
    app.add_handler(
        CallbackQueryHandler(
            membership_callback,
            pattern=r"^check_membership$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            admin_order_action,
            pattern=r"^(approve|reject):",
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^👤 حساب کاربری$"),
            account,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("ربات در حال اجراست.")
    app.run_polling()


if __name__ == "__main__":
    main()
