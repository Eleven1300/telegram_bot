import time
# import winsound
import threading
import requests
from datetime import datetime, date
from colorama import Fore, init

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

init(autoreset=True)

TOKEN = "8636291404:AAF-R-48ulxFjn7WLSpVHX5WC1YggK-lNME"
CHAT_ID = "@Alertvisaturk"  # قناة التنبيه

LOCATIONS = [
    {"name": "Oran", "url": "https://appointment.mosaicvisa.com/calendar/7?month=2026-04"},
    {"name": "Oran VIP", "url": "https://appointment.mosaicvisa.com/calendar/8?month=2026-04"},
    {"name": "Alger", "url": "https://appointment.mosaicvisa.com/calendar/9?month=2026-04"},
    {"name": "Constantine", "url": "https://appointment.mosaicvisa.com/calendar/17?month=2026-04"}
]

bot_running = True
check_interval = 45
sound_alert = True
locations_status = {loc["name"]: True for loc in LOCATIONS}

# لتخزين آخر فئة تم إرسالها لكل مركز + آخر يوم
last_alert = {loc["name"]: {"category": None, "day": date.today()} for loc in LOCATIONS}

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-gpu")

# -------- Helper: تحديد الفئة --------
def categorize(count):
    if count >= 100:
        return "very_high"
    elif count >= 50:
        return "high"
    elif count >= 30:
        return "medium"
    elif count >= 15:
        return "low"
    else:
        return "critical"

# -------- Telegram Handlers --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 الحالة", callback_data="status")],
        [InlineKeyboardButton("⏸️ إيقاف مؤقت", callback_data="pause"),
         InlineKeyboardButton("▶️ استئناف", callback_data="resume")],
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data="interval_30"),
         InlineKeyboardButton("⏱️ 60 ثانية", callback_data="interval_60")],
        [InlineKeyboardButton("🔔 تشغيل الصوت", callback_data="sound_on"),
         InlineKeyboardButton("🔕 إيقاف الصوت", callback_data="sound_off")],
        [InlineKeyboardButton("✅ Oran", callback_data="toggle_Oran"),
         InlineKeyboardButton("✅ Oran VIP", callback_data="toggle_Oran VIP")],
        [InlineKeyboardButton("✅ Alger", callback_data="toggle_Alger"),
         InlineKeyboardButton("✅ Constantine", callback_data="toggle_Constantine")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مرحبا! لوحة تحكم البوت:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running, check_interval, sound_alert, locations_status

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "status":
        enabled = [n for n, s in locations_status.items() if s]
        disabled = [n for n, s in locations_status.items() if not s]
        msg = (
            f"✅ البوت يعمل\n"
            f"⏱️ فاصل الفحص: {check_interval} ثانية\n"
            f"🟢 المراكز المفعّلة: {', '.join(enabled)}\n"
            f"🔴 المراكز الموقوفة: {', '.join(disabled) if disabled else 'لا يوجد'}"
        )
        await query.message.reply_text(msg)

    elif data == "pause":
        bot_running = False
        await query.message.reply_text("⏸️ تم إيقاف جميع الفحوصات مؤقتًا")

    elif data == "resume":
        bot_running = True
        await query.message.reply_text("▶️ تم استئناف جميع الفحوصات")

    elif data == "interval_30":
        check_interval = 30
        await query.message.reply_text("⏱️ تم تغيير الفاصل إلى 30 ثانية")

    elif data == "interval_60":
        check_interval = 60
        await query.message.reply_text("⏱️ تم تغيير الفاصل إلى 60 ثانية")

    elif data == "sound_on":
        sound_alert = True
        await query.message.reply_text("🔔 تم تشغيل الصوت")

    elif data == "sound_off":
        sound_alert = False
        await query.message.reply_text("🔕 تم إيقاف الصوت")

    elif data.startswith("toggle_"):
        loc_name = data.replace("toggle_", "")
        locations_status[loc_name] = not locations_status.get(loc_name, True)
        status = "✅ مفعل" if locations_status[loc_name] else "⛔️ معطل"
        await query.message.reply_text(f"{loc_name} الآن {status}")

# -------- Monitor --------
def monitor_appointments():
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    print(Fore.CYAN + "=== بدأ الفحص الذكي ===")

    while True:
        if not bot_running:
            time.sleep(check_interval)
            continue

        today = date.today()
        for loc in LOCATIONS:
            if not locations_status.get(loc["name"], True):
                continue

            try:
                driver.get(loc['url'])
                time.sleep(8)
                rows = driver.find_elements(By.XPATH, "//tr")
                available_dates = []

                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 2:
                        date_text = cols[0].text.strip()
                        avail_text = cols[1].text.strip()
                        if "Available" in avail_text:
                            available_dates.append(f"📅 {date_text} {avail_text}")

                now = datetime.now().strftime("%H:%M:%S")
                count = sum(int(d.split()[-1]) for d in available_dates) if available_dates else 0
                category = categorize(count)

                # إعادة العد إذا تغير اليوم
                if last_alert[loc["name"]]["day"] != today:
                    last_alert[loc["name"]]["day"] = today
                    last_alert[loc["name"]]["category"] = None

                send_alert = False
                if category == "critical":
                    send_alert = True
                elif last_alert[loc["name"]]["category"] != category:
                    send_alert = True

                last_alert[loc["name"]]["category"] = category

                if available_dates and send_alert:
                    msg = (
                        f"🔔 تنبيه: مواعيد متاحة!\n\n"
                        f"📍 المركز: {loc['name']}\n"
                        f"📅 التواريخ المستخرجة:\n" +
                        "\n".join(available_dates)
                    )
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                  json={"chat_id": CHAT_ID, "text": msg})

                    if sound_alert:
                        for _ in range(3):
                            winsound.Beep(2500, 800)

                print(
                    Fore.YELLOW + f"[{now}] فحص {loc['name']}...  " +
                    (Fore.GREEN + "[✔️] متاح!" if available_dates else Fore.RED + "[✖️] غير متاح")
                )

            except Exception as e:
                print(Fore.RED + f"خطأ {loc['name']}: {e}")

        time.sleep(check_interval)

# -------- Start --------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    threading.Thread(target=monitor_appointments, daemon=True).start()
    app.run_polling()
