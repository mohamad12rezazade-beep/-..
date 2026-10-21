import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
import os

# ================== تنظیمات (از Secrets گیت‌هاب خونده میشه) ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8935601841))
CHANNEL_ID = "@BNI_MMAD"
GROUP_ID = "@BNI_MMAD1"

CARD_NUMBER = "6219861856357990"
CARD_OWNER = "رضازاده"
PRICE_PER_STAR = 100
PRICE_PER_DUGES = 12000

GIFTS = {
    "🧸 تدی - ۶۰,۰۰۰ تومان": 60000,
    "❤️ قلب - ۶۰,۰۰۰ تومان": 60000,
    "🌹 گل - ۱۱۰,۰۰۰ تومان": 110000,
    "🚀 موشک - ۲۲۵,۰۰۰ تومان": 225000,
    "💎 الماس - ۴۶۰,۰۰۰ تومان": 460000,
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است")

bot = telebot.TeleBot(BOT_TOKEN)

# ================== حافظه موقت (با هر بار اجرا پاک میشه!) ==================
# ⚠️ هشدار: روی GitHub Actions دیتابیس دائمی وجود نداره
user_state = {}      # uid -> dict (وضعیت فعلی کاربر)
users_verified = {}  # uid -> bool (شماره تایید شده یا نه)
orders = []          # لیست سفارش‌ها (موقت)

# ================== کیبوردها ==================
def kb_main():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🛒 منو محصولات سفارش", "🆘 پشتیبانی")
    m.row("📢 چنل گزارش سفارش‌ها")
    return m

def kb_products():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("⭐ ریکشن استارزی", "🎁 گیفت")
    m.row("🐶 داگز اولترا", "🔙 بازگشت")
    return m

def kb_gifts():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🧸 تدی - ۶۰,۰۰۰ تومان", "❤️ قلب - ۶۰,۰۰۰ تومان")
    m.row("🌹 گل - ۱۱۰,۰۰۰ تومان", "🚀 موشک - ۲۲۵,۰۰۰ تومان")
    m.row("💎 الماس - ۴۶۰,۰۰۰ تومان", "🔙 بازگشت")
    return m

def kb_phone():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    m.add(types.KeyboardButton("📱 ارسال شماره من", request_contact=True))
    return m

def kb_join():
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/BNI_MMAD"))
    m.add(types.InlineKeyboardButton("💬 عضویت در گپ", url="https://t.me/BNI_MMAD1"))
    m.add(types.InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_member"))
    return m

def kb_admin_approve(oid, uid):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{oid}_{uid}"))
    m.add(types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{oid}_{uid}"))
    return m

# ================== بررسی عضویت ==================
def is_member(uid):
    try:
        st_ch = bot.get_chat_member(CHANNEL_ID, uid).status
        st_gp = bot.get_chat_member(GROUP_ID, uid).status
        ok = ["member", "administrator", "creator"]
        return st_ch in ok and st_gp in ok
    except ApiTelegramException:
        return False

# ================== /start ==================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    if not users_verified.get(uid):
        bot.send_message(uid,
            "👋 خوش آمدی!\nبرای شروع، شماره تلگرام خودت را با دکمه زیر ارسال کن.\n"
            "⚠️ فقط شماره ایران (+98) پذیرفته می‌شود.",
            reply_markup=kb_phone())
        return
    check_join_and_menu(message)

def check_join_and_menu(message):
    uid = message.from_user.id
    if not is_member(uid):
        bot.send_message(uid,
            "❌ برای استفاده از ربات، ابتدا در کانال و گپ زیر عضو شو، سپس دکمه بررسی را بزن:",
            reply_markup=kb_join())
        return
    bot.send_message(uid, "🏠 منوی اصلی:", reply_markup=kb_main())

# ================== دریافت شماره ==================
@bot.message_handler(content_types=['contact'])
def get_contact(message):
    uid = message.from_user.id
    if message.contact.user_id != uid:
        bot.send_message(uid, "❌ لطفاً شماره خودت را ارسال کن.")
        return
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    if not phone.startswith("+98"):
        bot.send_message(uid, "❌ فقط شماره ایران (+98) پذیرفته می‌شود. دوباره تلاش کن.",
                         reply_markup=kb_phone())
        return
    users_verified[uid] = True
    bot.send_message(uid, "✅ شماره تأیید شد.", reply_markup=types.ReplyKeyboardRemove())
    check_join_and_menu(message)

# ================== بررسی عضویت با دکمه ==================
@bot.callback_query_handler(func=lambda c: c.data == "check_member")
def cb_check_member(call):
    if is_member(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تأیید شد")
        bot.edit_message_text("✅ عضویت تأیید شد.", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🏠 منوی اصلی:", reply_markup=kb_main())
    else:
        bot.answer_callback_query(call.id, "❌ هنوز عضو نشدی!", show_alert=True)

# ================== منوها ==================
@bot.message_handler(func=lambda m: m.text == "🛒 منو محصولات سفارش")
def menu_products(message):
    bot.send_message(message.chat.id, "محصول را انتخاب کن:", reply_markup=kb_products())

@bot.message_handler(func=lambda m: m.text == "🔙 بازگشت")
def back_main(message):
    user_state.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🏠 منوی اصلی:", reply_markup=kb_main())

@bot.message_handler(func=lambda m: m.text == "📢 چنل گزارش سفارش‌ها")
def menu_report(message):
    bot.send_message(message.chat.id, "📢 چنل گزارش: https://t.me/BNI_MMAD")

# ================== داگز اولترا ==================
@bot.message_handler(func=lambda m: m.text == "🐶 داگز اولترا")
def duges_start(message):
    uid = message.from_user.id
    user_state[uid] = {"type": "duges", "step": "amount"}
    bot.send_message(uid, "🔢 تعداد داگز اولترا را وارد کن (حداقل ۱۰۰۰):")

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("type") == "duges"
                                 and user_state[m.from_user.id].get("step") == "amount")
def duges_amount(message):
    uid = message.from_user.id
    try:
        amount = int(message.text.replace(",", "").strip())
        if amount < 1000:
            bot.send_message(uid, "❌ حداقل ۱۰۰۰ عدد است. دوباره وارد کن:")
            return
        user_state[uid]["amount"] = amount
        user_state[uid]["step"] = "username"
        bot.send_message(uid, "👤 یوزرنیم اکانتی که واریز می‌شود را وارد کن:")
    except ValueError:
        bot.send_message(uid, "❌ لطفاً عدد معتبر وارد کن:")

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("type") == "duges"
                                 and user_state[m.from_user.id].get("step") == "username")
def duges_username(message):
    uid = message.from_user.id
    st = user_state[uid]
    st["username"] = message.text.strip()
    st["price"] = st["amount"] * PRICE_PER_DUGES
    st["step"] = "receipt"
    orders.append({"uid": uid, "type": "داگز اولترا", "price": st["price"], "status": "pending"})
    text = (f"🧾 سفارش داگز اولترا\n"
            f"🔢 تعداد: {st['amount']}\n"
            f"👤 یوزرنیم: {st['username']}\n"
            f"💰 مبلغ: {st['price']:,} تومان\n\n"
            f"💳 کارت: `{CARD_NUMBER}`\n"
            f"👤 به نام: {CARD_OWNER}\n\n"
            f"📸 لطفاً رسید پرداخت را ارسال کن.")
    bot.send_message(uid, text, parse_mode="Markdown")

# ================== ریکشن استارزی ==================
@bot.message_handler(func=lambda m: m.text == "⭐ ریکشن استارزی")
def stars_start(message):
    uid = message.from_user.id
    user_state[uid] = {"type": "stars", "step": "amount"}
    bot.send_message(uid, "🔢 تعداد استارز را وارد کن (حداقل ۱، حداکثر ۱۰۰۰):")

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("type") == "stars"
                                 and user_state[m.from_user.id].get("step") == "amount")
def stars_amount(message):
    uid = message.from_user.id
    try:
        amount = int(message.text.strip())
        if amount < 1 or amount > 1000:
            bot.send_message(uid, "❌ تعداد باید بین ۱ تا ۱۰۰۰ باشد. دوباره وارد کن:")
            return
        user_state[uid]["amount"] = amount
        user_state[uid]["step"] = "link"
        bot.send_message(uid, "🔗 لینک پست را وارد کن:")
    except ValueError:
        bot.send_message(uid, "❌ لطفاً عدد معتبر وارد کن:")

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("type") == "stars"
                                 and user_state[m.from_user.id].get("step") == "link")
def stars_link(message):
    uid = message.from_user.id
    st = user_state[uid]
    st["link"] = message.text.strip()
    st["price"] = st["amount"] * PRICE_PER_STAR
    st["step"] = "receipt"
    orders.append({"uid": uid, "type": "ریکشن استارزی", "price": st["price"], "status": "pending"})
    text = (f"🧾 سفارش ریکشن استارزی\n"
            f"⭐ تعداد: {st['amount']}\n"
            f"🔗 لینک: {st['link']}\n"
            f"💰 مبلغ: {st['price']:,} تومان\n\n"
            f"💳 کارت: `{CARD_NUMBER}`\n"
            f"👤 به نام: {CARD_OWNER}\n\n"
            f"📸 لطفاً رسید پرداخت را ارسال کن.")
    bot.send_message(uid, text, parse_mode="Markdown")

# ================== گیفت ==================
@bot.message_handler(func=lambda m: m.text == "🎁 گیفت")
def gift_start(message):
    bot.send_message(message.chat.id, "🎁 نوع گیفت را انتخاب کن:", reply_markup=kb_gifts())

@bot.message_handler(func=lambda m: m.text in GIFTS)
def gift_selected(message):
    uid = message.from_user.id
    price = GIFTS[message.text]
    user_state[uid] = {"type": "gift", "gift": message.text, "price": price, "step": "receipt"}
    orders.append({"uid": uid, "type": "گیفت", "price": price, "status": "pending"})
    text = (f"🧾 سفارش گیفت\n"
            f"🎁 نوع: {message.text}\n"
            f"💰 مبلغ: {price:,} تومان\n\n"
            f"💳 کارت: `{CARD_NUMBER}`\n"
            f"👤 به نام: {CARD_OWNER}\n\n"
            f"📸 لطفاً رسید پرداخت را ارسال کن.")
    bot.send_message(uid, text, parse_mode="Markdown")

# ================== پشتیبانی ==================
@bot.message_handler(func=lambda m: m.text == "🆘 پشتیبانی")
def support_start(message):
    uid = message.from_user.id
    user_state[uid] = {"type": "support", "step": "msg"}
    bot.send_message(uid, "✍️ پیامت را بنویس تا برای پشتیبانی ارسال شود:")

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("type") == "support"
                                 and user_state[m.from_user.id].get("step") == "msg")
def support_forward(message):
    uid = message.from_user.id
    bot.forward_message(ADMIN_ID, uid, message.message_id)
    bot.send_message(ADMIN_ID,
        f"📩 پیام پشتیبانی از `{uid}`\nبرای پاسخ، روی پیام فوروارد شده **ریپلای** کن.",
        parse_mode="Markdown")
    bot.send_message(uid, "✅ پیامت برای پشتیبانی ارسال شد.", reply_markup=kb_main())
    user_state.pop(uid, None)

# ================== دریافت رسید (عکس) ==================
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    uid = message.from_user.id
    st = user_state.get(uid)
    if not st or st.get("step") != "receipt":
        bot.send_message(uid, "❌ لطفاً ابتدا سفارش را ثبت کن.")
        return

    file_id = message.photo[-1].file_id
    oid = len(orders) + 1
    orders.append({"uid": uid, "type": st.get("type", "سفارش"), "price": st.get("price", 0), "status": "pending"})
    user_state.pop(uid, None)

    bot.send_photo(ADMIN_ID, file_id,
        caption=(f"📥 رسید جدید\n"
                 f"👤 کاربر: `{uid}`\n"
                 f"🆔 شماره سفارش: {oid}\n"
                 f"💰 مبلغ: {st.get('price',0):,} تومان"),
        parse_mode="Markdown",
        reply_markup=kb_admin_approve(oid, uid))

    bot.send_message(uid, "📸 رسید دریافت شد. پس از بررسی توسط مدیر، به تو اطلاع داده می‌شود.")

# ================== تأیید/رد مالک ==================
@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
def admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ دسترسی نداری", show_alert=True)
        return
    parts = call.data.split("_")
    action, oid, uid = parts[0], int(parts[1]), int(parts[2])

    if action == "approve":
        bot.send_message(uid, "✅ واریز شما تأیید شد و سفارش در حال انجام است.")
        bot.send_message(CHANNEL_ID,
            f"✅ سفارش تأیید شد\n🆔 #{oid}\n👤 کاربر: `{uid}`",
            parse_mode="Markdown")
        txt = "✅ تأیید شد"
    else:
        bot.send_message(uid, "❌ متأسفانه رسید تأیید نشد. با پشتیبانی تماس بگیر.")
        txt = "❌ رد شد"

    try:
        bot.edit_message_caption(txt, call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=None)

# ================== پاسخ مالک به پشتیبانی ==================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message is not None,
                     content_types=['text'])
def admin_reply_support(message):
    try:
        txt = message.reply_to_message.text or ""
        if "پیام پشتیبانی از" in txt:
            uid = int(txt.split("`")[1])
            bot.send_message(uid, f"📨 پاسخ پشتیبانی:\n\n{message.text}")
            bot.send_message(ADMIN_ID, "✅ پاسخ ارسال شد.")
    except Exception:
        pass

# ================== شروع (فقط یک بار اجرا میشه) ==================
if __name__ == "__main__":
    print("🤖 ربات شروع به کار کرد (حالت موقت)")
    # روی GitHub Actions نمیتونیم infinity_polling بزنیم چون نامحدود اجرا میشه
    # به جاش از polling با تایم‌اوت کوتاه استفاده می‌کنیم
    try:
        bot.polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"خطا: {e}")
