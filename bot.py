import os
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# تنظیمات
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_ID = 8935601841

CARD_NUMBER = "6219861856357990"
CARD_OWNER = "رضازاده"

CHANNEL_USERNAME = "@BNI_MMAD"
GROUP_USERNAME = "@BNI_MMAD1"

CHANNEL_LINK = "https://t.me/BNI_MMAD"
GROUP_LINK = "https://t.me/BNI_MMAD1"

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"
ORDERS_FILE = BASE_DIR / "orders.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# =========================
# فایل‌های ذخیره‌سازی
# =========================


def load_json(path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
    except (json.JSONDecodeError, OSError):
        logger.exception("خطا در خواندن فایل %s", path.name)

    return default


def save_json(path, data):
    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    temp_path.replace(path)


users = load_json(USERS_FILE, {})
orders = load_json(ORDERS_FILE, {})

# مراحل جاری هر کاربر در حافظه
user_states = {}

# =========================
# ابزارهای کمکی
# =========================


def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🛒 خرید DOGS", "💎 خرید TON"],
            ["⭐ خرید Stars", "📦 سفارش‌های من"],
            ["👤 حساب کاربری", "📞 پشتیبانی"],
            ["📚 راهنما"],
        ],
        resize_keyboard=True,
    )


def money(amount):
    return f"{amount:,} تومان"


def new_order_id():
    number = 1

    if orders:
        number = max(
            int(order_id)
            for order_id in orders
        ) + 1

    return str(number)


def user_record(user):
    uid = str(user.id)

    if uid not in users:
        users[uid] = {
            "id": user.id,
            "name": user.full_name,
            "username": user.username,
            "phone": None,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        save_json(USERS_FILE, users)

    return users[uid]


async def check_membership(bot, user_id):
    """
    اگر بات دسترسی بررسی عضویت نداشته باشد،
    خطا را ثبت می‌کند و اجازه ادامه می‌دهد.
    """
    for chat_id in (CHANNEL_USERNAME, GROUP_USERNAME):
        try:
            member = await bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )

            if member.status in ("left", "kicked"):
                return False

        except Exception:
            logger.exception(
                "بررسی عضویت در %s ناموفق بود",
                chat_id,
            )

    return True


async def show_membership(update):
    keyboard = InlineKeyboardMarkup(
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
                    "بررسی عضویت",
                    callback_data="check_membership",
                )
            ],
        ]
    )

    await update.effective_message.reply_text(
        "برای ادامه، لطفاً در کانال و گروه عضو شو.",
        reply_markup=keyboard,
    )


async def create_order(user_id, product, quantity, price, destination=None):
    order_id = new_order_id()

    orders[order_id] = {
        "id": order_id,
        "user_id": user_id,
        "product": product,
        "quantity": quantity,
        "price": price,
        "destination": destination,
        "status": "awaiting_receipt",
        "receipt_file_id": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    save_json(ORDERS_FILE, orders)

    return order_id


# =========================
# شروع و راهنما
# =========================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user or not update.effective_message:
        return

    user_record(user)

    user_states.pop(user.id, None)

    await update.effective_message.reply_text(
        f"سلام {user.first_name} عزیز! 👋\n\n"
        "به ربات خرید DOGS، TON و Telegram Stars خوش اومدی.\n\n"
        "از منوی پایین یک گزینه انتخاب کن.",
        reply_markup=main_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 راهنمای ربات\n\n"
        "۱. محصول موردنظرت رو انتخاب کن.\n"
        "۲. مقدار خرید رو وارد کن.\n"
        "۳. اطلاعات موردنیاز رو بفرست.\n"
        "۴. مبلغ و شماره کارت رو بررسی کن.\n"
        "۵. تصویر رسید پرداخت رو ارسال کن.\n"
        "۶. سفارش برای بررسی به مدیر ارسال می‌شه.\n\n"
        "انتشار سفارش فقط پس از تأیید مدیر انجام می‌شه.",
        reply_markup=main_keyboard(),
    )


# =========================
# خرید محصولات
# =========================


async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.effective_message.text

    user_record(user)

    products = {
        "🛒 خرید DOGS": "DOGS",
        "💎 خرید TON": "TON",
        "⭐ خرید Stars": "Stars",
    }

    product = products.get(text)

    if not product:
        return

    user_states[user.id] = {
        "step": "quantity",
        "product": product,
    }

    if product == "DOGS":
        description = (
            "🛒 خرید DOGS\n\n"
            "قیمت هر DOGS: ۱۲ تومان\n"
            "حداقل خرید: ۱۰۰۰ عدد\n\n"
            "تعداد DOGS موردنظر رو وارد کن:"
        )

    elif product == "TON":
        description = (
            "💎 خرید TON\n\n"
            "قیمت هر ۰٫۱ TON: ۴۰٬۰۰۰ تومان\n"
            "حداقل خرید: ۰٫۱ TON\n"
            "مقدار باید مضربی از ۰٫۱ باشه.\n\n"
            "مقدار TON موردنظر رو وارد کن؛ مثلاً ۰٫۱ یا ۰٫۵:"
        )

    else:
        description = (
            "⭐ خرید Telegram Stars\n\n"
            "قیمت هر Star: ۴٬۸۰۰ تومان\n"
            "حداقل خرید: ۱ عدد\n"
            "حداکثر خرید: ۱۰۰۰ عدد\n\n"
            "تعداد Stars موردنظر رو وارد کن:"
        )

    await update.effective_message.reply_text(description)


def parse_number(text):
    text = text.strip()

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬",
        "01234567890123456789.,",
    )

    text = text.translate(translation).replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


async def receive_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = user_states.get(user.id)

    if not state or state.get("step") != "quantity":
        return

    amount = parse_number(update.effective_message.text)

    if amount is None or amount <= 0:
        await update.effective_message.reply_text(
            "❌ مقدار معتبر نیست. لطفاً یک عدد وارد کن."
        )
        return

    product = state["product"]

    if product == "DOGS":
        if not amount.is_integer() or amount < 1000:
            await update.effective_message.reply_text(
                "حداقل خرید DOGS برابر ۱۰۰۰ عدده."
            )
            return

        quantity = int(amount)
        price = quantity * 12

    elif product == "TON":
        if amount < 0.1 or abs(amount * 10 - round(amount * 10)) > 1e-7:
            await update.effective_message.reply_text(
                "مقدار TON باید حداقل ۰٫۱ و مضربی از ۰٫۱ باشه."
            )
            return

        quantity = round(amount, 1)
        price = int(round(quantity * 400000))

    else:
        if not amount.is_integer() or not 1 <= amount <= 1000:
            await update.effective_message.reply_text(
                "تعداد Stars باید بین ۱ تا ۱۰۰۰ باشه."
            )
            return

        quantity = int(amount)
        price = quantity * 4800

    state["quantity"] = quantity
    state["price"] = price

    if product in ("DOGS", "TON"):
        state["step"] = "destination"

        destination_label = (
            "آدرس کیف پول DOGS"
            if product == "DOGS"
            else "آدرس کیف پول TON"
        )

        await update.effective_message.reply_text(
            f"مبلغ سفارش: {money(price)}\n\n"
            f"لطفاً {destination_label} رو بفرست."
        )

    else:
        state["step"] = "destination"

        await update.effective_message.reply_text(
            f"مبلغ سفارش: {money(price)}\n\n"
            "لطفاً لینک پست تلگرام مربوط به Stars رو بفرست.\n"
            "نمونه: https://t.me/channelname/123"
        )


# =========================
# دریافت آدرس یا لینک
# =========================


async def receive_destination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    state = user_states.get(user.id)

    if not state or state.get("step") != "destination":
        return

    destination = update.effective_message.text.strip()
    product = state["product"]

    if not destination:
        await update.effective_message.reply_text(
            "لطفاً اطلاعات موردنیاز رو بفرست."
        )
        return

    if product == "Stars":
        if not (
            destination.startswith("https://t.me/")
            or destination.startswith("http://t.me/")
        ):
            await update.effective_message.reply_text(
                "لینک معتبر تلگرام بفرست؛ مثلاً:\n"
                "https://t.me/channelname/123"
            )
            return

    state["destination"] = destination
    state["step"] = "receipt"

    await update.effective_message.reply_text(
        "💳 اطلاعات پرداخت\n\n"
        f"شماره کارت:\n{CARD_NUMBER}\n\n"
        f"صاحب کارت: {CARD_OWNER}\n"
        f"مبلغ قابل پرداخت: {money(state['price'])}\n\n"
        "بعد از پرداخت، تصویر رسید رو به‌صورت عکس ارسال کن."
    )


# =========================
# دریافت رسید
# =========================


async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    state = user_states.get(user.id)

    if not state or state.get("step") != "receipt":
        return

    if not update.effective_message.photo:
        await update.effective_message.reply_text(
            "لطفاً تصویر رسید رو با گزینه ارسال عکس بفرست."
        )
        return

    receipt_file_id = update.effective_message.photo[-1].file_id

    order_id = await create_order(
        user_id=user.id,
        product=state["product"],
        quantity=state["quantity"],
        price=state["price"],
        destination=state.get("destination"),
    )

    orders[order_id]["receipt_file_id"] = receipt_file_id
    save_json(ORDERS_FILE, orders)

    order = orders[order_id]

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

    caption = (
        f"📥 سفارش جدید شماره {order_id}\n\n"
        f"کاربر: {user.full_name}\n"
        f"شناسه کاربر: {user.id}\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {order['quantity']}\n"
        f"مبلغ: {money(order['price'])}\n"
        f"اطلاعات مقصد: {order['destination']}\n"
        "وضعیت: در انتظار بررسی"
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=receipt_file_id,
            caption=caption,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("ارسال سفارش به مدیر ناموفق بود")

        await update.effective_message.reply_text(
            "سفارش ثبت شد، اما ارسال آن برای مدیر ناموفق بود. "
            "لطفاً بعداً با پشتیبانی تماس بگیر."
        )
        user_states.pop(user.id, None)
        return

    await update.effective_message.reply_text(
        f"✅ سفارش شماره {order_id} ثبت شد.\n"
        "سفارش برای بررسی به مدیر ارسال شد.\n"
        "بعد از تأیید، نتیجه اعلام می‌شه.",
        reply_markup=main_keyboard(),
    )

    user_states.pop(user.id, None)


# =========================
# تأیید یا رد سفارش
# =========================


async def handle_admin_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer(
            "فقط مدیر می‌تونه این کار رو انجام بده.",
            show_alert=True,
        )
        return

    await query.answer()

    action, order_id = query.data.split(":", 1)

    if order_id not in orders:
        await query.edit_message_caption(
            caption="❌ سفارش پیدا نشد."
        )
        return

    order = orders[order_id]

    if order["status"] != "awaiting_receipt":
        await query.answer(
            "این سفارش قبلاً بررسی شده.",
            show_alert=True,
        )
        return

    if action == "approve":
        order["status"] = "approved"
    else:
        order["status"] = "rejected"

    order["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(ORDERS_FILE, orders)

    user_id = order["user_id"]

    if action == "approve":
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ سفارش شماره {order_id} تأیید شد.\n"
                    "سفارش شما توسط مدیر تأیید شد."
                ),
            )
        except Exception:
            logger.exception("اطلاع‌رسانی به کاربر ناموفق بود")

        # فقط سفارش تأییدشده در کانال منتشر می‌شود.
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=(
                    f"✅ سفارش تأییدشده شماره {order_id}\n\n"
                    f"محصول: {order['product']}\n"
                    f"مقدار: {order['quantity']}\n"
                    "وضعیت: تأییدشده"
                ),
            )
        except Exception:
            logger.exception("انتشار سفارش در کانال ناموفق بود")

        result = f"✅ سفارش {order_id} تأیید شد."

    else:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"❌ سفارش شماره {order_id} رد شد.\n"
                    "برای پیگیری با پشتیبانی تماس بگیر."
                ),
            )
        except Exception:
            logger.exception("اطلاع‌رسانی رد سفارش ناموفق بود")

        result = f"❌ سفارش {order_id} رد شد و در کانال منتشر نمی‌شود."

    try:
        await query.edit_message_caption(caption=result)
    except Exception:
        logger.exception("ویرایش پیام مدیر ناموفق بود")


# =========================
# منوی کاربر
# =========================


async def my_orders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    my_items = [
        order
        for order in orders.values()
        if order["user_id"] == user_id
    ]

    if not my_items:
        await update.effective_message.reply_text(
            "هنوز سفارشی ثبت نکردی."
        )
        return

    lines = ["📦 سفارش‌های شما:\n"]

    for order in sorted(
        my_items,
        key=lambda item: int(item["id"]),
        reverse=True,
    )[:20]:
        status_map = {
            "awaiting_receipt": "در انتظار بررسی",
            "approved": "تأییدشده",
            "rejected": "ردشده",
        }

        lines.append(
            f"شماره: {order['id']}\n"
            f"محصول: {order['product']}\n"
            f"مقدار: {order['quantity']}\n"
            f"مبلغ: {money(order['price'])}\n"
            f"وضعیت: {status_map.get(order['status'], order['status'])}\n"
        )

    await update.effective_message.reply_text("\n".join(lines))


async def account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    record = user_record(user)

    phone = record.get("phone") or "ثبت نشده"

    keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "📱 ارسال شماره تلفن",
                    request_contact=True,
                )
            ],
            ["🔙 منوی اصلی"],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await update.effective_message.reply_text(
        f"👤 حساب کاربری\n\n"
        f"نام: {user.full_name}\n"
        f"شناسه: {user.id}\n"
        f"نام کاربری: @{user.username or 'ندارد'}\n"
        f"شماره تلفن: {phone}",
        reply_markup=keyboard,
    )


async def receive_contact(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    contact = update.effective_message.contact

    if contact.user_id != user.id:
        await update.effective_message.reply_text(
            "لطفاً شماره تلفن خودت رو با دکمه ارسال شماره بفرست."
        )
        return

    record = user_record(user)
    record["phone"] = contact.phone_number
    save_json(USERS_FILE, users)

    await update.effective_message.reply_text(
        "✅ شماره تلفنت ثبت شد.",
        reply_markup=main_keyboard(),
    )


async def support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "📞 برای پشتیبانی، شناسه تلگرام مدیر:\n"
        f"{ADMIN_ID}\n\n"
        "در پیام خود شماره سفارش رو هم بنویس."
    )


async def menu_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = update.effective_message.text
    user = update.effective_user

    if text in ("🛒 خرید DOGS", "💎 خرید TON", "⭐ خرید Stars"):
        await choose_product(update, context)
        return

    if text == "📦 سفارش‌های من":
        await my_orders(update, context)
        return

    if text == "👤 حساب کاربری":
        await account(update, context)
        return

    if text == "📞 پشتیبانی":
        await support(update, context)
        return

    if text == "📚 راهنما":
        await help_command(update, context)
        return

    if text == "🔙 منوی اصلی":
        user_states.pop(user.id, None)

        await update.effective_message.reply_text(
            "به منوی اصلی برگشتی.",
            reply_markup=main_keyboard(),
        )
        return

    state = user_states.get(user.id, {})
    step = state.get("step")

    if step == "quantity":
        await receive_quantity(update, context)
    elif step == "destination":
        await receive_destination(update, context)
    elif step == "receipt":
        await update.effective_message.reply_text(
            "لطفاً تصویر رسید پرداخت رو به‌صورت عکس بفرست."
        )
    else:
        await update.effective_message.reply_text(
            "از منوی پایین یک گزینه انتخاب کن.",
            reply_markup=main_keyboard(),
        )


# =========================
# دکمه‌های عضویت
# =========================


async def membership_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    allowed = await check_membership(
        context.bot,
        query.from_user.id,
    )

    if allowed:
        await query.message.reply_text(
            "می‌تونی از منوی اصلی استفاده کنی.",
            reply_markup=main_keyboard(),
        )
    else:
        await query.message.reply_text(
            "هنوز عضویتت در کانال یا گروه تأیید نشده."
        )


# =========================
# مدیریت خطاها
# =========================


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "خطای پردازش به‌روزرسانی",
        exc_info=context.error,
    )


# =========================
# اجرای ربات
# =========================


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است. "
            "توکن را در GitHub Secrets با نام BOT_TOKEN ذخیره کن."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    # دستورات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # دکمه‌های تأیید و رد مدیر
    app.add_handler(
        CallbackQueryHandler(
            handle_admin_action,
            pattern=r"^(approve|reject):\d+$",
        )
    )

    # بررسی عضویت
    app.add_handler(
        CallbackQueryHandler(
            membership_callback,
            pattern=r"^check_membership$",
        )
    )

    # شماره تلفن
    app.add_handler(
        MessageHandler(
            filters.CONTACT,
            receive_contact,
        )
    )

    # رسید عکس
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_receipt,
        )
    )

    # پیام‌های متنی
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_router,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("ربات آماده دریافت پیام است.")

    # برای شروع تازه، آپدیت‌های قدیمی کنار گذاشته می‌شوند.
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
