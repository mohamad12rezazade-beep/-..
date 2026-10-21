import os
import json
import logging
from pathlib import Path

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
    filters,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "8935601841"))

REPORT_CHANNEL = "@BNI_MMAD"
CHANNEL_LINK = "https://t.me/BNI_MMAD"

CARD = "6219861856357990"
CARD_NAME = "رضازاده"

DATA_FILE = Path("orders.json")

GIFTS = {
    "تدی": 60000,
    "قلب": 60000,
    "گل": 110000,
    "موشک": 225000,
    "الماس": 460000,
}


def load_orders():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logging.exception("Could not load orders")
    return {}


def save_orders(orders):
    DATA_FILE.write_text(
        json.dumps(orders, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🛍 منو محصولات سفارش"],
            ["📞 پشتیبانی", "📢 چنل گزارش سفارش‌ها"],
        ],
        resize_keyboard=True,
    )


def product_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["⭐ ریکشن استارزی", "🐶 داگز اولترا"],
            ["🎁 گیفت"],
            ["🔙 بازگشت به منو"],
        ],
        resize_keyboard=True,
    )


def gift_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🧸 تدی", "❤️ قلب"],
            ["🌹 گل", "🚀 موشک"],
            ["💎 الماس"],
            ["🔙 بازگشت به محصولات"],
        ],
        resize_keyboard=True,
    )


def payment_text(amount):
    return (
        "💳 اطلاعات پرداخت\n\n"
        f"شماره کارت:\n{CARD}\n\n"
        f"به نام: {CARD_NAME}\n\n"
        f"مبلغ قابل پرداخت: {amount:,} تومان\n\n"
        "پس از پرداخت، تصویر رسید را همین‌جا ارسال کنید."
    )


# بررسی عضویت فقط در چنل
async def check_membership(bot, user_id):
    try:
        member = await bot.get_chat_member("@BNI_MMAD", user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        logging.exception(
            "Membership check failed for user %s",
            user_id,
        )
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["state"] = "phone"

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 تأیید شماره ایران", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await update.message.reply_text(
        "سلام! 👋\n\n"
        "برای شروع، شماره تلفن ایران خودت را با دکمه زیر ارسال کن.\n"
        "شماره باید با +98 شروع شود.",
        reply_markup=keyboard,
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact

    if contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "❌ لطفاً شماره خودت را ارسال کن."
        )
        return

    phone = contact.phone_number.replace(" ", "").replace("-", "")

    if phone.startswith("0098"):
        phone = "+98" + phone[4:]
    elif phone.startswith("98"):
        phone = "+" + phone
    elif phone.startswith("0"):
        phone = "+98" + phone[1:]

    if not phone.startswith("+98"):
        await update.message.reply_text(
            "❌ فقط شماره‌های ایران پذیرفته می‌شوند."
        )
        return

    context.user_data["phone"] = phone

    # بررسی عضویت فقط در چنل
    if not await check_membership(
        context.bot,
        update.effective_user.id,
    ):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📢 عضویت در چنل",
                    url=CHANNEL_LINK,
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 بررسی مجدد",
                    callback_data="check_members",
                )
            ],
        ])

        await update.message.reply_text(
            "برای استفاده از ربات، ابتدا در چنل عضو شو.",
            reply_markup=keyboard,
        )
        return

    context.user_data["state"] = "menu"

    await update.message.reply_text(
        "✅ شماره ثبت شد!\n"
        "به منوی اصلی خوش آمدی.",
        reply_markup=main_keyboard(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_members":
        if await check_membership(context.bot, query.from_user.id):
            context.user_data["state"] = "menu"

            await query.message.reply_text(
                "✅ عضویت تأیید شد.",
                reply_markup=main_keyboard(),
            )
        else:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📢 عضویت در چنل",
                        url=CHANNEL_LINK,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 بررسی مجدد",
                        callback_data="check_members",
                    )
                ],
            ])

            await query.message.reply_text(
                "❌ هنوز در چنل عضو نشده‌ای.",
                reply_markup=keyboard,
            )
        return

    if query.data.startswith(("approve:", "reject:")):
        action, order_id = query.data.split(":", 1)

        if query.from_user.id != OWNER_ID:
            await query.message.reply_text("⛔ دسترسی ندارید.")
            return

        orders = load_orders()
        order = orders.get(order_id)

        if not order or order.get("status") != "pending":
            await query.message.reply_text(
                "این سفارش وجود ندارد یا قبلاً بررسی شده است."
            )
            return

        if action == "approve":
            order["status"] = "approved"

            result = "✅ واریز شما تأیید شد."

            if order["product"] == "داگز اولترا":
                result += "\n🐶 سفارش داگز شما تأیید شد."
            elif order["product"] == "ری‌اکشن استارزی":
                result += "\n⭐ سفارش استارز شما تأیید شد."
            else:
                result += "\n🎁 سفارش گیفت شما تأیید شد."

        else:
            order["status"] = "rejected"
            result = (
                "❌ رسید سفارش شما تأیید نشد.\n"
                "لطفاً با پشتیبانی تماس بگیرید."
            )

        save_orders(orders)

        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=result,
            )
        except Exception:
            logging.exception("Could not notify order user")

        await query.message.reply_text("✅ عملیات انجام شد.")
        return

    if query.data.startswith("reply:"):
        if query.from_user.id != OWNER_ID:
            await query.message.reply_text("⛔ دسترسی ندارید.")
            return

        target_id = int(query.data.split(":", 1)[1])
        context.user_data["reply_to"] = target_id

        await query.message.reply_text(
            "پیام پاسخ را ارسال کن."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user
    text = message.text or ""

    if message.contact:
        await handle_contact(update, context)
        return

    # پاسخ مالک به پیام پشتیبانی
    if user.id == OWNER_ID and context.user_data.get("reply_to"):
        target_id = context.user_data.pop("reply_to")

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="📩 پاسخ پشتیبانی:\n\n" + text,
            )
            await message.reply_text("✅ پاسخ ارسال شد.")
        except Exception:
            logging.exception("Could not send support reply")
            await message.reply_text("❌ ارسال پاسخ ناموفق بود.")

        return

    if context.user_data.get("state") == "phone":
        await message.reply_text(
            "برای ادامه، شماره خودت را با دکمه اشتراک‌گذاری شماره بفرست."
        )
        return

    # دریافت تعداد محصولات
    if context.user_data.get("state") == "quantity":
        try:
            normalized_text = text.translate(
                str.maketrans(
                    "۰۱۲۳۴۵۶۷۸۹",
                    "0123456789",
                )
            )
            quantity = int(normalized_text)
        except ValueError:
            await message.reply_text(
                "لطفاً تعداد را به صورت عدد وارد کن."
            )
            return

        product = context.user_data.get("product")

        if product == "داگز اولترا":
            if quantity < 1000:
                await message.reply_text(
                    "حداقل تعداد سفارش ۱۰۰۰ داگز است."
                )
                return

            amount = quantity * 12

            context.user_data["quantity"] = quantity
            context.user_data["amount"] = amount
            context.user_data["state"] = "destination"

            await message.reply_text(
                "یوزرنیم اکانتی که داگز به آن واریز می‌شود را وارد کن."
            )
            return

        if product == "ری‌اکشن استارزی":
            if not 1 <= quantity <= 1000:
                await message.reply_text(
                    "تعداد استارز باید بین ۱ تا ۱۰۰۰ باشد."
                )
                return

            context.user_data["quantity"] = quantity
            context.user_data["amount"] = None
            context.user_data["state"] = "post_link"

            await message.reply_text("لینک پست را ارسال کن.")
            return

    # دریافت مقصد داگز
    if context.user_data.get("state") == "destination":
        if not text.strip():
            await message.reply_text(
                "لطفاً یوزرنیم مقصد را وارد کن."
            )
            return

        context.user_data["destination"] = text.strip()
        context.user_data["state"] = "payment"

        amount = context.user_data["amount"]

        await message.reply_text(payment_text(amount))
        return

    # دریافت لینک پست استارز
    if context.user_data.get("state") == "post_link":
        if not text.startswith(("https://t.me/", "http://t.me/")):
            await message.reply_text(
                "لطفاً لینک معتبر پست تلگرام را بفرست."
            )
            return

        context.user_data["post_link"] = text
        context.user_data["state"] = "payment"

        await message.reply_text(
            "برای استارز، قیمت باید پیش از پرداخت مشخص باشد.\n"
            "لطفاً نرخ هر استارز را از مالک استعلام کن.\n\n"
            + payment_text(0)
        )
        return

    # انتخاب منو
    if text == "🛍 منو محصولات سفارش":
        await message.reply_text(
            "یکی از محصولات را انتخاب کن:",
            reply_markup=product_keyboard(),
        )

    elif text == "🐶 داگز اولترا":
        context.user_data["product"] = "داگز اولترا"
        context.user_data["state"] = "quantity"

        await message.reply_text(
            "تعداد داگز را وارد کن. حداقل ۱۰۰۰."
        )

    elif text == "⭐ ریکشن استارزی":
        context.user_data["product"] = "ری‌اکشن استارزی"
        context.user_data["state"] = "quantity"

        await message.reply_text(
            "تعداد استارز را وارد کن (۱ تا ۱۰۰۰)."
        )

    elif text == "🎁 گیفت":
        await message.reply_text(
            "نوع گیفت را انتخاب کن:",
            reply_markup=gift_keyboard(),
        )

    elif text in GIFTS:
        context.user_data["product"] = text
        context.user_data["quantity"] = 1
        context.user_data["amount"] = GIFTS[text]
        context.user_data["destination"] = None
        context.user_data["post_link"] = None
        context.user_data["state"] = "payment"

        await message.reply_text(payment_text(GIFTS[text]))

    # پشتیبانی
    elif text == "📞 پشتیبانی":
        context.user_data["state"] = "support"

        await message.reply_text(
            "پیامت را ارسال کن تا برای پشتیبانی فرستاده شود."
        )

    elif context.user_data.get("state") == "support":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "↩️ پاسخ به کاربر",
                    callback_data=f"reply:{user.id}",
                )
            ]
        ])

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=(
                "📩 پیام پشتیبانی\n"
                f"کاربر: {user.id}\n"
                f"نام: {user.full_name}\n\n"
                f"{text}"
            ),
            reply_markup=keyboard,
        )

        context.user_data["state"] = "menu"

        await message.reply_text(
            "پیامت برای پشتیبانی ارسال شد.",
            reply_markup=main_keyboard(),
        )

    elif text == "📢 چنل گزارش سفارش‌ها":
        await message.reply_text(CHANNEL_LINK)

    elif text == "🔙 بازگشت به منو":
        context.user_data["state"] = "menu"

        await message.reply_text(
            "منوی اصلی:",
            reply_markup=main_keyboard(),
        )

    elif text == "🔙 بازگشت به محصولات":
        context.user_data["state"] = "menu"

        await message.reply_text(
            "منوی محصولات:",
            reply_markup=product_keyboard(),
        )

    # دریافت رسید پرداخت
    elif context.user_data.get("state") == "payment" and message.photo:
        orders = load_orders()

        order_id = f"{message.message_id}_{user.id}"

        order = {
            "user_id": user.id,
            "product": context.user_data.get("product"),
            "quantity": context.user_data.get("quantity"),
            "amount": context.user_data.get("amount"),
            "destination": context.user_data.get("destination"),
            "post_link": context.user_data.get("post_link"),
            "phone": context.user_data.get("phone"),
            "status": "pending",
        }

        orders[order_id] = order
        save_orders(orders)

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
                chat_id=OWNER_ID,
                photo=message.photo[-1].file_id,
                caption=(
                    "🛒 سفارش جدید\n"
                    f"کد: {order_id}\n"
                    f"کاربر: {user.id}\n"
                    f"محصول: {order['product']}\n"
                    f"تعداد: {order['quantity']}\n"
                    f"مبلغ: {order['amount']}\n"
                    f"مقصد: {order['destination']}\n"
                    f"لینک پست: {order['post_link']}\n"
                    "وضعیت: در انتظار بررسی"
                ),
                reply_markup=keyboard,
            )
        except Exception:
            logging.exception("Could not send order to owner")

            await message.reply_text(
                "❌ ارسال سفارش برای مالک ناموفق بود. "
                "لطفاً دوباره تلاش کن یا با پشتیبانی تماس بگیر."
            )
            return

        try:
            await context.bot.send_message(
                chat_id=REPORT_CHANNEL,
                text=(
                    "🛒 سفارش جدید\n"
                    f"کد سفارش: {order_id}\n"
                    f"محصول: {order['product']}\n"
                    f"تعداد: {order['quantity']}\n"
                    f"مبلغ: {order['amount']}\n"
                    "وضعیت: در انتظار بررسی"
                ),
            )
        except Exception:
            logging.exception("Could not post report")

        context.user_data["state"] = "menu"

        await message.reply_text(
            "✅ رسید دریافت شد و برای بررسی مالک ارسال شد.",
            reply_markup=main_keyboard(),
        )
        return

    elif context.user_data.get("state") == "payment":
        await message.reply_text(
            "لطفاً رسید پرداخت را به صورت عکس ارسال کن."
        )


async def post_init(app):
    logging.info("Bot started successfully")


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing"
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message,
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()
