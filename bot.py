# bot.py
# ربات فروش DOGS و TON - نسخه اصلاح‌شده با مدیریت خطای بررسی عضویت
# نیازمندی‌ها: pip install "python-telegram-bot[job-queue]"

import json
import os
import logging
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
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

BOT_TOKEN = "8714704830:AAGYitrRQQ0TLv2Zg-fc1gbKTyi6Jm08n-g"          # ← توکن ربات را اینجا قرار دهید
ADMIN_CHAT_ID = 8935601841                  # ← آیدی عددی مدیر (چت خصوصی)
CARD_NUMBER = "6037-XXXX-XXXX-XXXX"         # شماره کارت
CARD_HOLDER = "رضازاده"

# --- کانال و گروه اجباری ---
# چون لینک‌ها عمومی هستند، از یوزرنیم استفاده می‌کنیم.
# ربات حتماً باید در کانال و گروه «ادمین» باشد تا بتواند عضویت را بررسی کند.
REQUIRED_CHANNEL = "@BNI_MMAD"              # کانال گزارش سفارش‌ها
REQUIRED_GROUP = "@BNI_MMAD1"               # گروه

# قیمت‌ها (تومان)
DOGS_PRICE_PER_UNIT = 12
DOGS_MIN_ORDER = 1000
TON_PRICE_PER_01 = 40000
TON_MIN_ORDER = 0.1

# مسیر فایل‌های ذخیره‌سازی
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

# ============================================================
# ==================  تعریف state ها  ========================
# ============================================================

(
    MENU,
    GET_PHONE,
    GET_AMOUNT,
    GET_WALLET,
    GET_RECEIPT,
    SUPPORT_MESSAGE,
) = range(6)

# ============================================================
# ==================  توابع ذخیره‌سازی  ======================
# ============================================================

def load_json(filepath: str, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def save_json(filepath: str, data) -> None:
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
    return str(user_id) in get_users()


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
    """بررسی عضویت در کانال و گروه. با مدیریت خطا."""
    user_id = update.effective_user.id
    missing = []
    technical_error = False

    for chat_id in [REQUIRED_CHANNEL, REQUIRED_GROUP]:
        if not chat_id or chat_id in ("@your_channel", "@your_group"):
            continue
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ("member", "administrator", "creator", "restricted"):
                missing.append(chat_id)
        except Exception as e:
            logging.error(f"Membership check failed for {chat_id}: {e}")
            technical_error = True

    if technical_error and not missing:
        # خطای فنی رخ داده اما کاربر لزوماً غیرعضو نیست → اجازه عبور می‌دهیم
        await update.effective_message.reply_text(
            "⚠️ بررسی عضویت با خطا مواجه شد (احتمالاً ربات در کانال/گروه ادمین نیست).\n"
            "ادمین ربات را از این موضوع مطلع کنید."
        )
        return True

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
# ==================  کیبوردها  ==============================
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

    await update.message.reply_text(
        f"سلام {user.first_name}!\nبه منوی خرید خوش آمدید:",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    if not contact or contact.user_id != update.effective_user.id:
        await update.message.reply_text(
            "❌ لطفاً از دکمه «ارسال شماره تلفن» استفاده کنید.",
            reply_markup=phone_keyboard(),
        )
        return GET_PHONE

    user = update.effective_user
    register_user(user.id, contact.phone_number, user.first_name or "")

    await update.message.reply_text(
        "✅ ثبت‌نام با موفقیت انجام شد!\n\nاز منوی زیر خرید کنید:",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id

    if not user_exists(user_id):
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
            f"مقدار DOGS را وارد کنید:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GET_AMOUNT

    elif text == "💎 خرید TON":
        context.user_data["product"] = "TON"
        await update.message.reply_text(
            f"💎 خرید TON\n\n"
            f"قیمت هر 0.1 TON: {TON_PRICE_PER_01:,} تومان\n"
            f"حداقل خرید: {TON_MIN_ORDER} TON\n\n"
            f"مقدار TON را وارد کنید (مثلاً 0.1):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GET_AMOUNT

    elif text == "📞 پشتیبانی":
        await update.message.reply_text(
            "📞 پیام خود را برای پشتیبانی بنویسید:",
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
                f"❌ حداقل سفارش DOGS برابر {DOGS_MIN_ORDER:,} است."
            )
            return GET_AMOUNT
        total_price = amount * DOGS_PRICE_PER_UNIT
    else:
        if amount < TON_MIN_ORDER:
            await update.message.reply_text(
                f"❌ حداقل خرید TON برابر {TON_MIN_ORDER} است."
            )
            return GET_AMOUNT
        total_price = int(amount / 0.1 * TON_PRICE_PER_01)

    context.user_data["amount"] = amount
    context.user_data["total_price"] = total_price

    await update.message.reply_text(
        f"✅ مقدار: {amount}\n"
        f"💰 مبلغ نهایی: {total_price:,} تومان\n\n"
        f"آدرس کیف پول مقصد (TON Wallet) را وارد کنید:"
    )
    return GET_WALLET


async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wallet = update.message.text.strip()
    if len(wallet) < 10:
        await update.message.reply_text("❌ آدرس معتبر نیست. دوباره وارد کنید:")
        return GET_WALLET

    context.user_data["wallet"] = wallet
    product = context.user_data["product"]
    amount = context.user_data["amount"]
    total_price = context.user_data["total_price"]

    await update.message.reply_text(
        f"📋 **جزئیات سفارش**\n\n"
        f"محصول: {product}\n"
        f"مقدار: {amount}\n"
        f"کیف پول: `{wallet}`\n"
        f"💰 مبلغ قابل پرداخت: **{total_price:,} تومان**\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"👤 به نام: {CARD_HOLDER}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"پس از واریز، **عکس رسید** را ارسال کنید:",
        parse_mode="Markdown",
    )
    return GET_RECEIPT


async def get_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("❌ لطفاً عکس رسید پرداخت را ارسال کنید.")
        return GET_RECEIPT

    user = update.effective_user
    product = context.user_data["product"]
    amount = context.user_data["amount"]
    total_price = context.user_data["total_price"]
    wallet = context.user_data["wallet"]
    photo = update.message.photo[-1]

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
    context.user_data["current_order_id"] = order_id

    admin_text = (
        f"🔔 **سفارش جدید**\n\n"
        f"🆔 {order_id}\n"
        f"👤 {user.first_name} (ID: `{user.id}`)\n"
        f"📦 {product}\n"
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

    # ارسال سفارش به کانال گزارش سفارش‌ها
    try:
        await context.bot.send_photo(
            chat_id=REQUIRED_CHANNEL,
            photo=photo.file_id,
            caption=admin_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except Exception as e:
        logging.error(f"Failed to send order to channel: {e}")
        # اگر ارسال به کانال نشد، به مدیر خصوصی بفرست
        try:
            await context.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=photo.file_id,
                caption=admin_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as e2:
            logging.error(f"Failed to send order to admin: {e2}")
            await update.message.reply_text(
                "⚠️ خطا در ارسال سفارش. لطفاً بعداً تلاش کنید."
            )
            return ConversationHandler.END

    await update.message.reply_text(
        "✅ رسید شما دریافت شد و برای بررسی ارسال گردید.\n"
        "پس از تأیید، محصول به کیف پول شما واریز می‌شود.\n\n"
        "از خرید شما سپاسگزاریم! 🙏",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
            "✅ پیام شما برای پشتیبانی ارسال شد.",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await update.message.reply_text(
            "⚠️ خطا در ارسال پیام. بعداً تلاش کنید.",
            reply_markup=main_menu_keyboard(),
        )
    return MENU


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    if not (data.startswith("approve_") or data.startswith("reject_")):
        return

    action, order_id = data.split("_", 1)
    orders = get_orders()
    target_order = next((o for o in orders if o["order_id"] == order_id), None)

    if not target_order:
        await query.edit_message_caption(caption="❌ سفارش یافت نشد.", parse_mode="Markdown")
        return

    if target_order["status"] != "pending":
        await query.edit_message_caption(
            caption=f"⚠️ این سفارش قبلاً پردازش شده است ({target_order['status']}).",
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
        try:
            await context.bot.send_message(
                chat_id=target_order["user_id"],
                text=(
                    f"✅ **سفارش شما تأیید شد!**\n\n"
                    f"🆔 {order_id}\n"
                    f"📦 {target_order['product']} - {target_order['amount']}\n"
                    f"محصول به کیف پول شما ارسال خواهد شد.\n\nبا تشکر 🙏"
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception as e:
            logging.error(f"Notify user failed: {e}")
    else:
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
                    f"🆔 {order_id}\nدر صورت نیاز با پشتیبانی تماس بگیرید."
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception as e:
            logging.error(f"Notify user failed: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu)],
            GET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            GET_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
            GET_RECEIPT: [
                MessageHandler(filters.PHOTO, get_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_receipt),
            ],
            SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_message)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(
        CallbackQueryHandler(admin_callback, pattern="^(approve_|reject_)")
    )
    application.add_error_handler(error_handler)

    print("🤖 ربات در حال اجراست...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
