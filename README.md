import requests
import telebot
from telebot import types
from bs4 import BeautifulSoup
import random
import string

TOKEN = "8045234407:AAFae6Uiugb2UCVezR5elso8o3fPGj3RdiA"
bot = telebot.TeleBot(TOKEN)

def generate_email():
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{username}@drmail.in"

def fetch_messages(email):
    inbox_url = f"https://drmail.in/mailbox/{email.split('@')[0]}"
    response = requests.get(inbox_url)
    soup = BeautifulSoup(response.text, "html.parser")
    messages = soup.find_all("div", class_="card mt-2 shadow-sm")
    result = []

    for msg in messages:
        sender = msg.find("h6").text.strip()
        subject = msg.find("h5").text.strip()
        body = msg.find("p").text.strip()
        timestamp = msg.find("small").text.strip()
        full_msg = f"📬 *رسالة جديدة:*\n👤 من: `{sender}`\n🕒 الوقت: _{timestamp}_\n📝 العنوان: *{subject}*\n\n📩 {body}"
        result.append(full_msg)

    return result

user_data = {}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    email = generate_email()

    user_data[user_id] = {"email": email, "history": []}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📥 عرض الرسائل", "🕓 عرض آخر رسالة فقط")
    markup.row("📤 توليد بريد جديد", "🗑️ حذف البريد")

    bot.send_message(
        message.chat.id,
        f"👋 أهلاً {message.from_user.first_name}\n📧 تم توليد بريدك:\n\n`{email}`",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: True)
def handle_all(message):
    user_id = str(message.from_user.id)
    text = message.text

    if user_id not in user_data:
        bot.reply_to(message, "❗ استخدم /start الأول لإنشاء بريد.")
        return

    email = user_data[user_id]["email"]

    if text == "📥 عرض الرسائل":
        bot.send_message(message.chat.id, "🔍 جاري البحث...")
        msgs = fetch_messages(email)
        if msgs:
            for m in msgs:
                bot.send_message(message.chat.id, m, parse_mode="Markdown")
            user_data[user_id]["history"] = msgs
        else:
            bot.send_message(message.chat.id, "📭 لا توجد رسائل حالياً.")

    elif text == "🕓 عرض آخر رسالة فقط":
        msgs = fetch_messages(email)
        if msgs:
            bot.send_message(message.chat.id, msgs[0], parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "📭 لا توجد رسائل حالياً.")

    elif text == "📤 توليد بريد جديد":
        new_email = generate_email()
        user_data[user_id]["email"] = new_email
        user_data[user_id]["history"] = []
        bot.send_message(message.chat.id, f"✅ تم توليد بريد جديد:\n\n`{new_email}`", parse_mode="Markdown")

    elif text == "🗑️ حذف البريد":
        old_email = user_data[user_id]["email"]
        user_data[user_id] = {}
        bot.send_message(message.chat.id, f"🗑️ تم حذف البريد `{old_email}`", parse_mode="Markdown")

    else:
        bot.send_message(message.chat.id, "❓ الأمر غير معروف. استخدم /start لعرض الخيارات.")

print("✅ Bot is running...")
bot.infinity_polling()
