from flask import Flask
import requests
import os
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("8648221285:AAGnZC1ujew6seX9wxYz3b-WytN75hss5pM", "")
CHAT_IDS = os.environ.get("8379040124", "8798291565", "").split(",")  # ใส่หลาย Chat ID คั่นด้วย , ค่ะ
ALPHA_KEY = os.environ.get("XWJGG2KTQW35QXNM", "")

TZ = pytz.timezone("Asia/Bangkok")

IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟡"
}

# วิเคราะห์ผลข่าวค่ะ
EVENT_ANALYSIS = {
    "CPI": {
        "better": "เงินเฟ้อต่ำกว่าคาด 📉 Fed อาจลดดอกเบี้ย → USD อ่อน, ทองอาจขึ้น, หุ้นอาจขึ้น",
        "worse": "เงินเฟ้อสูงกว่าคาด 📈 Fed อาจขึ้นดอกเบี้ย → USD แข็ง, ทองอาจลง, หุ้นอาจลง"
    },
    "GDP": {
        "better": "เศรษฐกิจดีกว่าคาด 💪 → USD แข็ง, หุ้นอาจขึ้น",
        "worse": "เศรษฐกิจแย่กว่าคาด 😟 → USD อ่อน, หุ้นอาจลง"
    },
    "NFP": {
        "better": "การจ้างงานดีกว่าคาด 💼 → USD แข็ง, ทองอาจลง",
        "worse": "การจ้างงานแย่กว่าคาด 😟 → USD อ่อน, ทองอาจขึ้น"
    },
    "Non-Farm": {
        "better": "การจ้างงานดีกว่าคาด 💼 → USD แข็ง, ทองอาจลง",
        "worse": "การจ้างงานแย่กว่าคาด 😟 → USD อ่อน, ทองอาจขึ้น"
    },
    "Interest Rate": {
        "better": "ขึ้นดอกเบี้ยหรือคงที่สูง 📈 → USD แข็ง, ทองอาจลง",
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
    "PPI": {
        "better": "เงินเฟ้อผู้ผลิตต่ำกว่าคาด 📉 → USD อ่อน, ทองอาจขึ้น",
        "worse": "เงินเฟ้อผู้ผลิตสูงกว่าคาด 📈 → USD แข็ง, ทองอาจลง"
    },
    "Retail Sales": {
        "better": "การใช้จ่ายดีกว่าคาด 🛍 → USD แข็ง, หุ้นอาจขึ้น",
        "worse": "การใช้จ่ายแย่กว่าคาด 😟 → USD อ่อน, หุ้นอาจลง"
    },
}

def get_analysis(title, actual, forecast):
    try:
        if actual == "-" or forecast == "-":
            return None
        actual_val = float(str(actual).replace("%", "").replace("K", "000").replace("M", "000000").strip())
        forecast_val = float(str(forecast).replace("%", "").replace("K", "000").replace("M", "000000").strip())

        for key, analysis in EVENT_ANALYSIS.items():
            if key.lower() in title.lower():
                is_unemployment = "unemployment" in key.lower()
                if is_unemployment:
                    is_better = actual_val < forecast_val
                else:
                    is_better = actual_val > forecast_val

                diff = abs(actual_val - forecast_val)
                if diff == 0:
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
        print(f"Sent to {chat_id}: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def send_all(message):
    for chat_id in CHAT_IDS:
        chat_id = chat_id.strip()
        if chat_id:
            send_telegram(message, chat_id)

def get_events():
    try:
        url = f"https://www.alphavantage.co/query?function=ECONOMIC_CALENDAR&horizon=3month&apikey={ALPHA_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        now = datetime.now(TZ)
        today = now.date()
        events = []

        for item in data.get("data", []):
            impact = item.get("impact", "")
            if impact not in ["High", "Medium", "Low"]:
                continue
            try:
                dt_str = item.get("date", "")
                if "T" in dt_str:
                    dt = datetime.fromisoformat(dt_str).astimezone(TZ)
                else:
                    dt = TZ.localize(datetime.strptime(dt_str, "%Y-%m-%d"))
                if dt.date() == today:
                    events.append({
                        "title": item.get("event", ""),
                        "country": item.get("country", ""),
                        "impact": impact,
                        "time": dt,
                        "forecast": item.get("forecast", "-"),
                        "previous": item.get("previous", "-"),
                        "actual": item.get("actual", "-"),
                    })
            except:
                continue

        events.sort(key=lambda x: x["time"])
        return events
    except Exception as e:
        print(f"API error: {e}")
        return []

@app.route("/")
def index():
    return "Economic Calendar Bot ✅"

@app.route("/daily")
def daily():
    events = get_events()
    if not events:
        send_all("📅 <b>สรุปเหตุการณ์วันนี้</b>\n\nไม่มีข่าวสำคัญวันนี้ค่ะ ✅")
        return "No events today"

    msg = f"📅 <b>เหตุการณ์เศรษฐกิจวันนี้</b>\n"
    msg += f"🗓 {datetime.now(TZ).strftime('%d/%m/%Y')}\n\n"

    for e in events:
        emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
        time_str = e["time"].strftime("%H:%M") if e["time"].hour != 0 else "ทั้งวัน"
        msg += f"{emoji} <b>{e['title']}</b>\n"
        msg += f"🌍 {e['country']} | ⏰ {time_str} น.\n"
        msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}\n\n"

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
    send_all("🤖 <b>Economic Calendar Bot ทดสอบระบบค่ะ!</b>\n\nBot พร้อมทำงานแล้วค่ะ ✅")
    return "Test sent!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
