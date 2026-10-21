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

# ==================================================
# تنظیمات اصلی
# ==================================================

TOKEN = "8714704830:AAGYitrRQQ0TLv2Zg-fc1gbKTyi6Jm08n-g"

OWNER_ID = 8935601841

CHANNEL_USERNAME = "@BNI_MMAD"
GROUP_USERNAME = "@BNI_MMAD1"

REPORT_CHANNEL = "@BNI_MMAD"

# اطلاعات پرداخت
CARD_NUMBER = "6219861856357990"
CARD_HOLDER = "رضازاده"

# قیمت‌ها به تومان
DOGS_PRICE = 12
MIN_DOGS = 1000

TON_PRICE_PER_01 = 40000
MIN_TON = Decimal("0.1")
TON_STEP = Decimal("0.1")

ORDERS_FILE = "orders.json"
PERSISTENCE_FILE = "bot_data.pickle"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ==================================================
# صفحه‌کلیدها
# ==================================================

phone_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📱 ارسال شماره تلفن", request_contact=True)]
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


# ==================================================
# توابع کمکی
# ==================================================

def normalize_digits(text: str) -> str:
    """تبدیل اعداد فارسی و عربی به انگلیسی."""

    if not text:
        return ""

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return text.translate(translation).replace(",", ".").replace("٬", "")


def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return {}

    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        logger.exception("خطا در خواندن فایل سفارش‌ها")
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


def money(value):
    return f"{int(value):,}"


async def check_membership(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> bool:
    """بررسی عضویت کاربر در کانال و گروه."""

    for chat_id in (CHANNEL_USERNAME, GROUP_USERNAME):
        try:
            member = await context.bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )

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


async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["state"] = "menu"

    await update.effective_message.reply_text(
        "به ربات خرید DOGS و TON خوش آمدی 🌹\n\n"
        "یکی از گزینه‌های زیر را انتخاب کن:",
        reply_markup=main_keyboard,
    )


async def ask_membership(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["state"] = "membership"

    await update.effective_message.reply_text(
        "برای استفاده از ربات، ابتدا عضو کانال و گروه شو "
        "و سپس روی «بررسی عضویت» بزن.",
        reply_markup=membership_keyboard,
    )


# ==================================================
# شروع ربات
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    # اطلاعات کاربر را پاک نمی‌کنیم؛ شماره قبلی حفظ می‌شود.
    phone = context.user_data.get("phone")

    if phone:
        if await check_membership(
            context,
            update.effective_user.id,
        ):
            await show_main_menu(update, context)
        else:
            await ask_membership(update, context)

        return

    context.user_data["state"] = "phone"

    await update.message.reply_text(
        "سلام 🌹 به ربات خرید DOGS و TON خوش آمدی.\n\n"
        "برای شروع، شماره تلفنت را با دکمه زیر ارسال کن.",
        reply_markup=phone_keyboard,
    )


# ==================================================
# دریافت شماره تلفن
# ==================================================

async def handle_contact(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    contact = update.message.contact
    user = update.effective_user

    if not contact:
        return

    if contact.user_id != user.id:
        await update.message.reply_text(
            "لطفاً شماره تلفن خودت را با دکمه ارسال شماره بفرست."
        )
        return

    phone = normalize_digits(contact.phone_number)

    context.user_data["phone"] = phone

    if await check_membership(context, user.id):
        await show_main_menu(update, context)
    else:
        await ask_membership(update, context)


# ==================================================
# بررسی عضویت
# ==================================================

async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "check_membership":
        if await check_membership(
            context,
            query.from_user.id,
        ):
            context.user_data["state"] = "menu"

            await query.message.reply_text(
                "عضویتت تأیید شد ✅\n"
                "حالا می‌تونی از منوی ربات استفاده کنی.",
                reply_markup=main_keyboard,
            )
        else:
            await query.message.reply_text(
                "هنوز عضویتت در کانال و گروه تأیید نشده است.",
                reply_markup=membership_keyboard,
            )

        return

    # پاسخ مدیر به سفارش
    if data.startswith("approve:") or data.startswith("reject:"):
        if query.from_user.id != OWNER_ID:
            await query.message.reply_text(
                "این عملیات فقط برای مدیر ربات مجاز است."
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
            message = "سفارش شما توسط مدیر تأیید شد ✅"
            admin_message = "سفارش تأیید شد ✅"
        else:
            order["status"] = "rejected"
            message = (
                "سفارش شما رد شد ❌\n"
                "اگر فکر می‌کنی اشتباهی رخ داده، با پشتیبانی تماس بگیر."
            )
            admin_message = "سفارش رد شد ❌"

        save_orders(orders)

        try:
            await context.bot.send_message(
                chat_id=int(order["user_id"]),
                text=message,
            )
        except Exception:
            logger.exception(
                "ارسال نتیجه سفارش به کاربر ناموفق بود"
            )

        await query.message.reply_text(admin_message)

        return

    # پاسخ به پیام کاربر از سوی مدیر
    if data.startswith("reply:"):
        if query.from_user.id != OWNER_ID:
            await query.message.reply_text(
                "این عملیات فقط برای مدیر مجاز است."
            )
            return

        target_user_id = data.split(":", 1)[1]

        context.user_data["reply_to"] = target_user_id
        context.user_data["state"] = "owner_reply"

        await query.message.reply_text(
            f"پیام پاسخ را برای کاربر {target_user_id} ارسال کن."
        )


# ==================================================
# شروع خرید DOGS
# ==================================================

async def start_dogs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["state"] = "dogs_quantity"

    await update.message.reply_text(
        f"🐶 خرید DOGS\n\n"
        f"قیمت هر DOGS: {DOGS_PRICE} تومان\n"
        f"حداقل سفارش: {MIN_DOGS} عدد\n\n"
        "تعداد DOGS موردنظرت را وارد کن:",
        reply_markup=back_keyboard,
    )


# ==================================================
# شروع خرید TON
# ==================================================

async def start_ton(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["state"] = "ton_quantity"

    await update.message.reply_text(
        "💎 خرید TON\n\n"
        "قیمت هر ۰٫۱ TON: ۴۰٬۰۰۰ تومان\n"
        "حداقل سفارش: ۰٫۱ TON\n\n"
        "مقدار TON را وارد کن.\n"
        "مثال: ۰٫۱ یا ۰٫۵ یا ۱",
        reply_markup=back_keyboard,
    )


# ==================================================
# ثبت سفارش
# ==================================================

async def create_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    product = context.user_data.get("product")
    quantity = context.user_data.get("quantity")
    destination = context.user_data.get("destination")
    total = context.user_data.get("total")

    if not all(
        value is not None
        for value in (product, quantity, destination, total)
    ):
        context.user_data["state"] = "menu"

        await update.message.reply_text(
            "اطلاعات سفارش ناقص است. لطفاً از منو دوباره شروع کن.",
            reply_markup=main_keyboard,
        )
        return

    orders = load_orders()

    order_id = str(
        max(
            [int(key) for key in orders if key.isdigit()]
            or [0]
        ) + 1
    )

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
        f"محصول: {product}\n"
        f"مقدار: {quantity}\n"
        f"آدرس مقصد: {destination}\n"
        f"مبلغ قابل پرداخت: {money(total)} تومان\n\n"
        f"شماره کارت: {CARD_NUMBER}\n"
        f"به نام: {CARD_HOLDER}\n\n"
        "پس از پرداخت، عکس رسید را همین‌جا ارسال کن.\n"
        "⚠️ تا ارسال رسید، سفارش نهایی نمی‌شود.",
        reply_markup=back_keyboard,
    )


# ==================================================
# پردازش پیام‌ها
# ==================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    user = update.effective_user
    text = message.text or ""
    state = context.user_data.get("state", "menu")

    # مدیر در حال پاسخ دادن به کاربر است
    if (
        user.id == OWNER_ID
        and state == "owner_reply"
        and text
        and text != "🔙 بازگشت به منو"
    ):
        target_user_id = context.user_data.get("reply_to")

        if target_user_id:
            try:
                await context.bot.send_message(
                    chat_id=int(target_user_id),
                    text=f"💬 پاسخ پشتیبانی:\n\n{text}",
                )

                await message.reply_text(
                    "پاسخ برای کاربر ارسال شد ✅"
                )

            except Exception:
                logger.exception("ارسال پاسخ پشتیبانی ناموفق بود")

                await message.reply_text(
                    "ارسال پیام ناموفق بود."
                )

        context.user_data.pop("reply_to", None)
        context.user_data["state"] = "menu"
        return

    # دکمه بازگشت در همه مراحل
    if text == "🔙 بازگشت به منو":
        context.user_data["state"] = "menu"
        await show_main_menu(update, context)
        return

    # منوی اصلی؛ قبل از پردازش حالت‌های سفارش بررسی می‌شود
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
            "📢 کانال گزارش سفارش‌ها:\n"
            "https://t.me/BNI_MMAD"
        )
        return

    if text == "💬 پشتیبانی":
        context.user_data["state"] = "support"

        await message.reply_text(
            "پیام خودت را برای پشتیبانی بنویس.\n"
            "پیامت برای مدیر ارسال می‌شود.",
            reply_markup=back_keyboard,
        )
        return

    # دریافت پیام پشتیبانی
    if state == "support":
        if not text:
            await message.reply_text(
                "لطفاً پیام پشتیبانی را به‌صورت متن ارسال کن."
            )
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
                f"نام کاربری: @{user.username or 'ندارد'}\n"
                f"شماره: {context.user_data.get('phone', 'ثبت نشده')}\n\n"
                f"پیام:\n{text}"
            ),
            reply_markup=keyboard,
        )

        await message.reply_text(
            "پیامت برای پشتیبانی ارسال شد ✅",
            reply_markup=main_keyboard,
        )

        context.user_data["state"] = "menu"
        return

    # دریافت تعداد DOGS
    if state == "dogs_quantity":
        if not text:
            await message.reply_text(
                "لطفاً تعداد DOGS را به‌صورت عدد وارد کن."
            )
            return

        normalized = normalize_digits(text.strip())

        try:
            if not normalized.isdigit():
                raise ValueError

            quantity = int(normalized)

        except ValueError:
            await message.reply_text(
                "تعداد باید یک عدد صحیح باشد. دوباره وارد کن."
            )
            return

        if quantity < MIN_DOGS:
            await message.reply_text(
                f"حداقل سفارش {MIN_DOGS} عدد DOGS است."
            )
            return

        total = quantity * DOGS_PRICE

        context.user_data["product"] = "DOGS"
        context.user_data["quantity"] = quantity
        context.user_data["total"] = total
        context.user_data["state"] = "destination"

        await message.reply_text(
            f"تعداد: {quantity:,} DOGS\n"
            f"مبلغ: {money(total)} تومان\n\n"
            "آدرس کیف پول یا مقصد DOGS را وارد کن:",
            reply_markup=back_keyboard,
        )
        return

    # دریافت مقدار TON
    if state == "ton_quantity":
        if not text:
            await message.reply_text(
                "لطفاً مقدار TON را وارد کن؛ مثلاً ۰٫۱ یا ۰٫۵."
            )
            return

        normalized = normalize_digits(text.strip())

        try:
            ton_amount = Decimal(normalized)

        except InvalidOperation:
            await message.reply_text(
                "مقدار TON نامعتبر است. مثال صحیح: ۰٫۱ یا ۰٫۵ یا ۱"
            )
            return

        if not ton_amount.is_finite():
            await message.reply_text(
                "مقدار TON معتبر نیست."
            )
            return

        if ton_amount < MIN_TON:
            await message.reply_text(
                "حداقل مقدار خرید ۰٫۱ TON است."
            )
            return

        if ton_amount % TON_STEP != 0:
            await message.reply_text(
                "مقدار TON باید مضربی از ۰٫۱ باشد.\n"
                "مثال: ۰٫۱، ۰٫۲، ۰٫۵ یا ۱"
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
            f"مبلغ: {money(total)} تومان\n\n"
            "آدرس کیف پول TON مقصد را وارد کن:",
            reply_markup=back_keyboard,
        )
        return

    # دریافت آدرس مقصد
    if state == "destination":
        if not text:
            await message.reply_text(
                "لطفاً آدرس مقصد را به‌صورت متن ارسال کن."
            )
            return

        destination = text.strip()

        if len(destination) < 5 or len(destination) > 200:
            await message.reply_text(
                "آدرس واردشده معتبر به نظر نمی‌رسد. دوباره وارد کن."
            )
            return

        context.user_data["destination"] = destination

        await create_order(update, context)
        return

    # دریافت عکس رسید
    if state == "payment":
        if message.photo:
            order_id = context.user_data.get("order_id")
            orders = load_orders()
            order = orders.get(str(order_id))

            if not order:
                await message.reply_text(
                    "سفارش پیدا نشد. لطفاً با پشتیبانی تماس بگیر."
                )
                return

            if order.get("status") != "awaiting_receipt":
                await message.reply_text(
                    "این سفارش قبلاً رسید دریافت کرده یا بررسی شده است."
                )
                return

            order["status"] = "pending"
            save_orders(orders)

            approval_keyboard = InlineKeyboardMarkup(
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
                f"🧾 رسید پرداخت سفارش شماره {order_id}\n\n"
                f"کاربر: {user.full_name}\n"
                f"شناسه کاربر: {user.id}\n"
                f"نام کاربری: @{user.username or 'ندارد'}\n"
                f"شماره تلفن: {context.user_data.get('phone', 'ثبت نشده')}\n\n"
                f"محصول: {order['product']}\n"
                f"مقدار: {order['quantity']}\n"
                f"مقصد: {order['destination']}\n"
                f"مبلغ: {money(order['total'])} تومان"
            )

            # ارسال رسید و جزئیات سفارش به مدیر
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=message.photo[-1].file_id,
                caption=caption,
                reply_markup=approval_keyboard,
            )

            # گزارش سفارش به کانال
            try:
                await context.bot.send_photo(
                    chat_id=REPORT_CHANNEL,
                    photo=message.photo[-1].file_id,
                    caption=(
                        f"🧾 سفارش جدید شماره {order_id}\n\n"
                        f"محصول: {order['product']}\n"
                        f"مقدار: {order['quantity']}\n"
                        f"مبلغ: {money(order['total'])} تومان\n"
                        "وضعیت: در انتظار بررسی مدیر"
                    ),
                )
            except Exception:
                logger.exception(
                    "ارسال گزارش به کانال ناموفق بود"
                )

            await message.reply_text(
                "رسیدت با موفقیت ارسال شد ✅\n"
                "سفارش پس از بررسی مدیر تأیید یا رد می‌شود.",
                reply_markup=main_keyboard,
            )

            context.user_data["state"] = "menu"
            return

        await message.reply_text(
            "لطفاً عکس رسید پرداخت را ارسال کن."
        )
        return

    # پیام عمومی
    if not context.user_data.get("phone"):
        await start(update, context)
        return

    await message.reply_text(
        "لطفاً یکی از گزینه‌های منو را انتخاب کن.",
        reply_markup=main_keyboard,
    )


# ==================================================
# مدیریت خطا
# ==================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "خطای زمان اجرای ربات",
        exc_info=context.error,
    )


# ==================================================
# اجرای ربات
# ==================================================

def main():
    if TOKEN == "YOUR_BOT_TOKEN":
        raise RuntimeError(
            "ابتدا TOKEN ربات را در ابتدای فایل وارد کن."
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

    print("ربات اجرا شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
