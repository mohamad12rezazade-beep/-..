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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "8935601841"))

REPORT_CHANNEL = "@BNI_MMAD"
CHANNEL_LINK = "https://t.me/BNI_MMAD"

CARD = "6219861856357990"
CARD_NAME = "رضازاده"

STAR_PRICE = 4700

DATA_FILE = Path("orders.json")

GIFTS = {
    "تدی": 60000,
    "قلب": 60000,
    "گل": 110000,
    "موشک": 225000,
    "الماس": 460000,
}

GIFT_NAMES = {
    "🧸 تدی": "تدی",
    "❤️ قلب": "قلب",
    "🌹 گل": "گل",
    "🚀 موشک": "موشک",
    "💎 الماس": "الماس",
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
        "پس از پرداخت، تصویر رسید را همین‌جا ارسال کن."
    )


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
            await query.answer("⛔ دسترسی ندارید.", show_alert=True)
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
            result = "✅ پرداخت شما تأیید شد."

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
                "لطفاً با پشتیبانی تماس بگیر."
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
            await query.answer("⛔ دسترسی ندارید.", show_alert=True)
            return

        target_id = int(query.data.split(":", 1)[1])
        context.user_data["reply_to"] = target_id
        context.user_data["state"] = "owner_reply"

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

    state = context.user_data.get("state")

    if state == "phone":
        await message.reply_text(
            "برای ادامه، شماره خودت را با دکمه اشتراک‌گذاری شماره بفرست."
        )
        return

    # دریافت تعداد محصولات
    if state == "quantity":
        try:
            normalized_text = text.translate(
                str.maketrans(
                    "۰۱۲۳۴۵۶۷۸۹",
                    "0123456789",
                )
            )
            normalized_text = normalized_text.translate(
                str.maketrans(
                    "٠١٢٣٤٥٦٧٨٩",
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

            context.user_data["quantity"] = quantity
            context.user_data["amount"] = quantity * 12
            context.user_data["state"] = "destination"

            await message.reply_text(
                f"🐶 تعداد داگز: {quantity:,}\n"
                f"💰 مبلغ: {quantity * 12:,} تومان\n\n"
                "یوزرنیم اکانتی که داگز به آن واریز می‌شود را وارد کن."
            )
            return

        if product == "ری‌اکشن استارزی":
            if not 1 <= quantity <= 1000:
                await message.reply_text(
                    "تعداد استارز باید بین ۱ تا ۱۰۰۰ باشد."
                )
                return

            amount = quantity * STAR_PRICE

            context.user_data["quantity"] = quantity
            context.user_data["amount"] = amount
            context.user_data["state"] = "post_link"

            await message.reply_text(
                f"⭐ تعداد استارز: {quantity:,}\n"
                f"💰 قیمت هر استارز: {STAR_PRICE:,} تومان\n"
                f"💵 مبلغ کل: {amount:,} تومان\n\n"
                "حالا لینک پست تلگرام را ارسال کن."
            )
            return

    # دریافت مقصد داگز
    if state == "destination":
        if not text.strip():
            await message.reply_text(
                "لطفاً یوزرنیم مقصد را وارد کن."
            )
            return

        context.user_data["destination"] = text.strip()
        context.user_data["state"] = "payment"

        await message.reply_text(
            payment_text(context.user_data["amount"])
        )
        return

    # دریافت لینک پست استارز
    if state == "post_link":
        if not text.startswith(("https://t.me/", "http://t.me/")):
            await message.reply_text(
                "❌ لطفاً لینک معتبر پست تلگرام را ارسال کن."
            )
            return

        context.user_data["post_link"] = text
        context.user_data["state"] = "payment"

        await message.reply_text(
            "⭐ سفارش استارز آماده پرداخت است.\n\n"
            + payment_text(context.user_data["amount"])
        )
        return

    # انتخاب منو و محصولات
    if text == "🛍 منو محصولات سفارش":
        context.user_data["state"] = "menu"

        await message.reply_text(
            "یکی از محصولات را انتخاب کن:",
            reply_markup=product_keyboard(),
        )
        return

    if text == "🐶 داگز اولترا":
        context.user_data["product"] = "داگز اولترا"
        context.user_data["quantity"] = None
        context.user_data["amount"] = None
        context.user_data["destination"] = None
        context.user_data["post_link"] = None
        context.user_data["state"] = "quantity"

        await message.reply_text(
            "تعداد داگز را وارد کن. حداقل ۱۰۰۰."
        )
        return

    if text == "⭐ ریکشن استارزی":
        context.user_data["product"] = "ری‌اکشن استارزی"
        context.user_data["quantity"] = None
        context.user_data["amount"] = None
        context.user_data["destination"] = None
        context.user_data["post_link"] = None
        context.user_data["state"] = "quantity"

        await message.reply_text(
            f"تعداد استارز را وارد کن (۱ تا ۱۰۰۰).\n"
            f"قیمت هر استارز: {STAR_PRICE:,} تومان"
        )
        return

    if text == "🎁 گیفت":
        context.user_data["state"] = "gift_menu"

        await message.reply_text(
            "نوع گیفت را انتخاب کن:",
            reply_markup=gift_keyboard(),
        )
        return

    # انتخاب گیفت با تطبیق دقیق نام دکمه
    if text in GIFT_NAMES:
        gift = GIFT_NAMES[text]
        amount = GIFTS[gift]

        context.user_data["product"] = gift
        context.user_data["quantity"] = 1
        context.user_data["amount"] = amount
        context.user_data["destination"] = None
        context.user_data["post_link"] = None
        context.user_data["state"] = "payment"

        await message.reply_text(
            f"🎁 گیفت انتخاب‌شده: {gift}\n\n"
            + payment_text(amount)
        )
        return

    # پشتیبانی
    if text == "📞 پشتیبانی":
        context.user_data["state"] = "support"

        await message.reply_text(
            "پیامت را ارسال کن تا برای پشتیبانی فرستاده شود."
        )
        return

    if state == "support":
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
        return

    if text == "📢 چنل گزارش سفارش‌ها":
        await message.reply_text(CHANNEL_LINK)
        return

    if text == "🔙 بازگشت به منو":
        context.user_data["state"] = "menu"

        await message.reply_text(
            "منوی اصلی:",
            reply_markup=main_keyboard(),
        )
        return

    if text == "🔙 بازگشت به محصولات":
        context.user_data["state"] = "menu"

        await message.reply_text(
            "منوی محصولات:",
            reply_markup=product_keyboard(),
        )
        return

    # دریافت رسید پرداخت
    if state == "payment":
        if not message.photo:
            await message.reply_text(
                "لطفاً رسید پرداخت را به صورت عکس ارسال کن."
            )
            return

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
                    f"مبلغ: {order['amount']:,} تومان\n"
                    f"مقصد: {order['destination'] or '-'}\n"
                    f"لینک پست: {order['post_link'] or '-'}\n"
                    "وضعیت: در انتظار بررسی"
                ),
                reply_markup=keyboard,
            )
        except Exception:
            logging.exception("Could not send order to owner")

            await message.reply_text(
                "❌ ارسال سفارش برای مالک ناموفق بود. "
                "لطفاً بعداً دوباره تلاش کن."
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
                    f"مبلغ: {order['amount']:,} تومان\n"
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
