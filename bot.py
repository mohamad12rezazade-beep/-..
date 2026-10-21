import json
import logging
import os
from decimal import Decimal, InvalidOperation

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    PicklePersistence,
    filters,
)

# =====================================================
# تنظیمات ربات
# =====================================================

TOKEN = "8714704830:AAGYitrRQQ0TLv2Zg-fc1gbKTyi6Jm08n-g"

OWNER_ID = 8935601841

CHANNEL_USERNAME = "@BNI_MMAD"
GROUP_USERNAME = "@BNI_MMAD1"
REPORT_CHANNEL = "@BNI_MMAD"

CARD_NUMBER = "6219861856357990"
CARD_HOLDER = "رضازاده"

# قیمت DOGS
DOGS_PRICE = 12
MIN_DOGS = 1000

# قیمت TON
TON_PRICE_PER_01 = 40000
MIN_TON = Decimal("0.1")
TON_STEP = Decimal("0.1")

ORDERS_FILE = "orders.json"
PERSISTENCE_FILE = "bot_data.pickle"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# =====================================================
# صفحه‌کلیدها
# =====================================================

phone_keyboard = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton(
                "📱 ارسال شماره تلفن",
                request_contact=True,
            )
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

main_keyboard = ReplyKeyboardMarkup(
    [
        ["🐶 خرید DOGS", "💎 خرید TON"],
        ["💬 پشتیبانی", "📢 کانال گزارش سفارش‌ها"],
    ],
    resize_keyboard=True,
)

back_keyboard = ReplyKeyboardMarkup(
    [["🔙 بازگشت به منو"]],
    resize_keyboard=True,
)

membership_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "📢 عضویت در کانال",
                url="https://t.me/BNI_MMAD",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 عضویت در گروه",
                url="https://t.me/BNI_MMAD1",
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


# =====================================================
# توابع کمکی
# =====================================================

def normalize_digits(value):
    """تبدیل اعداد فارسی و عربی به انگلیسی."""

    if not value:
        return ""

    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return (
        value.translate(table)
        .replace("٬", "")
        .replace(",", ".")
    )


def format_money(value):
    return f"{int(value):,}"


def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return {}

    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as file:
            result = json.load(file)

        return result if isinstance(result, dict) else {}

    except (OSError, json.JSONDecodeError):
        logger.exception("خطا در خواندن سفارش‌ها")
        return {}


def save_orders(orders):
    temporary_file = ORDERS_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(
            orders,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, ORDERS_FILE)


async def check_membership(context, user_id):
    """بررسی عضویت در کانال و گروه."""

    for chat_id in (CHANNEL_USERNAME, GROUP_USERNAME):
        try:
            member = await context.bot.get_chat_member(
                chat_id,
                user_id,
            )

            if member.status in ("left", "kicked"):
                return False

        except Exception:
            logger.exception(
                "بررسی عضویت ناموفق بود: user=%s chat=%s",
                user_id,
                chat_id,
            )
            return False

    return True


async def show_main_menu(update, context):
    context.user_data["state"] = "menu"

    await update.effective_message.reply_text(
        "سلام، خوش اومدی 🌹\n\n"
        "از منوی زیر یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=main_keyboard,
    )


async def show_membership(update, context):
    context.user_data["state"] = "membership"

    await update.effective_message.reply_text(
        "برای استفاده از ربات ابتدا عضو کانال و گروه شو، "
        "بعد روی بررسی عضویت بزن.",
        reply_markup=membership_keyboard,
    )


# =====================================================
# دستور START
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # اطلاعات کاربر را پاک نمی‌کنیم.
    # اگر شماره قبلاً ثبت شده باشد، دوباره درخواست نمی‌شود.

    if context.user_data.get("phone"):
        if await check_membership(
            context,
            update.effective_user.id,
        ):
            await show_main_menu(update, context)
        else:
            await show_membership(update, context)

        return

    context.user_data["state"] = "phone"

    await update.message.reply_text(
        "سلام 🌹 به ربات خرید DOGS و TON خوش اومدی.\n\n"
        "برای شروع، شماره تلفنت رو با دکمه زیر ارسال کن.",
        reply_markup=phone_keyboard,
    )


# =====================================================
# دریافت شماره تلفن
# =====================================================

async def handle_contact(update, context):
    contact = update.message.contact
    user = update.effective_user

    if not contact:
        return

    if contact.user_id != user.id:
        await update.message.reply_text(
            "لطفاً شماره تلفن خودت رو ارسال کن."
        )
        return

    context.user_data["phone"] = normalize_digits(
        contact.phone_number
    )

    if await check_membership(context, user.id):
        await show_main_menu(update, context)
    else:
        await show_membership(update, context)


# =====================================================
# بررسی عضویت و دکمه‌های مدیر
# =====================================================

async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "check_membership":
        if await check_membership(context, query.from_user.id):
            context.user_data["state"] = "menu"

            await query.message.reply_text(
                "عضویت تأیید شد ✅\n"
                "حالا می‌تونی از منوی خرید استفاده کنی.",
                reply_markup=main_keyboard,
            )
        else:
            await query.message.reply_text(
                "هنوز عضویت در کانال و گروه تأیید نشده.",
                reply_markup=membership_keyboard,
            )

        return

    if data.startswith(("approve:", "reject:")):
        if query.from_user.id != OWNER_ID:
            await query.message.reply_text(
                "این عملیات فقط برای مدیر مجاز است."
            )
            return

        action, order_id = data.split(":", 1)
        orders = load_orders()
        order = orders.get(order_id)

        if not order:
            await query.message.reply_text(
                "سفارش پیدا نشد."
            )
            return

        if order.get("status") != "pending":
            await query.message.reply_text(
                "این سفارش قبلاً بررسی شده است."
            )
            return

        if action == "approve":
            order["status"] = "approved"
            result_text = (
                "سفارش شما توسط مدیر تأیید شد ✅"
            )
            admin_text = "سفارش تأیید شد ✅"
        else:
            order["status"] = "rejected"
            result_text = (
                "سفارش شما رد شد ❌\n"
                "برای پیگیری با پشتیبانی تماس بگیر."
            )
            admin_text = "سفارش رد شد ❌"

        save_orders(orders)

        try:
            await context.bot.send_message(
                chat_id=int(order["user_id"]),
                text=result_text,
            )
        except Exception:
            logger.exception("ارسال نتیجه سفارش ناموفق بود")

        await query.message.reply_text(admin_text)
        return

    if data.startswith("reply:"):
        if query.from_user.id != OWNER_ID:
            return

        target_user = data.split(":", 1)[1]

        context.user_data["reply_to"] = target_user
        context.user_data["state"] = "owner_reply"

        await query.message.reply_text(
            f"پاسخ خودت را برای کاربر {target_user} بفرست."
        )


# =====================================================
# شروع خرید DOGS
# =====================================================

async def start_dogs(update, context):
    context.user_data["state"] = "dogs_quantity"

    await update.message.reply_text(
        "🐶 خرید DOGS\n\n"
        f"قیمت هر عدد: {DOGS_PRICE} تومان\n"
        f"حداقل سفارش: {MIN_DOGS} عدد\n\n"
        "تعداد موردنظرت را وارد کن:",
        reply_markup=back_keyboard,
    )


# =====================================================
# شروع خرید TON
# =====================================================

async def start_ton(update, context):
    context.user_data["state"] = "ton_quantity"

    await update.message.reply_text(
        "💎 خرید TON\n\n"
        "قیمت هر ۰٫۱ TON برابر ۴۰٬۰۰۰ تومان است.\n"
        "حداقل خرید: ۰٫۱ TON\n\n"
        "مقدار TON را وارد کن.\n"
        "مثال: ۰٫۱ یا ۰٫۲ یا ۰٫۵ یا ۱",
        reply_markup=back_keyboard,
    )


# =====================================================
# ساخت سفارش و نمایش اطلاعات پرداخت
# =====================================================

async def create_order(update, context):
    user = update.effective_user

    product = context.user_data.get("product")
    quantity = context.user_data.get("quantity")
    destination = context.user_data.get("destination")
    total = context.user_data.get("total")

    if any(
        value is None
        for value in (product, quantity, destination, total)
    ):
        context.user_data["state"] = "menu"

        await update.message.reply_text(
            "اطلاعات سفارش ناقص است. دوباره از منو شروع کن.",
            reply_markup=main_keyboard,
        )
        return

    orders = load_orders()

    numeric_ids = [
        int(key)
        for key in orders
        if str(key).isdigit()
    ]

    order_id = str(max(numeric_ids, default=0) + 1)

    orders[order_id] = {
        "order_id": order_id,
        "user_id": user.id,
        "username": user.username or "",
        "phone": context.user_data.get("phone", ""),
        "product": product,
        "quantity": str(quantity),
        "destination": destination,
        "total": int(total),
        "status": "awaiting_receipt",
    }

    save_orders(orders)

    context.user_data["order_id"] = order_id
    context.user_data["state"] = "payment"

    await update.message.reply_text(
        "💳 اطلاعات پرداخت\n\n"
        f"شماره سفارش: {order_id}\n"
        f"محصول: {product}\n"
        f"مقدار: {quantity}\n"
        f"آدرس مقصد: {destination}\n"
        f"مبلغ: {format_money(total)} تومان\n\n"
        f"شماره کارت: {CARD_NUMBER}\n"
        f"به نام: {CARD_HOLDER}\n\n"
        "بعد از پرداخت، عکس رسید را ارسال کن.",
        reply_markup=back_keyboard,
    )


# =====================================================
# دریافت رسید پرداخت
# =====================================================

async def handle_receipt(update, context):
    message = update.effective_message
    user = update.effective_user

    order_id = context.user_data.get("order_id")

    if not order_id:
        await message.reply_text(
            "سفارش فعالی پیدا نشد. از منو دوباره شروع کن.",
            reply_markup=main_keyboard,
        )
        context.user_data["state"] = "menu"
        return

    orders = load_orders()
    order = orders.get(str(order_id))

    if not order or order.get("status") != "awaiting_receipt":
        await message.reply_text(
            "این سفارش در انتظار دریافت رسید نیست."
        )
        return

    order["status"] = "pending"
    save_orders(orders)

    keyboard = InlineKeyboardMarkup(
        [
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
        ]
    )

    caption = (
        f"🧾 سفارش شماره {order_id}\n\n"
        f"کاربر: {user.full_name}\n"
        f"شناسه: {user.id}\n"
        f"نام کاربری: @{user.username or 'ندارد'}\n"
        f"شماره: {context.user_data.get('phone', 'ثبت نشده')}\n\n"
        f"محصول: {order['product']}\n"
        f"مقدار: {order['quantity']}\n"
        f"مقصد: {order['destination']}\n"
        f"مبلغ: {format_money(order['total'])} تومان"
    )

    try:
        await context.bot.send_photo(
            chat_id=OWNER_ID,
            photo=message.photo[-1].file_id,
            caption=caption,
            reply_markup=keyboard,
        )
    except Exception:
        # در صورت خطا، سفارش را برای تلاش مجدد آماده می‌کنیم.
        order["status"] = "awaiting_receipt"
        save_orders(orders)

        logger.exception("ارسال رسید به مدیر ناموفق بود")

        await message.reply_text(
            "ارسال رسید به مدیر ناموفق بود. دوباره تلاش کن."
        )
        return

    try:
        await context.bot.send_photo(
            chat_id=REPORT_CHANNEL,
            photo=message.photo[-1].file_id,
            caption=(
                f"🧾 سفارش جدید شماره {order_id}\n"
                f"محصول: {order['product']}\n"
                f"مقدار: {order['quantity']}\n"
                f"مبلغ: {format_money(order['total'])} تومان\n"
                "وضعیت: در انتظار بررسی"
            ),
        )
    except Exception:
        logger.exception("ارسال گزارش به کانال ناموفق بود")

    context.user_data["state"] = "menu"

    await message.reply_text(
        "رسید پرداخت ارسال شد ✅\n"
        "بعد از بررسی مدیر، نتیجه برایت ارسال می‌شود.",
        reply_markup=main_keyboard,
    )


# =====================================================
# پردازش پیام‌ها
# =====================================================

async def handle_message(update, context):
    message = update.effective_message

    if not message:
        return

    user = update.effective_user
    text = message.text or ""
    state = context.user_data.get("state", "menu")

    # رسید را پیش از پردازش پیام‌های متنی بررسی می‌کنیم.
    if state == "payment" and message.photo:
        await handle_receipt(update, context)
        return

    # پاسخ مدیر به کاربر
    if (
        user.id == OWNER_ID
        and state == "owner_reply"
        and text
        and text != "🔙 بازگشت به منو"
    ):
        target = context.user_data.get("reply_to")

        if target:
            try:
                await context.bot.send_message(
                    chat_id=int(target),
                    text=f"💬 پاسخ پشتیبانی:\n\n{text}",
                )
                await message.reply_text("پیام ارسال شد ✅")
            except Exception:
                logger.exception("ارسال پاسخ ناموفق بود")
                await message.reply_text("ارسال پیام ناموفق بود.")

        context.user_data.pop("reply_to", None)
        context.user_data["state"] = "menu"
        return

    # بازگشت به منو
    if text == "🔙 بازگشت به منو":
        await show_main_menu(update, context)
        return

    # دکمه‌های منو همیشه بررسی می‌شوند.
    if text == "🐶 خرید DOGS":
        if not context.user_data.get("phone"):
            await start(update, context)
            return

        await start_dogs(update, context)
        return

    if text == "💎 خرید TON":
        if not context.user_data.get("phone"):
            await start(update, context)
            return

        await start_ton(update, context)
        return

    if text == "📢 کانال گزارش سفارش‌ها":
        await message.reply_text(
            "کانال گزارش سفارش‌ها:\n"
            "https://t.me/BNI_MMAD"
        )
        return

    if text == "💬 پشتیبانی":
        context.user_data["state"] = "support"

        await message.reply_text(
            "پیامت را بنویس تا برای مدیر ارسال کنم.",
            reply_markup=back_keyboard,
        )
        return

    # دریافت پیام پشتیبانی
    if state == "support":
        if not text:
            await message.reply_text("لطفاً پیام متنی ارسال کن.")
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "↩️ پاسخ به کاربر",
                        callback_data=f"reply:{user.id}",
                    )
                ]
            ]
        )

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=(
                "💬 پیام جدید پشتیبانی\n\n"
                f"شناسه کاربر: {user.id}\n"
                f"نام کاربری: @{user.username or 'ندارد'}\n\n"
                f"پیام:\n{text}"
            ),
            reply_markup=keyboard,
        )

        context.user_data["state"] = "menu"

        await message.reply_text(
            "پیامت به پشتیبانی ارسال شد ✅",
            reply_markup=main_keyboard,
        )
        return

    # تعداد DOGS
    if state == "dogs_quantity":
        try:
            normalized = normalize_digits(text.strip())

            if not normalized.isdigit():
                raise ValueError

            quantity = int(normalized)

        except ValueError:
            await message.reply_text(
                "تعداد باید عدد صحیح باشد. مثال: ۱۰۰۰"
            )
            return

        if quantity < MIN_DOGS:
            await message.reply_text(
                f"حداقل سفارش {MIN_DOGS} عدد است."
            )
            return

        context.user_data["product"] = "DOGS"
        context.user_data["quantity"] = quantity
        context.user_data["total"] = quantity * DOGS_PRICE
        context.user_data["state"] = "destination"

        await message.reply_text(
            f"تعداد: {quantity:,} DOGS\n"
            f"مبلغ: {format_money(quantity * DOGS_PRICE)} تومان\n\n"
            "آدرس کیف پول یا مقصد DOGS را وارد کن:",
            reply_markup=back_keyboard,
        )
        return

    # مقدار TON
    if state == "ton_quantity":
        try:
            normalized = normalize_digits(text.strip())
            ton_amount = Decimal(normalized)

        except (InvalidOperation, ValueError):
            await message.reply_text(
                "مقدار TON معتبر نیست. مثال: ۰٫۱ یا ۰٫۵ یا ۱"
            )
            return

        if not ton_amount.is_finite():
            await message.reply_text("مقدار TON معتبر نیست.")
            return

        if ton_amount < MIN_TON:
            await message.reply_text(
                "حداقل خرید ۰٫۱ TON است."
            )
            return

        if ton_amount % TON_STEP != 0:
            await message.reply_text(
                "مقدار باید مضربی از ۰٫۱ باشد؛ "
                "مثلاً ۰٫۱، ۰٫۲، ۰٫۵ یا ۱."
            )
            return

        total = int(
            (ton_amount / TON_STEP) * TON_PRICE_PER_01
        )

        context.user_data["product"] = "TON"
        context.user_data["quantity"] = str(ton_amount)
        context.user_data["total"] = total
        context.user_data["state"] = "destination"

        await message.reply_text(
            f"مقدار: {ton_amount} TON\n"
            f"مبلغ: {format_money(total)} تومان\n\n"
            "آدرس کیف پول TON مقصد را وارد کن:",
            reply_markup=back_keyboard,
        )
        return

    # آدرس مقصد
    if state == "destination":
        destination = text.strip()

        if len(destination) < 5 or len(destination) > 200:
            await message.reply_text(
                "آدرس مقصد معتبر نیست؛ دوباره وارد کن."
            )
            return

        context.user_data["destination"] = destination

        await create_order(update, context)
        return

    # اگر هنوز شماره ثبت نشده باشد
    if not context.user_data.get("phone"):
        await start(update, context)
        return

    await message.reply_text(
        "یکی از گزینه‌های منو را انتخاب کن.",
        reply_markup=main_keyboard,
    )


# =====================================================
# خطاها
# =====================================================

async def error_handler(update, context):
    logger.error(
        "خطای ربات",
        exc_info=context.error,
    )


# =====================================================
# اجرای ربات
# =====================================================

def main():
    if TOKEN == "توکن_واقعی_ربات":
        raise RuntimeError(
            "توکن ربات را در ابتدای فایل وارد کن."
        )

    persistence = PicklePersistence(
        filepath=PERSISTENCE_FILE,
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .persistence(persistence)
        .build()
    )

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.CONTACT,
            handle_contact,
        )
    )

    app.add_handler(
        CallbackQueryHandler(handle_callback)
    )

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message,
        )
    )

    app.add_error_handler(error_handler)

    print("ربات اجرا شد.")
    app.run_polling()


if __name__ == "__main__":
    main()
