import requests
import os
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from flask import Flask

app = Flask(__name__)

# ===== ตั้งค่าตรงนี้ค่ะ =====
TELEGRAM_TOKEN = "8648221285:AAGDO-wrMCoXiwi3A2Vy1vlbZ9t20X2qZxA"
CHAT_ID = "8379040124"
ALPHA_KEY = "XWJGG2KTQW35QXNM"

TZ = pytz.timezone("Asia/Bangkok")
scheduler = BackgroundScheduler(timezone=TZ)
scheduled_event_jobs = set()

IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟡"
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_events():
    try:
        url = f"https://www.alphavantage.co/query?function=ECONOMIC_CALENDAR&horizon=3month&apikey={ALPHA_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        events = []
        now = datetime.now(TZ)
        today = now.date()

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
                    })
            except:
                continue

        events.sort(key=lambda x: x["time"])
        return events
    except Exception as e:
        print(f"API error: {e}")
        return []

def send_daily_summary():
    events = get_events()
    if not events:
        send_telegram("📅 <b>สรุปเหตุการณ์วันนี้</b>\n\nไม่มีข่าวสำคัญวันนี้ค่ะ ✅")
        return

    msg = "📅 <b>สรุปเหตุการณ์เศรษฐกิจวันนี้</b>\n"
    msg += f"🗓 {datetime.now(TZ).strftime('%d/%m/%Y')}\n\n"

    for e in events:
        emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
        time_str = e["time"].strftime("%H:%M") if e["time"].hour != 0 else "ทั้งวัน"
        msg += f"{emoji} <b>{e['title']}</b>\n"
        msg += f"🌍 {e['country']} | ⏰ {time_str} น.\n"
        msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}\n\n"

    send_telegram(msg)
    schedule_event_alerts(events)

def schedule_event_alerts(events):
    now = datetime.now(TZ)
    for e in events:
        event_time = e["time"]
        if event_time.hour == 0:
            continue
        event_id = f"{e['title']}_{event_time.strftime('%H%M')}"

        for minutes_before in [60, 30, 5, 1]:
            alert_time = event_time - timedelta(minutes=minutes_before)
            job_id = f"{event_id}_{minutes_before}"
            if alert_time > now and job_id not in scheduled_event_jobs:
                emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
                msg = f"⏰ <b>แจ้งเตือนล่วงหน้า {minutes_before} นาที</b>\n\n"
                msg += f"{emoji} <b>{e['title']}</b>\n"
                msg += f"🌍 {e['country']}\n"
                msg += f"🕐 เวลา {event_time.strftime('%H:%M')} น.\n"
                msg += f"📊 คาด: {e['forecast']} | ก่อนหน้า: {e['previous']}"

                scheduler.add_job(
                    send_telegram,
                    trigger=DateTrigger(run_date=alert_time, timezone=TZ),
                    args=[msg],
                    id=job_id
                )
                scheduled_event_jobs.add(job_id)

        # แจ้งเตือนหลังข่าวจบ 2 นาที
        after_time = event_time + timedelta(minutes=2)
        after_job_id = f"{event_id}_after"
        if after_time > now and after_job_id not in scheduled_event_jobs:
            scheduler.add_job(
                send_after_event,
                trigger=DateTrigger(run_date=after_time, timezone=TZ),
                args=[e],
                id=after_job_id
            )
            scheduled_event_jobs.add(after_job_id)

def send_after_event(event):
    try:
        url = f"https://www.alphavantage.co/query?function=ECONOMIC_CALENDAR&horizon=3month&apikey={ALPHA_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        actual = "-"
        for item in data.get("data", []):
            if item.get("event") == event["title"]:
                actual = item.get("actual", "-")
                break

        emoji = IMPACT_EMOJI.get(event["impact"], "⚪")
        msg = f"📢 <b>สรุปผลข่าว</b>\n\n"
        msg += f"{emoji} <b>{event['title']}</b>\n"
        msg += f"🌍 {event['country']}\n\n"
        msg += f"✅ ผลจริง: <b>{actual}</b>\n"
        msg += f"📊 คาด: {event['forecast']}\n"
        msg += f"📈 ก่อนหน้า: {event['previous']}"

        send_telegram(msg)
    except Exception as e:
        print(f"After event error: {e}")

# ตั้งเวลาส่งทุกเช้า 08:00
scheduler.add_job(
    send_daily_summary,
    trigger=CronTrigger(hour=8, minute=0, timezone=TZ),
    id="daily_summary"
)

scheduler.start()

@app.route("/")
def index():
    return "Economic Calendar Bot is running! ✅"

@app.route("/test")
def test():
    send_daily_summary()
    return "Test sent! ✅"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
