from flask import Flask, request, jsonify
import requests
import csv
import io
import os
from datetime import datetime
import pytz

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_IDS = os.environ.get("CHAT_IDS", "").split(",")
BASE_URL = os.environ.get("BASE_URL", "")
SHEET_ID = os.environ.get("SHEET_ID", "")

TZ = pytz.timezone("Asia/Bangkok")
sent_messages = {}

IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟡"
}

EVENT_ANALYSIS = {
    "CPI": {
        "better": "เงินเฟ้อต่ำกว่าคาด 📉 Fed อาจลดดอกเบี้ย → USD อ่อน, ทองอาจขึ้น",
        "worse": "เงินเฟ้อสูงกว่าคาด 📈 Fed อาจขึ้นดอกเบี้ย → USD แข็ง, ทองอาจลง"
    },
    "GDP": {
        "better": "เศรษฐกิจดีกว่าคาด 💪 → USD แข็ง, หุ้นอาจขึ้น",
        "worse": "เศรษฐกิจแย่กว่าคาด 😟 → USD อ่อน, หุ้นอาจลง"
    },
    "Non-Farm": {
        "better": "การจ้างงานดีกว่าคาด 💼 → USD แข็ง, ทองอาจลง",
        "worse": "การจ้างงานแย่กว่าคาด 😟 → USD อ่อน, ทองอาจขึ้น"
    },
    "Interest Rate": {
        "better": "ขึ้นดอกเบี้ย 📈 → USD แข็ง, ทองอาจลง",
        "worse": "ลดดอกเบี้ย 📉 → USD อ่อน, ทองอาจขึ้น"
    },
    "Unemployment": {
        "better": "ว่างงานต่ำกว่าคาด ✅ → USD แข็ง, หุ้นอาจขึ้น",
        "worse": "ว่างงานสูงกว่าคาด ❌ → USD อ่อน, หุ้นอาจลง"
    },
    "PMI": {
        "better": "กิจกรรมเศรษฐกิจดีกว่าคาด 💪 → USD แข็ง, หุ้นอาจขึ้น",
        "worse": "กิจกรรมเศรษฐกิจแย่กว่าคาด 😟 → USD อ่อน, หุ้นอาจลง"
    },
    "Retail Sales": {
        "better": "การใช้จ่ายดีกว่าคาด 🛍 → USD แข็ง, หุ้นอาจขึ้น",
        "worse": "การใช้จ่ายแย่กว่าคาด 😟 → USD อ่อน, หุ้นอาจลง"
    },
}

def get_analysis(title, actual, forecast):
    try:
        if not actual or not forecast or actual == "-" or forecast == "-":
            return None
        actual_val = float(str(actual).replace("%", "").replace("K", "000").strip())
        forecast_val = float(str(forecast).replace("%", "").replace("K", "000").strip())
        for key, analysis in EVENT_ANALYSIS.items():
            if key.lower() in title.lower():
                is_unemployment = "unemployment" in key.lower()
                is_better = actual_val < forecast_val if is_unemployment else actual_val > forecast_val
                if abs(actual_val - forecast_val) == 0:
                    return "📊 ตรงตามคาด ไม่มีผลกระทบมากนักค่ะ"
                result = "🟢 ดีกว่าคาด" if is_better else "🔴 แย่กว่าคาด"
                detail = analysis["better"] if is_better else analysis["worse"]
                return f"{result}\n💡 {detail}"
        return None
    except:
        return None

def send_telegram(message, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        data = r.json()
        if data.get("ok"):
            msg_id = data["result"]["message_id"]
            key = str(chat_id)
            if key not in sent_messages:
                sent_messages[key] = []
            sent_messages[key].append(msg_id)
        print(f"Sent to {chat_id}: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def delete_messages(chat_id):
    key = str(chat_id)
    ids = sent_messages.get(key, [])
    for msg_id in ids:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
            requests.post(url, json={"chat_id": chat_id, "message_id": msg_id}, timeout=10)
        except:
            pass
    sent_messages[key] = []

def send_all(message):
    for chat_id in CHAT_IDS:
        chat_id = chat_id.strip()
        if chat_id:
            send_telegram(message, chat_id)

def get_events():
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        r = requests.get(url, timeout=15)
        print(f"Sheet status: {r.status_code}")

        now = datetime.now(TZ)
        today = now.date()
        events = []

        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            try:
                date_str = row.get("date", "").strip()
                time_str = row.get("time", "").strip()
                impact = row.get("impact", "").strip()

                if impact not in ["High", "Medium", "Low"]:
                    continue

                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if event_date != today:
                    continue

                # แปลงเวลาค่ะ
                try:
                    dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    dt = TZ.localize(dt_naive)
                except:
                    dt = TZ.localize(datetime.combine(event_date, datetime.min.time()))

                events.append({
                    "title": row.get("event", "").strip(),
                    "country": row.get("country", "").strip(),
                    "impact": impact,
                    "time": dt,
                    "forecast": row.get("forecast", "-").strip() or "-",
                    "previous": row.get("previous", "-").strip() or "-",
                    "actual": row.get("actual", "-").strip() or "-",
                })
            except Exception as e:
                print(f"Row error: {e}")
                continue

        events.sort(key=lambda x: x["time"])
        print(f"Found {len(events)} events today")
        return events
    except Exception as e:
        print(f"Sheet error: {e}")
        return []

def build_daily_message():
    events = get_events()
    if not events:
        return "📅 <b>สรุปเหตุการณ์วันนี้</b>\n\nไม่มีข่าวสำคัญวันนี้ค่ะ ✅"
    msg = f"📅 <b>เหตุการณ์เศรษฐกิจวันนี้</b>\n"
    msg += f"🗓 {datetime.now(TZ).strftime('%d/%m/%Y')}\n\n"
    for e in events:
        emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
        time_str = e["time"].strftime("%H:%M") if e["time"].hour != 0 else "ทั้งวัน"
        msg += f"{emoji} <b>{e['title']}</b>\n"
        msg += f"🌍 {e['country']} | ⏰ {time_str} น.\n"
        msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}\n\n"
    return msg

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        message = data.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip().lower()

        if text.startswith("/today"):
            msg = build_daily_message()
            send_telegram(msg, chat_id)

        elif text.startswith("/customers"):
            admin_id = CHAT_IDS[0].strip() if CHAT_IDS else ""
            if chat_id == admin_id:
                msg = "👥 <b>รายชื่อลูกค้าทั้งหมดค่ะ</b>\n\n"
                for i, cid in enumerate(CHAT_IDS, 1):
                    cid = cid.strip()
                    if cid:
                        msg += f"{i}. <code>{cid}</code>\n"
                msg += f"\nทั้งหมด {len([c for c in CHAT_IDS if c.strip()])} คนค่ะ"
                send_telegram(msg, chat_id)
            else:
                send_telegram("❌ ไม่มีสิทธิ์ใช้คำสั่งนี้ค่ะ", chat_id)

        elif text.startswith("/clear"):
            delete_messages(chat_id)
            send_telegram("🧹 ลบข้อความของ Bot ทั้งหมดแล้วค่ะ!", chat_id)

        elif text.startswith("/help"):
            msg = "🤖 <b>คำสั่งที่ใช้ได้ค่ะ</b>\n\n"
            msg += "/today - ดูข่าวเศรษฐกิจวันนี้ค่ะ\n"
            msg += "/clear - ลบข้อความของ Bot ทั้งหมดค่ะ\n"
            msg += "/customers - ดูรายชื่อลูกค้า (Admin เท่านั้น) ค่ะ\n"
            msg += "/help - ดูคำสั่งทั้งหมดค่ะ"
            send_telegram(msg, chat_id)

    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"ok": True})

@app.route("/set_webhook")
def set_webhook():
    webhook_url = f"https://{BASE_URL}/webhook"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    r = requests.get(url)
    return r.json()

@app.route("/")
def index():
    return "Economic Calendar Bot ✅"

@app.route("/daily")
def daily():
    msg = build_daily_message()
    send_all(msg)
    return "Daily summary sent!"

@app.route("/alert")
def alert():
    events = get_events()
    now = datetime.now(TZ)
    sent = 0
    for e in events:
        if e["time"].hour == 0:
            continue
        diff = (e["time"] - now).total_seconds() / 60
        for mins in [60, 30, 5, 1]:
            if abs(diff - mins) <= 1:
                emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
                msg = f"⏰ <b>แจ้งเตือนล่วงหน้า {mins} นาที</b>\n\n"
                msg += f"{emoji} <b>{e['title']}</b>\n"
                msg += f"🌍 {e['country']}\n"
                msg += f"🕐 เวลา {e['time'].strftime('%H:%M')} น.\n"
                msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}"
                send_all(msg)
                sent += 1
        if -3 <= diff <= -1:
            emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
            actual = e.get("actual", "-")
            analysis = get_analysis(e["title"], actual, e["forecast"])
            msg = f"📢 <b>สรุปผลข่าว</b>\n\n"
            msg += f"{emoji} <b>{e['title']}</b>\n"
            msg += f"🌍 {e['country']}\n\n"
            msg += f"✅ ผลจริง: <b>{actual}</b>\n"
            msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}\n"
            if analysis:
                msg += f"\n{analysis}"
            send_all(msg)
            sent += 1
    return f"Checked alerts, sent {sent} messages"

@app.route("/test")
def test():
    send_all("🤖 <b>Economic Calendar Bot ทดสอบระบบค่ะ!</b>\n\nBot พร้อมทำงานแล้วค่ะ ✅\n\nพิมพ์ /today เพื่อดูข่าววันนี้ได้เลยค่ะ")
    return "Test sent!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
