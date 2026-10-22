# bot.py
# ربات فروش DOGS و TON - نسخه کامل با python-telegram-bot v20+
# نیازمندی‌ها: pip install "python-telegram-bot[job-queue]"

import json
import os
import logging
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============================================================
# ==================  تنظیمات قابل تغییر  ====================
# ============================================================

BOT_TOKEN = "8714704830:AAGYitrRQQ0TLv2Zg-fc1gbKTyi6Jm08n-g"          # توکن ربات را اینجا قرار دهید
ADMIN_CHAT_ID = 8935601841                   # آیدی عددی مدیر (چت خصوصی)
CARD_NUMBER = "6219861856357990"         # شماره کارت برای واریز
CARD_HOLDER =  "رضازاده"

# کانال و گروه اجباری (بدون @ یا با @ – هر دو پشتیبانی می‌شود)
REQUIRED_CHANNEL = "https://t.me/BNI_MMAD"          # کانال اجباری
REQUIRED_GROUP = "https://t.me/BNI_MMAD1"              # گروه اجباری

# قیمت‌ها (تومان)
DOGS_PRICE_PER_UNIT = 12                    # قیمت هر DOGS
DOGS_MIN_ORDER = 1000                       # حداقل سفارش DOGS
TON_PRICE_PER_01 = 40000                    # قیمت هر 0.1 TON
TON_MIN_ORDER = 0.1                         # حداقل خرید TON

# مسیر فایل‌های ذخیره‌سازی
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

# ============================================================
# ==================  تعریف state ها  ========================
# ============================================================

(
    MENU,
    GET_PHONE,
    CHOOSE_PRODUCT,
    GET_AMOUNT,
    GET_WALLET,
    SHOW_PAYMENT,
    GET_RECEIPT,
    SUPPORT_MESSAGE,
    ADMIN_ACTION,
) = range(9)

# ============================================================
# ==================  توابع ذخیره‌سازی  ======================
# ============================================================

def load_json(filepath: str, default: dict | list) -> dict | list:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def save_json(filepath: str, data: dict | list) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_users() -> dict:
    return load_json(USERS_FILE, {})


def save_users(users: dict) -> None:
    save_json(USERS_FILE, users)


def get_orders() -> list:
    return load_json(ORDERS_FILE, [])


def save_orders(orders: list) -> None:
    save_json(ORDERS_FILE, orders)


def user_exists(user_id: int) -> bool:
    users = get_users()
    return str(user_id) in users


def register_user(user_id: int, phone: str, first_name: str = "") -> None:
    users = get_users()
    users[str(user_id)] = {
        "phone": phone,
        "first_name": first_name,
        "registered_at": datetime.now().isoformat(),
    }
    save_users(users)


# ============================================================
# ==================  بررسی عضویت  ===========================
# ============================================================

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت در کانال و گروه. در صورت عدم عضویت پیام هشدار ارسال می‌کند."""
    user_id = update.effective_user.id
    missing = []

    for chat_id in [REQUIRED_CHANNEL, REQUIRED_GROUP]:
        if not chat_id or chat_id == "@your_channel" or chat_id == "@your_group":
            continue  # اگر تنظیم نشده باشد، رد می‌شود
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ("member", "administrator", "creator", "restricted"):
                missing.append(chat_id)
        except Exception:
            # اگر ربات نتواند عضویت را بررسی کند (مثلاً ادمین نیست)، اجازه عبور می‌دهیم
            # برای سخت‌گیری بیشتر می‌توانید missing.append(chat_id) کنید
            logging.warning(f"Could not check membership for {chat_id}")

    if missing:
        text = "⚠️ برای استفاده از ربات ابتدا در کانال و گروه زیر عضو شوید:\n\n"
        if REQUIRED_CHANNEL in missing:
            text += f"📢 کانال: {REQUIRED_CHANNEL}\n"
        if REQUIRED_GROUP in missing:
            text += f"👥 گروه: {REQUIRED_GROUP}\n"
        text += "\nسپس /start را مجدداً ارسال کنید."
        await update.effective_message.reply_text(text)
        return False
    return True


# ============================================================
# ==================  منوها  =================================
# ============================================================

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["🛒 خرید DOGS", "💎 خرید TON"],
        ["📞 پشتیبانی"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def phone_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton("📱 ارسال شماره تلفن", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# ============================================================
# ==================  Handler ها  ============================
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نقطه ورود اصلی. اگر کاربر ثبت‌نام نشده باشد، شماره می‌گیرد؛ در غیر این صورت منو نمایش می‌دهد."""
    user = update.effective_user
    user_id = user.id

    if not await check_membership(update, context):
        return ConversationHandler.END

    if not user_exists(user_id):
        await update.message.reply_text(
            "سلام! به ربات خوش آمدید.\n\n"
            "برای شروع لطفاً شماره تلفن خود را با دکمه زیر ارسال کنید:",
            reply_markup=phone_keyboard(),
        )
        return GET_PHONE

    # کاربر قبلاً ثبت‌نام کرده – مستقیماً منو
    await update.message.reply_text(
        f"سلام {user.first_name}!\nبه منوی خرید خوش آمدید:",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت شماره تلفن از contact و ثبت کاربر."""
    contact = update.message.contact
    if not contact or contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "❌ لطفاً از دکمه «ارسال شماره تلفن» استفاده کنید.",
            reply_markup=phone_keyboard(),
        )
        return GET_PHONE

    phone = contact.phone_number
    user = update.effective_user
    register_user(user.id, phone, user.first_name or "")

    await update.message.reply_text(
        "✅ ثبت‌نام با موفقیت انجام شد!\n\nحالا می‌توانید از منوی زیر خرید کنید:",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مدیریت انتخاب‌های منو."""
    text = update.message.text
    user_id = update.effective_user.id

    if not user_exists(user_id):
        # اگر به هر دلیلی کاربر ثبت‌نام نشده باشد
        await update.message.reply_text(
            "لطفاً ابتدا شماره تلفن خود را ارسال کنید:",
            reply_markup=phone_keyboard(),
        )
        return GET_PHONE

    if text == "🛒 خرید DOGS":
        context.user_data["product"] = "DOGS"
        await update.message.reply_text(
            f"🛒 خرید DOGS\n\n"
            f"قیمت هر DOGS: {DOGS_PRICE_PER_UNIT:,} تومان\n"
            f"حداقل سفارش: {DOGS_MIN_ORDER:,} عدد\n\n"
            f"لطفاً مقدار DOGS مورد نظر را وارد کنید (عدد صحیح):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GET_AMOUNT

    elif text == "💎 خرید TON":
        context.user_data["product"] = "TON"
        await update.message.reply_text(
            f"💎 خرید TON\n\n"
            f"قیمت هر 0.1 TON: {TON_PRICE_PER_01:,} تومان\n"
            f"حداقل خرید: {TON_MIN_ORDER} TON\n\n"
            f"لطفاً مقدار TON مورد نظر را وارد کنید (مثلاً 0.1 یا 0.5):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GET_AMOUNT

    elif text == "📞 پشتیبانی":
        await update.message.reply_text(
            "📞 لطفاً پیام خود را برای پشتیبانی بنویسید:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SUPPORT_MESSAGE

    else:
        await update.message.reply_text(
            "لطفاً از دکمه‌های منو استفاده کنید.",
            reply_markup=main_menu_keyboard(),
        )
        return MENU


async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت مقدار محصول و اعتبارسنجی."""
    text = update.message.text.strip()
    product = context.user_data.get("product")

    try:
        amount = float(text) if product == "TON" else int(text)
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return GET_AMOUNT

    if product == "DOGS":
        if amount < DOGS_MIN_ORDER:
            await update.message.reply_text(
                f"❌ حداقل سفارش DOGS برابر {DOGS_MIN_ORDER:,} عدد است. لطفاً مقدار بیشتری وارد کنید:"
            )
            return GET_AMOUNT
        total_price = amount * DOGS_PRICE_PER_UNIT
        context.user_data["amount"] = amount
        context.user_data["total_price"] = total_price
        await update.message.reply_text(
            f"✅ مقدار: {amount:,} DOGS\n"
            f"💰 مبلغ نهایی: {total_price:,} تومان\n\n"
            f"لطفاً آدرس کیف پول مقصد (TON Wallet) را وارد کنید:"
        )
        return GET_WALLET

    else:  # TON
        if amount < TON_MIN_ORDER:
            await update.message.reply_text(
                f"❌ حداقل خرید TON برابر {TON_MIN_ORDER} است. لطفاً مقدار بیشتری وارد کنید:"
            )
            return GET_AMOUNT
        total_price = int(amount / 0.1 * TON_PRICE_PER_01)
        context.user_data["amount"] = amount
        context.user_data["total_price"] = total_price
        await update.message.reply_text(
            f"✅ مقدار: {amount} TON\n"
            f"💰 مبلغ نهایی: {total_price:,} تومان\n\n"
            f"لطفاً آدرس کیف پول مقصد (TON Wallet) را وارد کنید:"
        )
        return GET_WALLET


async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت آدرس کیف پول و نمایش اطلاعات پرداخت."""
    wallet = update.message.text.strip()
    if len(wallet) < 10:
        await update.message.reply_text("❌ آدرس کیف پول معتبر نیست. لطفاً دوباره وارد کنید:")
        return GET_WALLET

    context.user_data["wallet"] = wallet
    product = context.user_data["product"]
    amount = context.user_data["amount"]
    total_price = context.user_data["total_price"]

    await update.message.reply_text(
        f"📋 **جزئیات سفارش**\n\n"
        f"محصول: {product}\n"
        f"مقدار: {amount}\n"
        f"آدرس کیف پول: `{wallet}`\n"
        f"💰 مبلغ قابل پرداخت: **{total_price:,} تومان**\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"👤 به نام: {CARD_HOLDER}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"لطفاً مبلغ را واریز کنید و **عکس رسید پرداخت** را ارسال نمایید:",
        parse_mode="Markdown",
    )
    return GET_RECEIPT


async def get_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت عکس رسید و ارسال به مدیر."""
    if not update.message.photo:
        await update.message.reply_text("❌ لطفاً عکس رسید پرداخت را ارسال کنید.")
        return GET_RECEIPT

    user = update.effective_user
    product = context.user_data["product"]
    amount = context.user_data["amount"]
    total_price = context.user_data["total_price"]
    wallet = context.user_data["wallet"]
    photo = update.message.photo[-1]  # بالاترین کیفیت

    order_id = f"ORD-{int(datetime.now().timestamp())}-{user.id}"
    order_data = {
        "order_id": order_id,
        "user_id": user.id,
        "user_name": user.first_name or "",
        "product": product,
        "amount": amount,
        "total_price": total_price,
        "wallet": wallet,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    orders = get_orders()
    orders.append(order_data)
    save_orders(orders)

    # ذخیره order_id برای استفاده در callback
    context.user_data["current_order_id"] = order_id

    # ارسال به مدیر
    admin_text = (
        f"🔔 **سفارش جدید**\n\n"
        f"🆔 {order_id}\n"
        f"👤 کاربر: {user.first_name} (ID: `{user.id}`)\n"
        f"📦 محصول: {product}\n"
        f"🔢 مقدار: {amount}\n"
        f"💰 مبلغ: {total_price:,} تومان\n"
        f"👛 کیف پول: `{wallet}`\n\n"
        f"وضعیت: ⏳ در انتظار تأیید"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{order_id}"),
        ]
    ])

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo.file_id,
            caption=admin_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except Exception as e:
        logging.error(f"Failed to send order to admin: {e}")
        await update.message.reply_text(
            "⚠️ خطا در ارسال سفارش به مدیر. لطفاً بعداً تلاش کنید یا با پشتیبانی تماس بگیرید."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ رسید شما دریافت شد و برای بررسی به مدیر ارسال گردید.\n"
        "پس از تأیید، محصول به کیف پول شما واریز خواهد شد.\n\n"
        "از خرید شما سپاسگزاریم! 🙏",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ارسال پیام پشتیبانی به مدیر."""
    user = update.effective_user
    text = update.message.text

    admin_text = (
        f"📞 **پیام پشتیبانی**\n\n"
        f"👤 {user.first_name} (ID: `{user.id}`)\n"
        f"📝 پیام:\n{text}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            "✅ پیام شما برای پشتیبانی ارسال شد. به زودی پاسخ داده می‌شود.",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await update.message.reply_text(
            "⚠️ خطا در ارسال پیام. لطفاً بعداً تلاش کنید.",
            reply_markup=main_menu_keyboard(),
        )
    return MENU


# ============================================================
# ==================  تأیید/رد مدیر  =========================
# ============================================================

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش دکمه‌های تأیید/رد توسط مدیر."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("approve_") and not data.startswith("reject_"):
        return

    action, order_id = data.split("_", 1)
    orders = get_orders()
    target_order = None
    for o in orders:
        if o["order_id"] == order_id:
            target_order = o
            break

    if not target_order:
        await query.edit_message_caption(
            caption="❌ سفارش یافت نشد.",
            parse_mode="Markdown",
        )
        return

    if target_order["status"] != "pending":
        await query.edit_message_caption(
            caption=f"⚠️ این سفارش قبلاً پردازش شده است (وضعیت: {target_order['status']}).",
            parse_mode="Markdown",
        )
        return

    if action == "approve":
        target_order["status"] = "approved"
        target_order["processed_at"] = datetime.now().isoformat()
        save_orders(orders)

        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ **تأیید شد**",
            parse_mode="Markdown",
        )

        # اطلاع به کاربر
        try:
            await context.bot.send_message(
                chat_id=target_order["user_id"],
                text=(
                    f"✅ **سفارش شما تأیید شد!**\n\n"
                    f"🆔 {order_id}\n"
                    f"📦 {target_order['product']} - {target_order['amount']}\n"
                    f"محصول به کیف پول شما ارسال خواهد شد.\n\n"
                    f"با تشکر از خرید شما! 🙏"
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception as e:
            logging.error(f"Failed to notify user {target_order['user_id']}: {e}")

    else:  # reject
        target_order["status"] = "rejected"
        target_order["processed_at"] = datetime.now().isoformat()
        save_orders(orders)

        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ **رد شد**",
            parse_mode="Markdown",
        )

        try:
            await context.bot.send_message(
                chat_id=target_order["user_id"],
                text=(
                    f"❌ **سفارش شما رد شد.**\n\n"
                    f"🆔 {order_id}\n"
                    f"در صورت نیاز با پشتیبانی تماس بگیرید."
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception as e:
            logging.error(f"Failed to notify user {target_order['user_id']}: {e}")


# ============================================================
# ==================  لغو و پایان  ===========================
# ============================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """لغو عملیات جاری و بازگشت به منو."""
    context.user_data.clear()
    await update.message.reply_text(
        "عملیات لغو شد.",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(f"Update {update} caused error: {context.error}")


# ============================================================
# ==================  main  ==================================
# ============================================================

def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # ConversationHandler اصلی
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            GET_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
            ],
            MENU: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    menu,
                ),
            ],
            GET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount),
            ],
            GET_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet),
            ],
            GET_RECEIPT: [
                MessageHandler(filters.PHOTO, get_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_receipt),
            ],
            SUPPORT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, support_message),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(approve_|reject_)"))

    application.add_error_handler(error_handler)

    print("🤖 ربات در حال اجراست...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
