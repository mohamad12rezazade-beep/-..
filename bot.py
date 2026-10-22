import os
import json
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================================================
# تنظیمات
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_ID = 8935601841

CHANNEL_ID = "@BNI_MMAD"
GROUP_ID = "@BNI_MMAD1"

CHANNEL_LINK = "https://t.me/BNI_MMAD"
GROUP_LINK = "https://t.me/BNI_MMAD1"

CARD_NUMBER = "6219861856357990"
CARD_OWNER = "رضازاده"

DOGS_PRICE = 12
TON_PRICE_PER_01 = 40000
STARS_PRICE = 4800

BASE_DIR = Path(__file__).resolve().parent

USERS_FILE = BASE_DIR / "users.json"
ORDERS_FILE = BASE_DIR / "orders.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# ==================================================
# ذخیره‌سازی
# ==================================================


def load_json(path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
    except (OSError, json.JSONDecodeError):
        logger.exception("خطا در خواندن %s", path.name)

    return default


def save_json(path, data):
    temporary = path.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temporary.replace(path)


users = load_json(USERS_FILE, {})
orders = load_json(ORDERS_FILE, {})

# مرحله فعلی هر کاربر
user_states = {}

# قفل ساده برای جلوگیری از ایجاد شناسه تکراری در همین اجرا
order_counter_lock = __import__("threading").Lock()


def get_user_record(user):
    uid = str(user.id)

    if uid not in users:
        users[uid] = {
            "id": user.id,
            "name": user.full_name,
            "username": user.username,
            "phone": None,
            "created_at": datetime.now().isoformat(),
        }
    else:
        users[uid]["name"] = user.full_name
        users[uid]["username"] = user.username

    save_json(USERS_FILE, users)

    return users[uid]


def next_order_id():
    with order_counter_lock:
        existing_ids = []

        for key in orders:
            try:
                existing_ids.append(int(key))
            except ValueError:
                pass

        return str(max(existing_ids, default=0) + 1)


def money(value):
    return f"{int(value):,} تومان"


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


def membership_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url=CHANNEL_LINK,
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 عضویت در گروه",
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


# ==================================================
# بررسی اجباری عضویت
# ==================================================


async def is_member(bot, user_id):
    for chat_id in (CHANNEL_ID, GROUP_ID):
        try:
            member = await bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )

            if member.status in ("left", "kicked"):
                return False

            if member.status == "restricted" and not getattr(
                member, "is_member", False
            ):
                return False

        except TelegramError:
            logger.exception(
                "بررسی عضویت در %s ناموفق بود",
                chat_id,
            )
            return None

    return True


async def show_membership_required(message):
    await message.reply_text(
        "سلام! 👋\n\n"
        "برای استفاده از ربات، باید ابتدا عضو کانال و گروه بشی.\n\n"
        "۱. در کانال عضو شو.\n"
        "۲. در گروه عضو شو.\n"
        "۳. روی «بررسی عضویت» بزن.\n\n"
        "تا قبل از تأیید عضویت، منوی خرید فعال نمی‌شه.",
        reply_markup=membership_keyboard(),
    )


async def ensure_member(update, context):
    user = update.effective_user

    if not user:
        return False

    result = await is_member(context.bot, user.id)

    if result is True:
        return True

    if result is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ فعلاً امکان بررسی عضویت وجود نداره.\n"
                "لطفاً کمی بعد دوباره تلاش کن."
            )
        return False

    if update.effective_message:
        await show_membership_required(update.effective_message)

    return False


# ==================================================
# شروع و راهنما
# ==================================================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    get_user_record(user)
    user_states.pop(user.id, None)

    if not await ensure_member(update, context):
        return

    await message.reply_text(
        f"سلام {user.first_name} عزیز! 🎉\n\n"
        "به ربات خرید DOGS، TON و Telegram Stars خوش اومدی.\n"
        "از منوی پایین گزینه موردنظرت رو انتخاب کن.",
        reply_markup=main_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_member(update, context):
        return

    await update.effective_message.reply_text(
        "📚 راهنمای خرید\n\n"
        "۱. محصول رو انتخاب کن.\n"
        "۲. مقدار موردنظر رو وارد کن.\n"
        "۳. آدرس کیف پول یا لینک پست رو بفرست.\n"
        "۴. مبلغ رو به کارت اعلام‌شده پرداخت کن.\n"
        "۵. عکس رسید رو ارسال کن.\n"
        "۶. منتظر بررسی مدیر بمون.\n\n"
        "سفارش فقط پس از تأیید مدیر منتشر می‌شه.",
        reply_markup=main_keyboard(),
    )


# ==================================================
# دکمه بررسی عضویت
# ==================================================


async def membership_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    result = await is_member(
        context.bot,
        query.from_user.id,
    )

    if result is True:
        get_user_record(query.from_user)

        await query.message.reply_text(
            "✅ عضویتت در کانال و گروه تأیید شد!\n"
            "حالا می‌تونی از منوی اصلی استفاده کنی.",
            reply_markup=main_keyboard(),
        )

    elif result is False:
        await query.message.reply_text(
            "❌ هنوز عضو هر دو بخش نیستی.\n"
            "عضویتت رو کامل کن و دوباره بررسی کن.",
            reply_markup=membership_keyboard(),
        )

    else:
        await query.message.reply_text(
            "⚠️ بررسی عضویت ناموفق بود.\n"
            "مدیر ربات باید دسترسی ربات به کانال و گروه رو بررسی کنه."
        )


# ==================================================
# انتخاب محصول
# ==================================================


async def choose_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await ensure_member(update, context):
        return

    user = update.effective_user
    text = update.effective_message.text

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
            "قیمت هر عدد: ۱۲ تومان\n"
            "حداقل خرید: ۱۰۰۰ عدد\n\n"
            "تعداد DOGS موردنظرت رو وارد کن:"
        )

    elif product == "TON":
        description = (
            "💎 خرید TON\n\n"
            "هر ۰٫۱ TON برابر ۴۰٬۰۰۰ تومان\n"
            "حداقل خرید: ۰٫۱ TON\n"
            "مقدار باید مضربی از ۰٫۱ باشه.\n\n"
            "مثال: ۰٫۱ یا ۰٫۵ یا ۱\n\n"
            "مقدار TON رو وارد کن:"
        )

    else:
        description = (
            "⭐ خرید Telegram Stars\n\n"
            "قیمت هر Star: ۴٬۸۰۰ تومان\n"
            "حداقل: ۱ عدد\n"
            "حداکثر: ۱۰۰۰ عدد\n\n"
            "تعداد Stars رو وارد کن:"
        )

    await update.effective_message.reply_text(description)


# ==================================================
# خواندن عدد فارسی یا انگلیسی
# ==================================================


def parse_number(text):
    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬",
        "01234567890123456789.,",
    )

    text = text.strip().translate(translation)
    text = text.replace(",", ".")

    try:
        number = Decimal(text)

        if not number.is_finite():
            return None

        return number

    except InvalidOperation:
        return None


# ==================================================
# دریافت تعداد
# ==================================================


async def receive_quantity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message
    state = user_states.get(user.id)

    if not state or state.get("step") != "quantity":
        return False

    amount = parse_number(message.text)

    if amount is None or amount <= 0:
        await message.reply_text(
            "❌ عدد واردشده معتبر نیست. دوباره تلاش کن."
        )
        return True

    product = state["product"]

    if product == "DOGS":
        if amount < 1000 or amount != amount.to_integral_value():
            await message.reply_text(
                "حداقل خرید DOGS برابر ۱۰۰۰ عدد است."
            )
            return True

        quantity = int(amount)
        price = quantity * DOGS_PRICE

    elif product == "TON":
        if amount < Decimal("0.1"):
            await message.reply_text(
                "حداقل خرید TON برابر ۰٫۱ است."
            )
            return True

        if amount * 10 != (amount * 10).to_integral_value():
            await message.reply_text(
                "مقدار TON باید مضربی از ۰٫۱ باشه."
            )
            return True

        quantity = float(amount)
        price = int(amount * 10) * TON_PRICE_PER_01

    else:
        if (
            amount < 1
            or amount > 1000
            or amount != amount.to_integral_value()
        ):
            await message.reply_text(
                "تعداد Stars باید عدد صحیح بین ۱ تا ۱۰۰۰ باشه."
            )
            return True

        quantity = int(amount)
        price = quantity * STARS_PRICE

    state["quantity"] = quantity
    state["price"] = price
    state["step"] = "destination"

    if product == "DOGS":
        await message.reply_text(
            f"مقدار: {quantity}\n"
            f"مبلغ: {money(price)}\n\n"
            "آدرس کیف پول DOGS رو ارسال کن:"
        )

    elif product == "TON":
        await message.reply_text(
            f"مقدار: {quantity} TON\n"
            f"مبلغ: {money(price)}\n\n"
            "آدرس کیف پول TON رو ارسال کن:"
        )

    else:
        await message.reply_text(
            f"تعداد: {quantity} Stars\n"
            f"مبلغ: {money(price)}\n\n"
            "لینک پست تلگرام رو بفرست.\n"
            "مثال: https://t.me/channelname/123"
        )

    return True


# ==================================================
# دریافت آدرس یا لینک پست
# ==================================================


async def receive_destination(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message
    state = user_states.get(user.id)

    if not state or state.get("step") != "destination":
        return False

    destination = message.text.strip()
    product = state["product"]

    if product == "Stars":
        if not (
            destination.startswith("https://t.me/")
            or destination.startswith("http://t.me/")
        ):
            await message.reply_text(
                "❌ لینک معتبر تلگرام بفرست.\n"
                "مثال: https://t.me/channelname/123"
            )
            return True

    if len(destination) < 5:
        await message.reply_text(
            "اطلاعات واردشده کوتاهه. دوباره بررسی کن."
        )
        return True

    state["destination"] = destination
    state["step"] = "receipt"

    await message.reply_text(
        "💳 اطلاعات پرداخت\n\n"
        f"شماره کارت:\n{CARD_NUMBER}\n\n"
        f"صاحب کارت: {CARD_OWNER}\n"
        f"مبلغ قابل پرداخت: {money(state['price'])}\n\n"
        "پس از پرداخت، تصویر رسید رو به‌صورت عکس ارسال کن.\n"
        "سفارش تا زمان بررسی مدیر در انتظار می‌مونه."
    )

    return True


# ==================================================
# دریافت رسید و ثبت سفارش
# ==================================================


async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message
    state = user_states.get(user.id)

    if not state or state.get("step") != "receipt":
        return False

    if not message.photo:
        await message.reply_text(
            "لطفاً رسید پرداخت رو به‌صورت عکس ارسال کن."
        )
        return True

    order_id = next_order_id()

    order = {
        "id": order_id,
        "user_id": user.id,
        "user_name": user.full_name,
        "product": state["product"],
        "quantity": state["quantity"],
        "price": state["price"],
        "destination": state["destination"],
        "receipt_file_id": message.photo[-1].file_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    orders[order_id] = order
    save_json(ORDERS_FILE, orders)

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
        f"نام کاربر: {user.full_name}\n"
        f"شناسه: {user.id}\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {order['quantity']}\n"
        f"مبلغ: {money(order['price'])}\n"
        f"مقصد: {order['destination']}\n"
        "وضعیت: در انتظار بررسی"
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=order["receipt_file_id"],
            caption=caption,
            reply_markup=keyboard,
        )

    except TelegramError:
        logger.exception("ارسال سفارش برای مدیر ناموفق بود")

        await message.reply_text(
            "سفارش ثبت شد، اما ارسال برای مدیر ناموفق بود.\n"
            "مدیر باید ربات رو در تلگرام باز کنه و /start بزنه."
        )

        user_states.pop(user.id, None)
        return True

    await message.reply_text(
        f"✅ سفارش شماره {order_id} ثبت شد.\n"
        "رسید برای مدیر ارسال شد.\n"
        "پس از بررسی، نتیجه بهت اطلاع داده می‌شه.",
        reply_markup=main_keyboard(),
    )

    user_states.pop(user.id, None)

    return True


# ==================================================
# تأیید یا رد سفارش توسط مدیر
# ==================================================


async def admin_order_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer(
            "این دکمه فقط برای مدیر فعاله.",
            show_alert=True,
        )
        return

    await query.answer()

    action, order_id = query.data.split(":", 1)

    order = orders.get(order_id)

    if not order:
        await query.answer(
            "سفارش پیدا نشد.",
            show_alert=True,
        )
        return

    if order["status"] != "pending":
        await query.answer(
            "این سفارش قبلاً بررسی شده.",
            show_alert=True,
        )
        return

    if action == "approve":
        order["status"] = "approved"
    else:
        order["status"] = "rejected"

    order["reviewed_at"] = datetime.now().isoformat()
    save_json(ORDERS_FILE, orders)

    user_id = order["user_id"]

    if action == "approve":
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ سفارش شماره {order_id} تأیید شد.\n\n"
                    f"محصول: {order['product']}\n"
                    f"مقدار: {order['quantity']}\n"
                    "سفارش شما توسط مدیر تأیید شد."
                ),
            )
        except TelegramError:
            logger.exception("ارسال پیام تأیید به کاربر ناموفق بود")

        # فقط سفارش تأییدشده منتشر می‌شود.
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=(
                    f"✅ سفارش تأییدشده شماره {order_id}\n\n"
                    f"محصول: {order['product']}\n"
                    f"مقدار: {order['quantity']}\n"
                    "وضعیت: تأییدشده"
                ),
            )
        except TelegramError:
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
        except TelegramError:
            logger.exception("اطلاع‌رسانی رد سفارش ناموفق بود")

        result = (
            f"❌ سفارش {order_id} رد شد.\n"
            "این سفارش در کانال منتشر نمی‌شود."
        )

    try:
        await query.edit_message_caption(
            caption=result,
            reply_markup=None,
        )
    except TelegramError:
        logger.exception("ویرایش پیام سفارش ناموفق بود")


# ==================================================
# سفارش‌های کاربر
# ==================================================


async def my_orders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await ensure_member(update, context):
        return

    user_id = update.effective_user.id

    items = [
        order
        for order in orders.values()
        if order["user_id"] == user_id
    ]

    if not items:
        await update.effective_message.reply_text(
            "📦 هنوز سفارشی ثبت نکردی."
        )
        return

    status_names = {
        "pending": "در انتظار بررسی",
        "approved": "تأییدشده",
        "rejected": "ردشده",
    }

    lines = ["📦 سفارش‌های شما:\n"]

    for order in sorted(
        items,
        key=lambda item: int(item["id"]),
        reverse=True,
    )[:20]:
        lines.append(
            f"شماره سفارش: {order['id']}\n"
            f"محصول: {order['product']}\n"
            f"مقدار: {order['quantity']}\n"
            f"مبلغ: {money(order['price'])}\n"
            f"وضعیت: {status_names.get(order['status'], 'نامشخص')}\n"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=main_keyboard(),
    )


# ==================================================
# حساب کاربری و شماره تلفن
# ==================================================


async def account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await ensure_member(update, context):
        return

    user = update.effective_user
    record = get_user_record(user)

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

    if not await ensure_member(update, context):
        return

    if contact.user_id != user.id:
        await update.effective_message.reply_text(
            "لطفاً شماره خودت رو با دکمه ارسال شماره بفرست."
        )
        return

    record = get_user_record(user)
    record["phone"] = contact.phone_number
    save_json(USERS_FILE, users)

    await update.effective_message.reply_text(
        "✅ شماره تلفنت ثبت شد.",
        reply_markup=main_keyboard(),
    )


# ==================================================
# پشتیبانی
# ==================================================


async def support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await ensure_member(update, context):
        return

    await update.effective_message.reply_text(
        "📞 پشتیبانی\n\n"
        "شناسه مدیر ربات:\n"
        f"{ADMIN_ID}\n\n"
        "برای پیگیری سفارش، شماره سفارش رو هم بنویس."
    )


# ==================================================
# مدیریت منو
# ==================================================


async def menu_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message
    text = message.text

    if not await ensure_member(update, context):
        return

    if text == "🔙 منوی اصلی":
        user_states.pop(user.id, None)

        await message.reply_text(
            "به منوی اصلی برگشتی.",
            reply_markup=main_keyboard(),
        )
        return

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

    state = user_states.get(user.id, {})
    step = state.get("step")

    if step == "quantity":
        await receive_quantity(update, context)
        return

    if step == "destination":
        await receive_destination(update, context)
        return

    if step == "receipt":
        await message.reply_text(
            "برای تکمیل سفارش، تصویر رسید رو به‌صورت عکس ارسال کن."
        )
        return

    await message.reply_text(
        "از منوی پایین یک گزینه انتخاب کن.",
        reply_markup=main_keyboard(),
    )


# ==================================================
# مدیریت خطاها
# ==================================================


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "خطای ربات",
        exc_info=context.error,
    )


# ==================================================
# اجرای ربات
# ==================================================


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "توکن تنظیم نشده است. "
            "در GitHub Secrets یک Secret به نام BOT_TOKEN بساز."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        CallbackQueryHandler(
            membership_callback,
            pattern=r"^check_membership$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_order_action,
            pattern=r"^(approve|reject):\d+$",
        )
    )

    app.add_handler(
        MessageHandler(
            filters.CONTACT,
            receive_contact,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_receipt,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_router,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("ربات در حال اجراست.")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
