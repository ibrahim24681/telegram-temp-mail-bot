import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from datetime import datetime, timedelta
import threading
import time
import sqlite3
import re

# ========= ضع بياناتك هنا =========
TOKEN = "8608097209:AAH3WFxDgqIbO8okmWuuCvY3xaZivKLDGLc"
SUPER_ADMIN_ID = 6270570103  # ضع الـ ID الخاص بك هنا
# ===================================

bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

cursor.execute("INSERT OR IGNORE INTO admins VALUES (?)", (SUPER_ADMIN_ID,))
conn.commit()

# ================= DB FUNCTIONS =================
def add_user(uid):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (uid,))
    conn.commit()

def get_users():
    cursor.execute("SELECT user_id FROM users")
    return [x[0] for x in cursor.fetchall()]

def is_admin(uid):
    cursor.execute("SELECT * FROM admins WHERE user_id=?", (uid,))
    return cursor.fetchone() is not None

def get_admins():
    cursor.execute("SELECT user_id FROM admins")
    return [x[0] for x in cursor.fetchall()]

def add_admin(uid):
    cursor.execute("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
    conn.commit()

def remove_admin(uid):
    if uid == SUPER_ADMIN_ID:
        return False
    cursor.execute("DELETE FROM admins WHERE user_id=?", (uid,))
    conn.commit()
    return True

def set_setting(key, val):
    cursor.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, val))
    conn.commit()

def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = cursor.fetchone()
    return r[0] if r else None

# ================= PRAYER =================
PRAYER_NAMES = {
    "Fajr":"الفجر",
    "Dhuhr":"الظهر",
    "Asr":"العصر",
    "Maghrib":"المغرب",
    "Isha":"العشاء"
}

def get_prayer_times():
    url = "http://api.aladhan.com/v1/timingsByCity"
    params = {"city":"Cairo","country":"Egypt","method":5}
    return requests.get(url, params=params).json()["data"]["timings"]

# ================= REMOVE TASHKEEL =================
def remove_tashkeel(text):
    tashkeel = re.compile(r'[\u0617-\u061A\u064B-\u0652]')
    return re.sub(tashkeel, '', text)

# ================= AZKAR =================
MORNING_AZKAR = [
    {"text":"آية الكرسي","count":1},
    {"text":"قل هو الله أحد","count":3},
    {"text":"سبحان الله وبحمده","count":100}
]

EVENING_AZKAR = MORNING_AZKAR

azkar_sessions = {}
tasbeeh_sessions = {}
search_mode = set()
ayah_mode = set()
broadcast_mode = set()
add_admin_mode = set()
remove_admin_mode = set()

# ================= KEYBOARDS =================
def main_menu(uid):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🕌 مواقيت الصلاة", callback_data="prayer"),
        InlineKeyboardButton("⏳ المتبقي", callback_data="remain"),
        InlineKeyboardButton("🌅 أذكار الصباح", callback_data="morning"),
        InlineKeyboardButton("🌇 أذكار المساء", callback_data="evening"),
        InlineKeyboardButton("📿 التسبيح", callback_data="tas_menu"),
        InlineKeyboardButton("🔍 بحث قرآن", callback_data="search"),
        InlineKeyboardButton("📖 آية / سورة", callback_data="ayah"),
        InlineKeyboardButton("📘 القرآن الكريم", callback_data="quran_menu")
    )
    if is_admin(uid):
        markup.add(InlineKeyboardButton("🛡 لوحة الأدمن", callback_data="admin"))
    return markup

def admin_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 عدد المستخدمين",callback_data="a_users"),
        InlineKeyboardButton("📢 إذاعة",callback_data="a_broadcast"),
        InlineKeyboardButton("➕ إضافة أدمن",callback_data="a_add"),
        InlineKeyboardButton("🗑 حذف أدمن",callback_data="a_remove"),
        InlineKeyboardButton("📋 عرض الأدمنز",callback_data="a_list"),
        InlineKeyboardButton("🔔 تشغيل إشعارات",callback_data="a_on"),
        InlineKeyboardButton("🔕 إيقاف إشعارات",callback_data="a_off"),
    )
    return markup

# ================= START =================
@bot.message_handler(commands=["start"])
def start(msg):
    add_user(msg.from_user.id)
    bot.send_message(msg.chat.id,"🤍 أهلاً بك",reply_markup=main_menu(msg.from_user.id))

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call:True)
def callback(call):
    uid = call.from_user.id

    if call.data=="prayer":
        t=get_prayer_times()
        text="🕌 مواقيت الصلاة\n\n"
        for k in PRAYER_NAMES:
            text+=f"{PRAYER_NAMES[k]} : {t[k]}\n"
        bot.send_message(call.message.chat.id,text)

    elif call.data=="remain":
        t=get_prayer_times()
        now=datetime.now()
        for k in PRAYER_NAMES:
            pt=datetime.strptime(t[k],"%H:%M").replace(
                year=now.year,month=now.month,day=now.day)
            if pt>now:
                diff=pt-now
                h=diff.seconds//3600
                m=(diff.seconds%3600)//60
                bot.send_message(call.message.chat.id,
                    f"⏳ الصلاة القادمة {PRAYER_NAMES[k]}\nباقي {h} ساعة و {m} دقيقة")
                break

    elif call.data=="morning":
        azkar_sessions[uid]={"list":MORNING_AZKAR,"i":0,"c":0}
        send_zekr(call)

    elif call.data=="evening":
        azkar_sessions[uid]={"list":EVENING_AZKAR,"i":0,"c":0}
        send_zekr(call)

    elif call.data=="zekr":
        handle_zekr(call)

    elif call.data=="tas_menu":
        markup=InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("بعد الصلاة",callback_data="tas_after"),
            InlineKeyboardButton("×100",callback_data="tas_100"),
            InlineKeyboardButton("مفتوح",callback_data="tas_open"),
        )
        bot.send_message(call.message.chat.id,"اختر نوع التسبيح",reply_markup=markup)

    elif call.data in ["tas_after","tas_100","tas_open"]:
        start_tas(call)

    elif call.data=="tas":
        handle_tas(call)

    elif call.data=="search":
        search_mode.add(uid)
        bot.send_message(call.message.chat.id,"اكتب كلمة للبحث")

    elif call.data=="ayah":
        ayah_mode.add(uid)
        bot.send_message(call.message.chat.id,"اكتب:\n2:255\nأو\n2")

    elif call.data=="quran_menu":
        surahs = requests.get("http://api.alquran.cloud/v1/surah").json()["data"]
        markup = InlineKeyboardMarkup(row_width=3)
        for s in surahs:
            markup.add(
                InlineKeyboardButton(
                    f"{s['number']}-{s['name']}",
                    callback_data=f"surah_{s['number']}"
                )
            )
        bot.edit_message_text("📖 اختر السورة:",
                              call.message.chat.id,
                              call.message.message_id,
                              reply_markup=markup)

    elif call.data.startswith("surah_"):
        surah_number = call.data.split("_")[1]
        url = f"http://api.alquran.cloud/v1/surah/{surah_number}/ar"
        response = requests.get(url).json()["data"]

        surah_name = response["name"]
        ayahs = response["ayahs"]

        header = f"📖 سورة {surah_name}\nعدد الآيات: {len(ayahs)}\n\n"
        current = header

        for ayah in ayahs:
            line = f"{ayah['numberInSurah']}. {ayah['text']}\n"
            if len(current) + len(line) > 4000:
                bot.send_message(call.message.chat.id,current)
                current = line
            else:
                current += line

        if current:
            bot.send_message(call.message.chat.id,current)

    elif call.data=="admin" and is_admin(uid):
        bot.send_message(call.message.chat.id,"🎛 لوحة الأدمن",reply_markup=admin_menu())

    elif call.data.startswith("a_") and is_admin(uid):

        if call.data=="a_users":
            bot.send_message(call.message.chat.id,f"عدد المستخدمين: {len(get_users())}")

        elif call.data=="a_broadcast":
            broadcast_mode.add(uid)
            bot.send_message(call.message.chat.id,"اكتب الرسالة")

        elif call.data=="a_add":
            add_admin_mode.add(uid)
            bot.send_message(call.message.chat.id,"ارسل ID")

        elif call.data=="a_remove":
            remove_admin_mode.add(uid)
            bot.send_message(call.message.chat.id,"ارسل ID")

        elif call.data=="a_list":
            bot.send_message(call.message.chat.id,"\n".join(map(str,get_admins())))

        elif call.data=="a_on":
            set_setting("notify","on")
            bot.send_message(call.message.chat.id,"تم التشغيل")

        elif call.data=="a_off":
            set_setting("notify","off")
            bot.send_message(call.message.chat.id,"تم الإيقاف")

# ================= AZKAR =================
def send_zekr(call):
    s=azkar_sessions[call.from_user.id]
    current=s["list"][s["i"]]
    text=f"{current['text']}\n\n{s['c']} / {current['count']}"
    markup=InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("اضغط 🤍",callback_data="zekr"))
    bot.edit_message_text(text,call.message.chat.id,call.message.message_id,reply_markup=markup)

def handle_zekr(call):
    s=azkar_sessions[call.from_user.id]
    current=s["list"][s["i"]]
    s["c"]+=1
    if s["c"]>=current["count"]:
        s["i"]+=1
        s["c"]=0
        if s["i"]>=len(s["list"]):
            bot.edit_message_text("تم الانتهاء 🤍",call.message.chat.id,call.message.message_id)
            del azkar_sessions[call.from_user.id]
            return
    send_zekr(call)

# ================= TASBEEH =================
def start_tas(call):
    uid=call.from_user.id
    if call.data=="tas_after":
        tasbeeh_sessions[uid]=[
            {"text":"سبحان الله","count":33},
            {"text":"الحمد لله","count":33},
            {"text":"الله أكبر","count":34},
            {"i":0,"c":0}
        ]
    elif call.data=="tas_100":
        tasbeeh_sessions[uid]=[
            {"text":"سبحان الله","count":100},
            {"i":0,"c":0}
        ]
    else:
        tasbeeh_sessions[uid]=[
            {"text":"سبحان الله","count":999999},
            {"i":0,"c":0}
        ]
    send_tas(call)

def send_tas(call):
    s=tasbeeh_sessions[call.from_user.id]
    meta=s[-1]
    current=s[meta["i"]]
    text=f"{current['text']}\n\n{meta['c']} / {current['count']}"
    markup=InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("اضغط 🤍",callback_data="tas"))
    bot.edit_message_text(text,call.message.chat.id,call.message.message_id,reply_markup=markup)

def handle_tas(call):
    s=tasbeeh_sessions[call.from_user.id]
    meta=s[-1]
    current=s[meta["i"]]
    meta["c"]+=1
    if meta["c"]>=current["count"]:
        meta["i"]+=1
        meta["c"]=0
        if meta["i"]>=len(s)-1:
            bot.edit_message_text("تم الانتهاء 🤍",call.message.chat.id,call.message.message_id)
            del tasbeeh_sessions[call.from_user.id]
            return
    send_tas(call)

# ================= MESSAGE HANDLER =================
@bot.message_handler(func=lambda m:True)
def handle_msg(m):

    uid=m.from_user.id

    if uid in broadcast_mode:
        broadcast_mode.remove(uid)
        for u in get_users():
            try: bot.send_message(u,m.text)
            except: pass
        bot.reply_to(m,"تم الإرسال")

    elif uid in add_admin_mode:
        add_admin_mode.remove(uid)
        add_admin(int(m.text))
        bot.reply_to(m,"تمت الإضافة")

    elif uid in remove_admin_mode:
        remove_admin_mode.remove(uid)
        remove_admin(int(m.text))
        bot.reply_to(m,"تم الحذف")

    elif uid in search_mode:
        search_mode.remove(uid)
        try:
            query=remove_tashkeel(m.text)
            url="http://api.alquran.cloud/v1/quran/ar"
            data=requests.get(url).json()["data"]["surahs"]
            results=[]
            for surah in data:
                for ayah in surah["ayahs"]:
                    clean=remove_tashkeel(ayah["text"])
                    if query in clean:
                        results.append(f"{surah['name']} {ayah['numberInSurah']}\n{ayah['text']}")
                    if len(results)>=5: break
                if len(results)>=5: break
            if not results:
                bot.reply_to(m,"لا توجد نتائج")
            else:
                bot.reply_to(m,"\n\n".join(results))
        except:
            bot.reply_to(m,"خطأ")

    elif uid in ayah_mode:
        ayah_mode.remove(uid)
        text = m.text.replace(":", " ").split()
        try:
            if len(text)==2:
                surah=int(text[0])
                ayah=int(text[1])
                url=f"http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/ar"
                res=requests.get(url).json()
                bot.reply_to(m,res["data"]["text"])
            elif len(text)==1:
                surah=int(text[0])
                sdata=requests.get(f"http://api.alquran.cloud/v1/surah/{surah}").json()["data"]
                markup=InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("📖 فتح السورة كاملة",callback_data=f"surah_{surah}"))
                bot.reply_to(m,f"سورة {sdata['name']}\nعدد الآيات: {sdata['numberOfAyahs']}",reply_markup=markup)
            else:
                bot.reply_to(m,"اكتب 2:255 أو 2")
        except:
            bot.reply_to(m,"صيغة غير صحيحة")

# ================= NOTIFICATION LOOP =================
def notify_loop():
    sent={}
    while True:
        if get_setting("notify")=="on":
            t=get_prayer_times()
            now=datetime.now()
            for k in PRAYER_NAMES:
                pt=datetime.strptime(t[k],"%H:%M").replace(
                    year=now.year,month=now.month,day=now.day)
                notify=pt-timedelta(minutes=10)
                tag=f"{k}_{now.date()}"
                if now.hour==notify.hour and now.minute==notify.minute:
                    if tag not in sent:
                        for u in get_users():
                            try:
                                bot.send_message(u,f"🔔 بعد 10 دقائق صلاة {PRAYER_NAMES[k]}")
                            except: pass
                        sent[tag]=1
        time.sleep(30)

threading.Thread(target=notify_loop).start()

print("Bot Running...")
bot.infinity_polling()