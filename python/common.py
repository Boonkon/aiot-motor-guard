"""ค่าและฟังก์ชันที่ใช้ร่วมกันระหว่าง simulator / collect / train / gateway / bot"""
import os
import sqlite3
import sys

try:
    import config  # ไฟล์ของผู้เรียนเอง (ไม่อยู่บน GitHub)
except ImportError:
    import config_example as config
    if "pytest" not in sys.modules:
        print("[i] ไม่พบ config.py — ใช้ค่าจาก config_example.py ไปก่อน")

# ฟีเจอร์ที่บอร์ดส่งมาและโมเดลใช้ (ต้องตรงกับ devices/02_mqtt_features)
FEATURES = ["rms_x", "rms_y", "rms_z", "rms", "p2p", "crest", "f_dom", "temp"]
# อุณหภูมิไม่ใส่ให้โมเดล เพราะขึ้นกับอุณหภูมิห้องมากกว่าสภาพมอเตอร์ (โมเดลจะ "จำผิด" ได้)
# อุณหภูมิใช้ในกฎความปลอดภัยแทน — ดูบทเรียนที่ 4
MODEL_FEATURES = ["rms_x", "rms_y", "rms_z", "rms", "p2p", "crest", "f_dom"]
LABELS = ["normal", "unbalanced", "off"]
LABEL_TH = {"normal": "ปกติ", "unbalanced": "ไม่สมดุล/สั่นผิดปกติ", "off": "หยุดทำงาน",
            "unknown": "ไม่เคยเห็นรูปแบบนี้"}

TOPIC_TELEMETRY = "aiot/{device}/telemetry"
TOPIC_PREDICTION = "aiot/{device}/prediction"
TOPIC_ALERT = "aiot/{device}/alert"

HERE = os.path.dirname(os.path.abspath(__file__))


def path(p: str) -> str:
    """แปลง path สัมพัทธ์ใน config ให้อิงโฟลเดอร์ python/ เสมอ"""
    return p if os.path.isabs(p) else os.path.join(HERE, p)


def db_connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path(config.DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(path(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, device TEXT,
            rms_x REAL, rms_y REAL, rms_z REAL, rms REAL, p2p REAL,
            crest REAL, f_dom REAL, temp REAL, hum REAL,
            label TEXT, confidence REAL, anomaly REAL
        );
        CREATE INDEX IF NOT EXISTS idx_tel ON telemetry(device, ts);
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, device TEXT, kind TEXT, message TEXT, sent INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS subscribers (chat_id INTEGER PRIMARY KEY);
        """
    )
    return conn


def mqtt_client(name: str):
    import paho.mqtt.client as mqtt
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{name}-{os.getpid()}")
