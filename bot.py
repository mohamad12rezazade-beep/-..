import os
import json
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

ADMIN_ID = 8935601841

CARD_NUMBER = "6219861856357990"
CARD_OWNER = "رضازاده"

CHANNEL_USERNAME = "@BNI_MMAD"
CHANNEL_LINK = "https://t.me/BNI_MMAD"

GROUP_USERNAME = "@BNI_MMAD1"
GROUP_LINK = "https://t.me/BNI_MMAD1"

DOGS_PRICE = 12
TON_PRICE_PER_01 = 40000
STARS_PRICE = 4800

DOGS_MIN = 1000
TON_MIN = 0.1
STARS_MIN = 1
STARS_MAX = 1000

USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================
# فایل‌های ذخیره‌سازی
# =========================

def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users():
    return load_json(USERS_FILE, {})


def save_users(users):
    save_json(USERS_FILE, users)


def load_orders():
    return load_json(ORDERS_FILE, [])


def save_orders(orders):
    save_json(ORDERS_FILE, orders)


# =========================
# ابزارهای کمکی
# =========================

def is_private(update: Update) -> bool:
    """هیچ منو یا فرایند خریدی در گروه اجرا نمی‌شود."""
    return (
        update.effective_chat is not None
        and update.effective_chat.type == "private"
    )


def main_menu():
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


async def is_member(bot, user_id):
    for chat_id in (CHANNEL_USERNAME, GROUP_USERNAME):
        try:
            member = await bot.get_chat_member(chat_id, user_id)

            if member.status in ("left", "kicked"):
                return False

        except Exception:
            logger.exception(
                "خطا در بررسی عضویت کاربر %s در %s",
                user_id,
                chat_id,
            )
            return False

    return True


async def show_main_menu(update, context):
    if not is_private(update):
        return

    await update.effective_message.reply_text(
        "سلام! 👋\nبه ربات فروش خوش آمدی.\n\n"
        "از منوی زیر محصول موردنظرت رو انتخاب کن.",
        reply_markup=main_menu(),
    )


async def require_membership(update, context):
    if not is_private(update):
        return False

    user = update.effective_user

    if await is_member(context.bot, user.id):
        return True

    await update.effective_message.reply_text(
        "برای استفاده از ربات، ابتدا در کانال و گروه عضو شو "
        "و سپس روی «بررسی عضویت» بزن.",
        reply_markup=membership_keyboard(),
    )
    return False


def get_user_record(user):
    users = load_users()
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

    save_users(users)
    return users[uid]


def create_order(user, product, amount, details, price):
    orders = load_orders()

    order_id = max(
        [int(o.get("id", 0)) for o in orders],
        default=0,
    ) + 1

    order = {
        "id": order_id,
        "user_id": user.id,
        "name": user.full_name,
        "username": user.username,
        "product": product,
        "amount": amount,
        "details": details,
        "price": price,
        "status": "awaiting_receipt",
        "created_at": datetime.now().isoformat(),
        "receipt_file_id": None,
    }

    orders.append(order)
    save_orders(orders)

    return order


def find_order(order_id):
    orders = load_orders()

    for order in orders:
        if int(order.get("id", 0)) == int(order_id):
            return order

    return None


def update_order(order_id, **changes):
    orders = load_orders()

    for order in orders:
        if int(order.get("id", 0)) == int(order_id):
            order.update(changes)
            save_orders(orders)
            return order

    return None


# =========================
# شروع ربات
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private(update):
        return

    user = update.effective_user
    get_user_record(user)

    if not await require_membership(update, context):
        return

    context.user_data.clear()
    await show_main_menu(update, context)


async def check_membership_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query.message.chat.type != "private":
        await query.answer()
        return

    await query.answer()

    if await is_member(context.bot, query.from_user.id):
        get_user_record(query.from_user)
        await query.message.reply_text(
            "عضویت تأیید شد ✅",
            reply_markup=main_menu(),
        )
    else:
        await query.message.reply_text(
            "هنوز عضویتت تأیید نشده. ابتدا عضو کانال و گروه شو.",
            reply_markup=membership_keyboard(),
        )


# =========================
# شروع خرید
# =========================

async def begin_purchase(update, context, product):
    if not is_private(update):
        return

    if not await require_membership(update, context):
        return

    context.user_data.clear()
    context.user_data["product"] = product
    context.user_data["step"] = "amount"

    if product == "DOGS":
        message = (
            "🐶 خرید DOGS\n\n"
            "قیمت هر DOGS: ۱۲ تومان\n"
            "حداقل سفارش: ۱۰۰۰ عدد\n\n"
            "تعداد DOGS موردنظر رو وارد کن:"
        )

    elif product == "TON":
        message = (
            "💎 خرید TON\n\n"
            "قیمت هر ۰٫۱ TON: ۴۰٬۰۰۰ تومان\n"
            "حداقل سفارش: ۰٫۱ TON\n\n"
            "مقدار باید مضربی از ۰٫۱ باشد.\n"
            "مثلاً ۰٫۱ یا ۰٫۲ یا ۱\n\n"
            "مقدار TON رو وارد کن:"
        )

    else:
        message = (
            "⭐ خرید Telegram Stars\n\n"
            "قیمت هر Star: ۴٬۸۰۰ تومان\n"
            "حداقل: ۱ عدد\n"
            "حداکثر: ۱۰۰۰ عدد\n\n"
            "تعداد Stars رو وارد کن:"
        )

    await update.effective_message.reply_text(
        message,
        reply_markup=ReplyKeyboardRemove(),
    )


def calculate_price(product, amount):
    if product == "DOGS":
        return int(amount) * DOGS_PRICE

    if product == "TON":
        return int(round(float(amount) * 10)) * TON_PRICE_PER_01

    if product == "Stars":
        return int(amount) * STARS_PRICE

    return 0


async def process_amount(update, context):
    if not is_private(update):
        return

    product = context.user_data.get("product")

    if not product or context.user_data.get("step") != "amount":
        return

    raw = update.effective_message.text.strip()

    try:
        normalized = raw.replace(",", ".").replace("٫", ".")
        amount = float(normalized)
    except ValueError:
        await update.effective_message.reply_text(
            "لطفاً مقدار رو به‌صورت عددی وارد کن."
        )
        return

    if product == "DOGS":
        if not amount.is_integer() or amount < DOGS_MIN:
            await update.effective_message.reply_text(
                "حداقل سفارش DOGS برابر ۱۰۰۰ عدد است. "
                "لطفاً یک عدد صحیح وارد کن."
            )
            return

        amount = int(amount)

    elif product == "TON":
        if amount < TON_MIN:
            await update.effective_message.reply_text(
                "حداقل سفارش ۰٫۱ TON است."
            )
            return

        tenths = round(amount * 10)

        if abs(amount * 10 - tenths) > 1e-7:
            await update.effective_message.reply_text(
                "مقدار باید مضربی از ۰٫۱ باشد؛ "
                "مثلاً ۰٫۱، ۰٫۲ یا ۱."
            )
            return

        amount = tenths / 10

    else:
        if (
            not amount.is_integer()
            or amount < STARS_MIN
            or amount > STARS_MAX
        ):
            await update.effective_message.reply_text(
                "تعداد Stars باید عدد صحیح بین ۱ تا ۱۰۰۰ باشد."
            )
            return

        amount = int(amount)

    context.user_data["amount"] = amount
    context.user_data["step"] = "details"

    if product in ("DOGS", "TON"):
        prompt = (
            "آدرس کیف پول خودت رو ارسال کن.\n\n"
            "⚠️ آدرس را با دقت بررسی کن."
        )
    else:
        prompt = (
            "لینک پست تلگرام یا اطلاعات موردنیاز برای ارسال Stars "
            "رو بفرست."
        )

    await update.effective_message.reply_text(prompt)


async def process_details(update, context):
    if not is_private(update):
        return

    if context.user_data.get("step") != "details":
        return

    product = context.user_data.get("product")
    amount = context.user_data.get("amount")
    details = update.effective_message.text.strip()

    if not details:
        await update.effective_message.reply_text(
            "لطفاً اطلاعات موردنیاز رو ارسال کن."
        )
        return

    price = calculate_price(product, amount)
    order = create_order(
        update.effective_user,
        product,
        amount,
        details,
        price,
    )

    context.user_data["order_id"] = order["id"]
    context.user_data["step"] = "receipt"

    await update.effective_message.reply_text(
        f"🧾 سفارش شماره {order['id']}\n\n"
        f"محصول: {product}\n"
        f"مقدار: {amount}\n"
        f"مبلغ قابل پرداخت: {price:,} تومان\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n\n"
        f"👤 به نام: {CARD_OWNER}\n\n"
        "پس از پرداخت، عکس رسید رو همین‌جا ارسال کن.\n"
        "سفارش بعد از بررسی مدیر تأیید یا رد می‌شه.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


# =========================
# رسید پرداخت
# =========================

async def process_receipt(update, context):
    if not is_private(update):
        return

    if context.user_data.get("step") != "receipt":
        return

    if not update.effective_message.photo:
        await update.effective_message.reply_text(
            "لطفاً عکس رسید پرداخت رو به‌صورت تصویر ارسال کن."
        )
        return

    order_id = context.user_data.get("order_id")
    order = find_order(order_id)

    if not order or order["user_id"] != update.effective_user.id:
        await update.effective_message.reply_text(
            "سفارش پیدا نشد. دوباره از منوی خرید شروع کن."
        )
        context.user_data.clear()
        return

    photo_id = update.effective_message.photo[-1].file_id

    update_order(
        order_id,
        receipt_file_id=photo_id,
        status="pending_review",
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تأیید سفارش",
                    callback_data=f"approve_{order_id}",
                ),
                InlineKeyboardButton(
                    "❌ رد سفارش",
                    callback_data=f"reject_{order_id}",
                ),
            ]
        ]
    )

    admin_text = (
        f"🛒 سفارش جدید برای بررسی\n\n"
        f"شماره سفارش: {order_id}\n"
        f"کاربر: {order['name']}\n"
        f"شناسه کاربر: {order['user_id']}\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {order['amount']}\n"
        f"مبلغ: {order['price']:,} تومان\n"
        f"اطلاعات تحویل: {order['details']}\n"
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=admin_text,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("ارسال رسید به مدیر ناموفق بود")

        await update.effective_message.reply_text(
            "ارسال رسید برای مدیر ناموفق بود. "
            "لطفاً کمی بعد دوباره تلاش کن یا با پشتیبانی تماس بگیر."
        )
        return

    context.user_data.clear()

    await update.effective_message.reply_text(
        "رسیدت دریافت شد ✅\n"
        "سفارش برای مدیر ارسال شد و پس از بررسی نتیجه اعلام می‌شه.",
        reply_markup=main_menu(),
    )


# =========================
# تأیید و رد سفارش توسط مدیر
# =========================

async def admin_order_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer(
            "فقط مدیر اجازه انجام این کار رو داره.",
            show_alert=True,
        )
        return

    data = query.data

    if data.startswith("approve_"):
        order_id = int(data.split("_", 1)[1])
        new_status = "approved"

    elif data.startswith("reject_"):
        order_id = int(data.split("_", 1)[1])
        new_status = "rejected"

    else:
        return

    order = find_order(order_id)

    if not order:
        await query.message.reply_text("سفارش پیدا نشد.")
        return

    if order["status"] != "pending_review":
        await query.message.reply_text(
            "این سفارش قبلاً بررسی شده یا دیگر در انتظار بررسی نیست."
        )
        return

    update_order(order_id, status=new_status)

    if new_status == "approved":
        channel_text = (
            f"✅ سفارش تأیید شد\n\n"
            f"شماره سفارش: {order_id}\n"
            f"محصول: {order['product']}\n"
            f"مقدار: {order['amount']}\n"
            f"مبلغ: {order['price']:,} تومان\n"
        )

        try:
            await context.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=channel_text,
            )
        except Exception:
            logger.exception("انتشار سفارش در کانال ناموفق بود")

        user_text = (
            f"سفارش شماره {order_id} تأیید شد ✅\n"
            "برای پیگیری تحویل، با پشتیبانی تماس بگیر."
        )

    else:
        user_text = (
            f"سفارش شماره {order_id} رد شد ❌\n"
            "اگر فکر می‌کنی اشتباهی رخ داده، با پشتیبانی تماس بگیر."
        )

    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=user_text,
        )
    except Exception:
        logger.exception("اطلاع‌رسانی به مشتری ناموفق بود")

    await query.message.reply_text(
        f"سفارش {order_id} بررسی شد: {new_status}"
    )


# =========================
# حساب کاربری و سفارش‌ها
# =========================

async def show_orders(update, context):
    if not is_private(update):
        return

    orders = load_orders()
    user_orders = [
        order for order in orders
        if order.get("user_id") == update.effective_user.id
    ]

    if not user_orders:
        await update.effective_message.reply_text(
            "هنوز سفارشی ثبت نکردی.",
            reply_markup=main_menu(),
        )
        return

    lines = ["📦 سفارش‌های شما:\n"]

    for order in user_orders[-20:]:
        lines.append(
            f"شماره: {order['id']}\n"
            f"محصول: {order['product']}\n"
            f"مقدار: {order['amount']}\n"
            f"مبلغ: {order['price']:,} تومان\n"
            f"وضعیت: {order['status']}\n"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=main_menu(),
    )


async def show_account(update, context):
    if not is_private(update):
        return

    user = get_user_record(update.effective_user)

    keyboard = ReplyKeyboardMarkup(
        [["📱 ارسال شماره تلفن"], ["🔙 منوی اصلی"]],
        resize_keyboard=True,
    )

    from telegram import KeyboardButton

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

    phone = user.get("phone") or "ثبت نشده"

    await update.effective_message.reply_text(
        f"👤 حساب کاربری\n\n"
        f"نام: {user['name']}\n"
        f"شناسه تلگرام: {user['id']}\n"
        f"نام کاربری: @{user['username'] or 'ندارد'}\n"
        f"شماره تلفن: {phone}",
        reply_markup=keyboard,
    )


async def save_contact(update, context):
    if not is_private(update):
        return

    contact = update.effective_message.contact

    if not contact:
        return

    if contact.user_id and contact.user_id != update.effective_user.id:
        await update.effective_message.reply_text(
            "لطفاً شماره تلفن خودت رو ارسال کن."
        )
        return

    users = load_users()
    uid = str(update.effective_user.id)

    if uid not in users:
        users[uid] = {
            "id": update.effective_user.id,
            "name": update.effective_user.full_name,
            "username": update.effective_user.username,
            "created_at": datetime.now().isoformat(),
        }

    users[uid]["phone"] = contact.phone_number
    save_users(users)

    await update.effective_message.reply_text(
        "شماره تلفنت ثبت شد ✅",
        reply_markup=main_menu(),
    )


# =========================
# راهنما و پشتیبانی
# =========================

async def show_help(update, context):
    if not is_private(update):
        return

    await update.effective_message.reply_text(
        "📚 راهنمای خرید\n\n"
        "۱. محصول موردنظر رو انتخاب کن.\n"
        "۲. مقدار رو وارد کن.\n"
        "۳. آدرس کیف پول یا لینک لازم رو بفرست.\n"
        "۴. مبلغ نمایش‌داده‌شده رو پرداخت کن.\n"
        "۵. عکس رسید رو ارسال کن.\n"
        "۶. منتظر بررسی مدیر بمون.\n\n"
        "DOGS: هر عدد ۱۲ تومان، حداقل ۱۰۰۰ عدد.\n"
        "TON: هر ۰٫۱ برابر ۴۰٬۰۰۰ تومان.\n"
        "Stars: هر عدد ۴٬۸۰۰ تومان، از ۱ تا ۱۰۰۰ عدد.",
        reply_markup=main_menu(),
    )


async def show_support(update, context):
    if not is_private(update):
        return

    await update.effective_message.reply_text(
        "📞 برای پشتیبانی، به مدیر ربات پیام بده:\n"
        "شناسه مدیر: 8935601841\n\n"
        "شماره سفارش خودت رو هم ارسال کن تا پیگیری راحت‌تر باشه.",
        reply_markup=main_menu(),
    )


# =========================
# منوی اصلی
# =========================

async def menu_router(update, context):
    if not is_private(update):
        return

    text = update.effective_message.text

    if not text:
        return

    if not await require_membership(update, context):
        return

    if text == "🛒 خرید DOGS":
        await begin_purchase(update, context, "DOGS")

    elif text == "💎 خرید TON":
        await begin_purchase(update, context, "TON")

    elif text == "⭐ خرید Stars":
        await begin_purchase(update, context, "Stars")

    elif text == "📦 سفارش‌های من":
        await show_orders(update, context)

    elif text == "👤 حساب کاربری":
        await show_account(update, context)

    elif text == "📞 پشتیبانی":
        await show_support(update, context)

    elif text == "📚 راهنما":
        await show_help(update, context)

    elif text == "🔙 منوی اصلی":
        context.user_data.clear()
        await show_main_menu(update, context)

    elif context.user_data.get("step") == "amount":
        await process_amount(update, context)

    elif context.user_data.get("step") == "details":
        await process_details(update, context)

    else:
        await update.effective_message.reply_text(
            "لطفاً یکی از گزینه‌های منو رو انتخاب کن.",
            reply_markup=main_menu(),
        )


# =========================
# خطاهای ناشناخته
# =========================

async def unknown_command(update, context):
    if not is_private(update):
        return

    await update.effective_message.reply_text(
        "دستور شناخته نشد. از منوی اصلی استفاده کن.",
        reply_markup=main_menu(),
    )


# =========================
# اجرای ربات
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "توکن تنظیم نشده است. در GitHub Secrets مقدار BOT_TOKEN را ثبت کن."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    # بررسی عضویت و تأیید مدیر از طریق دکمه‌های شیشه‌ای
    app.add_handler(
        CallbackQueryHandler(
            check_membership_callback,
            pattern=r"^check_membership$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_order_callback,
            pattern=r"^(approve|reject)_\d+$",
        )
    )

    # تمام ورودی‌های عادی فقط در پیوی
    app.add_handler(
        CommandHandler(
            "start",
            start,
            filters=filters.ChatType.PRIVATE,
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            show_help,
            filters=filters.ChatType.PRIVATE,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.CONTACT,
            save_contact,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.PHOTO,
            process_receipt,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            menu_router,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.COMMAND,
            unknown_command,
        )
    )

    logger.info("ربات اجرا شد.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
