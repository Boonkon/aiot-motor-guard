"""Telegram bot: หน้าจอผู้ใช้ของระบบ
    /status      สถานะล่าสุดของทุกเครื่อง (AI ทายว่าอะไร มั่นใจแค่ไหน)
    /history 10  กราฟการสั่นย้อนหลัง 10 นาที
    /subscribe   รับการแจ้งเตือนอัตโนมัติ      /unsubscribe  เลิกรับ
    /explain     อธิบายว่าระบบ AIoT นี้ทำงานอย่างไร (สำหรับผู้เรียน)

    python bot.py
"""
import asyncio
import io
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from common import LABEL_TH, config, db_connect

db = db_connect()
COLORS = {"normal": "tab:green", "unbalanced": "tab:orange", "off": "tab:gray", "unknown": "tab:red"}


def status_text() -> str:
    rows = db.execute(
        "SELECT t.* FROM telemetry t JOIN (SELECT device, MAX(id) AS id FROM telemetry GROUP BY device) m"
        " ON t.id = m.id ORDER BY t.device").fetchall()
    if not rows:
        return "ยังไม่มีข้อมูล — ตรวจว่าบอร์ด (หรือ simulator) และ gateway ทำงานอยู่"
    lines = []
    for r in rows:
        age = time.time() - r["ts"]
        stale = " ⏳ (ข้อมูลเก่า บอร์ดอาจหลุด)" if age > 10 else ""
        lines.append(
            f"🔧 *{r['device']}*{stale}\n"
            f"AI ทายว่า: *{LABEL_TH.get(r['label'], r['label'])}* (มั่นใจ {r['confidence']:.0%})\n"
            f"การสั่น RMS: {r['rms']:.3f} g · ความถี่เด่น {r['f_dom']:.0f} Hz\n"
            f"อุณหภูมิ {r['temp']:.1f}°C · ความชื้น {r['hum']:.0f}%\n"
            f"อัปเดตเมื่อ {age:.0f} วินาทีที่แล้ว")
    return "\n\n".join(lines)


def history_png(minutes: int) -> io.BytesIO | None:
    since = time.time() - minutes * 60
    rows = db.execute("SELECT ts, device, rms, temp, label FROM telemetry WHERE ts > ? ORDER BY ts",
                      (since,)).fetchall()
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(7, 3.6))
    t0 = rows[-1]["ts"]
    for lab, color in COLORS.items():
        pts = [((r["ts"] - t0) / 60, r["rms"]) for r in rows if r["label"] == lab]
        if pts:
            ax.scatter(*zip(*pts), s=10, c=color, label=lab)
    ax.set_xlabel("minutes (0 = now)")
    ax.set_ylabel("vibration RMS [g]")
    ax2 = ax.twinx()
    ax2.plot([(r["ts"] - t0) / 60 for r in rows], [r["temp"] for r in rows], "k--", lw=0.8)
    ax2.set_ylabel("temperature [°C]")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"Last {minutes} min — colour = AI prediction")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "สวัสดีครับ 👋 ผมคือผู้ช่วยเฝ้าระวังมอเตอร์ (AIoT Motor Guard)\n\n"
        "/status – ดูสถานะล่าสุด\n/history 10 – กราฟย้อนหลัง 10 นาที\n"
        "/subscribe – รับแจ้งเตือนอัตโนมัติ\n/unsubscribe – เลิกรับแจ้งเตือน\n"
        "/explain – ระบบนี้ทำงานอย่างไร")


async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(status_text(), parse_mode="Markdown")


async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    minutes = int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else 10
    png = history_png(min(minutes, 24 * 60))
    if png is None:
        await update.message.reply_text("ไม่มีข้อมูลในช่วงเวลานี้")
    else:
        await update.message.reply_photo(png, caption=f"การสั่นย้อนหลัง {minutes} นาที (สีตามที่ AI ทาย)")


async def subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db.execute("INSERT OR IGNORE INTO subscribers VALUES (?)", (update.effective_chat.id,))
    db.commit()
    await update.message.reply_text("🔔 รับการแจ้งเตือนแล้ว")


async def unsubscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db.execute("DELETE FROM subscribers WHERE chat_id = ?", (update.effective_chat.id,))
    db.commit()
    await update.message.reply_text("🔕 ยกเลิกการแจ้งเตือนแล้ว")


async def explain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ระบบนี้มี 4 ส่วน:\n"
        "1️⃣ *IoT* – บอร์ด Cucumber ติดบนพัดลม วัดการสั่น 200 ครั้ง/วินาที แล้วสรุปเป็นตัวเลขไม่กี่ตัว\n"
        "2️⃣ *MQTT* – ส่งตัวเลขเหล่านั้นผ่าน WiFi ไปยัง broker\n"
        "3️⃣ *AI* – โมเดล Random Forest ที่ฝึกจากข้อมูลจริง ทายว่าพัดลม ปกติ / ไม่สมดุล / หยุด\n"
        "4️⃣ *ผู้ใช้* – ผมเอง (Telegram) แจ้งเตือนเมื่อสถานะเปลี่ยนติดกัน 5 วินาที\n\n"
        "อุณหภูมิเกินกำหนดใช้ *กฎตายตัว* ไม่ใช้ AI เพราะเรื่องความปลอดภัยต้องตรวจสอบได้",
        parse_mode="Markdown")


async def alert_pusher(app: Application):
    """ตรวจตาราง alerts ทุก 2 วินาที แล้วส่งให้ผู้ที่ /subscribe ไว้"""
    while True:
        pending = db.execute("SELECT id, message FROM alerts WHERE sent = 0 ORDER BY id").fetchall()
        chats = [r["chat_id"] for r in db.execute("SELECT chat_id FROM subscribers")]
        for a in pending:
            for chat in chats:
                try:
                    await app.bot.send_message(chat, a["message"])
                except Exception as e:  # ผู้ใช้บล็อกบอท ฯลฯ
                    print("ส่งไม่สำเร็จ:", chat, e)
            db.execute("UPDATE alerts SET sent = 1 WHERE id = ?", (a["id"],))
        db.commit()
        await asyncio.sleep(2)


async def post_init(app: Application):
    # ข้ามการแจ้งเตือนเก่าที่ค้างตอนบอทปิดอยู่
    db.execute("UPDATE alerts SET sent = 1 WHERE sent = 0")
    db.commit()
    app.create_task(alert_pusher(app))


def main():
    if "PASTE" in config.TELEGRAM_TOKEN:
        raise SystemExit("ใส่ TELEGRAM_TOKEN ใน python/config.py ก่อน (ขอจาก @BotFather)")
    app = Application.builder().token(config.TELEGRAM_TOKEN).post_init(post_init).build()
    for name, fn in [("start", start), ("help", start), ("status", status), ("history", history),
                     ("subscribe", subscribe), ("unsubscribe", unsubscribe), ("explain", explain)]:
        app.add_handler(CommandHandler(name, fn))
    print("บอททำงานแล้ว — เปิด Telegram แล้วพิมพ์ /start")
    app.run_polling()


if __name__ == "__main__":
    main()
