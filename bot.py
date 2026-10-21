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

# اطلاعات عضویت
CHANNEL_ID = "@BNI_MMAD"
CHANNEL_LINK = "https://t.me/BNI_MMAD"

# این دو مقدار را با اطلاعات واقعی گروهت تنظیم کن
GROUP_ID = os.getenv("GROUP_ID", "@BNI_MMAD1")
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/BNI_MMAD1")

# اطلاعات پرداخت
CARD = "6219861856357990"
CARD_NAME = "رضازاده"

# قیمت‌ها به تومان
STAR_PRICE = 4700
DOGS_PRICE = 12

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
            return json.loads(
                DATA_FILE.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            logging.exception("Could not load orders")
    return {}


def save_orders(orders):
    DATA_FILE.write_text(
        json.dumps(
            orders,
            ensure_ascii=False,
            indent=2,
        ),
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


def membership_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 عضویت در چنل",
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
                "🔄 بررسی مجدد",
                callback_data="check_members",
            )
        ],
    ])


def payment_text(amount):
    return (
        "💳 اطلاعات پرداخت\n\n"
        f"شماره کارت:\n{CARD}\n\n"
        f"به نام: {CARD_NAME}\n\n"
        f"مبلغ قابل پرداخت: {amount:,} تومان\n\n"
        "پس از پرداخت، تصویر رسید را به صورت عکس همین‌جا ارسال کن."
    )


async def check_one_membership(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=chat_id,
            user_id=user_id,
        )
        return member.status not in ("left", "kicked")

    except Exception:
        logging.exception(
            "Membership check failed: chat=%s user=%s",
            chat_id,
            user_id,
        )
        return False


async def check_membership(bot, user_id):
    channel_ok = await check_one_membership(
        bot,
        CHANNEL_ID,
        user_id,
    )

    group_ok = await check_one_membership(
        bot,
        GROUP_ID,
        user_id,
    )

    return channel_ok and group_ok


async def ask_membership(update, context):
    await update.message.reply_text(
        "برای استفاده از ربات، ابتدا در چنل و گروه عضو شو "
        "و سپس روی «بررسی مجدد» بزن.",
        reply_markup=membership_keyboard(),
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()
    context.user_data["state"] = "phone"

    keyboard = ReplyKeyboardMarkup(
        [[
            KeyboardButton(
                "📱 تأیید شماره ایران",
                request_contact=True,
            )
        ]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await update.message.reply_text(
        "سلام! 👋\n\n"
        "برای شروع، شماره تلفن ایران خودت را با دکمه زیر ارسال کن.\n"
        "شماره باید با +98 شروع شود.",
        reply_markup=keyboard,
    )


async def handle_contact(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    contact = update.message.contact

    if contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "❌ لطفاً شماره خودت را ارسال کن."
        )
        return

    phone = (
        contact.phone_number
        .replace(" ", "")
        .replace("-", "")
    )

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
        await ask_membership(update, context)
        return

    context.user_data["state"] = "menu"

    await update.message.reply_text(
        "✅ شماره ثبت شد!\n"
        "عضویت تأیید شد؛ به منوی اصلی خوش آمدی.",
        reply_markup=main_keyboard(),
    )


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if query.data == "check_members":
        if await check_membership(
            context.bot,
            query.from_user.id,
        ):
            context.user_data["state"] = "menu"

            await query.message.reply_text(
                "✅ عضویت در چنل و گروه تأیید شد.",
                reply_markup=main_keyboard(),
            )
        else:
            await query.message.reply_text(
                "❌ عضویت در چنل یا گروه هنوز تأیید نشده است.",
                reply_markup=membership_keyboard(),
            )
        return

    if query.data.startswith(("approve:", "reject:")):
        if query.from_user.id != OWNER_ID:
            await query.answer(
                "⛔ دسترسی ندارید.",
                show_alert=True,
            )
            return

        action, order_id = query.data.split(":", 1)
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
        else:
            order["status"] = "rejected"
            result = (
                "❌ رسید پرداخت شما تأیید نشد.\n"
                "لطفاً با پشتیبانی تماس بگیر."
            )

        save_orders(orders)

        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=result,
            )
        except Exception:
            logging.exception("Could not notify user")

        await query.message.reply_text(
            "✅ وضعیت سفارش ثبت شد."
        )
        return

    if query.data.startswith("reply:"):
        if query.from_user.id != OWNER_ID:
            await query.answer(
                "⛔ دسترسی ندارید.",
                show_alert=True,
            )
            return

        target_id = int(query.data.split(":", 1)[1])
        context.user_data["reply_to"] = target_id
        context.user_data["state"] = "owner_reply"

        await query.message.reply_text(
            "پیام پاسخ را ارسال کن."
        )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.message
    user = update.effective_user
    text = message.text or ""
    state = context.user_data.get("state")

    if message.contact:
        await handle_contact(update, context)
        return

    # پاسخ مدیر به کاربر
    if (
        user.id == OWNER_ID
        and context.user_data.get("reply_to")
    ):
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

        context.user_data["state"] = "menu"
        return

    if state == "phone":
        await message.reply_text(
            "برای ادامه، شماره خودت را با دکمه اشتراک‌گذاری شماره بفرست."
        )
        return

    # دریافت تعداد استارز یا داگز
    if state == "quantity":
        digits = str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
            "01234567890123456789",
        )

        try:
            quantity = int(text.translate(digits).strip())
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

            amount = quantity * DOGS_PRICE
            context.user_data["quantity"] = quantity
            context.user_data["amount"] = amount
            context.user_data["state"] = "destination"

            await message.reply_text(
                f"🐶 تعداد داگز: {quantity:,}\n"
                f"💰 قیمت هر داگز: {DOGS_PRICE:,} تومان\n"
                f"💵 مبلغ کل: {amount:,} تومان\n\n"
                "یوزرنیم اکانت مقصد را وارد کن."
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
            context.user_data["state"] = "destination"

            await message.reply_text(
                f"⭐ تعداد استارز: {quantity:,}\n"
                f"💰 قیمت هر استارز: {STAR_PRICE:,} تومان\n"
                f"💵 مبلغ کل: {amount:,} تومان\n\n"
                "یوزرنیم اکانت مقصد را وارد کن."
            )
            return

    # دریافت یوزرنیم مقصد برای داگز، استارز و گیفت
    if state == "destination":
        destination = text.strip()

        if not destination:
            await message.reply_text(
                "لطفاً یوزرنیم اکانت مقصد را وارد کن."
            )
            return

        context.user_data["destination"] = destination
        context.user_data["state"] = "payment"

        await message.reply_text(
            "✅ مقصد سفارش ثبت شد.\n\n"
            + payment_text(context.user_data["amount"])
        )
        return

    # منوی محصولات
    if text == "🛍 منو محصولات سفارش":
        context.user_data["state"] = "menu"
        await message.reply_text(
            "یکی از محصولات را انتخاب کن:",
            reply_markup=product_keyboard(),
        )
        return

    if text == "🐶 داگز اولترا":
        context.user_data.update({
            "product": "داگز اولترا",
            "quantity": None,
            "amount": None,
            "destination": None,
            "post_link": None,
            "state": "quantity",
        })
        await message.reply_text(
            "تعداد داگز را وارد کن. حداقل ۱۰۰۰."
        )
        return

    if text == "⭐ ریکشن استارزی":
        context.user_data.update({
            "product": "ری‌اکشن استارزی",
            "quantity": None,
            "amount": None,
            "destination": None,
            "post_link": None,
            "state": "quantity",
        })
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

    # انتخاب گیفت و سپس دریافت یوزرنیم
    if text in GIFT_NAMES:
        gift = GIFT_NAMES[text]
        amount = GIFTS[gift]

        context.user_data.update({
            "product": gift,
            "quantity": 1,
            "amount": amount,
            "destination": None,
            "post_link": None,
            "state": "destination",
        })

        await message.reply_text(
            f"🎁 گیفت انتخاب‌شده: {gift}\n"
            f"💰 قیمت: {amount:,} تومان\n\n"
            "حالا یوزرنیم اکانتی که می‌خواهی گیفت به آن ارسال شود را وارد کن."
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
                    f"یوزرنیم مقصد: {order['destination'] or '-'}\n"
                    "وضعیت: در انتظار بررسی"
                ),
                reply_markup=keyboard,
            )
        except Exception:
            logging.exception("Could not send order to owner")
            await message.reply_text(
                "❌ ارسال سفارش برای مدیر ناموفق بود."
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
            "✅ رسید دریافت شد و برای بررسی مدیر ارسال شد.",
            reply_markup=main_keyboard(),
        )
        return


async def post_init(app):
    logging.info("Bot started successfully")


def main():
    if not TOKEN:
        raise RuntimeError(
            "متغیر محیطی BOT_TOKEN تنظیم نشده است."
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
