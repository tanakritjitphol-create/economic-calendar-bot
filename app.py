from flask import Flask
import requests
import os
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
ALPHA_KEY = os.environ.get("ALPHA_KEY", "")

TZ = pytz.timezone("Asia/Bangkok")

IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟡"
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

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
        send_telegram("📅 <b>สรุปเหตุการณ์วันนี้</b>\n\nไม่มีข่าวสำคัญวันนี้ค่ะ ✅")
        return "No events today"

    msg = f"📅 <b>เหตุการณ์เศรษฐกิจวันนี้</b>\n"
    msg += f"🗓 {datetime.now(TZ).strftime('%d/%m/%Y')}\n\n"

    for e in events:
        emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
        time_str = e["time"].strftime("%H:%M") if e["time"].hour != 0 else "ทั้งวัน"
        msg += f"{emoji} <b>{e['title']}</b>\n"
        msg += f"🌍 {e['country']} | ⏰ {time_str} น.\n"
        msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}\n\n"

    send_telegram(msg)
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
                send_telegram(msg)
                sent += 1

        if -3 <= diff <= -1:
            emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
            actual = e.get("actual", "-")
            msg = f"📢 <b>สรุปผลข่าว</b>\n\n"
            msg += f"{emoji} <b>{e['title']}</b>\n"
            msg += f"🌍 {e['country']}\n\n"
            msg += f"✅ ผลจริง: <b>{actual}</b>\n"
            msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}"
            send_telegram(msg)
            sent += 1

    return f"Checked alerts, sent {sent} messages"

@app.route("/test")
def test():
    send_telegram("🤖 <b>Economic Calendar Bot ทดสอบระบบค่ะ!</b>\n\nBot พร้อมทำงานแล้วค่ะ ✅")
    return "Test sent!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
